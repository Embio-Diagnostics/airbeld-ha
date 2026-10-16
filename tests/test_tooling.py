"""Exercise gate rejection paths and development routing without live services."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts import dev_bootstrap


@pytest.mark.parametrize("mode", ["local", "staging"])
def test_dev_bootstrap_routing(monkeypatch, mode):
    """The real bootstrap selects only the requested origin before HA starts."""
    monkeypatch.setenv("AIRBELD_DEV_MODE", mode)
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(
        dev_bootstrap.const, "DEFAULT_API_BASE", "https://api.airbeld.com"
    )
    monkeypatch.setattr(
        dev_bootstrap.integration, "DEFAULT_API_BASE", "https://api.airbeld.com"
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
    assert expected == dev_bootstrap.integration.DEFAULT_API_BASE
    assert calls == [(("homeassistant",), {"run_name": "__main__"})]
    assert sys.argv == ["hass", "--config", "/config"]


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
