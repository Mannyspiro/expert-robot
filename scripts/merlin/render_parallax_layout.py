#!/usr/bin/env python3
"""Render precise plots and unitless mesh exports from the abstract layout model."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python"))
from merlin.parallax_layout import (FACES, LABEL, comparison_report, make_layout,
                                    to_obj, to_openscad, vertices)


def render(report, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Rectangle
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    colors = {"compute": "#225da8", "kv": "#0d9473", "control": "#b37429"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.labelcolor": "#354253", "text.color": "#182637"})
    fig = plt.figure(figsize=(16, 12), facecolor="#ffffff")
    gs = fig.add_gridspec(3, 2, height_ratios=(1.0, 2.3, 1.15), top=.80, bottom=.10,
                          left=.045, right=.95, hspace=.24, wspace=.13)
    fig.suptitle(LABEL, fontsize=23, fontweight="bold", y=.972)
    fig.text(.5, .932, "Fixed addresses and shared-KV mapping across three placements", ha="center", fontsize=15)
    fig.text(.5, .898, "16 query/R lanes  ·  8 KV banks  ·  8 buffer/control/IO tiles", ha="center", fontsize=12)
    fig.legend(handles=[Patch(color=c, label=l) for c, l in
                        ((colors["compute"], "C: query/R lane"), (colors["kv"], "K: shared KV bank"),
                         (colors["control"], "I: buffer/control/IO"), ("#9b234f", "Logical KV transfer"))],
               loc="upper center", bbox_to_anchor=(.5, .877), ncol=4, frameon=False)
    for i, layout in enumerate(report["layouts"]):
        grid, tiles = make_layout(layout["name"])
        if i == 0:
            ax = fig.add_subplot(gs[0, :])
            for tile in tiles:
                x = tile.cell[0]
                ax.add_patch(Rectangle((x + .125, .125), .75, .75, facecolor=colors[tile.role]))
                ax.text(x + .5, .5, tile.label, ha="center", va="center", color="white", fontsize=8)
            for transfer in layout["transfers"]:
                a, b = transfer["source_address"] + .5, transfer["destination_address"] + .5
                y = 1.55 if transfer["hops"] == 2 else 1.05
                ax.annotate("", xy=(b, y), xytext=(a, y), arrowprops={"arrowstyle": "->", "color": "#9b234f", "lw": 1.4})
                ax.text((a + b) / 2, y + .06, f"{transfer['hops']} hop" + ("s" if transfer["hops"] > 1 else ""), ha="center", fontsize=7)
            ax.set(xlim=(0, 32), ylim=(0, 1.95), yticks=[], xticks=range(0, 33, 4), xlabel="x (tile pitch)")
            ax.set_title(f"Line 32 × 1 × 1  |  {layout['metrics']['total_hops']} total hops  |  top view; arrows offset for visibility", fontsize=13, pad=16)
            for edge in ("left", "right", "top"):
                ax.spines[edge].set_visible(False)
            continue
        ax = fig.add_subplot(gs[1, i - 1], projection="3d", computed_zorder=False)
        for tile in tiles:
            points = vertices(tile)
            ax.add_collection3d(Poly3DCollection([[points[v] for v in face] for face in FACES],
                                facecolors=colors[tile.role], edgecolors="#ffffff", linewidths=.35, alpha=.62, zorder=1))
            x, y, z = (v + .5 for v in tile.cell)
            if i == 1 or tile.cell[2] == grid.nz - 1 or tile.cell[1] == 0:
                ax.text(x, y, z + .47, tile.label, fontsize=8, ha="center", color="#182637", zorder=20)
        for transfer in layout["transfers"]:
            route = [[v + .5 for v in cell] for cell in transfer["route_cells"]]
            ax.plot(*zip(*route), color="#9b234f", linewidth=1.8, alpha=.85, zorder=10)
        for axis, bound in zip((ax.xaxis, ax.yaxis, ax.zaxis), layout["dimensions"]):
            axis.set_ticks([0, bound])
        ax.set(xlim=(0, grid.nx), ylim=(0, grid.ny), zlim=(0, grid.nz),
               xlabel="x (tile pitch)", ylabel="y (tile pitch)", zlabel="z (tile pitch)")
        ax.set_box_aspect((grid.nx, grid.ny, max(grid.nz, .9)))
        ax.view_init(elev=25, azim=-65)
        ax.set_title(f"{layout['name'].title()}  {grid.nx} × {grid.ny} × {grid.nz}  |  {layout['metrics']['total_hops']} total hops", fontsize=13, pad=14)
        ax.tick_params(labelsize=8)
        ax.grid(False)
    table_ax = fig.add_subplot(gs[2, :])
    table_ax.axis("off")
    table_ax.set_title("Exact traffic accounting — one modeled full-KV sweep", fontsize=14, pad=12, loc="left")
    rows = [[r["name"].title(), str(r["metrics"]["logical_reads"]), str(r["metrics"]["total_hops"]),
             str(r["metrics"]["maximum_hops"]), f"{r['metrics']['payload_read_bytes'] / 2**20:,.4g}",
             f"{r['metrics']['byte_hops'] / 2**20:,.4g}"] for r in report["layouts"]]
    table = table_ax.table(cellText=rows, colLabels=["Placement", "KV reads", "Total hops", "Max hops", "Read MiB", "MiB × hops"],
                           cellLoc="center", bbox=[0, .37, 1, .63])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor("#dae2ec")
        cell.set_facecolor("#eaf0f7" if row == 0 else "#ffffff")
        if row == 0:
            cell.set_text_props(weight="bold")
    shape = report["checkpoint_shape"]
    table_ax.text(0, .15, f"KV capacity: {shape['kv_cache_bytes'] / 2**20:,.4g} MiB  |  28 layers · 16 Q/R · 8 KV · D128 · L{shape['context_length']} · batch 1 · BF16", fontsize=11)
    fig.text(.05, .074, "Result: no hop reduction. Each local group keeps C(2g), C(2g+1), K(g), I(g) in one row.", fontsize=12, weight="bold")
    fig.text(.05, .048, "Tile pitch is abstract; box sizes are display assumptions only. Unicast reads; no cache reuse, request/write or control traffic.", fontsize=9)
    fig.text(.05, .029, "No calibrated timing, energy, thermal, manufacturability or perplexity result. Lines show logical transfers, not routed physical wires.", fontsize=9)
    fig.savefig(output / "parallax_layouts.png", dpi=200, facecolor=fig.get_facecolor())
    fig.savefig(output / "parallax_layouts.svg", facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--context-length", type=int, default=4096)
    args = parser.parse_args()
    report = comparison_report(args.context_length)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("line", "plane", "stack"):
        (args.output_dir / f"{name}.obj").write_text(to_obj(name))
        (args.output_dir / f"{name}.scad").write_text(to_openscad(name))
    report["source_sha256"] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in (ROOT / "python/merlin/parallax_layout.py", Path(__file__))}
    (args.output_dir / "layout_comparison.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    render(report, args.output_dir)
    print(json.dumps({"output_dir": str(args.output_dir), "layouts": len(report["layouts"]),
                      "kv_cache_bytes": report["checkpoint_shape"]["kv_cache_bytes"],
                      "total_hops": [r["metrics"]["total_hops"] for r in report["layouts"]]}))


if __name__ == "__main__":
    main()
