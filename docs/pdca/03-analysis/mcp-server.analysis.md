# mcp-server Analysis Report (v2 - Post Manual Testing)

> **Analysis Type**: Gap Analysis (Design vs Implementation)
>
> **Project**: myaicoder
> **Analyst**: gap-detector
> **Date**: 2026-03-13
> **Design Doc**: [mcp-server.design.md](../02-design/features/mcp-server.design.md)
> **Iteration**: 2 (Post manual testing bug fixes)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

Re-analyze the MCP Server feature after manual testing (Design Step 12) uncovered two bugs that were fixed. This v2 analysis compares the updated implementation against the original design, noting where implementation now EXCEEDS the design specification.

### 1.2 Analysis Scope

- **Design Document**: `docs/pdca/02-design/features/mcp-server.design.md`
- **Implementation Path**: `src/myaicoder/` (tools/base.py, mcp/server.py, core/engine.py, core/config.py, cli.py)
- **Test Path**: `tests/` (test_mcp/test_server.py, test_core/test_engine_tools.py, test_tools/test_registry.py)
- **Analysis Date**: 2026-03-13
- **Previous Analysis**: v1.0 (pre-manual-testing, 100% match rate)

### 1.3 Changes Since v1 Analysis

Two bugs were discovered during manual testing (Step 12: Claude Code compatibility) and fixed:

1. **inputSchema bug**: `_register_single_tool` used `**kwargs` handler (as designed), but FastMCP infers inputSchema from function signature, producing `{"kwargs": {"type": "string"}}` instead of actual tool parameters. Fixed by adding `_build_typed_handler()` that dynamically creates functions with proper type-annotated signatures.

2. **None parameter bug**: Optional parameters defaulted to `None` were passed directly to `tool.execute()`, causing errors (e.g., `offset=None` in ReadTool). Fixed by filtering `None` values in `_execute_and_format()`.

---

## 2. Gap Analysis (Design vs Implementation)

### 2.1 Implementation Step Checklist (Section 12)

| Step | Task | File | Design | Implementation | Status |
|:----:|------|------|:------:|:--------------:|:------:|
| 1 | Tool.to_mcp_tool() | tools/base.py | O | O | ✅ Match |
| 2 | MCPServer class (basic) | mcp/server.py | O | O | ✅ Match |
| 3 | ToolRegistry -> FastMCP dynamic registration | mcp/server.py | O | O (enhanced) | ✅ Match+ |
| 4 | _truncate_tool_result() middleware | core/engine.py | O | O | ✅ Match |
| 5 | _is_retryable_error() + retry | core/engine.py | O | O | ✅ Match |
| 6 | serve CLI command | cli.py | O | O | ✅ Match |
| 7 | --transport, --port, --max-concurrent | cli.py + mcp/server.py | O | O | ✅ Match |
| 8 | --allow-bash, --working-dir | cli.py + mcp/server.py | O | O | ✅ Match |
| 9 | agentic_task registration + --agentic | mcp/server.py + cli.py | O | O | ✅ Match |
| 10 | Unit tests (12 cases) | tests/test_mcp/test_server.py | O | O (13 tests) | ✅ Match+ |
| 11 | Existing test enhancement | test_engine_tools.py, test_registry.py | O | O | ✅ Match |
| 12 | Claude Code compatibility test | manual | O | Completed | ✅ Done |
| 13 | Revit/CAD MCP connection verification | manual + docs | O | N/A | -- Manual |
| 14 | MCP chaining prototype | cli.py serve + MCP Client | O | N/A | -- Manual |

**Automated Steps: 11/11 (100%)**
**Manual Steps: 1/3 completed (Step 12)**

### 2.2 Key Interface Specifications

#### 2.2.1 TOOL_NAME_MAP (Section 4.2)

| Internal Name | Design MCP Name | Implementation MCP Name | Status |
|---------------|----------------|------------------------|:------:|
| Read | read_file | read_file | ✅ |
| Write | write_file | write_file | ✅ |
| Edit | edit_file | edit_file | ✅ |
| Glob | glob_search | glob_search | ✅ |
| Grep | grep_search | grep_search | ✅ |
| Bash | run_command | run_command | ✅ |

**TOOL_NAME_MAP: 6/6 (100%)**

#### 2.2.2 MCPServer.__init__ Parameters (Section 4.2)

| Parameter | Design | Implementation | Status |
|-----------|--------|----------------|:------:|
| name: str = "myaicoder" | O | O | ✅ |
| tool_registry: ToolRegistry \| None = None | O | O | ✅ |
| allow_bash: bool = False | O | O | ✅ |
| working_dir: str \| None = None | O | O | ✅ |
| max_concurrent: int = 1 | O | O | ✅ |
| max_result_tokens: int = 4000 | O | O | ✅ |
| enable_agentic: bool = False | O | O | ✅ |
| llm_provider=None | O | O | ✅ |

