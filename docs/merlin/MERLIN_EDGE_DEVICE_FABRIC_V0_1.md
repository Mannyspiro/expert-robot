# Merlin Avrea Edge Fabric and Device Clients v0.1

## Objective

Keep Merlin's expensive intelligence and engineering workloads on Avrea/approved compute while making the browser client usable from phones, tablets, televisions and small IoT devices. Devices are thin clients and capability endpoints; they are not assumed to run the full Merlin model stack.

## Critical infrastructure distinction

Avrea build cache is not the same thing as a persistent application runtime, object store, database, or GPU inference service. A cache hit can reduce dependency/build time, but it does not prove that a model is resident, that a service is running, or that a device can reach it. The runtime design must separately qualify:

- Runner execution: a real job ran on the named Avrea/OCI runner and returned a job identity, logs, exit status and artifacts.
- Build/dependency cache: a content-addressed cache hit for an exact dependency/toolchain/source key.
- Model cache: model files are present, complete, versioned, integrity-checked and licensed for the intended use.
- Service runtime: the model/API process is running, health-checked and resource-budgeted.
- Durable state: registry, graph, events and memory are stored in durable volumes/databases with backup and restore tests.

Do not assume the Avrea cache is directly mountable or writable by Merlin until the runner integration explicitly exposes and verifies that interface. Do not place the only copy of durable state in an evictable cache.

## Target topology

```text
Phone / tablet / TV browser / IoT companion
  - responsive Merlin HUD
  - local input/output and device-native controls
  - short-lived session state
  - explicit device capability manifest
             |
             | outbound HTTPS + authenticated device session
             v
Merlin Edge Gateway / API
  - device identity and revocation
  - request validation, rate limits, quotas
  - task routing and streaming
  - no direct arbitrary shell or peripheral control
             |
             v
Hermes orchestration -> Avrea / OCI workers -> MCFC resource scheduler
             |
             +---- canonical registry / knowledge graph / event outbox
             |
             +---- CACE independent evidence verification
```

The current MVP API binds to 127.0.0.1. That is suitable for same-machine local use, but it is not a network-accessible phone/TV service. Remote clients must use an authenticated HTTPS edge gateway or an explicitly configured secure tunnel; never solve this by binding the existing unauthenticated loopback API to 0.0.0.0 or exposing it directly to the internet.

## Compute placement policy

| Workload | Preferred location | Device responsibility |
|---|---|---|
| Large language model inference | Qualified Avrea/OCI model worker | Send prompt/context; render streamed response |
| Research, multi-agent council, code generation | Hermes-dispatched Avrea workers | Submit task and display status/results |
| CAD, Lean, numerical simulation, video generation | Budgeted Avrea/OCI worker | Upload/download approved artifacts |
| Registry, event ledger, knowledge graph | Durable canonical service/storage | Query only; cache small read-only views |
| Voice capture/playback | Device-native browser/app | Microphone permission and local audio playback |
| Bluetooth pairing/OS audio routing | Android/TV operating system | Native settings or a separately permissioned native companion |
| TV remote navigation | TV browser/app | D-pad focus, select/back, readable layout |
| Offline fallback | Small local model only where explicitly installed and qualified | Clearly label reduced/offline capability |

Use cache keys that bind the complete build or model identity: source commit, dependency lock, compiler/runtime, adapter version, model revision, quantization, tokenizer, configuration and content digest. Never treat cache identity as CACE verification.

## Device capability contract

Each client should advertise a small allowlisted manifest, for example:

- `chat.display`, `chat.input`, `voice.capture`, `voice.playback`
- `media.playback`, `media.seek`, `media.volume`
- `tv.remote.dpad`, `tv.remote.back`, `tv.remote.select`
- `bluetooth.status.read`, `bluetooth.settings.open` (native companion only)
- `camera.capture`, `location.coarse`, `notification.display` only when the user grants the relevant permission.

A capability declaration is not proof of current availability. Store separate fields for declared, permission-granted, qualified, health and last-seen. Require user approval for each sensitive action. Revoke a device session independently of the user's Merlin account. Do not accept arbitrary commands or arbitrary capability names from a client.

