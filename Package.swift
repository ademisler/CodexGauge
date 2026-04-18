// swift-tools-version: 6.2

import PackageDescription

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
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("SwiftUI"),
            ]),
    ])
