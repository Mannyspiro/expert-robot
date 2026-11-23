# Merlin Studio 0.2

Merlin Studio provides a local chat interface, persistent conversations, workspace files, an agent tool loop, and explicit approvals for code and desktop actions. It opens at **http://127.0.0.1:8771/studio/**.

The app and offline commands run with **Python 3.10 or newer** and its standard library. AI conversation and automatic tool selection require a separately supplied local inference server and model. This package contains no model weights, inference engine, Python distribution, or account credentials.

## Start

1. Extract the entire ZIP into a writable folder. Open its `Merlin_Studio` directory.
2. Windows: run `START.bat`. macOS: run `START.command`, or `sh START.sh` in Terminal. Linux: run `sh START.sh`.
3. Keep the server terminal open. The launcher asks your default browser to open Studio. If it does not open, visit http://127.0.0.1:8771/studio/ yourself.
4. Click **Try /help** or send `/files`. These commands work before a language model is connected.

The Windows launcher tries a locally supplied `runtime/python/python.exe`, then `py -3`, then `python`. The Unix launchers try `runtime/python/bin/python3`, then installed `python3` or `python`. A bundled Python distribution is not included in this build. Windows and macOS launcher behavior has not been qualified on those operating systems.

For a terminal-only launch without opening a browser:

```sh
python3 server.py --port 8771
```

Use `python` or `py -3` where appropriate. `--port 8773` selects another local port. Stop the server with **Ctrl+C**. Closing only the browser tab leaves the server running.

## Work without a model

| Command | Behavior |
| --- | --- |
| `/help` | Show available offline commands. |
| `/files` or `/files notes` | List files in the workspace or a workspace folder. |
| `/read notes/idea.md` | Read a UTF-8 text file. |
| `/write notes/idea.md` followed by a new line and content | Save a text file. |
| `/python answer.py` | Request approval to execute an existing workspace script. |
| `/fetch https://example.org/` | Request public HTTPS retrieval when internet research is enabled and a network is available. This command needs connectivity. |

Example message:

```text
/write answer.py
print(6 * 7)
```

Then send `/python answer.py`, review the action and source identity, and approve it if the script is the one you intend to run. The result is recorded in the conversation and Activity.

The **Workspace** panel also opens and edits files directly. Text files are limited to 256 KiB. File tools reject paths outside the workspace and refuse workspace symlinks. Python execution is a separate capability: **approved Python code has the local user's permissions and can access the computer beyond the workspace. It is not an OS sandbox.**

## Optional isolated Python execution (operator configuration)

The default Python tool still uses the **approved host Python worker** and is
not an OS sandbox. An operator can instead explicitly select **OpenSandbox**.
This mode is not enabled by any chat message, model response or Studio setting.

