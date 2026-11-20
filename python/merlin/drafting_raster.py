"""Conservative extra-ink measurement for source-reconstructed drawing guides.

This is not a netlist extractor or an electrical verifier.  A detected stroke
is unexplained ink, not proof of a conductor.  A clean result is useful only
alongside the existing source reconstruction and independent human verdict.
"""
from collections import deque
import hashlib
import io

from PIL import Image, ImageChops, ImageFilter, UnidentifiedImageError


CANVAS = (1536, 1024)
MARKS = {"A": [64, 64], "B": [1472, 64], "C": [1472, 960], "D": [64, 960]}
PARAMETERS = {
    "ink_luminance_at_most": 160,
    "guide_tolerance_radius_px": 3,
    "registration_tolerance_radius_px": 2,
    "max_missing_fiducial_fraction": 0.05,
    "max_missing_guide_fraction": 0.01,
    "max_residual_pixels": 25000,
    "max_components": 4096,
    "max_reported_components": 32,
    "minimum_stroke_axis_run_px": 32,
    "minimum_stroke_pixels": 48,
    "maximum_ignored_isolated_noise_pixels": 8,
}
LIMITS = (
    "Registered opaque 1536x1024 PNGs only; no alignment fitting. "
    "No OCR, terminal graph or electrical connection identity. Ink within the "
    "3px guide corridor, faint/short additions and overlapping strokes may be "
    "missed. Added annotation can resemble a conductor. No qualification, "
    "absence proof or calibrated probability; human review remains mandatory."
)


def _count(mask):
    return mask.histogram()[255]


def _decode(raw):
    with Image.open(io.BytesIO(raw), formats=["PNG"]) as src:
        # Inspect dimensions before pixel loading, including direct helper use.
        if src.size != CANVAS or src.n_frames != 1:
            raise ValueError("requires_exact_single_frame_canvas")
        if src.mode not in ("1", "L", "LA", "P", "RGB", "RGBA"):
            raise ValueError("unsupported_pixel_mode")
        rgba = src.convert("RGBA")
        if rgba.getchannel("A").getextrema() != (255, 255):
            raise ValueError("requires_opaque_pixels")
        return rgba.convert("L")


def _components(mask):
    """Bounded 8-connected components, with exact longest axis-aligned runs."""
    width, height = mask.size
    remaining = {i for i, value in enumerate(mask.tobytes()) if value}
    summaries = []
    while remaining:
        if len(summaries) >= PARAMETERS["max_components"]:
            return summaries, True
        start = min(remaining)
        remaining.remove(start)
        queue = deque([start])
        points = []
        while queue:
            index = queue.popleft()
            y, x = divmod(index, width)
            points.append((x, y))
            for dy in (-1, 0, 1):
                ny = y + dy
                if not 0 <= ny < height:
                    continue
                for dx in (-1, 0, 1):
                    nx = x + dx
                    if (dx or dy) and 0 <= nx < width:
                        neighbor = ny * width + nx
                        if neighbor in remaining:
                            remaining.remove(neighbor)
                            queue.append(neighbor)
        rows, columns = {}, {}
        for x, y in points:
            rows.setdefault(y, []).append(x)
            columns.setdefault(x, []).append(y)
        longest = 0
        for groups in (rows, columns):
            for values in groups.values():
                previous, run = None, 0
                for value in sorted(values):
                    run = run + 1 if previous is not None and value == previous + 1 else 1
                    longest = max(longest, run)
                    previous = value
        bbox = [min(columns), min(rows), max(columns) + 1, max(rows) + 1]
        is_stroke = (longest >= PARAMETERS["minimum_stroke_axis_run_px"]
                     and len(points) >= PARAMETERS["minimum_stroke_pixels"])
        summaries.append({"bbox_px_half_open": bbox, "pixels": len(points),
                          "longest_axis_run_px": longest, "stroke_like": is_stroke})
    summaries.sort(key=lambda row: (-row["pixels"], row["bbox_px_half_open"]))
    return summaries, False


