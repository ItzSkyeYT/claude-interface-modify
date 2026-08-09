---
name: interface-modify
description: Visual "mini-Figma" round-trip editor for Android app screens. Use whenever the user wants to visually rearrange, annotate, or redesign a screen of an Android app being developed, e.g. "/interface-modify main_screen landscape", "/interface-modify 'the screen at the beginning'", "let me move things around myself", "I'll show you where to put stuff", or when they paste back an interface-modify/v1 JSON export. The screen argument is free-form: a name or a plain-English description that Claude resolves to the right activity/fragment. Works with a running emulator/device (pixel-true capture) or with NO device at all (code mode: reconstruct the screen from the layout XML). Publishes an interactive editor where the user drags/resizes/rotates/crops real UI elements, rewrites text, groups, and pins comments, then interprets their exported JSON into concrete layout code changes.
---

# interface-modify

Round-trip: **capture or reconstruct** the screen, **publish** an interactive editor, the
user edits and clicks *Copy for Claude*, then **interpret** the pasted JSON into layout code
changes. Rebuild, screenshot, verify.

The user's visual edit is the spec. Your job on re-entry is translation, not re-design. If
their JSON moves a button 40dp up, that is the requirement. Don't second-guess it unless it
is technically impossible, and say so if it is.

## Arguments

`/interface-modify <screen> [portrait|landscape]`

