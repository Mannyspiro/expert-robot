# Merlin Flight Deck with Xenomaths research

Boot the image on an x86-64 PC. Use the Xfce Network menu to join Wi-Fi, or run `nmcli --ask device wifi connect "YOUR_SSID"` from the live desktop terminal. NetworkManager handles credentials. Merlin reads device state and never sees the password. The dashboard is at `http://127.0.0.1:8770/`.

Qwen and the saved Kokoro Heart voice are included. If a build has omitted the 92 MB voice model but retains the voice pack, Merlin downloads the exact pinned model on first use or when you click “Check voice dependency.” It verifies the byte count and SHA-256 before installing the file to the local cache. The image uses Debian's Wi-Fi drivers and firmware. Compatibility with a specific wireless chipset requires a device test.

## Specialized workers and tools

Every research cycle creates routing, physics and material-report workers. The dashboard can create more named tools from these same reviewed templates. Workers use Python and open-source scientific components. A generated tool must match reference output and reject a missing-input control before it enters the worker library. Download workers as Python files and run them with a research receipt as the argument. Templates and execution are local. New specialties and arbitrary downloaded code are outside this factory.

## Autonomous research cycle

The first run starts about 12 seconds after launch. When the service stays running, it checks every 15 minutes whether 24 hours have passed since the last completed run. The dashboard can trigger a round immediately. No internet connection is needed for the experiments. The cycle attempts to retrieve a fixed public research reference and records errors if it cannot reach the source. Merlin explains the measured results in a local chat turn. Explanations do not control promotion.

- **Xenomaths and chips.** The Ideonomy catalogue enumerates 48 combinations of four-tier layouts, bank placements and reducers, replaying 169 tensor dimensions from the Qwen checkpoint. A fixed ranking balances data travel, a lower-bound routing proxy and peak heat. A separate test compares the selected geometry against the baseline on unfamiliar workloads. Success positions are rendered as nominal CAD solids. This lane produces model designs and never substitutes those solids for real circuit implementation.
- **Physics loop.** The experimentally selected solver precomputes fixed face coefficients. Promotion requires exact full field histories and a median speed gain of at least 5% on all nine discovery and shifted verification cases. Eligible settings are tied to the host fingerprint and change the code path used by the dashboard. The reference solver remains the fallback.
- **Matter printer and replicator.** Four equal-inventory designs use 48 high-conductivity voxels each. The printer scans the selected coupon using two synthetic channels and emits two virtual copies. One deliberately dropped packet is counted and retried. Independent post-print scans compare materials and occupancy. The coupon's thermal ranking and replica verification are separate evidence.
- **Persistence.** Cycle data is under `/var/lib/merlin-ai-os/xenomaths` in the live image. Without Debian Live persistence, state lasts until shutdown. For cross-boot storage, configure a Debian Live persistence volume and include `/var/lib/merlin-ai-os` in its `persistence.conf`. Boot with the `persistence` kernel option. OS Wi-Fi profile persistence is separate.

The study changes a verified runtime setting. It does not rewrite model weights or update the host firmware. Virtual conductivity, scanners, and thermal values are simulation parameters without hardware calibration.

- [NetworkManager Wi-Fi commands](https://networkmanager.pages.freedesktop.org/NetworkManager/NetworkManager/nmcli.html)
- [Debian live persistence](https://manpages.debian.org/unstable/live-boot-doc/persistence.conf.5.en.html)
- [Frigo and Strumpen’s stencil study](https://www.fftw.org/~athena/papers/ics05.pdf)

## Restore the exact ISO

Use the original Debian Live 13.8 Xfce amd64 ISO and the earlier Merlin Chip USB ZIP. The restore script verifies the original files and the output SHA-256.

```bash
python3 Restore_ISO.py --base /path/to/debian-live-13.8.0-amd64-xfce.iso \
  --model /path/to/Merlin_Chip_USB_Linux_x86_64.zip
```

[Debian Live Xfce ISO](https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/debian-live-13.8.0-amd64-xfce.iso)
