import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeTraceData:
    executed_lines: dict[str, set[int]] = field(default_factory=dict)
    call_counts: dict[str, int] = field(default_factory=dict)
    source: str = "unknown"


def parse_trace_dict(data: dict[str, Any], source: str = "inline") -> RuntimeTraceData:
    """
    Parse a dictionary representation of execution traces.
    Supports:
    1. Coverage.py JSON export: {"files": {"path/to/file.py": {"executed_lines": [1, 2, ...]}}}
    2. Structured trace logs: {"executed_lines": {"user.py": [1, 2]}, "call_counts": {"user.py:func": 5}}
    3. Direct file line map: {"user.py": [1, 2, 3]}
    """
    executed_lines: dict[str, set[int]] = {}
    call_counts: dict[str, int] = {}

    if "call_counts" in data and isinstance(data["call_counts"], dict):
        call_counts = {str(k): int(v) for k, v in data["call_counts"].items()}

    # Format 1: coverage.py JSON format
    if "files" in data and isinstance(data["files"], dict):
        for raw_path, file_data in data["files"].items():
            norm_path = Path(raw_path).as_posix()
            lines = file_data.get("executed_lines", [])
            executed_lines[norm_path] = {int(line) for line in lines}

    # Format 2: explicit executed_lines key
    elif "executed_lines" in data and isinstance(data["executed_lines"], dict):
        for raw_path, lines in data["executed_lines"].items():
            norm_path = Path(raw_path).as_posix()
            executed_lines[norm_path] = {int(line) for line in lines}

    # Format 3: direct {filename: [lines]} mapping
    else:
        for raw_path, lines in data.items():
            if raw_path == "call_counts":
                continue
            if isinstance(lines, list):
                norm_path = Path(raw_path).as_posix()
                executed_lines[norm_path] = {int(line) for line in lines}

    return RuntimeTraceData(
        executed_lines=executed_lines,
        call_counts=call_counts,
        source=source,
    )


def load_runtime_trace(
    repo_path: Path | str,
    trace_file: str | None = None,
) -> RuntimeTraceData | None:
    """
    Load runtime trace data from a file in the repository or from an absolute path.
    If trace_file is None, searches for 'runtime_trace.json', 'coverage.json',
    or 'trace.json' in repo_path.
    """
    repo_path = Path(repo_path)

    candidate_files: list[Path] = []
    if trace_file:
        custom_path = Path(trace_file)
        if custom_path.is_absolute():
            candidate_files.append(custom_path)
        else:
            candidate_files.append(repo_path / custom_path)
    else:
        for name in ("runtime_trace.json", "coverage.json", "trace.json"):
            candidate_files.append(repo_path / name)

    for target in candidate_files:
        if target.is_file():
            try:
                content = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(content, dict):
                    return parse_trace_dict(content, source=target.name)
            except Exception:
                continue

    return None
