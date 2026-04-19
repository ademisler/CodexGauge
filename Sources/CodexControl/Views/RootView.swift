import SwiftUI

struct RootView: View {
    @ObservedObject var model: AppModel
    @ObservedObject var appUpdater: AppUpdater

    var body: some View {
        ZStack {
            VStack(spacing: 10) {
                self.header
                self.searchBar
                self.accountList
            }
            .allowsHitTesting(self.model.pendingRemovalAccount == nil)

            if let pendingRemovalAccount = self.model.pendingRemovalAccount {
                self.removalOverlay(for: pendingRemovalAccount)
            }
        }
        .padding(12)
        .frame(width: 430, height: 580)
        .background(Color(NSColor.windowBackgroundColor))
    }

    private var header: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text("Codex")
                    .font(.system(size: 14, weight: .semibold))
                Text(self.headerStatusText)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer()

            HStack(spacing: 8) {
                HeaderIconButton(
                    systemName: "plus",
                    action: { self.model.startAddAccount() },
                    alternateSystemName: "xmark",
                    isActive: self.model.isAddingAccount,
                    activeAction: { self.model.cancelAddAccount() })
                    .help(self.model.isAddingAccount ? "Cancel account setup" : "Add account")

                HeaderIconButton(
                    systemName: "arrow.clockwise",
                    action: { Task { await self.model.refreshAll() } })
                    .help("Refresh all accounts")
                    .disabled(self.model.isRefreshingAll)

                HeaderIconButton(
                    systemName: "arrow.down.circle",
                    action: { self.appUpdater.checkForUpdates() })
                    .help("Check for updates")
                    .disabled(!self.appUpdater.canCheckForUpdates)
            }
        }
        .padding(.horizontal, 2)
    }

    private var searchBar: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundStyle(.secondary)

            TextField("Search accounts", text: self.$model.searchText)
                .textFieldStyle(.plain)

            if !self.model.searchText.isEmpty {
                Button {
                    self.model.searchText = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(NSColor.controlBackgroundColor)))
    }

    @ViewBuilder
    private var accountList: some View {
        if self.model.filteredAccounts.isEmpty {
            ContentUnavailableView(
                "No Accounts",
                systemImage: "tray",
                description: Text("Add a Codex account to start tracking quota."))
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            ScrollView {
                LazyVStack(spacing: 10) {
                    ForEach(self.model.filteredAccounts) { account in
                        let isSelected = self.model.selectedAccountID == account.id
                        let nextSelection = isSelected ? nil : account.id

                        AccountRowView(
                            account: account,
                            state: self.model.runtimeState(for: account.id),
                            isActive: self.model.isActiveAccount(account),
                            canSwitch: self.model.canSwitchAccount(account),
                            isSelected: isSelected,
                            isReauthenticating: self.model.reauthenticatingAccountID == account.id,
                            onSelect: {
                                self.model.selectedAccountID = nextSelection
                            },
                            onSaveNickname: { self.model.updateNickname(for: account.id, nickname: $0) },
                            onRefresh: { Task { await self.model.refresh(account: account) } },
                            onSwitch: { Task { await self.model.switchAccount(account) } },
                            onReauthenticate: { Task { await self.model.reauthenticate(account) } },
                            onOpenFolder: { self.model.openFolder(for: account) },
                            onRemove: { self.model.requestRemoval(of: account) })
                    }
                }
                .padding(.vertical, 4)
            }
        }
    }

    private var headerStatusText: String {
        if let statusMessage = self.model.statusMessage, !statusMessage.isEmpty {
            return statusMessage
        }

        let lowQuotaCount = self.model.lowQuotaCount
        if lowQuotaCount > 0 {
            return "\(self.model.accountCount) accounts, \(lowQuotaCount) critical"
        }
        return "\(self.model.accountCount) accounts"
    }

    private func removalOverlay(for account: StoredAccount) -> some View {
        ZStack {
            Color.black.opacity(0.16)
                .ignoresSafeArea()
                .onTapGesture {
                    self.model.cancelPendingRemoval()
                }

            VStack(alignment: .leading, spacing: 12) {
                Text("Remove Account")
                    .font(.system(size: 14, weight: .semibold))

                Text("\(account.displayName) will be removed from CodexControl.")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)

                HStack(spacing: 8) {
                    Spacer()

                    Button("Cancel") {
                        self.model.cancelPendingRemoval()
                    }
                    .buttonStyle(.plain)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(
                        Capsule(style: .continuous)
                            .fill(Color(NSColor.controlBackgroundColor)))

                    Button("Remove") {
                        self.model.confirmPendingRemoval()
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(
                        Capsule(style: .continuous)
                            .fill(Color.red))
                }
            }
            .padding(14)
            .frame(width: 300, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(Color(NSColor.windowBackgroundColor)))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(Color.primary.opacity(0.08), lineWidth: 1))
            .shadow(color: Color.black.opacity(0.14), radius: 18, y: 6)
        }
    }
}

private struct HeaderIconButton: View {
    let defaultSystemName: String
    let action: () -> Void
    var alternateSystemName: String?
    var isActive = false
    var activeAction: (() -> Void)?

    init(
        systemName: String,
        action: @escaping () -> Void,
        alternateSystemName: String? = nil,
        isActive: Bool = false,
        activeAction: (() -> Void)? = nil)
    {
        self.defaultSystemName = systemName
        self.action = action
        self.alternateSystemName = alternateSystemName
        self.isActive = isActive
        self.activeAction = activeAction
    }

    var body: some View {
        Button(action: self.currentAction) {
            Image(systemName: self.currentSystemName)
                .font(.system(size: 13, weight: .semibold))
                .frame(width: 28, height: 28)
                .background(
                    RoundedRectangle(cornerRadius: 9, style: .continuous)
                        .fill(self.isActive ? Color.accentColor.opacity(0.16) : Color(NSColor.controlBackgroundColor)))
        }
        .buttonStyle(.plain)
    }

    private var currentAction: () -> Void {
        if self.isActive, let activeAction {
            return activeAction
        }
        return self.action
    }

    private var currentSystemName: String {
        if self.isActive, let alternateSystemName {
            return alternateSystemName
        }
        return self.defaultSystemName
    }
}
