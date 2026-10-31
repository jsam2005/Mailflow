"""Safe MailFlow local updater.

Fetches a trusted GitHub ref into a staging directory, builds there, stops
launcher-owned services, backs up config/DB, migrates once, syncs code into the
install root (preserving .env/storage), then restarts.

Never force-pushes, never overwrites .env, never drops the client database.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from launcher.manager import ProcessManager, LauncherStatus, venv_python
from launcher.update_config import (
    UpdateConfig,
    ensure_mailflow_dirs,
    load_installed,
    load_update_config,
    mailflow_dir,
    save_installed,
    should_preserve_relative,
)
from launcher.update_state import UpdateLockError, UpdateOperationState, UpdateStateStore

RunFn = Callable[..., subprocess.CompletedProcess[str]]
FetchBytesFn = Callable[[str], bytes]


@dataclass
class CheckResult:
    ok: bool
    update_available: bool
    installed_commit: str | None
    available_commit: str | None
    available_short: str | None
    release_ref: str
    message: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "update_available": self.update_available,
            "installed_commit": self.installed_commit,
            "available_commit": self.available_commit,
            "available_short": self.available_short,
            "release_ref": self.release_ref,
            "message": self.message,
            "error": self.error,
        }


class MailFlowUpdater:
    def __init__(
        self,
        install_root: Path,
        manager: ProcessManager,
        *,
        runner: RunFn | None = None,
        fetcher: FetchBytesFn | None = None,
    ) -> None:
        self.install_root = install_root.resolve()
        self.manager = manager
        self.store = UpdateStateStore(self.install_root)
        self._run = runner or self._default_run
        self._fetch_bytes = fetcher or self._default_fetch_bytes
        ensure_mailflow_dirs(self.install_root)

    def snapshot_update(self) -> dict[str, Any]:
        state = self.store.read()
        installed = load_installed(self.install_root)
        cfg = load_update_config(self.install_root)
        return {
            "busy": self.store.is_busy(),
            "phase": state.phase,
            "message": state.message,
            "error": state.error,
            "progress": state.progress[-12:],
            "installed": installed,
            "release_ref": cfg.release_ref,
            "remote_url": cfg.remote_url,
            "target_commit": state.target_commit,
            "target_short": state.target_short,
            "backup_path": state.backup_path,
            "migration_revision_before": state.migration_revision_before,
        }

    def check_for_updates(self) -> CheckResult:
        cfg = load_update_config(self.install_root)
        installed = load_installed(self.install_root)
        installed_commit = installed.get("commit") or self._detect_local_commit()

        try:
            available = self._resolve_remote_commit(cfg)
        except OfflineError as exc:
            return CheckResult(
                ok=False,
                update_available=False,
                installed_commit=installed_commit,
                available_commit=None,
                available_short=None,
                release_ref=cfg.release_ref,
                message="Could not reach GitHub.",
                error=str(exc),
            )
        except AuthError as exc:
            return CheckResult(
                ok=False,
                update_available=False,
                installed_commit=installed_commit,
                available_commit=None,
                available_short=None,
                release_ref=cfg.release_ref,
                message="GitHub authentication/authorization failed.",
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                ok=False,
                update_available=False,
                installed_commit=installed_commit,
                available_commit=None,
                available_short=None,
                release_ref=cfg.release_ref,
                message="Update check failed.",
                error=str(exc),
            )

        available_short = available[:7]
        if installed_commit and installed_commit.startswith(available):
            same = True
        elif installed_commit and available.startswith(installed_commit):
            same = True
        else:
            same = bool(installed_commit) and installed_commit == available

        if same:
            msg = f"Already up to date ({available_short}) on {cfg.release_ref}."
            state = self.store.read()
            state.phase = "no_update"
            state.message = msg
            state.error = None
            state.target_commit = available
            state.target_short = available_short
            self.store.write(state)
            return CheckResult(
                ok=True,
                update_available=False,
                installed_commit=installed_commit or available,
                available_commit=available,
                available_short=available_short,
                release_ref=cfg.release_ref,
                message=msg,
            )

        msg = (
            f"Update available: {available_short} on {cfg.release_ref}"
            + (f" (installed {installed_commit[:7]})" if installed_commit else " (no installed marker yet)")
        )
        state = self.store.read()
        state.phase = "checked"
        state.message = msg
        state.error = None
        state.target_commit = available
        state.target_short = available_short
        self.store.write(state)
        if not installed_commit:
            save_installed(
                self.install_root,
                {
                    "commit": available if same else (installed_commit or "unknown"),
                    "short": (installed_commit or "unknown")[:7],
                    "note": "Marker missing; check compared against remote only",
                    "recorded_at": _iso_now(),
                },
            )
        return CheckResult(
            ok=True,
            update_available=True,
            installed_commit=installed_commit,
            available_commit=available,
            available_short=available_short,
            release_ref=cfg.release_ref,
            message=msg,
        )

    def apply_update(self, *, target_commit: str | None = None) -> dict[str, Any]:
        if self.manager.status in {LauncherStatus.STARTING, LauncherStatus.STOPPING}:
            return {
                "ok": False,
                "error": "Cannot update while Start/Stop is in progress. Wait, then try again.",
                **self.snapshot_update(),
            }

        try:
            state = self.store.acquire()
        except UpdateLockError as exc:
            return {"ok": False, "error": str(exc), **self.snapshot_update()}

        cfg = load_update_config(self.install_root)
        installed = load_installed(self.install_root)
        previous = installed.get("commit") or self._detect_local_commit()
        state.previous_commit = previous

        try:
            self._assert_not_dirty()
            state = self.store.append_progress(state, "Resolved local tree is clean")

            if not target_commit:
                state.phase = "checking"
                state = self.store.append_progress(state, f"Resolving {cfg.release_ref} on GitHub…")
                target_commit = self._resolve_remote_commit(cfg)

            state.target_commit = target_commit
            state.target_short = target_commit[:7]
            self.store.write(state)

            if previous and (previous == target_commit or previous.startswith(target_commit) or target_commit.startswith(previous)):
                state.phase = "no_update"
                state.message = "Already on the selected commit; nothing to install."
                state.finished_at = _iso_now()
                self.store.write(state)
                return {"ok": True, "update_available": False, **self.snapshot_update()}

            # --- download / stage (before stopping app if possible) ---
            state.phase = "downloading"
            state = self.store.append_progress(state, f"Downloading {target_commit[:7]} into staging…")
            stage = self._prepare_release_dir(cfg, target_commit)
            state = self.store.append_progress(state, f"Staged at {stage}")

            state.phase = "building"
            state = self.store.append_progress(state, "Installing dependencies and building…")
            self._build_staged(stage)

            # --- stop owned services ---
            state.phase = "stopping"
            state = self.store.append_progress(
                state,
                "Stopping launcher-owned services (graceful worker shutdown)…",
            )
            stop_result = self.manager.stop()
            if stop_result.get("status") == "error" and stop_result.get("owned"):
                raise RuntimeError(f"Could not stop services: {stop_result.get('error')}")

            # --- backup ---
            state.phase = "backing_up"
            state = self.store.append_progress(state, "Creating backup of config and database…")
            backup_dir = self._create_backup(state)
            state.backup_path = str(backup_dir)
            self.store.write(state)
            state = self.store.append_progress(state, f"Backup OK: {backup_dir.name}")

            # --- migrate once with new code ---
            state.phase = "migrating"
            rev_before = self._alembic_current()
            state.migration_revision_before = rev_before
            self.store.write(state)
            state = self.store.append_progress(
                state, f"Applying migrations (before={rev_before or 'unknown'})…"
            )
            self._run_migrations(stage)
            state = self.store.append_progress(state, "Migrations finished")

            # --- switch code into install root ---
            state.phase = "switching"
            state = self.store.append_progress(state, "Switching application files (preserving .env/storage)…")
            self._sync_release_into_install(stage)
            self._reinstall_runtime_deps()

            save_installed(
                self.install_root,
                {
                    "commit": target_commit,
                    "short": target_commit[:7],
                    "ref": cfg.release_ref,
                    "installed_at": _iso_now(),
                    "previous_commit": previous,
                    "backup_path": str(backup_dir),
                    "migration_revision_before": rev_before,
                },
            )

            # --- restart + verify ---
            state.phase = "restarting"
            state = self.store.append_progress(state, "Restarting MailFlow…")
            start_result = self.manager.start(open_browser=False)
            if start_result.get("status") != "running":
                raise StartupAfterUpdateError(
                    f"Updated files are in place and migrations ran, but startup failed: "
                    f"{start_result.get('error')}. "
                    f"Do NOT restore an old DB dump if the app already wrote new data. "
                    f"Backup kept at {backup_dir}. "
                    f"Previous commit was {previous}. See docs/LOCAL_UPDATES.md."
                )

            state.phase = "success"
            state.error = None
            state.message = f"Updated to {target_commit[:7]} and services are running."
            state.finished_at = _iso_now()
            state = self.store.append_progress(state, state.message)
            self.store.write(state)
            return {"ok": True, **self.snapshot_update(), "services": start_result}

        except Exception as exc:  # noqa: BLE001
            state = self.store.read()
            # If we failed before migrating, installed code should still be previous.
            state.phase = "failed"
            state.error = str(exc)
            state.message = "Update failed"
            state.finished_at = _iso_now()
            state = self.store.append_progress(state, f"FAILED: {exc}")
            self.store.write(state)
            return {"ok": False, "error": str(exc), **self.snapshot_update()}
        finally:
            self.store.release()

    # --- internals ---------------------------------------------------------

    def _detect_local_commit(self) -> str | None:
        git_dir = self.install_root / ".git"
        if not git_dir.exists():
            return None
        try:
            proc = self._run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(self.install_root),
                check=False,
            )
            if proc.returncode == 0:
                return proc.stdout.strip()
        except OSError:
            return None
        return None

    def _assert_not_dirty(self) -> None:
        git_dir = self.install_root / ".git"
        if not git_dir.exists():
            # ZIP installs: allow update; local edits to tracked-like files are
            # still overwritten for non-preserved paths — warn via state only.
            return
        proc = self._run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=str(self.install_root),
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError("Could not inspect git status; refusing to update.")
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        # Ignore dirty .mailflow and runtime-only if somehow tracked
        meaningful = []
        for ln in lines:
            path = ln[3:].strip()
            if should_preserve_relative(path):
                continue
            meaningful.append(ln)
        if meaningful:
            preview = "\n".join(meaningful[:12])
            raise RuntimeError(
                "Local source modifications detected. Update aborted to avoid "
                "discarding your changes.\n"
                "Recovery: commit/stash/move your edits, or copy them elsewhere, "
                "then run Check for updates again.\n"
                f"Dirty paths:\n{preview}"
            )

    def _resolve_remote_commit(self, cfg: UpdateConfig) -> str:
        # Prefer git ls-remote against the configured remote (no credentials in URL).
        try:
            proc = self._run(
                ["git", "ls-remote", cfg.remote_url, cfg.release_ref],
                cwd=str(self.install_root),
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                # Lines: <sha>\trefs/heads/main  or tags
                for line in proc.stdout.splitlines():
                    parts = line.split()
                    if not parts:
                        continue
                    sha = parts[0].strip()
                    if re.fullmatch(r"[0-9a-f]{40}", sha):
                        return sha
                    if re.fullmatch(r"[0-9a-f]{64}", sha):  # future-proof
                        return sha
            if proc.returncode != 0 and _looks_offline(proc.stderr):
                raise OfflineError(proc.stderr.strip() or "Network error talking to GitHub")
            if proc.returncode != 0 and _looks_auth(proc.stderr):
                raise AuthError(proc.stderr.strip() or "GitHub auth failed")
        except FileNotFoundError:
            pass

        # Fallback: GitHub REST API (public repos need no token)
        api = (
            f"https://api.github.com/repos/{cfg.api_repo}/commits/"
            f"{cfg.release_ref}"
        )
        try:
            raw = self._fetch_bytes(api)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise AuthError(
                    "GitHub API refused access. For a private repo, configure git "
                    "credentials on the machine (never put tokens in launcher HTML)."
                ) from exc
            if exc.code == 404:
                raise RuntimeError(
                    f"Release ref '{cfg.release_ref}' not found on {cfg.api_repo}."
                ) from exc
            raise
        except URLError as exc:
            raise OfflineError(str(exc.reason if hasattr(exc, "reason") else exc)) from exc

        data = json.loads(raw.decode("utf-8"))
        sha = data.get("sha")
        if not sha:
            raise RuntimeError("GitHub API response missing commit sha.")
        return str(sha)

    def _prepare_release_dir(self, cfg: UpdateConfig, sha: str) -> Path:
        releases = mailflow_dir(self.install_root) / "releases"
        dest = releases / sha
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        git_dir = self.install_root / ".git"
        if git_dir.exists():
            # Fetch into local object DB then archive — does not checkout into running tree.
            fetch = self._run(
                ["git", "fetch", "--depth", "1", cfg.remote_url, sha],
                cwd=str(self.install_root),
                check=False,
            )
            if fetch.returncode == 0:
                archive = self._run(
                    ["git", "archive", "--format=tar", sha],
                    cwd=str(self.install_root),
                    check=False,
                    capture_binary=True,
                )
                if archive.returncode == 0 and archive.stdout_bytes:
                    self._extract_tar_bytes(archive.stdout_bytes, dest)
                    return dest

        # ZIP fallback (works for ZIP-based client installs without usable fetch)
        url = f"{cfg.zipball_url_for}/{sha}.zip"
        try:
            blob = self._fetch_bytes(url)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise AuthError(
                    "Could not download release zip (auth). Configure git credentials "
                    "for private repos; do not embed tokens in the launcher."
                ) from exc
            raise RuntimeError(f"Download failed HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            raise OfflineError(str(exc)) from exc

        with tempfile.TemporaryDirectory() as tmp:
            zpath = Path(tmp) / "release.zip"
            zpath.write_bytes(blob)
            with zipfile.ZipFile(zpath) as zf:
                zf.extractall(tmp)
            roots = [p for p in Path(tmp).iterdir() if p.is_dir()]
            if not roots:
                raise RuntimeError("Release zip had no top-level directory.")
            # Move contents into dest
            for child in roots[0].iterdir():
                shutil.move(str(child), dest / child.name)
        return dest

    def _build_staged(self, stage: Path) -> None:
        backend = stage / "backend"
        frontend = stage / "frontend"
        if not backend.is_dir() or not frontend.is_dir():
            raise RuntimeError("Staged release is missing backend/ or frontend/.")

        py = sys.executable
        venv_dir = backend / ".venv"
        self._run([py, "-m", "venv", str(venv_dir)], cwd=str(backend), check=True)
        vpy = venv_python(backend)
        self._run(
            [str(vpy), "-m", "pip", "install", "--upgrade", "pip"],
            cwd=str(backend),
            check=True,
        )
        self._run(
            [str(vpy), "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=str(backend),
            check=True,
        )

        lock = frontend / "package-lock.json"
        if lock.is_file():
            npm_ci = self._run(["npm", "ci"], cwd=str(frontend), check=False)
            if npm_ci.returncode != 0:
                self._run(["npm", "install"], cwd=str(frontend), check=True)
        else:
            self._run(["npm", "install"], cwd=str(frontend), check=True)
        self._run(["npm", "run", "build"], cwd=str(frontend), check=True)

    def _create_backup(self, state: UpdateOperationState) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup = mailflow_dir(self.install_root) / "backups" / f"update-{stamp}"
        backup.mkdir(parents=True)
        meta = {
            "created_at": _iso_now(),
            "previous_commit": state.previous_commit,
            "target_commit": state.target_commit,
            "files": [],
        }

        for name in (".env", "backend/.env"):
            src = self.install_root / name
            if src.is_file():
                dest = backup / name.replace("/", "_")
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                meta["files"].append(name)

        # Database dump via docker compose when available (no secrets logged).
        dump = backup / "mailflow.dump"
        dumped = False
        try:
            proc = self._run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "postgres",
                    "pg_dump",
                    "-U",
                    "mailflow",
                    "-Fc",
                    "mailflow",
                ],
                cwd=str(self.install_root),
                check=False,
                capture_binary=True,
            )
            if proc.returncode == 0 and proc.stdout_bytes:
                dump.write_bytes(proc.stdout_bytes)
                dumped = True
                meta["files"].append("mailflow.dump")
        except OSError:
            dumped = False

        if not dumped:
            # Try local pg_dump if DATABASE_URL points at localhost
            db_url = self._read_database_url()
            if db_url and ("localhost" in db_url or "127.0.0.1" in db_url):
                try:
                    proc = self._run(
                        ["pg_dump", "-Fc", "-d", db_url.replace("postgresql+psycopg2://", "postgresql://")],
                        cwd=str(self.install_root),
                        check=False,
                        capture_binary=True,
                    )
                    if proc.returncode == 0 and proc.stdout_bytes:
                        dump.write_bytes(proc.stdout_bytes)
                        dumped = True
                        meta["files"].append("mailflow.dump")
                except OSError:
                    pass

        if not dumped:
            raise RuntimeError(
                "Backup failed: could not create a database dump. "
                "Ensure Docker Desktop is running (postgres) or pg_dump is on PATH. "
                "Update aborted before migrations. Installed version left unchanged."
            )

        (backup / "backup-meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )
        # Verify dump non-empty
        if not dump.is_file() or dump.stat().st_size < 16:
            raise RuntimeError("Backup verification failed: dump file missing or empty.")
        return backup

    def _alembic_current(self) -> str | None:
        vpy = venv_python(self.install_root / "backend")
        if not vpy.is_file():
            return None
        proc = self._run(
            [str(vpy), "-m", "alembic", "current"],
            cwd=str(self.install_root / "backend"),
            check=False,
        )
        if proc.returncode != 0:
            return None
        # First token often revision id
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            return line.split()[0]
        return None

    def _run_migrations(self, stage: Path) -> None:
        vpy = venv_python(stage / "backend")
        env = os.environ.copy()
        # Prefer install-root env files without printing them
        for candidate in (
            self.install_root / "backend" / ".env",
            self.install_root / ".env",
        ):
            if candidate.is_file():
                env.update(_parse_env_file(candidate))
                break
        db_url = env.get("DATABASE_URL", "")
        if "localhost" not in db_url and "127.0.0.1" not in db_url:
            raise RuntimeError(
                "Refusing migrations: DATABASE_URL is not localhost. "
                "Update aborted after backup; install files not switched."
            )
        # Never enable sending/billing as a side effect
        env["CAMPAIGN_SENDING_ENABLED"] = "false"
        env["BILLING_ENABLED"] = env.get("BILLING_ENABLED", "false")
        proc = self._run(
            [str(vpy), "-m", "alembic", "upgrade", "head"],
            cwd=str(stage / "backend"),
            check=False,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                "Migration failed. Application files were NOT switched. "
                f"Backup is at {self.store.read().backup_path}. "
                f"Details: {(proc.stderr or proc.stdout)[:800]}"
            )

    def _sync_release_into_install(self, stage: Path) -> None:
        for src in stage.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(stage).as_posix()
            if should_preserve_relative(rel):
                continue
            if rel.startswith(".venv/") or "/.venv/" in f"/{rel}":
                continue
            if "node_modules/" in rel or rel.startswith("node_modules/"):
                continue
            dest = self.install_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    def _reinstall_runtime_deps(self) -> None:
        backend = self.install_root / "backend"
        frontend = self.install_root / "frontend"
        vpy = venv_python(backend)
        if not vpy.is_file():
            self._run([sys.executable, "-m", "venv", str(backend / ".venv")], cwd=str(backend), check=True)
            vpy = venv_python(backend)
        self._run(
            [str(vpy), "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=str(backend),
            check=True,
        )
        if (frontend / "package-lock.json").is_file():
            ci = self._run(["npm", "ci"], cwd=str(frontend), check=False)
            if ci.returncode != 0:
                self._run(["npm", "install"], cwd=str(frontend), check=True)
        else:
            self._run(["npm", "install"], cwd=str(frontend), check=True)

    def _read_database_url(self) -> str | None:
        for candidate in (
            self.install_root / "backend" / ".env",
            self.install_root / ".env",
        ):
            if candidate.is_file():
                values = _parse_env_file(candidate)
                return values.get("DATABASE_URL")
        return None

    @staticmethod
    def _default_run(
        cmd: list[str],
        *,
        cwd: str,
        check: bool = False,
        env: dict[str, str] | None = None,
        capture_binary: bool = False,
    ) -> Any:
        if capture_binary:
            proc = subprocess.run(  # noqa: S603
                cmd,
                cwd=cwd,
                env=env,
                check=False,
                capture_output=True,
            )
            wrapper = subprocess.CompletedProcess(
                proc.args,
                proc.returncode,
                stdout="",
                stderr=(proc.stderr or b"").decode("utf-8", errors="replace"),
            )
            wrapper.stdout_bytes = proc.stdout or b""  # type: ignore[attr-defined]
            if check and proc.returncode != 0:
                raise RuntimeError(
                    f"Command failed ({proc.returncode}): {' '.join(cmd)}\n{wrapper.stderr[:500]}"
                )
            return wrapper

        proc = subprocess.run(  # noqa: S603
            cmd,
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if check and proc.returncode != 0:
            raise RuntimeError(
                f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
                f"{(proc.stderr or proc.stdout or '')[:800]}"
            )
        return proc

    @staticmethod
    def _default_fetch_bytes(url: str) -> bytes:
        req = Request(
            url,
            headers={
                "User-Agent": "MailFlow-Local-Updater",
                "Accept": "application/vnd.github+json, application/zip, */*",
            },
        )
        with urlopen(req, timeout=60) as resp:  # noqa: S310 — https GitHub only via callers
            return resp.read()

    @staticmethod
    def _extract_tar_bytes(data: bytes, dest: Path) -> None:
        import io
        import tarfile

        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tf:
            tf.extractall(dest)


class OfflineError(RuntimeError):
    pass


class AuthError(RuntimeError):
    pass


class StartupAfterUpdateError(RuntimeError):
    pass


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip().strip('"').strip("'")
    return values


def _looks_offline(text: str) -> bool:
    t = (text or "").lower()
    return any(
        s in t
        for s in (
            "could not resolve",
            "nodename nor servname",
            "network is unreachable",
            "timed out",
            "failed to connect",
            "temporary failure",
        )
    )


def _looks_auth(text: str) -> bool:
    t = (text or "").lower()
    return any(
        s in t
        for s in ("authentication failed", "permission denied", "403", "401", "could not read username")
    )
