import AVFoundation
import SwiftUI
import UIKit
import CoreImage

private struct ActiveSessionResponse: Decodable {
    let sessionId: String
    let protocolo: String
    let accessToken: String?
    let accessRequired: Bool?
}

private struct CreatedSessionResponse: Decodable {
    let sessionId: String
    let accessToken: String
    let pairingCode: String
}

class HandWashViewModel: NSObject, ObservableObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    @Published var currentStep: HandWashStep?
    @Published var stepProgress: Double = 0
    @Published var completedSteps: Double = 0
    @Published var isConnected = false
    @Published var connectionMessage: String?
    @Published var ownPairingCode: String?
    @Published var currentViolation: Violation?
    @Published var sessionCompleted = false
    @Published var sessionResult = SessionResult(completedSteps: 0, duration: 0, violations: [])

    let camera = CameraManager()
    private var webSocketClient: WebSocketClient?
    private var sessionId: String?
    private var accessToken: String?
    private var sessionStartTime: Date?
    private var violations: [Violation] = []
    private var completedStepsCount = 0
    private var lastRemoteInferenceAt = Date.distantPast
    private let remoteInferenceInterval: TimeInterval = 0.30
    private let ciContext = CIContext()

    override init() {
        super.init()
        webSocketClient = WebSocketClient()
        setupCallbacks()
        camera.startCapture(delegate: self)
        joinActiveSessionIfAvailable()
    }

    private func joinActiveSessionIfAvailable() {
        guard let baseURL = BackendConfig.apiBaseURL else { return }
        let url = baseURL.appending(path: "api").appending(path: "session").appending(path: "active")
        URLSession.shared.dataTask(with: url) { [weak self] data, response, _ in
            if (response as? HTTPURLResponse)?.statusCode == 409 {
                DispatchQueue.main.async {
                    self?.connectionMessage = "Hay varias sesiones activas. Introduce el código del dashboard."
                }
                return
            }
            guard let data,
                  let active = try? JSONDecoder().decode(ActiveSessionResponse.self, from: data) else { return }
            DispatchQueue.main.async {
                guard self?.sessionId == nil else { return }
                if active.accessRequired == true {
                    self?.connectionMessage = "Introduce el código del dashboard para vincularte."
                } else {
                    self?.joinSession(active.sessionId, accessToken: nil)
                }
            }
        }.resume()
    }

    func pairSession(code: String) {
        guard let baseURL = BackendConfig.apiBaseURL else {
            connectionMessage = "Configura la dirección del backend."
            return
        }
        let normalized = code.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty else {
            connectionMessage = "Introduce el código del dashboard."
            return
        }
        let url = baseURL.appending(path: "api").appending(path: "session").appending(path: "pair")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONEncoder().encode(["code": normalized])
        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            let status = (response as? HTTPURLResponse)?.statusCode
            guard status == 200, let data,
                  let paired = try? JSONDecoder().decode(ActiveSessionResponse.self, from: data) else {
                DispatchQueue.main.async {
                    self?.connectionMessage = status == 404
                        ? "Código inválido o sesión terminada."
                        : "No se pudo vincular el iPhone al backend."
                }
                return
            }
            self?.joinSession(paired.sessionId, accessToken: paired.accessToken)
        }.resume()
    }

    private func setupCallbacks() {
        webSocketClient?.onStateUpdate = { [weak self] data in
            self?.handleServerResponse(data)
        }
        webSocketClient?.onConnectionChange = { [weak self] connected in
            DispatchQueue.main.async {
                self?.isConnected = connected
            }
        }
    }

    func startSession(protocol washProtocol: HandWashProtocol) {
        guard let baseURL = BackendConfig.apiBaseURL else { return }
        let activeURL = baseURL.appending(path: "api").appending(path: "session").appending(path: "active")

        URLSession.shared.dataTask(with: activeURL) { [weak self] data, _, _ in
            let active = data.flatMap { try? JSONDecoder().decode(ActiveSessionResponse.self, from: $0) }
            let useActive = active?.protocolo == washProtocol.rawValue
                && active?.accessRequired == false
            if useActive, let sessionId = active?.sessionId {
                self?.joinSession(sessionId, accessToken: nil)
                return
            }

            let url = baseURL.appending(path: "api").appending(path: "session")
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try? JSONEncoder().encode(["protocolo": washProtocol.rawValue])

            URLSession.shared.dataTask(with: request) { [weak self] data, _, _ in
                guard let data,
                      let created = try? JSONDecoder().decode(CreatedSessionResponse.self, from: data) else { return }
                self?.joinSession(created.sessionId, accessToken: created.accessToken,
                                  pairingCode: created.pairingCode)
            }.resume()
        }.resume()
    }

    private func joinSession(_ sessionId: String, accessToken: String?, pairingCode: String? = nil) {
        DispatchQueue.main.async { [weak self] in
            self?.sessionId = sessionId
            self?.accessToken = accessToken
            self?.ownPairingCode = pairingCode
            self?.sessionStartTime = Date()
            self?.connectionMessage = nil
            self?.webSocketClient?.connect(sessionId: sessionId, accessToken: accessToken)
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
        sessionId = nil
        accessToken = nil
        ownPairingCode = nil
        webSocketClient?.disconnect()
        isConnected = false
    }

    private func handleServerResponse(_ response: [String: Any]) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }

            if let messageType = response["messageType"] as? String, messageType == "SESSION_SUMMARY" {
                self.sessionCompleted = true
                let duration = Date().timeIntervalSince(self.sessionStartTime ?? Date())
                self.sessionResult = SessionResult(
                    completedSteps: self.completedStepsCount,
                    duration: duration,
                    violations: self.violations,
                    procedureCompleteValidated: response["procedimientoCompletoValidado"] as? Bool ?? false
                )
                return
            }

            if let infraccion = response["infraccion"] as? [String: Any],
               let detalle = infraccion["detalle"] as? String {
                let violation = Violation(type: infraccion["tipo"] as? String ?? "", detail: detalle)
                self.currentViolation = violation
                self.violations.append(violation)
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                    self.currentViolation = nil
                }
            }

            if let estado = response["estadoActual"] as? String,
               let step = HandWashStep.fromBackendState(estado) {
                self.currentStep = step
            }

            if let progreso = response["progreso"] as? [String: Any],
               let completados = progreso["pasosCompletados"] as? Int {
                self.completedSteps = Double(completados)
                self.completedStepsCount = completados
            }

            if let tiempoAcumuladoMs = response["tiempoAcumuladoMs"] as? Double {
                self.stepProgress = max(0, tiempoAcumuladoMs / 1000.0)
            }

            if let estadoSesion = response["estadoSesion"] as? String, estadoSesion == "COMPLETADA" {
                self.sessionCompleted = true
                let duration = Date().timeIntervalSince(self.sessionStartTime ?? Date())
                self.sessionResult = SessionResult(
                    completedSteps: self.completedStepsCount,
                    duration: duration,
                    violations: self.violations
                )
            }
        }
    }

    func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer, from connection: AVCaptureConnection) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        // The phone is a camera only. Native YOLO26 runs on the PC/Mac gateway;
        // the Java WebSocket remains the feedback channel for this optional
        // camera-streamer build.
        let now = Date()
        guard now.timeIntervalSince(lastRemoteInferenceAt) >= remoteInferenceInterval else { return }
        lastRemoteInferenceAt = now
        sendFrameToYolo(pixelBuffer: pixelBuffer)
    }

    private func sendFrameToYolo(pixelBuffer: CVPixelBuffer) {
        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        guard let baseURL = BackendConfig.yoloBaseURL,
              let sessionId,
              let cgImage = ciContext.createCGImage(ciImage, from: ciImage.extent),
              let imageData = UIImage(cgImage: cgImage).jpegData(compressionQuality: 0.55) else { return }

        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: baseURL.appending(path: "api").appending(path: "infer"))
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let accessToken { request.setValue(accessToken, forHTTPHeaderField: "X-Session-Token") }

        var body = Data()
        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"file\"; filename=\"frame.jpg\"\r\n".utf8))
        body.append(Data("Content-Type: image/jpeg\r\n\r\n".utf8))
        body.append(imageData)
        body.append(Data("\r\n--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"session_id\"\r\n\r\n".utf8))
        body.append(Data("\(sessionId)\r\n".utf8))
        body.append(Data("--\(boundary)--\r\n".utf8))
        request.httpBody = body

        URLSession.shared.dataTask(with: request).resume()
    }
}
