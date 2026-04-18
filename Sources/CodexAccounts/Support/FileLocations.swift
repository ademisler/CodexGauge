import Foundation

enum FileLocations {
    static var appSupportDirectory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser
        return base.appendingPathComponent("CodexGauge", isDirectory: true)
    }

    static var legacyAppSupportDirectory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser
        return base.appendingPathComponent("CodexAccounts", isDirectory: true)
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

    static var ambientCodexHome: URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".codex", isDirectory: true)
    }

    static func ensureDirectories() throws {
        if !FileManager.default.fileExists(atPath: self.appSupportDirectory.path),
           FileManager.default.fileExists(atPath: self.legacyAppSupportDirectory.path)
        {
            try FileManager.default.moveItem(at: self.legacyAppSupportDirectory, to: self.appSupportDirectory)
        }
        try FileManager.default.createDirectory(at: self.appSupportDirectory, withIntermediateDirectories: true)
        try FileManager.default.createDirectory(at: self.managedHomesDirectory, withIntermediateDirectories: true)
    }
}