**MCPServer.__init__: 8/8 (100%)**

#### 2.2.3 _register_single_tool -- DESIGN EXCEEDED

| Aspect | Design (Section 4.2) | Implementation | Status |
|--------|---------------------|----------------|:------:|
| Handler function | `async def tool_handler(**kwargs)` | `_build_typed_handler()` with dynamic typed signature | ✅ Exceeds |
| inputSchema generation | Relies on FastMCP + add_tool | Explicit `inspect.Parameter` with type annotations | ✅ Exceeds |
| Schema source | tool.parameters_schema (implicit) | tool.parameters_schema parsed into `inspect.Signature` | ✅ Exceeds |

**Why this exceeds design**: The design assumed `**kwargs` would work with FastMCP. In practice, FastMCP infers `inputSchema` from function signatures. The `**kwargs` approach produced `{"kwargs": {"type": "string"}}` -- wrong schema. The implementation creates properly typed handler functions at runtime, ensuring MCP clients (Claude Code, Cursor) see correct parameter names, types, and optionality.

Key implementation details in `_build_typed_handler()` (mcp/server.py lines 85-140):
- `_JSON_TYPE_MAP` converts JSON Schema types to Python types
- Required vs optional parameters distinguished via `inspect.Parameter` defaults
- Optional params with no explicit default get `None` default and union type (`py_type | None`)
- `handler.__signature__` set so FastMCP reads correct schema

#### 2.2.4 _execute_and_format -- DESIGN EXCEEDED

| Aspect | Design (Section 4.2) | Implementation | Status |
|--------|---------------------|----------------|:------:|
| Signature | `_execute_and_format(self, tool, kwargs)` | Same | ✅ Match |
| Execute call | `await tool.execute(**kwargs)` | `kwargs = {k: v for k, v in kwargs.items() if v is not None}` then `await tool.execute(**kwargs)` | ✅ Exceeds |
| Error format | `f"Error: {result.error}"` | Same | ✅ Match |
| Result truncation | `self._truncate_result(result.output)` | Same | ✅ Match |

**Why this exceeds design**: Optional MCP parameters default to `None` when not provided by the client. Passing `None` to tools like ReadTool caused errors (e.g., `offset=None` when ReadTool expects `int`). The None-filtering line ensures tools receive only explicitly provided parameters, falling back to their own defaults.

#### 2.2.5 _truncate_result Logic (Section 4.2, 8.1)

| Specification | Design | Implementation | Status |
|--------------|--------|----------------|:------:|
| max_chars = max_result_tokens * 4 | O | O | ✅ |
| Appends "truncated, N chars total" | O | O | ✅ |
| Passes through when under limit | O | O | ✅ |

#### 2.2.6 Bash Security (Section 4.2)

| Specification | Design | Implementation | Status |
|--------------|--------|----------------|:------:|
| Skip Bash when allow_bash=False | O | O (line 69-70) | ✅ |

#### 2.2.7 Concurrency Control (Section 7)

| Specification | Design | Implementation | Status |
|--------------|--------|----------------|:------:|
| Semaphore created when max_concurrent > 1 | O | O (line 192) | ✅ |
| Semaphore applied in handler | O | O (line 129-131) | ✅ |

#### 2.2.8 agentic_task Registration (Section 4.2)

| Specification | Design | Implementation | Status |
|--------------|--------|----------------|:------:|
| Registered only when enable_agentic=True AND llm_provider provided | O | O (line 62-63) | ✅ |
| Uses AgentEngine internally | O | O (lines 173-177) | ✅ |

#### 2.2.9 Error Retry Logic (Section 4.3, 6.2)

| Specification | Design | Implementation | Status |
|--------------|--------|----------------|:------:|
| MAX_TOOL_RETRIES = 2 | O | O (engine.py line 24) | ✅ |
| Non-retryable keywords: permission, denied, auth, connection, refused | O | O (engine.py line 174) | ✅ |
| Retry loop in _execute_tool_with_approval | O | O (engine.py lines 138-143) | ✅ |

#### 2.2.10 _truncate_tool_result in chat() (Section 4.3)

| Specification | Design | Implementation | Status |
|--------------|--------|----------------|:------:|
| Applied to tool results before adding to conversation | O | O (engine.py line 83) | ✅ |

### 2.3 Config Extensions (Section 13)

#### 2.3.1 ServerConfig Dataclass

