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
        'myaicoder.core.config',
        'myaicoder.core.context',
        'myaicoder.core.conversation',
        'myaicoder.core.engine',
        'myaicoder.core.session',
        'myaicoder.core.memory',
        'myaicoder.core.memory.loader',
        'myaicoder.core.memory.store',
        'myaicoder.core.middleware',
        'myaicoder.core.middleware.base',
        'myaicoder.core.middleware.filesystem',
        'myaicoder.core.middleware.hitl',
        'myaicoder.core.middleware.memory',
        'myaicoder.core.middleware.planning',
        'myaicoder.core.middleware.stack',
        'myaicoder.core.middleware.subagent',
        'myaicoder.core.middleware.summarization',
        'myaicoder.core.planning',
        'myaicoder.core.planning.todos',
        'myaicoder.core.subagent',
        'myaicoder.core.subagent.base',
        'myaicoder.core.subagent.registry',
        'myaicoder.core.subagent.runner',
        'myaicoder.llm',
        'myaicoder.llm.base',
        'myaicoder.llm.vllm_provider',
        'myaicoder.mcp',
        'myaicoder.mcp.client',
        'myaicoder.mcp.config',
        'myaicoder.mcp.server',
        'myaicoder.mcp.transport',
        'myaicoder.models',
        'myaicoder.models.config',
        'myaicoder.models.manager',
        'myaicoder.models.process',
        'myaicoder.models.scanner',
        'myaicoder.tools',
        'myaicoder.tools.base',
        'myaicoder.tools.registry',
        'myaicoder.tools.external',
        'myaicoder.tools.external.build_runner',
        'myaicoder.tools.external.web_fetch',
        'myaicoder.tools.filesystem',
        'myaicoder.tools.filesystem.edit',
        'myaicoder.tools.filesystem.list_dir',
        'myaicoder.tools.filesystem.read',
        'myaicoder.tools.filesystem.write',
        'myaicoder.tools.search',
        'myaicoder.tools.search.bash',
        'myaicoder.tools.search.glob_tool',
        'myaicoder.tools.search.grep_tool',
        'myaicoder.ui',
        'myaicoder.ui.chat',
        'myaicoder.utils',
        'click',
        'rich',
        'rich.console',
        'rich.markdown',
        'openai',
        'httpx',
        'pydantic',
        'yaml',
        'aiofiles',
        'mcp',
        'mcp.server',
        'mcp.server.fastmcp',
        'dotenv',
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
