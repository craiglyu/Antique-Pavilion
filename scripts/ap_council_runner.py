#!/usr/bin/env python3
"""ap_council_runner.py — entry for Council Protocol state machine (3-state pilot).

Sprint 1 functionality:
- `list`                          : show all active topics
- `new <description>`             : create a NEW topic from CLI
- `show <topic_id>`               : print full JSON state
- `advance <topic_id> <state>`    : force-advance (Craig admin)
- `signoff <topic_id> <decision>` : record sign-off + auto-dispatch tasks

Future Sprint 3 will add: `--phase1`, `--phase2`, `--phase3` automation that
calls Council members (PM, Designer, etc.) in parallel via the agent registry.
For now, all phase work happens manually in #council-meetings; this runner
manages persistence and dispatch only.

Run:
    python -u scripts/ap_council_runner.py list
    python -u scripts/ap_council_runner.py new "首頁 Hero 區應該放藏品輪播還是品牌敘事影片？"
    python -u scripts/ap_council_runner.py advance ap-2026-04-30-103200-001 STRUCTURED
    python -u scripts/ap_council_runner.py signoff ap-2026-04-30-103200-001 approve
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from any cwd.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from ap_org_bot.council.dispatcher import (  # noqa: E402
    append_dispatched_tasks,
    convened_agents_for,
)
from ap_org_bot.council.persistence import (  # noqa: E402
    list_active_topics,
    load_topic,
    make_topic_id,
    save_topic,
)
from ap_org_bot.council.state_machine import (  # noqa: E402
    IllegalTransitionError,
    State,
    Topic,
    transition,
)


def cmd_list(_args: argparse.Namespace) -> int:
    topics = list_active_topics()
    if not topics:
        print("(no active topics)")
        return 0
    print(f"{'topic_id':<32} {'state':<20} {'type':<12} raw_input")
    for t in topics:
        print(f"{t.topic_id:<32} {t.state.value:<20} {t.topic_type:<12} "
              f"{t.raw_input[:60]}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    topic_id = make_topic_id()
    now = datetime.now(timezone.utc).isoformat()
    topic = Topic(
        topic_id=topic_id,
        created_at=now,
        updated_at=now,
        raw_input=args.description,
        topic_type=args.type,
    )
    topic.audit_log.append({
        "ts": now, "from": None, "to": "NEW",
        "actor": "cli", "payload": {"raw_input": args.description},
    })
    convened = convened_agents_for(args.type)
    if convened:
        topic.convened = convened
    save_topic(topic)
    print(f"created {topic_id} (type={args.type}, convened={convened})")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    topic = load_topic(args.topic_id)
    if topic is None:
        print(f"topic {args.topic_id} not found", file=sys.stderr)
        return 1
    print(json.dumps(topic.to_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    topic = load_topic(args.topic_id)
    if topic is None:
        print(f"topic {args.topic_id} not found", file=sys.stderr)
        return 1
    try:
        target_state = State(args.state)
    except ValueError:
        print(f"unknown state {args.state!r}", file=sys.stderr)
        print(f"valid: {[s.value for s in State]}", file=sys.stderr)
        return 1
    try:
        transition(topic, target_state, actor=args.actor or "cli")
    except IllegalTransitionError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    save_topic(topic)
    print(f"{topic.topic_id} now {topic.state.value}")
    return 0


def cmd_signoff(args: argparse.Namespace) -> int:
    topic = load_topic(args.topic_id)
    if topic is None:
        print(f"topic {args.topic_id} not found", file=sys.stderr)
        return 1
    target = State.SIGNED_OFF if args.decision == "approve" else State.REJECTED
    try:
        transition(topic, target, actor=args.actor or "cli")
    except IllegalTransitionError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    topic.signoff = {
        "decision": args.decision,
        "decided_by": args.actor or "cli",
        "decided_at": topic.updated_at,
        "reaction": "✅" if args.decision == "approve" else "❌",
    }

    # If approved + has follow-up tasks pre-staged in pilot_proposal, dispatch now.
    if target == State.SIGNED_OFF and topic.pilot_proposal:
        for t in topic.pilot_proposal.get("follow_up_tasks", []):
            topic.dispatched_tasks.append(t)

    save_topic(topic)
    written_to = append_dispatched_tasks(topic)
    print(f"{topic.topic_id} → {topic.state.value}")
    if written_to:
        print(f"dispatched {len(topic.dispatched_tasks)} task(s) to {written_to}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ap_council_runner",
        description="AP Council Protocol — 3-state pilot CLI",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all active topics")

    p_new = sub.add_parser("new", help="create a new topic in NEW state")
    p_new.add_argument("description", help="raw topic description")
    p_new.add_argument(
        "--type", default="其他",
        help="topic type from council_routing.yaml (default: 其他)",
    )

    p_show = sub.add_parser("show", help="print full JSON state")
    p_show.add_argument("topic_id")

    p_adv = sub.add_parser("advance", help="advance state (admin)")
    p_adv.add_argument("topic_id")
    p_adv.add_argument("state", help="target state name")
    p_adv.add_argument("--actor", default="cli")

    p_so = sub.add_parser("signoff", help="record sign-off decision")
    p_so.add_argument("topic_id")
    p_so.add_argument("decision", choices=["approve", "reject"])
    p_so.add_argument("--actor", default="cli")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "list": cmd_list,
        "new": cmd_new,
        "show": cmd_show,
        "advance": cmd_advance,
        "signoff": cmd_signoff,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