| Field | Design | Implementation | Status |
|-------|--------|----------------|:------:|
| transport: str = "stdio" | O | O | ✅ |
| port: int = 3000 | O | O | ✅ |
| allow_bash: bool = False | O | O | ✅ |
| working_dir: str \| None = None | O | O | ✅ |
| max_concurrent: int = 1 | O | O | ✅ |
| enable_agentic: bool = False | O | O | ✅ |

**ServerConfig: 6/6 (100%)**

#### 2.3.2 ToolsConfig.max_result_tokens

| Specification | Design | Implementation | Status |
|--------------|--------|----------------|:------:|
| max_result_tokens: int = 4000 | O | O (config.py line 33) | ✅ |

#### 2.3.3 AppConfig.server Field

| Specification | Design | Implementation | Status |
|--------------|--------|----------------|:------:|
| server: ServerConfig = field(default_factory=ServerConfig) | O | O (config.py line 60) | ✅ |
| Server section parsing in _from_file() | O | O (config.py lines 107-110) | ✅ |

### 2.4 CLI serve Command (Section 4.4)

| Specification | Design | Implementation | Status |
|--------------|--------|----------------|:------:|
| @main.command() decorator | O | O | ✅ |
| --transport (stdio, streamable-http) | O | O | ✅ |
| --port (default 3000) | O | O | ✅ |
| --allow-bash (is_flag) | O | O | ✅ |
| --working-dir (default None) | O | O | ✅ |
| --max-concurrent (default 1) | O | O | ✅ |
| --agentic (is_flag) | O | O | ✅ |
| LLM provider setup when agentic | O | O | ✅ |
| HTTP port env var for streamable-http | O | O | ✅ |

**CLI serve: 9/9 (100%)**

### 2.5 MCP Protocol Verification (Manual Testing Results)

| Protocol | Test | Result | Status |
|----------|------|--------|:------:|
| initialize | MCP handshake via stdio | Successful | ✅ |
| tools/list | Lists all registered tools with correct inputSchema | Successful (typed params) | ✅ |
| tools/call | Execute tool and return result | Successful | ✅ |
| inputSchema | Proper typed parameters (not `{"kwargs": "string"}`) | Verified after _build_typed_handler fix | ✅ |
| Optional params | None values filtered before tool.execute() | Verified after None filtering fix | ✅ |
| Bash security | run_command excluded without --allow-bash | Verified | ✅ |

### 2.6 Test Coverage (Section 11)

#### 2.6.1 test_mcp/test_server.py (Design: 12, Implementation: 13)

| # | Design Test Case | Implementation | Status |
|---|-----------------|----------------|:------:|
| 1 | test_server_creation | TestMCPServerCreation.test_server_creation | ✅ |
| 2 | test_tool_registration_count | test_tool_registration_count_no_bash + test_tool_registration_count_with_bash | ✅ |
| 3 | test_bash_excluded_by_default | TestMCPServerCreation.test_bash_excluded_by_default | ✅ |
| 4 | test_bash_included_when_allowed | TestMCPServerCreation.test_bash_included_when_allowed | ✅ |
| 5 | test_tool_name_mapping | TestToolNameMapping.test_tool_name_mapping + test_name_map_completeness | ✅ |
| 6 | test_direct_tool_execution | test_direct_tool_execution (standalone, async) | ✅ |
| 7 | test_result_truncation | TestResultTruncation.test_result_truncation | ✅ |
| 8 | test_result_no_truncation | TestResultTruncation.test_result_no_truncation | ✅ |
| 9 | test_agentic_task_registration | TestAgenticTask.test_agentic_task_registration | ✅ |
| 10 | test_error_retryable | TestRetryAndTruncation.test_is_retryable_error (test_engine_tools.py) | ✅ |
| 11 | test_error_non_retryable | TestRetryAndTruncation.test_is_retryable_error (test_engine_tools.py) | ✅ |
| 12 | test_concurrency_semaphore | TestConcurrency.test_concurrency_semaphore | ✅ |

**Design Test Cases: 12/12 (100%)**

#### 2.6.2 Bonus Tests (Not in Design)

| # | Test | Location | Value |
|---|------|----------|-------|
| B1 | test_agentic_task_not_registered_by_default | test_server.py:108-114 | Negative case coverage |
| B2 | test_name_map_completeness | test_server.py:67-70 | Map validation |

#### 2.6.3 Existing Test Enhancement (Section 11.2)

| File | Design Change | Implementation | Status |
|------|--------------|----------------|:------:|
| test_engine_tools.py | _truncate_tool_result() test | TestRetryAndTruncation.test_truncate_tool_result | ✅ |
| test_registry.py | to_mcp_tool() test | TestToolRegistry.test_to_mcp_tool | ✅ |

