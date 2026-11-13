// Host-side tests for the state rules: pio test -e native
#include <unity.h>

#include "duck.h"
#include "sprites.h"

static uint16_t fb[240 * 240];
using S = DuckState;

// Connecting is entered from any state, so it resets the engine between tests.
void setUp() {
  duck_set_state(S::Connecting, 0);
  duck_set_state(S::Idle, 0);
}
void tearDown() {}

void test_message_wakes_sleeping_duck_with_excited() {
  duck_set_state(S::Sleeping, 0);
  duck_set_state(S::Thinking, 1000);
  TEST_ASSERT_EQUAL(S::Excited, duck_state());
  duck_set_state(S::Working, 1500);  // latest message wins after the wake
  duck_tick(2999, fb);
  TEST_ASSERT_EQUAL(S::Excited, duck_state());
  duck_tick(3000, fb);
  TEST_ASSERT_EQUAL(S::Working, duck_state());
}

void test_excited_preview_returns_to_idle() {
  duck_set_state(S::Excited, 0);
  duck_tick(2000, fb);
  TEST_ASSERT_EQUAL(S::Idle, duck_state());
}

void test_timeouts() {
  duck_set_state(S::Success, 0);
  duck_tick(4999, fb);
  TEST_ASSERT_EQUAL(S::Success, duck_state());
  duck_tick(5000, fb);
  TEST_ASSERT_EQUAL(S::Idle, duck_state());
  duck_tick(5000 + 10 * 60000, fb);
  TEST_ASSERT_EQUAL(S::Sleeping, duck_state());
}

void test_stale_working_returns_to_idle() {
  duck_set_state(S::Working, 0);
  duck_set_state(S::Working, 25 * 60000);  // each message restarts the stale timer
  duck_tick(50 * 60000, fb);
  TEST_ASSERT_EQUAL(S::Working, duck_state());
  duck_tick(55 * 60000, fb);
  TEST_ASSERT_EQUAL(S::Idle, duck_state());
}

void test_backlight_turns_off_after_sleeping_a_while() {
  duck_set_state(S::Sleeping, 0);
  TEST_ASSERT_NOT_EQUAL(0, duck_tick(1000, fb));
  TEST_ASSERT_NOT_EQUAL(0, duck_tick(19 * 60000, fb));
  TEST_ASSERT_EQUAL(0, duck_tick(20 * 60000, fb));
}

void test_connecting_does_not_wake() {
  duck_set_state(S::Sleeping, 0);
  duck_set_state(S::Connecting, 1000);
  TEST_ASSERT_EQUAL(S::Connecting, duck_state());
}

void test_welcome_wakes_dark_duck_without_excited() {
  duck_set_state(S::Sleeping, 0);
  TEST_ASSERT_EQUAL(0, duck_tick(20 * 60000, fb));
  duck_set_state(S::Welcome, 20 * 60000);
  TEST_ASSERT_EQUAL(S::Welcome, duck_state());
  TEST_ASSERT_NOT_EQUAL(0, duck_tick(20 * 60000, fb));
  duck_tick(20 * 60000 + 4999, fb);
  TEST_ASSERT_EQUAL(S::Welcome, duck_state());
  duck_tick(20 * 60000 + 5000, fb);
  TEST_ASSERT_EQUAL(S::Idle, duck_state());
}

void test_welcome_from_idle() {
  duck_set_state(S::Welcome, 1000);
  TEST_ASSERT_EQUAL(S::Welcome, duck_state());
}

void test_welcome_ignored_while_busy() {
  duck_set_state(S::Working, 0);
  duck_set_state(S::Welcome, 1000);
  TEST_ASSERT_EQUAL(S::Working, duck_state());
}

// The engine draws grid pixel (x, y) as a 4x4 block, byte-swapped for TFT_eSprite.
static bool shows(const uint16_t *img) {
  for (int i = 0; i < 60 * 60; i++) {
    uint16_t c = img[i];
    if (fb[i / 60 * 4 * 240 + i % 60 * 4] != (uint16_t)(c << 8 | c >> 8)) return false;
  }
  return true;
}

void test_sequence_runs_from_state_entry_not_from_each_message() {
  const Seq &w = SEQS[(int)S::Working];
  TEST_ASSERT_NOT_EQUAL(w.open[0], w.open[1]);
  duck_set_state(S::Working, 1000);
  duck_tick(1000, fb);
  TEST_ASSERT_TRUE(shows(FRAMES[w.open[0]]));
  duck_set_state(S::Working, 1000 + w.ms);
  duck_tick(1000 + w.ms, fb);
  TEST_ASSERT_TRUE(shows(FRAMES[w.open[1]]));
}

int main() {
  UNITY_BEGIN();
  RUN_TEST(test_message_wakes_sleeping_duck_with_excited);
  RUN_TEST(test_excited_preview_returns_to_idle);
  RUN_TEST(test_timeouts);
  RUN_TEST(test_stale_working_returns_to_idle);
  RUN_TEST(test_backlight_turns_off_after_sleeping_a_while);
  RUN_TEST(test_connecting_does_not_wake);
  RUN_TEST(test_welcome_wakes_dark_duck_without_excited);
  RUN_TEST(test_welcome_from_idle);
  RUN_TEST(test_welcome_ignored_while_busy);
  RUN_TEST(test_sequence_runs_from_state_entry_not_from_each_message);
  return UNITY_END();
}
