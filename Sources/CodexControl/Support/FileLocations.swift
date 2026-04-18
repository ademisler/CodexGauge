import Foundation

enum FileLocations {
    static var appSupportDirectory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser
        return base.appendingPathComponent("CodexControl", isDirectory: true)
    }

    static var legacyAppSupportDirectories: [URL] {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser
        return [
            base.appendingPathComponent(["Codex", "Gauge"].joined(), isDirectory: true),
            base.appendingPathComponent(["Codex", "Accounts"].joined(), isDirectory: true),
        ]
    }

    static var accountsFile: URL {
        self.appSupportDirectory.appendingPathComponent("accounts.json", isDirectory: false)
    }

    static var snapshotsFile: URL {
        self.appSupportDirectory.appendingPathComponent("snapshots.json", isDirectory: false)
    }

    static var managedHomesDirectory: URL {
        self.appSupportDirectory.appendingPathComponent("managed-homes", isDirectory: true)
    }

    static var authBackupsDirectory: URL {
        self.appSupportDirectory.appendingPathComponent("auth-backups", isDirectory: true)
    }

    static var ambientCodexHome: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex", isDirectory: true)
    }

    static func ensureDirectories() throws {
        if !FileManager.default.fileExists(atPath: self.appSupportDirectory.path) {
            for legacyDirectory in self.legacyAppSupportDirectories where FileManager.default.fileExists(atPath: legacyDirectory.path) {
                try FileManager.default.moveItem(at: legacyDirectory, to: self.appSupportDirectory)
                break
            }
        }
        try FileManager.default.createDirectory(at: self.appSupportDirectory, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: self.managedHomesDirectory, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: self.authBackupsDirectory, withIntermediateDirectories: true)
    }
}
