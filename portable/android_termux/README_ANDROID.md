# Merlin Studio Android Termux package

**Android-compatible local web application, not an APK.** Includes the existing Merlin Studio interface, offline workspace tools, persistent conversations, and Obsidian-compatible read-only Second Brain viewer. No credentials, private state, trained weights, or binaries are bundled.

## Install on an Android arm64 phone

1. Install Termux from F-Droid or its official GitHub distribution.
2. Open Termux and run: `pkg update && pkg install -y python unzip`.
3. Copy the Merlin-Studio-Android-Termux.zip to Termux home. Extract in Termux home: `unzip Merlin-Studio-Android-Termux.zip -d "$HOME"`. If using Downloads, run `termux-setup-storage` before accessing it.
4. Run: `cd ~/Merlin_Studio && bash START_ANDROID.sh`.
5. Open `http://127.0.0.1:8771/studio/` in the Android browser. Try `/help` and `/files`.

## Optional one-time on-device AI setup

With internet access, run `cd ~/Merlin_Studio && bash INSTALL_ANDROID_MODEL.sh`. This tries to install Termux's llama-cpp package and downloads an exact-revision Qwen2.5 0.5B Q4_K_M model (~491 MB), rejecting a mismatched SHA-256. Restart Studio and use the local model connection check, selecting model ID `local`. The app's local inference endpoint is `127.0.0.1:8772`. Package availability, ABI, memory limits, Android battery throttling and model quality are device-specific; no physical Android device has been qualified.

After installation, ordinary workspace commands and AI inference can run without internet. The plain ZIP does not provide an offline AI on first launch: Termux Python, llama.cpp and the model need setup. Android may suspend a background Termux server. Use Termux private home, not shared storage, for the extracted working directory.

Local Studio is intended for one user on loopback. Approved Python code runs with the Termux user's permissions; it is not an OS sandbox. Do not enable private or regulated-note import into the plaintext evidence registry. This distribution does not include all unmerged Merlin experimental branches or certify production autonomy.
