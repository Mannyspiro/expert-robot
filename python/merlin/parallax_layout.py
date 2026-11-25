"""Exact accounting for a proposed abstract tile model, not a chip simulator.

Coordinates and decorative boxes use tile pitch, never physical millimetres.
The geometry IR's mandatory physical-unit conversion is intentionally not used.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

LAYOUTS = {"line": (32, 1, 1), "plane": (8, 4, 1), "stack": (4, 4, 2)}
ROLES = ("compute", "compute", "kv", "control")
MODEL_REVISION = "0cf73e2d49ea1a09a9ef85178b73ad68e019ae36"
LABEL = "PROPOSED ABSTRACT TILE MODEL"
FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


@dataclass(frozen=True)
class Grid:
    nx: int
    ny: int
    nz: int

    def __post_init__(self):
        for name in ("nx", "ny", "nz"):
            _integer(getattr(self, name), name, 1)

    @property
    def volume(self):
        return self.nx * self.ny * self.nz

    def pack(self, cell):
        if len(cell) != 3:
            raise ValueError("A cell requires exactly three coordinates")
        for v, bound in zip(cell, (self.nx, self.ny, self.nz)):
            if _integer(v, "coordinate") >= bound:
                raise ValueError("Coordinate outside the half-open grid")
        x, y, z = cell
        return x + self.nx * (y + self.ny * z)

    def unpack(self, address):
        if _integer(address, "address") >= self.volume:
            raise ValueError("Address outside grid volume")
        return address % self.nx, (address // self.nx) % self.ny, address // (self.nx * self.ny)


@dataclass(frozen=True)
class Tile:
    address: int
    role: str
    index: int
    cell: tuple[int, int, int]

    @property
    def label(self):
        return {"compute": "C", "kv": "K", "control": "I"}[self.role] + f"{self.index:02d}"

    @property
    def bounds_eighths(self):
        return tuple(8 * v + 1 for v in self.cell), tuple(8 * v + 7 for v in self.cell)


def axis_separated(a, b):
    alo, ahi = a.bounds_eighths
    blo, bhi = b.bounds_eighths
    return any(ahi[i] <= blo[i] or bhi[i] <= alo[i] for i in range(3))


def assignment(address):
    if _integer(address, "tile address") >= 32:
        raise ValueError("This model contains exactly 32 tiles")
    group, slot = divmod(address, 4)
    return ROLES[slot], 2 * group + slot if slot < 2 else group


def validate_tiles(grid, tiles):
    if grid.volume != 32 or len(tiles) != 32:
        raise ValueError("The layout requires exactly 32 grid cells and tiles")
    if len({tile.address for tile in tiles}) != 32:
        raise ValueError("Tile addresses must be unique")
    for tile in tiles:
        _integer(tile.index, "tile role index")
        if grid.pack(tile.cell) != tile.address:
            raise ValueError("Tile coordinate/address mapping disagrees")
        if (tile.role, tile.index) != assignment(tile.address):
            raise ValueError("Tile assignment must be identical across layouts")
    if any(not axis_separated(a, b) for a, b in combinations(tiles, 2)):
        raise ValueError("Decorative tile boxes overlap")


def make_layout(name):
    if name not in LAYOUTS:
        raise ValueError("Unknown layout")
    grid = Grid(*LAYOUTS[name])
    tiles = tuple(Tile(a, *assignment(a), grid.unpack(a)) for a in range(32))
    validate_tiles(grid, tiles)
    return grid, tiles


def manhattan(a, b):
    if len(a) != 3 or len(b) != 3:
        raise ValueError("Endpoints require three coordinates")
    for v in (*a, *b):
        _integer(v, "coordinate")
    return sum(abs(x - y) for x, y in zip(a, b))


def xyz_route(grid, a, b):
    grid.pack(a)
    grid.pack(b)
    point, route = list(a), [tuple(a)]
    for axis in range(3):
        while point[axis] != b[axis]:
            point[axis] += 1 if point[axis] < b[axis] else -1
            route.append(tuple(point))
    return tuple(route)


def kv_cache_bytes(*, layers=28, kv_heads=8, head_dim=128,
                   context_length=4096, batch=1, element_bytes=2):
    values = (layers, kv_heads, head_dim, context_length, batch, element_bytes)
    for v in values:
        _integer(v, "KV dimension", 1)
    return 2 * layers * kv_heads * head_dim * context_length * batch * element_bytes


def layout_report(name, context_length=4096):
    grid, tiles = make_layout(name)
    bank_bytes = kv_cache_bytes(context_length=context_length) // 8
    transfers = []
    for tile in tiles:
        if tile.role != "compute":
            continue
        bank = tiles[4 * (tile.index // 2) + 2]
        hops = manhattan(tile.cell, bank.cell)
        transfers.append({"compute": tile.label, "source_address": bank.address,
                          "shared_kv": bank.label, "destination_address": tile.address,
                          "route_cells": xyz_route(grid, bank.cell, tile.cell),
                          "hops": hops, "payload_bytes": bank_bytes, "byte_hops": bank_bytes * hops})
    return {"name": name, "dimensions": [grid.nx, grid.ny, grid.nz],
            "tiles": [{"address": t.address, "role": t.role, "index": t.index,
                       "label": t.label, "cell": t.cell,
                       "box_bounds_eighths": t.bounds_eighths} for t in tiles],
            "transfers": transfers,
            "validation": {"in_bounds_tiles": 32, "unique_addresses": 32,
                           "axis_separated_pairs": 496, "assignment_preserved": True},
            "metrics": {"logical_reads": len(transfers), "total_hops": sum(t["hops"] for t in transfers),
                        "maximum_hops": max(t["hops"] for t in transfers),
                        "payload_read_bytes": bank_bytes * len(transfers),
                        "byte_hops": sum(t["byte_hops"] for t in transfers)}}


def comparison_report(context_length=4096):
    capacity = kv_cache_bytes(context_length=context_length)
    return {"schema": "merlin-parallax-abstract-layouts/1", "label": LABEL,
            "units": {"coordinates": "tile pitch", "hops": "adjacent grid edges",
                      "traffic": "bytes * hops", "box_bounds_eighths": "tile pitch / 8"},
            "checkpoint_shape": {"model_id": "YifeiZuo/Parallax-0.6B", "revision": MODEL_REVISION,
                                 "layers": 28, "query_r_heads": 16, "kv_heads": 8, "head_dim": 128,
                                 "context_length": context_length, "batch": 1, "kv_dtype": "BF16",
                                 "kv_cache_bytes": capacity, "bytes_per_kv_bank": capacity // 8,
                                 "evidence": "https://huggingface.co/YifeiZuo/Parallax-0.6B"},
            "assumptions": ["Proposed 32 abstract tiles, not an author chip specification.",
                            "Each address group 4g..4g+3 contains C(2g), C(2g+1), K(g), I(g).",
                            "I denotes an abstract buffer/control/IO tile; its traffic is excluded.",
                            "One full-bank K+V read per combined Q/R lane across all layers; no multicast or inter-lane cache reuse.",
                            "Dense retained KV at batch 1; allocations, padding and runtime metadata are excluded.",
                            "Unit-cost adjacent 3D mesh edges, XYZ routes; no contention or routing capacity model.",
                            "Request packets, writes, weights, activations and control transfers are excluded.",
                            "Decorative boxes span 3/4 tile pitch with 1/8 margins; dimensions are display assumptions only.",
                            "No calibrated latency, energy, thermal, fabrication or perplexity claim."],
            "formal_model": {"source": "formal/MathAI/Parallax/Hardware.lean",
                             "theorems": ["pack3_unique", "pack3_lt_volume", "axis_separated_no_shared_point"],
                             "scope": "Shared mathematical definitions; these references do not certify this Python implementation or hardware."},
            "layouts": [layout_report(name, context_length) for name in LAYOUTS],
            "finding": "All three layouts have identical costs: groups remain contiguous within rows. 3D packing alone gives no hop reduction for this mapping."}


def vertices(tile):
    lo, hi = (tuple(v / 8 for v in bound) for bound in tile.bounds_eighths)
    x, y, z = lo
    X, Y, Z = hi
    return ((x, y, z), (X, y, z), (X, Y, z), (x, Y, z),
            (x, y, Z), (X, y, Z), (X, Y, Z), (x, Y, Z))


def to_obj(name):
    _, tiles = make_layout(name)
    lines = [f"# {LABEL}", "# Unitless coordinates: tile pitch; decorative dimensions only."]
    for i, tile in enumerate(tiles):
        lines.append(f"o {tile.label}_address_{tile.address}")
        lines.extend("v " + " ".join(map(str, point)) for point in vertices(tile))
        lines.extend("f " + " ".join(str(i * 8 + v + 1) for v in face) for face in FACES)
    return "\n".join(lines) + "\n"


def to_openscad(name):
    _, tiles = make_layout(name)
    colors = {"compute": "[0.13,0.36,0.66]", "kv": "[0.05,0.58,0.45]", "control": "[0.70,0.45,0.16]"}
    lines = [f"// {LABEL}", "// Unitless: one coordinate unit = one tile pitch, not mm.",
             "// Cube sizes are display assumptions; not fabrication geometry."]
    for tile in tiles:
        lower = [v / 8 for v in tile.bounds_eighths[0]]
        lines.append(f"// {tile.label}, address {tile.address}")
        lines.append(f"color({colors[tile.role]}) translate({lower}) cube([0.75,0.75,0.75]);")
    return "\n".join(lines) + "\n"
