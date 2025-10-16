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
   - Creates `.venv/` and installs dependencies (takes ~1-2 minutes)

4. Start Home Assistant:
   ```bash
   ./scripts/develop
   ```

5. Visit <http://localhost:8123> to complete onboarding

---

## Local Development

Local development using Python virtual environments. Choose pip (standard) or uv (faster).

### Prerequisites

- Python 3.13.2+ (required by Home Assistant 2025.10+)
- Git
- Note: uv can auto-install Python 3.13 if needed

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

**Note:** uv can auto-install Python versions: `./scripts/setup --uv --python 3.13`

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
./scripts/sync-deps  # Generates requirements.txt for pip users
git add pyproject.toml requirements.txt uv.lock  # uv.lock created by uv sync
```

---

## Scripts Reference

All scripts work in both dev container and local environments. They automatically detect and use `.venv/` if present.

### `./scripts/setup`

**Purpose:** Setup development environment or update dependencies

**What it does:**
- Creates `.venv/` virtual environment (if needed)
- **uv:** Installs from `pyproject.toml` using `uv sync --no-install-project` (creates `uv.lock`)
- **pip:** Installs from `requirements.txt` (generated from `pyproject.toml`)

**Options:**
- `--pip` - Use pip package manager (default)
- `--uv` - Use uv package manager (faster, reads pyproject.toml)
- `--python X.Y` - Use specific Python version (e.g., 3.13)
- `--update` - Only update dependencies (skip venv creation)
- `--help` - Show help message

**Examples:**
```bash
# Initial setup with pip
./scripts/setup --pip

# Initial setup with uv (faster, modern)
./scripts/setup --uv

# Specify Python version
./scripts/setup --pip --python 3.13
./scripts/setup --uv --python 3.13  # uv auto-downloads Python

# Update dependencies only (faster than recreating venv)
./scripts/setup --update
./scripts/setup --update --uv

# Show help
./scripts/setup --help
```

---

### `./scripts/sync-deps`

**Purpose:** Generate `requirements.txt` from `pyproject.toml`

**What it does:**
- Reads dependencies from `pyproject.toml`
- Generates pinned `requirements.txt` for pip users
- Run this after editing dependencies in `pyproject.toml`

**When to use:**
- After adding/updating dependencies in `pyproject.toml`
- Before committing dependency changes

**Example:**
```bash
# Edit pyproject.toml dependencies
vim pyproject.toml

# Generate requirements.txt
./scripts/sync-deps

# Commit both files
git add pyproject.toml requirements.txt
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

**Note:** This runs lightweight local checks. Full hassfest and HACS validation run on GitHub Actions.

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
# Lint your code
./scripts/lint

# Check for errors
python -m py_compile custom_components/airbeld/*.py
```

---

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
- Python 3.13 target
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

# Check for remaining issues
git diff
```

**What each script does:**

- `./scripts/lint` - Formats code with ruff and fixes linting issues
- `./scripts/validate` - Validates manifest.json, strings.json, translations, and required files

**Important:** Both scripts must pass before pushing to GitHub. They catch common issues that would cause CI failures.

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
   python --version  # Should be 3.13.2+

   # For pip:
   pip list | grep airbeld

   # For uv:
   uv pip list | grep airbeld
   ```

3. If using older Python (< 3.13.2), use uv to install correct version:
   ```bash
   rm -rf .venv
   ./scripts/setup --uv --python 3.13
   ```

---

## Need Help?

- **Bug reports:** [GitHub Issues](https://github.com/Embio-Diagnostics/airbeld-ha/issues)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

---

Happy coding! 🚀
