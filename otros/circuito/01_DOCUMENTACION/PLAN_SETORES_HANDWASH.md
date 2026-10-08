# Integracion de Sensores ESP32 al Proyecto Hand Wash YOLO
 
> **Version:** 2.0 | **Fecha:** 19 de Septiembre 2026  
> **Plataforma:** iOS (iPhone) + ESP32 + Arduino IDE  
> **Comunicacion:** Bluetooth Low Energy (BLE)

---

## 1. Resumen Ejecutivo

Este documento describe como integrar **sensores fisicos** (distancia y movimiento) al sistema existente de verificacion de lavado de manos.

### ¿Que hace el sistema?

`
  PERSONA SE ACERCA              ESP32 LEE SENSORES              iPhone MUESTRA
  ─────────────────              ───────────────────              ──────────────
  Manos frente al     ──>       VL53L0X: 15cm           ──>     "Manos detectadas"
  lavamanos                     MPU6050: frotando        ──>     Timer: 20s
                                Envia por BLE            ──>     Progreso: 75%
`

### ¿Por que agregar sensores fisicos?

| Problema actual | Solucion con sensores |
|----------------|----------------------|
| Solo detecta con camara | VL53L0X detecta presencia sin camara |
| No valida movimiento real | MPU6050 mide aceleracion real |
| Sin feedback sin telefono | LEDs y Buzzer funcionan solos |
| Requiere internet para YOLO | Sensores funcionan offline |

### ¿Que componentes se necesitan?

| Componente | Funcion | Precio aprox |
|------------|---------|--------------|
| ESP32 DevKit V1 | Microcontrolador + Bluetooth | -8 USD |
| VL53L0X | Sensor de distancia laser | -5 USD |
| MPU6050 | Sensor de movimiento (IMU 6 ejes) | -3 USD |
| Buzzer pasivo | Feedback sonoro | .50 USD |
| LED RGB o 3 LEDs | Feedback visual | .50 USD |
| Resistencias 220 ohm | Proteccion de LEDs | .20 USD |
| Protoboard | Montaje temporal |  USD |
| Cables jumper | Conexiones |  USD |
| **TOTAL** | | **~-25 USD** |

---

## 2. Arquitectura del Sistema

### 2.1 Diagrama Completo

`
+=============================================================+
|                    ESTACION DE LAVADO                       |
|                                                             |
|   +-----------+      +-----------+      +---------------+   |
|   |  VL53L0X  |      |   ESP32   |      | LEDs + Buzzer |   |
|   |  (Laser)  |----->| DevKit V1 |----->|  (Feedback)   |   |
|   | Distancia |  I2C |           | GPIO |               |   |
|   | 3-200cm   |      | BLE Radio |      | Rojo/Verde/   |   |
|   +-----------+      |           |      | Azul + Sonido |   |
|                      |  SDA/SCL  |      +---------------+   |
|   +-----------+      |  (bus     |                          |
|   |  MPU6050  |----->| comparti-)|                          |
|   |   (IMU)   |  I2C |  do)     |                          |
|   | 6 ejes    |      |           |                          |
|   +-----------+      +-----+-----+                          |
|                          |                                   |
|                   Bluetooth Low Energy                      |
+==========================|==================================+
                           |
                           v
+=============================================================+
|                     iPhone (iOS)                             |
|                                                             |
|   +-----------+      +-----------+      +---------------+   |
|   |  Camara   |----->|   YOLO    |----->|  App Swift    |   |
|   |  Trasera  |      | (CoreML)  |      |  SwiftUI      |   |
|   |           |      | 7 clases  |      |               |   |
|   +-----------+      +-----------+      | Timer 20s     |   |
|                                         | Progreso      |   |
|   +-----------+                       | Estado BLE    |   |
|   | CoreBluetooth<--------------------|               |   |
|   |    (BLE)  |                       | WebSocket     |   |
|   +-----------+                       +-------+-------+   |
+=============================================================+
                                                    |
                                                    v
                                           +---------------+
                                           | Java Backend  |
                                           | (Spring Boot) |
                                           +---------------+
`

