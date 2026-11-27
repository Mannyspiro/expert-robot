# Merlin audio for After the Grid Went Violet

**Two Ways Out** is an original 42-second synth score in D minor,
at 96 BPM. Its parts are an instrumental WAV, a synthetic vocal stem,
and the full stereo mix. The source includes an editable note plan,
intended lyric lines, and a standard MIDI file for the vocal melody.
The six original effects cover the relay latch, cooling surge,
warning pulses, relay rumble, stabilized chime, and violet transition.

## Merlin Ideonomy

[Ideonomy.json](Ideonomy.json) records the release module's bounded
enumeration of 84 pair and triple combinations. Fourteen were eligible.
The rank uses explicit judgments about readiness, vowel and lyric
clarity, edit control and reproducibility.

| Approach | Ready-now score | Lyric-focused score | Status |
|---|---:|---:|---|
| Local formant singing and procedural Foley | 90 | 75 | Rendered the theme and six effects |
| OpenUtau with a documented singer bank | 70 | 85 | First candidate for a lyric-focused comparison |
| OpenUtau and a compatible DiffSinger bank | 55 | 80 | Candidate with added model and setup requirements |

The current vocal uses harmonic formant synthesis, vowel transitions,
pitch vibrato, and approximate consonant noise. It gives the melody an
electronic singing timbre. The recorded words are approximate and need
a compatible voicebank and listening review if clear lyrics are
required. Yamaha VOCALOID and third-party vocal recordings were not used
in this render. The ranking is a production judgment, not a listening
test or a statement about a particular bank's terms.

## Run and edit

From the repo root, with Python 3.11+, NumPy and SciPy:

```bash
tool=tools/merlin_studio/audio
python3 "$tool/audio_ideonomy.py"
python3 "$tool/synth_relay.py" "$tool/relay_score.json" rendered-score
python3 "$tool/score_midi.py" "$tool/relay_score.json" vocal-melody.mid
```

The mix and stems have synchronized lengths and gains. Use the
instrumental stem under dialogue. The cue names describe fictional
effects and do not represent recordings of actual equipment.

## References

- [OpenUtau editor and project](https://github.com/openutau/OpenUtau)
- [OpenVPI DiffSinger](https://github.com/openvpi/DiffSinger)
- [Yamaha's VOCALOID product](https://www.vocaloid.com/en/)
