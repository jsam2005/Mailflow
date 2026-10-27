"""Cross-platform path and Windows termination helpers (run on any OS)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from launcher.manager import ProcessManager, setup_hint, venv_python


def test_venv_python_uses_scripts_on_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    path = venv_python(tmp_path / "backend")
    assert path.as_posix().endswith("backend/.venv/Scripts/python.exe")


def test_venv_python_uses_bin_on_posix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    path = venv_python(tmp_path / "backend")
    assert path.as_posix().endswith("backend/.venv/bin/python")


def test_setup_hint_mentions_windows_cmd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert "Setup-MailFlow-Windows.cmd" in setup_hint()


def test_validate_prerequisites_accepts_space_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "Mail Flow Project"
    backend = root / "backend"
    frontend = root / "frontend"
    if sys.platform == "win32":
        py = backend / ".venv" / "Scripts" / "python.exe"
    else:
        py = backend / ".venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text("", encoding="utf-8")
    (frontend / "node_modules").mkdir(parents=True)
    (root / ".env").write_text("ENVIRONMENT=development\n", encoding="utf-8")

    mgr = ProcessManager(root, browser_opener=lambda _u: None)
    # Should not raise.
    mgr._validate_prerequisites()


def test_windows_terminate_uses_pid_taskkill(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):  # noqa: ANN001, ANN003
        calls.append(list(args))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr("launcher.manager.subprocess.run", fake_run)

    ProcessManager._terminate_windows_tree(4242, force=True)
    assert calls
    assert calls[0][:3] == ["taskkill", "/PID", "4242"]
    assert "/T" in calls[0]
    assert "/F" in calls[0]
    # Must never target process image names globally.
    joined = " ".join(calls[0]).lower()
    assert "python.exe" not in joined
    assert "node.exe" not in joined
