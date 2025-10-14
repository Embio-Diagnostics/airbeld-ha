# Airbeld – Home Assistant Integration (Developer README)

This README is a practical, end-to-end guide for developing the **Airbeld** integration for Home Assistant using the **recommended workflow**:

* **One source-of-truth repo** (`airbeld-ha`) for the integration code.
* A **normal Home Assistant** instance (Docker) that bind-mounts this repo as a **custom component** (lives under `dev/` locally).
* A **Home Assistant Core fork** used only for Pull Requests to upstream. In local dev, the Core checkout points to the same code via a **symlink**. Before committing to the Core fork, you normalize files (e.g., remove `version` from `manifest.json`).

This keeps development fast, avoids submodule headaches, and cleanly separates product code from the upstream Core repository.

---

## Table of Contents

1. Goals & Architecture
2. Prerequisites
3. Repository Layout (recommended)
4. Create Standalone Repo (source of truth)
5. Run a “normal” Home Assistant via Docker (for testing)
6. Bind-mount the custom component
7. Fork Home Assistant Core & set remotes
8. Symlink the Core integration folder to your repo
9. Cloud Polling → Cloud Push (data path)
10. Auth0 OAuth2 (Application Credentials) – quick notes
11. Using the local SDK (unpublished)
12. Scaffold a Core-style integration (optional)
    12b. Scaffold Prompts Explained
13. Normalize & Copy for Core PR (script)
14. Git Workflow Cheat-Sheet
15. Team Onboarding Quickstart
16. FAQ & Troubleshooting

---

## 1) Goals & Architecture

* **UX:** Add Integration → **Airbeld** → user logs in with **Auth0** (OAuth2), selects tenant/location/sector, entities show up.
* **Data Path:** Start with ``(REST `/devices`, `/telemetry/latest`) using a `DataUpdateCoordinator`; later evolve to`` (WebSocket/SSE) from the Airbeld backend → instant updates.
* **No MQTT requirement inside HA:** Devices publish to **EMQX** → **Airbeld backend** handles ingestion; the HA integration talks to the backend only (poll/push). MQTT in HA can be optional later.

---

## 2) Prerequisites

* Windows + **WSL2** (Ubuntu/Debian) or Linux/macOS
* **Docker Desktop** (WSL2 backend on Windows)
* **VS Code** + extensions: Dev Containers, Python, YAML
* **Git**, `jq` (for JSON edits), optional `rsync`

---

## 3) Repository Layout (recommended)

Before cloning, create a working directory (e.g. `~/your-directory`). Inside it you will have three folders: your integration repo, your dev HA instance, and your Core fork.

```
~/your-directory/
├─ airbeld-ha/                    # ← GitHub repo (source of truth)
│  ├─ custom_components/
│  │  └─ airbeld/                 # integration code (manifest.json has "version")
│  └─ tools/                      # helper scripts (sync_to_core.sh, link_core.sh, etc.)
│
├─ dev/                           # ← Local directory (not a repo) with Docker HA
│  ├─ docker-compose.yml
│  └─ config/
│     └─ custom_components/
│
└─ core/                          # ← Fork of Home Assistant Core (GitHub repo)
   └─ homeassistant/
      └─ components/
         └─ airbeld → symlink to ~/your-directory/airbeld-ha/custom_components/airbeld
```

---

## 4) Create Standalone Repo (source of truth)

```bash
mkdir -p ~/your-directory
cd ~/your-directory
git clone git@github.com:Embio-Diagnostics/airbeld-ha.git
cd airbeld-ha

mkdir -p custom_components/airbeld tools

cat > custom_components/airbeld/manifest.json << 'JSON'
{
  "domain": "airbeld",
  "name": "Airbeld",
  "version": "0.1.0",
  "config_flow": true,
  "iot_class": "cloud_polling",
  "requirements": ["aiohttp>=3.9.0"],
  "codeowners": ["@Embio-Diagnostics"]
}
JSON

git add .
git commit -m "feat: initial Airbeld integration (custom component skeleton)"
```

---

## 5) Run a “normal” Home Assistant via Docker (for testing)

Create the `dev/` directory next to `airbeld-ha`:

```bash
mkdir -p ~/your-directory/dev/config/custom_components
cd ~/your-directory/dev
```

Minimal Docker run:

