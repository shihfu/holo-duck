// Animation engine: one table row per DuckState, no network code.
#include "duck.h"

#include <string.h>

#include "sprites.h"

namespace {

constexpr int GRID = 60, SCALE = 4, W = GRID * SCALE;
constexpr uint8_t BACKLIGHT = 180;            // 0-255; palette check used 100
constexpr uint32_t DARK_MS = 20 * 60000;      // backlight off after sleeping this long
constexpr uint32_t MIN = 60000, NEVER = 0;
constexpr uint32_t BLINK_MS = 120;            // eyes closed this long, every 2-6 s

// After timeout_ms in the state, go to next (Excited goes to the latest message).
// The frames come from SEQS in sprites.h (tools/animate.py), in the same order.
struct Rule {
  uint32_t timeout_ms;
  DuckState next;
};

using S = DuckState;
const Rule RULES[] = {
    /* Idle       */ {10 * MIN, S::Sleeping},
    /* Thinking   */ {30 * MIN, S::Idle},
    /* Working    */ {30 * MIN, S::Idle},
    /* Permission */ {30 * MIN, S::Idle},
    /* Success    */ {5000, S::Idle},
    /* Error      */ {5000, S::Idle},
    /* Sleeping   */ {NEVER, S::Sleeping},
    /* Excited    */ {2000, S::Idle},
    /* Welcome    */ {5000, S::Idle},
    /* Connecting */ {NEVER, S::Connecting},
};
static_assert(sizeof SEQS / sizeof *SEQS == sizeof RULES / sizeof *RULES, "one sequence per DuckState");

DuckState cur = S::Connecting, after_wake = S::Idle;
uint32_t since = 0;  // when cur was entered, or the last message for it
uint32_t t0 = 0;     // when cur was entered; the sequence plays from here
uint32_t blink_at = 2000, blink_start = 0u - BLINK_MS, rng = 1;

uint32_t next_blink(uint32_t now) {
  rng = rng * 1664525u + 1013904223u;
  return now + 2000 + (rng >> 8) % 4000;
}

void enter(DuckState s, uint32_t now) {
  if (s != cur) {
    t0 = now;
    blink_at = next_blink(now);
  }
  cur = s;
  since = now;
}

}  // namespace

void duck_set_state(DuckState s, uint32_t now) {
  if (s == S::Welcome) {  // session launch: greet only a resting duck
    if (cur == S::Sleeping || cur == S::Idle) enter(s, now);
    return;
  }
  if (s == S::Excited) after_wake = S::Idle;  // previewing the art
  else if (s != S::Connecting && (cur == S::Sleeping || cur == S::Excited)) {
    // A message wakes the duck: play Excited, then show the latest message.
    after_wake = s;
    if (cur == S::Sleeping && s != S::Sleeping) enter(S::Excited, now);
    return;
  }
  enter(s, now);
}

DuckState duck_state() { return cur; }

uint8_t duck_tick(uint32_t now, uint16_t *fb) {
  const Rule &r = RULES[(int)cur];
  if (r.timeout_ms != NEVER && now - since >= r.timeout_ms) enter(cur == S::Excited ? after_wake : r.next, now);

  if ((int32_t)(now - blink_at) >= 0) {
    blink_start = now;
    blink_at = next_blink(now);
  }
  const Seq &q = SEQS[(int)cur];
  const uint16_t *seq = q.closed && now - blink_start < BLINK_MS ? q.closed : q.open;
  const uint16_t *img = FRAMES[seq[(now - t0) / q.ms % q.n]];
  for (int y = 0; y < GRID; y++) {
    uint16_t *row = fb + y * SCALE * W;
    for (int x = 0; x < GRID; x++) {
      uint16_t c = img[y * GRID + x];
      c = (uint16_t)(c << 8 | c >> 8);  // TFT_eSprite keeps pixels byte-swapped
      for (int k = 0; k < SCALE; k++) row[x * SCALE + k] = c;
    }
    for (int k = 1; k < SCALE; k++) memcpy(row + k * W, row, W * sizeof *row);
  }
  return cur == S::Sleeping && now - since >= DARK_MS ? 0 : BACKLIGHT;
}
