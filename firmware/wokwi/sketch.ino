#include <WiFi.h>
#include <PubSubClient.h>
#include "DHTesp.h"

// ===== CHANGE THIS LINE: must match FRESHSENSE_MQTT_TOPIC in the backend =====
const char* TOPIC = "freshsense/fs-CHANGE-ME/tag/C-001";

const char* WIFI_SSID = "Wokwi-GUEST";   // Wokwi's built-in virtual WiFi, no password
const char* WIFI_PASS = "";
const char* MQTT_HOST = "broker.hivemq.com";
const int   MQTT_PORT = 1883;

const int DHT_PIN = 15;
const int POT_PIN = 34;
const int BTN_PIN = 4;
const int LED_PIN = 2;
const float TEMP_ALERT_C = 7.0;          // LED turns on above this (dairy safe limit)

DHTesp dht;
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

bool doorOpen = false;
int lastBtn = HIGH;
unsigned long lastPublish = 0;

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASS, 6);
  while (WiFi.status() != WL_CONNECTED) { delay(250); Serial.print("."); }
  Serial.println(" connected!");
}

void connectMQTT() {
  while (!mqtt.connected()) {
    String clientId = "freshsense-tag-" + String((uint32_t)esp_random(), HEX);
    Serial.print("Connecting to MQTT...");
    if (mqtt.connect(clientId.c_str())) {
      Serial.println(" connected!");
    } else {
      Serial.print(" failed, rc="); Serial.println(mqtt.state());
      delay(1000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  dht.setup(DHT_PIN, DHTesp::DHT22);
  connectWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  connectMQTT();
}

void loop() {
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  // Button toggles the door state (press once = open, press again = closed)
  int btn = digitalRead(BTN_PIN);
  if (btn == LOW && lastBtn == HIGH) {
    doorOpen = !doorOpen;
    Serial.println(doorOpen ? "DOOR OPEN" : "DOOR CLOSED");
    delay(50);
  }
  lastBtn = btn;

  if (millis() - lastPublish >= 2000) {
    lastPublish = millis();
    TempAndHumidity d = dht.getTempAndHumidity();
    if (isnan(d.temperature) || isnan(d.humidity)) {
      Serial.println("DHT read failed");
      return;
    }
    int raw = analogRead(POT_PIN);            // 0..4095
    int voc = map(raw, 0, 4095, 0, 500);      // VOC index 0..500
    digitalWrite(LED_PIN, d.temperature > TEMP_ALERT_C ? HIGH : LOW);

    char payload[220];
    snprintf(payload, sizeof(payload),
      "{\"crate_id\":\"C-001\",\"temp_c\":%.2f,\"humidity\":%.1f,\"voc_index\":%d,\"door_open\":%s,\"source\":\"wokwi\"}",
      d.temperature, d.humidity, voc, doorOpen ? "true" : "false");
    mqtt.publish(TOPIC, payload);
    Serial.println(payload);
  }
}
