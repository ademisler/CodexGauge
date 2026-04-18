import Darwin
import Foundation

enum CodexAccountManagerError: LocalizedError {
    case binaryMissing
    case loginFailed(String)
    case loginTimedOut
    case loginCancelled
    case launchFailed(String)
    case missingIdentity
    case missingAuth
    case unsafeDeletePath

    var errorDescription: String? {
        switch self {
        case .binaryMissing:
            return "The `codex` command could not be found."
        case let .loginFailed(output):
            return "The Codex sign-in flow did not complete.\n\(output)"
        case .loginTimedOut:
            return "The Codex sign-in flow timed out."
        case .loginCancelled:
            return "Account setup cancelled."
        case let .launchFailed(message):
            return "Failed to start the Codex sign-in flow: \(message)"
        case .missingIdentity:
            return "Sign-in completed, but the account identity could not be read."
        case .missingAuth:
            return "The selected account does not contain `auth.json`."
        case .unsafeDeletePath:
            return "This path is not an app-managed home directory."
        }
    }
}

struct CodexLoginResult {
    enum Outcome {
        case success
        case timedOut
        case cancelled
        case failed(status: Int32)
        case missingBinary
        case launchFailed(String)
    }

    let outcome: Outcome
    let output: String
}

struct CodexSwitchResult {
    let materializedAccount: StoredAccount?
    let backupPath: String?
}

private final class ManagedLoginProcess: @unchecked Sendable {
    private let lock = NSLock()
    private var process: Process?

    func bind(_ process: Process) {
        self.lock.lock()
        self.process = process
        self.lock.unlock()
    }

    func clear() {
        self.lock.lock()
        self.process = nil
        self.lock.unlock()
    }

    func cancel() {
        self.lock.lock()
        let process = self.process
        self.lock.unlock()

        guard let process, process.isRunning else {
            return
        }

        process.interrupt()
        process.terminate()

        let pid = process.processIdentifier
        DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + 0.75) {
            guard process.isRunning, pid > 0 else {
                return
            }
            kill(pid, SIGKILL)
        }
    }
}

enum CodexLoginRunner {
    static func run(homePath: String, timeout: TimeInterval = 180) async -> CodexLoginResult {
        let loginProcess = ManagedLoginProcess()

        return await withTaskCancellationHandler {
            guard let binary = CodexBinaryLocator.resolve() else {
                return CodexLoginResult(outcome: .missingBinary, output: "")
            }

            var env = ProcessInfo.processInfo.environment
            env["CODEX_HOME"] = homePath

            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = [binary, "login"]
            process.environment = env

            let stdout = Pipe()
            let stderr = Pipe()
            process.standardOutput = stdout
            process.standardError = stderr

            do {
                try process.run()
            } catch {
                return CodexLoginResult(outcome: .launchFailed(error.localizedDescription), output: "")
            }
            loginProcess.bind(process)
            defer {
                loginProcess.clear()
            }

            let timedOut = await self.wait(for: process, timeout: timeout)
            if timedOut, process.isRunning {
                process.terminate()
            }

            let output = await self.combinedOutput(stdout: stdout, stderr: stderr)
            if Task.isCancelled {
                return CodexLoginResult(outcome: .cancelled, output: output)
            }
            if timedOut {
                return CodexLoginResult(outcome: .timedOut, output: output)
            }

            if process.terminationStatus == 0 {
                return CodexLoginResult(outcome: .success, output: output)
            }

            return CodexLoginResult(outcome: .failed(status: process.terminationStatus), output: output)
        } onCancel: {
            loginProcess.cancel()
        }
    }

    private static func wait(for process: Process, timeout: TimeInterval) async -> Bool {
        await withTaskGroup(of: Bool.self) { group in
            group.addTask {
                process.waitUntilExit()
                return false
            }
            group.addTask {
                let nanoseconds = UInt64(max(0, timeout) * 1_000_000_000)
                try? await Task.sleep(nanoseconds: nanoseconds)
                return true
            }

            let result = await group.next() ?? false
            group.cancelAll()
            return result
        }
    }

