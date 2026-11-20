"""Export one validated Merlin exhibit layout as editable FreeCAD box features."""
import argparse
import os
from pathlib import Path
import tempfile

from merlin.spatial_layout import read_study


def export(source, index, destination):
    import FreeCAD as cad

    project, _ = read_study(source)
    if not 1 <= index <= len(project["layouts"]):
        raise ValueError("layout index outside project")
    if destination.suffix.lower() != ".fcstd":
        raise ValueError("use an .FCStd destination")
    layout = project["layouts"][index - 1]
    doc = cad.newDocument("Exhibit")
    try:
        doc.Label = layout["name"]
        for item in layout["items"]:
            feature = doc.addObject("Part::Box", "ExhibitItem")
            feature.Label = item["id"]
            feature.Length, feature.Width, feature.Height = [float(v) * 1000 for v in item["size"]]
            feature.Placement.Base = cad.Vector(*(float(v) * 1000 for v in item["origin"]))
        doc.recompute()
        with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
            staged = Path(tmp) / "layout.FCStd"
            doc.saveAs(str(staged))
            os.link(staged, destination)
    finally:
        cad.closeDocument(doc.Name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("layout_index", type=int, help="one-based alternative number")
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        export(args.source, args.layout_index, args.destination)
    except (OSError, ValueError, ImportError, RuntimeError) as error:
        parser.exit(2, f"{error}\n")
