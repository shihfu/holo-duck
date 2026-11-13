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
| `EXCITED`    | EXCITED           | Wakes up / hops when a message wakes it from `SLEEPING` |
| `WELCOME`    | --                | Turns to face you and waves when you launch Copilot     |
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
-   The mock's palette works as-is (verified through the prism at
    backlight 100/255): white, greys down to `#404040`, yellow, orange,
    red, green, cyan, blue, dark blue, and navy all read clearly. Keep
    the duck itself the brightest thing on screen.
-   No unnecessary text
-   Strong silhouette
-   Large readable eyes
-   Expressions must remain recognizable at small size

### Prism check before drawing

**Done** (bring-up step 5, Phase 7). The full mock, all 9 tiles at
240×240, and 12 labelled swatches were shown through the prism. No
colour or element faded, including the grey laptop, grey bubble, grey
swirl, and dark spinner dots. The black square edge is faint at
backlight 100.

### Design states

`juno-design-mock.png` is the concept reference. It is an AI-style
render: soft edges, uneven pixel blocks (6.4--7.5 px) and about 6,700
colours. A plain downscale blurs it.

**Base sprites (done):** `tools/mock2sprites.py` cuts each mock tile
into `assets/sprites/<state>.png`. The mock draws the duck at different
sizes (loading is ~17% smaller than idle, permission ~9% larger), so the
script scales every tile to the same duck: 33 px from head to feet,
feet centred at x = 30, standing on y = 58. Keep these numbers if you
redraw a tile, so the duck does not jump between states.

To keep the pixels crisp, the script sets each output pixel from the
matching block of mock pixels:

1.  It ignores the navy panel background.
2.  If the duck covers less than half of the block, the pixel is black.
3.  Otherwise, it takes the mean colour of the duck pixels and snaps it
    to a fixed 16-colour palette taken from the mock.

A majority vote per block was tried first; it lost the eyes and thin
lines. A hand redraw in a pixel editor (Aseprite or Piskel) is now
optional: the extracted sprites passed review on the device.

### Animation philosophy

**Build-time frames (done).** Poses like sleeping, working (laptop)
and thinking (wing on chin) change the whole silhouette, so each state
has its own base sprite. `tools/animate.py` moves parts of each base
sprite by whole pixels to build finished frames:

``` text
assets/sprites/<state>.png ──animate.py──▶ firmware/src/sprites.h
                                      └──▶ assets/preview/<state>.gif (4×)
```

-   **Body:** the largest connected shape of non-black pixels. Duck
    motions (sway, tilt, wings, hops) move only body pixels.
-   **Effects:** all other pixels (bubble dots, marks, lines, swirl).
    Effect motions move only effect pixels. A rectangle that overlaps
    both never drags the other along, so the thought bubble keeps its
    outline when the head tilts.
-   Small per-state rectangles in the script mark wings, tail, head
    and feet. Colour finds the eyes (dark pixels inside white) and the
    beak and feet (orange).
-   **Squash and stretch:** hops crouch, stretch on take-off and land
    squashed. The ground shadow narrows while the duck is in the air.
-   Each state gets a frame sequence plus a closed-eye copy of every
    frame. Duplicate frames are stored once.
-   The engine plays the sequence from state entry. Every 2--6 s at
    random it shows the closed-eye copy for 120 ms (blink).
-   Result: 126 unique 60×60 frames, 885 KB. The firmware uses 54% of
    the app partition.

Build-time frames beat runtime part composition: frames are plain
copies (fastest), and the GIFs show the motion without flashing.

