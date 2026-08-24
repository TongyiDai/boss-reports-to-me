#!/usr/bin/env python3
"""Optional automatic leader-chain resolver for boss-reports-to-me.

Walks up the org chart using contact/v3 `leader_open_id`, starting from the
current user, up to N levels (+1..+N). Requires the lark-cli user token to
hold the `contact:contact.base:readonly` scope; if it does not, this exits
cleanly with needs_scope=true so the caller falls back to the manual roster.

This script only RESOLVES the chain and prints it. It does not write the
roster; the caller shows the chain to the user for confirmation, then uses
roster.py to persist it.

Output (stdout JSON):
  {"ok": true, "chain": [{"level": "直属上级", "name": "...", "open_id": "ou_..."}, ...]}
  {"ok": false, "needs_scope": true, "missing_scopes": [...]}   # graceful fallback
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

MISSING_SCOPE_CODE = 99991679


def lark_get_user(open_id: str, profile: str | None) -> dict:
    """Call contact/v3/users/:open_id as the user; return parsed JSON envelope."""
    cmd = ["lark-cli"]
    if profile:
        cmd += ["--profile", profile]
    cmd += [
        "api",
        "--as",
        "user",
        "GET",
        f"/open-apis/contact/v3/users/{open_id}",
        "--params",
        json.dumps({"user_id_type": "open_id", "department_id_type": "open_department_id"}),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # lark-cli prints success envelopes to stdout and error envelopes to stderr;
    # try both so missing-scope errors are parsed as structured JSON, not opaque text.
    for stream in (proc.stdout, proc.stderr):
        stream = (stream or "").strip()
        if not stream:
            continue
        try:
            return json.loads(stream)
        except json.JSONDecodeError:
            continue
    return {"ok": False, "error": {"message": (proc.stderr or proc.stdout or "no output").strip()}}


def self_open_id(profile: str | None) -> str | None:
    cmd = ["lark-cli"]
    if profile:
        cmd += ["--profile", profile]
    cmd += ["contact", "+get-user", "--as", "user", "--format", "json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout)
        return data.get("data", {}).get("user", {}).get("open_id")
    except (json.JSONDecodeError, AttributeError):
        return None


def level_label(depth: int) -> str:
    return "直属上级" if depth == 1 else f"+{depth}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start-open-id", help="open_id to start from; default = current user")
    ap.add_argument("--levels", type=int, default=4, help="how many levels up (default 4)")
    ap.add_argument("--profile", help="lark-cli profile")
    args = ap.parse_args()

    start = args.start_open_id or self_open_id(args.profile)
    if not start:
        print(json.dumps({"ok": False, "error": "could not resolve current user open_id"}))
        return 1

    chain = []
    current = start
    for depth in range(1, args.levels + 1):
        env = lark_get_user(current, args.profile)
        if not env.get("ok"):
            err = env.get("error", {}) or {}
            if err.get("code") == MISSING_SCOPE_CODE or err.get("subtype") == "missing_scope":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "needs_scope": True,
                            "missing_scopes": err.get(
                                "missing_scopes", ["contact:contact.base:readonly"]
                            ),
                            "resolved_so_far": chain,
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            print(
                json.dumps(
                    {"ok": False, "error": err.get("message", "unknown"), "resolved_so_far": chain},
                    ensure_ascii=False,
                )
            )
            return 1
        user = env.get("data", {}).get("user", {})
        leader_id = user.get("leader_user_id") or user.get("leader_open_id")
        if not leader_id:
            break  # reached the top of the chain
        leader_env = lark_get_user(leader_id, args.profile)
        leader = leader_env.get("data", {}).get("user", {}) if leader_env.get("ok") else {}
        chain.append(
            {
                "level": level_label(depth),
                "name": leader.get("name") or leader.get("en_name") or "(未知)",
                "open_id": leader_id,
            }
        )
        current = leader_id

    print(json.dumps({"ok": True, "chain": chain}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
