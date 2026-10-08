import SwiftUI

struct Violation: Identifiable, Equatable {
    let id = UUID()
    let type: String
    let detail: String
}