| State | ms/frame | Body motion | Eyes | Effects |
|---|---|---|---|---|
| idle | 125 | Breathing, tail wiggle, head tilt, waddle | Blink, glances left and right | -- |
| thinking | 150 | Head tilts while the dots appear, then the wing taps the chin | Blink, look up at the bubble | Dots appear one by one |
| working | 100 | Wing types, head bobs | Blink | Motion lines flicker |
| permission | 100 | Small hops with squash, wings flap | Blink | Orange marks pulse |
| success | 100 | Jump with squash and stretch, wings flap | Happy `^ ^`, no blink | Sparkles twinkle |
| error | 100 | Short shake, then the head droops | Wince, then slow blinks | Swirl wobbles |
| sleeping | 250 | Slow breathing | Closed | Two Z's rise, drift and fade |
| excited | 80 | Big hop with squash and stretch, wings flap | Blink | Motion lines flicker |
| welcome | 100 | Hops to face front, then waves the raised wing (plays once, 5 s) | Blink | -- |
| connecting | 125 | Walks in place (lean, lift a foot, bob) | Blink, look up at the spinner | Spinner dots rotate |

Skip rotation and smooth tilt; they look jagged on low-resolution pixel
art.

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
│   ├── platformio.ini    # env duck (default) + env native (host tests)
│   ├── src/
│   │   ├── main.cpp      # Wi-Fi, mDNS, HTTP, LCD push, backlight
│   │   ├── duck.h/.cpp   # animation engine (no network code)
│   │   └── sprites.h     # generated by tools/animate.py
│   └── test/test_duck/   # state-rule tests (Unity, runs on the Mac)
├── assets/
│   ├── sprites/          # 60×60 base sprite per state
│   └── preview/          # 4× GIF per state (generated)
└── tools/
    ├── mock2sprites.py   # crisp base sprites cut from the mock
    ├── animate.py        # base sprites → frames, sprites.h, GIFs
    └── png2c.py          # PNG → RGB565 C array (Pillow)
```

Python tools run from a venv: `python3 -m venv tools/.venv &&
tools/.venv/bin/pip install pillow`.

### Engine

The engine lives in `firmware/src/duck.cpp`. Each `DuckState` has one
row in the `RULES` table (timeout, next state) and one sequence in
`SEQS` (frame time, frame indices, blink copies), in the same order.
`duck_tick` picks the frame from the time since the state was entered
(`t0`), shows the blink copy when a blink is due, and draws the 60×60
frame at 4× into the 240×240 `TFT_eSprite` buffer. A repeat message for
the current state resets its timeout (`since`) but does not restart the
animation.

``` cpp
void duck_set_state(DuckState s, uint32_t now_ms);
DuckState duck_state();
uint8_t duck_tick(uint32_t now_ms, uint16_t* fb);  // returns backlight level
```

Animations are developed with the GIF previews first, then checked
**on the device**: `pio run -t upload` (~35 s), then switch states with
`curl -4 -d state=thinking http://duck.local/state`. No Mac simulator; add one
only if flashing becomes the bottleneck.

The state rules (wake, timeouts, backlight) have host tests. On this
Mac, run them with the Command Line Tools toolchain (see Phase 2
gotchas):

``` sh
cd firmware && DEVELOPER_DIR=/Library/Developer/CommandLineTools pio test -e native
```

Rebuild the frames after you change a PNG in `assets/sprites/` or a
motion in `tools/animate.py` (~5 s). Check the GIFs in
`assets/preview/` before you flash:

``` sh
tools/.venv/bin/python tools/animate.py
```

No TypeScript/Node is needed.

### Message format

`POST http://duck.local/state` with one form field naming the state:

``` text
state=working
```

Reply: `204` for a known state, `400` for anything else (ignored). No
JSON, no timestamp; add fields only when something needs them.

Send it with `curl -4 -d state=working http://duck.local/state`. Both
parts matter (verified on the device):

-   `-4`: macOS also asks mDNS for an IPv6 address, which the ESP32
    never answers, so name lookup stalls 5 s. With `-4` it takes ~10 ms.
-   `state=`: `curl -d` sends form encoding, and the Arduino WebServer
    drops a bare form body without `=`.

`GET http://duck.local/status` reports uptime, the reason for the last
reset, Wi-Fi drops since boot, and the current state. Use it to check
stability when the board is not on the Mac:

