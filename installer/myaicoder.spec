# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for myAiCoder CLI frozen binary."""

import os
from PyInstaller.utils.hooks import collect_data_files

# CI: WORKSPACE_ROOT env var set by GitHub Actions (avoids MSYS path mangling)
# Local: fallback to SPECPATH (already a directory path) → one level up
WORKSPACE_ROOT = os.environ.get('WORKSPACE_ROOT')

if WORKSPACE_ROOT:
    REPO_ROOT = WORKSPACE_ROOT
else:
    REPO_ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
SERVICE_DIR = os.path.join(REPO_ROOT, 'services', 'myaicoder')
SRC_DIR = os.path.join(SERVICE_DIR, 'src')
ENTRY_POINT = os.path.join(SRC_DIR, 'myaicoder', 'cli.py')

a = Analysis(
    [ENTRY_POINT],
    pathex=[SRC_DIR],
    binaries=[],
    datas=collect_data_files('certifi'),
    hiddenimports=[
        'myaicoder',
        'myaicoder.cli',
        'myaicoder.core',
        'myaicoder.core.engine',
        'myaicoder.core.config',
        'myaicoder.core.context',
        'myaicoder.core.conversation',
        'myaicoder.core.session',
        'myaicoder.llm',
        'myaicoder.llm.vllm_provider',
        'myaicoder.tools',
        'myaicoder.mcp',
        'myaicoder.models',
        'myaicoder.ui',
        'click',
        'rich',
        'openai',
        'httpx',
        'pydantic',
        'yaml',
        'aiofiles',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='myaicoder',
    debug=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
