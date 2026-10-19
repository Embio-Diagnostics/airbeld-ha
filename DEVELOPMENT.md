# Development Guide

This guide helps you set up a development environment for the Airbeld Home Assistant integration.

## Table of Contents

1. [Quick Start (Dev Container)](#quick-start-dev-container)
2. [Local Development](#local-development)
   - [Setup with pip](#setup-with-pip)
   - [Setup with uv](#setup-with-uv)
3. [Scripts Reference](#scripts-reference)
4. [Testing Your Changes](#testing-your-changes)
5. [Code Style](#code-style)
6. [Troubleshooting](#troubleshooting)
7. [Development HA containers](#development-ha-containers)
8. [Dependency PR review](#dependency-pr-review)

---

## Quick Start (Dev Container)

Recommended approach for contributors. The devcontainer automatically creates a virtual environment and installs all dependencies.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- [Visual Studio Code](https://code.visualstudio.com/)
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Embio-Diagnostics/airbeld-ha.git
   cd airbeld-ha
   ```

2. Open in VSCode:
   ```bash
   code .
   ```

3. Reopen in Container when prompted (VSCode will detect `.devcontainer.json`)
   - Container automatically runs `scripts/setup --pip`
   - Creates `.venv/` and installs the locked root dependencies

4. Start Home Assistant:
   ```bash
   ./scripts/develop
   ```

5. Visit <http://localhost:8123> to complete onboarding

The host-native runner uses the production API when Airbeld is added; use
[`just dev-staging`](#development-ha-containers) for test accounts.

---

## Local Development

Local development using Python virtual environments. Choose pip (standard) or uv (faster).

### Prerequisites

- Python 3.14.2+ (required by the pinned Home Assistant 2026.10.1 environment)
- Git
- Note: uv can auto-install Python 3.14 if needed

### Setup with pip

```bash
git clone https://github.com/Embio-Diagnostics/airbeld-ha.git
cd airbeld-ha
./scripts/setup --pip
source .venv/bin/activate
./scripts/develop
```

Visit <http://localhost:8123> to complete onboarding.

### Setup with uv

Install uv (one-time):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Setup:

```bash
git clone https://github.com/Embio-Diagnostics/airbeld-ha.git
cd airbeld-ha
./scripts/setup --uv
source .venv/bin/activate
./scripts/develop
```

Visit <http://localhost:8123> to complete onboarding.

**Note:** uv can auto-install Python versions: `./scripts/setup --uv --python 3.14`
The root's `dev` dependency group is installed by default; it is not a `--extra dev` extra.

### Update Dependencies

After pulling changes or when dependencies are updated:

```bash
./scripts/setup --update
# Or specify package manager:
./scripts/setup --update --uv
```

### Modify Dependencies

**Source of truth:** `pyproject.toml` (edit this file)

After modifying dependencies in `pyproject.toml`:

```bash
uv lock
uv lock --project ci/ha-min  # if the floor project's dependencies changed too
./scripts/sync-deps  # Exports frozen requirements.txt for pip users
git add pyproject.toml requirements.txt uv.lock
```

---

## Scripts Reference

The host-native scripts work in both dev container and local environments.
`scripts/develop` and `scripts/lint` activate `.venv/` if present; activate it
yourself before `scripts/validate` if needed.

### `./scripts/setup`

**Purpose:** Setup development environment or update dependencies

**What it does:**
- Creates `.venv/` virtual environment (if needed)
- **uv:** Installs from `pyproject.toml` using `uv sync --no-install-project`; the default `dev` dependency group is included, and an existing lock is used with `--frozen`
- **pip:** Installs from `requirements.txt` (exported from the root lock)

**Options:**
- `--pip` - Use pip package manager (default)
- `--uv` - Use uv package manager (faster, reads pyproject.toml)
- `--python X.Y` - Use specific Python version (e.g., 3.14)
- `--update` - Only update dependencies (skip venv creation)
- `--help` - Show help message

**Examples:**
```bash
# Initial setup with pip
./scripts/setup --pip

# Initial setup with uv (faster, modern)
./scripts/setup --uv

# Specify Python version
./scripts/setup --pip --python 3.14
./scripts/setup --uv --python 3.14  # uv auto-downloads Python

# Update dependencies only (faster than recreating venv)
./scripts/setup --update
./scripts/setup --update --uv

# Show help
./scripts/setup --help
```

---

### `./scripts/sync-deps`

**Purpose:** Generate `requirements.txt` from the root's locked dependencies

**What it does:**
- Exports `uv.lock`, including the `dev` dependency group
- Generates pinned `requirements.txt` for pip users
- Run this after locking dependency changes in `pyproject.toml`

**When to use:**
- After adding/updating dependencies in `pyproject.toml` and running `uv lock`
- Before committing dependency changes

**Example:**
```bash
# Edit pyproject.toml dependencies
vim pyproject.toml
uv lock

# Generate requirements.txt
./scripts/sync-deps

# Commit the dependency files together
git add pyproject.toml requirements.txt uv.lock
git commit -m "Update dependencies"
```

---

### `./scripts/develop`

**Purpose:** Run Home Assistant with the integration loaded

**What it does:**
- Activates `.venv/` if present
- Creates `config/` directory
- Symlinks integration to `config/custom_components/airbeld`
- Starts Home Assistant in debug mode

**When to use:**
- Testing integration changes
- Developing new features
- Debugging issues

**Example:**
```bash
./scripts/develop
```

**Access:** http://localhost:8123

This runner retains the production API default. Signing in uses a real production
account; use `just dev-staging` for test accounts and isolated container state.

---

### `./scripts/lint`

**Purpose:** Format and lint code with Ruff

**What it does:**
- Activates `.venv/` if present
- Runs `ruff format .` (auto-formats code)
- Runs `ruff check . --fix` (fixes linting issues)

**When to use:**
- Before committing changes
- To ensure code style compliance
- To auto-fix formatting issues

**Example:**
```bash
./scripts/lint
```

---

### `./scripts/validate`

**Purpose:** Validate integration structure and configuration files

**What it does:**

- Validates `manifest.json` JSON syntax
- Validates `strings.json` JSON syntax
- Validates `translations/en.json` JSON syntax
- Checks all required files exist
- Verifies manifest has required fields (domain, name, version, etc.)

**When to use:**

- Before committing changes (catches common mistakes)
- After modifying manifest.json or strings.json
- To ensure integration structure is correct

**Example:**

```bash
./scripts/validate

# Run both validation scripts
./scripts/lint && ./scripts/validate
```

**Note:** This runs lightweight local checks. `just ci` also runs official
hassfest locally; full upstream HACS validation remains in GitHub Actions.

---

## Testing Your Changes

### In Dev Container

1. Make changes to files in `custom_components/airbeld/`
2. Restart Home Assistant:
   ```bash
   # Press Ctrl+C to stop
   ./scripts/develop
   ```
3. Or reload in HA UI: Developer Tools → YAML → Reload custom integrations

### Locally

Same as dev container - the workflow is identical!

### Running Tests

```bash
just ci
```

### Automated gate

Install Docker (with Compose v2.24+), uv and just. The integration is not a
distributable Python package: both uv projects use `package = false`.

```sh
uv sync --frozen
uv sync --frozen --project ci/ha-min
just ci
```

`just ci` runs Ruff check/format, both pinned HA test environments, the H1–H7
manifest checker, credential-free local HACS metadata checks, and the official
digest-pinned hassfest image with networking disabled and source mounted read-only.
The local metadata checker checks the declared floor, name, layout, config flow,
version, runtime requirements, required local files and JSON syntax. It is **not
full HACS validation**: `hacs/action` remains the owner gate after push.

The root tests need Python 3.14.2+ (pin: 3.14). Floor tests need Python 3.12;
see [compatibility](docs/ha-compatibility.md) for dependency overrides and limitations.
For targeted iteration:

```sh
uv run --frozen --offline pytest -q tests/test_characterization.py
uv run --frozen --offline --project ci/ha-min pytest -q tests/test_characterization.py
uv run --frozen --offline python scripts/check_defects.py --verify-unfixed
```

Tests use HA's `hass` fixture, the **real SDK**, and `httpx.MockTransport` at
its HTTP boundary. No live backend or login is needed. Strict xfails record
desired H1–H7 behavior; the checker runs them with `--runxfail` and inspects the
original exception type. The task fixing a defect changes its manifest state to
`fixed` and removes its xfail in the same diff; never loosen an assertion.

When changing dependencies, run `uv lock` in each affected project and
`bash scripts/sync-deps` to export the root's frozen requirements for pip users.
Pip users need Python 3.14.2+ and install `requirements.txt`.

## Development HA containers

```sh
just dev                 # http://localhost:8123
just dev-staging         # http://localhost:8124
just dev-down
just dev-staging-down
```

Both commands build the pinned HA 2026.10.1 image with the vendored SDK 1.0.0 candidate (`vendor/wheels/`) preinstalled,
boot without credentials, mount the integration read-only, and use separate named
Docker volumes. No HA config, database, token or log is written into the checkout.
HA's own image remains root because its bundled runtime expects that layout;
this is a local development container, not a production deployment.

`dev` boots HA for onboarding without making API requests until the owner adds
Airbeld. **"Local" mode still talks to the production API:** the integration's
`DEFAULT_API_BASE` is `https://api.airbeld.com`, so signing in there uses a real
production account. Use **`just dev-staging` for test accounts**.
`dev-staging` replaces the API base **only in that container's Python
memory**, before HA starts, with the documented staging App Service origin:
`https://airbeld-staging-api-fmb3htfqfua5hhgk.westeurope-01.azurewebsites.net`.
The v1 SDK appends `/api/v1`; task 21 changes the integration to SDK v2.
Auth0 is shared between environments as the initiative specifies.

Complete HA onboarding, then Settings → Devices & services → Add integration →
Airbeld. Signing in with a dedicated test account and seeing staging sensors is
an **owner-only manual check**. Do not store credentials or tokens in this repo
or evidence. Persistent HA state lives in its named volume; `down` retains it.

The VS Code devcontainer uses Python 3.14. `scripts/setup --pip` installs the
locked root environment; `scripts/develop` is the older host-native runner.
Container commands above are preferred for isolated state.

## Code Style

This project follows Home Assistant code standards:

### Guidelines

- **Async-first:** Use `async`/`await` for all I/O operations
- **Type hints:** Add type annotations to all functions
- **Docstrings:** Document public functions and classes
- **Formatting:** Ruff handles formatting automatically
- **Imports:** Organized by stdlib, third-party, local
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes

### Ruff Configuration

The project uses `.ruff.toml` matching Home Assistant Core standards:
- Python 3.13 target (the integration's syntax target, separate from the newest-HA Python 3.14 environment)
- Comprehensive rule set
- Auto-fixes common issues
- Compatible with `black` formatting

### Before Committing

Always run both validation scripts before committing:

```bash
# Run linting (format + check code style)
./scripts/lint

# Run validation (check JSON syntax + required files)
./scripts/validate

# Or run both at once
./scripts/lint && ./scripts/validate

# Run the automated gate, including tests on both HA versions
just ci

# Check for remaining issues
git diff
```

**What each script does:**

- `./scripts/lint` - Formats code with ruff and fixes linting issues
- `./scripts/validate` - Validates manifest.json, strings.json, translations, and required files

**Important:** Both scripts and `just ci` must pass before pushing to GitHub.
Full upstream HACS validation is still a post-push owner gate.

---

## Troubleshooting

### Integration not loading

**Symptom:** Airbeld doesn't appear in "Add Integration"

**Solutions:**
1. Check `manifest.json` has `"version"` field (required for custom components)
2. Restart Home Assistant completely
3. Check logs: `tail -f config/home-assistant.log`
4. Verify symlink exists: `ls -la config/custom_components/airbeld`

---

### Import errors

**Symptom:** `ModuleNotFoundError: No module named 'airbeld'`

**Solutions:**
1. Verify SDK is installed: `pip show airbeld-api-sdk` or `uv pip list | grep airbeld`
2. Update dependencies: `./scripts/setup --update`
3. In dev container: restart container
4. Locally: re-run `./scripts/setup --pip` (or `--uv`)

---

### OAuth flow fails

**Symptom:** Authentication doesn't start or fails

**Solutions:**
1. Check `const.py` has correct Auth0 URLs
2. Verify `OAUTH2_CLIENT_ID` is set
3. Check Home Assistant logs for OAuth errors
4. Try removing and re-adding the integration

---

### Circular import error

**Symptom:** `cannot import name 'AirbeldClient' from partially initialized module 'airbeld'`

**Solution:**
- This is fixed by using symlinks instead of PYTHONPATH
- Run `./scripts/develop` which handles this automatically
- Do NOT manually set PYTHONPATH to `custom_components/`

---

### Port 8123 already in use

**Symptom:** Home Assistant fails to start

**Solutions:**
```bash
# Find what's using port 8123
lsof -i :8123

# Stop existing HA instance
pkill -f "hass --config"

# Or use a different port (edit scripts/develop)
```

---

### Virtual environment issues

**Symptom:** Dependencies not found even after `bootstrap`

**Solutions:**
1. Remove and recreate venv:
   ```bash
   rm -rf .venv
   ./scripts/setup --pip  # or --uv
   ```

2. Manually activate and check:
   ```bash
   source .venv/bin/activate
   python --version  # Should be 3.14.2+ for the newest-HA environment

   # For pip:
   pip list | grep airbeld

   # For uv:
   uv pip list | grep airbeld
   ```

3. If using older Python (< 3.14.2), use uv to install correct version:
   ```bash
   rm -rf .venv
   ./scripts/setup --uv --python 3.14
   ```

---

## Dependency PR review

See [recorded recommendations](docs/dependabot-recommendations.md). No PR is
merged, closed, commented on or pushed by this task.

## Need Help?

- **Bug reports:** [GitHub Issues](https://github.com/Embio-Diagnostics/airbeld-ha/issues)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

---

Happy coding! 🚀
