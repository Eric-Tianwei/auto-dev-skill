#!/usr/bin/env python3
"""
validate_dag.py — minimal zero-dependency validator for .auto-dev/dag.json.

Catches *structural collapse* only: malformed JSON, missing top-level fields,
dangling edge references, cycles. It does NOT judge whether the graph is a
good plan — that's the AI's job.

Usage:
  python3 scripts/validate_dag.py [path]

Default path: .auto-dev/dag.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
NODE_STATUSES = {"pending", "dev", "done", "blocked", "abandoned"}


def validate(dag: object) -> list[str]:
    errs: list[str] = []

    if not isinstance(dag, dict):
        return ["root: must be object"]

    if dag.get("version") != 2:
        errs.append(f"root.version: must be 2 (got {dag.get('version')!r})")
    for key in ("base_branch", "upstream_branch"):
        v = dag.get(key)
        if not isinstance(v, str) or not v:
            errs.append(f"root.{key}: must be non-empty string")

    nodes = dag.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errs.append("root.nodes: must be non-empty array")
        nodes = []

    edges = dag.get("edges")
    if not isinstance(edges, list):
        errs.append("root.edges: must be array")
        edges = []

    or_groups = dag.get("or_groups", [])
    if not isinstance(or_groups, list):
        errs.append("root.or_groups: must be array")
        or_groups = []

    # nodes
    ids: list[str] = []
    for i, n in enumerate(nodes):
        if not isinstance(n, dict):
            errs.append(f"nodes[{i}]: must be object")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not NODE_ID_RE.match(nid or ""):
            errs.append(f"nodes[{i}].id: must match ^[a-z0-9][a-z0-9-]*$")
        else:
            ids.append(nid)
        if n.get("status") not in NODE_STATUSES:
            errs.append(f"nodes[{i}].status: must be one of {sorted(NODE_STATUSES)}")

    id_set = set(ids)
    if len(ids) != len(id_set):
        dup = sorted({x for x in ids if ids.count(x) > 1})
        errs.append(f"nodes: duplicate ids {dup}")

    # edges
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            errs.append(f"edges[{i}]: must be object")
            continue
        f, t = e.get("from"), e.get("to")
        if f not in id_set:
            errs.append(f"edges[{i}].from='{f}': not a known node id")
        if t not in id_set:
            errs.append(f"edges[{i}].to='{t}': not a known node id")
        if f == t and f is not None:
            errs.append(f"edges[{i}]: self-loop on '{f}'")

    # or_groups
    for i, og in enumerate(or_groups):
        if not isinstance(og, dict):
            errs.append(f"or_groups[{i}]: must be object")
            continue
        if not isinstance(og.get("id"), str) or not og.get("id"):
            errs.append(f"or_groups[{i}].id: must be non-empty string")
        cands = og.get("candidates")
        if not isinstance(cands, list) or len(cands) < 2:
            errs.append(f"or_groups[{i}].candidates: must have >= 2 node ids")
        else:
            for j, c in enumerate(cands):
                if c not in id_set:
                    errs.append(f"or_groups[{i}].candidates[{j}]='{c}': not a known node id")
        decided = og.get("decided")
        if decided is not None and decided not in id_set:
            errs.append(f"or_groups[{i}].decided='{decided}': not a known node id")
        for j, rj in enumerate(og.get("rejected", []) or []):
            if rj not in id_set:
                errs.append(f"or_groups[{i}].rejected[{j}]='{rj}': not a known node id")

    if errs:
        return errs

    # cycle detection (only when structure is clean)
    adj: dict[str, list[str]] = {n: [] for n in ids}
    for e in edges:
        if isinstance(e, dict):
            f, t = e.get("from"), e.get("to")
            if f in adj and t in adj:
                adj[f].append(t)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in ids}
    parent: dict[str, str | None] = {n: None for n in ids}

    def dfs(u: str) -> list[str] | None:
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                path = [v, u]
                cur = parent[u]
                while cur is not None and cur != v:
                    path.append(cur)
                    cur = parent[cur]
                path.append(v)
                return list(reversed(path))
            if color[v] == WHITE:
                parent[v] = u
                c = dfs(v)
                if c is not None:
                    return c
        color[u] = BLACK
        return None

    for n in ids:
        if color[n] == WHITE:
            cycle = dfs(n)
            if cycle:
                errs.append(f"cycle detected: {' -> '.join(cycle)}")
                break

    return errs


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path(".auto-dev/dag.json")
    if not path.exists():
        print(f"validate_dag: no such file: {path}", file=sys.stderr)
        return 2
    try:
        dag = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        print(f"validate_dag: JSON parse error in {path}: {ex}", file=sys.stderr)
        return 2

    errs = validate(dag)
    if not errs:
        print(f"validate_dag: OK ({path})")
        return 0

    print(f"validate_dag: FAIL ({path})", file=sys.stderr)
    for e in errs:
        print(f"  - {e}", file=sys.stderr)
    print(f"  ({len(errs)} error(s))", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
