# HA compatibility record — task 11

Newest stable resolved once from PyPI `homeassistant` release JSON during the
initial H11 attempt (2026-10-15 UTC); the earlier attempt did not preserve the
exact timestamp. PyPI stable-release selection was reconfirmed at
**2026-10-15T23:35:36.328523Z**; this is a
recording timestamp, not a fabricated original resolution time. The selected
release is **2026.10.1**, per the orchestrator's correction decision. Stable
selection excludes PEP 440 prereleases, development releases and yanked releases.

| Environment | HA | Python | pytest HA plugin |
|---|---|---|---|
| Root (newest stable) | 2026.10.1 | 3.14 (executed 3.14.3; HA requires ≥3.14.2) | 0.13.372 |
| `ci/ha-min` (floor) | 2024.6.0 | 3.12 (executed 3.12.12) | 0.13.132 |

The integration project's `requires-python = ">=3.13.2"` is unchanged. Root dev
dependencies carry `requires-python >=3.14.2`; `.python-version` selects 3.14.
The separate floor project imports the component source without installing the
root project. This tests source compatibility, not root-project installability.

## Boundary findings and owner choices

| API needed by tasks 21/22 | HA 2024.6.0 | HA 2026.10.1 | Follow-up |
|---|---|---|---|
| `LocalOAuth2ImplementationWithPkce` | absent | present | Owner: implement a floor shim generating verifier/challenge and token exchange, or raise minimum to a release supplying it. Current component uses non-PKCE implementation at both ends (H3). |
| `httpx_client.get_async_client` | present | present | Use HA helper; no shim needed. |
| `SensorDeviceClass.PM4` | absent | present | Owner: floor shim uses no PM4 class (never PM10), or raise minimum to a release supplying PM4. |
| `issue_registry.async_create_issue` (repairs) | present | present | Repair plumbing is available at both ends. |
| `ConfigEntry.runtime_data` | available | available | Current component still uses `hass.data` (H4). |

No supported minimum is changed by this record. Missing floor APIs remain an
owner decision for tasks 21/22, not a guessed version-policy change.

### SDK 0.4.0 floor incompatibility

SDK metadata requires `httpx>=0.28.1`, `pydantic>=2.11.7`, `tenacity>=9.1.2`.
HA 2024.6 pins httpx 0.27.0. The floor test project explicitly overrides httpx
to 0.27.0 and uses a current pydantic (old pydantic broke this SDK's import).
It also pins josepy 1.14.0: acme 2.10.0 references `josepy.ComparableX509`, removed
in josepy 2. These are **test-environment compatibility overrides**, not evidence
that unmodified SDK metadata installs on HA 2024.6. The real SDK HTTP/parser path
passes the characterization tests under the override. Owner options: a
floor-compatible SDK requirement/artifact, or an explicit supported-floor change.
Tasks 21/22 must resolve this before claiming the advertised installation range.

## Validation evidence

HA APIs were imported in both isolated offline environments; characterization
and strict defects executed against both. Exact command outputs are in run
`smarthome-w4-oct16/results/H11-*`. The full repository gate remains the lane
harness's responsibility. H1–H7 are deliberately not fixed here.
