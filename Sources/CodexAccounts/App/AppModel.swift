import AppKit
import Foundation

@MainActor
final class AppModel: ObservableObject {
    @Published private(set) var accounts: [StoredAccount] = []
    @Published private(set) var runtimeStates: [UUID: AccountRuntimeState] = [:]
    @Published var selectedAccountID: UUID?
    @Published var searchText = ""
    @Published private(set) var isRefreshingAll = false
    @Published private(set) var isAddingAccount = false
    @Published private(set) var reauthenticatingAccountID: UUID?
    @Published var pendingRemovalAccount: StoredAccount?
    @Published var statusMessage: String?

    private let accountStore = AccountStore()
    private let snapshotStore = SnapshotStore()
    private let accountManager = CodexAccountManager()
    private let autoRefreshInterval: TimeInterval = 5 * 60
    private var autoRefreshTask: Task<Void, Never>?
    private var addAccountTask: Task<Void, Never>?

    init() {
        self.loadInitialAccounts()
        self.autoRefreshTask = Task { [weak self] in
            await self?.autoRefreshLoop()
        }
        Task { [weak self] in
            await self?.refreshAll()
        }
    }

    deinit {
        self.autoRefreshTask?.cancel()
        self.addAccountTask?.cancel()
    }

    var filteredAccounts: [StoredAccount] {
        let trimmedQuery = self.searchText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()

        let filtered = self.accounts.filter { account in
            guard !trimmedQuery.isEmpty else { return true }
            let haystacks = [
                account.displayName,
                account.emailHint ?? "",
                account.providerAccountID ?? "",
                account.codexHomePath,
            ]
            return haystacks.contains { $0.lowercased().contains(trimmedQuery) }
        }

        return filtered.sorted { left, right in
            let leftSnapshot = self.runtimeStates[left.id]?.snapshot
            let rightSnapshot = self.runtimeStates[right.id]?.snapshot

            let leftPriority = leftSnapshot?.sortPriority ?? 2
            let rightPriority = rightSnapshot?.sortPriority ?? 2
            if leftPriority != rightPriority {
                return leftPriority < rightPriority
            }

            switch (leftSnapshot, rightSnapshot) {
            case let (.some(leftSnapshot), .some(rightSnapshot)):
                if leftSnapshot.hasUsableQuotaNow && rightSnapshot.hasUsableQuotaNow {
                    let leftRemaining = leftSnapshot.lowestRemainingPercent
                    let rightRemaining = rightSnapshot.lowestRemainingPercent
                    if leftRemaining != rightRemaining {
                        return leftRemaining > rightRemaining
                    }

                    let leftReset = leftSnapshot.nextResetAt ?? .distantFuture
                    let rightReset = rightSnapshot.nextResetAt ?? .distantFuture
                    if leftReset != rightReset {
                        return leftReset < rightReset
                    }
                } else {
                    let leftReset = leftSnapshot.nextResetAt ?? .distantFuture
                    let rightReset = rightSnapshot.nextResetAt ?? .distantFuture
                    if leftReset != rightReset {
                        return leftReset < rightReset
                    }
                }
            case (.some, .none):
                return true
            case (.none, .some):
                return false
            case (.none, .none):
                break
            }

            return left.displayName.localizedCaseInsensitiveCompare(right.displayName) == .orderedAscending
        }
    }

    var selectedAccount: StoredAccount? {
        guard let selectedAccountID else {
            return self.filteredAccounts.first ?? self.accounts.first
        }
        return self.accounts.first(where: { $0.id == selectedAccountID })
    }

    var accountCount: Int {
        self.accounts.count
    }

    var lowQuotaCount: Int {
        self.accounts.filter {
            (self.runtimeStates[$0.id]?.snapshot?.lowestRemainingPercent ?? 101) <= 20
        }.count
    }

    var healthyCount: Int {
        max(0, self.accountCount - self.lowQuotaCount)
    }

    var menuBarLabel: String {
        if self.lowQuotaCount > 0 {
            return "!\(self.lowQuotaCount)"
        }
        return "\(self.accountCount)"
    }

