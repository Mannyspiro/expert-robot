# Scientific Visualization Designer

Merlin can consult a creative UI and scientific-visualization specialist or render a local data series. The specialist uses the same persona packet and qualified loopback model adapter as the research council. Select it explicitly for one design consultation. The six-person default council keeps its existing call budget.

From the repository root, prepare a design brief, or request ideas from an already-qualified local model.

```sh
PYTHONPATH=python python -m merlin.science_visualizer brief 'Design two keyboard-accessible views of an irregular time series. Name a visual analogy and a case where it fails.'
PYTHONPATH=python python -m merlin.science_visualizer imagine 'Draft a small HTML interface for exploring a cooling curve. Explain how a reader can recover exact values.'
```

The brief works offline. The imagination command prints the model response for review. Code suggestions remain text. Rendering uses a fixed, local implementation and accepts only data.

## Render a movie and accessible viewer

The tested environment used Python 3.12, Matplotlib 3.10.8 and an FFmpeg executable with the libx264 encoder. Only the render command needs Matplotlib and FFmpeg.

```sh
PYTHONPATH=python python -m merlin.science_visualizer render examples/merlin/synthetic-cooling.json cooling-view
```

Open `cooling-view/index.html` to play, pause or seek the H.264 movie and inspect an HTML table of exact input values. The receipt binds the source bytes and generated artifacts by SHA-256. Existing destinations are preserved.

The input contains printable strings for the title, source, provenance, time unit, quantity and value unit, plus 2–300 pairs of strictly increasing times and finite scalar values. Use `synthetic`, `simulation` or `measurement` for provenance. The caller supplies that classification. Include the model or collection method in the source. Check the example for exact field names.

Each frame adds one plotted observation at its original time coordinate on fixed axes. Playback runs at four observations per second even when the sampling interval varies. The time label and table preserve those intervals. The renderer rejects missing values and repeated times so a user can choose a scientifically defensible handling policy before rendering. A video summarizes supplied observations and inherits their measurement limits.

## Compare spatial concepts

The designer can sketch exhibit layouts, propose sightline and circulation hypotheses, and explain how to test them. The local geometry command compares axis-aligned equipment boxes in a rectangular room. It produces a rotatable 3D viewer, per-alternative Wavefront OBJ models and a machine-readable critique.

```sh
PYTHONPATH=python python -m merlin.science_visualizer brief 'Imagine two spatial arrangements for the wave exhibit and name the trade-offs.'
PYTHONPATH=python python -m merlin.science_visualizer layout examples/merlin/exhibit-layouts.json exhibit-study
```

Open `exhibit-study/index.html` locally. Choose an alternative and adjust the angle by keyboard or pointer. The table gives exact origins and sizes in metres. Download a mesh using the link beside the view. When importing OBJ, select metres and a positive Z up axis. OBJ has no standard unit field.

To revise a scheme, edit an item's XYZ `origin` or `size` in the source JSON and render to a new directory. Room dimensions follow the same XYZ order. The file supports up to eight named alternatives, each containing 1–64 named volumes. Numbers must be representable on a one-micrometre grid within 10,000 metres of the coordinate origin. Use positive sizes; object origins can be negative so crossing an enclosure is reported as a finding.

The review checks each object against all six room boundaries and each pair for strictly positive overlap on all three axes. Objects can touch at faces, edges and corners. At least one coordinate outside the enclosure produces a bounds finding. All comparisons use integer micrometres. The example's central island has one intersecting pair and one item crossing the room boundary; the split gallery preserves the inventory and clears both findings. The source and exported meshes are bound by SHA-256 digests in `critique.json`.

These checks establish geometric fit for the supplied boxes. Clearances, accessibility, load paths, material performance, sightlines, code compliance and suitability for construction require additional evidence.

For a native editable model, run the companion exporter with a Python interpreter that can import FreeCAD, using a one-based layout number. For example, on the tested Linux install:

```sh
PYTHONPATH=python:/usr/lib/freecad/lib /usr/bin/python3 scripts/merlin/export_exhibit_freecad.py examples/merlin/exhibit-layouts.json 2 split-gallery.FCStd
```

This writes each equipment item as a named parametric box and converts the study's metres to FreeCAD millimetres. Reopen the document to change length, width, height or placement. The room dimensions and critique remain in the source study and its review.
