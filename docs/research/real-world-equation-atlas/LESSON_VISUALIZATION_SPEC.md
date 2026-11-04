# Lesson visualization specification

## General layout
Use one canonical object at the centre and place its representations around it. Connect frames with directional arrows whose labels state the map type: coordinate change, active transformation, projection, embedding, measurement, or basis change.

## Required visual layers
- **Object layer:** what exists in the model independently of coordinates.
- **Frame layer:** named coordinate/representation frames, dimensions, units, and conventions.
- **Operator layer:** transformations, differential operators, graph operators, or basis changes.
- **Invariant layer:** quantities proven or numerically checked to remain unchanged under named transformations.
- **Evidence layer:** source, assumptions, test result, tolerance, and evidence status.
- **Loss layer:** visible warning when projection/discretization removes information.

## Recommended lesson views
1. Garden: rectangle in physical x-y coordinates; area constraint and perimeter objective; animate aspect ratio while area stays fixed.
2. Heat: continuous temperature curve -> grid samples -> state vector -> Fourier modes; show resolution loss and diffusion smoothing.
3. Signal: time waveform -> sampled points -> spectrum; demonstrate aliasing by overlaying distinct signals with identical samples.
4. Robot: world/body/sensor frames with axes and rigid transforms; preserve a point's physical location while changing coordinates.
5. Graph: network nodes -> adjacency matrix -> Laplacian -> eigenmodes; distinguish vertex relabeling from changing graph topology.

## Accessibility and learning constraints
Keep beginner explanations short, introduce no more than two new ideas at once, include units on axes, and do not rely on color alone to distinguish map types or evidence states.
