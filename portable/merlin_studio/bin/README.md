# Optional local executables

The source-only package contains no binaries.

## Local inference server

You may supply `llama-server` on Unix or `llama-server.exe` on Windows, with the supporting libraries required by that distribution. Studio can launch it with one explicitly supplied GGUF model. See [MODEL_SETUP.md](../MODEL_SETUP.md).

The package builder does not copy an inference server or other arbitrary files from this directory. It does not download executable dependencies.

## Optional protocol core

A package built with `portable/build_portable.py --include-native` also includes `expert_robot_runtime`. That build option supports **Linux x86_64 only** and compiles the protocol sources shipped in `core/cpp`. Compatible system libraries are still required.

This executable answers the protocol health check and rejects generic requests that need model ownership. It does not contain model weights, perform inference, or provide the full Merlin research engine. Check `PACKAGE_MANIFEST.json` for whether it is included and for the recorded compiler/libc identity.
