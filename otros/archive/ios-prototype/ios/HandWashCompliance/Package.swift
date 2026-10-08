// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "HandWashCompliance",
    platforms: [.iOS(.v16)],
    dependencies: [
        .package(url: "https://github.com/ultralytics/yolo-ios-app.git", from: "8.9.13")
    ],
    targets: [
        .executableTarget(
            name: "HandWashCompliance",
            dependencies: [
                .product(name: "UltralyticsYOLO", package: "yolo-ios-app")
            ],
            path: "HandWashCompliance"
        )
    ]
)
