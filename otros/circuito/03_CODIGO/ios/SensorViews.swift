// ============================================================
// SensorViews.swift
// Vistas SwiftUI para mostrar estado de sensores
// Sistema de Lavado de Manos - iOS
// ============================================================

import SwiftUI

// ============================================================
// Vista principal que combina todo
// ============================================================
struct SensorViews: View {
    @StateObject private var viewModel = SensorViewModel()
    
    var body: some View {
        ZStack {
            // Fondo oscuro
            Color.black.ignoresSafeArea()
            
            VStack(spacing: 20) {
                // Header
                HeaderView()
                
                // Estado de conexion
                ConnectionView(isConnected: viewModel.isConnected)
                
                // Sensor de distancia
                DistanceView(distance: viewModel.distance, 
                            isDetected: viewModel.washingState == .handsDetected)
                
                // Sensor de movimiento
                MovementView(movement: viewModel.movement,
                           isFrotando: viewModel.isFrotando)
                
                // Timer de lavado
                TimerView(seconds: viewModel.timerSeconds,
                         progress: viewModel.progress,
                         state: viewModel.washingState)
                
                // Estado actual
                StatusView(message: viewModel.statusMessage,
                          state: viewModel.washingState)
                
                Spacer()
            }
            .padding()
        }
        .onAppear {
            viewModel.startScanning()
        }
    }
}

// ============================================================
// Header
// ============================================================
struct HeaderView: View {
    var body: some View {
        HStack {
            VStack(alignment: .leading) {
                Text("HAND WASH")
                    .font(.system(size: 24, weight: .bold, design: .monospaced))
                    .foregroundColor(.cyan)
                Text("Sistema de Lavado de Manos")
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundColor(.gray)
            }
            Spacer()
            Image(systemName: "hand.raised.fill")
                .font(.system(size: 32))
                .foregroundColor(.cyan)
        }
        .padding()
        .background(Color.black.opacity(0.5))
        .cornerRadius(12)
    }
}

// ============================================================
// Conexion BLE
// ============================================================
struct ConnectionView: View {
    let isConnected: Bool
    
    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(isConnected ? Color.green : Color.red)
                .frame(width: 12, height: 12)
                .shadow(color: isConnected ? .green : .red, radius: 4)
            
            Text(isConnected ? "CONECTADO AL ESP32" : "DESCONECTADO")
                .font(.system(size: 12, weight: .bold, design: .monospaced))
                .foregroundColor(isConnected ? .green : .red)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.black.opacity(0.5))
        .cornerRadius(20)
        .overlay(
            RoundedRectangle(cornerRadius: 20)
                .stroke((isConnected ? Color.green : Color.red).opacity(0.5), lineWidth: 1)
        )
    }
}

// ============================================================
// Sensor de Distancia
// ============================================================
struct DistanceView: View {
    let distance: Double
    let isDetected: Bool
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: "ruler")
                    .foregroundColor(.cyan)
                Text("DISTANCIA")
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundColor(.cyan)
                Spacer()
            }
            
            // Barra de distancia
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.gray.opacity(0.3))
                        .frame(height: 20)
                    
                    RoundedRectangle(cornerRadius: 4)
                        .fill(isDetected ? Color.green : Color.orange)
                        .frame(width: min(CGFloat(distance / 100.0) * geometry.size.width, geometry.size.width), height: 20)
                }
            }
            .frame(height: 20)
            
            HStack {
                Text("\(String(format: "%.1f", distance)) cm")
                    .font(.system(size: 16, weight: .bold, design: .monospaced))
                    .foregroundColor(.white)
                
                Spacer()
                
                Text(isDetected ? "DETECTADO" : "SIN MANOS")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundColor(isDetected ? .green : .gray)
            }
        }
        .padding()
        .background(Color.black.opacity(0.5))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isDetected ? Color.green : Color.gray.opacity(0.3), lineWidth: 1)
        )
    }
}

// ============================================================
// Sensor de Movimiento
// ============================================================
struct MovementView: View {
    let movement: Double
    let isFrotando: Bool
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: "waveform.path.ecg")
                    .foregroundColor(.pink)
                Text("MOVIMIENTO")
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundColor(.pink)
                Spacer()
            }
            
            // Indicador circular de movimiento
            ZStack {
                Circle()
                    .stroke(Color.gray.opacity(0.3), lineWidth: 8)
                    .frame(width: 80, height: 80)
                
                Circle()
                    .trim(from: 0, to: CGFloat(min(movement / 20.0, 1.0)))
                    .stroke(isFrotando ? Color.green : Color.orange, 
                            style: StrokeStyle(lineWidth: 8, lineCap: .round))
                    .frame(width: 80, height: 80)
                    .rotationEffect(.degrees(-90))
                
                VStack(spacing: 2) {
                    Text(String(format: "%.1f", movement))
                        .font(.system(size: 14, weight: .bold, design: .monospaced))
                        .foregroundColor(.white)
                    Text("m/s2")
                        .font(.system(size: 8, design: .monospaced))
                        .foregroundColor(.gray)
                }
            }
            
            Text(isFrotando ? "FROTANDO" : "QUIETO")
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundColor(isFrotando ? .green : .gray)
        }
        .padding()
        .background(Color.black.opacity(0.5))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isFrotando ? Color.green : Color.gray.opacity(0.3), lineWidth: 1)
        )
    }
}

// ============================================================
// Timer de Lavado
// ============================================================
struct TimerView: View {
    let seconds: Int
    let progress: Double
    let state: WashingState
    
    var body: some View {
        VStack(spacing: 12) {
            HStack {
                Image(systemName: "timer")
                    .foregroundColor(.orange)
                Text("TIMER DE LAVADO")
                    .font(.system(size: 12, weight: .bold, design: .monospaced))
                    .foregroundColor(.orange)
                Spacer()
            }
            
            // Barra de progreso
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color.gray.opacity(0.3))
                        .frame(height: 12)
                    
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color.green)
                        .frame(width: CGFloat(progress) * geometry.size.width, height: 12)
                        .animation(.linear(duration: 1), value: progress)
                }
            }
            .frame(height: 12)
            
            HStack {
                // Tiempo restante
                Text("\(seconds)/20s")
                    .font(.system(size: 28, weight: .bold, design: .monospaced))
                    .foregroundColor(.white)
                
                Spacer()
                
                // Porcentaje
                Text("\(Int(progress * 100))%")
                    .font(.system(size: 20, weight: .bold, design: .monospaced))
                    .foregroundColor(.green)
            }
        }
        .padding()
        .background(Color.black.opacity(0.5))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(state == .washing ? Color.orange : Color.gray.opacity(0.3), lineWidth: 1)
        )
    }
}

// ============================================================
// Estado Actual
// ============================================================
struct StatusView: View {
    let message: String
    let state: WashingState
    
    var stateColor: Color {
        switch state {
        case .idle: return .gray
        case .handsDetected: return .orange
        case .washing: return .green
        case .completed: return .cyan
        case .cancelled: return .red
        }
    }
    
    var body: some View {
        HStack {
            Circle()
                .fill(stateColor)
                .frame(width: 10, height: 10)
            
            Text(message)
                .font(.system(size: 12, weight: .bold, design: .monospaced))
                .foregroundColor(.white)
            
            Spacer()
        }
        .padding()
        .background(Color.black.opacity(0.5))
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(stateColor.opacity(0.5), lineWidth: 1)
        )
    }
}

// ============================================================
// Preview
// ============================================================
struct SensorViews_Previews: PreviewProvider {
    static var previews: some View {
        SensorViews()
    }
}
