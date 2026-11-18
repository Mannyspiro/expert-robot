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

## Measure maintenance clearance

Add optional `service_zones` to individual equipment items. Each zone has an `id`, a three-component `origin` relative to its owner's origin, and a positive XYZ `size`, all in metres. Moving an item moves all its zones. Enter supplier dimensions or label a synthetic assumption in the study title. The example uses assumed axis-aligned boxes for service access.

```sh
PYTHONPATH=python python -m merlin.science_visualizer layout examples/merlin/exhibit-service-layouts.json service-study
```

Open `service-study/index.html` and toggle **Show service zones** to inspect the dashed volumes. Compare the alternatives and inspect each zone's room coordinates in the table. Equipment mesh exports contain only physical items. The report lists three separate checks.

| Finding | Geometric meaning |
| --- | --- |
| Equipment intrusion | An occupied item, including the zone's owner, intersects the zone interior. Moving a second worker to a different time cannot free the occupied volume. |
| Service zone outside room | A portion of the specified service volume extends beyond the room enclosure. |
| Simultaneous service conflict | Zones belonging to two different items share interior volume. This matters if both tasks require the shared space at the same time. |

Touching faces, edges or corners passes all interior-overlap checks. Each item accepts up to eight named zones and each layout up to 64. Zone IDs must be unique within their owner. Different items may reuse the same zone ID. Overlapping zones on the same item can define portions of one task. An item without zones has no tested maintenance envelope.

Both sample layouts fit all equipment into the room without a solid collision. The tight arrangement blocks a pump panel, places part of a filter drawer envelope outside the room and shares space between two panels. The revised arrangement clears these checks with the same equipment sizes and local zone dimensions. Clear zones alone do not establish reachability, safe working conditions or compliance with service requirements.

## Draft a scientific signal wiring sheet

Supply a synthetic or approved signal diagram as component rectangles, pins and named routes. The following draws a sensor, a recorder and a display. The recorder has separate input and output pins.

```sh
python -m pip install -r requirements-merlin-wiring.txt
PYTHONPATH=python python -m merlin.science_visualizer wiring examples/merlin/lab-signal-sheet.json signal-sheet
```

The hand-drafted SVG and editable R2010 DXF use the same geometry. Open `wiring.svg` to inspect the ink-and-grid sheet. In the DXF, isolate `COMPONENTS`, `PINS`, `LABELS` or a `NET_<id>` layer. Each route is an editable polyline. The MERLIN extended data on that entity stores its net, start pin and end pin in that order. DXF modelspace uses Cartesian XY millimetres with positive Y up. SVG maps that plane into screen coordinates with positive Y down and retains the millimetre scale. Unit declarations, provenance and file hashes are captured in `receipt.json`.

* Each pin's offset is relative to the component's lower-left origin. Its location must lie on the component boundary.
* A route identifies two pins by `component.pin` and supplies all vertices in global XY millimetres. Coordinates use a one-micrometre grid. Paths must have nonzero axis-aligned segments. The supplied endpoints must coincide with the two named pins.
* Every net must connect its declared pin pairs into one graph. Separate nets cannot touch or cross on this single drawing plane. Routes cannot pass through another pin or enter a component interior.
* The sample's two polylines measure 52 mm and 62 mm along the drawn path. A real harness needs separate pinout, minimum spacing, bend radius, slack and electrical checks. This drawing represents the supplied logical connections.

`image-brief.txt` derives an illustration prompt from the validated topology. It can be supplied to a chosen image generator. The renderer runs locally without an image-provider call. To credit a reference image, include the optional `reference_image` object with `title`, `source` and `credit`. Those fields are recorded as attribution. The renderer neither retrieves the image nor extracts connections from its pixels. Keep illustrative images separate from the measured sheet.

Merlin's existing engineering-IR exporter still produces DOT and CSV views of projects and proposed routes. This drawing command takes explicit sheet placement and routes. The CAD dependency is the MIT-licensed ezdxf 1.4.4 distribution from `mozman/ezdxf`. Repeated exports on the same dependency version use fixed DXF metadata for reproducibility.

## Control an image edit with the measured drawing

In hand drafting, a construction line fixes where an edge belongs. Here the source model fixes each route and the raster guide fixes where that route lands on the image. The `wiring` command also writes `conditioning-guide.png`, `draft-controls.json`, and `image-edit-brief.txt`. The controls specify guide dimensions, a pixel scale, four labeled corner fiducials and the pixel coordinates of every pin and bend. The preferred SVG rasterizer is CairoSVG 2.8.2. An installed Inkscape command can render the guide when CairoSVG is unavailable. The controls record the selected renderer and version. Reproduce a review with the same renderer, fonts and raster environment.

Pass the guide **as the image to edit** and provide the edit brief with it. Save the candidate as a single PNG. Ask an independent reviewer to compare that candidate with the guide, tracing every named connection and checking each endpoint, bend, label and fiducial. Verify that extra connections, crossings or junction dots were not introduced. The generated illustration is a separate deliverable; the source, SVG and DXF retain the measured geometry.

Use this interface to register the review.

```sh
PYTHONPATH=python python -m merlin.science_visualizer wiring-review \
  examples/merlin/lab-signal-sheet.json signal-sheet candidate.png verdict.json reviewed
```

The verdict uses schema `merlin-drafting-verdict/1`. Supply a reviewer label, notes describing visible evidence, and `source_sha256`, `guide_sha256` and `image_sha256` for the exact input, guide PNG and candidate PNG. The first two hashes are in the control record. Use `sha256sum candidate.png` for the third. Include a `checks` object with `component_labels`, `geometry`, `fiducials`, and `no_extra_connections`. Each check takes `pass`, `fail` or `unknown`. The `nets` list must enumerate every net once. For each, supply `id`, `status`, and `connections`. Each connection records `from`, `to` and `status` for the exact source pair. Use `unknown` wherever the evidence is insufficient.

The command rebuilds the guide from the source, checks the digests, verifies the PNG, enforces the guide aspect ratio, and validates complete review coverage. All checks must pass to record an accepted illustration (exit 0). A complete review with failed or unknown observations records a rejection (exit 1). Stale or malformed evidence and missing observations return exit 2. The JSON record captures a reviewer assertion and the evidence it refers to. The command does not authenticate the reviewer, infer endpoint alignment from pixels or certify physical implementation.