def check_registered_raster(guide_png, candidate_png, controls):
    """Return measured mismatch/abstention; never independently accept a review.

    The caller must reconstruct the control package from authoritative source
    before invoking this helper.  Hash matching alone cannot establish that.
    No thresholds or permission settings are taken from candidate metadata.
    """
    result = {
        "schema": "merlin-registered-raster-check/1",
        "method": "registered-dark-ink-residual-v1",
        "status": "unknown", "reason": "not_measured",
        "guide_sha256": hashlib.sha256(guide_png).hexdigest(),
        "image_sha256": hashlib.sha256(candidate_png).hexdigest(),
        "parameters": dict(PARAMETERS), "limits": LIMITS,
        "qualification": False, "promotion_authority": False,
        "authority": "illustration mismatch measurement only",
    }
    if (not isinstance(controls, dict)
            or controls.get("schema") != "merlin-draft-control/1"
            or controls.get("canvas_px") != list(CANVAS)
            or controls.get("fiducials_px") != MARKS
            or controls.get("guide_sha256") != result["guide_sha256"]):
        result["reason"] = "guide_identity_or_scope_mismatch"
        return result
    result["source_sha256"] = controls.get("source_sha256")
    if len(guide_png) > 16_000_000 or len(candidate_png) > 32_000_000:
        result["reason"] = "input_byte_budget_exceeded"
        return result
    try:
        guide, candidate = _decode(guide_png), _decode(candidate_png)
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError,
            UnidentifiedImageError):
        result["reason"] = "unsupported_or_unreadable_registered_pixels"
        return result
    table = [255 if n <= PARAMETERS["ink_luminance_at_most"] else 0 for n in range(256)]
    expected, observed = guide.point(table), candidate.point(table)
    # Fixed filters, never alignment or threshold optimization against a candidate.
    observed_near = observed.filter(ImageFilter.MaxFilter(5))
    missing_marks = {}
    for name, (x, y) in MARKS.items():
        box = (x - 18, y - 18, x + 18, y + 18)
        template = expected.crop(box)
        count = _count(template)
        if not count:
            result["reason"] = "missing_reference_fiducial"
            return result
        lost = _count(ImageChops.subtract(template, observed_near.crop(box)))
        missing_marks[name] = {"expected_pixels": count, "missing_pixels": lost,
                               "missing_fraction": lost / count}
    result["registration"] = missing_marks
    if any(row["missing_fraction"] > PARAMETERS["max_missing_fiducial_fraction"]
           for row in missing_marks.values()):
        result["reason"] = "registration_not_established"
        return result
    allowed = expected.filter(ImageFilter.MaxFilter(7))
    residual = ImageChops.subtract(observed, allowed)
    residual_count, expected_count = _count(residual), _count(expected)
    if not expected_count:
        result["reason"] = "empty_reference_ink"
        return result
    missing = _count(ImageChops.subtract(expected, observed_near))
    result["measurement"] = {"expected_ink_pixels": expected_count,
                              "missing_ink_pixels": missing,
                              "missing_ink_fraction": missing / expected_count,
                              "unexplained_ink_pixels": residual_count}
    if residual_count > PARAMETERS["max_residual_pixels"]:
        result["reason"] = "residual_pixel_budget_exceeded"
        return result
    components, exhausted = _components(residual)
    result["component_count"] = len(components)
    result["component_scan_complete"] = not exhausted
    result["components"] = components[:PARAMETERS["max_reported_components"]]
    result["components_omitted"] = len(components) - len(result["components"])
    if exhausted:
        result["reason"] = "component_budget_exceeded"
        return result
    stroke_count = sum(row["stroke_like"] for row in components)
    result["stroke_like_component_count"] = stroke_count
    if stroke_count:
        result.update(status="unexpected_stroke", reason="long_unmodeled_dark_ink_requires_review")
    elif missing / expected_count > PARAMETERS["max_missing_guide_fraction"]:
        result["reason"] = "guide_ink_not_preserved"
    elif residual_count and not (residual_count <= PARAMETERS["maximum_ignored_isolated_noise_pixels"]
                                 and all(row["pixels"] == 1 for row in components)):
        result["reason"] = "ambiguous_unmodeled_ink"
    else:
        result.update(status="clear_within_scope", reason="no_unexpected_stroke_detected_within_limits")
    return result
