#pragma once
#include <stdint.h>

enum class DuckState : uint8_t {
  Idle, Thinking, Working, Permission, Success, Error, Sleeping, Excited, Welcome,
  Connecting,  // firmware-only: joining Wi-Fi or Wi-Fi lost
};

// Names accepted by POST /state, in DuckState order.
static const char *const DUCK_STATE_NAMES[] = {
    "idle", "thinking", "working", "permission",
    "success", "error", "sleeping", "excited", "welcome"};

void duck_set_state(DuckState s, uint32_t now_ms);
DuckState duck_state();
// Draws one 240x240 frame into fb (TFT_eSprite byte order) and applies
// timeouts. Returns the backlight level (0-255).
uint8_t duck_tick(uint32_t now_ms, uint16_t *fb);
