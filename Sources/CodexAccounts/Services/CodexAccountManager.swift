import Darwin
import Foundation

enum CodexAccountManagerError: LocalizedError {
    case binaryMissing
    case loginFailed(String)
    case loginTimedOut
    case loginCancelled
    case launchFailed(String)
    case missingIdentity
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
            providerAccountID: identity.providerAccountID ?? existing?.providerAccountID,
            codexHomePath: homeURL.path,
            source: source,
            createdAt: existing?.createdAt ?? now,
            updatedAt: now,
            lastAuthenticatedAt: now)
    }
}
