# Copilot Duck Hologram --- Build Plan

## 1. Project Goal

Build a small, expressive **pixel-art duck hologram** that sits on top
of a computer monitor and reflects the state of a **GitHub Copilot CLI
session** running on the user's Mac.

The first prototype will use the **Waveshare ESP32-S3-LCD-1.3-C kit (SKU
30559)**, which includes:

-   ESP32-S3R8
-   1.3" 240×240 IPS LCD
-   Prism cube for the holographic effect
-   Wi-Fi
-   Bluetooth
-   8 MB PSRAM
-   16 MB flash
-   6-axis IMU
-   USB-C
-   Battery support

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

  -----------------------------------------------------------------------
  State                               Duck behavior
  ----------------------------------- -----------------------------------
  `IDLE`                              Relaxed, blinking, subtle
                                      breathing/bobbing

  `THINKING`                          Looks around, thoughtful
                                      expression, subtle thought
                                      animation

  `WORKING`                           Focused, energetic, typing/working
                                      animation

  `PERMISSION`                        Looks toward user, raises wing,
                                      asks for attention

  `SUCCESS`                           Excited, happy, celebratory
                                      animation

  `ERROR`                             Confused/worried expression

  `OFFLINE`                           Sleeping or resting

  `CONNECTING`                        Loading/searching animation
  -----------------------------------------------------------------------

The exact state vocabulary can evolve once we understand what Copilot
CLI exposes.

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
│  Copilot event/state adapter  │
│          │                    │
│          ▼                    │
│  TypeScript bridge service     │
└──────────┬────────────────────┘
           │
         Wi-Fi
           │
           ▼
┌───────────────────────────────┐
│       Waveshare ESP32-S3      │
│                               │
│  Wi-Fi receiver               │
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

Keep the Mac-side service responsible for **what is happening**.

Keep the ESP32 responsible for **how the duck looks and moves**.

This allows the animation system to remain responsive even if network
messages arrive infrequently.

------------------------------------------------------------------------

# 4. Phase 0 --- Design the Duck

## Goal

Define the duck's visual language before writing the animation system.

### Visual requirements

-   Pixel-art style
-   White duck
-   Yellow/orange beak
-   Minimal palette
-   Designed for a 240×240 canvas
-   Dark/black background
-   No unnecessary text
-   Strong silhouette
-   Large readable eyes
-   Expressions must remain recognizable at small size

### Initial design states

Create sprite/keyframe concepts for:

1.  Idle
2.  Blink
3.  Thinking
4.  Working
5.  Permission request
6.  Success
7.  Error
8.  Sleeping
9.  Connecting/loading

### Animation philosophy

Avoid traditional large sprite sheets where possible.

Instead, build the duck from reusable layers:

``` text
Duck
 ├── body
 ├── head
 ├── eyes
 ├── pupils
 ├── beak
 ├── wings
 ├── feet
 └── effects
```

This should make it possible to procedurally animate:

-   blinking
-   eye movement
-   pupil movement
-   breathing
-   body bobbing
-   head tilt
-   wing movement
-   beak movement
-   small particles
-   squash/stretch
-   jumping

This will give the duck much more personality than a collection of
static images.

------------------------------------------------------------------------

# 5. Phase 1 --- Development Environment

This can be done before the hardware arrives.

## Mac development

Set up a dedicated project repository.

Suggested structure:

``` text
copilot-duck/
├── README.md
├── docs/
│   └── build-plan.md
├── mac/
│   ├── src/
│   ├── package.json
│   └── tsconfig.json
├── firmware/
│   └── ...
├── assets/
│   ├── sprites/
│   └── animations/
└── tools/
```

### Mac-side stack

Preferred:

-   TypeScript
-   Node.js
-   WebSocket or lightweight HTTP/UDP transport
-   JSON state messages

Example message:

``` json
{
  "state": "working",
  "timestamp": 1727700000000
}
```

Keep the protocol deliberately simple.

------------------------------------------------------------------------

# 6. Phase 2 --- ESP32 Firmware Skeleton

Before implementing Copilot integration, establish communication with
the board.

## Firmware responsibilities

The ESP32 should:

1.  Connect to Wi-Fi.
2.  Connect to the Mac-side service.
3.  Receive state messages.
4.  Maintain the current duck state.
5.  Render animation frames.
6.  Transition smoothly between states.

### Recommended firmware approach

Start with the Waveshare-supported environment.

Evaluate:

-   Arduino
-   ESP-IDF
-   LVGL

For the first prototype, prioritize **fast iteration and reliable
rendering** over architectural purity.

If LVGL makes the graphics pipeline unnecessarily complicated, a custom
lightweight renderer may be preferable for the small 240×240 display.

------------------------------------------------------------------------

# 7. Phase 3 --- Display Rendering

## Initial target

Aim for approximately:

**30--60 FPS**

The duck should feel smooth rather than like a slideshow.

### Rendering layers

A frame could conceptually be:

``` text
background
    ↓
shadow
    ↓
body
    ↓
head
    ↓
wings
    ↓
eyes
    ↓
pupils
    ↓
beak
    ↓
effects
```

The background should remain as close to black as possible to maximize
the holographic effect.

