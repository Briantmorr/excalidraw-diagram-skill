import math


def calculate_excalidraw_bounds(
    text: str,
    font_family: int,
    font_size: int,
    current_width: float | None = None,
    current_height: float | None = None,
) -> dict:
    """Calculate approximate pixel dimensions for text in Excalidraw.

    Returns tight text bounds and recommended container bounds.
    Uses character-width approximation (not pixel-accurate but catches major overflows).
    """
    PADDING_X = 12
    PADDING_Y = 12
    LINE_HEIGHT_MULTIPLIER = 1.25

    font_width_multipliers = {
        1: 0.6,   # Virgil
        2: 0.55,  # Helvetica
        3: 0.6,   # Cascadia (Monospace)
    }

    char_width_multiplier = font_width_multipliers.get(font_family, 0.6)

    lines = text.split("\n")
    max_line_width = max(
        len(line) * font_size * char_width_multiplier for line in lines
    )

    text_height = (font_size * LINE_HEIGHT_MULTIPLIER) * len(lines)
    text_width = max_line_width

    container_width = math.ceil((text_width + (PADDING_X * 2)) * 1.05)
    container_height = math.ceil((text_height + (PADDING_Y * 2)) * 1.10)

    overflow_detected = False
    if current_width is not None and current_width < math.ceil(text_width):
        overflow_detected = True
    if current_height is not None and current_height < math.ceil(text_height):
        overflow_detected = True

    return {
        "textWidth": math.ceil(text_width),
        "textHeight": math.ceil(text_height),
        "containerWidth": container_width,
        "containerHeight": container_height,
        "overflowDetected": overflow_detected,
    }
