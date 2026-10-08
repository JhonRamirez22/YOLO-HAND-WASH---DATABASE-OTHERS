// ============================================================
// SISTEMA DE LAVADO DE MANOS - ESP32
// Sensores: VL53L0X + MPU6050
// Comunicacion: Bluetooth Low Energy (BLE) - Compatible iOS
// ============================================================

#include <Wire.h>
#include <Adafruit_VL53L0X.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// ============================================================
// UUIDs del servicio BLE
// ============================================================
#define SERVICE_UUID        "12345678-1234-1234-1234-123456789abc"
#define CHARACTERISTIC_UUID "abcd1234-ab12-cd34-ef56-123456789abc"

// ============================================================
// Objetos de sensores
// ============================================================
Adafruit_VL53L0X lox = Adafruit_VL53L0X();
Adafruit_MPU6050 mpu;

// ============================================================
// BLE objects
// ============================================================
BLEServer* pServer = NULL;
BLECharacteristic* pCharacteristic = NULL;
bool deviceConnected = false;
bool oldDeviceConnected = false;

// ============================================================
// Variables de estado
// ============================================================
bool manosDetectadas = false;
bool frotando = false;
int umbralDistancia = 200;    // 200mm = 20cm
float umbralMovimiento = 12.0; // m/s2
unsigned long ultimoEnvio = 0;
const unsigned long intervaloEnvio = 200; // 200ms

// ============================================================
// Pines
// ============================================================
#define BUZZER_PIN 25
#define LED_VERDE  27
#define LED_ROJO   26
#define LED_AZUL   14

// ============================================================
// Callback del servidor BLE - Detecta conexiones
// ============================================================
class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        deviceConnected = true;
        Serial.println("Cliente BLE conectado");
        digitalWrite(LED_AZUL, HIGH);
    }

    void onDisconnect(BLEServer* pServer) {
        deviceConnected = false;
        Serial.println("Cliente BLE desconectado");
        digitalWrite(LED_AZUL, LOW);
    }
};

// ============================================================
// Enviar mensaje por BLE
// ============================================================
void enviarBLE(String mensaje) {
    if (deviceConnected) {
        pCharacteristic->setValue(mensaje.c_str());
        pCharacteristic->notify();
        Serial.println("BLE TX: " + mensaje);
    }
}

// ============================================================
// SETUP
// ============================================================
void setup() {
    Serial.begin(115200);
    Serial.println("=== Sistema de Lavado de Manos ===");
    
    // Configurar pines de salida
    pinMode(BUZZER_PIN, OUTPUT);
    pinMode(LED_VERDE, OUTPUT);
    pinMode(LED_ROJO, OUTPUT);
    pinMode(LED_AZUL, OUTPUT);
    
    // Indicador visual de inicio
    digitalWrite(LED_AZUL, HIGH);
    delay(500);
    digitalWrite(LED_AZUL, LOW);
    
    // Iniciar I2C
    Wire.begin(21, 22);
    
    // ---- Iniciar VL53L0X ----
    Serial.println("Iniciando VL53L0X...");
    if (!lox.begin()) {
        Serial.println("ERROR: VL53L0X no encontrado. Verificar conexiones I2C.");
        while (1) {
            digitalWrite(LED_ROJO, HIGH);
            delay(100);
            digitalWrite(LED_ROJO, LOW);
            delay(100);
        }
    }
    lox.startRangeContinuous();
    Serial.println("VL53L0X OK (Direccion: 0x29)");
    
    // ---- Iniciar MPU6050 ----
    Serial.println("Iniciando MPU6050...");
    if (!mpu.begin()) {
        Serial.println("ERROR: MPU6050 no encontrado. Verificar 3.3V y I2C.");
        while (1) {
            digitalWrite(LED_ROJO, HIGH);
            delay(200);
            digitalWrite(LED_ROJO, LOW);
            delay(200);
        }
    }
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println("MPU6050 OK (Direccion: 0x68)");
    
    // ---- Iniciar BLE ----
    Serial.println("Iniciando Bluetooth Low Energy...");
    BLEDevice::init("Lavamanos");
    
    // Crear servidor BLE
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());
    
    // Crear servicio
    BLEService *pService = pServer->createService(SERVICE_UUID);
    
    // Crear caracteristica para enviar datos
    pCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID,
        BLECharacteristic::PROPERTY_READ |
        BLECharacteristic::PROPERTY_NOTIFY
    );
    
    // Agregar descriptor para notificaciones
    pCharacteristic->addDescriptor(new BLE2902());
    
    // Iniciar servicio
    pService->start();
    
    // Iniciar advertising (anuncio BLE)
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x06);
    pAdvertising->setMinPreferred(0x12);
    BLEDevice::startAdvertising();
    
    Serial.println("BLE listo. Nombre: Lavamanos");
    Serial.println("Esperando conexion del iPhone...");
    
    // Encender LED azul indicando BLE activo
    digitalWrite(LED_AZUL, HIGH);
    
    Serial.println("=== Sistema listo ===");
}

