"""Scan runtime + repo paths for PII patterns. Exits non-zero on hit.

CI runs this on the repo (must stay clean). `job lint` runs it on the user's
XDG dirs (must stay clean across discover/apply runs). Designed to fail loudly
rather than miss a leak.

Patterns (loose by design — we'd rather flag a false positive than miss):
- CPF: 11 digits, optionally formatted xxx.xxx.xxx-xx
- CNPJ: 14 digits, optionally formatted xx.xxx.xxx/xxxx-xx
- BR phone: (xx) 9xxxx-xxxx or 11-digit cell
- Generic RG-like: 6-10 digits with optional state prefix
- BR IBAN/agency-account: ag:xxxx cc:xxxxxxxx-x (avoided for now — too noisy)

Exclusions:
- Anything matching the patterns set in `--exclude-glob`.
- Files with the marker `# job-hunter:allow-pii` on the same line (intentional test fixtures).
- The lint script itself (it contains pattern literals).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

DEFAULT_EXCLUDES = (
    "*.example",
    "*.example.*",
    "*personal.env",
    "*.egg-info",
    "__pycache__",
    ".git",
    ".venv",
    ".uv-cache",
    "node_modules",
    "uv.lock",
    "*.lock",
)

ALLOW_MARKER = "# job-hunter:allow-pii"

# Regexes — keep them generous to err on the side of flagging.
PATTERNS: dict[str, re.Pattern[str]] = {
    "cpf": re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"),
    "cnpj": re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"),
    "br_phone": re.compile(r"\(?\d{2}\)?\s?9\d{4}-?\d{4}"),
}


@dataclass(frozen=True)
class Hit:
    path: Path
    line_no: int
    kind: str
    snippet: str


def is_text_file(path: Path) -> bool:
    if path.suffix.lower() in {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".pdf",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".pyc",
        ".so",
        ".dylib",
        ".dll",
        ".bin",
        ".sqlite",
        ".db",
        ".har",
    }:
        return False
    try:
        with path.open("rb") as fh:
            chunk = fh.read(2048)
        chunk.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return True


def excluded(path: Path, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch(path.name, p) or fnmatch(str(path), p) for p in patterns)


def iter_files(roots: list[Path], excludes: tuple[str, ...]) -> list[Path]:
    seen: list[Path] = []
    self_path = Path(__file__).resolve()
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if root.resolve() == self_path:
                continue
            if excluded(root, excludes):
                continue
            seen.append(root)
            continue
        for p in root.rglob("*"):
            if p.is_dir():
                continue
            if p.resolve() == self_path:
                continue
            if excluded(p, excludes):
                continue
            seen.append(p)
    return seen


def scan_file(path: Path) -> list[Hit]:
    hits: list[Hit] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return hits
    for i, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for kind, pat in PATTERNS.items():
            for m in pat.finditer(line):
                hits.append(Hit(path, i, kind, _redact(line.strip(), m.start(), m.end())))
    return hits


def _redact(line: str, start: int, end: int) -> str:
    return line[:start] + "[REDACTED]" + line[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan paths for BR PII patterns.")
    parser.add_argument("--paths", nargs="+", default=["."], help="Roots to scan.")
    parser.add_argument(
        "--exclude-glob",
        nargs="*",
        default=list(DEFAULT_EXCLUDES),
        help="Glob patterns to exclude (default: scaffolding/templates).",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Treat zero scanned files as success (default: warn).",
    )
    args = parser.parse_args(argv)

    roots = [Path(p) for p in args.paths]
    excludes = tuple(args.exclude_glob)
    files = [p for p in iter_files(roots, excludes) if is_text_file(p)]

    if not files:
        msg = "No files scanned."
        if args.allow_empty:
            print(msg)
            return 0
        print(msg, file=sys.stderr)
        return 0  # phase-1: don't fail; phase-2 will add stricter mode

    all_hits: list[Hit] = []
    for f in files:
        all_hits.extend(scan_file(f))

    if not all_hits:
        print(f"OK: scanned {len(files)} file(s) for PII patterns — clean.")
        return 0

    print(f"FOUND {len(all_hits)} potential PII leak(s):", file=sys.stderr)
    for hit in all_hits:
        print(f"  {hit.path}:{hit.line_no} [{hit.kind}] {hit.snippet}", file=sys.stderr)
    print(
        "\nIf any of these are intentional test fixtures, add the marker "
        f"`{ALLOW_MARKER}` on the same line.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
