// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "LWMMenuBar",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/groue/GRDB.swift.git", from: "7.5.0"),
    ],
    targets: [
        .executableTarget(
            name: "LWMMenuBar",
            dependencies: [
                .product(name: "GRDB", package: "GRDB.swift"),
            ]
        ),
    ]
)
