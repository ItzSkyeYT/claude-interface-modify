---
name: interface-modify
description: Visual "mini-Figma" round-trip editor for Android app screens. Use whenever the user wants to visually rearrange, annotate, or redesign a screen of an Android app being developed — e.g. "/interface-modify main_screen landscape", "/interface-modify settings portrait", "let me move things around myself", "I'll show you where to put stuff", "give me the editor for the compass screen", or when they paste back an interface-modify/v1 JSON export. Arguments are "<screen> [portrait|landscape]" — the orientation selects which layout variant is captured and later edited. Captures the real screen from the running app/emulator, publishes an interactive editor where the user drags/resizes/rotates/crops real UI elements and adds shapes/labels/comment pins, then interprets their exported JSON into concrete layout code changes.
---

# interface-modify

Round-trip: **capture** the real screen → **publish** an interactive editor → user edits and
clicks *Copy for Claude* → **interpret** the pasted JSON into layout code changes → rebuild,
screenshot, verify.

## Arguments

`/interface-modify <screen> [portrait|landscape]`

- `<screen>` — which screen of the app; interpret it against the app's fragments/activities
  (e.g. "main_screen" → the launcher fragment, "settings" → the settings screen). Navigate
  the running app there before capturing.
- Orientation (optional) — which variant to capture and edit. **This decides everything
  downstream**: the emulator rotation during capture, which layout file the interpreted
  edits land in (`res/layout/` vs `res/layout-land/`), and the scene name
  (`<screen>_portrait` / `<screen>_landscape`). If omitted, use the device's current
  orientation and SAY which one you captured, so a mismatch is caught immediately.

The user's visual edit is the spec. Your job on re-entry is translation, not re-design: if
their JSON moves a button 40dp up, that is the requirement — don't second-guess it unless it
is technically impossible, and say so if it is.

## Stage 1 — Capture

Everything runs on a booted emulator/device with the target app in the foreground, in the
requested orientation.

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

Sanity-check the capture matches the requested orientation (`identify screen.png` — width >
height for landscape) before building the scene; a stale rotation captures the wrong layout
and every downstream number lands in the wrong file. Captures can also race app launches
(a splash-screen screenshot is small and mostly flat) — if the PNG looks tiny, wait and
recapture.

`parse_bounds.py` works while the UI is animating (`uiautomator dump` does not — it needs an
idle window, and sensor-driven screens are never idle). It walks the indentation tree and
accumulates parent offsets, so bounds come out absolute even for nested layouts. If the dump
has several `View Hierarchy:` sections (launcher + app), it picks the target package's one.

**Curate, don't dump.** Raw output includes every labelled view. Hand-write a
`scene_spec.json` choosing 5–12 *semantic* elements the user would actually move:

- Group tightly-coupled rows into one element (a lat/long/altitude readout is one block, not
  six TextViews) — users move blocks, and the interpretation maps blocks back to chains.
- Exclude children of a custom-drawn view (a compass dial's letters rotate with the dial;
  they are not independently movable).
- Give every element a human `label` — it appears in the Layers panel and as the `near` hint
  on comments.
- Add `"circle_mask": true` for circular elements so their square crop corners don't occlude
  neighbours when dragged.
- **Text-bearing elements get a `"text"` field** and become live editable text layers
  (double-click to rewrite content in the editor) instead of pixel crops. Provide the current
  on-screen text (`\n` for multiline), `font_px` (device px — sp × density/160 × … just read
  the rendered size: textSize sp × px_per_dp), and optionally `color`/`align` from the
  theme. Icons and drawn views stay image crops — they move fine as pixels.

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
# scene_meta.json: {"screen": "<name>", "app": "<package>", "density": <dpi>, "bg_probe": [x, y]}
#   bg_probe = a px coordinate over empty flat background, used as the heal colour.
python3 scripts/prep_assets.py screen.png scene_spec.json scene_meta.json scene.json
```

Get density from `adb shell wm density`. Healing assumes a flat background — for gradient or
image backgrounds the healed rects will be visible; acceptable for annotation, but note it to
the user.

## Stage 2 — Publish

```bash
python3 scripts/build_editor.py assets/editor_template.html scene.json <screen>_editor.html
```

Publish the built file with the Artifact tool (favicon suggestion: 📐). The page is fully
self-contained (CSP-safe: no external resources, images are data URIs). Tell the user:

- drag to move · handles resize (shift = keep aspect) · knob above rotates (shift = 15° steps)
- Crop button (element selected) turns handles into croppers
- R/O/A/T add shapes and labels; C drops numbered comment pins; Del hides/deletes
- when done: **Copy for Claude** → paste the JSON back here (Download JSON is the fallback;
  if the sandbox blocks both, a modal shows the JSON to copy manually)

Do not edit generated `*_editor.html` files directly — fix `assets/editor_template.html` and
rebuild, or the fix is lost on the next screen.

## Stage 3 — Interpret the returned JSON

Schema reference: [references/export-schema.md](references/export-schema.md). Read it before
interpreting your first export. Key rules:

- All `*_px` are physical device pixels; `device.units` carries the px→dp formula. Work in
  **dp** when writing Android layouts.
- `elements_moved[].delta_px` is derived fresh at export from original vs final rect — trust
  it over any mental accumulation.
- `elements_unchanged` / `elements_hidden` are bare id lists. Hidden = the user wants it gone
  from this screen (usually `visibility="gone"` or removal — confirm if destructive).
- **Positions are approximate by declaration.** The user is eyeballing with a mouse, not
  measuring. Read deltas as intent — "move it to the top-right area", "make it about half
  the size" — then snap to the app's own conventions: existing margins (16/24dp grids),
  alignment with neighbouring elements, existing chains and guidelines. Never copy a raw
  37.3dp offset into a layout when the app's spacing system says 40dp.
- `text_changed` on a moved element means the user rewrote a text layer's content — that's a
  string-resource change (and possibly a format-string change), separate from any geometry.
- Annotations and comments are the user's *intent* channel: a rect drawn around empty space
  plus a comment "put the readout here" outranks small pixel deltas. `near` names the closest
  element to each pin at its final position.
- Translate deltas into the layout system actually in use (ConstraintLayout constraints,
  margins, chains) — not absolute positions. A 40dp upward move of a bottom-constrained
  button is `layout_marginBottom += 40dp`, not a new Y coordinate.

After implementing: rebuild the app, screenshot the same screen, and show it side by side
with the editor state so the user can verify their edit landed.

## Regenerating

Same screen after code changes → recapture (stage 1 is cheap) and republish to the same
Artifact URL so the user's tab updates. Different screen → new spec, new artifact.