### 2.2 Flujo de Datos Detallado

**Paso 1: Persona se acerca al lavamanos**
`
VL53L0X mide distancia con laser
  -> Si distancia < 20cm (200mm):
     ESP32 envia "MANOS_DETECTADAS" por BLE
     LED rojo se enciende
     iPhone recibe notificacion
  -> Si distancia > 30cm:
     ESP32 envia "MANOS_ALEJADAS"
     Todo se apaga
`

**Paso 2: Persona empieza a frotar**
`
MPU6050 mide aceleracion (eje X + Y + Z)
  -> Calcula magnitud = sqrt(x^2 + y^2 + z^2)
  -> Si magnitud > 12.0 m/s2:
     ESP32 envia "FROTANDO_INICIO"
     iPhone inicia timer de 20 segundos
     LED verde empieza a parpadear
`

**Paso 3: Lavado en curso**
`
Cada 200ms:
  MPU6050 envia valor actual de movimiento
  ESP32 envia "MOVIMIENTO:15.3"
  iPhone actualiza barra de progreso
  
  LED estado:
  - Rojo parpadeando = manos detectadas, esperando frotado
  - Verde parpadeando = frotando correctamente
`

**Paso 4: Lavado completado (20 segundos)**
`
Timer del iPhone llega a 20s
  -> iPhone envia "WASHING_COMPLETE" por BLE
  -> ESP32 recibe y activa:
     - Buzzer: 3 beeps largos
     - LED verde: encendido fijo 3 segundos
  -> iPhone muestra pantalla de exito
`

---

## 3. Componentes Tecnicos Explicados

### 3.1 ESP32 DevKit V1 - El Cerebro

El ESP32 es un microcontrolador con **Wi-Fi y Bluetooth integrados**. Aqui es donde corre el codigo que lee los sensores y envia datos al iPhone.

**Pinout del ESP32 (vista superior):**

`
                    +------------------+
           3V3  ---|1               28|--- GND
          EN   ---|2               27|--- GPIO23
      GPIO36   ---|3               26|--- GPIO22 (SCL) <--- MPU6050 + VL53L0X
      GPIO39   ---|4               25|--- GPIO21 (SDA) <--- MPU6050 + VL53L0X
      GPIO34   ---|5               24|--- GPIO19
      GPIO35   ---|6               23|--- GPIO18
      GPIO32   ---|7               22|--- GPIO5
      GPIO33   ---|8               21|--- GPIO17
      GPIO25   ---|9               20|--- GPIO16
      GPIO26   ---|10              19|--- GPIO4
      GPIO27   ---|11              18|--- GPIO2
      GPIO14   ---|12              17|--- GPIO15
      GPIO12   ---|13              16|--- GPIO13
           GND ---|14              15|--- VIN (5V)
                    +------------------+
`

**Pines que usamos en este proyecto:**

| Pin | Uso | Color de cable |
|-----|-----|----------------|
| GPIO21 | SDA (datos I2C) | Verde |
| GPIO22 | SCL (reloj I2C) | Azul |
| GPIO25 | Buzzer | Amarillo |
| GPIO26 | LED Rojo | Rojo |
| GPIO27 | LED Verde | Verde claro |
| GPIO14 | LED Azul | Azul claro |
| 3V3 | Alimentacion 3.3V | Rojo |
| GND | Tierra | Negro |

### 3.2 VL53L0X - Sensor de Distancia Laser

**¿Como funciona?**
El VL53L0X envia un rayo laser infrarrojo y mide cuánto tarda en rebotar. Esto se llama **Time-of-Flight** (Tiempo de Vuelo).

`
   ESP32                          VL53L0X
   -----                          -------
     |    Laser infrarrojo ----->  O  <-- Emisor laser
     |    <--- Rebote del laser   |     <-- Receptor
     |                             |
     |  Mide tiempo: 0.0000001s   |
     |  Distancia = tiempo x vel  |
     |  Resultado: 15cm (150mm)   |
`

