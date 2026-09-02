"""SessionStart hook: inject the prompting profile that matches the session model.

Claude Code sends a JSON object on stdin; when it includes ``model`` (it does not always),
we pick the matching ``## model: <slug>`` section of ``.claude/model_profiles.md`` and emit
it as additionalContext together with the ``## model: common`` section. When the model is
unknown we emit the common section plus a one-line pointer so the model reads its own
section (it knows its own name from the system prompt).

Fail-soft by design: any error prints nothing and exits 0, so a broken profile file can
never block a session.

Usage (manual test):  python .claude/hooks/model_profile.py --model claude-opus-5 --plain
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

SLUGS = (  # substring of the model id/name -> section slug (order matters)
    ("fable", "fable-5-1"),
    ("mythos", "fable-5-1"),
    ("opus", "opus-5"),
    ("sonnet", "sonnet-5"),
    ("haiku", "haiku-4-5"),
)
MAX_CHARS = 6000


def project_root() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[2]


def sections(text: str) -> dict[str, str]:
    """Split on '## model: <slug>' headings; body runs to the next '## ' heading."""
    out: dict[str, str] = {}
    parts = re.split(r"^## model: ([a-z0-9\-]+)\s*$", text, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        body = re.split(r"^## ", parts[i + 1], maxsplit=1, flags=re.M)[0]
        out[parts[i]] = body.strip()
    return out


def pick_slug(model: str) -> str | None:
    m = model.lower()
    for needle, slug in SLUGS:
        if needle in m:
            return slug
    return None


def project_extra(root: Path) -> str:
    """Project-specific live facts appended after the profile (kept tiny)."""
    return ""


def build(model: str, root: Path) -> str:
    profile_path = root / ".claude" / "model_profiles.md"
    secs = sections(profile_path.read_text(encoding="utf-8"))
    slug = pick_slug(model) if model else None
    lines = ["# Model prompting profile (SessionStart hook, .claude/model_profiles.md)"]
    if "common" in secs:
        lines += ["", "## common", secs["common"]]
    if slug and slug in secs:
        lines += ["", f"## {slug} (detected model: {model})", secs[slug]]
    else:
        lines += [
            "",
            "Model not reported by the hook. You know your model from your system prompt: "
            "read the matching `## model:` section of `.claude/model_profiles.md` now.",
        ]
    extra = project_extra(root)
    if extra:
        lines += ["", extra]
    text = "\n".join(lines)
    return text[:MAX_CHARS]


def main(argv: list[str]) -> int:
    # Windows consoles default to a legacy code page; the profile and PROGRESS.md are UTF-8.
    for stream in (sys.stdout, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    model = ""
    if "--model" in argv:
        model = argv[argv.index("--model") + 1]
    else:
        try:
            raw = sys.stdin.read() if not sys.stdin.isatty() else ""
            if raw.strip():
                model = str(json.loads(raw).get("model") or "")
        except Exception:
            model = ""
    text = build(model, project_root())
    if "--plain" in argv:
        sys.stdout.write(text + "\n")
    else:
        payload = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
        sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        sys.exit(0)
