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

## Connect local AI

Open **Settings**, enter a loopback model endpoint such as `http://127.0.0.1:8080/v1/chat/completions`, and use **Save & check connection**. Select the model ID reported by that server. If you change the ID, save and check again.

See [MODEL_SETUP.md](MODEL_SETUP.md) for using an existing server or supplying a local `llama-server` executable and one GGUF model. No model is downloaded automatically. Setup status and tool execution are real application states; an unconfigured model does not generate an AI reply.

## Optional connected public Chromium browser (authorized Linux host only)

The portable Studio ZIP remains fully useful for offline interface, workspace and slash-command tasks **without a browser or model**. It does not include a rendered browser worker, browser service, Python distribution, model weights or credentials.

An explicitly installed **Merlin public-browser supervisor** can be used only on its authorized Linux host. To enable it, run Studio as Merlin's fixed service UID 982, with the root-owned Unix socket `/run/merlin-public-browser/browser.sock` and the separate browser modules installed on the host. Then enable **Internet research** and **Connected research browser** in Settings and use a model that emits native function tool calls. Studio verifies the socket identity; the browser client verifies its root supervisor peer. Ordinary standalone ZIP installs do not satisfy these conditions, and the browser remains unavailable even if its toggle is selected.

Merlin's supported agent browser operations are `browser_open` (one public URL and one durable evidence episode per Studio run) and `browser_read` (a bounded text excerpt from the exact capture created by that same run). The worker, not Studio, enforces public-network egress, cookie/account exclusion, process isolation, 60-second browser execution and canonical source capture. Studio verifies the returned source's exact `ArtifactRef`, SHA-256 excerpt digest and byte boundaries. Browser source text is **untrusted**: a capture can establish what a site returned, not whether its claims are true.

The experimental **Read-only JSON fallback** for small local models does **not** grant browser access. This connected browser integration requires genuine native tool calls; it is not a claim that the tested small Qwen model can use it. The Studio browser tool does not support arbitrary JavaScript, authentication, private services, filesystem upload, arbitrary shell commands or autonomous promotion. A failed or timed-out browser episode may have retained side effects and must be reconciled by episode identity, never silently replayed.

## Included behavior and boundaries

- Conversations, settings, tool activity, and file artifacts persist across server restarts. The original Merlin registry and `ArtifactRef` implementation are included in `core/python/merlin`.
- The agent loop uses the configured local model to choose declared tools, within a budget of 1–12 steps. Model behavior and tool-selection quality depend on the supplied model and its chat template; no real-model quality qualification is included here.
- Python and optional desktop actions pause for an approval tied to the pending action. Script approvals also bind the script bytes. A changed script requires a new approval.
- Cancellation stops waiting or continuing work. External side effects already completed are not undone. Interrupted requests are recorded after a restart and are not automatically replayed.
- Tool activity records arguments and results. Workspace writes retain canonical artifacts and previous contents. Source retrieval retains raw bytes and receipts when it succeeds.
- The built-in `fetch_url` research transport retrieves public HTTPS responses without rendering JavaScript. The **separate, optional** authenticated Chromium service is not bundled with the ZIP and has independent installation and native acceptance requirements.
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
