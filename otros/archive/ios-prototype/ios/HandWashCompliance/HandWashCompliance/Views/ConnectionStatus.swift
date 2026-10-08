import SwiftUI

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
