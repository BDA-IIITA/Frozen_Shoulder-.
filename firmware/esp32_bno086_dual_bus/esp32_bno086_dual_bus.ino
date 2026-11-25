// ShoulderSense: classic dual-I2C ESP32, two BNO086 devices at 0x4B.
// Arduino libraries: SparkFun BNO080 Cortex Based IMU (BNO080 class),
// ArduinoJson 7. Select the correct ESP32 board in Arduino IDE.
// The newer SparkFun BNO08x library shares SH-2 driver state across instances.

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <SparkFun_BNO080_Arduino_Library.h>
#include <WiFi.h>
#include <Wire.h>
#include <esp_timer.h>
#include <math.h>

constexpr char WIFI_SSID[] = "YOUR_WIFI_NAME";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";
constexpr char BACKEND_URL[] = "http://10.245.161.252:8000/api/sensor/ingest";
constexpr char DEVICE_ID[] = "esp32-shoulder-01";

constexpr uint8_t IMU_ADDRESS = 0x4B;
// Wire each module's active-low INT/H_INT pin separately. 255 selects
// best-effort polling only for boards where interrupt wiring is unavailable.
constexpr uint8_t CHEST_INT = 25;
constexpr uint8_t WRIST_INT = 26;
constexpr uint32_t I2C_FREQUENCY = 100000;
constexpr uint16_t REPORT_INTERVAL_MS = 20;
constexpr uint32_t POST_INTERVAL_MS = 50;
constexpr int64_t MAX_READ_AGE_US = 75000;
constexpr int64_t MAX_READ_SKEW_US = 25000;

struct Orientation {
  float x = 0, y = 0, z = 0, w = 0;
  uint8_t accuracy = 0;
  int64_t readUs = 0;
  bool fresh = false;
};

TwoWire chestBus(0);
TwoWire wristBus(1);
BNO080 chestImu;
BNO080 wristImu;
Orientation chest;
Orientation wrist;
bool chestOnline = false;
bool wristOnline = false;
uint32_t lastPostMs = 0;
uint32_t lastLogMs = 0;
uint32_t delivered = 0;
uint32_t failed = 0;
uint32_t droppedPairs = 0;

bool setupImu(BNO080 &imu, TwoWire &bus, int sda, int scl, uint8_t interruptPin, const char *role) {
  if (!bus.begin(sda, scl, I2C_FREQUENCY)) {
    Serial.printf("[%s] Could not initialize I2C on GPIO %d/%d\n", role, sda, scl);
    return false;
  }
  if (!imu.begin(IMU_ADDRESS, bus, interruptPin)) {
    Serial.printf("[%s] No BNO086 response at 0x4B on GPIO %d/%d\n", role, sda, scl);
    return false;
  }
  // Consume any startup reset notification before configuring the report.
  imu.hasReset();
  imu.enableRotationVector(REPORT_INTERVAL_MS);
  Serial.printf("[%s] BNO086 at 0x4B, SDA %d, SCL %d, INT %u\n", role, sda, scl, interruptPin);
  return true;
}

void pollImu(BNO080 &imu, Orientation &sample) {
  // Bound the amount of work per bus so the other bus is also serviced.
  for (int i = 0; i < 6; ++i) {
    const uint16_t report = imu.getReadings();
    if (imu.hasReset()) {
      sample.fresh = false;
      imu.enableRotationVector(REPORT_INTERVAL_MS);
      return;
    }
    if (report == 0) return;
    if (report != SENSOR_REPORTID_ROTATION_VECTOR) continue;

    sample.x = imu.getQuatI();
    sample.y = imu.getQuatJ();
    sample.z = imu.getQuatK();
    sample.w = imu.getQuatReal();
    sample.accuracy = imu.getQuatAccuracy();
    sample.readUs = esp_timer_get_time();
    const float normSquared = sample.x * sample.x + sample.y * sample.y +
                              sample.z * sample.z + sample.w * sample.w;
    sample.fresh = isfinite(normSquared) && normSquared >= 0.81f && normSquared <= 1.21f;
  }
}