**Especificaciones:**

| Parametro | Valor |
|-----------|-------|
| Rango | 3cm a 200cm |
| Precision | +/- 3% |
| Frecuencia | 50 Hz (20 lecturas/segundo) |
| Alimentacion | 2.6V a 3.5V (usar 3.3V) |
| Protocolo | I2C |
| Direccion | 0x29 (fija) |
| Pines activos | VIN, GND, SDA, SCL |

**Importante:** Los pines XSHUT y GPIO1 no se usan. Dejarlos sin conectar.

### 3.3 MPU6050 - Sensor de Movimiento (IMU)

**¿Que es un IMU?**
IMU = Unidad de Medicion Inercial. Contiene:
- **Acelerometro:** Mide aceleracion en 3 ejes (X, Y, Z)
- **Giroscopio:** Mide rotacion en 3 ejes

`
         MPU6050 - Vista del chip
    +---------------------------+
    |    +---+                   |
    |    | MPU| 6050            |
    |    +---+                   |
    |         Z (arriba)         |
    |         ^                  |
    |         |                  |
    |    Y <--+--> X             |
    |                            |
    +---+---+---+---+---+---+   |
    |VCC|GND|SDA|SCL|AD0|INT|   |
    +---+---+---+---+---+---+   |
`

**¿Como detecta frotado?**
Cuando las manos se frotan, hay movimiento en los ejes X e Y. El sensor mide la aceleracion:

`
Quieto:    magnitud = sqrt(0^2 + 0^2 + 9.8^2) = 9.8 m/s2 (gravedad)
Frotando:  magnitud = sqrt(3^2 + 4^2 + 9.8^2) = 11.2 m/s2
Mucho:     magnitud = sqrt(8^2 + 6^2 + 9.8^2) = 14.1 m/s2
`

**Umbral de deteccion:** 12.0 m/s2 (si es mayor, se considera "frotando")

| Parametro | Valor |
|-----------|-------|
| Rango acelerometro | +/- 2g, 4g, 8g, 16g |
| Rango giroscopio | +/- 250, 500, 1000, 2000 deg/s |
| Frecuencia | 100 Hz |
| Alimentacion | 3.3V (NO usar 5V) |
| Protocolo | I2C |
| Direccion | 0x68 (por defecto) |

### 3.4 I2C - Protocolo de Comunicacion

**¿Que es I2C?**
I2C (Inter-Integrated Circuit) es un protocolo que permite conectar varios sensores usando solo **2 cables**:

- **SDA** (Serial Data): Datos - por aqui viaja la informacion
- **SCL** (Serial Clock): Reloj - sincroniza la comunicacion

`
   ESP32 (Maestro)
       |
       |--- SDA (GPIO21) ---+---+---+
       |                     |   |   |
       |--- SCL (GPIO22) ---+---+---+
       |                     |   |   |
   VL53L0X (0x29)           |   |   +--- MPU6050 (0x68)
   Sensor 1                 |   |       Sensor 2
`

**¿Por que funciona con 2 sensores?**
Cada sensor tiene una **direccion unica**:
- VL53L0X = direccion **0x29**
- MPU6050 = direccion **0x68**

El ESP32 puede "hablar" con cada uno por separado usando su direccion.

**Resistencias Pull-Up:**
En el bus I2C se necesitan resistencias pull-up de **4.7K ohm** de SDA y SCL a 3.3V. Muchos modulos ya las traen integradas.

---

## 4. Guia de Conexion Paso a Paso

### 4.1 Colores Estandar de Cables

Usa estos colores para organizar el cableado:

| Color | Uso | Ejemplo |
|-------|-----|---------|
| **Rojo** | Alimentacion 3.3V / 5V | VIN, VCC |
| **Negro** | Tierra (GND) | GND |
| **Verde** | Datos I2C (SDA) | GPIO21 |
| **Azul** | Reloj I2C (SCL) | GPIO22 |
| **Amarillo** | Buzzer / Senal | GPIO25 |
| **Naranja** | LED Rojo | GPIO26 |
| **Verde claro** | LED Verde | GPIO27 |
| **Azul claro** | LED Azul | GPIO14 |

### 4.2 Conexion VL53L0X

`
  VL53L0X (Sensor de Distancia)         ESP32
  =================================     ========
  
  Pin VIN (alimentacion)  ---------> Pin 3V3
  Pin GND (tierra)        ---------> Pin GND
  Pin SDA (datos)         ---------> Pin GPIO21
  Pin SCL (reloj)         ---------> Pin GPIO22
  Pin XSHUT               ---------> SIN CONECTAR
  Pin GPIO1               ---------> SIN CONECTAR
  
  Cableados:
  - VIN -> 3.3V: Cable ROJO
  - GND -> GND:  Cable NEGRO
  - SDA -> GPIO21: Cable VERDE
  - SCL -> GPIO22: Cable AZUL
`

### 4.3 Conexion MPU6050

`
  MPU6050 (Sensor de Movimiento)        ESP32
  =================================     ========
  
  Pin VCC (alimentacion)   ---------> Pin 3.3V  (MISMO que VL53L0X)
  Pin GND (tierra)         ---------> Pin GND   (MISMO que VL53L0X)
  Pin SDA (datos)          ---------> Pin GPIO21 (MISMO que VL53L0X)
  Pin SCL (reloj)          ---------> Pin GPIO22 (MISMO que VL53L0X)
  Pin AD0                  ---------> SIN CONECTAR (direccion 0x68)
  Pin INT                  ---------> SIN CONECTAR
  
  IMPORTANTE: Ambos sensores comparten los mismos cables I2C.
  Esto funciona porque tienen direcciones diferentes (0x29 y 0x68).
`

### 4.4 Conexion LEDs

`
  Cada LED necesita una resistencia de 220 ohm en serie.
  
  ESP32 GPIO26 ----[220 ohm]----(+) LED ROJO (-)---- GND
  ESP32 GPIO27 ----[220 ohm]----(+) LED VERDE (-)--- GND
  ESP32 GPIO14 ----[220 ohm]----(+) LED AZUL (-)---- GND
  
  Sin la resistencia, el LED se quemaria.
  Los LEDs tienen polaridad:
    - Patilla LARGA = positivo (+)
    - Patilla CORTA = negativo (-)
    - Lado PLANO = negativo (-)
`

### 4.5 Conexion Buzzer

`
  ESP32 GPIO25 ----(+) BUZZER (-)---- GND
  
  El buzzer pasivo tiene polaridad:
    - Pin + (marcado) -> GPIO25
    - Pin - (sin marcar) -> GND
`

### 4.6 Diagrama de Cableado Completo

`
  +------------------------------------------+
  |            PROTBOARD                     |
  |  +  +  +  +  +  +  +  +  +  +  +  +    |
  |  |  |  |  |  |  |  |  |  |  |  |  |    |
  |  +--+--+--+--+--+--+--+--+--+--+--+    |
  |  |  |  |  |  |  |  |  |  |  |  |  |    |
  |  +--+--+--+--+--+--+--+--+--+--+--+    |
  +------------------------------------------+
       |  |  |  |
       |  |  |  +-- Resistencia 220 ohm -- LED ROJO
       |  |  +---- Resistencia 220 ohm -- LED VERDE
       |  +------ Resistencia 220 ohm -- LED AZUL
       +--------- Buzzer (+)
  
  Fila + del protoboard: 3.3V del ESP32
  Fila - del protoboard: GND del ESP32
`

---

## 5. Codigo ESP32 Explicado

El codigo esta en:  3_CODIGO/esp32/lavamanos_sensores.ino

### 5.1 Estructura del Codigo