``` text
$ curl -4 http://duck.local/status
uptime_s 86400
reset poweron
wifi_drops 0
state idle
```

A small `uptime_s` with `reset poweron` means the power was cut (for
example, the monitor turned off its USB ports). `panic`, `task_wdt`,
`int_wdt` or `brownout` means a crash or a weak power supply.

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
  -DTFT_INVERSION_ON -DTFT_RGB_ORDER=TFT_BGR
  -DSPI_FREQUENCY=40000000
  -DLOAD_GLCD                                  ; built-in font for debug text
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

-   **Prism mirroring (verified on the device):** stock TFT_eSPI 2.5.0
    has no mirrored ST7789 rotations (`rotation = m % 4`, so
    `setRotation(4)` is the same as `0`). Use `setRotation(2)`, then
    rewrite `MADCTL` as `TFT_MAD_MY | TFT_MAD_COLOR_ORDER` (clear `MX`).
    `MX` is the full 240 px axis, so the library's CGRAM offsets stay
    valid. See `setPrismRotation()` in `firmware/src/main.cpp`.
-   **Backlight is GPIO 20** (schematic net `BL_PWM` → NPN transistor).
    Waveshare's ESP-IDF `main.c` says `PIN_NUM_BL 4`; that is wrong for
    this board. Drive it with `ledcWrite` PWM for brightness.
-   **Colour order is BGR (verified on the device).** Waveshare's
    config says `TFT_RGB`, but with that setting red and blue swap
    (yellow shows light blue). Use `-DTFT_RGB_ORDER=TFT_BGR`.
-   Call `tft.invertDisplay(1)` and `sprite.setSwapBytes(true)` when
    pushing RGB565 arrays, or colours come out wrong.
-   Full-frame push at 40 MHz SPI takes ≈ 23 ms, so ~40 FPS is the
    ceiling. 30 FPS fits; if it gets tight, push only the rectangle
    around the duck.
-   IPS black is not truly black (backlight bleed shows as a faint
    square in the prism). Use backlight 180/255. The palette check
    chose 100 over 60, 160 and 255; 180 is brighter. Turn the
    backlight off after a while in `SLEEPING`.
-   Mac flashing: the USB-C port is a CH343 serial bridge; macOS's
    built-in driver handles it. If upload fails, hold Reset for >1 s
    and retry.
-   **Wi-Fi must be the Mac's network.** `duck.local` (mDNS) only works
    on one subnet. Here that is the eero network (192.168.4.0/22), not
    the TELUS modem's `TELUS5949-2.4G` (192.168.1.x). The ESP32 joins the
    eero's 2.4 GHz band under the same network name.
-   **Turn off Wi-Fi modem sleep** (`WiFi.setSleep(false)`). The
    Arduino core enables modem sleep by default, and it delayed
    requests by up to 0.93 s. The hooks give curl only 1 s. With
    modem sleep off, the request median is 32 ms and the maximum is
    65 ms.
-   **Opening the serial port resets the board**, even with DTR and RTS
    held low. Start a serial logger only when a reboot is acceptable.
-   **Host tests need the Command Line Tools linker.** On this Mac,
    `xcode-select` points at an older Xcode.app (ld-1266) that cannot
    read the newer SDK 27.2, so even a hello-world fails to link
    ("unknown architecture arm64e.x1"). Prefix host builds with
    `DEVELOPER_DIR=/Library/Developer/CommandLineTools`, or fix it once
    with `sudo xcode-select -s /Library/Developer/CommandLineTools` or an
    Xcode update. The ESP32 build is not affected.

### Reference projects

-   Waveshare demo zip, `Arduino/examples/01_AstronautClock/
    AstronautClock_Prism` (official prism config)
