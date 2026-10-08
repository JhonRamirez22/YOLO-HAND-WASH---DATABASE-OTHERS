import AVFoundation
import UIKit

class CameraManager: NSObject, ObservableObject {
    let captureSession = AVCaptureSession()
    let previewLayer = AVCaptureVideoPreviewLayer()
    private let videoOutput = AVCaptureVideoDataOutput()
    private let sessionQueue = DispatchQueue(label: "camera.session.queue")

    override init() {
        super.init()
        setupCamera()
    }

    private func setupCamera() {
        sessionQueue.async { [weak self] in
            guard let self = self else { return }

            self.captureSession.sessionPreset = .medium

            guard let camera = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back),
                  let input = try? AVCaptureDeviceInput(device: camera) else { return }

            if self.captureSession.canAddInput(input) {
                self.captureSession.addInput(input)
            }

            self.videoOutput.setSampleBufferDelegate(nil, queue: DispatchQueue(label: "video.output"))
            self.videoOutput.alwaysDiscardsLateVideoFrames = true

            if self.captureSession.canAddOutput(self.videoOutput) {
                self.captureSession.addOutput(self.videoOutput)
            }

            self.previewLayer.session = self.captureSession
            self.captureSession.startRunning()
        }
    }

    func startCapture(delegate: AVCaptureVideoDataOutputSampleBufferDelegate) {
        sessionQueue.async { [weak self] in
            self?.videoOutput.setSampleBufferDelegate(delegate, queue: DispatchQueue(label: "video.delegate"))
        }
    }
}
