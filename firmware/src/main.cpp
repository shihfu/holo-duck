#include <ESPmDNS.h>
#include <TFT_eSPI.h>
#include <WebServer.h>
#include <WiFi.h>

#include "duck.h"
#include "secrets.h"

constexpr int BL_PIN = 20, BL_CH = 0;
constexpr uint32_t FRAME_MS = 33;  // ~30 FPS; a full push takes ~23 ms

TFT_eSPI tft;
TFT_eSprite frame(&tft);
WebServer server(80);

// The prism mirrors the image, but TFT_eSPI 2.5.0 has no mirrored ST7789
// rotations (setRotation(4) == 0). Rotation 2 writes MADCTL MX|MY; clearing
// MX mirrors it. MX is the full 240 px axis, so CGRAM offsets stay valid.
void setPrismRotation() {
  tft.setRotation(2);
  tft.writecommand(TFT_MADCTL);
  tft.writedata(TFT_MAD_MY | TFT_MAD_COLOR_ORDER);
}

// Body is a form field (`curl -d state=working`): WebServer drops bare
// form bodies that have no `=`.
void handleState() {
  String s = server.arg("state");
  for (size_t i = 0; i < sizeof DUCK_STATE_NAMES / sizeof *DUCK_STATE_NAMES; i++) {
    if (s == DUCK_STATE_NAMES[i]) {
      Serial.printf("duck: state %s\n", DUCK_STATE_NAMES[i]);
      duck_set_state((DuckState)i, millis());
      server.send(204);
      return;
    }
  }
  server.send(400, "text/plain", "unknown state\n");
}

void setup() {
  Serial.begin(115200);
  ledcSetup(BL_CH, 5000, 8);
  ledcAttachPin(BL_PIN, BL_CH);
  tft.init();
  tft.invertDisplay(1);
  setPrismRotation();
  frame.setAttribute(PSRAM_ENABLE, false);  // internal RAM pushes faster
  frame.createSprite(240, 240);

  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // modem sleep delays requests up to ~1 s; hooks give curl 1 s
  WiFi.setHostname("duck");
  WiFi.begin(WIFI_SSID, WIFI_PASS);  // reconnects on its own if dropped
  server.on("/state", HTTP_POST, handleState);
  server.begin();
}

// Shows Connecting until Wi-Fi is up, and again whenever it drops.
void watchWifi(uint32_t now) {
  static bool online = false, mdns = false;
  bool up = WiFi.status() == WL_CONNECTED;
  if (up == online) return;
  online = up;
  duck_set_state(up ? DuckState::Idle : DuckState::Connecting, now);
  if (up && !mdns) {
    mdns = MDNS.begin("duck");
    MDNS.addService("http", "tcp", 80);
  }
  if (up) Serial.printf("duck: ready at http://duck.local/state (%s)\n", WiFi.localIP().toString().c_str());
  else Serial.println("duck: wifi lost");
}

void loop() {
  static uint32_t last = 0;
  server.handleClient();
  uint32_t now = millis();
  watchWifi(now);
  if (now - last < FRAME_MS) return;
  last = now;
  ledcWrite(BL_CH, duck_tick(now, (uint16_t *)frame.getPointer()));
  frame.pushSprite(0, 0);
}
