"""Parametric exhibit models with exact micrometre-grid box checks."""
from dataclasses import dataclass
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile


VERTICES = ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
            (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))
FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))
SCALE = 1_000_000


def label(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 100 or not value.isprintable():
        raise ValueError("expected a printable title or name of 1 to 100 characters")
    return value


def vector(value, *, positive):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("coordinates must be three numbers in metres")
    result = []
    for n in value:
        if type(n) not in (int, Decimal) or not Decimal(n).is_finite() or Decimal(n).copy_abs() > 10000:
            raise ValueError("coordinates must be finite and within 10000 metres")
        # Use an integer grid so decimal faces that meet exactly never intersect.
        number = Decimal(n)
        if number and number.copy_abs() < Decimal("0.000001"):
            raise ValueError("coordinates must lie on the micrometre grid")
        numerator, denominator = number.as_integer_ratio()
        scaled, remainder = divmod(numerator * SCALE, denominator)
        if remainder:
            raise ValueError("coordinates must lie on the micrometre grid")
        if positive and scaled <= 0:
            raise ValueError("size and room dimensions must be positive")
        result.append(scaled)
    return tuple(result)


@dataclass(frozen=True)
class Box:
    name: str
    low: tuple
    high: tuple

    @classmethod
    def read(cls, spec, *, offset=(0, 0, 0)):
        if not isinstance(spec, dict) or not isinstance(spec.get("id"), str) or not re.fullmatch(
                r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", spec["id"]):
            raise ValueError("invalid item id")
        relative = vector(spec.get("origin"), positive=False)
        low = tuple(a + b for a, b in zip(relative, offset))
        size = vector(spec.get("size"), positive=True)
        return cls(spec["id"], low, tuple(a + b for a, b in zip(low, size)))

    def overlaps(self, other):
        return all(max(a, c) < min(b, d) for a, b, c, d in zip(self.low, self.high, other.low, other.high))

    def outside(self, room):
        return any(lo < 0 or hi > limit for lo, hi, limit in zip(self.low, self.high, room))

    def dimensions(self):
        return {"id": self.name, "origin": list(map(meters, self.low)),
                "size": [meters(hi - lo) for hi, lo in zip(self.high, self.low)]}

    def vertices(self):
        return [tuple((self.low[i], self.high[i])[corner[i]] for i in range(3)) for corner in VERTICES]


def meters(um):
    return um / SCALE


def obj_text(boxes):
    lines = ["# units: m", "# right-handed coordinates; +Z up"]
    for index, box in enumerate(boxes):
        lines.append("o " + box.name)
        for point in box.vertices():
            lines.append("v " + " ".join(f"{meters(n):.6f}" for n in point))
        for face in FACES:
            lines.append("f " + " ".join(str(8 * index + offset + 1) for offset in face))
    return "\n".join(lines) + "\n"


def service_review(items, boxes, room):
    zones = []
    for item, owner in zip(items, boxes):
        specs = item.get("service_zones", [])
        if not isinstance(specs, list) or len(specs) > 8:
            raise ValueError("each item may specify up to 8 service zones")
        if len(zones) + len(specs) > 64:
            raise ValueError("a layout may specify up to 64 service zones")
        names = set()
        for spec in specs:
            zone = Box.read(spec, offset=owner.low)
            if zone.name in names:
                raise ValueError("duplicate service zone id for one item")
            names.add(zone.name)
            zones.append((owner.name, zone))

    intrusions = []
    outside = []
    conflicts = []
    for index, (owner, zone) in enumerate(zones):
        if zone.outside(room):
            outside.append({"owner": owner, "zone": zone.name})
        for box in boxes:
            if zone.overlaps(box):
                intrusions.append({"owner": owner, "zone": zone.name, "equipment": box.name})
        for other_owner, other_zone in zones[index + 1:]:
            if owner != other_owner and zone.overlaps(other_zone):
                conflicts.append({"owner_a": owner, "zone_a": zone.name,
                                  "owner_b": other_owner, "zone_b": other_zone.name})
    return {"service_zones": [{"owner": owner, **zone.dimensions()} for owner, zone in zones],
            "service_intrusions": intrusions, "service_out_of_bounds": outside,
            "simultaneous_service_conflicts": conflicts}


def critique(spec, room, index):
    if not isinstance(spec, dict):
        raise ValueError("each layout must be an object")
    name = label(spec.get("name"))
    items = spec.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= 64:
        raise ValueError("a layout must have 1 to 64 items")
    boxes = [Box.read(item) for item in items]
    if len({box.name for box in boxes}) != len(boxes):
        raise ValueError("duplicate item id within a layout")
    outside = [box.name for box in boxes if box.outside(room)]
    collisions = [[a.name, b.name] for i, a in enumerate(boxes) for b in boxes[i + 1:] if a.overlaps(b)]
    model = obj_text(boxes).encode()
    report = {"name": name, "collisions": collisions, "out_of_bounds": outside,
              "obj": f"layout-{index}.obj", "obj_sha256": hashlib.sha256(model).hexdigest(),
              "items": [box.dimensions() for box in boxes], **service_review(items, boxes, room)}
    return report, model


def read_study(source):
    with source.open("rb") as stream:
        raw = stream.read(131073)
    if len(raw) > 131072:
        raise ValueError("input exceeds 128 KiB")
    spec = json.loads(raw, parse_float=Decimal)
    if not isinstance(spec, dict) or spec.get("unit") != "m":
        raise ValueError("expected a layout study with unit m")
    title = label(spec.get("title"))
    room = vector(spec.get("room"), positive=True)
    layouts = spec.get("layouts")
    if not isinstance(layouts, list) or not 1 <= len(layouts) <= 8:
        raise ValueError("expected 1 to 8 layout alternatives")
    records = [critique(layout, room, i) for i, layout in enumerate(layouts, 1)]
    if len({layout["name"] for layout, _ in records}) != len(records):
        raise ValueError("alternative names must be distinct")
    report = {"schema": "merlin-spatial-critique/1", "title": title, "unit": "m", "grid_m": 0.000001,
              "input_sha256": hashlib.sha256(raw).hexdigest(), "room": list(map(meters, room)),
              "layouts": [record for record, _ in records],
              "scope": "Axis-aligned interior overlap and rectangular room containment. Face contact is allowed. "
                       "Accessibility, circulation, structure and building code require separate evaluation."}
    return report, {record["obj"]: data for record, data in records}


def render_layout(source, destination):
    report, models = read_study(source)
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        stage = Path(temp)
        for filename, data in models.items():
            (stage / filename).write_bytes(data)
        text = json.dumps(report, ensure_ascii=True, indent=2)
        (stage / "critique.json").write_text(text + "\n", encoding="utf-8")
        template = Path(__file__).with_name("spatial_viewer.html").read_text(encoding="utf-8")
        # The HTML raw-text script element must never contain a literal input '<'.
        (stage / "index.html").write_text(template.replace("{{REPORT}}", text.replace("<", "\\u003c")),
                                         encoding="utf-8")
        destination.mkdir()
        try:
            for path in stage.iterdir():
                path.rename(destination / path.name)
        except OSError:
            shutil.rmtree(destination)
            raise
    return report
