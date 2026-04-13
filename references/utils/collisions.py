import math


def detect_collisions(elements: list[dict], min_gap: float = 20.0) -> list[str]:
    """Identify overlapping elements and suggest resolution.

    Skips: deleted elements, arrows/lines, text inside containers,
    and elements fully nested inside others.

    Returns list of warning messages (not errors — intentional proximity is OK).
    """
    warnings: list[str] = []

    spatial_els = [
        el
        for el in elements
        if not el.get("isDeleted") and el.get("type") not in ("arrow", "line")
    ]

    for i in range(len(spatial_els)):
        for j in range(i + 1, len(spatial_els)):
            el1 = spatial_els[i]
            el2 = spatial_els[j]

            # Skip text inside its container
            if el1.get("type") == "text" and el1.get("containerId") == el2.get("id"):
                continue
            if el2.get("type") == "text" and el2.get("containerId") == el1.get("id"):
                continue

            x1, y1 = el1.get("x", 0), el1.get("y", 0)
            w1, h1 = el1.get("width", 0), el1.get("height", 0)
            x2, y2 = el2.get("x", 0), el2.get("y", 0)
            w2, h2 = el2.get("width", 0), el2.get("height", 0)

            # Skip if one element is fully inside the other (nested)
            if x1 >= x2 and y1 >= y2 and (x1 + w1) <= (x2 + w2) and (y1 + h1) <= (y2 + h2):
                continue
            if x2 >= x1 and y2 >= y1 and (x2 + w2) <= (x1 + w1) and (y2 + h2) <= (y1 + h1):
                continue

            overlap_x = (x1 < x2 + w2 + min_gap) and (x1 + w1 + min_gap > x2)
            overlap_y = (y1 < y2 + h2 + min_gap) and (y1 + h1 + min_gap > y2)

            if overlap_x and overlap_y:
                id1 = el1.get("id", "unknown")
                id2 = el2.get("id", "unknown")
                shift = math.ceil((x1 + w1 + min_gap) - x2)
                warnings.append(
                    f"Overlap: '{id1}' and '{id2}' — shift '{id2}' ~{shift}px right to clear"
                )

    return warnings