-   [VolosR/esp32Prism](https://github.com/VolosR/esp32Prism)
    `holly/holly.ino`: ~40 lines; TFT_eSPI + full-screen sprite +
    `setRotation(4)` (not mirrored with stock TFT_eSPI; see gotchas).
    Closest template for our firmware.
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

Each state is a table entry (a `RULES` row and a `SEQS` sequence), not
a class. The motion is built into the frames at build time (Phase 0).
One `duck_tick` reads the current entry and draws.

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
| `EXCITED`                         | latest state received | ~2 s |
| `WELCOME`                         | `IDLE`     | 5 s          |
| `SUCCESS`                         | `IDLE`     | ~5 s         |
| `ERROR`                           | `IDLE`     | ~5 s         |
| `THINKING`/`WORKING`/`PERMISSION` | `IDLE`     | ~30 min with no message |
| `IDLE`                            | `SLEEPING` | ~10 min      |

A message that arrives while `SLEEPING` plays `EXCITED` first, then
shows the latest state received (hooks never send `excited`;
`state=excited` still works for previewing the art). All durations are
constants to tune on real sessions.

`welcome` is accepted only while `SLEEPING` (screen on or off) or
`IDLE`; other states ignore it. From `SLEEPING` it plays without
`EXCITED`. Any other message replaces `WELCOME` at once.

------------------------------------------------------------------------

# 9. Phase 5 --- Mac → ESP32 Communication

``` text
Copilot CLI hook
        │
        │ curl -4 -d state=<state> http://duck.local/state  (fire-and-forget)
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
| `userPromptSubmitted`                                            | `THINKING`   |
| `preToolUse`, `postToolUse`                                      | `WORKING`    |
| `notification` (`permission_prompt` or `elicitation_dialog`)     | `PERMISSION` |
| `postToolUse` with "User cancelled the request."                 | `IDLE`       |
| Esc on a permission prompt (`duck-watch.sh`)                     | `IDLE`       |
| Approving a permission prompt (`duck-watch.sh`)                  | `WORKING`    |
| `agentStop`                                                      | `SUCCESS`    |
| `errorOccurred`                                                  | `ERROR`      |
| `sessionEnd`                                                     | `SLEEPING`   |

Verified on real sessions (CLI 1.0.109): every row above except
`errorOccurred` and `elicitation_dialog`, which are hard to trigger on
purpose. `sessionEnd` arrives even though Copilot is exiting.

Notes:

-   `sessionStart` is not used. It fires with the first prompt, not at
    launch, about 1 s before `userPromptSubmitted`, so `EXCITED` would
    be replaced at once. The duck plays `EXCITED` itself on wake
    (Phase 4). Verified again on CLI 1.0.111: launching `copilot`
    fires no hook.
-   `WELCOME` comes from a shell wrapper instead of a hook. Add it to
    `~/.zshrc`, then open a new terminal:

    ``` sh
    copilot() { ( curl -4 -s -m 1 -d state=welcome http://duck.local/state >/dev/null 2>&1 & ); command copilot "$@"; }
    ```
-   Use `notification`, **not** `permissionRequest`, for `PERMISSION`.
    `permissionRequest` fires even when the tool is auto-approved.
-   `agentStop` fires at the end of **every** turn, so `SUCCESS` means
    "done, your turn", not "task succeeded". Keep the celebration short
    so it doesn't get annoying.
-   Map `postToolUse` to `WORKING`. No hook fires when you approve a
    permission prompt or answer a question, so without it the duck
    stays `PERMISSION` until the next tool call or the end of the
    turn. `postToolUse` fires when the tool finishes. For a permission
    prompt, `duck-watch.sh` sends `WORKING` as soon as you approve
    (see below).
-   Ignore `postToolUseFailure`. Failed tool calls (e.g. a grep with
    no matches) are routine, not errors. The duck stays `WORKING`
    until the turn ends.
-   Cancelling a prompt sends `IDLE`. Verified on CLI 1.0.111:
    -   Esc on a question (`ask_user`) fires `postToolUse` with
        `"textResultForLlm":"User cancelled the request."`. The hook
        checks stdin for that text and sends `idle` instead of
        `working`.
    -   Esc on a permission prompt fires **no** hook. `duck-watch.sh`
        handles it (next note).
-   No hook fires when you answer a permission prompt. Copilot only
    writes `permission.completed` to
    `~/.copilot/session-state/<sessionId>/events.jsonl`. The
    `permission_prompt` notification starts `hooks/duck-watch.sh` in
    the background. The script checks that file once per second until
    the prompt resolves:
    -   `"kind":"cancelled"` (Esc): sends `idle`.
    -   `"kind":"approved"` or `"approved-for-location"`: sends
        `working`. If a `postToolUse` hook already appears after the
        approval, the tool has finished and the hook sent `working`,
        so the script sends nothing. This stops a late `working` from
        replacing `success`.
    -   Any other result: sends nothing.

    The script stops when Copilot exits (its `$PPID` is the `copilot`
    process) or after 30 min. Each check reads only the bytes added
    since the prompt appeared (about 15 ms), so a large log does not
    slow it down. Reading by line instead took 1.6 s per check on a
    36 MB log. Verified on CLI 1.0.111.
-   Esc/Ctrl+C while working may not fire `agentStop`; the stale
    timeout in Phase 4 covers it.

## `hooks/duck.json`

``` json
{
  "version": 1,
  "hooks": {
    "userPromptSubmitted": [{ "type": "command", "bash": "curl -4 -s -m 1 -d state=thinking   http://duck.local/state >/dev/null 2>&1 &" }],
    "preToolUse":          [{ "type": "command", "bash": "curl -4 -s -m 1 -d state=working    http://duck.local/state >/dev/null 2>&1 &" }],
    "postToolUse":         [{ "type": "command", "bash": "s=working; grep -q ': *\"User cancelled the request\\.\"' && s=idle; curl -4 -s -m 1 -d state=$s http://duck.local/state >/dev/null 2>&1 &" }],
    "notification":        [{ "type": "command", "matcher": "permission_prompt|elicitation_dialog",
                              "bash": "curl -4 -s -m 1 -d state=permission http://duck.local/state >/dev/null 2>&1 &" },
                            { "type": "command", "matcher": "permission_prompt", "bash": "sh ~/.copilot/hooks/duck-watch.sh" }],
    "agentStop":           [{ "type": "command", "bash": "curl -4 -s -m 1 -d state=success    http://duck.local/state >/dev/null 2>&1 &" }],
    "errorOccurred":       [{ "type": "command", "bash": "curl -4 -s -m 1 -d state=error      http://duck.local/state >/dev/null 2>&1 &" }],
    "sessionEnd":          [{ "type": "command", "bash": "curl -4 -s -m 1 -d state=sleeping   http://duck.local/state >/dev/null 2>&1 &" }]
  }
}
```

Install: `cp hooks/duck.json hooks/duck-watch.sh ~/.copilot/hooks/`
(copies, not symlinks). Hooks load when a session starts, so test in a new session.

### Testing hooks

Run `pio device monitor` in `firmware/` and use Copilot in a new
terminal. The board prints `duck: state <name>` for each message; check
the sequence against the table above. Each hook returns in ~20 ms, so
it never slows Copilot down.

Results from the Phase 8 demo (Milestone 5):

-   A session already running when `duck.json` is installed sends
    nothing. Hooks load when a session starts.
-   `permission` shows only while an approval prompt waits. If you
    approve within about 1 s, the duck can skip `permission`.
-   After you approve, `duck-watch.sh` switches the duck to `working`
    within about 1 s, even while a long command runs.
-   Killing Copilot (SIGTERM, or SIGHUP when you close the terminal)
    still fires `sessionEnd`, so the duck shows `sleeping`.

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
    `ls /dev/cu.*`. **Done:** the CH343 (`1A86:55D3`) shows as
    `/dev/cu.usbmodem*` with the built-in macOS driver. macOS asks
    "Allow accessory to connect?" on first plug-in; accept it, or the
    board only gets power.
3.  **Hello-world + prism orientation.** Flash a sketch that draws a
    black screen with a white **"F"** in the top-left corner and logs
    to serial (`pio device monitor`). Through the prism the F must read
    correctly and sit top-left. **Done:** mirrored rotation 2
    (`setRotation(2)` with `MX` cleared; see Phase 2 gotchas).
4.  **Network.** Wi-Fi + mDNS + `POST /state` logging the body to
    serial. `curl -4 -d state=working http://duck.local/state` from the
    Mac. **Done:** all states return `204` in 0.07--0.45 s.
5.  **Palette check.** `tools/png2c.py` the mock (and a few tiles at
    4×) to RGB565 and display them. Note which colours fade, and tune
    backlight PWM (GPIO 20). Feed results back into Phase 0.
    **Done:** the mock palette works as-is; colour order is BGR;
    backlight 100/255.

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
First prompt after the duck fell asleep
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
-   [x] Factory demo runs
-   [x] Serial port shows up on the Mac
-   [x] `firmware/platformio.ini` (Phase 2); hello-world flashes
-   [x] Prism "F" test passes: mirrored rotation 2
-   [x] Wi-Fi + mDNS + `POST /state` reachable via `curl`
-   [x] Mock displayed through the prism; palette + backlight notes
    recorded in Phase 0

## Milestone 2 --- Copilot hooks

-   [x] Write `hooks/duck.json`; install to `~/.copilot/hooks/`
-   [x] Verify the state sequence on real sessions, including a
    permission prompt. Esc/Ctrl+C not tested; the stale timeout
    (Phase 4) covers it.

## Milestone 3 --- Duck art

-   [x] Lock the colour palette from the Milestone 1 prism check
    (the mock palette as-is)
-   [x] Crisp base sprites cut from the mock at one duck size
    (`tools/mock2sprites.py`)
-   [x] Expressive motion for the 9 states: blink, waddle, tail
    wiggle, squash and stretch, shadows (`tools/animate.py`)
-   [x] Generate `firmware/src/sprites.h` and `assets/preview/*.gif`
    with `tools/animate.py`
-   [ ] Optional: redraw tiles by hand in a pixel editor

## Milestone 4 --- Engine on the device

-   [x] `duck.cpp` (`duck_set_state`, `duck_tick`), driven by
    `POST /state`; `CONNECTING` while Wi-Fi is down
-   [x] All 9 states animated, plus a random blink, at 30 FPS
-   [x] Timeouts from Phase 4, including `EXCITED` on wake (host tests)
-   [x] Backlight off after 20 min in `SLEEPING`

## Milestone 5 --- First complete prototype

-   [x] Copilot → hooks → Wi-Fi → ESP32 → duck (Phase 8 demo passed)
-   [ ] Verify stability: after a day of real use on the monitor's USB
    port, check `curl -4 http://duck.local/status` for resets and Wi-Fi
    drops
-   [x] Tune animation
-   [x] Tune brightness (backlight 180)
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

1.  ~~Plug in the board and confirm the factory demo runs.~~ Done.
2.  ~~`brew install platformio`; write `firmware/platformio.ini`
    (Phase 2) and flash the "F" hello-world. Lock the prism rotation.~~
    Done: mirrored rotation 2.
3.  ~~Add Wi-Fi + mDNS + `POST /state`; `curl` it from the Mac.~~ Done.
4.  ~~Display the mock through the prism; record palette and backlight
    findings.~~ Done: palette as-is, BGR, backlight 100.
5.  ~~In parallel with 1--4: write `hooks/duck.json` and verify it
    on real sessions.~~ Done.
6.  ~~Redraw the duck with the confirmed palette, then build the engine
    on the device.~~ Done: crisp sprites from the mock, motion from
    `tools/animate.py`, and an engine with sequences and blink.
7.  Run real Copilot sessions end to end (Milestone 5). Check
    stability, then tune brightness and the prism position.

The next objective:

**A full day of real Copilot sessions with no stuck states or resets.**