    private static func combinedOutput(stdout: Pipe, stderr: Pipe) async -> String {
        async let stdoutData = self.readToEnd(stdout)
        async let stderrData = self.readToEnd(stderr)
        let merged = await [stdoutData, stderrData]
            .compactMap { $0.isEmpty ? nil : $0 }
            .joined(separator: "\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        return merged.isEmpty ? "No output captured." : String(merged.prefix(4000))
    }

    private static func readToEnd(_ pipe: Pipe) async -> String {
        if #available(macOS 13.0, *),
           let data = try? pipe.fileHandleForReading.readToEnd(),
           let text = String(data: data, encoding: .utf8)
        {
            return text
        }

        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        return String(data: data, encoding: .utf8) ?? ""
    }
}

struct CodexAccountManager {
    func addManagedAccount() async throws -> StoredAccount {
        try FileLocations.ensureDirectories()
        let homeURL = FileLocations.managedHomesDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: homeURL, withIntermediateDirectories: true)

        do {
            let account = try await self.authenticateAccount(homeURL: homeURL, source: .managedByApp)
            return account
        } catch {
            try? FileManager.default.removeItem(at: homeURL)
            throw error
        }
    }

    func reauthenticate(_ account: StoredAccount) async throws -> StoredAccount {
        let homeURL = URL(fileURLWithPath: account.codexHomePath, isDirectory: true)
        return try await self.authenticateAccount(homeURL: homeURL, source: account.source, existing: account)
    }

    func loadActiveIdentity() -> AuthBackedIdentity? {
        let authURL = FileLocations.ambientCodexHome.appendingPathComponent("auth.json", isDirectory: false)
        guard FileManager.default.fileExists(atPath: authURL.path) else {
            return nil
        }

        return try? CodexAPI.loadIdentity(codexHomePath: FileLocations.ambientCodexHome.path)
    }

    func removeManagedFilesIfOwned(_ account: StoredAccount) throws {
        guard account.source.ownsFiles else {
            return
        }

        let root = FileLocations.managedHomesDirectory.standardizedFileURL.path
        let target = URL(fileURLWithPath: account.codexHomePath, isDirectory: true).standardizedFileURL.path
        let prefix = root.hasSuffix("/") ? root : root + "/"
        guard target.hasPrefix(prefix) else {
            throw CodexAccountManagerError.unsafeDeletePath
        }

        if FileManager.default.fileExists(atPath: target) {
            try FileManager.default.removeItem(atPath: target)
        }
    }

    func discoverManagedAccounts(existing: [StoredAccount]) throws -> [StoredAccount] {
        try FileLocations.ensureDirectories()
        let homeURLs = try FileManager.default.contentsOfDirectory(
            at: FileLocations.managedHomesDirectory,
            includingPropertiesForKeys: [.creationDateKey, .contentModificationDateKey],
            options: [.skipsHiddenFiles])

        return homeURLs.compactMap { homeURL in
            self.discoveredManagedAccount(at: homeURL, existing: existing)
        }
    }

    func discoverAmbientAccount(existing: [StoredAccount]) throws -> StoredAccount? {
        let homeURL = FileLocations.ambientCodexHome
        let authURL = homeURL.appendingPathComponent("auth.json", isDirectory: false)
        guard FileManager.default.fileExists(atPath: authURL.path) else {
            return nil
        }

        guard let identity = try? CodexAPI.loadIdentity(codexHomePath: homeURL.path),
              identity.email != nil || identity.providerAccountID != nil
        else {
            return nil
        }

        let discoveredAt = self.directoryTimestamp(for: homeURL)
        let candidate = StoredAccount(
            id: UUID(),
            nickname: nil,
            emailHint: identity.email,
            authSubject: identity.authSubject,
            providerAccountID: identity.providerAccountID,
            codexHomePath: homeURL.path,
            source: .ambient,
            createdAt: discoveredAt,
            updatedAt: discoveredAt,
            lastAuthenticatedAt: discoveredAt)

        let matchedExisting = existing.first(where: { $0.matches(candidate) })

        return StoredAccount(
            id: matchedExisting?.id ?? UUID(),
            nickname: matchedExisting?.nickname,
            emailHint: identity.email ?? matchedExisting?.emailHint,
            authSubject: identity.authSubject ?? matchedExisting?.authSubject,
            providerAccountID: identity.providerAccountID ?? matchedExisting?.providerAccountID,
            codexHomePath: homeURL.path,
            source: .ambient,
            createdAt: matchedExisting?.createdAt ?? discoveredAt,
            updatedAt: max(matchedExisting?.updatedAt ?? .distantPast, discoveredAt),
            lastAuthenticatedAt: max(matchedExisting?.lastAuthenticatedAt ?? .distantPast, discoveredAt))
    }

