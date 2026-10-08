// ============================================================
// SensorViewModel.swift
// ViewModel que integra sensores ESP32 + YOLO
// Sistema de Lavado de Manos - iOS
// ============================================================

import Foundation
import SwiftUI
import Combine

// ============================================================
// Estado del lavado
// ============================================================
enum WashingState: String {
    case idle = "ESPERANDO"
    case handsDetected = "MANOS DETECTADAS"
    case washing = "FROTANDO"
    case completed = "COMPLETADO"
    case cancelled = "CANCELADO"
}

// ============================================================
// ViewModel principal
// ============================================================
class SensorViewModel: ObservableObject {
    
    // MARK: - Published Properties (UI)
    @Published var washingState: WashingState = .idle
    @Published var distance: Double = 0
    @Published var movement: Double = 0
    @Published var isFrotando = false
    @Published var timerSeconds: Int = 0
    @Published var progress: Double = 0
    @Published var isConnected = false
    @Published var statusMessage = "Esperando sensores..."
    
    // MARK: - Constants
    private let requiredWashTime = 20 // segundos
    private let distanceThreshold = 20.0 // cm
    private let movementThreshold = 12.0 // m/s2
    
    // MARK: - Private Properties
    private var bluetoothService: BluetoothService
    private var timer: Timer?
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Init
    init() {
        bluetoothService = BluetoothService()
        setupBluetoothCallbacks()
        setupTimer()
    }
    
    // MARK: - Setup
    
    private func setupBluetoothCallbacks() {
        bluetoothService.delegate = self
        
        // Observar conexion BLE
        bluetoothService.$isConnected
            .receive(on: DispatchQueue.main)
            .assign(to: &$isConnected)
    }
    
    private func setupTimer() {
        // Timer que actualiza la UI cada segundo
        Timer.publish(every: 1.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.updateTimer()
            }
            .store(in: &cancellables)
    }
    
    // MARK: - Public Methods
    
    /// Iniciar escaneo BLE
    func startScanning() {
        bluetoothService.startScanning()
        statusMessage = "Buscando ESP32..."
    }
    
    /// Detener escaneo
    func stopScanning() {
        bluetoothService.stopScanning()
    }
    
    /// Resetear sesion
    func resetSession() {
        washingState = .idle
        timerSeconds = 0
        progress = 0
        isFrotando = false
        movement = 0
        statusMessage = "Esperando sensores..."
        stopTimer()
    }
    
    // MARK: - Private Methods
    
    private func updateTimer() {
        guard washingState == .washing else { return }
        
        timerSeconds += 1
        progress = Double(timerSeconds) / Double(requiredWashTime)
        
        if timerSeconds >= requiredWashTime {
            washingComplete()
        }
    }
    
    private func startTimer() {
        timerSeconds = 0
        progress = 0
        washingState = .washing
        statusMessage = "Frotando manos... \(requiredWashTime - timerSeconds)s restantes"
    }
    
    private func stopTimer() {
        timer?.invalidate()
        timer = nil
    }
    
    private func washingComplete() {
        washingState = .completed
        statusMessage = "Lavado completado!"
        stopTimer()
        
        // Enviar confirmacion al ESP32
        bluetoothService.sendWashingComplete()
        
        // Resetear despues de 3 segundos
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) { [weak self] in
            self?.resetSession()
        }
    }
    
    private func processMessage(_ message: String) {
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            
            switch message {
            case "MANOS_DETECTADAS":
                self.washingState = .handsDetected
                self.statusMessage = "Manos detectadas - Iniciando lavado"
                self.startTimer()
                
            case "MANOS_ALEJADAS":
                self.washingState = .cancelled
                self.statusMessage = "Manos alejadas - Cancelando"
                self.stopTimer()
                
                // Resetear despues de 1 segundo
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                    self.resetSession()
                }
                
            case "FROTANDO_INICIO":
                self.isFrotando = true
                self.statusMessage = "Frotando manos... \(self.requiredWashTime - self.timerSeconds)s restantes"
                
            case "FROTANDO_FIN":
                self.isFrotando = false
                self.statusMessage = "Esperando movimiento..."
                
            default:
                // Manejar mensajes con datos (MOVIMIENTO:XX.X)
                if message.hasPrefix("MOVIMIENTO:") {
                    let valueStr = message.replacingOccurrences(of: "MOVIMIENTO:", with: "")
                    if let value = Double(valueStr) {
                        self.movement = value
                        self.statusMessage = "Movimiento: \(String(format: "%.1f", value)) m/s2"
                    }
                }
            }
        }
    }
}

// MARK: - BluetoothServiceDelegate
extension SensorViewModel: BluetoothServiceDelegate {
    
    func bluetoothDidConnect() {
        isConnected = true
        statusMessage = "Conectado al ESP32"
        print("ESP32 conectado via BLE")
    }
    
    func bluetoothDidDisconnect() {
        isConnected = false
        statusMessage = "Desconectado - Reconectando..."
        print("ESP32 desconectado")
    }
    
    func bluetoothDidReceiveMessage(_ message: String) {
        processMessage(message)
    }
}