void writeOrientation(JsonObject sensor, const Orientation &sample) {
  JsonObject quaternion = sensor["quaternion"].to<JsonObject>();
  quaternion["x"] = sample.x;
  quaternion["y"] = sample.y;
  quaternion["z"] = sample.z;
  quaternion["w"] = sample.w;
  sensor["calibration_status"] = sample.accuracy;
  // This is when the ESP32 read the report, on the shared ESP32 clock.
  // The sensor acquisition clocks are independent. Do not call this sample_timestamp.
  sensor["report_read_timestamp"] = sample.readUs / 1000000.0;
}

void postPair(int64_t packetUs) {
  JsonDocument doc;
  doc["source"] = "live";
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = packetUs / 1000000.0;
  JsonObject sensors = doc["sensors"].to<JsonObject>();
  writeOrientation(sensors["chest"].to<JsonObject>(), chest);
  writeOrientation(sensors["wrist"].to<JsonObject>(), wrist);
  // Consume each pair once, including on HTTP error. Never re-send stale orientation.
  chest.fresh = false;
  wrist.fresh = false;

  String body;
  serializeJson(doc, body);
  WiFiClient connection;
  HTTPClient http;
  if (!http.begin(connection, BACKEND_URL)) {
    ++failed;
    Serial.println("[HTTP] Invalid backend URL");
    return;
  }
  http.setConnectTimeout(350);
  http.setTimeout(400);
  http.addHeader("Content-Type", "application/json");
  const int status = http.POST(body);
  if (status >= 200 && status < 300) {
    ++delivered;
  } else {
    ++failed;
    if (failed == 1 || failed % 20 == 0) {
      if (status > 0) Serial.printf("[HTTP] %d %s\n", status, http.getString().c_str());
      else Serial.printf("[HTTP] %s\n", HTTPClient::errorToString(status).c_str());
    }
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  chestOnline = setupImu(chestImu, chestBus, 21, 22, CHEST_INT, "chest");
  wristOnline = setupImu(wristImu, wristBus, 18, 19, WRIST_INT, "wrist");
  Serial.println("[Wi-Fi] Connect the ESP32 and backend computer to the same network.");
  Serial.printf("[HTTP] %s\n", BACKEND_URL);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void loop() {
  if (chestOnline) pollImu(chestImu, chest);
  if (wristOnline) pollImu(wristImu, wrist);
  const uint32_t nowMs = millis();
  const int64_t nowUs = esp_timer_get_time();

  if (chest.fresh && nowUs - chest.readUs > MAX_READ_AGE_US) chest.fresh = false;
  if (wrist.fresh && nowUs - wrist.readUs > MAX_READ_AGE_US) wrist.fresh = false;

  if (chest.fresh && wrist.fresh && nowMs - lastPostMs >= POST_INTERVAL_MS) {
    const int64_t skew = chest.readUs - wrist.readUs;
    if (skew > MAX_READ_SKEW_US || skew < -MAX_READ_SKEW_US) {
      ++droppedPairs;
      if (skew > 0) wrist.fresh = false;
      else chest.fresh = false;
    } else if (WiFi.status() == WL_CONNECTED) {
      lastPostMs = nowMs;
      postPair(nowUs);
    }
  }

  if (nowMs - lastLogMs >= 3000) {
    lastLogMs = nowMs;
    const bool chestReporting = chest.readUs > 0 && nowUs - chest.readUs < 500000;
    const bool wristReporting = wrist.readUs > 0 && nowUs - wrist.readUs < 500000;
    Serial.printf("[Status] Wi-Fi %s | chest %s | wrist %s | HTTP OK %lu | failed %lu | unpaired %lu\n",
                  WiFi.status() == WL_CONNECTED ? "connected" : "connecting",
                  chestReporting ? "reporting" : chestOnline ? "waiting" : "offline",
                  wristReporting ? "reporting" : wristOnline ? "waiting" : "offline",
                  static_cast<unsigned long>(delivered), static_cast<unsigned long>(failed),
                  static_cast<unsigned long>(droppedPairs));
  }
  delay(1);
}
