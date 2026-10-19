# HA compatibility record — v2 candidate

The owner raised the minimum to **2025.10.0** on 2026-10-19. No compatibility
shims are used. Users on older Home Assistant must keep **v0.1.2 (v1)**.

| Environment | HA | Python | pytest HA plugin |
|---|---|---|---|
| Root (newest stable selected for this wave) | 2026.10.1 | 3.14 (executed 3.14.3; requires ≥3.14.2) | 0.13.372 |
| `ci/ha-min` (floor) | 2025.10.0 | 3.13 (executed 3.13.12; requires ≥3.13.2) | 0.13.285 |

The floor project imports the same component source without installing the root
project. Its Python constraint is `>=3.13.2,<3.14`. The old test-only httpx and
pydantic overrides and josepy 1.14.0 pin are removed: the floor's native httpx
0.28.1, pydantic 2.11.9 and josepy 2.2.0 satisfy this environment.
The floor additionally pins pycares 4.11.0: its aiodns 3.5.0 imports result
classes removed in pycares 5. Without that transitive compatibility pin the
floor's aiohttp import fails before tests can collect.

Both HA versions provide `LocalOAuth2ImplementationWithPkce`,
`httpx_client.get_async_client`, repairs and `ConfigEntry.runtime_data`. PM4
first appears at this floor and is used unconditionally for PM4 sensors.
Device and sensor identities include environment, Auth0 subject and device uid;
each entry owns its own device rows on both HA ends. No deprecated device-registry
add/remove-config-entry arguments are used.

## SDK artifact and release installation

Both uv projects pin the real **airbeld-api-sdk 1.0.0 candidate** by wheel path
and lockfile SHA256 under `vendor/wheels/`:
`b001f608d7c729056a27a40a031726a9255803f5ffb0cf39c83241ae15a2a8d3`.
CI and development preinstall this wheel. The HA manifest names
`airbeld-api-sdk==1.0.0`; HACS installs it from **PyPI at the coordinated release
(task 35)**, when this exact artifact is published. The candidate is not yet a
public-PyPI installation. No production deployment is part of this packet.

## Upgrade changelog

- Users on Home Assistant older than 2025.10.0 keep **v0.1.2 (v1)**.
- Version-1 config entries bump to version 2 immediately. Registry completion
  waits for authenticated v2 inventory and the SDK legacy-id resolver, not the
  inventory's `legacyId` field. A journal and per-id completion markers allow
  interrupted rewrites to resume without recreating entities.
  HA's delayed storage writes are flushed in order: source journal, device and
  entity registries, then each completion marker. HA exposes no public immediate
  config-entry/registry flush, so the narrowly scoped storage calls are tested
  on both supported ends.
- Ordinary entity IDs, names, areas, disabled state and recorder history are
  preserved by updating unique IDs and device identifiers on the existing rows.
  Original VOC/NOx AQI rows retain their unique IDs and entity IDs, are disabled
  (existing user-disabled state is kept), and keep their recorder history and
  statistics. Separate VOC/NOx index entities use `_index` keys, no device class,
  and fresh recorder statistics. This is the explicit exception to entity-ID
  preservation. PM4 keeps its existing entity ID, unit and statistic.
- Unresolved legacy IDs remain untouched and unavailable, appear in diagnostics,
  and are removable only through the user's repair confirmation.
- Auth failures request reauthentication; backend failures retry setup. A different
  subject cannot reauthenticate an existing entry. Duplicate accounts in the same
  environment keep the oldest entry, ordered by creation time then entry ID.
  Legacy subjects are recovered from Auth0 RS256 signatures with issuer and
  audience verification. An expired signed token may bind the original account
  identity, but never authorizes polling; fresh sign-ins use authenticated userinfo.
- H1–H7 are fixed. The gate rejects any remaining unfixed defect.
- Devices and metrics are discovered on coordinator updates, using the existing
  180-second poll. Three successful complete inventory absences remove only the
  owning entry's rows; failed or invalid inventory fetches do not count. Telemetry
  failures do not invalidate a successful inventory. A present device resets the
  counter even when offline/stale; offline/stale sensors show unavailable.
- Known sensors use translated entity names, measurement state classes and native
  units. Local metadata checks verify `brand/icon.png` and `brand/logo.png` PNGs;
  these checks are not upstream HACS validation.

## Validation

Targeted offline tests use the real candidate SDK with a fixture backend and
seeded HA registries at both ends. Evidence lives in the run
`smarthome-w6-oct19/results/HA1-*` and `HA2-*`. The full repository gate is the lane harness's
responsibility; the live staging upgrade is task 32.
