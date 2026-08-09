# interface-modify

**Intuitive Android interface modifying for Claude.**

Stop describing UI changes in words. This [Claude Code](https://claude.com/claude-code)
skill turns any screen of your Android app into a mini-Figma editor — you drag the real UI
elements where you want them, and Claude writes the layout code to match. Every edit round-
trips through a **structured JSON export** (before/after geometry in px *and* dp, rewritten
text, groups, annotated comments) that you can also use standalone: version it, diff it, or
feed it to any other tool.

Tell Claude `/interface-modify main_screen landscape` and it:

1. **Captures** the real screen from your running emulator/device — screenshot plus the
   actual view-hierarchy bounds of every UI element
2. **Publishes** a self-contained interactive editor (as a private Claude Artifact) where
   each real UI element is a draggable layer
3. You **redesign visually**: drag, resize, rotate, crop, rewrite text, add shapes/arrows/
   labels, pin numbered comments — then click **Copy for Claude**
4. Claude **interprets** the exported JSON into concrete layout code changes (ConstraintLayout
   constraints, margins, string resources), rebuilds the app, and screenshots the result for
   you to compare

Your visual edit becomes the spec. No more describing positions in words.

## Install

Paste this to Claude Code:

> Install the interface-modify skill from https://github.com/ItzSkyeYT/claude-interface-modify

or manually:

```bash
git clone https://github.com/ItzSkyeYT/claude-interface-modify ~/.claude/skills/interface-modify
```

(Per-project install: clone into `<project>/.claude/skills/interface-modify` instead.)

## Requirements

- Claude Code with a claude.ai login (the editor is published as a private Artifact)
- `adb` with a running emulator or connected device showing the app you're editing
- Python 3 with [Pillow](https://pypi.org/project/pillow/) (`pip install pillow`) for asset prep

## Usage

```
/interface-modify <screen> [portrait|landscape]
```

- `<screen>` — the screen to edit, in your words ("main_screen", "settings", "the compass
  page"); Claude navigates the running app there
- orientation — which layout variant to capture and, later, which layout file the edits land
  in (`res/layout/` vs `res/layout-land/`). Omitted = current device orientation.

### In the editor

| Action | How |
|---|---|
| Move | drag (magenta smart guides snap edges/centres, Slides-style; **Alt** disables) |
| Multi-select / group | **shift-click**, then **Ctrl+G** (Ctrl+Shift+G ungroups) |
| Resize | 8 handles — **shift** keeps aspect; text boxes reflow Google-Slides-style (sides rewrap, top/bottom add space but never clip, corners scale the text) |
| Rotate | knob above the selection — snaps at 0/90/180/270°, **shift** = 15° steps |
| Crop | select an image layer → **Crop** button |
| Edit text | double-click any text (or *Edit text* in the sidebar) |
| Annotate | **R**ect / ellipse (**O**) / **A**rrow / **T**ext label / **C**omment pin |
| Finish | **Copy for Claude** → paste the JSON back into the chat |

The export is a diff-shaped document (before/after/delta in device px *and* dp, rewritten
text, style changes, groups, comments with nearest-element hints) designed for an LLM to
translate into layout code — see
[references/export-schema.md](references/export-schema.md).

## What's in the box

```
SKILL.md                      the skill definition Claude follows
assets/editor_template.html   the self-contained editor (vanilla JS, no dependencies)
scripts/parse_bounds.py       view-hierarchy → absolute element bounds (works mid-animation)
scripts/prep_assets.py        crop elements, heal background, build the scene
scripts/build_editor.py       inject the scene into the template
references/export-schema.md   the interface-modify/v1 export format + interpretation rules
```

## Known limits

- Background "healing" behind lifted elements assumes a flat background colour
- Groups move as one but don't yet resize/rotate as a unit
- The editor targets desktop browsers (mouse + keyboard)

## License

MIT
