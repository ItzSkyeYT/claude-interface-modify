#!/usr/bin/env python3
"""Parse `dumpsys activity top` view hierarchy into absolute element bounds.

Works while the UI is animating (unlike `uiautomator dump`, which needs an idle
window). Bounds in the dump are parent-relative; this walks the indentation tree
and accumulates offsets so the output is absolute screen px.

    python3 parse_bounds.py dump.txt <package> [--visible-only] > elements.json
"""
import json
import re
import sys

LINE = re.compile(
    r"^(\s*)([\w.$]+)\{[0-9a-f]+ (.)[\w.]{8} [\w.]{8} "
    r"(-?\d+),(-?\d+)-(-?\d+),(-?\d+)(?: #[0-9a-f]+ (?:app|android):id/([\w]+))?"
)


def parse(path, package, visible_only=True):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()

    # The dump can contain several "View Hierarchy:" sections (one per visible
    # activity). Take the LAST section that mentions the target package above it.
    sections = [i for i, l in enumerate(lines) if "View Hierarchy:" in l]
    start = None
    for idx in sections:
        context = "\n".join(lines[max(0, idx - 40):idx])
        if package in context or any(package in l for l in lines[idx:idx + 200]):
            start = idx
    if start is None and sections:
        start = sections[-1]
    if start is None:
        raise SystemExit("no View Hierarchy section found")

    stack = []  # (indent, abs_x, abs_y)
    out = []
    for line in lines[start + 1:]:
        m = LINE.match(line)
        if not m:
            if line.strip() and not line.startswith(" "):
                break  # left the hierarchy block
            continue
        indent = len(m.group(1))
        visible = m.group(3)  # V=visible G=gone I=invisible
        l, t, r, b = (int(m.group(i)) for i in range(4, 8))
        vid = m.group(8)

        while stack and stack[-1][0] >= indent:
            stack.pop()
        ox, oy = (stack[-1][1], stack[-1][2]) if stack else (0, 0)
        ax, ay = ox + l, oy + t
        stack.append((indent, ax, ay))

        if vid is None:
            continue
        if visible_only and visible != "V":
            continue
        w, h = r - l, b - t
        if w <= 0 or h <= 0:
            continue
        out.append({"id": vid, "cls": m.group(2).rsplit(".", 1)[-1],
                    "x": ax, "y": ay, "w": w, "h": h})
    return out


if __name__ == "__main__":
    visible_only = "--visible-only" in sys.argv
    els = parse(sys.argv[1], sys.argv[2], visible_only)
    json.dump(els, sys.stdout, indent=1)
