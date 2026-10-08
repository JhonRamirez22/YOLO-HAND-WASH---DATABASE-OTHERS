import SwiftUI

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
