// ============================================================
// BluetoothService.swift
// Servicio BLE para comunicacion con ESP32
// Sistema de Lavado de Manos - iOS
// ============================================================

import Foundation
import CoreBluetooth
import Combine

// ============================================================
// Protocolo para notificar mensajes del ESP32
// ============================================================
protocol BluetoothServiceDelegate: AnyObject {
    func bluetoothDidConnect()
    func bluetoothDidDisconnect()
    func bluetoothDidReceiveMessage(_ message: String)
}

// ============================================================
// Servicio BLE principal
// ============================================================
class BluetoothService: NSObject, ObservableObject {
    
    // MARK: - Public Properties
    @Published var isConnected = false
    @Published var lastMessage = ""
    
    weak var delegate: BluetoothServiceDelegate?
    
    // MARK: - UUIDs (deben coincidir con ESP32)
    private let serviceUUID = CBUUID(string: "12345678-1234-1234-1234-123456789abc")
    private let characteristicUUID = CBUUID(string: "abcd1234-ab12-cd34-ef56-123456789abc")
    
    // MARK: - BLE Objects
    private var centralManager: CBCentralManager!
    private var connectedPeripheral: CBPeripheral?
    private var dataCharacteristic: CBCharacteristic?
    
    // MARK: - Init
    override init() {
        super.init()
        centralManager = CBCentralManager(delegate: self, queue: nil)
    }
    
    // MARK: - Public Methods
    
    /// Iniciar escaneo de dispositivos BLE
    func startScanning() {
        guard centralManager.state == .poweredOn else {
            print("Bluetooth no disponible")
            return
        }
        
        print("Escaneando dispositivos BLE...")
        centralManager.scanForPeripherals(withServices: [serviceUUID], options: nil)
    }
    
    /// Detener escaneo
    func stopScanning() {
        centralManager.stopScan()
    }
    
    /// Desconectar del dispositivo actual
    func disconnect() {
        if let peripheral = connectedPeripheral {
            centralManager.cancelPeripheralConnection(peripheral)
        }
    }
    
    /// Enviar comando al ESP32
    func sendCommand(_ command: String) {
        guard let characteristic = dataCharacteristic,
              let peripheral = connectedPeripheral,
              peripheral.state == .connected else {
            print("No hay conexion BLE activa")
            return
        }
        
        if let data = command.data(using: .utf8) {
            peripheral.writeValue(data, for: characteristic, type: .withResponse)
            print("BLE TX: \(command)")
        }
    }
    
    /// Enviar WASHING_COMPLETE al ESP32
    func sendWashingComplete() {
        sendCommand("WASHING_COMPLETE")
    }
}

// MARK: - CBCentralManagerDelegate
extension BluetoothService: CBCentralManagerDelegate {
    
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn:
            print("Bluetooth encendido")
            startScanning()
        case .poweredOff:
            print("Bluetooth apagado")
            isConnected = false
        case .unauthorized:
            print("Bluetooth no autorizado")
        case .unsupported:
            print("BLE no soportado en este dispositivo")
        default:
            print("Estado BLE: \(central.state.rawValue)")
        }
    }
    
    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        
        let peripheralName = peripheral.name ?? "Desconocido"
        print("Dispositivo encontrado: \(peripheralName)")
        
        if peripheral.name == "Lavamanos" {
            print("ESP32 encontrado! Conectando...")
            centralManager.stopScan()
            connectedPeripheral = peripheral
            centralManager.connect(peripheral, options: nil)
        }
    }
    
    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        print("Conectado a: \(peripheral.name ?? "ESP32")")
        
        connectedPeripheral = peripheral
        peripheral.delegate = self
        peripheral.discoverServices([serviceUUID])
        
        DispatchQueue.main.async {
            self.isConnected = true
            self.delegate?.bluetoothDidConnect()
        }
    }
    
    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        print("Desconectado de: \(peripheral.name ?? "ESP32")")
        
        connectedPeripheral = nil
        dataCharacteristic = nil
        
        DispatchQueue.main.async {
            self.isConnected = false
            self.delegate?.bluetoothDidDisconnect()
        }
        
        // Reconectar automaticamente
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
            self.startScanning()
        }
    }
    
    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        print("Error al conectar: \(error?.localizedDescription ?? "unknown")")
    }
}

// MARK: - CBPeripheralDelegate
extension BluetoothService: CBPeripheralDelegate {
    
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error = error {
            print("Error descubriendo servicios: \(error.localizedDescription)")
            return
        }
        
        guard let services = peripheral.services else { return }
        
        for service in services {
            print("Servicio encontrado: \(service.uuid)")
            peripheral.discoverCharacteristics([characteristicUUID], for: service)
        }
    }
    
    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        if let error = error {
            print("Error descubriendo caracteristicas: \(error.localizedDescription)")
            return
        }
        
        guard let characteristics = service.characteristics else { return }
        
        for characteristic in characteristics {
            print("Caracteristica encontrada: \(characteristic.uuid)")
            
            if characteristic.uuid == characteristicUUID {
                dataCharacteristic = characteristic
                
                // Suscribirse a notificaciones
                peripheral.setNotifyValue(true, for: characteristic)
                print("Suscrito a notificaciones del ESP32")
            }
        }
    }
    
    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error {
            print("Error recibiendo datos: \(error.localizedDescription)")
            return
        }
        
        guard let data = characteristic.value,
              let message = String(data: data, encoding: .utf8) else {
            return
        }
        
        print("BLE RX: \(message)")
        
        DispatchQueue.main.async {
            self.lastMessage = message
            self.delegate?.bluetoothDidReceiveMessage(message)
        }
    }
    
    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error = error {
            print("Error enviando dato: \(error.localizedDescription)")
        } else {
            print("Dato enviado correctamente")
        }
    }
}
