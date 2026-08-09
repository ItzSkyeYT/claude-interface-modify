#!/usr/bin/env python3
"""Build the editor scene from a screenshot + curated element list.

Crops each element from the pristine screenshot, heals the background behind
every element (flat fill with the sampled bg colour), downscales everything by
SCALE, and emits scene.json with data-URI images ready for the HTML template.
"""
import base64
import io
import json
import sys

from PIL import Image, ImageDraw

SCALE = 2  # device px -> editor px divisor


def data_uri(img):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main(screen_path, elements_path, meta_path, out_path):
    screen = Image.open(screen_path).convert("RGBA")
    spec = json.load(open(elements_path))
    meta = json.load(open(meta_path))

    bg_probe = tuple(meta["bg_probe"])
    bg_color = screen.getpixel(bg_probe)

    els_out = []
    for el in spec["elements"]:
        x, y, w, h = el["x"], el["y"], el["w"], el["h"]
        base = {"id": el["id"], "label": el["label"],
                "x": x / SCALE, "y": y / SCALE, "w": w / SCALE, "h": h / SCALE}
        if "text" in el:
            # Text-bearing elements become live text layers so the user can rewrite
            # the content, not just push pixels around. font_px/color are the
            # DEVICE-px size and colour read from the app's layout/theme.
            els_out.append({**base, "type": "text", "text": el["text"],
                            "fontPx": el["font_px"] / SCALE,
                            "color": el.get("color", "#e6e1e6"),
                            "align": el.get("align", "left")})
            continue
        crop = screen.crop((x, y, x + w, y + h))
        if el.get("circle_mask"):
            mask = Image.new("L", (w * 2, h * 2), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, w * 2 - 1, h * 2 - 1], fill=255)
            crop.putalpha(mask.resize((w, h), Image.LANCZOS))
        crop = crop.resize((max(1, w // SCALE), max(1, h // SCALE)), Image.LANCZOS)
        els_out.append({**base, "src": data_uri(crop)})

    healed = screen.copy()
    draw = ImageDraw.Draw(healed)
    for el in spec["elements"]:
        draw.rectangle(
            [el["x"], el["y"], el["x"] + el["w"] - 1, el["y"] + el["h"] - 1],
            fill=bg_color,
        )
    healed = healed.convert("RGB").resize(
        (screen.width // SCALE, screen.height // SCALE), Image.LANCZOS
    )

    scene = {
        "meta": {
            "screen": meta["screen"],
            "app": meta["app"],
            "deviceW": screen.width,
            "deviceH": screen.height,
            "density": meta["density"],
            "scale": SCALE,
        },
        "bg": {"src": data_uri(healed), "w": healed.width, "h": healed.height},
        "els": els_out,
    }
    json.dump(scene, open(out_path, "w"))
    total = sum(len(e.get("src", "")) for e in els_out) + len(scene["bg"]["src"])
    n_text = sum(1 for e in els_out if e.get("type") == "text")
    print(f"scene.json written: {len(els_out)} elements ({n_text} text), ~{total // 1024}KB of images")


if __name__ == "__main__":
    main(*sys.argv[1:5])
