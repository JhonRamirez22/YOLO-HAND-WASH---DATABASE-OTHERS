//nolint:unused
import SwiftUI
import AVFoundation
import UltralyticsYOLO

// MARK: - Hand Wash Compliance iOS App
// Uses UltralyticsYOLO SDK for real-time hand wash step detection
// Sends detections to backend via WebSocket for compliance validation

@main
struct HandWashApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

// MARK: - Content View
struct ContentView: View {
    @StateObject private var handWashVM = HandWashViewModel()

    var body: some View {
        ZStack {
            // Camera preview
            CameraPreviewView(camera: handWashVM.camera)
                .ignoresSafeArea()

            // Overlay UI
            VStack {
                // Header
                HStack {
                    Text("HAND WASH")
                        .font(.system(size: 14, weight: .bold, design: .monospaced))
                        .foregroundColor(.cyan)
                    Spacer()
                    ConnectionStatusView(isConnected: handWashVM.isConnected)
                }
                .padding(.horizontal, 20)
                .padding(.top, 50)

                Spacer()

                // Current step indicator
                if let step = handWashVM.currentStep {
                    StepIndicatorView(step: step, progress: handWashVM.stepProgress)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                        .animation(.easeInOut, value: handWashVM.currentStep)
                }

                // Progress bar
                ProgressView(value: handWashVM.completedSteps, total: 7)
                    .progressViewStyle(LinearProgressViewStyle(tint: .cyan))
                    .scaleEffect(x: 1, y: 3, anchor: .center)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 10)

                // Step counter
                Text("\(handWashVM.completedSteps)/7 PASOS")
                    .font(.system(size: 16, weight: .bold, design: .monospaced))
                    .foregroundColor(.white)
                    .padding(.bottom, 20)

                // Control buttons
                HStack(spacing: 20) {
                    Button(action: {
                        handWashVM.startSession(protocol: .clinicoQuirurgico)
                    }) {
                        Text("CLINICO")
                            .font(.system(size: 12, weight: .bold, design: .monospaced))
                            .foregroundColor(.cyan)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Color.cyan.opacity(0.2))
                            .overlay(
                                RoundedRectangle(cornerRadius: 4)
                                    .stroke(Color.cyan, lineWidth: 1)
                            )
                    }

                    Button(action: {
                        handWashVM.startSession(protocol: .domestico)
                    }) {
                        Text("DOMESTICO")
                            .font(.system(size: 12, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Color.white.opacity(0.1))
                            .overlay(
                                RoundedRectangle(cornerRadius: 4)
                                    .stroke(Color.white.opacity(0.3), lineWidth: 1)
                            )
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 40)
            }

            // Violation alert
            if let violation = handWashVM.currentViolation {
                ViolationalertView(violation: violation)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .animation(.spring(), value: handWashVM.currentViolation)
            }

            // Completion overlay
            if handWashVM.sessionCompleted {
                CompletionOverlayView(
                    result: handWashVM.sessionResult,
                    onNewSession: { handWashVM.resetSession() }
                )
                .transition(.opacity)
                .animation(.easeInOut, value: handWashVM.sessionCompleted)
            }
        }
    }
}

// MARK: - Camera Preview
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

// MARK: - Connection Status
struct ConnectionStatusView: View {
    let isConnected: Bool

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(isConnected ? Color.green : Color.red)
                .frame(width: 8, height: 8)
            Text(isConnected ? "CONECTADO" : "DESCONECTADO")
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundColor(isConnected ? .green : .red)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.black.opacity(0.6))
        .overlay(
            RoundedRectangle(cornerRadius: 4)
                .stroke((isConnected ? Color.green : Color.red).opacity(0.5), lineWidth: 1)
        )
    }
}

// MARK: - Step Indicator
struct StepIndicatorView: View {
    let step: HandWashStep
    let progress: Double

    var body: some View {
        VStack(spacing: 8) {
            Text("PASO \(step.rawValue)")
                .font(.system(size: 48, weight: .black, design: .monospaced))
                .foregroundColor(.cyan)

            Text(step.name)
                .font(.system(size: 14, weight: .bold, design: .monospaced))
                .foregroundColor(.white)

            // Step-specific icon
            Image(systemName: step.icon)
                .font(.system(size: 32))
                .foregroundColor(.cyan)
                .symbolEffect(.pulse)

            // Mini progress
            Text(String(format: "%.1fs / %.1fs", progress * step.requiredTime, step.requiredTime))
                .font(.system(size: 12, design: .monospaced))
                .foregroundColor(.gray)
        }
        .padding(24)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.black.opacity(0.7))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.cyan.opacity(0.3), lineWidth: 1)
                )
        )
    }
}

