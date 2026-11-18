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
