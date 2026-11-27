# Merlin dialogue animation tools

See [Xenomaths motion](XENOMOTION.md) for sparse camera keys and timed blinks on this dialogue.
See [frame reuse](frame_reuse/README.md) for lossless caching and direct comparison of held and moving shots.

This prototype extends *After the Grid Went Violet*. The render lab
established the CPU pipeline. The animation study addresses the static
portraits during dialogue in the existing pilot.

[Ideonomy.json](Ideonomy.json) records the released Merlin research
module's enumeration of eight primitives. It considered 84 distinct
pairs and triples and retained 11 compatible combinations within the
declared cost cap. Priority scores are judgments about the pilot on four
weighted criteria. The original ISO was not booted for this study.

| Tool proposal | Priority | Status |
|---|---:|---|
| Dialogue exposure compiler | 100/100 | Implemented and run on the original cast dialogue |
| Exact match-cut verifier | 85/100 | Implemented and checked against a matching and an altered pilot cut |
| Exposure hold optimizer | 75/100 | One- and two-frame holds compared. Automatic artistic selection remains future work |
| Layered camera movement | 72.5/100 | Deferred until foreground and background plates are available |

The dialogue tool runs Rhubarb on one speaker and transcript line at a
time. An exact rational timeline samples the center of each output frame.
The exposure CSV uses zero-based frame numbers and exclusive end frames.
Actor and line identity remain explicit. Rest cues and speaker changes
take effect immediately, including when the optional two-frame hold is
active. The CSV can be used to plan mouth drawings in an exposure sheet.
The demonstration image rig was fitted to the pilot portraits and has
editable anchors, angles, colors and crop bounds. It previews lip poses
on a still illustration at 720p. Facial acting and phoneme accuracy need
separate visual review before release.

The small match-cut tool decodes and hashes both clips' boundary RGB
frames. It returns exit 2 for different boundary images. Use a lossless
intermediate for exact matches, since export compression or color
conversion can change decoded pixels. This gate checks a cut that was
intended to match. It does not rate unrelated edits.

## Pilot comparison

Rhubarb returned 320 mouth cues across seven dialogue lines. The 24 fps
sheet contains 327 exposures on ones and 294 on twos. Twos reduced the
exposure rows by 10.1% and changed the mouth shape on 150 of 1,494
frames. Speaker, line and rest-cue boundaries were preserved. The
demonstration uses ones to preserve the imported cue changes. See
[Evidence.json](Evidence.json) for input identities and both cut checks.

## Reproduce

Install Python 3.11+, Pillow, FFmpeg and Rhubarb 1.14.0. Run these
examples from the repository root. Use the art, WAV, and timing JSON
from the pilot creator kit.

```bash
tool=tools/merlin_studio/animation
python3 "$tool/ideonomy.py"
python3 "$tool/make_cues.py" /path/to/rhubarb pilot.wav timing.json cues
python3 "$tool/exposure.py" timing.json cues opening-24fps.csv \
  --duration 62.35 --start 2.5 --end 19.5
python3 "$tool/preview.py" Iona_and_Ren_Character_Art.png "$tool/pilot_rig.json" \
  pilot.wav opening-24fps.csv speech-test.mp4 --audio-start 2.5
python3 "$tool/match_cut.py" outgoing.mkv incoming.mkv
```

- [Rhubarb Lip Sync JSON cue format](https://github.com/DanielSWolf/rhubarb-lip-sync#json-format-json)
- [OpenToonz exposure workflow](https://opentoonz.readthedocs.io/en/latest/working_in_xsheet.html)
- [Blender Dope Sheet](https://docs.blender.org/manual/en/4.3/editors/dope_sheet/introduction.html)
