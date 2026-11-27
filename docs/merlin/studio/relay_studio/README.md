# Violet Relay Studio

An original browser recording studio for *After the Grid Went Violet*.
The supplied project contains a new 42-second chamber arrangement of
**Two Ways Out**, keeping the existing vocal melody and synthetic voice.
FluidSynth renders seven sampled instrument tracks from the TimGM6mb
SoundFont. Grand piano, chamber strings, nylon guitar, cello, celesta,
electric bass and drums have separate tracks. The original synthetic
vocal is the eighth track. The SoundFont bank itself is not bundled.

## Open the studio

Unzip the complete kit, then serve its app directory on localhost.

```bash
python3 -m http.server 8778 --bind 127.0.0.1 --directory app
```

Open **http://127.0.0.1:8778**, select **Load demo**, then press **Play**.
Audio editing and recording run locally inside the browser. Only the
local server supplies the app and included project assets.

| Work | Implemented |
|---|---|
| Record and import | Microphone takes, playback during recording, audio files, editable track offset |
| Arrange | Waveforms, click to seek, non-destructive clip start and end, name and position |
| Play instruments | Four synthesized patches. Enter MIDI note numbers and rests, then render an editable-duration pattern as a take |
| Mix | Gain, stereo pan, mute/solo, presence EQ, master level and peak meter |
| Save | Browser-local session storing the original audio blobs and edit settings |
| Export | 48 kHz stereo PCM16 WAV. Reports sample clipping |

The browser build handles up to 32 tracks, one editable clip per track,
and WAV export up to ten minutes. The saved session is scoped to the
same browser and localhost address. The prototype lacks a full MIDI
piano roll, plugin hosting and calibrated hardware monitoring. The
browser microphone practice run used a virtual device, so physical input
and its latency remain unverified.

## Virtual DSP session

The [modeled layouts](Chip_Study.json) compare one, four and eight
virtual processing lanes, three block sizes, and sessions with 8, 24
and 48 stereo tracks. The declared comparison prefers 128 samples at
48 kHz, a modeled 24 MHz clock, 128 KiB SRAM capacity, and no more than
75% peak callback budget. The four-lane design is the lowest symbolic
cost candidate meeting all of those conditions. At 48 tracks it uses
68.64% of the callback cycle budget and 104 KiB of modeled scratch
space. Its 128-frame buffer spans 2.67 ms. Interface, converter and
OS delays make total end-to-end latency a different quantity.

The cycle costs are assigned virtual slots rather than hardware
measurements. At 32 instead of 24 virtual slots per track sample,
the four-lane design would need 87.84% of the same budget and fail the
75% threshold. The eight-lane candidate reserves more compute headroom.

The fixed-point mixer processed all 2,016,000 frames of eight stems
with unity and varied coefficients. One-, four-, and eight-lane sums
matched the integer reference. The [session simulation](Virtual_Session_Evidence.json)
also generated a virtual microphone take, arranged and processed it
alongside the instrument stems, applied a presence effect and panning,
and produced stereo PCM through the virtual mixer. Muting the virtual
take changed the output. The browser app uses Web Audio for actual
playback. The chip model is a separate digital simulation.

Merlin's release-pinned Ideonomy module ran locally because the
private host bridge was disconnected. The ISO was not booted.

## Sources

- [FluidSynth SoundFont API](https://www.fluidsynth.org/api/Introduction.html)
- [TimGM6mb SoundFont package](https://packages.debian.org/trixie/timgm6mb-soundfont)
- [Ardour recording and track modes](https://manual.ardour.org/working-with-tracks/track-modes/)