    func switchActiveAccount(_ target: StoredAccount, existing: [StoredAccount]) throws -> CodexSwitchResult {
        try FileLocations.ensureDirectories()

        let targetHomeURL = URL(fileURLWithPath: target.codexHomePath, isDirectory: true)
        let targetAuthURL = targetHomeURL.appendingPathComponent("auth.json", isDirectory: false)
        guard FileManager.default.fileExists(atPath: targetAuthURL.path) else {
            throw CodexAccountManagerError.missingAuth
        }

        let ambientHomeURL = FileLocations.ambientCodexHome.standardizedFileURL
        let standardizedTargetHomeURL = targetHomeURL.standardizedFileURL
        if standardizedTargetHomeURL == ambientHomeURL {
            return CodexSwitchResult(materializedAccount: nil, backupPath: nil)
        }

        let ambientAccount = try self.discoverAmbientAccount(existing: existing)
        let materializedAccount: StoredAccount?
        if let ambientAccount, ambientAccount.source == .ambient, !ambientAccount.matches(target) {
            materializedAccount = try self.materializeAsManaged(ambientAccount)
        } else {
            materializedAccount = nil
        }

        try FileManager.default.createDirectory(at: FileLocations.ambientCodexHome, withIntermediateDirectories: true)
        let ambientAuthURL = FileLocations.ambientCodexHome.appendingPathComponent("auth.json", isDirectory: false)
        let backupPath = try self.backupAmbientAuth()
        let stagedAuthURL = FileLocations.ambientCodexHome.appendingPathComponent(".auth.staged.json", isDirectory: false)
        if FileManager.default.fileExists(atPath: stagedAuthURL.path) {
            try FileManager.default.removeItem(at: stagedAuthURL)
        }
        try FileManager.default.copyItem(at: targetAuthURL, to: stagedAuthURL)

        if FileManager.default.fileExists(atPath: ambientAuthURL.path) {
            _ = try FileManager.default.replaceItemAt(ambientAuthURL, withItemAt: stagedAuthURL)
        } else {
            try FileManager.default.moveItem(at: stagedAuthURL, to: ambientAuthURL)
        }

        return CodexSwitchResult(
            materializedAccount: materializedAccount,
            backupPath: backupPath)
    }

    private func authenticateAccount(
        homeURL: URL,
        source: StoredAccountSource,
        existing: StoredAccount? = nil) async throws -> StoredAccount
    {
        let result = await CodexLoginRunner.run(homePath: homeURL.path)

        switch result.outcome {
        case .success:
            break
        case .cancelled:
            throw CodexAccountManagerError.loginCancelled
        case .missingBinary:
            throw CodexAccountManagerError.binaryMissing
        case .timedOut:
            throw CodexAccountManagerError.loginTimedOut
        case let .launchFailed(message):
            throw CodexAccountManagerError.launchFailed(message)
        case .failed:
            throw CodexAccountManagerError.loginFailed(result.output)
        }

        let identity = try CodexAPI.loadIdentity(codexHomePath: homeURL.path)
        guard identity.email != nil || identity.providerAccountID != nil else {
            throw CodexAccountManagerError.missingIdentity
        }

        let now = Date()
        return StoredAccount(
            id: existing?.id ?? UUID(),
            nickname: existing?.nickname,
            emailHint: identity.email ?? existing?.emailHint,
            authSubject: identity.authSubject ?? existing?.authSubject,
            providerAccountID: identity.providerAccountID ?? existing?.providerAccountID,
            codexHomePath: homeURL.path,
            source: source,
            createdAt: existing?.createdAt ?? now,
            updatedAt: now,
            lastAuthenticatedAt: now)
    }

