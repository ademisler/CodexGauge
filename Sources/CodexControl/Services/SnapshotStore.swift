import Foundation

private struct SnapshotEnvelope: Codable {
    let snapshots: [String: AccountUsageSnapshot]
}

private struct LegacySnapshotEnvelope: Codable {
    let snapshots: [UUID: AccountUsageSnapshot]
}

struct SnapshotStore {
    func load() throws -> [UUID: AccountUsageSnapshot] {
        guard FileManager.default.fileExists(atPath: FileLocations.snapshotsFile.path) else {
            return [:]
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let data = try Data(contentsOf: FileLocations.snapshotsFile)

        if let decoded = try? decoder.decode(SnapshotEnvelope.self, from: data) {
            return Dictionary(uniqueKeysWithValues: decoded.snapshots.compactMap { key, value in
                UUID(uuidString: key).map { ($0, value) }
            })
        }

        if let decoded = try? decoder.decode(LegacySnapshotEnvelope.self, from: data) {
            return decoded.snapshots
        }

        throw CocoaError(.coderReadCorrupt)
    }

    func save(_ snapshots: [UUID: AccountUsageSnapshot]) throws {
        try FileLocations.ensureDirectories()
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        let stringKeyed = Dictionary(uniqueKeysWithValues: snapshots.map { ($0.key.uuidString, $0.value) })
        let data = try encoder.encode(SnapshotEnvelope(snapshots: stringKeyed))
        try data.write(to: FileLocations.snapshotsFile, options: .atomic)
    }
}
