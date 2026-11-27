# A Lantern in the Violet Woods

An 18-second forest scene for *After the Grid Went Violet*. The camera
follows a shale footpath through cedars and ferns toward an old violet
relay. The editable Blender scene contains the seeded forest, three
keyframed camera shots, the mist compositor, lantern lights, and drifting
pollen. The builder also supports a blue-hour lighting preset and
different forest seeds.

The audio mix brings together Kokoro Heart narration, wind and foliage,
birdlike synthetic calls, footsteps, a relay chime, and an original score.
The mix lowers the score during narration. All sound effects were
synthesized for the fictional scene. Stems use
48 kHz stereo PCM.

## Tuning and evidence

The score uses 12-tone equal temperament with **C5 = 528 Hz**,
equivalent to **A4 ≈ 443.99 Hz**. There is also a score-only version
using **A4 = 440 Hz**. Both scores use the same notes, timings and
synthesis. Listen to the alternatives as an artistic comparison.

The nine-person 2018 study of such music cannot establish a
general biological advantage for 528 Hz. A later meditation
trial bundled 528 Hz with other sounds and a meditation practice,
so it cannot isolate the effect of 528 Hz. The scene makes no
health claim. [2018 study](https://file.scirp.org/Html/2-8204397_87146.htm)
[Combined intervention trial](https://pmc.ncbi.nlm.nih.gov/articles/PMC13539022/)

## Reproduce or change the scene

Use Blender 4.3+, FFmpeg, Python 3.11+, NumPy, SciPy and
kokoro-onnx. Use the Kokoro v1.0 quantized model and voice pack from
[its model release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0).
The kit includes finished stems so regeneration is optional.

```bash
tool=tools/merlin_studio/forest_film
mkdir -p frames
blender -b --factory-startup --python-exit-code 1 \
  --python "$tool/build_forest.py" -- woods.blend frames --look dawn
blender -b woods.blend -o "$PWD/frames/frame-####" -F PNG -a
python3 "$tool/sound_forest.py" /path/to/kokoro-model-files sound
python3 "$tool/assemble_forest.py" frames sound forest.mp4
```

Use an installed serif font with `--font` to add the title in the
assembly step. The scene renders 144 source frames at 640 × 360 and
8 frames per second. The editing tool denoises and blends between
those frames separately inside each six-second shot, then exports
960 × 540 at 24 frames per second with optional English subtitles.
The native Blender frames and the final delivery frames have
different rates. The kit preserves the shot data and the scene so
a producer can render a higher-sample version later.

[Merlin Ideonomy](Ideonomy.json) records the geometry, render and audio
combinations considered. The pinned local research module ran with the
private Merlin bridge disconnected. The full OS image was not booted.
