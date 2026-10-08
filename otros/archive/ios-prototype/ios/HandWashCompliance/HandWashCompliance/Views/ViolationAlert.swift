import SwiftUI

struct ViolationAlertView: View {
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
