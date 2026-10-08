import SwiftUI

struct SessionResult {
    let completedSteps: Int
    let duration: Double
    let violations: [Violation]
    let procedureCompleteValidated: Bool = false

    var isApproved: Bool { procedureCompleteValidated && violations.isEmpty && completedSteps == 7 }
    var title: String { isApproved ? "APROBADO" : "NO APROBADO" }
    var icon: String { isApproved ? "checkmark.circle.fill" : "xmark.circle.fill" }
    var color: Color { isApproved ? .green : .red }
}
