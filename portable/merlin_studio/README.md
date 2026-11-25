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

The **Workspace** panel also opens and edits files directly. Text files are limited to 256 KiB. File tools reject paths outside the workspace and refuse workspace symlinks. Python execution is a separate capability: **approved Python code has the permissions of the account running Merlin on its host and can access that host beyond the workspace. It is not an OS sandbox.**

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
- By default, the server binds to loopback, checks local Host/Origin boundaries, and requires a per-launch session token for writes. It is intended for one trusted owner. Remote access requires the separate verifying gateway contract described below; the default mode does not authenticate remote accounts.
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


### Optional synthetic security review

Studio includes a read-only Security review page. By default it shows that no report is configured. A trusted local operator may start the server with `--security-report PATH` pointing at a host-exported `merlin-studio-security-summary/1` JSON file. The file is read once during startup and contains only synthetic counts, recent incident categories, and the source-reported anchor status. Keep it outside the model workspace and do not include keys, raw logs, client records, or signing identities. Restart Studio with a newly exported summary to refresh. Studio validates the shape and bounds of the snapshot; it does not independently verify the host's cryptographic evidence, run ARTEX, or authorize actions. No network provider, model, or signing key is needed.


## Combined research window and live activity

Start Studio with an explicit canonical research state directory:

```sh
python3 server.py --port 8771 --data-dir /path/to/studio-state --research-state-dir /path/to/research-state
```

The Research panel appears beside chat on wide screens and as a closable panel
on smaller screens. Select a recorded research run to retain its exact graphs,
proof sources and evidence while using chat. **Current Studio run** follows the
current request. The selector displays at most 200 recorded sessions; the HUD
projects the most recent 1,000 canonical telemetry records, so an older session
can have registered artifacts while its activity history is outside that window.
The existing ASCII emblem, motion preference and graph-follow controls remain.

Research uses the existing canonical registry, knowledge graph and durable
outbox in that directory. The runtime writes source-labelled metadata from real
Studio requests, tools, approvals and terminal outcomes. Stable event identities
make restart replay idempotent. Conversation text, tool arguments/results and
workspace files are not automatically published as research artifacts. A
completed Studio task never implies a theorem, formal proof or independent
verification. Register scientific artifacts explicitly using the research
publisher; no HTTP publishing endpoint is added.

Run and Activity updates use Server-Sent Events with bounded connection duration,
12 concurrent streams, per-run event IDs and browser reconnection. Browsers
without EventSource retain polling. Model responses are displayed when complete;
this transport does not stream model tokens. An interrupted request is recorded
after restart and its tools are not replayed.

## Optional owner-only remote gateway

The default listener and local Host/Origin/session-token protections remain.
For SSH forwarding, keep the browser-side port equal to the server port, for
example 8771. Forwarded headers do not change the accepted origin.

An operator can provide `--gateway-config /path/to/gateway.json` for one HTTPS
origin behind a separately configured **Cloudflare Access verifying gateway**.
The contract schema is `merlin-studio-trusted-gateway/1` and includes
`contract_version: 1`, `public_origin`, `team_name`, `audiences`, and
`identity_verifier: "cloudflared-access-required"`. The required per-ingress
cloudflared Access policy must validate the exact team and audiences before
forwarding to this loopback listener. Use the deployment preflight and templates
in `ops/merlin-studio` from the source repository.

The application checks its explicit origin contract and the presence/shape of
the gateway assertion; it does **not** cryptographically verify that assertion.
That verification belongs to the independently configured gateway. Header
presence, a secret-looking URL, and the local session token do not authenticate
a remote person. Every admitted identity shares one owner's conversations,
workspace and approval authority. This is not a multi-tenant service. Keep the
service identity separate from CI credentials; approved Python has that service
user's host permissions.