`cpp
// 1. INCLUIR LIBRERIAS
#include <Wire.h>              // Comunicacion I2C
#include <Adafruit_VL53L0X.h>  // Sensor de distancia
#include <Adafruit_MPU6050.h>  // Sensor de movimiento
#include <Adafruit_Sensor.h>   // Base para sensores Adafruit
#include <BLEDevice.h>         // Bluetooth Low Energy (para iPhone)

// 2. DECLARAR OBJETOS
Adafruit_VL53L0X lox = Adafruit_VL53L0X();
Adafruit_MPU6050 mpu;
BLEServer* pServer = NULL;
BLECharacteristic* pCharacteristic = NULL;

// 3. VARIABLES DE ESTADO
bool manosDetectadas = false;
bool frotando = false;
int umbralDistancia = 200;    // 200mm = 20cm
float umbralMovimiento = 12.0; // m/s2

// 4. CONFIGURAR EN SETUP()
void setup() {
  Wire.begin(21, 22);           // Iniciar I2C en GPIO21, 22
  lox.begin();                  // Iniciar VL53L0X
  mpu.begin();                  // Iniciar MPU6050
  BLEDevice::init("Lavamanos"); // Iniciar Bluetooth BLE
}

// 5. LEER SENSORES EN LOOP()
void loop() {
  // Leer VL53L0X cada 100ms
  // Leer MPU6050 cada 200ms
  // Enviar por BLE cuando hay cambio
  // Controlar LEDs segun estado
}
`

### 5.2 Protocolo BLE (Bluetooth Low Energy)

El ESP32 envia datos al iPhone usando BLE. iOS solo soporta BLE (no Bluetooth Classic).

`
  ESP32                              iPhone
  -----                              ------
    |   1. Anuncia servicio BLE        |
    |  ("Lavamanos-ESP32")             |
    |  ─────────────────────────────>  |
    |                                  |
    |   2. iPhone se conecta           |
    |  <─────────────────────────────  |
    |                                  |
    |   3. ESP32 envia datos           |
    |  "MANOS_DETECTADAS"              |
    |  ─────────────────────────────>  |
    |                                  |
    |   4. ESP32 envia movimiento      |
    |  "MOVIMIENTO:15.3"               |
    |  ─────────────────────────────>  |
    |                                  |
    |   5. iPhone envia comando        |
    |  "WASHING_COMPLETE"              |
    |  <─────────────────────────────  |
`

### 5.3 Mensajes BLE

| Mensaje | Quien envia | Significado |
|---------|-------------|-------------|
| MANOS_DETECTADAS | ESP32 -> iPhone | Distancia < 20cm |
| MANOS_ALEJADAS | ESP32 -> iPhone | Distancia > 30cm |
| FROTANDO_INICIO | ESP32 -> iPhone | Movimiento detectado |
| FROTANDO_FIN | ESP32 -> iPhone | Movimiento se detuvo |
| MOVIMIENTO:XX.X | ESP32 -> iPhone | Valor actual de aceleracion |
| WASHING_COMPLETE | iPhone -> ESP32 | Lavado completado (20s) |

---

## 6. Codigo iOS (iPhone) Explicado

El codigo esta en:  3_CODIGO/ios/BluetoothService.swift

### 6.1 Como funciona en iOS

`
  iOS (Swift)                          ESP32
  ----------                           -----
  
  1. CBCentralManager escanea
     busqueda: "Lavamanos"
     ─────────────────────────>
     
  2. Encuentra ESP32
     <─────────────────────────
     
  3. Se conecta al servicio BLE
     uuid: "12345678-1234-1234-1234-123456789abc"
     ─────────────────────────>
     
  4. Suscribe a notificaciones
     recibe datos cada 200ms
     <─────────────────────────
     
  5. Actualiza UI en SwiftUI
     @Published var distancia: Double
     @Published var frotando: Bool
`

### 6.2 Estructura del Codigo iOS