- `<screen>` is **free-form**. It can be an identifier ("main_screen", "settings") or a
  plain-English description: "the screen at the beginning", "the page with the ruler",
  "whatever opens when you tap the flashlight". Resolve it yourself: check the manifest's
  launcher activity, the fragment classes, layout file names, and navigation flow. Then
  SAY what you resolved it to ("reading 'the screen at the beginning' as CompassFragment,
  fragment_compass.xml") so a wrong guess is caught before any work happens.
- Orientation (optional) decides everything downstream: device rotation during capture,
  which layout file the interpreted edits land in (`res/layout/` vs `res/layout-land/`),
  and the scene name (`<screen>_portrait` / `<screen>_landscape`). If omitted, use the
  device's current orientation (device mode) or portrait (code mode), and say which.

## Choosing a mode

**Device mode** (a booted emulator or connected device shows the app): pixel-true. The
editor layers are crops of a real screenshot. Prefer this when available.

**Code mode** (no device, no emulator, no build): reconstruct the screen from source. The
render is a faithful approximation, not a pixel screenshot, and you should say so. The
round-trip is just as exact, because the geometry comes from the same dp values the layout
uses. Use it when `adb devices` shows nothing usable, or the user asks for it.

Check for a device first; fall back to code mode automatically and tell the user which mode
ran.

## Stage 1a: Device-mode capture

```bash
# Force the requested orientation FIRST (user_rotation: 0=portrait, 1=landscape),
# give the activity a beat to re-lay-out, then verify before capturing.
adb -s <serial> shell settings put system accelerometer_rotation 0
adb -s <serial> shell settings put system user_rotation <0|1>
adb -s <serial> shell 'sleep 2'

adb -s <serial> exec-out screencap -p > screen.png          # full-res, physical px
adb -s <serial> shell dumpsys activity top > dump.txt        # view hierarchy w/ bounds
python3 scripts/parse_bounds.py dump.txt <package> --visible-only > elements_raw.json
```

`parse_bounds.py` works while the UI is animating (`uiautomator dump` does not; it needs an
idle window, and sensor-driven screens are never idle). It walks the indentation tree and
accumulates parent offsets, so bounds come out absolute even for nested layouts.

Sanity-check the capture matches the requested orientation (`identify screen.png`; width >
height for landscape) before building the scene. A stale rotation captures the wrong layout
and every downstream number lands in the wrong file. Captures can also race app launches (a
splash-screen screenshot is small and mostly flat); if the PNG looks tiny, wait and
recapture.

**Curate, don't dump.** Raw output includes every labelled view. Hand-write a
`scene_spec.json` choosing 5 to 12 *semantic* elements the user would actually move:

- Group tightly-coupled rows into one element (a lat/long/altitude readout is one block,
  not six TextViews). Users move blocks, and the interpretation maps blocks back to chains.
- Exclude children of a custom-drawn view (a compass dial's letters rotate with the dial;
  they are not independently movable).
- Give every element a human `label`. It appears in the Layers panel and as the `near` hint
  on comments.
- Add `"circle_mask": true` for circular elements so their square crop corners don't
  occlude neighbours when dragged.
- Text-bearing elements get a `"text"` field and become live editable text layers
  (double-click to rewrite content in the editor) instead of pixel crops. Provide the
  current on-screen text (`\n` for multiline), `font_px` (device px: textSize sp times
  px_per_dp), and optionally `color`/`align` from the theme. Icons and drawn views stay
  image crops.

```json
{"elements": [
  {"id": "settings_btn", "label": "Settings button", "x": 1568, "y": 1152, "w": 144, "h": 144},
  {"id": "compass_view", "label": "Compass dial", "x": 172, "y": 120, "w": 1152, "h": 1152, "circle_mask": true},
  {"id": "city", "label": "Place name", "x": 1496, "y": 602, "w": 1496, "h": 172,
   "text": "New York, US", "font_px": 66, "color": "#e6e1e6", "align": "center"}
]}
```

Then build the scene (crops each element, heals the background behind it with the sampled
flat colour, downscales by 2, emits data URIs):

```bash
# scene_meta.json: {"screen": "<name>_<orientation>", "app": "<package>", "density": <dpi>, "bg_probe": [x, y]}
#   bg_probe = a px coordinate over empty flat background, used as the heal colour.
python3 scripts/prep_assets.py screen.png scene_spec.json scene_meta.json scene.json
```

Get density from `adb shell wm density`. Healing assumes a flat background. For gradient or
image backgrounds the healed rects will be visible; acceptable for annotation, but note it
to the user.

## Stage 1b: Code-mode reconstruction

No scripts needed: read the source and author `scene.json` directly.

1. Read the screen's layout XML (right orientation variant), plus `strings.xml`, theme
   colours, and `dimens.xml`. Pick a reference device (2992x1344 at 480dpi for landscape,
   1344x2992 for portrait, or match a device the user has named). Editor coordinates are
   device px divided by `scale` (use 2).
2. Compute each element's bounds from the constraints with ordinary dp math
   (px = dp x density/160). Solve the common patterns by hand: parent-edge anchors,
   margins, centring, simple chains. Where a bound is genuinely ambiguous (weights,
   barriers, runtime-sized content), estimate and note the estimate in your reply.
3. Author elements by kind:
   - Text views become `"type": "text"` layers with the real string resource content,
     `fontPx` (sp x density/160 / scale), `color` and `align` from the layout.
   - Buttons, icons, images, and custom-drawn views become `"type": "box"` placeholders:
     `{"type": "box", "label": "Settings", "color": "#26282d", "radius": 36}`. The label
     shows inside the box; radius half the width makes circles.
   - Background is a flat colour: `"bg": {"color": "#131316", "w": <W>, "h": <H>}`.
4. Build and publish exactly as in Stage 2. Tell the user this is a code-mode
   reconstruction: positions are computed from the layout, visuals are placeholders.

Scene skeleton:

```json
{
  "meta": {"screen": "compass_landscape", "app": "uk.akane.omni",
           "deviceW": 2992, "deviceH": 1344, "density": 480, "scale": 2},
  "bg": {"color": "#131316", "w": 1496, "h": 672},
  "els": [
    {"id": "compass_view", "label": "Compass dial", "type": "box",
     "x": 86, "y": 60, "w": 576, "h": 576, "radius": 288, "color": "#1b1c1e"},
    {"id": "city", "label": "Place name", "type": "text", "x": 748, "y": 301,
     "w": 748, "h": 86, "text": "New York, US", "fontPx": 33, "color": "#e6e1e6", "align": "center"}
  ]
}
```

## Stage 2: Publish

```bash
python3 scripts/build_editor.py assets/editor_template.html scene.json <screen>_editor.html
```

Publish the built file with the Artifact tool (favicon suggestion: a ruler or triangle
emoji). The page is fully self-contained (CSP-safe: no external resources; images, if any,
are data URIs). Tell the user:

- drag to move; magenta smart guides snap edges/centres, Slides-style (Alt disables)
- shift-click selects several; Ctrl+G groups, Ctrl+Shift+G ungroups
- handles resize (shift keeps aspect); text boxes reflow like Google Slides: side handles
  rewrap, top/bottom add space but never clip, corners scale the text
- knob rotates, snapping at the quarter turns; Crop button for image layers
- double-click any text to rewrite it; R/O/A/T add shapes and labels; C drops numbered
  comment pins; Del hides/deletes
- when done: **Copy for Claude**, then paste the JSON back here (Download JSON is the
  fallback; if the sandbox blocks both, a modal shows the JSON to copy manually)

Do not edit generated `*_editor.html` files directly. Fix `assets/editor_template.html` and
rebuild, or the fix is lost on the next screen.

## Stage 3: Interpret the returned JSON

Schema reference: [references/export-schema.md](references/export-schema.md). Read it
before interpreting your first export. Key rules:

- All `*_px` are physical device pixels; `device.units` carries the px-to-dp formula. Work
  in **dp** when writing Android layouts.
- **Positions are approximate by declaration.** The user is eyeballing with a mouse. Read
  deltas as intent, then snap to the app's own conventions: existing margins, alignment
  with neighbouring elements, existing chains and guidelines. Exception: exact edge/centre
  alignments in the export are deliberate (smart guides snapped them) and should become
  real constraints.
- `text_changed` means a rewritten text layer: a string-resource change, separate from
  geometry. `text_style` carries font size (sp precomputed) and colour changes; map colours
  to the nearest theme attribute, not hardcoded hex, unless clearly intentional.
- `elements_hidden` usually means `visibility="gone"` or removal. Confirm before deleting
  anything other code references.
- `groups` lists elements the user moved as one; preserve their relative spacing (chains, a
  shared parent, consistent margins).
- Annotations and comments are the user's *intent* channel: a rect drawn around empty space
  plus a comment "put the readout here" outranks small pixel deltas.
- Translate deltas into the layout system's own vocabulary (constraints, chains, margins),
  never absolute positions.

After implementing: rebuild the app, screenshot the same screen (device mode) and show it
next to the editor state so the user can verify their edit landed. In code mode, show the
updated layout's key numbers instead, or offer to boot an emulator for visual proof.

## Regenerating

Same screen after code changes: recapture or re-derive (stage 1 is cheap) and republish to
the same Artifact URL so the user's tab updates. Different screen: new spec, new artifact.
