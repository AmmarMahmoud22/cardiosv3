// ============================================================
// Cardios — ESP32 + AD8232 single-lead ECG Wi-Fi telemetry
// ------------------------------------------------------------
// Samples the AD8232 analog output at 250 Hz and uploads batches of 750 samples
// (~3 s) to the Cardios backend at POST /device-ecg as JSON:
//   { "deviceId", "sampleRateHz", "leadOff", "samples": [ ... ] }
//
// SETUP (edit the configuration below before uploading):
//   1. WIFI_SSID / WIFI_PASSWORD  -> your 2.4 GHz Wi-Fi (ESP32 has no 5 GHz).
//   2. DEVICE_TOKEN               -> only if the server runs DEVICE_AUTH_ENABLED=true
//                                    (must equal the server's DEVICE_API_TOKEN).
// Do NOT commit real Wi-Fi credentials — keep them local to your board.
//
// WIRING: AD8232 OUTPUT->GPIO34, LO+ ->GPIO26, LO- ->GPIO27, 3.3V, GND.
// ============================================================
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <WiFi.h>

// ---------------- user configuration (placeholders) ----------------
const char* WIFI_SSID     = "BM";
const char* WIFI_PASSWORD = "11112222";

const char* DISCOVERY_SERVICE  = "cardios";
const char* DISCOVERY_PROTOCOL = "tcp";

// Device authentication token. Must match DEVICE_API_TOKEN on the server when
// DEVICE_AUTH_ENABLED=true. Leave as-is for an unauthenticated local demo.
const char* DEVICE_TOKEN = "YOUR_DEVICE_TOKEN";

// Set to 1 to also stream raw samples to the Arduino Serial Plotter for local
// debugging. Leave 0 for telemetry runs so printing does not add loop jitter.
#define STREAM_TO_SERIAL_PLOTTER 0

// ---------------- pins ----------------
const int ECG_PIN      = 34;
const int LO_PLUS_PIN  = 26;
const int LO_MINUS_PIN = 27;

// ---------------- sampling / batching ----------------
const int SAMPLE_RATE_HZ     = 250;   // keep at 250 Hz
const int BATCH_SAMPLE_COUNT = 750;   // ~3 s per batch
const unsigned long SAMPLE_PERIOD_US = 1000000UL / SAMPLE_RATE_HZ;

// ---------------- network timeouts ----------------
const unsigned long WIFI_CONNECT_TIMEOUT_MS = 15000;  // give up a connect attempt after 15 s
const unsigned long WIFI_RETRY_INTERVAL_MS  = 5000;   // throttle reconnect attempts
const uint16_t HTTP_CONNECT_TIMEOUT_MS = 3000;
const uint16_t HTTP_READ_TIMEOUT_MS    = 5000;

uint16_t ecgSamples[BATCH_SAMPLE_COUNT];
size_t sampleIndex = 0;
bool leadOffSeenInBatch = false;
unsigned long nextSampleMicros = 0;
unsigned long lastWifiAttemptMs = 0;
bool mdnsStarted = false;
String apiUrl;
String deviceId;

void clearApiDiscovery() {
  if (mdnsStarted) {
    MDNS.end();
    mdnsStarted = false;
  }
  apiUrl = "";
}

// Non-blocking-ish Wi-Fi connect with a bounded timeout, so a missing/!2.4GHz
// network can never hang the firmware forever. Returns true when connected.
bool ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) {
    return true;
  }

  clearApiDiscovery();

  // Throttle reconnect attempts so we don't stall the sampling loop on every batch.
  if (lastWifiAttemptMs != 0 && (millis() - lastWifiAttemptMs) < WIFI_RETRY_INTERVAL_MS) {
    return false;
  }
  lastWifiAttemptMs = millis();

  Serial.print("Connecting to Wi-Fi");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_CONNECT_TIMEOUT_MS) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Wi-Fi connected. ESP32 IP: ");
    Serial.println(WiFi.localIP());
    return true;
  }

  Serial.println("Wi-Fi connect timed out; will retry.");
  return false;
}

void configureDeviceIdentity() {
  if (deviceId.length() > 0) {
    return;
  }
  deviceId = "cardios-" + WiFi.macAddress();
  deviceId.replace(":", "");
  deviceId.toLowerCase();
  Serial.print("Device ID: ");
  Serial.println(deviceId);
}