`swift
// BluetoothService.swift
// Maneja toda la comunicacion con el ESP32

import CoreBluetooth

class BluetoothService: NSObject, CBCentralManagerDelegate, CBPeripheralDelegate {
    // Estado
    @Published var isConnected = false
    @Published var distancia: Double = 0
    @Published var frotando: Bool = false
    
    // UUIDs del ESP32
    let serviceUUID = CBUUID(string: "12345678-1234-1234-1234-123456789abc")
    let characteristicUUID = CBUUID(string: "abcd1234-ab12-cd34-ef56-123456789abc")
    
    // Escanear ESP32
    func centralManager(_ central: CBCentralManager, didDiscover peripheral: ...) {
        // Encontro "Lavamanos" -> Conectar
    }
    
    // Recibir datos
    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: ...) {
        let message = String(data: value, encoding: .utf8)
        // "MANOS_DETECTADAS" -> actualizar UI
        // "MOVIMIENTO:15.3" -> actualizar grafico
    }
}
`

---

## 7. Solucion de Problemas Comunes

### 7.1 Sensores no detectan

| Sintoma | Causa | Solucion |
|---------|-------|----------|
| VL53L0X siempre lectura 0 | Cable SDA/SCL invertido | Verificar SDA->GPIO21, SCL->GPIO22 |
| MPU6050 no responde | Voltaje incorrecto | Usar 3.3V, NO 5V (se quema) |
| Ambos no funcionan | I2C sin pull-up | Agregar resistencias 4.7K a 3.3V |
| Lecturas inestables | Cables muy largos | Usar cables < 15cm |

### 7.2 Bluetooth no conecta

| Sintoma | Causa | Solucion |
|---------|-------|----------|
| iPhone no encuentra ESP32 | Usando Bluetooth Classic | Cambiar a BLE (ver codigo) |
| No se empareja | Nombre incorrecto | Verificar: "Lavamanos" |
| Se desconecta mucho | Fuera de alcance | Mantener < 10 metros |
| No recibe datos | Characteristica incorrecta | Verificar UUID en ambos lados |

### 7.3 LEDs no encienden

| Sintoma | Causa | Solucion |
|---------|-------|----------|
| LED no brilla | Pol invertida | Largo = +, Corto = - |
| LED se quema | Sin resistencia | Agregar 220 ohm |
| LED muy tenue | Resistencia muy alta | Usar 220 ohm (no 1K) |
| Todos parpadean juntos | Error en codigo | Verificar GPIO assignment |

### 7.4 Buzzer no suena

| Sintoma | Causa | Solucion |
|---------|-------|----------|
| No suena nada | Pol invertida | Pin marcado = +, otro = - |
| Suena muy bajo | Corriente insuficiente | Verificar conexion a GPIO25 |
| Suena constante | Error en codigo | Solo sonar en WASHING_COMPLETE |

---

## 8. Extensiones Futuras

1. **Sensor de flujo de agua:** Detectar si el agua esta corriendo
2. **Display OLED:** Mostrar estado sin depender del telefono
3. **Modo WiFi:** Enviar datos al backend por HTTP/WebSocket
4. **Bateria:** Modulo LiPo para portabilidad
5. **Multiples estaciones:** Varios lavamanos simultaneos
6. **Dashboard en tiempo real:** Graficar datos de uso

---

## 9. Referencias

- [ESP32 Arduino Core](https://docs.espressif.com/projects/esp32-arduino-core/)
- [Adafruit VL53L0X Library](https://github.com/adafruit/Adafruit_VL53L0X)
- [Adafruit MPU6050 Library](https://github.com/adafruit/Adafruit_MPU6050)
- [Apple CoreBluetooth](https://developer.apple.com/documentation/corebluetooth)
- [Protocolo OMS Lavado de Manos](https://www.who.int/publications/i/item/hand-hygiene-technical-reference-manual)

---

**Documento:** v2.0 | 19 Septiembre 2026  
**Autor:** Sistema de Verificacion de Lavado de Manos  
**Plataforma:** iOS (iPhone) + ESP32 + Arduino IDE
