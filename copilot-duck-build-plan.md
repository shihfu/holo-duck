# Copilot Duck Hologram --- Build Plan

## 1. Project Goal

Build a small, expressive **pixel-art duck hologram** that sits on top
of a computer monitor and reflects the state of a **GitHub Copilot CLI
session** running on the user's Mac.

The first prototype will use the **Waveshare ESP32-S3-LCD-1.3 "with case
and prism cube" kit (SKU 30559)**.
Wiki: <https://www.waveshare.com/wiki/ESP32-S3-LCD-1.3>

| Part           | Detail                                                        |
|----------------|---------------------------------------------------------------|
| MCU            | ESP32-S3R8, dual-core LX7 @ 240 MHz, 512 KB SRAM              |
| Memory         | 16 MB flash (QIO), 8 MB PSRAM (OPI)                           |
| Display        | 1.3" 240×240 IPS, **ST7789VW over SPI**, 262K colour          |
| Optics         | Prism cube (beam splitter) over the LCD, plastic case         |
| Wireless       | 2.4 GHz Wi-Fi b/g/n, BLE 5                                    |
| IMU            | QMI8658 6-axis                                                |
| USB            | USB-C via **CH343 USB-UART bridge**                           |
| Other          | TF card slot, MX1.25 Li-ion connector + charger, 16-pin GPIO  |
| Not on board   | Speaker/buzzer, microphone, touch                             |

The long-term goal is a clean, minimal monitor-top object rather than a
conventional electronics enclosure.

------------------------------------------------------------------------

## 2. Core Experience

The duck should feel like a tiny character living on the monitor.

It should:

-   React to what Copilot is doing.
-   Have smooth, expressive animation.
-   Communicate state at a glance without requiring text.
-   Remain visually appealing when idle.
-   Feel alive even when nothing is happening.
-   Eventually be able to react to physical movement/touch if useful.

### Initial Copilot states

One state per tile in `juno-design-mock.png`:

| State        | Mock tile         | Duck behavior                                           |
|--------------|-------------------|---------------------------------------------------------|
| `IDLE`       | IDLE              | Relaxed, blinking, subtle breathing/bobbing             |
| `THINKING`   | THINKING          | Looks around, thoughtful expression, thought bubble     |
| `WORKING`    | WORKING           | Focused, energetic, typing/working animation            |
| `PERMISSION` | ASKING PERMISSION | Looks toward user, raises wings, asks for attention     |
| `SUCCESS`    | SUCCESS           | Happy, celebratory animation                            |
| `ERROR`      | ERROR             | Confused/worried expression                             |
| `EXCITED`    | EXCITED           | Wakes up / hops when a session starts                   |
| `SLEEPING`   | SLEEPING          | Sleeping or resting (session ended or long idle)        |
| `CONNECTING` | LOADING           | Loading animation while joining Wi-Fi or Wi-Fi was lost |

Blink is not a state; it is an eye overlay used by every awake state.

What triggers each state is defined in Phase 6.

------------------------------------------------------------------------

# 3. Architecture

The initial architecture:

``` text
┌───────────────────────────────┐
│             Mac               │
│                               │
│  GitHub Copilot CLI           │
│          │                    │
│          ▼                    │
│  Copilot CLI hooks            │
│  (~/.copilot/hooks/duck.json) │
│          │                    │
│          ▼                    │
│  curl POST (fire-and-forget)  │
└──────────┬────────────────────┘
           │
     Home Wi-Fi (HTTP)
           │
           ▼
┌───────────────────────────────┐
│       Waveshare ESP32-S3      │
│                               │
│  HTTP server (duck.local)     │
│          │                    │
│          ▼                    │
│  Duck state machine           │
│          │                    │
│          ▼                    │
│  Animation engine             │
│          │                    │
│          ▼                    │
│      240×240 LCD              │
└──────────┬────────────────────┘
           │
           ▼
      Prism cube
           │
           ▼
   Floating duck image
```

## Design principle

Keep the Mac side (hooks) responsible for **what is happening**.

Keep the ESP32 responsible for **how the duck looks and moves**, and
for state timeouts (see Phase 4).

This allows the animation system to remain responsive even if network
messages arrive infrequently.

There is no Mac-side service. Copilot CLI hooks already fire on every
lifecycle event; each hook runs `curl` straight to the duck. Add a Mac
bridge only if a future need (e.g. merging several sessions) requires one.

------------------------------------------------------------------------

# 4. Phase 0 --- Design the Duck

## Goal

