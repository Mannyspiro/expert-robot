# CACE Browser Vision — bounded robot perception

This implements a **real headless browser** for research acquisition. It uses
Playwright/Chromium to load user-authorized research sites, capture a screenshot,
extract visible page text, the accessibility/ARIA snapshot, link destinations,
and image position/alt-text/size. It writes an evidence manifest with hashes,
URLs and matching excerpts.

It is intended for questions like:

- Locate **independently labeled** historical manuscript witnesses and record
  evidence about which page a museum/archive actually displays.
- Inspect diagrams and reference images through screenshot artifacts.
- Read current scientific documentation, model specifications and data portals.
- Detect which relevant links a research worker should investigate next.

## Usage

Install Playwright **in a disposable, network-isolated browser container**,
using the pinned version tested in CI:

```sh
python -m pip install playwright==1.63.0
python -m playwright install --with-deps chromium
```

Then authorize the exact research host in
`config/cace_browser_vision_policy.json`, and run:

```sh
python scripts/cace_browser_vision.py \
  --url "https://archive.org/" \
  --query "Sloane 1171 120r colour facsimile" \
  --pages 2 \
  --out research-browser-evidence
```

The output contains `research_evidence.json`, `view_00.jpg`, and
`view_01.jpg` when a matching on-domain link is followed. Both text and
screenshots are individually SHA256 hashed, but their presence is **not proof
that the scanned material is what the page labels it**. Missing manuscript
pixels remain missing.

## Optional pixel-reading robot vision

Screenshot capture does **not** by itself imply the robot understands image
content. For actual multimodal interpretation connect a **locally hosted**
OpenAI-compatible vision model endpoint (for example, a llama.cpp server
running a properly supported vision model; never substitute a text-only model
and claim visual understanding):

```sh
python scripts/cace_browser_vision.py \
  --url "https://archive.org/" \
  --query "circle diagram page evidence" \
  --out research-browser-evidence \
  --vision-endpoint http://127.0.0.1:8080/v1/chat/completions \
  --vision-model LOCAL_VISION_MODEL_NAME
```

The local model only describes screenshot evidence. The result is labeled
`unverified_model_interpretation`, with the screenshot separately retained.
It may not submit forms, expand the host policy, run local commands, make
network calls, sign a certificate, change a theorem or independently register
a manuscript observation as established.

**Actual deployment status:** The browser screenshot and DOM pipeline is
implemented and CI-tested. A working local multimodal model has **not** yet
been provisioned or qualified in this branch. An optional endpoint is not
itself a deployed model.

## Security contract

- Start with an exact **HTTPS host allowlist**; external pages do not authorize
  new domains. HTTP localhost is permitted **only** to the isolated test
  fixture using `CACE_BROWSER_LOCAL_FIXTURE=1` and `--local-fixture`.
- Block POST, uploads, form submissions, WebSockets, dialogs, popups and
  persistent session state. Resource requests count toward a strict budget.
- DNS-screen all host addresses for private, loopback, link-local and metadata
  destinations. This is **best effort only**: production deployment also
  requires container/host network egress ACLs and a private-IP/metadata
  blackhole to prevent DNS rebinding and other browser exfiltration.
- Do not place secrets, cookies, GitHub tokens, SSH keys, accounts or credentials
  into the browser profile. Browser storage is ephemeral.
- Cap inspected pages, image metadata, DOM text, screenshots, requests and
  runtime. All content is marked `untrusted_evidence_only`.
- Vision endpoints must resolve to localhost; screenshots must not be sent
  to an uncontrolled remote service.

## CACE bridge and further capability

The evidence manifest is a **candidate-source discovery artifact** for CACE's
existing historical-locus / material-research workflows. It is not a solver
input or verified provenance record until the selected source, folio,
object identity, date, image content and transformation are independently
checked.

To become a genuinely autonomous browsing researcher, the next milestones are:

1. Connect an audited, local vision model with a screenshot-based benchmark
   (including adversarial fake labels and near-identical glyphs).
2. Add a trust-governed controller that can *propose* a next URL or selected
   screenshot region, followed by deterministic policy validation.
3. Add image-region annotation/crop provenance and cross-witness visual
   alignment for Harley/Sloane/Egerton facsimiles.
4. Add independent archive-source identity checks, immutable image manifests
   and human/reviewer signoff before historical observations enter the
   witness-conditioned phylogeny.
5. Run entirely in a sandboxed network worker rather than inside the CACE
   numerical solver process.

The governing invariant remains **capability grows, authority never expands**.
