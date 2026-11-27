#!/usr/bin/env bash
set -euo pipefail
bundle=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
version=13.8.0
flavor="${MERLIN_DEBIAN_FLAVOR:-xfce}"
case "$flavor" in
  xfce) hash=99e40aa5a1602454f28042a1199852e90c283182f29ba3736cb4f3f0fe174dae ;;
  standard) hash=fc9822eea307a45ad3ff0ab4649c977658710c681cadbf2ae5efef4347c67394 ;;
  *) echo 'Use xfce or standard for MERLIN_DEBIAN_FLAVOR.' >&2; exit 2 ;;
esac
for tool in python3 xorriso mksquashfs; do
  if ! command -v "$tool" >/dev/null; then echo "Install $tool before building." >&2; exit 2; fi
done
merlin="${MERLIN_PORTABLE_ZIP:-$bundle/Merlin_Chip_USB_Linux_x86_64.zip}"
if [[ ! -f "$merlin" ]]; then
  echo "Place Merlin_Chip_USB_Linux_x86_64.zip next to BUILD.sh or set MERLIN_PORTABLE_ZIP." >&2
  exit 2
fi
name="debian-live-$version-amd64-$flavor.iso"
if [[ -n "${MERLIN_DEBIAN_ISO:-}" ]]; then
  base=(--base "$MERLIN_DEBIAN_ISO")
else
  base=(--download "https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/$name"
        --download "https://cdimage.debian.org/cdimage/archive/$version-live/amd64/iso-hybrid/$name"
        --download "https://cdimage.debian.org/mirror/cdimage/archive/$version-live/amd64/iso-hybrid/$name")
fi
exec python3 "$bundle/build.py" "${base[@]}" --sha256 "$hash" --merlin "$merlin" \
  --voice "$bundle/Merlin_Voice.zip" --cace "$bundle/CACE.zip" --output "${1:-Merlin_AI_OS.iso}"