    var menuBarSymbol: String {
        if self.lowQuotaCount > 0 {
            return "exclamationmark.circle.fill"
        }
        if self.isRefreshingAll {
            return "arrow.triangle.2.circlepath"
        }
        return "circle.grid.2x1.fill"
    }

    func runtimeState(for accountID: UUID) -> AccountRuntimeState {
        self.runtimeStates[accountID] ?? AccountRuntimeState()
    }

    func refreshAll() async {
        guard !self.accounts.isEmpty, !self.isRefreshingAll else {
            return
        }

        self.isRefreshingAll = true
        let snapshot = self.accounts
        for account in snapshot {
            var state = self.runtimeStates[account.id] ?? AccountRuntimeState()
            state.isLoading = true
            self.runtimeStates[account.id] = state
        }

        defer {
            self.isRefreshingAll = false
        }

        await withTaskGroup(of: (UUID, Result<AccountUsageSnapshot, Error>).self) { group in
            for account in snapshot {
                group.addTask {
                    do {
                        return (account.id, .success(try await CodexAPI.fetchSnapshot(for: account)))
                    } catch {
                        return (account.id, .failure(error))
                    }
                }
            }

            for await (accountID, result) in group {
                self.applyRefreshResult(result, to: accountID)
            }
        }
    }

    func refresh(account: StoredAccount) async {
        var state = self.runtimeStates[account.id] ?? AccountRuntimeState()
        guard !state.isLoading else {
            return
        }

        state.isLoading = true
        self.runtimeStates[account.id] = state

        do {
            let snapshot = try await CodexAPI.fetchSnapshot(for: account)
            self.applyRefreshResult(.success(snapshot), to: account.id)
        } catch {
            self.applyRefreshResult(.failure(error), to: account.id)
        }
    }

    func startAddAccount() {
        guard !self.isAddingAccount, self.addAccountTask == nil else {
            return
        }

        self.addAccountTask = Task { [weak self] in
            await self?.addAccount()
        }
    }

    func cancelAddAccount() {
        guard self.isAddingAccount else {
            return
        }

        self.statusMessage = "Cancelling account setup."
        self.addAccountTask?.cancel()
    }

    private func addAccount() async {
        self.isAddingAccount = true
        self.statusMessage = "Complete or cancel the Codex sign-in flow in your browser."
        defer {
            self.isAddingAccount = false
            self.addAccountTask = nil
        }

        do {
            let account = try await self.accountManager.addManagedAccount()
            self.accounts = self.accountStore.merge(existing: self.accounts, incoming: [account])
            try self.accountStore.saveAccounts(self.accounts)
            self.selectedAccountID = self.accounts.first(where: { $0.matches(account) })?.id ?? account.id
            self.statusMessage = "\(account.displayName) added."
            if let selectedAccount = self.selectedAccount {
                await self.refresh(account: selectedAccount)
            }
        } catch is CancellationError {
            self.statusMessage = "Account setup cancelled."
        } catch {
            self.statusMessage = error.localizedDescription
        }
    }

    func reauthenticate(_ account: StoredAccount) async {
        guard self.reauthenticatingAccountID == nil else {
            return
        }

        self.reauthenticatingAccountID = account.id
        self.statusMessage = "Waiting for \(account.displayName) to sign in again."
        defer {
            self.reauthenticatingAccountID = nil
        }

        do {
            let updated = try await self.accountManager.reauthenticate(account)
            self.mergeAccount(updated)
            try self.accountStore.saveAccounts(self.accounts)
            self.statusMessage = "\(updated.displayName) reauthenticated."
            if let refreshed = self.accounts.first(where: { $0.id == account.id }) {
                await self.refresh(account: refreshed)
            }
        } catch {
            self.statusMessage = error.localizedDescription
        }
    }

    func updateNickname(for accountID: UUID, nickname: String) {
        guard let index = self.accounts.firstIndex(where: { $0.id == accountID }) else {
            return
        }

        self.accounts[index].nickname = nickname.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? nil
            : nickname.trimmingCharacters(in: .whitespacesAndNewlines)
        self.accounts[index].updatedAt = Date()
        self.persistAccountsSilently()
    }