Define the duck's visual language before writing the animation system.

### Visual requirements

-   Pixel-art style
-   White duck
-   Yellow/orange beak
-   Minimal palette
-   Drawn on a fixed **60×60 logical pixel grid**, scaled by an integer
    factor (4× on the 240×240 LCD, 8× on the 480×480 AMOLED)
-   Pure black (`#000000`) background; black reads as transparent in
    the prism
-   Avoid grey and dim colours (grey laptop, grey error swirl, dark
    blue effects in the mock); they look faint or muddy in the prism.
    Use bright white, orange/yellow, and saturated cyan/blue only.
-   No unnecessary text
-   Strong silhouette
-   Large readable eyes
-   Expressions must remain recognizable at small size

### Prism check before drawing

Before redrawing anything, show the mock on the real prism (bring-up
step 5, Phase 7) and confirm which colours survive: navy background,
grey laptop, grey swirl, dim blue effects. Adjust the palette rules
above to what you actually see.

### Design states

`juno-design-mock.png` is the concept reference. It is not pixel-exact
(soft edges, uneven pixel sizes), so **redraw each tile on the 60×60
grid** in a pixel editor (Aseprite or Piskel) before use.

Sprites needed: one base pose per state (9, matching the mock), plus
eye overlays (open, closed/blink, happy `^ ^`, worried) and effect
sprites (thought bubble, sparkles, Zzz, motion lines, spinner dots).

### Animation philosophy

Hybrid: **base pose sprite per state + overlays + integer offsets.**

Poses like sleeping, working (laptop) and thinking (wing on chin)
change the whole silhouette, so they can't come from one shared body.
Each state gets its own base sprite; small overlays add life:

``` text
frame = base pose (per state)
      + eye overlay (blink, look direction)
      + effects (bubble, sparkles, Zzz, ...)
      + whole-pixel offset (bob, breathe, hop)
```

Procedural motion is limited to:

-   blinking (eye overlay swap)
-   pupil/look direction (overlay swap)
-   bobbing, breathing, hopping (integer pixel offsets)
-   small particles/effects

Skip rotation, head tilt and squash/stretch; they look jagged on
low-resolution pixel art. Use extra drawn frames instead.

------------------------------------------------------------------------

# 5. Phase 1 --- Development Environment

## Repository layout

``` text
holo-duck/
├── README.md
├── copilot-duck-build-plan.md
├── hooks/
│   └── duck.json         # Copilot CLI hooks → curl (copy to ~/.copilot/hooks/)
├── firmware/             # PlatformIO + Arduino
│   ├── platformio.ini
│   └── src/
│       ├── main.cpp      # Wi-Fi, mDNS, HTTP, LCD push, backlight
│       ├── duck.h/.cpp   # animation engine (no network code)
│       └── sprites.h     # generated by tools/png2c.py
├── assets/
│   └── sprites/          # Aseprite/PNG sources
└── tools/
    └── png2c.py          # PNG → RGB565 C array (Pillow)
```

### Engine

The engine lives in `firmware/src/duck.cpp` and draws into the
240×240 RGB565 sprite buffer:

``` cpp
void duck_set_state(DuckState s);
void duck_tick(uint32_t now_ms, uint16_t* fb);
```

Animations are developed **on the device**: edit, `pio run -t upload`
(~15--20 s), then switch states with
`curl -d thinking http://duck.local/state`. No Mac simulator; add one
only if flashing becomes the bottleneck.

No TypeScript/Node is needed.

### Message format

`POST http://duck.local/state` with a plain-text body naming the state:

``` text
working
```

Unknown states are ignored. No JSON, no timestamp; add fields only when
something needs them.

------------------------------------------------------------------------

# 6. Phase 2 --- ESP32 Firmware Skeleton

Before implementing Copilot integration, establish communication with
the board.

## Firmware responsibilities

The ESP32 should:

1.  Join home Wi-Fi (credentials in a gitignored
    `firmware/src/secrets.h`); show `CONNECTING` meanwhile.
2.  Advertise itself as `duck.local` via mDNS.
3.  Run an HTTP server accepting `POST /state`.
4.  Pass the state to the engine (`duck_set_state`).
5.  Render frames (`duck_tick`) and push them to the LCD.
6.  Return to `CONNECTING` if Wi-Fi drops.

### Firmware stack (decided)

-   PlatformIO + Arduino framework, **Arduino core 2.0.x**. Waveshare
    tests 2.0.12; PlatformIO has no 2.0.12 build, so pin
    `platform = espressif32@6.5.0` (core 2.0.14). Do not use core 3.x;
    TFT_eSPI has known problems on it.
