# Xenomaths motion for the Merlin anime

Edit a few camera poses and acting events in
[pilot_motion.json](../../../../tools/merlin_studio/animation/pilot_motion.json).
The compiler generates the intervening frames and the preview tool uses
the existing mouth-cue sheet and recording. The development clip uses
five camera keys and four timed blinks over three shots and 408 frames.

## What the maths does

- **N-ality.** Keep the camera, blink envelopes and dialogue exposure on
  separate axes. Changing the camera or a blink leaves the timing of the
  dialogue unchanged. Camera center and width travel together inside a shot.
- **Simplex.** Blend adjacent camera keys with nonnegative weights that
  sum to one. For normalized shot time t, the right weight is
  s = 3t² − 2t³ and the left weight is 1 − s.
- **Continuum.** Camera bounds and protected-face margins are affine
  inequalities in center and width. A blend of two valid keys stays
  valid for the entire segment, including subframes. The compiler
  checks keys using exact rational arithmetic.
- **Fuzzy values.** Eyelid closure is an intensity from fully open to
  fully closed, used to blend a hand-positioned layer. It is separate
  from the binary framing checks.

The artist draws a protected rectangle around the face in art pixels,
then enters the camera center, width and desired frame. Set
`"autoframe": true` on a shot to move invalid keys into the allowed
region and record both requested and applied positions. A face guard
that cannot fit within the art and margin still raises an error.
Separate shots can cut between different camera views.

Each eye overlay and protected rectangle is specific to the source
illustration. The sample animates camera and stylized blinks on
the existing 2D art. Production animation needs reviewed poses and
expression changes. The [evidence](Xenomotion_Evidence.json) records
the visual scope, input checks, and verified audio match.

## Run the sample

Use Python 3.11+, Pillow and FFmpeg. From the repository root, point the
commands at the artwork, WAV and opening exposure sheet included in the
dialogue kit.

```bash
tool=tools/merlin_studio/animation
python3 "$tool/xenomotion.py" "$tool/pilot_motion.json" compiled-motion.json
python3 "$tool/xenomotion_preview.py" "$tool/pilot_motion.json" \
  "$tool/pilot_rig.json" Iona_and_Ren_Character_Art.png pilot.wav \
  Opening_Exposure.csv Xenomaths_Motion_Test.mp4
```

The crop trajectory uses ordinary animation interpolation applied
through Merlin's Xenomaths lenses. See
[Blender's F-curve interpolation](https://docs.blender.org/manual/en/4.3/editors/graph_editor/fcurves/properties.html)
for artist controls that use related easing concepts.
