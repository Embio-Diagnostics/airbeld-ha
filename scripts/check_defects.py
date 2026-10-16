"""Validate the HA defect manifest against collected markers and real failures."""

import argparse
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml

EXPECTED = {"H1": 21, "H2": 21, "H3": 21, "H4": 21, "H5": 22, "H6": 22, "H7": 22}


class Recorder:
    """Capture pytest items and original exception types, not formatted messages."""

    def __init__(self) -> None:
        """Initialize capture storage for one pytest invocation."""
        self.items = {}
        self.failures = {}

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        """Retain exact node ids and effective markers."""
        self.items = {item.nodeid: item for item in items}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(
        self, item: pytest.Item, call: pytest.CallInfo
    ) -> Generator[None]:
        """Record only failures from the test body."""
        yield
        if call.when == "call" and call.excinfo is not None:
            self.failures[item.nodeid] = call.excinfo.type


def main() -> None:  # noqa: PLR0912 — explicit manifest-state validation branches
    """Return nonzero for stale, malformed, or falsely unfixed records."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-unfixed", action="store_true")
    parser.add_argument("--require-none-unfixed", action="store_true")
    args = parser.parse_args()
    entries = yaml.safe_load(Path("tests/defects.yaml").read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise SystemExit("defects: manifest must be a list")
    ids = [entry.get("id") for entry in entries]
    if len(ids) != len(set(ids)) or set(ids) != set(EXPECTED):
        raise SystemExit("defects: missing, duplicate or unknown id")
    recorder = Recorder()
    code = pytest.main(["--collect-only", "-q", "tests"], plugins=[recorder])
    if code != 0:
        raise SystemExit(f"defects: collection failed ({code})")
    unfixed = []
    fixed = []
    for entry in entries:
        node = entry.get("test")
        state = entry.get("state")
        if entry.get("owner_task") != EXPECTED[entry["id"]]:
            raise SystemExit(f"defects: wrong owner for {entry['id']}")
        if state == "external":
            if node or not entry.get("gate"):
                raise SystemExit("defects: external requires a named gate, no test")
            continue
        if state not in {"unfixed", "fixed", "invariant"} or node not in recorder.items:
            raise SystemExit(
                f"defects: invalid state or missing test for {entry['id']}"
            )
        marker = recorder.items[node].get_closest_marker("xfail")
        if state == "unfixed":
            if (
                marker is None
                or marker.args
                or marker.kwargs.get("condition", True) is not True
                or marker.kwargs.get("strict") is not True
                or marker.kwargs.get("raises") is not AssertionError
            ):
                raise SystemExit(
                    f"defects: {node} needs unconditional strict AssertionError xfail"
                )
            unfixed.append(node)
        else:
            if marker is not None:
                raise SystemExit(f"defects: {node} must not be xfailed")
            fixed.append(node)
    if args.require_none_unfixed and unfixed:
        raise SystemExit("defects: unfixed entries remain")
    if fixed and pytest.main(["-q", *fixed]) != 0:
        raise SystemExit("defects: fixed/invariant tests did not pass")
    if args.verify_unfixed and unfixed:
        probe = Recorder()
        code = pytest.main(["-q", "--runxfail", *unfixed], plugins=[probe])
        if code != 1 or any(
            probe.failures.get(node) is not AssertionError for node in unfixed
        ):
            raise SystemExit(
                "defects: an unfixed test did not fail with AssertionError"
            )
    print(f"defects: {len(entries)} entries valid; {len(unfixed)} unfixed verified")


if __name__ == "__main__":
    main()
