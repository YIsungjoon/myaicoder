"""Project context management (MYAICODER.md loading, project structure scan)."""

from pathlib import Path


class ContextManager:
    """Manages project context for system prompt construction.

    Loads MYAICODER.md for project-specific instructions.
    """

    BASE_PROMPT = """/no_think
You are myAiCoder, an AI coding assistant running locally.
Always respond in Korean. Write code and comments in English.

Behavior rules:
- Be concise and direct. No unnecessary explanations.
- NEVER use tools without user's explicit request or approval.
- When the user greets you, just greet back briefly. Do NOT analyze the project.
- Before taking any action (reading files, creating files, running commands), ask the user first.
- Only proceed with tool calls when the user clearly asks you to do something.
- If the user's request is ambiguous, ask a clarifying question instead of guessing.

Tool usage priority (when approved by user):
- Read files: use read_file (NOT Bash cat/type)
- Create/write files: use write_file (auto-creates parent directories)
- Modify files: use edit_file
- Search files: use glob_search or grep_search
- List directory: use list_dir (NOT Bash ls/dir)
- Only use Bash for system commands (git, npm, pip, pytest, etc.)
- NEVER use Bash for file read/write/edit when dedicated tools exist.

Project-specific instructions can be placed in MYAICODER.md at the workspace root."""

    AGENTIC_BASE_PROMPT = """You are myAiCoder agent executing a task autonomously.
Always respond in Korean. Write code and comments in English.

## 조기 대답 규칙 (EARLY EXIT - CRITICAL)
- 사용자가 건넨 입력이 도구(Tool) 호출이나 파일 분석/수정이 전혀 필요하지 않은 단순 인사말, 안부, 혹은 간단한 일반 질문인 경우, `write_todos`를 호출하거나 아래의 TAO 루프를 도는 복잡한 행동을 하지 말고 즉시 일반 텍스트로 친절하고 간결하게 최종 답변을 하라.
- 도구를 사용하는 분석이나 개발 요청인 경우에만 아래의 필수 절차를 따른다.

## 에이전트 사고 방식 (TAO 루프 - MANDATORY)
너는 도구를 사용하는 모든 추론 단계에서 반드시 TAO (Thought-Action-Observation) 구조를 따라야 한다.
답변을 출력할 때마다 반드시 다음 형식으로 생각(Thought)과 행동(Action)을 명시하라:

THOUGHT: <현재 태스크 상태를 진단하고, 목표 달성을 위해 다음으로 어떤 도구를 호출해야 하는지, 혹은 이전 Observation을 기반으로 분석이 끝났는지에 대한 논리적 생각 과정>
ACTION: <호출할 도구명과 파라미터 설명 (이후 실제 OpenAI tool_calls를 함께 리턴해야 함)>

- 이전 행동(Action)의 실행 결과(Observation)를 수신하면, 다음 THOUGHT 단계에서 해당 Observation의 데이터를 면밀히 분석하라.
- 만약 Observation을 통해 획득한 정보가 사용자의 요청을 충족하기에 충분하다면, 더 이상 추가 도구를 호출하지 말고 즉시 최종 답변(Final Answer)을 출력하여 태스크를 완수하고 루프를 탈출(break)하라.

## 시작 전 필수 절차 (MANDATORY)
1. 답변을 곧바로 텍스트로만 반환하지 마라.
2. 분석이나 코딩을 시작하기 전에 반드시 `write_todos` 툴로 할 일 목록을 먼저 작성한다 ([ ] 상태로).
3. 각 항목 시작 시 `write_todos`로 상태를 [~] in_progress로 업데이트하고, 완료 시 [x] done으로 업데이트한다.
4. 분석할 대상 파일이 워크스페이스에 존재하면, 답변을 출력하기 전에 **반드시 `read_file` 툴을 호출하여 파일들의 실제 내용을 먼저 읽어야 한다.** 단지 파일 이름만 보고 추측하여 "어떤 작업을 원하시나요?"라고 질문을 돌려막지 마라.

## 범위 경계 규칙 (CRITICAL)
- 요청에 번호가 있으면 (예: "3-1", "1단계", "섹션 A"):
  - **해당 번호의 작업만 완료**하고 즉시 멈춘다.
  - 다음 번호로 자동 진행 절대 금지.
  - 완료 후 반드시: "✅ [번호] 완료. 다음: '[다음 번호]' 요청 시 이어서 진행합니다."
- 1번의 호출로 완료하기 어려운 양이라면:
  - 첫 번째 의미 있는 단위에서 멈추고 진행 상황을 보고한다.
  - "⏸ 여기까지 완료. '[다음 작업]'을 요청하면 계속합니다."

## 실행 규칙
- 파일 수정 전에 read_file로 먼저 읽는다.
- 툴 에러 시 1회만 재시도.
- 완료 후 변경 파일 목록과 요약을 간결하게 출력.

## 툴 사용
- 파일 읽기: read_file
- 파일 생성/쓰기: write_file (부모 디렉토리 자동 생성)
- 파일 수정: edit_file
- 검색: glob_search, grep_search
- 디렉토리 목록: list_dir
- 시스템 명령: run_command (git, npm, pip 등)"""

    def __init__(self, working_dir: str | None = None, base_prompt: str | None = None):
        self.working_dir = Path(working_dir or Path.cwd())
        self._base_prompt = base_prompt or self.BASE_PROMPT

    def build_system_prompt(self) -> str:
        parts = [self._base_prompt]

        claude_md = self._load_claude_md()
        if claude_md:
            parts.append(f"# Project Context\n{claude_md}")

        structure = self._scan_project_structure()
        if structure:
            parts.append(f"# Project Structure\n```\n{structure}\n```")

        env_info = self._environment_info()
        parts.append(f"# Environment\n{env_info}")

        return "\n\n".join(parts)

    def _load_claude_md(self) -> str | None:
        """Load MYAICODER.md hierarchically.

        1. {working_dir}/MYAICODER.md
        2. ~/.config/myaicoder/MYAICODER.md (global)
        """
        paths = [
            self.working_dir / "MYAICODER.md",
            Path.home() / ".config" / "myaicoder" / "MYAICODER.md",
        ]

        contents = []
        for p in paths:
            if p.exists():
                contents.append(p.read_text(encoding="utf-8"))

        return "\n\n".join(contents) if contents else None

    def _scan_project_structure(self, max_depth: int = 3) -> str | None:
        """Scan project directory structure, respecting .gitignore."""
        if not self.working_dir.is_dir():
            return None

        lines = []
        self._walk_dir(self.working_dir, lines, depth=0, max_depth=max_depth)
        return "\n".join(lines) if lines else None

    def _walk_dir(
        self, path: Path, lines: list[str], depth: int, max_depth: int
    ) -> None:
        if depth >= max_depth:
            return

        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".next", "dist", ".terraform", ".mypy_cache", ".ruff_cache",
        }

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") and entry.is_dir():
                continue
            if entry.name in skip_dirs:
                continue

            indent = "  " * depth
            if entry.is_dir():
                lines.append(f"{indent}{entry.name}/")
                self._walk_dir(entry, lines, depth + 1, max_depth)
            else:
                lines.append(f"{indent}{entry.name}")

    def _environment_info(self) -> str:
        import platform

        system = platform.system().lower()
        info = (
            f"- Working directory: {self.working_dir}\n"
            f"- Platform: {system}\n"
            f"- Python: {platform.python_version()}"
        )

        if system == "windows":
            info += (
                "\n- Shell: cmd.exe (use Windows commands, NOT Linux commands)"
                "\n- Use 'mkdir' instead of 'mkdir -p'"
                "\n- Use 'dir' instead of 'ls'"
                "\n- Use 'type' instead of 'cat'"
                "\n- Use 'copy' instead of 'cp'"
                "\n- Use 'del' instead of 'rm'"
                "\n- Path separator: backslash (\\)"
            )

        return info