**Total Tests: 66 passing (all green)**

### 2.7 Match Rate Summary

```
+---------------------------------------------+
|  Overall Match Rate: 100%                    |
+---------------------------------------------+
|  Automated Steps:    11/11  (100%)           |
|  TOOL_NAME_MAP:       6/6   (100%)           |
|  MCPServer params:    8/8   (100%)           |
|  ServerConfig:        6/6   (100%)           |
|  CLI options:         9/9   (100%)           |
|  Test cases:         12/12  (100%)           |
|  Key specs:          15/15  (100%)           |
|  MCP protocol:        6/6   (100%)           |
+---------------------------------------------+
|  Implementation EXCEEDS design:  2 items     |
|  Manual steps completed:         1/3         |
|  Manual steps pending:           2           |
|  (Steps 13, 14)                              |
+---------------------------------------------+
```

---

## 3. Code Quality Analysis

### 3.1 File-Level Review

| File | Lines | Complexity | Status | Notes |
|------|:-----:|:----------:|:------:|-------|
| tools/base.py | 57 | Low | ✅ | Clean, well-structured |
| mcp/server.py | 195 | Medium-High | ✅ | _build_typed_handler adds complexity but is well-documented |
| core/engine.py | 190 | Medium | ✅ | Retry/truncation well integrated |
| core/config.py | 113 | Low | ✅ | Standard dataclass pattern |
| cli.py | 316 | Medium | ✅ | serve command cleanly separated |

### 3.2 New Code Quality (Post-Fix)

| Addition | File | Lines | Quality | Notes |
|----------|------|:-----:|:-------:|-------|
| `_build_typed_handler()` | mcp/server.py:85-140 | 56 | Good | Uses `inspect` module idiomatically; closure over `tool` and `server` |
| `_JSON_TYPE_MAP` | mcp/server.py:13-18 | 6 | Good | Clear mapping, covers common JSON Schema types |
| None filtering | mcp/server.py:145 | 1 | Good | Single-line dict comprehension, clear intent |

### 3.3 Security Review

| Aspect | Design Requirement | Implementation | Status |
|--------|-------------------|----------------|:------:|
| Bash tool disabled by default | O | O | ✅ |
| working_dir restriction param | O | O (param exists) | ✅ |

---

## 4. Clean Architecture Compliance

### 4.1 Layer Assignment

| Component | Layer | Location | Status |
|-----------|-------|----------|:------:|
| Tool.to_mcp_tool() | Domain (base interface) | tools/base.py | ✅ |
| MCPServer | Infrastructure (server) | mcp/server.py | ✅ |
| AgentEngine retry/truncate | Application (engine) | core/engine.py | ✅ |
| ServerConfig | Domain (config) | core/config.py | ✅ |
| serve CLI command | Presentation (CLI) | cli.py | ✅ |

### 4.2 Dependency Direction

| Import | From | To | Direction | Status |
|--------|------|-----|-----------|:------:|
| mcp/server.py | Infrastructure | tools/base.py (Domain) | Infra -> Domain | ✅ |
| mcp/server.py | Infrastructure | tools/registry.py (Domain) | Infra -> Domain | ✅ |
| mcp/server.py | Infrastructure | inspect, asyncio (stdlib) | Infra -> stdlib | ✅ |
| cli.py | Presentation | mcp/server.py (Infra) | Pres -> Infra | ✅ (lazy import) |
| cli.py | Presentation | core/config.py (Domain) | Pres -> Domain | ✅ |
| core/engine.py | Application | tools/ (Domain) | App -> Domain | ✅ |

**Architecture Compliance: 100%**

---

## 5. Convention Compliance

### 5.1 Naming Convention

| Category | Convention | Checked | Compliance | Violations |
|----------|-----------|:-------:|:----------:|------------|
| Classes | PascalCase | 4 | 100% | - |
| Functions | snake_case (Python) | 18+ | 100% | - |
| Constants | UPPER_SNAKE_CASE | 3 | 100% | TOOL_NAME_MAP, MAX_TOOL_RETRIES, _JSON_TYPE_MAP |
| Files | snake_case.py | 5 | 100% | - |
| Folders | snake_case | 2 | 100% | mcp/, core/ |

### 5.2 Import Order

All implementation files follow correct import order:
1. Standard library (asyncio, inspect, json, etc.)
2. Third-party (click, mcp, pytest)
3. Internal (myaicoder.*)

**Convention Compliance: 100%**

---

## 6. Design Exceeded Items