    func requestRemoval(of account: StoredAccount) {
        self.pendingRemovalAccount = account
    }

    func confirmPendingRemoval() {
        guard let account = self.pendingRemovalAccount else {
            return
        }
        self.pendingRemovalAccount = nil
        self.remove(account)
    }

    func cancelPendingRemoval() {
        self.pendingRemovalAccount = nil
    }

    func openFolder(for account: StoredAccount) {
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: account.codexHomePath, isDirectory: true)])
    }

    private func loadInitialAccounts() {
        do {
            let loadedAccounts = try self.accountStore.loadAccounts()
            let storedAccounts = loadedAccounts.filter { $0.source != .ambient }
            let discoveredManagedAccounts = try self.accountManager.discoverManagedAccounts(existing: storedAccounts)
            self.accounts = self.accountStore.merge(existing: storedAccounts, incoming: discoveredManagedAccounts)
            if self.accounts != storedAccounts {
                try self.accountStore.saveAccounts(self.accounts)
            }
            self.ensureSelection()
        } catch {
            self.statusMessage = error.localizedDescription
        }
    }

    private func mergeAccount(_ account: StoredAccount) {
        self.accounts = self.accountStore.merge(existing: self.accounts, incoming: [account])
        self.ensureSelection()
    }

    private func remove(_ account: StoredAccount) {
        self.accounts.removeAll { $0.id == account.id }
        self.runtimeStates.removeValue(forKey: account.id)

        do {
            try self.accountManager.removeManagedFilesIfOwned(account)
            try self.accountStore.saveAccounts(self.accounts)
            self.ensureSelection()
            self.statusMessage = "\(account.displayName) removed."
        } catch {
            self.statusMessage = error.localizedDescription
        }
    }

    private func applyRefreshResult(_ result: Result<AccountUsageSnapshot, Error>, to accountID: UUID) {
        var state = self.runtimeStates[accountID] ?? AccountRuntimeState()
        state.isLoading = false

        switch result {
        case let .success(snapshot):
            state.snapshot = snapshot
            state.errorMessage = nil
            self.runtimeStates[accountID] = state
            self.updateAccountMetadata(accountID: accountID, snapshot: snapshot)
            self.persistSnapshotsSilently()
        case let .failure(error):
            state.snapshot = nil
            state.errorMessage = error.localizedDescription
            self.runtimeStates[accountID] = state
            self.persistSnapshotsSilently()
        }
    }

    private func updateAccountMetadata(accountID: UUID, snapshot: AccountUsageSnapshot) {
        guard let index = self.accounts.firstIndex(where: { $0.id == accountID }) else {
            return
        }

        let normalizedEmail = StoredAccount.normalizeEmail(snapshot.email)
        var didChange = false

        if self.accounts[index].emailHint != normalizedEmail, let normalizedEmail {
            self.accounts[index].emailHint = normalizedEmail
            didChange = true
        }
        if self.accounts[index].providerAccountID != snapshot.providerAccountID,
           let providerAccountID = snapshot.providerAccountID
        {
            self.accounts[index].providerAccountID = providerAccountID
            didChange = true
        }
        if didChange {
            self.accounts[index].updatedAt = Date()
            self.persistAccountsSilently()
        }
    }

    private func persistAccountsSilently() {
        do {
            try self.accountStore.saveAccounts(self.accounts)
        } catch {
            self.statusMessage = error.localizedDescription
        }
    }

    private func persistSnapshotsSilently() {
        let snapshots = self.runtimeStates.compactMapValues(\.snapshot)
        do {
            try self.snapshotStore.save(snapshots)
        } catch {
            self.statusMessage = error.localizedDescription
        }
    }

    private func ensureSelection() {
        if let selectedAccountID, self.accounts.contains(where: { $0.id == selectedAccountID }) {
            return
        }
        self.selectedAccountID = self.filteredAccounts.first?.id ?? self.accounts.first?.id
    }

    private func autoRefreshLoop() async {
        while !Task.isCancelled {
            let nanoseconds = UInt64(self.autoRefreshInterval * 1_000_000_000)
            try? await Task.sleep(nanoseconds: nanoseconds)
            await self.refreshAll()
        }
    }
}
