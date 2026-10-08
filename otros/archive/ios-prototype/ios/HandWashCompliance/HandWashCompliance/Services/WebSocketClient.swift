import Foundation

class WebSocketClient {
    enum ConnectionState {
        case disconnected
        case connecting
        case connected
    }

    private var webSocket: URLSessionWebSocketTask?
    private var sessionId: String?
    private var hasConfirmedConnection = false

    var onStateUpdate: (([String: Any]) -> Void)?
    var onConnectionChange: ((Bool) -> Void)?

    func connect(sessionId: String, accessToken: String? = nil,
                 baseURL: URL? = BackendConfig.wsBaseURL) {
        guard let baseURL else {
            onConnectionChange?(false)
            return
        }

        self.sessionId = sessionId
        self.hasConfirmedConnection = false

        let endpoint = baseURL.appending(path: "ws").appending(path: sessionId)
        var components = URLComponents(url: endpoint, resolvingAgainstBaseURL: false)
        if let accessToken {
            components?.queryItems = [URLQueryItem(name: "access_token", value: accessToken)]
        }
        guard let url = components?.url else {
            onConnectionChange?(false)
            return
        }
        webSocket = URLSession.shared.webSocketTask(with: url)
        webSocket?.resume()

        onConnectionChange?(false)
        // URLSessionWebSocketTask has no public onOpen callback. A ping
        // confirms the TCP/WebSocket handshake even when YOLO has not yet
        // produced a detection (for example while the CoreML model loads).
        webSocket?.sendPing { [weak self] error in
            DispatchQueue.main.async {
                guard let self else { return }
                self.hasConfirmedConnection = error == nil
                self.onConnectionChange?(error == nil)
            }
        }
        receiveMessage()
    }

    func disconnect() {
        webSocket?.cancel(with: .normalClosure, reason: nil)
        hasConfirmedConnection = false
        onConnectionChange?(false)
    }

    func sendDetection(claseDetectada: String, confianza: Float) {
        let message: [String: Any] = [
            "sessionId": sessionId ?? "",
            "claseDetectada": claseDetectada,
            "confianza": confianza,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]

        guard let data = try? JSONSerialization.data(withJSONObject: message),
              let text = String(data: data, encoding: .utf8) else { return }

        webSocket?.send(.string(text)) { [weak self] error in
            if error != nil {
                DispatchQueue.main.async {
                    self?.hasConfirmedConnection = false
                    self?.onConnectionChange?(false)
                }
            }
        }
    }

    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                if case .string(let text) = message,
                   let data = text.data(using: .utf8),
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {

                    if self?.hasConfirmedConnection == false {
                        self?.hasConfirmedConnection = true
                        DispatchQueue.main.async {
                            self?.onConnectionChange?(true)
                        }
                    }

                    self?.onStateUpdate?(json)
                }
                self?.receiveMessage()
            case .failure:
                DispatchQueue.main.async {
                    self?.hasConfirmedConnection = false
                    self?.onConnectionChange?(false)
                }
            }
        }
    }
}
