# Merlin AI OS Xenomaths USB

This is the release handoff for the completed x86-64 Debian Live Xenomaths
image. Other AI chats with GitHub access can use [the release record](release.json)
to identify the precise build, find its inputs, and verify or reconstruct it.
This is the USB edition of Merlin.

| Artifact | Use |
|---|---|
| `Merlin_AI_OS_Xenomaths_x86_64.iso` | The 4,696,309,760-byte boot image |
| `Merlin_AI_OS_Xenomaths_Recovery.zip`, Library version 1 | The byte-exact recovery data and supporting evidence |
| `Merlin_AI_OS_USB_Builder.zip`, Library version 4 | Builder source, overlay assets, and optional packs |

The ISO SHA-256 is
`66b370c1d10d58cac54fbedd35c92ec1d6bb63318e15c83ebf8669c50fb19043`.

This pull request carries the release record, verifier, exact reconstruction
layout, and a source snapshot. Access to the recovery ZIP or the exported
ISO still depends on separate file permissions. This repository does not
host those large binary files. Use ChatGPT Library to find the named ZIP
if you already have Library access, or ask the file owner for an
authorized copy. Do not rely on temporary chat or sandbox links.

## Verify an exported ISO

From this directory, run with Python 3.11 or later:

```bash
python3 restore_usb.py verify /path/to/Merlin_AI_OS_Xenomaths_x86_64.iso
```

## Reconstruct the exact image

Obtain the recovery ZIP, the exact Debian Live 13.8.0 Xfce amd64 base
image, and the exact Qwen2.5-0.5B-Instruct Q4_0 GGUF. The release record
has the filenames, SHA-256 digests, and upstream source links. A newer
Debian ISO will fail the hash check.

```bash
python3 restore_usb.py restore \
  --recovery /path/to/Merlin_AI_OS_Xenomaths_Recovery.zip \
  --base /path/to/debian-live-13.8.0-amd64-xfce.iso \
  --model /path/to/qwen2.5-0.5b-instruct-q4_0.gguf \
  --output Merlin_AI_OS_Xenomaths_x86_64.iso
```

Add `--verify-only` to check the full reconstructed stream without writing
an ISO. A regular restore needs at least 4.7 GB free for the output.
The script checks all three inputs and validates the exact output digest.

The ISO contains legacy BIOS and UEFI boot entries. For a physical USB,
use your operating system's disk-image writer on a spare drive. Writing
an ISO erases the selected drive. Device-specific compatibility is still
subject to hardware testing.

## What is in the release

The local dashboard and inference server bind to the computer booted
from the image. The virtual chip models, Xenomaths research, local voice,
thermal simulations, virtual matter printing, and worker templates are
documented in the [release notes](recovery/RELEASE_NOTES.md). A GitHub
connection lets a chat read this handoff. Booting the image or reaching its
loopback services requires a host that can run it.

The [source snapshot](source/README.md) is for reviewing the application
behavior. The complete builder and its assets are in the builder ZIP.
The source snapshot does not substitute for the exact recovery archive.
