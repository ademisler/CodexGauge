// swift-tools-version: 6.1

import Foundation
import PackageDescription

let packageRoot = URL(fileURLWithPath: #filePath).deletingLastPathComponent().path
let sparkleFrameworkRoot = packageRoot + "/.sparkle-dist"

let package = Package(
    name: "CodexControl",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(
            name: "CodexControl",
            targets: ["CodexControl"]),
    ],
    targets: [
        .executableTarget(
            name: "CodexControl",
            path: "Sources/CodexControl",
            swiftSettings: [
                .unsafeFlags(["-F", sparkleFrameworkRoot]),
            ],
            linkerSettings: [
                .unsafeFlags([
                    "-F", sparkleFrameworkRoot,
                    "-Xlinker", "-rpath",
                    "-Xlinker", "@loader_path/../Frameworks",
                ]),
                .linkedFramework("AppKit"),
                .linkedFramework("Sparkle"),
                .linkedFramework("SwiftUI"),
            ]),
    ])