bool startMdns() {
  if (mdnsStarted) {
    return true;
  }
  mdnsStarted = MDNS.begin(deviceId.c_str());
  if (!mdnsStarted) {
    Serial.println("Could not start mDNS discovery.");
  }
  return mdnsStarted;
}

bool discoverCardiosApi() {
  if (!startMdns()) {
    return false;
  }
  Serial.println("Looking for the Cardios API...");
  int serviceCount = MDNS.queryService(DISCOVERY_SERVICE, DISCOVERY_PROTOCOL);
  if (serviceCount == 0) {
    Serial.println("Cardios API not found. Will retry with the next batch.");
    return false;
  }
  apiUrl = "http://" + MDNS.address(0).toString() + ":" +
           String(MDNS.port(0)) + "/device-ecg";
  Serial.print("Cardios API discovered: ");
  Serial.println(apiUrl);
  return true;
}

void postBatch() {
  if (!ensureWifi()) {
    Serial.println("Skipping upload because Wi-Fi is disconnected.");
    return;
  }
  configureDeviceIdentity();
  if (apiUrl.length() == 0 && !discoverCardiosApi()) {
    return;
  }

  String payload;
  payload.reserve(BATCH_SAMPLE_COUNT * 6 + 256);
  payload += "{\"deviceId\":\"";
  payload += deviceId;
  payload += "\",\"sampleRateHz\":";
  payload += SAMPLE_RATE_HZ;
  payload += ",\"leadOff\":";
  payload += leadOffSeenInBatch ? "true" : "false";
  payload += ",\"samples\":[";

  for (size_t i = 0; i < BATCH_SAMPLE_COUNT; i++) {
    payload += ecgSamples[i];
    if (i + 1 < BATCH_SAMPLE_COUNT) {
      payload += ",";
    }
  }

  payload += "]}";

  HTTPClient http;
  http.setConnectTimeout(HTTP_CONNECT_TIMEOUT_MS);
  http.setTimeout(HTTP_READ_TIMEOUT_MS);
  http.begin(apiUrl);
  http.addHeader("Content-Type", "application/json");
  // Sent only when a real token is configured; ignored by the server when
  // device auth is disabled (local demo).
  if (strlen(DEVICE_TOKEN) > 0 && strcmp(DEVICE_TOKEN, "YOUR_DEVICE_TOKEN") != 0) {
    http.addHeader("X-Device-Token", DEVICE_TOKEN);
  }

  int statusCode = http.POST(payload);

  Serial.print("POST status: ");
  Serial.println(statusCode);

  if (statusCode > 0) {
    String response = http.getString();
    Serial.println("Server response:");
    Serial.println(response);
  } else {
    Serial.print("HTTP error: ");
    Serial.println(http.errorToString(statusCode));
  }

  http.end();

  if (statusCode <= 0) {
    apiUrl = "";
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  pinMode(LO_PLUS_PIN, INPUT);
  pinMode(LO_MINUS_PIN, INPUT);

  analogReadResolution(12);
  analogSetPinAttenuation(ECG_PIN, ADC_11db);

  // Let the radio recover dropped links on its own; don't wear flash with creds.
  WiFi.persistent(false);
  WiFi.setAutoReconnect(true);
  if (ensureWifi()) {
    configureDeviceIdentity();
    discoverCardiosApi();
  }

  nextSampleMicros = micros();
  Serial.println("ESP32 AD8232 ECG sender is ready.");
}

void loop() {
  unsigned long now = micros();
  if ((long)(now - nextSampleMicros) < 0) {
    return;  // not time for the next sample yet
  }
  nextSampleMicros += SAMPLE_PERIOD_US;

  bool leadOffNow = digitalRead(LO_PLUS_PIN) == HIGH || digitalRead(LO_MINUS_PIN) == HIGH;
  leadOffSeenInBatch = leadOffSeenInBatch || leadOffNow;

  uint16_t rawValue = analogRead(ECG_PIN);
  ecgSamples[sampleIndex] = rawValue;
  sampleIndex++;

#if STREAM_TO_SERIAL_PLOTTER
  Serial.println(rawValue);
#endif

  if (sampleIndex >= BATCH_SAMPLE_COUNT) {
    postBatch();
    sampleIndex = 0;
    leadOffSeenInBatch = false;
    // Resync the sampling clock: the blocking POST consumed real time, so reset
    // the cadence instead of bursting samples to "catch up" to it.
    nextSampleMicros = micros();
  }
}
