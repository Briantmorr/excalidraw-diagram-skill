"""Render Excalidraw JSON to PNG using Playwright + headless Chromium.

Supports both .excalidraw (plain JSON) and .excalidraw.md (Obsidian plugin format).

Usage:
    cd .claude/skills/excalidraw-diagram/references
    uv run python render_excalidraw.py <path-to-file.excalidraw[.md]> [--output path.png] [--scale 2] [--width 1920]

First-time setup:
    cd .claude/skills/excalidraw-diagram/references
    uv sync
    uv run playwright install chromium
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import zlib
from pathlib import Path


def decompress_lzstring_base64(compressed: str) -> str:
    """Decompress LZ-String base64 encoded data (used by Obsidian Excalidraw plugin)."""
    # LZ-String uses a custom base64 alphabet and compression scheme.
    # We'll use the lz-string compatible approach via raw bytes.
    # The Obsidian plugin uses compressToBase64/decompressFromBase64 from lz-string.
    # Python port: we need to handle this properly.
    try:
        # Try standard base64 + zlib first (some versions use this)
        decoded = base64.b64decode(compressed)
        return zlib.decompress(decoded).decode("utf-8")
    except Exception:
        pass

    # LZ-String base64 decompression (custom algorithm)
    # Using the lz-string Python port approach
    key_str = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
    base_reverse_dict = {key_str[i]: i for i in range(len(key_str))}

    def _get_base_value(char: str) -> int:
        return base_reverse_dict.get(char, 0)

    length = len(compressed)
    reset_value = 32
    data_val = _get_base_value(compressed[0])
    data_position = 32
    data_index = 1

    dictionary: dict[int, str] = {}
    enlarge_in = 4
    dict_size = 4
    num_bits = 3
    result: list[str] = []

    # Read first entry
    bits = 0
    max_power = 2**2
    power = 1
    while power != max_power:
        resb = data_val & data_position
        data_position >>= 1
        if data_position == 0:
            data_position = reset_value
            if data_index < length:
                data_val = _get_base_value(compressed[data_index])
                data_index += 1
        bits |= (1 if resb > 0 else 0) * power
        power <<= 1

    next_val = bits
    if next_val == 0:
        bits = 0
        max_power = 2**8
        power = 1
        while power != max_power:
            resb = data_val & data_position
            data_position >>= 1
            if data_position == 0:
                data_position = reset_value
                if data_index < length:
                    data_val = _get_base_value(compressed[data_index])
                    data_index += 1
            bits |= (1 if resb > 0 else 0) * power
            power <<= 1
        c = chr(bits)
    elif next_val == 1:
        bits = 0
        max_power = 2**16
        power = 1
        while power != max_power:
            resb = data_val & data_position
            data_position >>= 1
            if data_position == 0:
                data_position = reset_value
                if data_index < length:
                    data_val = _get_base_value(compressed[data_index])
                    data_index += 1
            bits |= (1 if resb > 0 else 0) * power
            power <<= 1
        c = chr(bits)
    elif next_val == 2:
        return ""

    dictionary[3] = c
    w = c
    result.append(c)

    while True:
        if data_index > length:
            return ""

        bits = 0
        max_power = 2**num_bits
        power = 1
        while power != max_power:
            resb = data_val & data_position
            data_position >>= 1
            if data_position == 0:
                data_position = reset_value
                if data_index < length:
                    data_val = _get_base_value(compressed[data_index])
                    data_index += 1
            bits |= (1 if resb > 0 else 0) * power
            power <<= 1

        c_code = bits
        if c_code == 0:
            bits = 0
            max_power = 2**8
            power = 1
            while power != max_power:
                resb = data_val & data_position
                data_position >>= 1
                if data_position == 0:
                    data_position = reset_value
                    if data_index < length:
                        data_val = _get_base_value(compressed[data_index])
                        data_index += 1
                bits |= (1 if resb > 0 else 0) * power
                power <<= 1
            dictionary[dict_size] = chr(bits)
            dict_size += 1
            c_code = dict_size - 1
            enlarge_in -= 1
        elif c_code == 1:
            bits = 0
            max_power = 2**16
            power = 1
            while power != max_power:
                resb = data_val & data_position
                data_position >>= 1
                if data_position == 0:
                    data_position = reset_value
                    if data_index < length:
                        data_val = _get_base_value(compressed[data_index])
                        data_index += 1
                bits |= (1 if resb > 0 else 0) * power
                power <<= 1
            dictionary[dict_size] = chr(bits)
            dict_size += 1
            c_code = dict_size - 1
            enlarge_in -= 1
        elif c_code == 2:
            return "".join(result)

        if enlarge_in == 0:
            enlarge_in = 2**num_bits
            num_bits += 1

        if c_code in dictionary:
            entry = dictionary[c_code]
        elif c_code == dict_size:
            entry = w + w[0]
        else:
            return "".join(result)

        result.append(entry)
        dictionary[dict_size] = w + entry[0]
        dict_size += 1
        enlarge_in -= 1

        if enlarge_in == 0:
            enlarge_in = 2**num_bits
            num_bits += 1

        w = entry


def extract_excalidraw_json(file_path: Path) -> dict:
    """Extract Excalidraw JSON from either .excalidraw or .excalidraw.md files."""
    raw = file_path.read_text(encoding="utf-8")

    if file_path.suffix == ".md" or file_path.name.endswith(".excalidraw.md"):
        # .excalidraw.md format — look for compressed JSON or raw JSON block
        compressed_match = re.search(r"```compressed-json\n([\s\S]*?)\n```", raw)
        if compressed_match:
            compressed = compressed_match.group(1).replace("\n", "")
            decompressed = decompress_lzstring_base64(compressed)
            return json.loads(decompressed)

        # Try raw JSON block
        json_match = re.search(r"```json\n([\s\S]*?)\n```", raw)
        if json_match:
            return json.loads(json_match.group(1))

        # Try finding raw Excalidraw JSON embedded after ## Drawing
        drawing_match = re.search(r"## Drawing\n([\s\S]*)", raw)
        if drawing_match:
            return json.loads(drawing_match.group(1).strip())

        raise ValueError(f"Could not find Excalidraw data in {file_path}")
    else:
        # Plain .excalidraw JSON
        return json.loads(raw)


def validate_excalidraw(data: dict) -> list[str]:
    """Validate Excalidraw JSON structure. Returns list of errors (empty = valid)."""
    errors: list[str] = []

    if data.get("type") != "excalidraw":
        errors.append(f"Expected type 'excalidraw', got '{data.get('type')}'")

    if "elements" not in data:
        errors.append("Missing 'elements' array")
    elif not isinstance(data["elements"], list):
        errors.append("'elements' must be an array")
    elif len(data["elements"]) == 0:
        errors.append("'elements' array is empty — nothing to render")

    return errors


def check_layout_warnings(data: dict) -> list[str]:
    """Non-blocking checks for text overflow and element collisions."""
    warnings: list[str] = []
    try:
        from utils.bounds import calculate_excalidraw_bounds
        from utils.collisions import detect_collisions
    except ImportError:
        return warnings  # utils not available, skip checks

    for el in data.get("elements", []):
        if el.get("type") == "text" and not el.get("isDeleted"):
            bounds = calculate_excalidraw_bounds(
                el.get("text", ""),
                el.get("fontFamily", 1),
                el.get("fontSize", 20),
                current_width=el.get("width"),
                current_height=el.get("height"),
            )
            if bounds.get("overflowDetected"):
                warnings.append(
                    f"  WARNING: text '{el.get('id', '?')}' may overflow "
                    f"(needs ~{bounds['textWidth']}x{bounds['textHeight']}, "
                    f"has {el.get('width', 0)}x{el.get('height', 0)})"
                )

    collision_warnings = detect_collisions(data.get("elements", []), min_gap=20.0)
    warnings.extend(f"  WARNING: {w}" for w in collision_warnings)

    return warnings


def compute_bounding_box(elements: list[dict]) -> tuple[float, float, float, float]:
    """Compute bounding box (min_x, min_y, max_x, max_y) across all elements."""
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")

    for el in elements:
        if el.get("isDeleted"):
            continue
        x = el.get("x", 0)
        y = el.get("y", 0)
        w = el.get("width", 0)
        h = el.get("height", 0)

        # For arrows/lines, points array defines the shape relative to x,y
        if el.get("type") in ("arrow", "line") and "points" in el:
            for px, py in el["points"]:
                min_x = min(min_x, x + px)
                min_y = min(min_y, y + py)
                max_x = max(max_x, x + px)
                max_y = max(max_y, y + py)
        else:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x + abs(w))
            max_y = max(max_y, y + abs(h))

    if min_x == float("inf"):
        return (0, 0, 800, 600)

    return (min_x, min_y, max_x, max_y)


def render(
    excalidraw_path: Path,
    output_path: Path | None = None,
    scale: int = 2,
    max_width: int = 1920,
) -> Path:
    """Render an .excalidraw file to PNG. Returns the output PNG path."""
    # Import playwright here so validation errors show before import errors
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright not installed.", file=sys.stderr)
        print("Run: cd .claude/skills/excalidraw-diagram/references && uv sync && uv run playwright install chromium", file=sys.stderr)
        sys.exit(1)

    # Read and validate (supports both .excalidraw and .excalidraw.md)
    try:
        data = extract_excalidraw_json(excalidraw_path)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"ERROR: Could not parse {excalidraw_path}: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_excalidraw(data)
    if errors:
        print(f"ERROR: Invalid Excalidraw file:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # Non-blocking layout warnings (overflow, collisions)
    warnings = check_layout_warnings(data)
    if warnings:
        print("Layout warnings:", file=sys.stderr)
        for w in warnings:
            print(w, file=sys.stderr)

    # Compute viewport size from element bounding box
    elements = [e for e in data["elements"] if not e.get("isDeleted")]
    min_x, min_y, max_x, max_y = compute_bounding_box(elements)
    padding = 80
    diagram_w = max_x - min_x + padding * 2
    diagram_h = max_y - min_y + padding * 2

    # Cap viewport width, let height be natural
    vp_width = min(int(diagram_w), max_width)
    vp_height = max(int(diagram_h), 600)

    # Output path (handle .excalidraw.md → .png correctly)
    if output_path is None:
        if excalidraw_path.name.endswith(".excalidraw.md"):
            output_path = excalidraw_path.with_name(
                excalidraw_path.name.replace(".excalidraw.md", ".png")
            )
        else:
            output_path = excalidraw_path.with_suffix(".png")

    # Template path (same directory as this script)
    template_path = Path(__file__).parent / "render_template.html"
    if not template_path.exists():
        print(f"ERROR: Template not found at {template_path}", file=sys.stderr)
        sys.exit(1)

    template_url = template_path.as_uri()

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            if "Executable doesn't exist" in str(e) or "browserType.launch" in str(e):
                print("ERROR: Chromium not installed for Playwright.", file=sys.stderr)
                print("Run: cd .claude/skills/excalidraw-diagram/references && uv run playwright install chromium", file=sys.stderr)
                sys.exit(1)
            raise

        page = browser.new_page(
            viewport={"width": vp_width, "height": vp_height},
            device_scale_factor=scale,
        )

        # Load the template
        page.goto(template_url)

        # Wait for the ES module to load (imports from esm.sh)
        page.wait_for_function("window.__moduleReady === true", timeout=30000)

        # Inject the diagram data and render
        json_str = json.dumps(data)
        result = page.evaluate(f"window.renderDiagram({json_str})")

        if not result or not result.get("success"):
            error_msg = result.get("error", "Unknown render error") if result else "renderDiagram returned null"
            print(f"ERROR: Render failed: {error_msg}", file=sys.stderr)
            browser.close()
            sys.exit(1)

        # Wait for render completion signal
        page.wait_for_function("window.__renderComplete === true", timeout=15000)

        # Screenshot the SVG element
        svg_el = page.query_selector("#root svg")
        if svg_el is None:
            print("ERROR: No SVG element found after render.", file=sys.stderr)
            browser.close()
            sys.exit(1)

        svg_el.screenshot(path=str(output_path))
        browser.close()

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Excalidraw JSON to PNG (supports .excalidraw and .excalidraw.md)")
    parser.add_argument("input", type=Path, help="Path to .excalidraw or .excalidraw.md file")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output PNG path (default: same name with .png)")
    parser.add_argument("--scale", "-s", type=int, default=2, help="Device scale factor (default: 2)")
    parser.add_argument("--width", "-w", type=int, default=1920, help="Max viewport width (default: 1920)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: File not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    png_path = render(args.input, args.output, args.scale, args.width)
    print(str(png_path))


if __name__ == "__main__":
    main()
