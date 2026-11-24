# Local AI in Merlin Studio

Merlin Studio supports a source ZIP and a self-contained Linux profile. The source ZIP requires a compatible Python interpreter, inference server, and model. The Linux x86_64 profile includes those assets and can start local AI after extraction. No account or hosted AI service is required.

## Start the self-contained Linux profile

The file `Merlin-Studio-linux-x86_64-offline-Qwen1.5B.zip` contains standalone CPython 3.11.18, a CPU build of `llama-server`, and Qwen2.5-1.5B-Instruct in Q4_K_M GGUF format. This profile targets compatible Linux x86_64 systems; it is not a Windows or macOS runtime.

GitHub distributes the accepted ZIP as three parts, each at most 384 MiB, plus an evidence artifact. `offline-delivery-manifest.json` binds the original ZIP, all three parts, and the acceptance evidence to their exact hashes and source revision. The repository's `scripts/merlin/offline_delivery.py assemble` command verifies every part and reconstructs the unchanged full ZIP; the regular offline-profile verifier then checks its contents. A complete ZIP supplied directly has the same recorded full-file hash and needs no reassembly.

1. Extract the entire archive with a ZIP utility that preserves Unix executable permissions and symbolic links.
2. Open its `Merlin_Studio` directory and run `sh START.sh`.
3. Keep the terminal open. Studio opens at `http://127.0.0.1:8771/studio/` and starts the bundled model on loopback port 8772 when no other model endpoint is configured.
4. Allow the model to load, then send a message. The local model process uses two inference threads and two batch threads.

The model file alone is **1,117,320,736 bytes**. Keep enough free storage for the complete archive and its extracted contents, and enough physical RAM for the model, its context, the runtime, and the operating system. SSD capacity does not supply GPU computation or replace the model's active working memory.

The profile's model comes from [Qwen's official immutable release revision](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9). The build verifies the complete model SHA-256 `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` and the exact included publisher license before packaging. `OFFLINE_PROFILE_MANIFEST.json` lists the final asset hashes. The build publishes the complete ZIP only after extraction and a real local model answer pass its native smoke test. That bounded check does not establish broad reasoning or autonomous tool-selection quality.

The Qwen profile and the separate SSD-backed Parallax research implementation have different model requirements. This profile does not claim to run a Parallax-trained model.

## Use an existing local server

1. Start the inference server on a loopback address. Merlin accepts `http://127.0.0.1`, `http://localhost`, or `http://[::1]`, with a port and the `/v1/chat/completions` path. Remote HTTPS services and account logins are not supported by this adapter.
2. Open Studio's **Settings** and enter, for example, `http://127.0.0.1:8080/v1/chat/completions`.
3. Click **Save & check connection**. Studio requests `/v1/models` from the same local server.
4. Choose the returned model ID. If you change it, click **Save & check connection** again, then close Settings.
5. Send a simple question. Next, ask Merlin to list the workspace and examine Activity to confirm an actual tool result. A model response claiming it used a tool is not itself an execution record.

You can also set `MERLIN_MODEL_URL` and `MERLIN_MODEL_ID` before starting Studio. These environment values override saved settings on startup. Do not put account passwords or remote API keys into the endpoint; the local adapter rejects URL credentials.

## Local model response limits and tool-call compatibility

A slow CPU model may require more time. Studio's **Settings** include an output budget of 16–2,048 tokens (default 2,048) and a model response deadline of 10–120 seconds (default 45). A longer deadline does **not** increase model accuracy; use it only where the CPU and workload need it. The total agent run is separately bounded, and tool actions keep their existing permissions.

The **Local model tool-call compatibility** setting defaults to **Native function calls**. If a local model instead prints an exact JSON envelope such as `{"name":"read_file","arguments":{"path":"notes.txt"}}` without using the provider's native `tool_calls` interface, an experimental **Read-only JSON fallback** can be selected explicitly. It admits only `read_file` and `list_files` with validated workspace paths. It rejects ambiguous or malformed text, duplicate JSON keys, traversal paths, and attempts to express file writing, Python, desktop, or network tools through this fallback. It does not bypass Studio's tool policy.

After one adapted read, Studio records the actual tool result and asks the model for a tool-free continuation rather than repeating the read. The result is still *untrusted information*; inspect **Activity** for `model_tool_adapter`, `tool_started`, and `tool_result` events, along with the answer and source digest. A text representation of a tool call is not evidence the tool executed. This compatibility option is experimental and should not be treated as a general reasoning or release qualification.

## Example with llama.cpp

The official [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) describes its compatible chat endpoint, `/v1/models`, model aliases, and Jinja-based tool calling. It is the primary reference for the inference server's build requirements and model/chat-template compatibility.

With an already installed server and a local model file, a typical command is:

```sh
llama-server --model /absolute/path/model.gguf --host 127.0.0.1 --port 8080 --ctx-size 4096 --jinja --alias merlin-local --threads 2 --threads-batch 2
```

Use `llama-server.exe` on Windows. In Studio, set the endpoint to `http://127.0.0.1:8080/v1/chat/completions` and the model ID to `merlin-local`. Tool-call support can depend on the model's template; the official server documentation explains template options. This example is configuration guidance, not evidence that a model has been run or qualified in this package.

## Let Studio start supplied local assets

Studio can start a server you have deliberately placed beside the app:

- Put the appropriate executable at `bin/llama-server` or `bin/llama-server.exe`, together with any libraries required by that distribution.
- Put **exactly one** `.gguf` model in `models/`. Multiple files require an explicit `MERLIN_MODEL_PATH` instead of automatic selection.
- On Unix systems, ensure the server executable can be executed.
- Clear any saved model endpoint in Settings, save, and restart Studio. Automatic launch is used only when no endpoint is configured.

The launcher starts that executable with the supplied model, loopback address, port **8772**, context size **4096**, `--jinja`, two inference threads, and two batch threads. Studio then uses `http://127.0.0.1:8772/v1/chat/completions`. Allow the model to load, use **Save & check connection**, and select the server's reported model ID. Startup logs are written to `data/local-model.log`, or the chosen state directory.

Alternatively, set `MERLIN_LLAMA_SERVER` to an explicit executable path and `MERLIN_MODEL_PATH` to an explicit GGUF path. A saved or environment-provided `MERLIN_MODEL_URL` takes precedence over automatic startup.

The application does not download assets, install a runtime, select a model license, or silently change this setup. A Python distribution may also be supplied at the launcher paths described in [README.md](README.md), but is not included by the source-package builder.

## If a connection check fails

- Confirm the inference process is still running and has finished loading its model.
- Confirm the endpoint port matches the server's port; Studio's own web port is 8771.
- Select the exact ID returned by `/v1/models`, or the alias you supplied to the server.
- Inspect the inference server's log for missing files, libraries, unsupported model format, or hardware capacity errors.
- A successful connection check confirms only that the local server returned a model list. Test a real conversation and tool call before relying on its behavior.

The offline `/help`, `/files`, `/read`, and `/write` commands remain available while model setup is incomplete.