On a qualified Linux host running an independently configured, authenticated,
loopback OpenSandbox server (Docker bridge, dns+nft egress, protected control
plane, no arbitrary host bind), install the OpenSandbox Python SDK in the same
Python environment as Studio. See [the source-pinned Merlin acceptance
guide](https://github.com/Mannyspiro/expert-robot/blob/feat/merlin-native-sandbox-acceptance-20261122/docs/merlin/NATIVE_SANDBOX_ACCEPTANCE_20261122.md).
The SDK and Docker daemon are **not included** in this ZIP. Provide a trusted,
immutable Python container image and operator-owned API key separately.

Example operator environment before launching Studio on a Unix host:

~~~sh
export MERLIN_PYTHON_BACKEND=opensandbox
export MERLIN_SANDBOX_IMAGE='your-registry/python@sha256:<64-character-approved-digest>'
export MERLIN_SANDBOX_PORT=8080
export OPEN_SANDBOX_API_KEY='from-your-local-secret-store'
sh START.sh
~~~

Replace the placeholders with an actual image digest and stored key; never
put a real credential in a chat, script, or ZIP. OpenSandbox's server must
already be listening only where the operator intends. If the selected backend
has no valid image/port, Studio advertises python_setup_required and does
not offer run_python; there is **no fallback to host execution**. Backend
mode, immutable image, port and script bytes are bound to the same user
approval. A config or script change requires new approval.

The container receives only the approved script bytes in its temporary
filesystem, with no workspace mounts or environment credentials. Studio
retains its normal conversation/audit/ArtifactRef persistence. Container
results include a sandbox ID, output and source SHA-256 identity. The running
OpenSandbox server and Docker runtime are trusted infrastructure; selecting
the mode alone does not independently verify its actual isolation.

**Limitations:** The synchronous OpenSandbox SDK does not presently provide
hard interruption of a running request from Studio's cancellation callback.
The sandbox command and overall lifecycle are bounded separately, but a
blocked SDK/control-plane call may exceed Studio's deadline. Production-host
cancellation, secure-runtime posture and restart recovery need independent
acceptance before this candidate replaces host execution for regular work.

## Connect local AI

Open **Settings**, enter a loopback model endpoint such as `http://127.0.0.1:8080/v1/chat/completions`, and use **Save & check connection**. Select the model ID reported by that server. If you change the ID, save and check again.

See [MODEL_SETUP.md](MODEL_SETUP.md) for using an existing server or supplying a local `llama-server` executable and one GGUF model. No model is downloaded automatically. Setup status and tool execution are real application states; an unconfigured model does not generate an AI reply.

## Included behavior and boundaries

- Conversations, settings, tool activity, and file artifacts persist across server restarts. The original Merlin registry and `ArtifactRef` implementation are included in `core/python/merlin`.
- The agent loop uses the configured local model to choose declared tools, within a budget of 1–12 steps. Model behavior and tool-selection quality depend on the supplied model and its chat template; no real-model quality qualification is included here.
- Python and optional desktop actions pause for an approval tied to the pending action. Script approvals also bind the script bytes. A changed script requires a new approval.
- Cancellation stops waiting or continuing work. External side effects already completed are not undone. Interrupted requests are recorded after a restart and are not automatically replayed.
- Tool activity records arguments and results. Workspace writes retain canonical artifacts and previous contents. Source retrieval retains raw bytes and receipts when it succeeds.
- Research transport retrieves public HTTPS responses; it is not a JavaScript browser. External-site retrieval success has not been established by this package's local fixture tests.
- Desktop tools require `pyautogui` in the Python environment used by the launcher and a usable desktop session. Their availability and actual screenshot, click, and typing behavior are unverified on the target computer.
- The server binds to loopback, checks local Host/Origin boundaries, and requires a per-launch session token for writes. It is intended for one trusted local user, not public hosting or remote account access.
- The package makes no ChatGPT account or website connection and performs no autonomous merge, deployment, model training, or self-promotion.

## Your saved work

The default state directory is `data/` beside `server.py`. It holds the workspace, SQLite metadata, immutable registry blobs, and local model logs when applicable. To choose another location:

```sh
python3 server.py --data-dir /path/to/merlin-state
```

`MERLIN_DATA_DIR` also sets that location. Stop the server before copying its state directory as a backup. When replacing the application, retain the complete state directory and point the new copy at it. Package builds exclude state, workspace contents, caches, models, inference executables, and credentials by using an explicit source-file list.

## Optional C++ protocol core

`core/cpp` contains the original minimal JSONL protocol sources. A build made with `--include-native` additionally contains `bin/expert_robot_runtime`, compiled for **Linux x86_64 only**. The manifest identifies whether that binary is present and records its compiler and build libc. It needs compatible system libraries; it is not a universal Linux binary.

This core answers a protocol health check and explicitly rejects requests that would require model ownership. It is **not the full Merlin research engine or an inference engine**. The chat interface and offline file commands do not require it. A healthy protocol check does not qualify broader research or AI capabilities.

The runtime-supervision modules are included for the existing experimental recovery interfaces. Their presence does not authorize arbitrary host repair or deployment. Studio uses explicit process and restart boundaries described in its source.

## Verify the extracted application

From the extracted directory:

```sh
python3 VERIFY.py
python3 -m unittest discover -s tests -p 'test_studio.py' -v
```

`VERIFY.py` compares shipped files with `PACKAGE_MANIFEST.json`. For a ZIP, use `python3 VERIFY.py /path/to/package.zip`. Hashes detect changed bytes relative to this manifest; they are not a publisher signature or proof of model quality. User state and optional files added after extraction are outside the extracted-directory verification.

The included integration tests use temporary local state and synthetic model responses. They do not establish live model inference, desktop operation, external-network retrieval, rendered-browser acceptance, or a Windows/macOS/Linux qualification matrix.
