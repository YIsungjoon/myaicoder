# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for myAiCoder CLI frozen binary."""

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['../services/myaicoder/src/myaicoder/cli.py'],
    pathex=['../services/myaicoder/src'],
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
