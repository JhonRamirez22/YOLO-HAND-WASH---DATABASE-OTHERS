import SwiftUI

struct ContentView: View {
    @StateObject private var handWashVM = HandWashViewModel()
    @State private var pairingCode = ""

    var body: some View {
        ZStack {
            CameraPreviewView(camera: handWashVM.camera)
                .ignoresSafeArea()

            VStack {
                HStack {
                    Text("HAND WASH")
                        .font(.system(size: 14, weight: .bold, design: .monospaced))
                        .foregroundColor(.cyan)
                    Spacer()
                    ConnectionStatusView(isConnected: handWashVM.isConnected)
                }
                .padding(.horizontal, 20)
                .padding(.top, 50)

                Spacer()

                if let step = handWashVM.currentStep {
                    StepIndicatorView(step: step, progress: handWashVM.stepProgress)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                        .animation(.easeInOut, value: handWashVM.currentStep)
                }

                ProgressView(value: handWashVM.completedSteps, total: 7)
                    .progressViewStyle(LinearProgressViewStyle(tint: .cyan))
                    .scaleEffect(x: 1, y: 3, anchor: .center)
                    .padding(.horizontal, 20)
                    .padding(.bottom, 10)

                Text("\(Int(handWashVM.completedSteps))/7 PASOS")
                    .font(.system(size: 16, weight: .bold, design: .monospaced))
                    .foregroundColor(.white)
                    .padding(.bottom, 20)

                HStack(spacing: 8) {
                    TextField("Código del dashboard", text: $pairingCode)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                        .font(.system(size: 14, design: .monospaced))
                        .padding(10)
                        .background(Color.black.opacity(0.65))
                        .foregroundColor(.white)
                        .accessibilityLabel("Código de vinculación")
                    Button("VINCULAR") {
                        handWashVM.pairSession(code: pairingCode)
                    }
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundColor(.cyan)
                    .disabled(pairingCode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                .padding(.horizontal, 20)

                if let message = handWashVM.connectionMessage {
                    Text(message)
                        .font(.system(size: 12))
                        .foregroundColor(.yellow)
                        .padding(.horizontal, 20)
                        .padding(.top, 6)
                }

                if let code = handWashVM.ownPairingCode {
                    Text("Código de esta sesión: \(code)")
                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                        .foregroundColor(.cyan)
                        .padding(.horizontal, 20)
                        .padding(.top, 6)
                }

                HStack(spacing: 20) {
                    Button(action: { handWashVM.startSession(protocol: .clinicoQuirurgico) }) {
                        Text("CLINICO")
                            .font(.system(size: 12, weight: .bold, design: .monospaced))
                            .foregroundColor(.cyan)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Color.cyan.opacity(0.2))
                            .overlay(RoundedRectangle(cornerRadius: 4).stroke(Color.cyan, lineWidth: 1))
                    }

                    Button(action: { handWashVM.startSession(protocol: .domestico) }) {
                        Text("DOMESTICO")
                            .font(.system(size: 12, weight: .bold, design: .monospaced))
                            .foregroundColor(.white)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Color.white.opacity(0.1))
                            .overlay(RoundedRectangle(cornerRadius: 4).stroke(Color.white.opacity(0.3), lineWidth: 1))
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 40)
            }

            if let violation = handWashVM.currentViolation {
                ViolationAlertView(violation: violation)
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .animation(.spring(), value: handWashVM.currentViolation)
            }

            if handWashVM.sessionCompleted {
                CompletionOverlayView(
                    result: handWashVM.sessionResult,
                    onNewSession: { handWashVM.resetSession() }
                )
                .transition(.opacity)
                .animation(.easeInOut, value: handWashVM.sessionCompleted)
            }
        }
    }
}
