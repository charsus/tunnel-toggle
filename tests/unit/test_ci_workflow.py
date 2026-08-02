"""Tests for the GitHub Actions continuous-integration workflow."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
SETUP_PYTHON_SHA = "5fda3b95a4ea91299a34e894583c3862153e4b97"

ACTION_REFERENCE_PATTERN = re.compile(
    r"^\s*uses:\s+[^@\s]+@([0-9a-f]+)",
    flags=re.MULTILINE,
)


def load_workflow() -> str:
    """Return the tracked CI workflow text."""
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_ci_workflow_exists() -> None:
    """The repository should provide its expected CI workflow."""
    assert WORKFLOW_PATH.is_file()


def test_ci_uses_safe_events_and_read_only_permissions() -> None:
    """CI should avoid privileged pull-request execution."""
    workflow = load_workflow()

    assert "\n  push:\n" in workflow
    assert "\n  pull_request:\n" in workflow
    assert "pull_request_target" not in workflow
    assert "workflow_run" not in workflow
    assert "permissions:\n  contents: read\n" in workflow


def test_ci_actions_are_pinned_to_expected_commits() -> None:
    """External actions should use reviewed immutable revisions."""
    workflow = load_workflow()
    references = ACTION_REFERENCE_PATTERN.findall(workflow)

    assert references == [
        CHECKOUT_SHA,
        SETUP_PYTHON_SHA,
    ]
    assert all(len(reference) == 40 for reference in references)


def test_ci_checkout_does_not_persist_credentials() -> None:
    """Quality jobs should not retain the repository token."""
    workflow = load_workflow()

    assert "persist-credentials: false" in workflow


def test_ci_covers_supported_baseline_and_development_python() -> None:
    """CI should exercise the minimum and primary Python versions."""
    workflow = load_workflow()

    assert '- "3.11"' in workflow
    assert '- "3.13"' in workflow


def test_ci_runs_the_canonical_project_gate() -> None:
    """CI should reuse the same checks developers run locally."""
    workflow = load_workflow()

    assert "QT_QPA_PLATFORM: offscreen" in workflow
    assert "run: ./scripts/check.sh" in workflow