-   **TFT_eSPI 2.5.0** (same as Waveshare's demos), configured with
    build flags instead of editing the library's `User_Setup.h`.
-   A 240×240 `TFT_eSprite` is the framebuffer; push it once per frame.
    This is how the community prism projects do it.
-   **No LVGL** (it is a widget toolkit; we only draw sprites).
-   Wi-Fi, `WebServer` and `ESPmDNS` come with the Arduino core; no
    extra libraries.
-   Sprites are compiled into flash (16 MB is plenty); the TF card is
    not used.

### Board settings and pins (from the Waveshare wiki, demo and schematic)

``` ini
; firmware/platformio.ini
[env:duck]
platform = espressif32@6.5.0
board = esp32-s3-devkitc-1
framework = arduino
board_build.flash_mode = qio
board_upload.flash_size = 16MB
board_build.arduino.memory_type = qio_opi      ; 8 MB OPI PSRAM
board_build.partitions = huge_app.csv
monitor_speed = 115200
lib_deps = bodmer/TFT_eSPI@2.5.0
build_flags =
  -DBOARD_HAS_PSRAM
  -DARDUINO_USB_CDC_ON_BOOT=0                  ; serial goes through the CH343
  -DUSER_SETUP_LOADED -DST7789_DRIVER
  -DTFT_WIDTH=240 -DTFT_HEIGHT=240
  -DTFT_MOSI=41 -DTFT_SCLK=40 -DTFT_CS=39 -DTFT_DC=38 -DTFT_RST=42
  -DTFT_INVERSION_ON -DTFT_RGB_ORDER=TFT_RGB
  -DSPI_FREQUENCY=40000000
```

| Signal              | GPIO |
|---------------------|------|
| LCD MOSI            | 41   |
| LCD SCLK            | 40   |
| LCD CS              | 39   |
| LCD DC              | 38   |
| LCD RST             | 42   |
| LCD backlight (PWM) | 20   |

### Board gotchas

-   **Prism mirroring is solved:** Waveshare's `*_Prism` demos differ
    from `*_NoPrism` only by `tft.setRotation(4)` (mirrored) instead of
    `setRotation(2)`. Use `setRotation(4)`; no mirror flags needed.
-   **Backlight is GPIO 20** (schematic net `BL_PWM` → NPN transistor).
    Waveshare's ESP-IDF `main.c` says `PIN_NUM_BL 4`; that is wrong for
    this board. Drive it with `ledcWrite` PWM for brightness.
-   Call `tft.invertDisplay(1)` and `sprite.setSwapBytes(true)` when
    pushing RGB565 arrays, or colours come out wrong.
-   Full-frame push at 40 MHz SPI takes ≈ 23 ms, so ~40 FPS is the
    ceiling. 30 FPS fits; if it gets tight, push only the rectangle
    around the duck.
-   IPS black is not truly black (backlight bleed shows as a faint
    square in the prism). Keep the backlight as low as looks good, and
    turn it off after a while in `SLEEPING`.
-   Mac flashing: the USB-C port is a CH343 serial bridge. If upload
    fails, install the WCH CH34x Mac driver (wiki FAQ) and/or hold
    Reset for >1 s and retry.

### Reference projects

-   Waveshare demo zip, `Arduino/examples/01_AstronautClock/
    AstronautClock_Prism` (official prism config)
-   [VolosR/esp32Prism](https://github.com/VolosR/esp32Prism)
    `holly/holly.ino`: ~40 lines; TFT_eSPI + full-screen sprite +
    `setRotation(4)`. Closest template for our firmware.
-   [nishad2m8/WS-1.3](https://github.com/nishad2m8/WS-1.3),
    [LINXX3 prism weather station](https://github.com/LINXX3/ESP32-S3-LCD-1.3---Prism-Version---Weather-Station)

------------------------------------------------------------------------

# 7. Phase 3 --- Display Rendering

## Initial target

Render at **30 FPS** (the SPI ceiling is ~40 FPS; see Phase 2). Animate
sprites at about **8--12 FPS** (normal for pixel art); offsets and
effects can update every frame.

The duck should feel smooth rather than like a slideshow.

### Rendering layers

``` text
background (#000)
    ↓
shadow
    ↓
base pose (per state)
    ↓
eye overlay
    ↓
effects
```

The background should remain as close to black as possible to maximize
the holographic effect.

------------------------------------------------------------------------

# 8. Phase 4 --- Animation Engine

Build a small animation/state system rather than hard-coding animations
directly into the network logic.

``` text
DuckState
  IDLE
  THINKING
  WORKING
  PERMISSION
  SUCCESS
  ERROR
  EXCITED
  SLEEPING
  CONNECTING
```

Each state is a table entry (base pose frames, frame rate, eye
behaviour, effects, bob pattern), not a class. One `duck_tick` reads
the current entry and draws.

Example:

``` text
WORKING

base pose:
  duck at laptop, 2–3 frames of wing "typing"

offset:
  subtle 1–2 px bob

eyes:
  occasionally look toward the screen

effects:
  occasional tiny motion lines
```

### Timeouts (owned by the ESP32)

Hooks only report changes; the device must not get stuck if an event is
missed (e.g. Esc/Ctrl+C interrupts, crashed session):

| From                              | To         | After        |
|-----------------------------------|------------|--------------|
| `EXCITED`                         | `IDLE`     | ~2 s         |
| `SUCCESS`                         | `IDLE`     | ~3 s         |
| `ERROR`                           | `IDLE`     | ~5 s         |
| `THINKING`/`WORKING`/`PERMISSION` | `IDLE`     | ~5 min with no message |
| `IDLE`                            | `SLEEPING` | ~10 min      |

Any incoming message wakes the duck. All durations are constants to
tune on real sessions.

------------------------------------------------------------------------

# 9. Phase 5 --- Mac → ESP32 Communication

``` text
Copilot CLI hook
        │
        │ curl -d <state> http://duck.local/state  (fire-and-forget)
        ▼
      ESP32
```

-   One-way, stateless HTTP. No persistent connection, no Mac service.
-   Hooks background `curl` with a short timeout, so a powered-off duck
    never slows Copilot down.
-   Several Copilot sessions at once: **last message wins**. Add
    merging by priority only if it turns out to be confusing.
-   Only the state name is sent; no prompts, file names or other
    session content leave the Mac.
-   The ESP32 does not need to understand Copilot itself.

------------------------------------------------------------------------

# 10. Phase 6 --- Copilot CLI Integration

Copilot CLI **hooks** cover this. Hooks are JSON files in
`~/.copilot/hooks/` (user-level, all repos) that run a command on each
lifecycle event. Reference:
<https://docs.github.com/en/copilot/reference/hooks-configuration>

## Hook → DuckState mapping

| Hook event                                                       | DuckState    |
|------------------------------------------------------------------|--------------|
| `sessionStart`                                                   | `EXCITED`    |
| `userPromptSubmitted`                                            | `THINKING`   |
| `preToolUse`                                                     | `WORKING`    |
| `notification` (`permission_prompt` or `elicitation_dialog`)     | `PERMISSION` |
| `agentStop`                                                      | `SUCCESS`    |
| `errorOccurred`                                                  | `ERROR`      |
| `sessionEnd`                                                     | `SLEEPING`   |

Notes:

-   Use `notification`, **not** `permissionRequest`, for `PERMISSION`.
    `permissionRequest` fires even when the tool is auto-approved.
-   `agentStop` fires at the end of **every** turn, so `SUCCESS` means
    "done, your turn", not "task succeeded". Keep the celebration short
    so it doesn't get annoying.
-   Ignore `postToolUse`/`postToolUseFailure`. Mapping them would make
    the duck flicker during fast tool chains, and failed tool calls
    (e.g. a grep with no matches) are routine, not errors. The duck
    stays `WORKING` until the turn ends.
-   Esc/Ctrl+C may not fire `agentStop`; the stale timeout in Phase 4
    covers it.

## `hooks/duck.json`

``` json
{
  "version": 1,
  "hooks": {
    "sessionStart":        [{ "type": "command", "bash": "curl -s -m 1 -d excited    http://duck.local/state >/dev/null 2>&1 &" }],
    "userPromptSubmitted": [{ "type": "command", "bash": "curl -s -m 1 -d thinking   http://duck.local/state >/dev/null 2>&1 &" }],
    "preToolUse":          [{ "type": "command", "bash": "curl -s -m 1 -d working    http://duck.local/state >/dev/null 2>&1 &" }],
    "notification":        [{ "type": "command", "matcher": "permission_prompt|elicitation_dialog",
                              "bash": "curl -s -m 1 -d permission http://duck.local/state >/dev/null 2>&1 &" }],
    "agentStop":           [{ "type": "command", "bash": "curl -s -m 1 -d success    http://duck.local/state >/dev/null 2>&1 &" }],
    "errorOccurred":       [{ "type": "command", "bash": "curl -s -m 1 -d error      http://duck.local/state >/dev/null 2>&1 &" }],
    "sessionEnd":          [{ "type": "command", "bash": "curl -s -m 1 -d sleeping   http://duck.local/state >/dev/null 2>&1 &" }]
  }
}
```

### Testing hooks without the duck

Independent of the firmware, so it can run alongside bring-up.
Run `nc -lk 8080` and temporarily point the hooks at
`http://localhost:8080/state`. Use Copilot normally and check that the
state sequence printed by `nc` matches the table above.

The duck only ever sees state names, so a change in Copilot CLI means
editing `duck.json`, not the firmware.

------------------------------------------------------------------------

# 11. Phase 7 --- Hologram Prototype

## Bring-up (in order, stop at the first failure)

1.  **Factory demo.** Power on over USB-C; the board ships with
    Waveshare's factory demo (RGB colour test, then a status screen).
    This confirms the LCD and backlight. In that demo, standing the
    board upright (USB end down) turns the backlight off; that is
    intended.
2.  **Serial port.** `brew install platformio`, plug in, run
    `ls /dev/cu.*`. A new `usbmodem*` or `wchusbserial*` port should
    appear. If none appears, install the WCH CH34x Mac driver (wiki FAQ).
3.  **Hello-world + prism orientation.** Flash a sketch that draws a
    black screen with a white **"F"** in the top-left corner and logs
    to serial (`pio device monitor`). Through the prism the F must read
    correctly and sit top-left. Expected to work with `setRotation(4)`;
    if not, try 5--7 and record the answer here.
4.  **Network.** Wi-Fi + mDNS + `POST /state` logging the body to
    serial. `curl -d working http://duck.local/state` from the Mac.
5.  **Palette check.** `tools/png2c.py` the mock (and a few tiles at
    4×) to RGB565 and display them. Note which colours fade, and tune
    backlight PWM (GPIO 20). Feed results back into Phase 0.

Then build the engine on the device.

If the factory demo is ever needed again, its prebuilt firmware is in
the Waveshare demo zip under `ESP32-S3-LCD-1.3-Demo/Firmware`.

### Optical target

The duck should appear to float inside/above the prism rather than
simply looking like a normal LCD image.

Important considerations:

-   Pure black background
-   Bright white duck
-   High-contrast orange beak
-   Avoid gray backgrounds
-   Avoid unnecessary UI elements
-   Keep duck centered
-   Tune backlight PWM (GPIO 20): lowest level that still looks bright,
    to hide IPS backlight bleed

------------------------------------------------------------------------

# 12. Phase 8 --- Copilot End-to-End Demo

First complete demo:

``` text
Start Copilot
      ↓
Duck wakes up (EXCITED)
      ↓
Copilot thinks
      ↓
Duck looks thoughtful
      ↓
Copilot starts working
      ↓
Duck becomes energetic
      ↓
Copilot asks permission
      ↓
Duck gets user's attention
      ↓
Copilot succeeds
      ↓
Duck celebrates
      ↓
Returns to idle
```

This is the first major definition of done.

------------------------------------------------------------------------

# 13. Phase 9 --- Physical Monitor Mount

The V1 prism kit should initially be treated as a
development/proof-of-concept device.

After the software and animation are proven, design the final
monitor-top version.

## Desired characteristics

-   No large electronics enclosure
-   Minimal visible hardware
-   Mounts behind/on top of monitor
-   USB-C cable routed behind monitor
-   Duck appears to float above the monitor
-   Approximately 1--4" overall visual footprint
-   Clean industrial design

Potential final architecture:

``` text
             viewer
               👁
                \
                 \  floating duck
                  \
                   \  ~45°
                    ╲
                     ╲
                 ┌────────┐
                 │ glass  │
                 └────────┘
                       \
                        \
                 ┌─────────────┐
                 │ AMOLED      │
                 │ ESP32-S3    │
                 └─────────────┘
                  behind monitor
```

------------------------------------------------------------------------

# 14. Future Display Upgrade

If the V1 proves successful, evaluate replacing the 1.3" LCD/prism with:

**Waveshare ESP32-S3-Touch-AMOLED-2.16**

Benefits:

-   480×480
-   AMOLED
-   Better black levels
-   Higher pixel density
-   Better contrast
-   Larger canvas
-   8 MB PSRAM
-   Same ESP32-S3 family

This should produce a significantly cleaner holographic effect.

The V1 software should therefore avoid being tightly coupled to 240×240.

The 60×60 logical grid (Phase 0) already handles this: switch the
integer scale from 4× to 8×.

------------------------------------------------------------------------

# 15. Future Interaction

The board's QMI8658 IMU can eventually be used for
personality/interactivity. Waveshare's Snake and 2048 demos already read
tilt from it using SensorLib (v0.2.6), so that is the starting point.

Potential ideas:

### Physical movement

If the monitor is bumped:

``` text
Duck gets startled
        ↓
looks around
        ↓
settles back down
```

### Tilt

Tilt the device:

``` text
duck leans with the device
```

### Tap

If accessible:

``` text
tap → duck reacts
```

These are optional and should not delay the core Copilot functionality.

------------------------------------------------------------------------

# 16. Future Audio

Audio is optional.

Potential future behaviors:

-   tiny quack on success
-   sleepy sound when offline
-   alert sound for permission requests
-   subtle typing sounds

Keep audio out of V1. **The kit has no speaker or buzzer**; sound would
need an external I2S amp + speaker wired to the 16-pin GPIO header.

The duck should work perfectly without sound.

------------------------------------------------------------------------

# 17. Development Milestones

Milestones 1 and 2 are independent; do them in parallel.

## Milestone 1 --- Hardware bring-up (Phase 7)

-   [x] Receive Waveshare board
-   [ ] Factory demo runs
-   [ ] Serial port shows up on the Mac
-   [ ] `firmware/platformio.ini` (Phase 2); hello-world flashes
-   [ ] Prism "F" test passes; record the working rotation
-   [ ] Wi-Fi + mDNS + `POST /state` reachable via `curl`
-   [ ] Mock displayed through the prism; palette + backlight notes
    recorded in Phase 0

## Milestone 2 --- Copilot hooks

-   [ ] Write `hooks/duck.json`
-   [ ] Point it at `nc -lk 8080` and verify the state sequence on real
    sessions (including Esc/Ctrl+C and a permission prompt)

## Milestone 3 --- Duck art

-   [ ] Lock the colour palette from the Milestone 1 prism check
-   [ ] Redraw the 9 mock tiles on the 60×60 grid
-   [ ] Draw eye overlays and effect sprites
-   [ ] Convert with `tools/png2c.py` into `firmware/src/sprites.h`

## Milestone 4 --- Engine on the device

-   [ ] `duck.cpp` (`duck_set_state`, `duck_tick`), driven by
    `POST /state`
-   [ ] All 9 states animated, plus blink, at 30 FPS
-   [ ] Timeouts from Phase 4
-   [ ] Backlight dims/off in `SLEEPING`

## Milestone 5 --- First complete prototype

-   [ ] Copilot → hooks → Wi-Fi → ESP32 → duck
-   [ ] Verify stability
-   [ ] Tune animation
-   [ ] Tune brightness
-   [ ] Tune prism positioning

## Milestone 6 --- Final physical design

-   [ ] Measure monitor
-   [ ] Start from Waveshare's board/case outline (wiki → Resources →
    Structure Diagram)
-   [ ] Design hidden mount
-   [ ] Evaluate optical geometry
-   [ ] Evaluate 2.16" AMOLED
-   [ ] Build final prototype
-   [ ] Clean up cabling

------------------------------------------------------------------------

# 18. Definition of Done

The project succeeds when:

> I can start a Copilot CLI session on my Mac and have a tiny pixel-art
> duck visibly and smoothly react to what Copilot is doing without me
> manually controlling it.

The ideal final experience is:

**Copilot is working → the duck is working.**

**Copilot needs me → the duck gets my attention.**

**Copilot succeeds → the duck celebrates.**

**Nothing is happening → the duck is quietly alive.**

------------------------------------------------------------------------

# 19. Immediate Next Steps

The hardware has arrived. In order:

1.  Plug in the board and confirm the factory demo runs.
2.  `brew install platformio`; write `firmware/platformio.ini`
    (Phase 2) and flash the "F" hello-world. Lock the prism rotation.
3.  Add Wi-Fi + mDNS + `POST /state`; `curl` it from the Mac.
4.  Display the mock through the prism; record palette and backlight
    findings.
5.  In parallel with 1--4: write `hooks/duck.json` and verify it
    against `nc` on real sessions.
6.  Redraw the duck with the confirmed palette, then build the engine
    on the device.

The key objective for this week:

**A white "F" reading correctly through the prism, reachable at
`duck.local`, and hooks verified.**
