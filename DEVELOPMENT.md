# Development Guide

This guide helps you set up a development environment for the Airbeld Home Assistant integration.

## Table of Contents

1. [Quick Start (Dev Container)](#quick-start-dev-container) - Recommended
2. [Local Development (Alternative)](#local-development-alternative)
3. [Scripts Reference](#scripts-reference)
4. [Testing Your Changes](#testing-your-changes)
5. [Code Style](#code-style)
6. [Troubleshooting](#troubleshooting)

---

## Quick Start (Dev Container)

**Recommended for contributors** - Get a complete development environment with one click.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- [Visual Studio Code](https://code.visualstudio.com/)
- [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Embio-Diagnostics/airbeld-ha.git
   cd airbeld-ha
   ```

2. **Open in VSCode:**
   ```bash
   code .
   ```

3. **Reopen in Container:**
   - VSCode will detect `.devcontainer.json`
   - Click "Reopen in Container" when prompted
   - Container will automatically:
     - Install Python 3.13
     - Run `scripts/setup` to install dependencies
     - Install Home Assistant
     - Forward port 8123

4. **Start developing:**
   ```bash
   # In the VSCode terminal (inside container):
   ./scripts/develop
   ```

5. **Visit Home Assistant:**
   - Open http://localhost:8123
   - Complete onboarding
   - Add Airbeld integration

### What You Get

✅ Isolated Python 3.13 environment
✅ Home Assistant pre-installed
✅ All dependencies auto-installed
✅ Ruff linter and formatter
✅ Integration automatically loaded
✅ No configuration needed

---

## Local Development (Alternative)

Prefer working outside containers? You can develop locally using a Python virtual environment.

### Prerequisites

- Python 3.13 or higher
- Git

### Setup Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Embio-Diagnostics/airbeld-ha.git
   cd airbeld-ha
   ```

2. **Bootstrap the environment:**
   ```bash
   ./scripts/bootstrap
   ```

   This creates a `.venv/` directory and installs all dependencies.

3. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

   *Tip: Scripts will auto-activate `.venv/` if it exists, so this is optional.*

4. **Run Home Assistant:**
   ```bash
   ./scripts/develop
   ```

5. **Visit Home Assistant:**
   - Open http://localhost:8123
   - Complete onboarding
   - Add Airbeld integration

### What You Get

✅ Local Python virtual environment
✅ Full control over dependencies
✅ Fast iteration without Docker
✅ Works on any OS with Python 3.13+

---

## Scripts Reference

All scripts work in both dev container and local environments. They automatically detect and use `.venv/` if present.

### `./scripts/bootstrap`

**Purpose:** One-time setup for local development

**What it does:**
- Creates `.venv/` virtual environment
- Upgrades pip
- Installs all dependencies from `requirements.txt`

**When to use:**
- First time setting up locally
- After cleaning your environment

**Example:**
```bash
./scripts/bootstrap
```

---

### `./scripts/setup`

**Purpose:** Install or update dependencies

**What it does:**
- Detects if `.venv/` exists and activates it
- Installs/updates dependencies from `requirements.txt`
- Works globally if no venv exists

**When to use:**
- After pulling new changes
- When `requirements.txt` is updated

**Example:**
```bash
./scripts/setup
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

```bash
# Auto-format and fix issues
./scripts/lint

# Check for remaining issues
git diff
```

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
1. Verify SDK is installed: `pip show airbeld-api-sdk`
2. Re-run setup: `./scripts/setup`
3. In dev container: restart container
4. Locally: re-run `./scripts/bootstrap`

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
   ./scripts/bootstrap
   ```

2. Manually activate and check:
   ```bash
   source .venv/bin/activate
   python --version  # Should be 3.13+
   pip list | grep airbeld
   ```

---

## Need Help?

- **Bug reports:** [GitHub Issues](https://github.com/Embio-Diagnostics/airbeld-ha/issues)
- **Questions:** [GitHub Discussions](https://github.com/Embio-Diagnostics/airbeld-ha/discussions)
- **Contributing:** See [CONTRIBUTING.md](CONTRIBUTING.md)

---

Happy coding! 🚀
