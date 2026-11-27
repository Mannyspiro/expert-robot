# Merlin anime and technical video production

**After the Grid Went Violet** is an original science-fiction anime about
Iona Vale and Ren Sato, two underground relay engineers. A failing
compute tile gives them a reason to test an idea under pressure. Iona
sets up the control. Ren proposes a competing explanation and reads the
instruments. The pilot is titled *Two Ways Out*. Its thermal experiment
uses an explicitly ideal, steady-state model.

| Stage | Inputs and work | Evidence to preserve |
|---|---|---|
| Research | Baseline, alternatives, falsifier, exact upstream sources | Evidence ledger, candidate results, counterexamples |
| Story | Premise, script, storyboard, technical claims with source IDs | Editable script, claim list, writing review |
| Cast | Fictional adults with locked palettes and facial landmarks, synthetic voices with pinned voice IDs | Turnarounds, expression sheets, voice profile, pronunciation and character continuity checks |
| Worlds | Blender staging and camera, original image textures, depth and normals for controlled 2D renders | Scene file, texture hashes, shot transforms, color settings |
| Technical inserts | SVG from CAD/EDA, solver output with units, Lean theorem where useful | Source files, solver configuration, Lean toolchain, build and electrical-check receipts |
| Review | Watch cuts in order, compare matching frames and voices, inspect subtitles and technical UI | Independent rubric, reason and replacement ID for failed shots |
| Master | Draft from short clips, then normalize audio/video and package chapters | Cut manifest, chapters, captions, validation and master hashes |

Keep the established Kokoro Heart voice for Merlin narration. The pilot
uses Heart for Iona and Michael for Ren, with separate pace and delivery.
Keep stable character ID, voice ID, approved palette, costume and
facial landmarks across chapters. Frame composition, pose and depth
guide generated backgrounds or paintovers. Use rendered schematic
source for connection topology and legible values. Preserve CAD units
and check the netlist separately from its illustration.

The two-hour production outline has twelve ten-minute chapters. See the
[season bible](SEASON_ONE.md) for character arcs and episode beats. Each chapter needs a distinct question, visual beat and result. Render
individual scenes as resumable frame sequences. Set a render budget
using measured seconds per frame from at least one character shot and
one effects shot. Use the outgoing last frame as an input to the next
shot when an edit calls for a match. Intentional cuts have their own
handoffs. Keep shaders, output transforms and exposure pinned. Cache
reviewed shots by the hashes of their source scene, assets and settings.

For release, use a reviewer other than the writer for the script,
animation and on-screen UI. All three scores must exceed **8/10**.
Reject any unresolved scientific error, broken continuity or misleading
technical claim. Revise and review the affected shot again. A technical
pass and an editorial decision are separate receipts. A section plan
or an internally reviewed animatic is a development artifact.

Start with [the storyboard and two-hour outline](../../../tools/merlin_studio/pilot.json).
Run the [chapter validation tool](../../../tools/merlin_studio/series.py)
against that outline. For an edited series, add a manifest of prepared
chapter MP4s and review receipts, then use the tool to verify compatible
streams and assemble an approved master. Use the pinned Mathlib
toolchain and run the pilot theorem with
`lake env lean ../tools/merlin_studio/ThermalPaths.lean`
from the repository's `formal` directory.

The [pilot evidence](Pilot_Evidence.json) records the actual OpenBot
connection, the model's failed research answer, arithmetic verification,
media checks, and outstanding Lean and editorial checks.

- [Render Lab workstation, open-source stack and measured layout](renderlab/README.md)
- [Dialogue animation tools and Ideonomy study](animation/README.md)

## Open-source references

- [Blender background rendering](https://docs.blender.org/manual/en/latest/advanced/command_line/render.html)
- [FFmpeg concat demuxer](https://ffmpeg.org/ffmpeg-formats.html#concat)
- [KiCad CLI schematic ERC and SVG](https://docs.kicad.org/9.0/en/cli/cli.html)
- [Lean Mathlib](https://github.com/leanprover-community/mathlib4)

## OpenBot crew

The integration targets [pmwasim/OpenBot](https://github.com/pmwasim/OpenBot)
at the pinned revision in [crew.json](../../../tools/merlin_studio/crew.json).
Merlin orchestrates nine roles through separate named profiles. Use a
dedicated local project workspace and a loopback OpenBot daemon. On the
verified USB runtime, Merlin's local provider can serve OpenBot. After
starting Merlin once to unpack its runtime, run the following using the
actual extracted bundle and cache paths.

```bash
"$merlin_runtime/python/bin/python3.12" -B \
  tools/merlin_studio/iso_provider.py "$merlin_usb_bundle" "$merlin_runtime"
```

In another terminal, from the pinned OpenBot checkout, start the daemon.

```bash
HOST=127.0.0.1 OPENBOT_MODEL_PROTOCOL=chat-completions \
  OPENBOT_MODEL_URL=http://127.0.0.1:18961 node server.mjs
```

From this repository, register the crew and then dispatch research.

```bash
python3 tools/merlin_studio/openbot_crew.py --workspace "$episode_workspace"
python3 tools/merlin_studio/openbot_crew.py --workspace "$episode_workspace" \
  --job research --task "Propose one control and one falsifier for the heat model."
```

To dispatch a dependent role, pass `--receipts` with a JSON object mapping
required job IDs to reviewed JSON receipts inside the workspace. Each
receipt records its job ID and an explicit approval. An OpenBot result is
a draft proposal. The director reviews outputs and launches production
tools such as Blender, the narrator and FFmpeg using their checked
inputs. The independent critic reviews the finished cut. The bundled
0.5B model is a bounded local inference baseline. Longer prompts and
open-ended production tasks need a separately qualified model.
