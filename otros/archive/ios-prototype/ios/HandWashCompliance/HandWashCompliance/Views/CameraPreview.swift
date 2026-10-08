import SwiftUI

struct CameraPreviewView: UIViewRepresentable {
    let camera: CameraManager

    func makeUIView(context: Context) -> UIView {
        let view = UIView(frame: UIScreen.main.bounds)
        camera.previewLayer.frame = view.bounds
        camera.previewLayer.videoGravity = .resizeAspectFill
        view.layer.addSublayer(camera.previewLayer)
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {}
}
