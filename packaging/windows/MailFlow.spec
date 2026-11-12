# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the one-folder MailFlow Windows app.

Build with packaging/windows/build.ps1 on Windows. The spec expects
frontend/dist to already exist.
"""

from pathlib import Path
import sys

spec_dir = Path(SPECPATH).resolve()
root = spec_dir.parents[1]
backend = root / "backend"
frontend_dist = root / "frontend" / "dist"

if not (frontend_dist / "index.html").is_file():
    raise SystemExit(
        f"Missing frontend build at {frontend_dist}. Run npm run build in frontend first."
    )

sys.path.insert(0, str(backend))

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("app") + collect_submodules("uvicorn")
hiddenimports += [
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "pydantic",
    "pydantic_settings",
    "cryptography.fernet",
    "passlib.handlers.bcrypt",
    "bcrypt",
    "email_validator",
    "multipart",
    "python_multipart",
    "apscheduler.schedulers.background",
    "google.auth",
    "PIL",
    "openpyxl",
    "pandas",
    "bleach",
    "bs4",
    "stripe",
]

a = Analysis(
    [str(spec_dir / "desktop_entry.py")],
    pathex=[str(backend)],
    binaries=[],
    datas=[(str(frontend_dist), "frontend_dist")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MailFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MailFlow",
)
