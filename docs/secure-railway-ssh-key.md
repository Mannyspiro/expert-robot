# Secure Railway / GitHub SSH key setup

This branch intentionally does **not** contain a private key.

Use a **newly rotated key**. Do not reuse any private key that has ever been
pasted into a chat, issue, PR, commit, log, or other shared surface.

## 1. Generate a fresh key locally

```bash
ssh-keygen -t ed25519 -f ~/.ssh/expert_robot_railway -C "expert-robot-railway"
```

Keep this private:

```text
~/.ssh/expert_robot_railway
```

The public half is:

```text
~/.ssh/expert_robot_railway.pub
```

## 2. Add the public key where GitHub needs it

For repository read/write access from a Railway VM:

1. Open this repository in GitHub.
2. Go to **Settings -> Deploy keys**.
3. Choose **Add deploy key**.
4. Paste only the contents of `~/.ssh/expert_robot_railway.pub`.
5. Enable write access only if the worker truly needs to push commits.

A deploy key is a repository-access credential. It does **not** register a
GitHub Actions self-hosted runner by itself. Runner registration still requires
GitHub's runner registration flow/token.

## 3. Add the private key as a GitHub Actions secret

In this repository:

1. Open **Settings -> Secrets and variables -> Actions**.
2. Choose **New repository secret**.
3. Name it exactly:

```text
RAILWAY_SSH_PRIVATE_KEY
```

4. Paste the complete contents of the newly generated private key.

Do not put the private key in:
- a tracked file,
- a PR comment,
- an issue,
- a commit message,
- workflow YAML,
- repository variables.

## 4. Validate it

Run the manual workflow:

```text
Secure Railway SSH Check
```

With **test_connection = false**, it only verifies that the secret parses as a
valid OpenSSH private key.

With **test_connection = true**, it also performs a non-interactive
`ssh railway.new` handshake using the temporary key file.

The workflow:
- uses `umask 077`,
- writes the key only to `$RUNNER_TEMP`,
- sets mode `600`,
- never prints the private key,
- deletes the temporary key material in an `always()` cleanup step.

## 5. Railway VM usage

From your own Mac:

```bash
ssh -i ~/.ssh/expert_robot_railway railway.new
```

Inside the VM, clone using the same key or an SSH config entry:

```bash
git clone git@github.com:Mannyspiro/expert-robot.git
```

Then use the repo's low-memory preflight lane:

```bash
cd expert-robot
git checkout feat/reuse-refactored-fishstick
bash ./scripts/railway-preflight.sh --bootstrap
```

## Authority boundary

This key only enables transport/authentication. It does not expand runtime
authority, bypass Lean, bypass repository CI, or grant promotion authority.