```bash
docker run -d \
  --name ha-test \
  --restart unless-stopped \
  -e TZ=Europe/Athens \
  -p 8123:8123 \
  -v ~/your-directory/dev/config:/config \
  ghcr.io/home-assistant/home-assistant:stable
```

Or via compose (`dev/docker-compose.yml`):

```yaml
services:
  homeassistant:
    container_name: ha-test
    image: ghcr.io/home-assistant/home-assistant:stable
    restart: unless-stopped
    ports:
      - "8123:8123"
    environment:
      - TZ=Europe/Athens
    volumes:
      - ./config:/config
      - ../airbeld-ha/custom_components/airbeld:/config/custom_components/airbeld:ro
```

---

## 6) Bind-mount the custom component

Mounted path:

```
~/your-directory/airbeld-ha/custom_components/airbeld → /config/custom_components/airbeld
```

Edit files in `airbeld-ha/...` and reload in HA.

---

## 7) Fork Home Assistant Core & set remotes

```bash
cd ~/your-directory/
git clone git@github.com:<you>/core.git  # fork of home-assistant/core
cd core
git remote add upstream https://github.com/home-assistant/core.git
git fetch upstream
git checkout -B dev upstream/dev
git push -u origin dev
```

---

## 8) Symlink the Core integration folder to your repo

```bash
cd ~/your-directory/core/homeassistant/components
[ -e airbeld ] && mv airbeld ../airbeld.bak.$(date +%s)
ln -s ~/your-directory/airbeld-ha/custom_components/airbeld airbeld
```

---

## 9) Cloud Polling → Cloud Push (data path)

* **Phase A – cloud\_polling:** REST endpoints polled every 15–30s.
* **Phase B – cloud\_push:** WebSocket/SSE to HA → instant updates.
* **MQTT stays internal** (device ↔ backend).

---

## 10) Auth0 OAuth2 (Application Credentials)

* Use HA's `application_credentials` framework.
* Users add credentials in HA, then log in to Airbeld.

---

## 11) Using the Airbeld SDK (from PyPI)

The integration uses the `airbeld-api-sdk` package published on PyPI. Home Assistant will automatically install it based on the `requirements` field in `manifest.json`.

### Published Package

* **Package name:** `airbeld-api-sdk`
* **PyPI page:** https://pypi.org/project/airbeld-api-sdk/
* **Current version:** 0.2.0
* **Import statement:** `from airbeld import AirbeldClient`

### Automatic Installation

Home Assistant automatically installs dependencies listed in `manifest.json`:

```json
{
  "requirements": ["airbeld-api-sdk>=0.2.0"]
}
```

When the integration is loaded, HA will:
1. Check if `airbeld-api-sdk` is installed
2. Install it from PyPI if missing or outdated
3. Import the module for use by the integration

### Local SDK Development (Optional)

If you're actively developing the SDK alongside the integration:

1. **Clone the official SDK repo** as a sibling directory:

```bash
cd ~/your-directory
git clone git@github.com:Embio-Diagnostics/airbeld-api-sdk.git
```

This gives you:
```
~/your-directory/
├── airbeld-ha/           # This integration repo
├── airbeld-api-sdk/      # Official SDK repo
├── core/                 # HA Core fork
└── dev/                  # Docker HA instance
```

2. **Mount the SDK** in `dev/docker-compose.yml`:

```yaml
volumes:
  - ./config:/config
  - ../airbeld-ha/custom_components/airbeld:/config/custom_components/airbeld:ro
  - ../airbeld-api-sdk:/usr/src/airbeld-api-sdk:ro
```

3. **Install in editable mode** inside the container:

```bash
docker exec ha-test pip install -e /usr/src/airbeld-api-sdk
```

4. **Remember to update `manifest.json`** when publishing new SDK versions to PyPI

### Troubleshooting

* **ModuleNotFoundError: airbeld** → Check HA logs; HA should auto-install from PyPI
* **Wrong SDK version** → Update `requirements` in `manifest.json` and restart HA
* **SDK changes not reflecting** → If using local editable install, restart container

---

## 12) Scaffold a Core-style integration (optional)

```bash
python3 -m script.scaffold integration
```

Follow prompts.

---

## 12b) Scaffold Prompts Explained

When running `python3 -m script.scaffold integration`, you’ll be asked a series of questions. Below are the recommended answers for Airbeld and explanations:

| Prompt                                                                               | Example Answer       | Explanation                                                                               |
| ------------------------------------------------------------------------------------ | -------------------- | ----------------------------------------------------------------------------------------- |
| **What is the domain?**                                                              | `airbeld`            | Unique identifier for the integration (lowercase, no spaces). Must match the folder name. |
| **What is the name of your integration?**                                            | `Airbeld`            | Human-readable name shown in HA UI.                                                       |
| **What is your GitHub handle?**                                                      | `@Embio-Diagnostics` | Must start with `@`. This appears in `manifest.json` as `codeowners`.                     |
| **What PyPI package and version do you depend on?**                                  | *leave blank*        | Only fill if you plan to publish a Python SDK to PyPI. For now we use built-in `aiohttp`. |
| **How will your integration gather data?**                                           | `cloud_polling`      | Phase A: Use REST API polling. Later we can move to `cloud_push` (WebSocket/SSE).         |
| **Does Home Assistant need the user to authenticate to control the device/service?** | `yes`                | Required: users authenticate via Auth0 OAuth2.                                            |
| **Is the device/service discoverable on the local network?**                         | `no`                 | Devices talk via backend, not LAN discovery.                                              |
| **Is this a helper integration?**                                                    | `no`                 | Helper integrations are internal tools like input\_booleans. Ours is a real integration.  |
| **Can the user authenticate the device using OAuth2?**                               | `yes`                | We rely on Auth0 OAuth2 Application Credentials.                                          |

These answers scaffold:

* `manifest.json` with `config_flow` and `iot_class`.
* `application_credentials.py` and `config_flow.py` with OAuth2 support.
* Test stubs in `tests/components/airbeld/`.

---

## 13) Normalize & Copy for Core PR (script)

See `tools/sync_to_core.sh` – strips `version` from manifest and copies to Core.

---

## 14) Git Workflow Cheat-Sheet

```bash
# Standalone repo (your integration code)
cd ~/your-directory/airbeld-ha
git push -u origin main

# Core fork (for PRs)
cd ~/your-directory/core
git fetch upstream
git checkout dev
git rebase upstream/dev
~/your-directory/airbeld-ha/tools/sync_to_core.sh
git checkout -b feature/airbeld
git add homeassistant/components/airbeld
git commit -m "Airbeld: initial integration"
git push origin feature/airbeld
```

---

## 15) Team Onboarding Quickstart

For new developers joining the project:

1. **Prepare directory structure:**

   ```bash
   mkdir -p ~/your-directory
   cd ~/your-directory
   ```
2. **Clone the repo:**

   ```bash
   git clone git@github.com:Embio-Diagnostics/airbeld-ha.git
   ```
3. **Set up dev HA instance:**

   ```bash
   mkdir -p dev/config
   cd dev
   cp ../airbeld-ha/docker-compose.example.yml docker-compose.yml
   docker compose up -d
   ```

   → Open [http://localhost:8123](http://localhost:8123)
4. **Edit integration code:** in `airbeld-ha/custom_components/airbeld/`
5. **Reload:** HA → Developer Tools → YAML → Reload custom integrations (or restart container).
6. **Fork HA Core** (only if you need to make PRs upstream).
7. **Run symlink script:**

   ```bash
   ./tools/link_core.sh
   ```
8. **Prepare PR:** run `tools/sync_to_core.sh` then push branch to your fork.

With this setup, every dev works in their own `dev/` and `core/` folders, but shares the same `airbeld-ha` repo.

---

## 16) FAQ & Troubleshooting

* **Q: My component isn’t detected?** Check `manifest.json` has `"version"` in `airbeld-ha` (custom). Restart HA container.
* **Q: Core rejects **\`\`**?** Strip via sync script.
* **Q: Should MQTT be inside integration?** No, keep it backend-side.
* **Q: Devcontainer vs Docker?** Devcontainer is for Core PR prep; Docker is for user-like testing.

---

## Repo Diagram

``` mermaid
graph TD;
  subgraph Local Dev Environment
    A[airbeld-ha GitHub repo] --> B[dev/ Docker HA, local only]
    A --> C[tools/ helper scripts]
    A --> D[core HA fork, GitHub repo]
  end

  B -->|bind-mount| A
  D -->|symlink| A
```

---

Happy hacking! Iterate in `airbeld-ha`, test live in `dev/`, and sync to your Core fork only when you’re ready for review.
