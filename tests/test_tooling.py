"""Exercise gate rejection paths and development routing without live services."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import yaml
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.airbeld import async_setup_entry
from custom_components.airbeld.config_flow import OAuth2FlowHandler
from custom_components.airbeld.const import DOMAIN
from scripts import dev_bootstrap


@pytest.mark.parametrize("mode", ["local", "staging"])
async def test_dev_bootstrap_routing(hass, monkeypatch, mode):
    """The real bootstrap selects only the requested origin before HA starts."""
    monkeypatch.setenv("AIRBELD_DEV_MODE", mode)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(
        dev_bootstrap.const, "DEFAULT_API_BASE", "https://api.airbeld.com"
    )
    calls = []
    monkeypatch.setattr(
        dev_bootstrap.runpy,
        "run_module",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    monkeypatch.setattr(sys, "argv", [])
    dev_bootstrap.main()
    expected = (
        "https://api.airbeld.com"
        if mode == "local"
        else (
            "https://airbeld-staging-api-fmb3htfqfua5hhgk.westeurope-01.azurewebsites.net"
        )
    )
    assert calls == [(("homeassistant",), {"run_name": "__main__"})]
    assert sys.argv == ["hass", "--config", "/config"]

    # Bootstrap starts HA without supplying credentials; onboarding selects and
    # persists the origin through the flow's real environment resolver.
    flow = OAuth2FlowHandler()
    flow.hass = hass
    flow.context = {"source": "user"}
    monkeypatch.setattr(
        "custom_components.airbeld.config_flow.async_subject",
        AsyncMock(return_value="auth0|dev"),
    )
    result = await flow.async_oauth_create_entry(
        {
            "auth_implementation": DOMAIN,
            "token": {"access_token": "onboarding-only", "expires_at": 9999999999},
        }
    )
    assert result["data"]["environment"] == expected
    entry = MockConfigEntry(domain=DOMAIN, version=2, data=result["data"])
    entry.add_to_hass(hass)
    object.__setattr__(entry, "state", ConfigEntryState.SETUP_IN_PROGRESS)
    requests = []

    def respond(request):
        assert str(request.url).startswith(expected + "/")
        requests.append(request)
        assert request.url.path == "/api/v2/devices/"
        return httpx.Response(200, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as shared:
        monkeypatch.setattr(
            "custom_components.airbeld.get_async_client", lambda _hass: shared
        )
        monkeypatch.setattr(
            hass.config_entries, "async_forward_entry_setups", AsyncMock()
        )
        assert await async_setup_entry(hass, entry)
        assert entry.runtime_data.client.base_url.rstrip("/") == expected + "/api/v2"
        assert len(requests) == 1


def test_dev_bootstrap_rejects_unknown(monkeypatch):
    """A misspelled mode cannot silently run the production integration."""
    monkeypatch.setenv("AIRBELD_DEV_MODE", "mistyped")
    with pytest.raises(SystemExit, match="Unknown development mode"):
        dev_bootstrap.main()


@pytest.mark.parametrize(
    "defect", ["valid", "missing", "unknown", "marker", "wrong_failure", "passing"]
)
def test_defect_checker_rejection(tmp_path, defect):
    """Run the actual checker against independent miniature manifests/tests."""
    root = Path(__file__).resolve().parents[1]
    tests = tmp_path / "tests"
    tests.mkdir()
    entries = []
    source = "import pytest\n"
    for number in range(1, 8):
        entries.append(
            {
                "id": f"H{number}",
                "owner_task": 21 if number <= 4 else 22,
                "state": "unfixed",
                "test": f"tests/test_probe.py::test_h{number}",
            }
        )
        marker = "strict=True, raises=AssertionError"
        body = "assert False"
        if number == 1:
            if defect == "marker":
                marker = "strict=False, raises=AssertionError"
            elif defect == "wrong_failure":
                body = "raise ValueError('not the defect')"
            elif defect == "passing":
                body = "assert True"
        source += f"@pytest.mark.xfail({marker})\ndef test_h{number}():\n    {body}\n"
    if defect == "missing":
        entries.pop()
    elif defect == "unknown":
        entries[0]["id"] = "H8"
    (tests / "defects.yaml").write_text(yaml.safe_dump(entries), encoding="utf-8")
    (tests / "test_probe.py").write_text(source, encoding="utf-8")
    env = dict(
        os.environ,
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PYTEST_ADDOPTS="-p no:cacheprovider",
    )
    result = subprocess.run(  # noqa: S603 — fixed interpreter and repository checker
        [sys.executable, str(root / "scripts/check_defects.py"), "--verify-unfixed"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if defect == "valid":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "7 unfixed verified" in result.stdout
    else:
        assert result.returncode != 0, result.stdout + result.stderr
        expected = {
            "missing": "missing, duplicate or unknown id",
            "unknown": "missing, duplicate or unknown id",
            "marker": "needs unconditional strict AssertionError xfail",
            "wrong_failure": "did not fail with AssertionError",
            "passing": "did not fail with AssertionError",
        }[defect]
        assert expected in result.stdout + result.stderr
