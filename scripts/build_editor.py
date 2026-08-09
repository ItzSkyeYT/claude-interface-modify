#!/usr/bin/env python3
"""Inject a scene.json into the editor template.

    python3 build_editor.py template.html scene.json out.html
"""
import json
import sys

template, scene_path, out = sys.argv[1:4]
html = open(template, encoding="utf-8").read()
scene = json.dumps(json.load(open(scene_path)), separators=(",", ":"))

marker = "/*__SCENE__*/null"
if marker not in html:
    raise SystemExit("scene marker not found in template")
# Escape closing-script sequences so the JSON can't terminate the <script> block.
scene = scene.replace("</", "<\\/")
open(out, "w", encoding="utf-8").write(html.replace(marker, scene, 1))
print(f"{out}: {len(html) + len(scene)} bytes")
