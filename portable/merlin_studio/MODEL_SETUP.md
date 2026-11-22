# Connect a local model to Merlin Studio

Merlin Studio needs two separately supplied components for AI conversation: an inference server compatible with its local chat API, and a model that server can load. The distributed application includes neither. Choose a model and runtime suitable for your hardware and permitted use; this package has not qualified a particular model's reasoning or tool selection.

## Use an existing local server

1. Start the inference server on a loopback address. Merlin accepts `http://127.0.0.1`, `http://localhost`, or `http://[::1]`, with a port and the `/v1/chat/completions` path. Remote HTTPS services and account logins are not supported by this adapter.
2. Open Studio's **Settings** and enter, for example, `http://127.0.0.1:8080/v1/chat/completions`.
3. Click **Save & check connection**. Studio requests `/v1/models` from the same local server.
4. Choose the returned model ID. If you change it, click **Save & check connection** again, then close Settings.
5. Send a simple question. Next, ask Merlin to list the workspace and examine Activity to confirm an actual tool result. A model response claiming it used a tool is not itself an execution record.

You can also set `MERLIN_MODEL_URL` and `MERLIN_MODEL_ID` before starting Studio. These environment values override saved settings on startup. Do not put account passwords or remote API keys into the endpoint; the local adapter rejects URL credentials.

## Example with llama.cpp

The official [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) describes its compatible chat endpoint, `/v1/models`, model aliases, and Jinja-based tool calling. It is the primary reference for the inference server's build requirements and model/chat-template compatibility.

With an already installed server and a local model file, a typical command is:

```sh
llama-server --model /absolute/path/model.gguf --host 127.0.0.1 --port 8080 --ctx-size 4096 --jinja --alias merlin-local
```

Use `llama-server.exe` on Windows. In Studio, set the endpoint to `http://127.0.0.1:8080/v1/chat/completions` and the model ID to `merlin-local`. Tool-call support can depend on the model's template; the official server documentation explains template options. This example is configuration guidance, not evidence that a model has been run or qualified in this package.

## Let Studio start supplied local assets

Studio can start a server you have deliberately placed beside the app:

- Put the appropriate executable at `bin/llama-server` or `bin/llama-server.exe`, together with any libraries required by that distribution.
- Put **exactly one** `.gguf` model in `models/`. Multiple files require an explicit `MERLIN_MODEL_PATH` instead of automatic selection.
- On Unix systems, ensure the server executable can be executed.
- Clear any saved model endpoint in Settings, save, and restart Studio. Automatic launch is used only when no endpoint is configured.

The existing launcher starts that executable with the supplied model, loopback address, port **8772**, context size **4096**, and `--jinja`. Studio then uses `http://127.0.0.1:8772/v1/chat/completions`. Allow the model to load, use **Save & check connection**, and select the server's reported model ID. Startup logs are written to `data/local-model.log`, or the chosen state directory.

Alternatively, set `MERLIN_LLAMA_SERVER` to an explicit executable path and `MERLIN_MODEL_PATH` to an explicit GGUF path. A saved or environment-provided `MERLIN_MODEL_URL` takes precedence over automatic startup.

The application does not download assets, install a runtime, select a model license, or silently change this setup. A Python distribution may also be supplied at the launcher paths described in [README.md](README.md), but is not included by the source-package builder.

## If a connection check fails

- Confirm the inference process is still running and has finished loading its model.
- Confirm the endpoint port matches the server's port; Studio's own web port is 8771.
- Select the exact ID returned by `/v1/models`, or the alias you supplied to the server.
- Inspect the inference server's log for missing files, libraries, unsupported model format, or hardware capacity errors.
- A successful connection check confirms only that the local server returned a model list. Test a real conversation and tool call before relying on its behavior.

The offline `/help`, `/files`, `/read`, and `/write` commands remain available while model setup is incomplete.