// ============================================================
// LOOP PRINCIPAL
// ============================================================
void loop() {
    unsigned long ahora = millis();
    
    // ---- Leer VL53L0X (Distancia) ----
    if (lox.isRangeComplete()) {
        int distancia = lox.readRange();
        
        if (distancia < umbralDistancia && distancia > 0) {
            if (!manosDetectadas) {
                manosDetectadas = true;
                enviarBLE("MANOS_DETECTADAS");
                Serial.println("Manos detectadas: " + String(distancia) + "mm");
                digitalWrite(LED_ROJO, HIGH);
            }
        } else {
            if (manosDetectadas) {
                manosDetectadas = false;
                frotando = false;
                enviarBLE("MANOS_ALEJADAS");
                Serial.println("Manos alejadas: " + String(distancia) + "mm");
                digitalWrite(LED_ROJO, LOW);
                digitalWrite(LED_VERDE, LOW);
            }
        }
    }
    
    // ---- Leer MPU6050 (Movimiento) ----
    if (manosDetectadas && (ahora - ultimoEnvio >= intervaloEnvio)) {
        sensors_event_t a, g, temp;
        mpu.getEvent(&a, &g, &temp);
        
        // Calcular magnitud de aceleracion
        float magnitud = sqrt(
            a.acceleration.x * a.acceleration.x +
            a.acceleration.y * a.acceleration.y +
            a.acceleration.z * a.acceleration.z
        );
        
        if (magnitud > umbralMovimiento) {
            if (!frotando) {
                frotando = true;
                enviarBLE("FROTANDO_INICIO");
                Serial.println("Frotando detectado");
            }
            enviarBLE("MOVIMIENTO:" + String(magnitud, 1));
        } else {
            if (frotando) {
                frotando = false;
                enviarBLE("FROTANDO_FIN");
                Serial.println("Frotando detenido");
            }
        }
        ultimoEnvio = ahora;
    }
    
    // ---- Feedback LEDs ----
    if (manosDetectadas && !frotando) {
        // Parpadeo lento: manos detectadas, esperando frotado
        digitalWrite(LED_ROJO, (ahora / 1000) % 2 == 0 ? HIGH : LOW);
        digitalWrite(LED_VERDE, LOW);
    } else if (frotando) {
        // Parpadeo rapido: frotando correctamente
        digitalWrite(LED_VERDE, (ahora / 200) % 2 == 0 ? HIGH : LOW);
        digitalWrite(LED_ROJO, LOW);
    }
    
    // ---- Manejar conexion BLE ----
    if (!deviceConnected && oldDeviceConnected) {
        delay(500);
        pServer->startAdvertising();
        Serial.println("Reanunciando BLE...");
        oldDeviceConnected = deviceConnected;
    }
    
    if (deviceConnected && !oldDeviceConnected) {
        oldDeviceConnected = deviceConnected;
    }
    
    delay(10);
}