// MARK: - Violation Alert
struct ViolationalertView: View {
    let violation: Violation

    var body: some View {
        VStack {
            HStack {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.red)
                Text("INFRACCION")
                    .font(.system(size: 14, weight: .bold, design: .monospaced))
                    .foregroundColor(.red)
            }
            Text(violation.detail)
                .font(.system(size: 12, design: .monospaced))
                .foregroundColor(.white)
                .multilineTextAlignment(.center)
        }
        .padding(16)
        .background(Color.red.opacity(0.2))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.red, lineWidth: 1)
        )
        .padding(.top, 100)
        .padding(.horizontal, 20)
    }
}

// MARK: - Completion Overlay
struct CompletionOverlayView: View {
    let result: SessionResult
    let onNewSession: () -> Void

    var body: some View {
        ZStack {
            Color.black.opacity(0.9)

            VStack(spacing: 24) {
                Image(systemName: result.icon)
                    .font(.system(size: 80))
                    .foregroundColor(result.color)

                Text(result.title)
                    .font(.system(size: 24, weight: .black, design: .monospaced))
                    .foregroundColor(result.color)

                VStack(spacing: 8) {
                    Text("Pasos completados: \(result.completedSteps)/7")
                        .foregroundColor(.gray)
                    Text("Duracion: \(String(format: "%.1f", result.duration))s")
                        .foregroundColor(.gray)
                }

                Button(action: onNewSession) {
                    Text("NUEVA SESION")
                        .font(.system(size: 14, weight: .bold, design: .monospaced))
                        .foregroundColor(.black)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                        .background(Color.cyan)
                        .cornerRadius(8)
                }
                .padding(.horizontal, 40)
            }
        }
    }
}

// MARK: - Enums
enum HandWashProtocol: String {
    case clinicoQuirurgico = "CLINICO_QUIRURGICO"
    case domestico = "DOMESTICO"
}

enum HandWashStep: Int, CaseIterable {
    case paso1 = 1, paso2, paso3, paso4, paso5, paso6, paso7

    var name: String {
        switch self {
        case .paso1: return "Palmas"
        case .paso2: return "Dorsos"
        case .paso3: return "Interdigitales"
        case .paso4: return "Nudillos"
        case .paso5: return "Pulgar"
        case .paso6: return "Punta de Dedos"
        case .paso7: return "Circulares"
        }
    }

    var detectionClass: String {
        switch self {
        case .paso1: return "Paso1_Palmas"
        case .paso2: return "Paso2_Dorsos"
        case .paso3: return "Paso3_Interdigitales"
        case .paso4: return "Paso4_Nudillos"
        case .paso5: return "Paso5_Pulgar"
        case .paso6: return "Paso6_PuntaDeDedos"
        case .paso7: return "Paso7_Circulares"
        }
    }

    var icon: String {
        switch self {
        case .paso1: return "hand.raised.fill"
        case .paso2: return "hand.raised.back.fill"
        case .paso3: return "hand.raised.fingers.spread.fill"
        case .paso4: return "fist.raised.fill"
        case .paso5: return "hand.thumbsup.fill"
        case .paso6: return "hand.point.up.fill"
        case .paso7: return "arrow.triangle.2.circlepath"
        }
    }

    var requiredTime: Double {
        return 5.0 // seconds
    }
}

// MARK: - Models
struct Violation: Identifiable {
    let id = UUID()
    let type: String
    let detail: String
}

struct SessionResult {
    let completedSteps: Int
    let duration: Double
    let violations: [Violation]

    var isApproved: Bool { violations.isEmpty && completedSteps == 7 }
    var title: String { isApproved ? "APROBADO" : "NO APROBADO" }
    var icon: String { isApproved ? "checkmark.circle.fill" : "xmark.circle.fill" }
    var color: Color { isApproved ? .green : .red }
}

// MARK: - Camera Manager
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

