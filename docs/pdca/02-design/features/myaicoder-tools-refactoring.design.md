# Design: myAiCoder Core Tools 구조 개선 (Refactoring)

> **상태**: D (Design)
> **작성일**: 2026-03-24
> **목표**: 도구를 기능별 서브패키지로 완전히 이동시키고, Registry를 통한 관리 체계를 자동화하여 확장성을 높인다.

---

## 1. 상세 패키징 설계 (Sub-packaging Design)

### 1.1 도구 재배치 (Tool Relocation)

| 도구 파일 | 대상 패키지 | 분류 사유 |
|:---|:---|:---|
| `read.py`, `write.py`, `edit.py`, `list_dir.py` | `filesystem/` | 직접적인 파일/디렉토리 조작 |
| `bash.py`, `glob_tool.py`, `grep_tool.py` | `search/` | 파일 내용 검색 및 시스템 분석(Bash 포함) |
| `build_runner.py`, `web_fetch.py` | `external/` | 외부 프로세스 및 네트워크 자원 활용 |

### 1.2 패키지 노출 (`__init__.py`)
각 서브패키지의 `__init__.py`는 해당 패키지에 속한 도구 클래스들을 리스트 형태로 노출합니다.
- 예: `filesystem/__init__.py` -> `TOOLS = [ReadTool(), WriteTool(), EditTool(), ListDirTool()]`

---

## 2. Registry 자동화 설계 (Registry Automation)

### 2.1 동적 등록 메커니즘
`registry.py`의 `create_default_registry`가 각 패키지의 `TOOLS` 리스트를 순회하며 자동으로 등록하도록 개선합니다.

```python
def create_default_registry() -> ToolRegistry:
    from .filesystem import TOOLS as FILESYSTEM_TOOLS
    from .search import TOOLS as SEARCH_TOOLS
    from .external import TOOLS as EXTERNAL_TOOLS

    registry = ToolRegistry()
    for tool_class in FILESYSTEM_TOOLS + SEARCH_TOOLS + EXTERNAL_TOOLS:
        registry.register(tool_class())
    return registry
```

- **장점**: 새로운 도구를 추가할 때 해당 패키지의 `__init__.py`만 수정하면 `registry.py`는 건드릴 필요가 없음.

---

## 3. 리팩토링 수행 단계 (Implementation Strategy)

### Step 1: 파일 이동 및 패키지 초기화
- 12개 도구 파일을 `filesystem/`, `search/`, `external/`로 이동.
- 각 패키지에 `__init__.py`를 생성하고 도구 클래스를 `import`하여 `TOOLS` 리스트 생성.

### Step 2: `registry.py` 및 `base.py` 정규화
- `registry.py`를 위 설계에 따라 동적 등록 방식으로 수정.
- 각 도구 파일 내부의 `import` 경로가 깨지지 않도록 `myaicoder.tools.base` 참조 확인.

### Step 3: MCP 서버 및 CLI 연동 확인
- `services/myaicoder/src/myaicoder/mcp/server.py` 등에서 도구를 가져오는 경로 확인.

---

## 4. 검증 계획 (Validation Plan)

1. **단위 테스트**: `uv run pytest services/myaicoder/tests/test_tools/` 실행.
2. **스키마 검증**: `ToolRegistry.to_openai_tools()`를 호출하여 도구의 이름과 파라미터 스키마가 리팩토링 전과 동일한지 비교.
3. **E2E 테스트**: `myaicoder serve` 실행 후 VS Code Extension에서 도구가 정상적으로 조회되고 작동하는지 확인.