------------------------------------------------------------------------

# 8. Phase 4 --- Animation Engine

Build a small animation/state system rather than hard-coding animations
directly into the network logic.

Example:

``` text
DuckState
  IDLE
  THINKING
  WORKING
  PERMISSION
  SUCCESS
  ERROR
  OFFLINE
  CONNECTING
```

Each state gets:

``` text
enter()
update(deltaTime)
render()
exit()
```

Example:

``` text
WORKING

body:
  subtle 2–3 px bob

eyes:
  occasionally look toward cursor/focus direction

wings:
  periodic typing-like movement

head:
  small forward tilt

effects:
  occasional tiny motion lines
```

------------------------------------------------------------------------

# 9. Phase 5 --- Mac ↔ ESP32 Communication

## Initial protocol

Use a persistent connection if practical.

Preferred:

``` text
Mac TypeScript service
        │
        │ WebSocket
        ▼
      ESP32
```

Messages should be small and state-oriented.

Example:

``` json
{
  "type": "state",
  "state": "thinking"
}
```

Potential future messages:

``` json
{
  "type": "state",
  "state": "working",
  "detail": "editing"
}
```

``` json
{
  "type": "event",
  "event": "success"
}
```

The ESP32 should not need to understand Copilot itself.

------------------------------------------------------------------------

# 10. Phase 6 --- Copilot CLI Integration

This is the most uncertain part of the project and should be isolated
from the rest of the system.

## Goal

Determine what signals/events can reliably tell us:

-   Copilot started working
-   Copilot is thinking
-   Copilot is modifying files
-   Copilot is waiting for permission
-   Copilot completed successfully
-   Copilot encountered an error
-   Copilot became inactive

### Strategy

Investigate available Copilot CLI:

-   hooks
-   events
-   lifecycle signals
-   command output
-   shell integration
-   process state

Do not tightly couple the animation engine to a particular Copilot
implementation.

Instead:

``` text
Copilot
   ↓
Copilot adapter
   ↓
normalized DuckState
   ↓
WebSocket
   ↓
ESP32
```

This makes the project resilient to changes in Copilot CLI.

------------------------------------------------------------------------

# 11. Phase 7 --- Hologram Prototype

Once the board arrives:

## First milestone

Get the Waveshare demo running exactly as shipped.

Verify:

-   LCD works
-   Prism works
-   Wi-Fi works
-   USB connection works
-   Firmware can be flashed
-   Serial logging works

Then replace the demo graphics with the duck.

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
-   Test brightness levels

------------------------------------------------------------------------

# 12. Phase 8 --- Copilot End-to-End Demo

First complete demo:

``` text
Start Copilot
      ↓
Duck wakes up
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

Use a logical coordinate system where possible.

------------------------------------------------------------------------

# 15. Future Interaction

The ESP32-S3 board includes an IMU, which can eventually be used for
personality/interactivity.

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

Keep audio out of V1 unless the hardware/software makes it trivial.

The duck should work perfectly without sound.

------------------------------------------------------------------------

# 17. Development Milestones

## Milestone 1 --- Duck concept

-   [ ] Finalize pixel-art duck
-   [ ] Define color palette
-   [ ] Define core expressions
-   [ ] Define animation vocabulary

## Milestone 2 --- Mac prototype

-   [ ] Create TypeScript project
-   [ ] Implement normalized DuckState
-   [ ] Create local fake Copilot event generator
-   [ ] Implement WebSocket server
-   [ ] Test state transitions

## Milestone 3 --- ESP32

-   [ ] Receive Waveshare board
-   [ ] Flash example firmware
-   [ ] Confirm display
-   [ ] Confirm prism
-   [ ] Confirm Wi-Fi
-   [ ] Create minimal firmware
-   [ ] Receive state messages

## Milestone 4 --- Animation

-   [ ] Render duck
-   [ ] Idle animation
-   [ ] Blink
-   [ ] Thinking
-   [ ] Working
-   [ ] Permission
-   [ ] Success
-   [ ] Error
-   [ ] Offline

## Milestone 5 --- Copilot integration

-   [ ] Investigate Copilot CLI events/hooks
-   [ ] Implement Copilot adapter
-   [ ] Map Copilot activity → DuckState
-   [ ] Test real sessions

## Milestone 6 --- First complete prototype

-   [ ] Mac → Copilot → Wi-Fi → ESP32 → duck
-   [ ] Verify stability
-   [ ] Tune animation
-   [ ] Tune brightness
-   [ ] Tune prism positioning

## Milestone 7 --- Final physical design

-   [ ] Measure monitor
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

While the Waveshare kit is in transit:

1.  Create the project repository.
2.  Create the TypeScript Mac bridge.
3.  Define the DuckState protocol.
4.  Build a fake Copilot event generator.
5.  Design the pixel-art duck.
6.  Prototype animations on the Mac.
7.  Investigate Copilot CLI hooks/events.
8.  Document the ESP32 communication protocol.
9.  Prepare the firmware project structure.
10. When the hardware arrives, connect the existing software rather than
    starting from scratch.

The key objective during the 2--3 week wait is:

**Have the software architecture and duck animations ready before the
hardware arrives.**
