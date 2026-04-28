"""Root conftest.py — fixtures and pytest plugin for the IBD agent test suite.

When copied into /assets/<asset-name> this file:
  - provides shared fixtures used by prebuilt_tests/ (agent path)
  - registers custom markers
  - collects per-test results and writes test_report.json on session finish
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_ROOT = Path(__file__).parent

# Ordered list of (marker, display label, result-bucket key).
# Tests with no marker from this list fall into the "agent_tests" bucket.
# The structure marker must only be used by tests inside the prebuilt_tests/ module.
SECTIONS: list[tuple[str, str, str]] = [
    ("structure", "Structure Tests", "structure"),
    ("", "Agent Tests", "agent_tests"),
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def agent_path() -> Path:
    """Root directory of the generated agent."""
    return AGENT_ROOT


@pytest.fixture(scope="session")
def agent_app_path(agent_path: Path) -> Path:
    """Path to the agent's app/ package directory."""
    return agent_path / "app"


@pytest.fixture(scope="session")
def add_agent_to_path(agent_app_path: Path):
    """Add app/ to sys.path so agent modules can be imported directly."""
    s = str(agent_app_path)
    if s not in sys.path:
        sys.path.insert(0, s)
    yield
    if s in sys.path:
        sys.path.remove(s)


# ---------------------------------------------------------------------------
# pytest hooks — configuration
# ---------------------------------------------------------------------------


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "structure: Tests for file and module structure")


# ---------------------------------------------------------------------------
# Result collection
# ---------------------------------------------------------------------------

_results: dict[str, list[dict[str, Any]]] = {
    "structure": [],
    "agent_tests": [],
}


def _section_for(item: pytest.Item) -> str:
    marker_names = {m.name for m in item.iter_markers()}
    for marker, _label, key in SECTIONS[:-1]:  # skip the catch-all "agent_tests" entry
        if marker in marker_names:
            return key
    return "agent_tests"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo
) -> pytest.Generator:
    outcome = yield
    report: pytest.TestReport = outcome.get_result()

    if report.when == "call" or (report.when == "setup" and report.skipped):
        outcome_str = (
            "passed" if report.passed else ("failed" if report.failed else "skipped")
        )
        _results[_section_for(item)].append(
            {
                "name": report.nodeid.split("::")[-1],
                "outcome": outcome_str,
                "duration": round(getattr(report, "duration", 0.0), 4),
            }
        )


# ---------------------------------------------------------------------------
# Full-run detection
# ---------------------------------------------------------------------------


def _is_full_run(config: pytest.Config) -> bool:
    """Return True only when no narrowing filters are active.

    A partial run is detected when any of the following are present:
      -k  keyword filter
      -m  marker filter
      --lf  last-failed
      :: in a positional arg (node-id)
      a positional path that points *inside* a configured testpath dir
      a positional set that is a strict subset of the configured testpath roots
    """
    opt = config.option
    if getattr(opt, "keyword", ""):
        return False
    if getattr(opt, "markexpr", ""):
        return False
    if getattr(opt, "lf", False):
        return False

    positional = [
        a for a in config.invocation_params.args if not str(a).startswith("-")
    ]

    if not positional:
        return True  # no args → full suite via testpaths ini

    if any("::" in str(a) for a in positional):
        return False  # node-id selection

    rootdir = Path(config.rootdir)
    configured = {(rootdir / tp).resolve() for tp in config.getini("testpaths")}
    supplied = {
        (Path(config.invocation_params.dir) / str(a)).resolve() for a in positional
    }

    if supplied == configured:
        return True
    if supplied < configured:
        return False  # subset of testpath roots

    for sp in supplied:
        for tp in configured:
            if sp.is_relative_to(tp) and sp != tp:
                return False  # path inside a testpath dir

    return True


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Write test_report.json after a full run; skip for partial runs."""
    if not _is_full_run(session.config):
        return

    sections_out = []
    for _marker, label, key in SECTIONS:
        tests = _results[key]
        total = len(tests)
        passed = sum(1 for t in tests if t["outcome"] == "passed")
        failed = sum(1 for t in tests if t["outcome"] == "failed")
        skipped = sum(1 for t in tests if t["outcome"] == "skipped")

        section: dict[str, Any] = {
            "name": label,
            "marker": key,
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "score": round(passed / total * 100, 2) if total else 0.0,
            "tests": tests,
        }

        if key == "agent_tests":
            cov_path = AGENT_ROOT / "coverage.json"
            if cov_path.exists():
                try:
                    cov_data = json.loads(cov_path.read_text())
                    section["coverage"] = round(
                        cov_data["totals"]["percent_covered"], 2
                    )
                except Exception:
                    pass
            else:
                print(f"Coverage not found: {cov_path}")
            if total == 0:
                section["skipped_reason"] = "No agent tests found"

        sections_out.append(section)

    total_all = sum(s["total"] for s in sections_out)
    passed_all = sum(s["passed"] for s in sections_out)
    failed_all = sum(s["failed"] for s in sections_out)
    overall_score = round(passed_all / total_all * 100, 2) if total_all else 0.0

    report_path = AGENT_ROOT / "test_report.json"
    report_path.write_text(
        json.dumps(
            {
                "summary": {
                    "total": total_all,
                    "passed": passed_all,
                    "failed": failed_all,
                    "score": overall_score,
                },
                "sections": sections_out,
            },
            indent=2,
        )
    )
    print(f"\nReport written to {report_path}")
