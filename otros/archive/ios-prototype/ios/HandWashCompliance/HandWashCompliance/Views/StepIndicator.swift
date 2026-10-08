import SwiftUI

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

            Image(systemName: step.icon)
                .font(.system(size: 32))
                .foregroundColor(.cyan)

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
