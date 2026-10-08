package com.lavamanos.app

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import java.io.InputStream
import java.util.*

class MainActivity : AppCompatActivity() {
    
    private lateinit var statusText: TextView
    private lateinit var timerText: TextView
    private lateinit var progressText: TextView
    
    private var bluetoothSocket: BluetoothSocket? = null
    private var inputStream: InputStream? = null
    
    private var isWashing = false
    private var washingTime = 0
    private val requiredWashTime = 20
    
    private val handler = Handler(Looper.getMainLooper())
    private val timerRunnable = object : Runnable {
        override fun run() {
            if (isWashing && washingTime < requiredWashTime) {
                washingTime++
                updateTimerUI()
                handler.postDelayed(this, 1000)
            } else if (washingTime >= requiredWashTime) {
                washingComplete()
            }
        }
    }
    
    companion object {
        private const val TAG = "Lavamanos"
        // CAMBIAR POR LA MAC DE TU ESP32
        private const val ESP32_MAC = "XX:XX:XX:XX:XX:XX"
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        
        statusText = findViewById(R.id.statusText)
        timerText = findViewById(R.id.timerText)
        progressText = findViewById(R.id.progressText)
        
        connectBluetooth()
    }
    
    private fun connectBluetooth() {
        val bluetoothAdapter = BluetoothAdapter.getDefaultAdapter()
        
        if (bluetoothAdapter == null) {
            Toast.makeText(this, "Bluetooth no disponible", Toast.LENGTH_LONG).show()
            return
        }
        
        if (!bluetoothAdapter.isEnabled) {
            Toast.makeText(this, "Activa Bluetooth", Toast.LENGTH_LONG).show()
            return
        }
        
        Thread {
            try {
                val device = bluetoothAdapter.getRemoteDevice(ESP32_MAC)
                val uuid = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
                
                bluetoothSocket = device.createRfcommSocketToServiceRecord(uuid)
                bluetoothSocket?.connect()
                inputStream = bluetoothSocket?.inputStream
                
                runOnUiThread {
                    statusText.text = "Conectado al ESP32"
                }
                
                listenBluetooth()
                
            } catch (e: Exception) {
                Log.e(TAG, "Error de conexion", e)
                runOnUiThread {
                    statusText.text = "Error de conexion Bluetooth"
                }
            }
        }.start()
    }
    
    private fun listenBluetooth() {
        Thread {
            val buffer = ByteArray(1024)
            while (true) {
                try {
                    val bytes = inputStream?.read(buffer) ?: -1
                    if (bytes > 0) {
                        val message = String(buffer, 0, bytes).trim()
                        runOnUiThread { processMessage(message) }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Error leyendo Bluetooth", e)
                    break
                }
            }
        }.start()
    }
    
    private fun processMessage(message: String) {
        Log.d(TAG, "Mensaje ESP32: $message")
        
        when {
            message.contains("MANOS_DETECTADAS") -> {
                statusText.text = "Manos detectadas - Iniciando lavado"
                startWashing()
            }
            message.contains("MANOS_ALEJADAS") -> {
                statusText.text = "Manos alejadas - Cancelando"
                cancelWashing()
            }
            message.contains("FROTANDO_INICIO") -> {
                statusText.text = "Frotando manos..."
                progressText.text = "Progreso: ${washingTime}/${requiredWashTime}s"
            }
            message.contains("FROTANDO_FIN") -> {
                statusText.text = "Esperando movimiento..."
            }
            message.contains("MOVIMIENTO") -> {
                val magnitud = message.split(":").getOrNull(1) ?: "0"
                progressText.text = "Movimiento: $magnitud"
            }
        }
    }
    
    private fun startWashing() {
        if (!isWashing) {
            isWashing = true
            washingTime = 0
            handler.postDelayed(timerRunnable, 1000)
        }
    }
    
    private fun cancelWashing() {
        isWashing = false
        washingTime = 0
        handler.removeCallbacks(timerRunnable)
        
        runOnUiThread {
            timerText.text = "00:00"
            progressText.text = ""
            statusText.text = "Esperando manos..."
        }
    }
    
    private fun updateTimerUI() {
        val mins = washingTime / 60
        val secs = washingTime % 60
        timerText.text = String.format("%02d:%02d", mins, secs)
        
        val progress = (washingTime.toFloat() / requiredWashTime * 100).toInt()
        progressText.text = "Progreso: $progress%"
    }
    
    private fun washingComplete() {
        isWashing = false
        handler.removeCallbacks(timerRunnable)
        
        runOnUiThread {
            timerText.text = "00:20"
            progressText.text = "100%"
            statusText.text = "Lavado completado!"
            Toast.makeText(this, "Lavado completado!", Toast.LENGTH_LONG).show()
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        handler.removeCallbacks(timerRunnable)
        try {
            bluetoothSocket?.close()
        } catch (e: Exception) {
            Log.e(TAG, "Error cerrando Bluetooth", e)
        }
    }
}
