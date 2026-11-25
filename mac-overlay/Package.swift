// swift-tools-version:5.10
import PackageDescription

let package = Package(
    name: "JapaneseEyes",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "JapaneseEyes", path: "Sources/JapaneseEyes")
    ]
)
