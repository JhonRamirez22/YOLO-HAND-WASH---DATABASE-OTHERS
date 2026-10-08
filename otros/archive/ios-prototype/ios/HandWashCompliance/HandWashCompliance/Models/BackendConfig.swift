import Foundation

struct BackendConfig {
    private static var info: [String: Any] { Bundle.main.infoDictionary ?? [:] }

    static var host: String {
        if let value = info["BackendHost"] as? String, !value.isEmpty { return value }
        return "localhost"
    }

    static var port: Int {
        if let value = info["BackendPort"] as? NSNumber { return value.intValue }
        if let value = info["BackendPort"] as? String, let intValue = Int(value) { return intValue }
        return 8080
    }

    static var apiBaseURL: URL? {
        URL(string: "http://\(host):\(port)")
    }

    static var wsBaseURL: URL? {
        URL(string: "ws://\(host):\(port)")
    }

    static var yoloHost: String {
        if let value = info["YoloHost"] as? String, !value.isEmpty { return value }
        return host
    }

    static var yoloPort: Int {
        if let value = info["YoloPort"] as? NSNumber { return value.intValue }
        if let value = info["YoloPort"] as? String, let intValue = Int(value) { return intValue }
        return 8090
    }

    static var yoloBaseURL: URL? {
        URL(string: "http://\(yoloHost):\(yoloPort)")
    }
}
