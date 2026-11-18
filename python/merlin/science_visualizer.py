"""Local scientific visualization specialist and sample-indexed movie renderer."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import tempfile

from .council import build_deliberation_packets
from .council_runtime import run_local_council


def load_series(path):
    with path.open("rb") as handle:
        raw = handle.read(131073)
    if len(raw) > 131072:
        raise ValueError("input exceeds 128 KiB")
    series = json.loads(raw)
    fields = ("title", "source", "provenance", "time_unit", "quantity", "unit")
    if not isinstance(series, dict):
        raise ValueError("expected a series object")
    for field in fields:
        value = series.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 160 or not value.isprintable():
            raise ValueError(f"invalid {field}")
    if series["provenance"] not in {"synthetic", "simulation", "measurement"}:
        raise ValueError("unknown provenance")
    rows = series.get("samples")
    if not isinstance(rows, list) or not 2 <= len(rows) <= 300:
        raise ValueError("expected 2 to 300 samples")
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("each sample must contain time and value")
        if any(type(n) not in (int, float) or abs(n) > 1e100 or not math.isfinite(n) for n in row):
            raise ValueError("each coordinate must be a finite number within 1e100")
        if any(type(n) is int and int(float(n)) != n for n in row):
            raise ValueError("integer exceeds exact plotting precision")
    if any(t2 <= t1 for (t1, _), (t2, _) in zip(rows, rows[1:])):
        raise ValueError("time must strictly increase")
    return series, hashlib.sha256(raw).hexdigest()


def render_video(series, path):
    import matplotlib
    from matplotlib.animation import FFMpegWriter
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    times, values = zip(*series["samples"])
    with matplotlib.rc_context({"text.parse_math": False, "text.usetex": False}):
        figure = Figure(figsize=(9.6, 5.4), dpi=100, facecolor="#f7f6ef")
        FigureCanvasAgg(figure)
        axes = figure.add_axes([0.14, 0.21, 0.81, 0.58], facecolor="#f7f6ef")
        figure.text(0.14, 0.91, series["title"], fontsize=16, color="#172d34", wrap=True)
        status = figure.text(0.14, 0.84, "", fontsize=10, color="#33545c")
        figure.text(0.14, 0.055, "One frame per sample  •  Equal playback time per observation",
                    fontsize=9, color="#33545c")
        axes.set_xlabel(f'Time ({series["time_unit"]})')
        axes.set_ylabel(f'{series["quantity"]} ({series["unit"]})')
        axes.grid(axis="y", alpha=0.22)
        axes.spines[["top", "right"]].set_visible(False)
        axes.update_datalim(list(zip(times, values)))
        axes.autoscale_view()
        axes.set_autoscale_on(False)
        history, = axes.plot([], [], "o", color="#277785", markersize=5)
        current, = axes.plot([], [], "o", color="#a04120", markersize=9)
        writer = FFMpegWriter(fps=4, codec="libx264", extra_args=["-threads", "1", "-pix_fmt", "yuv420p",
                                                                   "-movflags", "+faststart"])
        with writer.saving(figure, str(path), dpi=100):
            for index, (t, value) in enumerate(zip(times, values), 1):
                history.set_data(times[:index], values[:index])
                current.set_data([t], [value])
                status.set_text(f'{series["provenance"].upper()}  /  {index} of {len(times)}'
                                f'     t = {t} {series["time_unit"]}     {value} {series["unit"]}')
                writer.grab_frame()


def viewer(series):
    labels = {k: html.escape(v) for k, v in series.items() if isinstance(v, str)}
    rows = "".join(f"<tr><td>{t}</td><td>{value}</td></tr>" for t, value in series["samples"])
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{labels['title']}</title>
<style>
*{{box-sizing:border-box}}body{{margin:auto;max-width:62rem;padding:clamp(1rem,4vw,3.5rem);
font:1rem/1.55 system-ui,sans-serif;color:#172d34;background:#f7f6ef}}h1{{font:2.3rem/1.12 Georgia,serif}}
video{{width:100%;height:auto;background:#172d34}}summary{{cursor:pointer;font-weight:bold;padding:.8rem 0}}
table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}
td,th{{text-align:left;border-bottom:1px solid #b3c7c6;padding:.4rem}}a{{color:#175661}}
</style><main><p>{labels['provenance'].upper()} · {len(series['samples'])} samples</p>
<h1>{labels['title']}</h1><p>{labels['source']}</p>
<video controls playsinline preload="metadata" aria-label="{labels['title']}"><source src="animation.mp4"
type="video/mp4"></video><p>Each frame reveals one recorded value. Playback advances one sample at a time.
The horizontal position shows the original time.</p>
<details><summary>Inspect sample values</summary><table><thead><tr><th scope="col">Time ({labels['time_unit']})</th>
<th scope="col">{labels['quantity']} ({labels['unit']})</th></tr></thead><tbody>{rows}</tbody></table></details>
<p><a href="receipt.json">View rendering receipt</a></p></main></html>
"""


def render(source, destination):
    series, digest = load_series(source)
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        stage = Path(tmp)
        render_video(series, stage / "animation.mp4")
        (stage / "index.html").write_text(viewer(series), encoding="utf-8")
        hashes = {name: hashlib.sha256((stage / name).read_bytes()).hexdigest()
                  for name in ("animation.mp4", "index.html")}
        receipt = {"schema": "merlin-science-movie/1", "input_sha256": digest,
                   "provenance": series["provenance"], "source": series["source"],
                   "frames": len(series["samples"]), "fps": 4, "playback": "one frame per sample",
                   "render_sha256": hashes}
        (stage / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        destination.mkdir()
        try:
            for name in ("animation.mp4", "index.html", "receipt.json"):
                (stage / name).rename(destination / name)
        except OSError:
            shutil.rmtree(destination)
            raise
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("brief", "imagine"):
        commands.add_parser(name).add_argument("question")
    movie = commands.add_parser("render")
    movie.add_argument("source", type=Path)
    movie.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "render":
            result = render(args.source, args.destination)
        elif args.command == "brief":
            result = build_deliberation_packets(args.question, visual_specialist_only=True)[0]
        else:
            result = run_local_council(args.question, visual_specialist_only=True)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
