import Foundation

enum CodexBinaryLocator {
    static func resolve() -> String? {
        for candidate in self.pathCandidates() where FileManager.default.isExecutableFile(atPath: candidate) {
            return candidate
        }

        return self.resolveFromLoginShell()
    }

    private static func pathCandidates() -> [String] {
        var candidates: [String] = []
        let envPath = ProcessInfo.processInfo.environment["PATH"] ?? ""

        for component in envPath.split(separator: ":").map(String.init) where !component.isEmpty {
            candidates.append(URL(fileURLWithPath: component).appendingPathComponent("codex", isDirectory: false).path)
        }

        let home = FileManager.default.homeDirectoryForCurrentUser.path
        candidates.append(contentsOf: [
            "/opt/homebrew/bin/codex",
            "/usr/local/bin/codex",
            "/usr/bin/codex",
            "\(home)/.bun/bin/codex",
            "\(home)/.npm-global/bin/codex",
        ])

        return Array(NSOrderedSet(array: candidates)) as? [String] ?? candidates
    }

    private static func resolveFromLoginShell() -> String? {
        let process = Process()
        let output = Pipe()
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = ["-lc", "command -v codex"]
        process.standardOutput = output
        process.standardError = Pipe()

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return nil
        }

        guard process.terminationStatus == 0,
              let data = try? output.fileHandleForReading.readToEnd(),
              let text = String(data: data, encoding: .utf8)?
                  .trimmingCharacters(in: .whitespacesAndNewlines),
              !text.isEmpty
        else {
            return nil
        }

        return text
    }
}