These are improvements in the implementation that go BEYOND the original design specification.

### 6.1 Typed Handler (_build_typed_handler)

| Aspect | Detail |
|--------|--------|
| **Design** | `async def tool_handler(**kwargs)` -- simple kwargs passthrough (Section 4.2) |
| **Implementation** | Dynamic function with `inspect.Signature` typed parameters |
| **Reason** | FastMCP infers inputSchema from function signatures; `**kwargs` produced wrong schema |
| **Impact** | MCP clients see correct parameter names, types, and optionality |
| **Files** | mcp/server.py lines 12-18 (_JSON_TYPE_MAP), 85-140 (_build_typed_handler) |

### 6.2 None Parameter Filtering

| Aspect | Detail |
|--------|--------|
| **Design** | `await tool.execute(**kwargs)` -- direct passthrough (Section 4.2) |
| **Implementation** | `kwargs = {k: v for k, v in kwargs.items() if v is not None}` before execute |
| **Reason** | Optional params default to None in MCP; tools expect absent params, not None |
| **Impact** | Prevents runtime errors when optional params are not provided |
| **Files** | mcp/server.py line 145 |

---

## 7. Overall Score

```
+---------------------------------------------+
|  Overall Score: 100/100                      |
+---------------------------------------------+
|  Design Match:            100%  ✅           |
|  Architecture Compliance: 100%  ✅           |
|  Convention Compliance:   100%  ✅           |
|  Test Coverage:           100%  ✅           |
|  Design Exceeded:          +2 items          |
+---------------------------------------------+
```

| Category | Score | Status |
|----------|:-----:|:------:|
| Design Match | 100% | ✅ |
| Architecture Compliance | 100% | ✅ |
| Convention Compliance | 100% | ✅ |
| **Overall** | **100%** | ✅ |

---

## 8. Missing Features (Design O, Implementation X)

None found.

---

## 9. Added Features (Design X, Implementation O)

| Item | Implementation Location | Description | Impact |
|------|------------------------|-------------|--------|
| _build_typed_handler() | mcp/server.py:85-140 | Typed handler for correct inputSchema | High (bug fix) |
| _JSON_TYPE_MAP | mcp/server.py:13-18 | JSON Schema to Python type mapping | Medium (supports typed handler) |
| None filtering | mcp/server.py:145 | Filter None kwargs before tool.execute() | High (bug fix) |
| test_agentic_task_not_registered_by_default | test_server.py:108-114 | Negative case test | Low (bonus coverage) |
| test_name_map_completeness | test_server.py:67-70 | Map validation test | Low (bonus coverage) |

Items 1-3 are bug fixes found during manual testing. They improve upon the design and are recommended to be reflected in a design document update.

---

## 10. Changed Features (Design != Implementation)

| Item | Design | Implementation | Impact | Recommendation |
|------|--------|----------------|--------|----------------|
| _register_single_tool handler | `async def tool_handler(**kwargs)` | `_build_typed_handler()` with typed signature | High | Update design Section 4.2 |
| _execute_and_format kwargs | Direct `**kwargs` passthrough | None-filtered kwargs | High | Update design Section 4.2 |

Both changes are strict improvements. The design's approach was correct in intent but insufficient for FastMCP's signature-based schema inference.

---

## 11. Recommended Actions

### 11.1 Immediate Actions

No blocking issues. All automated steps complete and verified.

### 11.2 Design Document Updates Recommended

| Priority | Update | Section |
|----------|--------|---------|
| Medium | Add `_build_typed_handler()` approach to replace `**kwargs` handler | Section 4.2 |
| Medium | Add None filtering in `_execute_and_format()` | Section 4.2 |
| Low | Add `_JSON_TYPE_MAP` constant description | Section 4.2 |

### 11.3 Pending Manual Steps

| Priority | Step | Task | Status |
|----------|:----:|------|--------|
| Done | 12 | Claude Code compatibility integration test | ✅ Completed (bugs found and fixed) |
| Medium | 13 | Revit/CAD MCP connection verification | Pending |
| Low | 14 | MCP chaining prototype | Pending |

---

## 12. Next Steps

- [x] Execute manual test Step 12 (Claude Code compatibility)
- [x] Fix bugs found during manual testing
- [x] Re-run all 66 tests (all passing)
- [ ] Update design document with typed handler and None filtering (recommended)
- [ ] Execute manual test Steps 13, 14
- [ ] Write completion report (`mcp-server.report.md`)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-13 | Initial analysis - 100% match rate | gap-detector |
| 2.0 | 2026-03-13 | Post manual testing - 2 bug fixes reflected, design exceeded in 2 areas | gap-detector |
