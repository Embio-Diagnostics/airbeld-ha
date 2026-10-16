# Dependabot recommendations (task 11 Evidence)

Read-only `gh pr list --repo Embio-Diagnostics/airbeld-ha --state open` on
2026-10-15 UTC returned these eight bot PRs. No comments or mutations were made.
Owner rebase/review and post-push CI are required before any disposition.

| PR | Proposal | Recommendation and reason |
|---|---|---|
| [15](https://github.com/Embio-Diagnostics/airbeld-ha/pull/15) | home-assistant/actions hash bump | Supersede after this packet: hassfest now uses a pinned official container digest in the shared local/CI gate. |
| [14](https://github.com/Embio-Diagnostics/airbeld-ha/pull/14) | checkout 5.0.0 → 6.0.1 | Review/rebase and merge after green CI; independent action runtime upgrade, not included here. |
| [13](https://github.com/Embio-Diagnostics/airbeld-ha/pull/13) | setup-python 6.0.0 → 6.1.0 | Review/rebase and merge after green CI; independent runner action update, retain new Python matrix. |
| [9](https://github.com/Embio-Diagnostics/airbeld-ha/pull/9) | Ruff 0.14.0 → 0.14.2 | Superseded: root dev group already pins 0.14.2, with exported lock. |
| [5](https://github.com/Embio-Diagnostics/airbeld-ha/pull/5) | PyYAML 6.0.2 → 6.0.3 | Superseded for newest (HA lock resolves 6.0.3); do not apply wholesale to floor where HA pins 6.0.1. |
| [4](https://github.com/Embio-Diagnostics/airbeld-ha/pull/4) | awesomeversion 25.5.0 → 25.8.0 | Superseded for newest (HA pins 25.8.0); floor HA pins 24.2.0 and stays isolated. |
| [3](https://github.com/Embio-Diagnostics/airbeld-ha/pull/3) | pyOpenSSL 25.1.0 → 25.3.0 | Superseded for newest (HA resolves 26.4.0); floor HA pins 24.1.0. Do not override HA's constraints via a requirements-only bump. |
| [1](https://github.com/Embio-Diagnostics/airbeld-ha/pull/1) | ulid-transform 1.4.0 → 1.5.2 | Superseded for newest (HA resolves 2.2.9); floor HA pins 0.9.0. Update the upstream HA pin as a tested unit, not its transitive requirements individually. |

`requirements.txt` is exported from `uv.lock`, not independently curated; direct
requirements-only PRs should be replaced by source manifest/lock updates.
