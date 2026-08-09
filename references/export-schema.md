# interface-modify/v1 export schema

The editor exports a *diff-shaped* document, not a raw scene: what changed, what didn't,
what the user drew, what they said. Interpret it in this order: comments first, then
annotations, then moved elements, then hidden elements.

```json
{
  "format": "interface-modify/v1",
  "app": "uk.akane.omni",
  "screen": "compass_landscape",
  "device": {
    "w_px": 2992, "h_px": 1344, "density_dpi": 480, "px_per_dp": 3,
    "units": "all *_px are physical device pixels; dp = px / 3. Rects are un-rotated boxes; rot is degrees clockwise about the rect centre."
  },
  "elements_moved": [{
    "id": "settings_btn", "label": "Settings button",
    "text_changed": null,
    "before_px": {"x": 1568, "y": 1152, "w": 144, "h": 144, "rot": 0},
    "after_px":  {"x": 2400, "y": 96,   "w": 144, "h": 144, "rot": 0},
    "before_dp": {"x": 522.7, "y": 384, "w": 48, "h": 48},
    "after_dp":  {"x": 800,   "y": 32,  "w": 48, "h": 48},
    "delta_px":  {"dx": 832, "dy": -1056, "dw": 0, "dh": 0, "drot": 0},
    "crop": null
  }, {
    "id": "city", "label": "Place name",
    "text_changed": {"before": "New York, US", "after": "New York"},
    "before_px": {"x": 1496, "y": 602, "w": 1496, "h": 172, "rot": 0},
    "after_px":  {"x": 1496, "y": 602, "w": 1496, "h": 172, "rot": 0},
    "before_dp": {"x": 498.7, "y": 200.7, "w": 498.7, "h": 57.3},
    "after_dp":  {"x": 498.7, "y": 200.7, "w": 498.7, "h": 57.3},
    "delta_px":  {"dx": 0, "dy": 0, "dw": 0, "dh": 0, "drot": 0},
    "crop": null
  }],
  "elements_unchanged": ["compass_view", "city"],
  "elements_hidden": ["text_indicator"],
  "annotations": [
    {"type": "rect", "px": {"x": 1500, "y": 80, "w": 400, "h": 160, "rot": 0},
     "dp": {"x": 500, "y": 26.7, "w": 133.3, "h": 53.3}, "text": null, "color": "#ff5555",
     "fill": "#58d68d"},
    {"type": "arrow", "from_px": {"x": 1640, "y": 1220}, "to_px": {"x": 2440, "y": 160},
     "from_near": "settings_btn", "to_near": "sheet_btn", "color": "#ff5555"},
    {"type": "text", "px": {"x": 1520, "y": 40, "w": 520, "h": 80, "rot": 0},
     "dp": {"x": 506.7, "y": 13.3, "w": 173.3, "h": 26.7},
     "text": "buttons live here now", "color": "#ffd24a"}
  ],
  "groups": [
    {"id": "g1", "members": ["settings_btn", "sheet_btn"]}
  ],
  "comments": [
    {"n": 1, "at_px": {"x": 2860, "y": 470}, "near": "Coordinates + altitude readout",
     "text": "make the altitude row bold"}
  ],
  "notes": "general free text, or null"
}
```

## Interpretation rules

- **Positions are approximate.** The user drags by eye; treat every coordinate as "about
  here", then land on the app's own spacing grid and alignments. An element left 3dp off
  another's edge almost certainly means "aligned with it".
- **`text_changed`** appears on text layers whose content the user rewrote (an element can
  be in `elements_moved` for a text change alone, with zero geometry delta). Map it to
  string resources / format strings, not layout.
- **`text_style`** appears when a text layer's font size or colour changed:
  `{font_px_before, font_px_after, font_sp_after, color_before, color_after}`.
  `font_sp_after` is precomputed for Android (`textSize` in sp). Colours are the editor's
  approximations: map them to the nearest theme attribute (`?colorOnSurface`,
  `?colorOutline`, `?colorPrimary`, ...), not hardcoded hex, unless the user clearly wants
  an off-theme colour.
- Text-layer *width* changes with unchanged font are reflow intent (the editor auto-fits
  height, Slides-style): translate to layout width/constraint changes and let Android wrap;
  the exported height is derived, don't copy it literally.
- Text-layer *height* beyond the text's natural fit (top/bottom handle drags; the editor
  clamps shrinking at the fit, so any surplus is deliberate) means vertical-space intent
  (padding, a taller touch target, or centring room), not a font change.
- A rotation of exactly 0/90/180/270 is deliberate (the editor magnets there); odd angles
  on UI elements are usually annotation-ish intent, so ask if unsure.
- **Work in dp** when writing Android layout XML; the `*_dp` values are precomputed at
  `density_dpi / 160` px per dp and rounded to 0.1.
- Deltas are derived at export from original-vs-final rects (never accumulated), with a
  0.75-editor-px epsilon, so sub-pixel drift is already filtered. `elements_unchanged` and
  `elements_hidden` are bare id lists.
- **Rot** is degrees clockwise about the rect centre; the rect itself is the un-rotated box.
- **crop**, when present, is `{src_frac: {x, y, w, h}}`: the visible window as 0..1
  fractions of the element's source bitmap, clamped so x+w <= 1.
- `near` / `from_near` / `to_near` name the closest *visible* element (by centre distance,
  at final positions); they ground vague comment prose like "this one".
- Intent outranks pixels: a drawn rect + comment describing a destination is the spec even
  if the user didn't drag the element itself. Conversely a 2dp accidental nudge that made
  it past the epsilon can be ignored if it contradicts nothing.
- Translate deltas into the layout system's own vocabulary (constraints, chains, margins,
  gravity) rather than absolute coordinates. Moving a bottom-anchored button up 40dp means
  `marginBottom += 40dp`; centring something means new constraints, not x = w/2.
- `elements_hidden` usually means `visibility="gone"` or removal; confirm with the user
  before deleting anything from code that other screens/logic reference.
- **`groups`** lists element ids the user grouped in the editor. Grouped elements moved
  together, so their relative spacing is deliberate: preserve it (chains, a shared parent,
  or consistent margins) rather than positioning each member independently. Snapping was
  active during drags, so exact edge/centre alignments between elements in the export are
  intentional, not coincidence. Implement them as real constraints
  (`layout_constraintStart_toStartOf`, centring, etc.).
