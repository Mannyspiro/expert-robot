# Merlin Studio installable Android APK — alpha

This Android app embeds the real Merlin Studio Python server and offline web UI using Chaquopy 17.2 and an Android WebView. It is **not** a Termux shortcut or browser bookmark. The APK is built from the exact checked-out Merlin source via portable/build_portable.py and includes a complete SHA-256 member manifest.

Supported target: Android API 26+, 64-bit ARM (arm64-v8a) and x86-64 emulator.
The build uses Android Gradle plugin 8.12.2, Gradle 8.13, and Python 3.11.
It runs an HTTP server bound only to 127.0.0.1:8771 inside the app. The native
WebView is restricted to that port. The app requests Internet permission only
for its loopback socket and has no external account or cloud API integration.

## First release scope

- Real Merlin workspace and persistent SQLite chat history; offline /help,
  /files, /read and /write commands; Second Brain reader available when
  explicitly configured with an accessible local vault.
- Python runtime is included in the APK: **no Termux required**.
- **This build profile includes** the pinned Qwen2.5-0.5B-Instruct Q4_K_M GGUF
  (~491 MB) and the CPU-only native llama.cpp ARM64/x86_64 libraries, with
  SHA-256 verification before APK packaging and before the first private-storage
  load. The model is the unchanged Apache-2.0 baseline; experimental LoRA v2
  and Heretic candidates are deliberately not promoted.
- Merlin loads the model in-process over its JNI bridge and exposes its own
  127.0.0.1:8772 OpenAI-compatible API; Internet and accounts are not needed
  after installation. App startup requires extracting an extra ~491 MB into
  private storage and enough RAM for the model. Android device inference and
  long-chat performance are **not yet independently qualified**.
- High-authority Python execution, desktop automation, public Internet
  retrieval and connected browser are disabled at the settings validation
  boundary. They must not be described as Android capabilities.
- Local state is stored inside the Android application sandbox; Android
  application backup is disabled. It remains plaintext local data, not a
  secure vault for regulated records.
- App may be paused/killed by Android in the background. This release has
  no foreground service and does not promise unattended autonomous operation.

## Build

  python3 portable/build_portable.py --output android/merlin-apk/app/src/main/assets/merlin-studio-pinned.zip
  cd android/merlin-apk
  gradle --no-daemon --console plain :app:assembleDebug

Use the dedicated GitHub Actions workflow for reproducible GitHub CI and an
instrumented emulator restart smoke test. The debug APK is developer-signed
by an ephemeral Android debug key. **Do not use it as a final signed
production release, publish to an app store, or distribute it as trusted
without a controlled signing process and real-device QA.**

Do not include secrets or user vault files. This explicitly labeled DEV GGUF release profile intentionally contains public Apache-2.0 model weights. It is a debug-signed, resource-heavy development candidate, not an independently qualified production release.
