/*
 * ==============================================================================
 * Project: ShoulderSense — Wearable IMU Dual/Single BNO086 Telemetry Hub
 * Target:  ESP32 DevKit V1 (ESP32-WROOM-32)
 * Library: SparkFun_BNO08x_Arduino_Library
 *
 * Auto-detects Single IMU or Dual IMUs:
 *   - If 1 IMU is connected (either at 0x4A or 0x4B): Auto-assigns to Upper Arm
 *   - If 2 IMUs are connected: 0x4A = Chest Reference, 0x4B = Upper Arm
 * ==============================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include "SparkFun_BNO08x_Arduino_Library.h"

// ========================== USER CONFIGURATION ==========================
// 1. Enter your Wi-Fi details (must be on the same network as your laptop)
const char* WIFI_SSID     = "YOUR_WIFI_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// 2. Enter your Laptop's Local IP Address (Port 8000)
//    Find on Mac: Terminal -> ipconfig getifaddr en0
//    Example: "http://192.168.1.105:8000/api/sensor/ingest"
const char* BACKEND_URL   = "http://192.168.1.100:8000/api/sensor/ingest";

// 3. Pin Definitions (Default ESP32 I2C & Status LED)
#define I2C_SDA_PIN 21
#define I2C_SCL_PIN 22
#define LED_PIN     2    // Onboard status LED (GPIO 2 on DevKit V1)

// 4. Transmission Rate: 50 ms = 20 packets per second (20 Hz)
const unsigned long SAMPLE_INTERVAL_MS = 50;
// ========================================================================

BNO08x imu1; // Address 0x4A
BNO08x imu2; // Address 0x4B

bool sensor4A_Found = false;
bool sensor4B_Found = false;

bool singleSensorMode = false;

unsigned long lastSampleTime = 0;
unsigned long packetCount    = 0;

WiFiClient wifiClient;
HTTPClient httpClient;

// Cached orientation variables
float chest_x = 0.0, chest_y = 0.0, chest_z = 0.0, chest_w = 1.0;
byte  chest_status = 0;

float arm_x = 0.0, arm_y = 0.0, arm_z = 0.0, arm_w = 1.0;
byte  arm_status = 0;

// Scan I2C bus and report findings
void detectSensors() {
  Serial.println("\n[I2C Scanner] Scanning bus for BNO086 sensors...");
  
  Wire.beginTransmission(0x4A);
  if (Wire.endTransmission() == 0) {
    sensor4A_Found = true;
    Serial.println("  --> [FOUND] Sensor at Address 0x4A");
  }

  Wire.beginTransmission(0x4B);
  if (Wire.endTransmission() == 0) {
    sensor4B_Found = true;
    Serial.println("  --> [FOUND] Sensor at Address 0x4B");
  }

  if (!sensor4A_Found && !sensor4B_Found) {
    Serial.println("  [ERROR] No sensor detected at 0x4A or 0x4B!");
    Serial.println("  --> Check 3.3V, GND, SDA (GPIO 21), and SCL (GPIO 22).");
  } else if ((sensor4A_Found && !sensor4B_Found) || (!sensor4A_Found && sensor4B_Found)) {
    singleSensorMode = true;
    Serial.println("  [MODE] Single IMU detected! Auto-assigning to Upper Arm (Movement Tracker).");
  } else {
    singleSensorMode = false;
    Serial.println("  [MODE] Dual IMUs detected! (0x4A = Torso, 0x4B = Upper Arm).");
  }
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH); // Solid ON when connected
    return;
  }

  Serial.printf("[WiFi] Connecting to \"%s\"", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 25) {
    digitalWrite(LED_PIN, !digitalRead(LED_PIN)); // Fast blink while searching for Wi-Fi
    delay(400);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(LED_PIN, HIGH); // Solid ON when Wi-Fi connected!
    Serial.println(" CONNECTED!");
    Serial.print("[WiFi] ESP32 IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.printf("[WiFi] Target Ingestion URL: %s\n\n", BACKEND_URL);
  } else {
    digitalWrite(LED_PIN, LOW); // OFF if failed
    Serial.println("\n[WiFi] Connection timed out! Will retry during loop...");
  }
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.begin(115200);
  delay(1500);

  Serial.println("\n=======================================================");
  Serial.println("     ShoulderSense — Smart Wearable IMU Hub            ");
  Serial.println("=======================================================");

  // 1. Initialize I2C Bus at 400kHz Fast-Mode
  Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN, 400000);

  // 2. Scan for physical hardware on bus
  detectSensors();

  // 3. Initialize Sensor at 0x4A (if present)
  if (sensor4A_Found) {
    Serial.print("[Init] Starting BNO086 at 0x4A... ");
    if (imu1.begin(0x4A, Wire)) {
      delay(100);
      imu1.enableRotationVector(SAMPLE_INTERVAL_MS);
      delay(100);
      Serial.println("ONLINE!");
    } else {
      Serial.println("FAILED!");
      sensor4A_Found = false;
    }
  }

  // 4. Initialize Sensor at 0x4B (if present)
  if (sensor4B_Found) {
    Serial.print("[Init] Starting BNO086 at 0x4B... ");
    if (imu2.begin(0x4B, Wire)) {
      delay(100);
      imu2.enableRotationVector(SAMPLE_INTERVAL_MS);
      delay(100);
      Serial.println("ONLINE!");
    } else {
      Serial.println("FAILED!");
      sensor4B_Found = false;
    }
  }

  // 5. Connect to Wi-Fi
  connectWiFi();

  Serial.println("\n[Setup Ready] Streaming IMU orientation to website...\n");
}

void loop() {
  // Service SHTP reports continuously from whichever sensor is connected
  if (sensor4A_Found) {
    if (imu1.wasReset()) {
      Serial.println("[WARN] Sensor 0x4A reset detected! Re-enabling rotation vector...");
      imu1.enableRotationVector(SAMPLE_INTERVAL_MS);
      delay(50);
    }
    if (imu1.getSensorEvent()) {
      float qx = imu1.getQuatI();
      float qy = imu1.getQuatJ();
      float qz = imu1.getQuatK();
      float qw = imu1.getQuatReal();
      byte  st = imu1.getQuatAccuracy();

      if (singleSensorMode) {
        // If single sensor, map it to the Arm so the arm moves on the website!
        arm_x = qx; arm_y = qy; arm_z = qz; arm_w = qw; arm_status = st;
      } else {
        // Dual sensor mode: 0x4A is Torso reference
        chest_x = qx; chest_y = qy; chest_z = qz; chest_w = qw; chest_status = st;
      }
    }
  }

  if (sensor4B_Found) {
    if (imu2.wasReset()) {
      Serial.println("[WARN] Sensor 0x4B reset detected! Re-enabling rotation vector...");
      imu2.enableRotationVector(SAMPLE_INTERVAL_MS);
      delay(50);
    }
    if (imu2.getSensorEvent()) {
      float qx = imu2.getQuatI();
      float qy = imu2.getQuatJ();
      float qz = imu2.getQuatK();
      float qw = imu2.getQuatReal();
      byte  st = imu2.getQuatAccuracy();

      // 0x4B is always the Upper Arm
      arm_x = qx; arm_y = qy; arm_z = qz; arm_w = qw; arm_status = st;
    }
  }

  // Rate Limiter: Send telemetry packet at 20 Hz (every 50 ms)
  unsigned long now = millis();
  if (now - lastSampleTime >= SAMPLE_INTERVAL_MS) {
    lastSampleTime = now;

    if (WiFi.status() != WL_CONNECTED) {
      connectWiFi();
      return;
    }

    // -------------------------------------------------------------
    // Build JSON Payload matching ShoulderSense Backend Schema
    // -------------------------------------------------------------
    #if ARDUINOJSON_VERSION_MAJOR >= 7
      JsonDocument doc;
    #else
      StaticJsonDocument<512> doc;
    #endif

    doc["timestamp"] = (double)now / 1000.0;
    doc["device_id"] = "esp32-shoulder-01";
    doc["source"]    = "live";

    JsonObject sensors = doc.createNestedObject("sensors");

    // 1. Torso / Chest Reference
    JsonObject chestObj = sensors.createNestedObject("chest");
    JsonObject chestQ   = chestObj.createNestedObject("quaternion");
    chestQ["x"] = round(chest_x * 10000.0) / 10000.0;
    chestQ["y"] = round(chest_y * 10000.0) / 10000.0;
    chestQ["z"] = round(chest_z * 10000.0) / 10000.0;
    chestQ["w"] = round(chest_w * 10000.0) / 10000.0;
    chestObj["calibration_status"] = chest_status;

    // 2. Upper Arm
    JsonObject armObj = sensors.createNestedObject("upper_arm");
    JsonObject armQ   = armObj.createNestedObject("quaternion");
    armQ["x"] = round(arm_x * 10000.0) / 10000.0;
    armQ["y"] = round(arm_y * 10000.0) / 10000.0;
    armQ["z"] = round(arm_z * 10000.0) / 10000.0;
    armQ["w"] = round(arm_w * 10000.0) / 10000.0;
    armObj["calibration_status"] = arm_status;

    String jsonBuffer;
    serializeJson(doc, jsonBuffer);

    // -------------------------------------------------------------
    // Transmit via HTTP POST to FastAPI Ingestion Endpoint
    // -------------------------------------------------------------
    httpClient.begin(wifiClient, BACKEND_URL);
    httpClient.addHeader("Content-Type", "application/json");

    int httpCode = httpClient.POST(jsonBuffer);

    if (httpCode == 200) {
      packetCount++;
      // Log to Serial Monitor every 1 second (every 20 packets)
      if (packetCount % 20 == 0) {
        Serial.printf("[TX #%lu] Live Packet OK | Arm Quat: [%.2f, %.2f, %.2f, %.2f]\n",
                      packetCount, arm_x, arm_y, arm_z, arm_w);
      }
    } else if (httpCode > 0) {
      Serial.printf("[HTTP ERROR] Server responded with code: %d\n", httpCode);
    } else {
      Serial.printf("[HTTP ERROR] Failed to send, error: %s\n", httpClient.errorToString(httpCode).c_str());
    }

    httpClient.end();
  }
}
