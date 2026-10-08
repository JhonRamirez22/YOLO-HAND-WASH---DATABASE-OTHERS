import UltralyticsYOLO
import UIKit
import CoreImage

class YOLODetector {
    private var model: YOLO?

    init() {
        loadModel()
    }

    private func loadModel() {
        // Xcode compiles a .mlpackage into a .mlmodelc bundle. The current
        // Ultralytics package resolves that compiled resource by name.
        model = YOLO("best.mlmodelc", task: .detect) { [weak self] result in
            if case .success(let loadedModel) = result {
                loadedModel.setThresholds(confidence: 0.6, iou: 0.45)
                self?.model = loadedModel
            }
        }
    }

    func detect(image: UIImage) -> (className: String, confidence: Double)? {
        guard let model = model else { return nil }
        let result = model(image)
        guard let topDetection = result.boxes.max(by: { $0.conf < $1.conf }) else { return nil }
        return (topDetection.cls, Double(topDetection.conf))
    }

    func detect(pixelBuffer: CVPixelBuffer) -> (className: String, confidence: Double)? {
        guard let model = model else { return nil }
        let result = model(CIImage(cvPixelBuffer: pixelBuffer))
        guard let topDetection = result.boxes.max(by: { $0.conf < $1.conf }) else { return nil }
        return (topDetection.cls, Double(topDetection.conf))
    }
}