## Pairing and network security requirements

1. Pair using a short-lived, single-use code displayed on the authenticated Merlin session and entered on the device, or a QR code containing a one-time enrollment URL.
2. Exchange the code for a device-scoped token; store only a salted/hashed verifier server-side. Never put long-lived API keys in browser JavaScript or QR payloads.
3. Use HTTPS, origin checks, strict request-size limits, rate limits, expiry and revocation. For service-to-service workers use authenticated workload identity or mTLS.
4. Scope device tokens to device ID and allowed capabilities. Do not grant worker, registry-write, shell or CACE authority to a display client.
5. Record pairing, revocation, capability changes and task receipts in the event ledger without recording microphone audio or raw prompt content by default.
6. Keep device state and artifact storage in durable storage, not build cache.

## Android Bluetooth support boundary

A browser-only Merlin page cannot repair Android Bluetooth pairing, change system Bluetooth permissions, force a codec, or control OS audio routing. A native Android companion can guide the user through supported settings and, with Android's documented permissions and APIs, inspect only the information those APIs expose. Actual pairing, unpairing, codec selection and connection behavior remain governed by Android and the headphone firmware.

A guided diagnostic should collect the headphone make/model, Android version/device, whether the headset appears in paired or available devices, exact connection error, and whether it connects to another device. It should then offer reversible, user-confirmed steps and record the observed result. Do not claim to have repaired a device unless the OS reports the connected state.

## Smart TV interface

First target a responsive TV-friendly web HUD/PWA with:

- 10-foot layout, large type and high-contrast status.
- Full keyboard and D-pad navigation with visible focus.
- Remote-friendly select/back behavior and no hover-only controls.
- Minimal chat, voice status, media controls and research/job cards.
- Reconnect handling and a read-only cached last-known dashboard.
- QR-based pairing from TV to phone.

A native app can follow once the exact TV platform is known (Android TV / Google TV, Samsung Tizen, LG webOS, Roku, etc.). Platform-specific app stores, remote APIs, media APIs and signing rules differ. Do not promise arbitrary TV control from a generic browser.

## Staged implementation and acceptance criteria

### E0 — Runtime and cache truth
- Inventory actual Avrea runner labels, cache surfaces, quota, disk/RAM/GPU and retention.
- Prove whether model files can be cached and reused across jobs; report cold/warm timings and eviction behavior.
- Add a durable artifact/object store and backup/restore test before moving persistent state.
- Pass only with runner identity, exact commit, cache-key receipt, logs and measured resource use.

### E1 — Device API contract
- Add versioned device registration, capability manifest validation, pairing, expiry and revocation.
- Reject unknown capabilities, expired tokens, cross-device token reuse and oversized payloads.
- Add tests for authorization boundaries and audit receipts.
- Keep the existing loopback-only MVP API loopback-only until the gateway is deployed.

### E2 — Lightweight phone client
- Responsive PWA with login/pairing, streaming chat, voice capture/playback, job status and artifact links.
- Offline shell and cached read-only dashboard; no claims that cloud/Avrea work continues offline.
- Test Android Chrome and iOS Safari.

### E3 — Headphone diagnostics
- Identify the actual headset and Android versions.
- Build a guided diagnostic UI first; add native companion functions only where Android APIs support them.
- Validate connection state through OS-reported state and user confirmation.

### E4 — TV client
- Build keyboard/D-pad accessible web UI.
- Test on the actual TV browser/platform.
- Only then choose a native TV app target and platform-specific APIs.

### E5 — Controlled device actions
- Each action has a typed capability, preview, explicit approval, timeout, cancellation and receipt.
- No generic shell execution and no silent authority escalation.

## Current status

This document is an architecture and acceptance contract, not evidence that Avrea cache is mounted, that a device has paired, that Bluetooth is repaired, or that a TV app is deployed. The existing Merlin MVP remains loopback-only. Avrea execution must be reported from actual workflow/job evidence; an Avrea credit or runner-assignment failure is an infrastructure blocker, not a test result.