// MARK: - ViewModel
class HandWashViewModel: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    @Published var currentStep: HandWashStep?
    @Published var stepProgress: Double = 0
    @Published var completedSteps: Double = 0
    @Published var isConnected = false
    @Published var currentViolation: Violation?
    @Published var sessionCompleted = false
    @Published var sessionResult = SessionResult(completedSteps: 0, duration: 0, violations: [])

    let camera = CameraManager()
    private var yoloModel: YOLO?
    private var webSocket: URLSessionWebSocketTask?
    private var sessionId: String?
    private var stepStartTime: Date?
    private var sessionStartTime: Date?
    private var violations: [Violation] = []
    private var completedStepsCount = 0

    override init() {
        super.init()
        loadYOLOModel()
        camera.startCapture(delegate: self)
    }

    private func loadYOLOModel() {
        // Load the custom YOLO26n model for hand wash detection
        // The model file (.mlpackage) should be added to the Xcode project
        if let modelURL = Bundle.main.url(forResource: "best", withExtension: "mlpackage") {
            yoloModel = try? YOLO(modelURL: modelURL, confidence: 0.6, iou: 0.45)
        }
    }

    func startSession(protocol washProtocol: HandWashProtocol) {
        // Create session on backend
        guard let url = URL(string: "http://localhost:8000/api/session") else { return }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONEncoder().encode(["protocolo": washProtocol.rawValue])

        URLSession.shared.dataTask(with: request) { [weak self] data, _, error in
            guard let data = data,
                  let response = try? JSONDecoder().decode([String: String].self, from: data),
                  let sessionId = response["sessionId"] else { return }

            DispatchQueue.main.async {
                self?.sessionId = sessionId
                self?.sessionStartTime = Date()
                self?.connectWebSocket()
            }
        }.resume()
    }

    private func connectWebSocket() {
        guard let sessionId = sessionId,
              let url = URL(string: "ws://localhost:8000/ws/\(sessionId)") else { return }

        webSocket = URLSession.shared.webSocketTask(with: url)
        webSocket?.resume()
        isConnected = true
        receiveMessage()
    }

    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                if case .string(let text) = message {
                    self?.handleServerResponse(text)
                }
                self?.receiveMessage()
            case .failure:
                DispatchQueue.main.async {
                    self?.isConnected = false
                }
            }
        }
    }

    private func handleServerResponse(_ json: String) {
        guard let data = json.data(using: .utf8),
              let response = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }

        DispatchQueue.main.async { [weak self] in
            // Handle violation
            if let infraccion = response["infraccion"] as? [String: Any],
               let detalle = infraccion["detalle"] as? String {
                self?.currentViolation = Violation(type: infraccion["tipo"] as? String ?? "", detail: detalle)
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                    self?.currentViolation = nil
                }
            }

            // Handle session complete
            if let estadoSesion = response["estadoSesion"] as? String, estadoSesion == "COMPLETADA" {
                self?.sessionCompleted = true
                let duration = Date().timeIntervalSince(self?.sessionStartTime ?? Date())
                self?.sessionResult = SessionResult(
                    completedSteps: self?.completedStepsCount ?? 0,
                    duration: duration,
                    violations: self?.violations ?? []
                )
            }
        }
    }

    func resetSession() {
        currentStep = nil
        stepProgress = 0
        completedSteps = 0
        completedStepsCount = 0
        currentViolation = nil
        sessionCompleted = false
        violations = []
        sessionStartTime = nil
        webSocket?.cancel(with: .normalClosure, reason: nil)
        isConnected = false
    }

    // AVCaptureVideoDataOutputSampleBufferDelegate
    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer),
              let model = yoloModel else { return }

        // Run YOLO inference
        let results = model.predict(pixelBuffer: pixelBuffer)

        // Get top detection
        guard let topDetection = results.first else { return }

        // Map detection to step
        let className = topDetection.className
        let confidence = topDetection.confidence

        // Send to backend
        sendDetection(claseDetectada: className, confianza: Float(confidence))
    }

    private func sendDetection(claseDetectada: String, confianza: Float) {
        let message: [String: Any] = [
            "claseDetectada": claseDetectada,
            "confianza": confianza
        ]

        guard let data = try? JSONSerialization.data(withJSONObject: message),
              let text = String(data: data, encoding: .utf8) else { return }

        webSocket?.send(.string(text)) { [weak self] error in
            if error != nil {
                DispatchQueue.main.async {
                    self?.isConnected = false
                }
            }
        }
    }
}