    private func discoveredManagedAccount(at homeURL: URL, existing: [StoredAccount]) -> StoredAccount? {
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: homeURL.path, isDirectory: &isDirectory), isDirectory.boolValue else {
            return nil
        }

        let authURL = homeURL.appendingPathComponent("auth.json", isDirectory: false)
        guard FileManager.default.fileExists(atPath: authURL.path) else {
            return nil
        }

        guard let identity = try? CodexAPI.loadIdentity(codexHomePath: homeURL.path),
              identity.email != nil || identity.providerAccountID != nil
        else {
            return nil
        }

        let discoveredAt = self.directoryTimestamp(for: homeURL)
        let candidate = StoredAccount(
            id: UUID(),
            nickname: nil,
            emailHint: identity.email,
            authSubject: identity.authSubject,
            providerAccountID: identity.providerAccountID,
            codexHomePath: homeURL.path,
            source: .managedByApp,
            createdAt: discoveredAt,
            updatedAt: discoveredAt,
            lastAuthenticatedAt: discoveredAt)

        let matchedExisting = existing.first(where: { $0.matches(candidate) })

        return StoredAccount(
            id: matchedExisting?.id ?? UUID(),
            nickname: matchedExisting?.nickname,
            emailHint: identity.email ?? matchedExisting?.emailHint,
            authSubject: identity.authSubject ?? matchedExisting?.authSubject,
            providerAccountID: identity.providerAccountID ?? matchedExisting?.providerAccountID,
            codexHomePath: homeURL.path,
            source: .managedByApp,
            createdAt: matchedExisting?.createdAt ?? discoveredAt,
            updatedAt: max(matchedExisting?.updatedAt ?? .distantPast, discoveredAt),
            lastAuthenticatedAt: max(matchedExisting?.lastAuthenticatedAt ?? .distantPast, discoveredAt))
    }

    private func materializeAsManaged(_ account: StoredAccount) throws -> StoredAccount {
        try FileLocations.ensureDirectories()

        let sourceHomeURL = URL(fileURLWithPath: account.codexHomePath, isDirectory: true)
        let sourceAuthURL = sourceHomeURL.appendingPathComponent("auth.json", isDirectory: false)
        guard FileManager.default.fileExists(atPath: sourceAuthURL.path) else {
            throw CodexAccountManagerError.missingAuth
        }

        let destinationHomeURL = FileLocations.managedHomesDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: destinationHomeURL, withIntermediateDirectories: true)
        try FileManager.default.copyItem(
            at: sourceAuthURL,
            to: destinationHomeURL.appendingPathComponent("auth.json", isDirectory: false))

        let now = Date()
        return StoredAccount(
            id: account.id,
            nickname: account.nickname,
            emailHint: account.emailHint,
            authSubject: account.authSubject,
            providerAccountID: account.providerAccountID,
            codexHomePath: destinationHomeURL.path,
            source: .managedByApp,
            createdAt: account.createdAt,
            updatedAt: now,
            lastAuthenticatedAt: account.lastAuthenticatedAt ?? now)
    }

    private func backupAmbientAuth() throws -> String? {
        try FileLocations.ensureDirectories()

        let ambientAuthURL = FileLocations.ambientCodexHome.appendingPathComponent("auth.json", isDirectory: false)
        guard FileManager.default.fileExists(atPath: ambientAuthURL.path) else {
            return nil
        }

        let backupURL = FileLocations.authBackupsDirectory
            .appendingPathComponent(
                "ambient-auth-\(self.timestampSlug())-\(UUID().uuidString.lowercased()).json",
                isDirectory: false)
        try FileManager.default.copyItem(at: ambientAuthURL, to: backupURL)
        return backupURL.path
    }

    private func directoryTimestamp(for homeURL: URL) -> Date {
        let values = try? homeURL.resourceValues(forKeys: [.creationDateKey, .contentModificationDateKey])
        return values?.contentModificationDate
            ?? values?.creationDate
            ?? Date()
    }

    private func timestampSlug() -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyyMMdd-HHmmss"
        return formatter.string(from: Date())
    }
}
