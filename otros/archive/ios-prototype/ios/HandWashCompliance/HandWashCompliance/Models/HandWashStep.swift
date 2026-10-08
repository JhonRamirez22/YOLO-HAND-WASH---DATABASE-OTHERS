import Foundation

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

    /// Minimum visual practice time shown by the iOS progress indicator.
    /// The backend remains the source of truth for the final validation.
    var requiredTime: Double {
        5.0
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

    static func fromBackendState(_ value: String) -> HandWashStep? {
        switch value {
        case "PASO_1_PALMAS": return .paso1
        case "PASO_2_DORSOS": return .paso2
        case "PASO_3_INTERDIGITALES": return .paso3
        case "PASO_4_NUDILLOS": return .paso4
        case "PASO_5_PULGAR": return .paso5
        case "PASO_6_PUNTA_DE_DEDOS": return .paso6
        case "PASO_7_CIRCULARES": return .paso7
        default: return nil
        }
    }
}
