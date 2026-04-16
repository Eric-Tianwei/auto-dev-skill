#!/usr/bin/env python3
"""
validate_dag.py — zero-dependency validator for .auto-dev/dag.json.

Hard-enforces the invariants the auto-dev skill relies on. Exits non-zero if
anything fails so design.md / review-gate.md can gate on this script.

Covers:
  - Required top-level fields, types, versions
  - Node schema (id format, required fields, enum values)
  - Edge schema (required fields, enum, rationale non-empty)
  - AND edges have and_group; OR edges have or_group referencing or_groups
  - Referential integrity (edges.from/to exist in nodes)
  - No cycles
  - No orphans (non-root node with no incoming edge)
  - No SEQ chain longer than 3 nodes without a non-SEQ break
  - or_groups.candidates / decided / rejected all reference existing nodes

Usage:
  python3 scripts/validate_dag.py [path-to-dag.json]

Defaults to .auto-dev/dag.json in the current working directory.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
NODE_KINDS = {"COMMON", "OR_HEAD", "SEQ", "AND", "SPIKE"}
NODE_STATUSES = {
    "pending", "dev", "done", "blocked",
    "pending-review", "abandoned", "decided",
}
EDGE_TYPES = {"SEQ", "AND", "OR"}
OR_TYPES = {"A", "B"}
MAX_SEQ_CHAIN = 3


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def ok(self) -> bool:
        return not self.errors


def _require(obj: dict, key: str, kind: type, path: str, r: Report) -> Any:
    if key not in obj:
        r.err(f"{path}: missing required field '{key}'")
        return None
    val = obj[key]
    if not isinstance(val, kind):
        r.err(f"{path}.{key}: expected {kind.__name__}, got {type(val).__name__}")
        return None
    return val


def validate_node(node: dict, path: str, r: Report) -> None:
    if not isinstance(node, dict):
        r.err(f"{path}: node must be object")
        return

    nid = _require(node, "id", str, path, r)
    if nid and not NODE_ID_RE.match(nid):
        r.err(f"{path}.id='{nid}': must match ^[a-z0-9][a-z0-9-]*$")

    kind = _require(node, "kind", str, path, r)
    if kind and kind not in NODE_KINDS:
        r.err(f"{path}.kind='{kind}': not in {sorted(NODE_KINDS)}")

    _require(node, "branch", str, path, r)

    entry = node.get("entry")
    if not isinstance(entry, list):
        r.err(f"{path}.entry: must be array of strings")
    else:
        for i, e in enumerate(entry):
            if not isinstance(e, str) or not e:
                r.err(f"{path}.entry[{i}]: must be non-empty string")

    completion = node.get("completion")
    if not isinstance(completion, list) or len(completion) < 1:
        r.err(f"{path}.completion: must be non-empty array of strings")
    else:
        for i, c in enumerate(completion):
            if not isinstance(c, str) or not c:
                r.err(f"{path}.completion[{i}]: must be non-empty string")

    scope = node.get("scope")
    if not isinstance(scope, dict):
        r.err(f"{path}.scope: must be object")
    else:
        mfc = scope.get("max_files_changed")
        if not isinstance(mfc, int) or mfc < 1:
            r.err(f"{path}.scope.max_files_changed: must be integer >= 1")

    rl = node.get("retry_limit")
    if not isinstance(rl, int) or rl < 1 or rl > 5:
        r.err(f"{path}.retry_limit: must be integer 1..5")

    status = node.get("status")
    if status not in NODE_STATUSES:
        r.err(f"{path}.status='{status}': not in {sorted(NODE_STATUSES)}")

    or_type = node.get("or_type")
    if or_type is not None and or_type not in OR_TYPES:
        r.err(f"{path}.or_type='{or_type}': not in {sorted(OR_TYPES)}")
    if kind == "OR_HEAD" and or_type is None:
        r.err(f"{path}: OR_HEAD node must set or_type (A or B)")


def validate_edge(edge: dict, path: str, r: Report) -> None:
    if not isinstance(edge, dict):
        r.err(f"{path}: edge must be object")
        return

    _require(edge, "from", str, path, r)
    _require(edge, "to", str, path, r)

    etype = _require(edge, "type", str, path, r)
    if etype and etype not in EDGE_TYPES:
        r.err(f"{path}.type='{etype}': not in {sorted(EDGE_TYPES)}")

    rationale = edge.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        r.err(f"{path}.rationale: REQUIRED non-empty string "
              f"(every edge must justify its type)")

    if etype == "AND":
        ag = edge.get("and_group")
        if not isinstance(ag, str) or not ag:
            r.err(f"{path}: AND edge must set and_group")
    if etype == "OR":
        og = edge.get("or_group")
        if not isinstance(og, str) or not og:
            r.err(f"{path}: OR edge must set or_group")


def detect_cycle(nodes: list[str], edges: list[dict]) -> list[str]:
    """Return a list of nodes forming a cycle, or empty list if DAG is acyclic."""
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for e in edges:
        f, t = e.get("from"), e.get("to")
        if f in adj and t in adj:
            adj[f].append(t)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    parent: dict[str, str | None] = {n: None for n in nodes}
    cycle: list[str] = []

    def dfs(u: str) -> bool:
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                # cycle found; walk parent chain
                cur = u
                cycle.append(v)
                while cur is not None and cur != v:
                    cycle.append(cur)
                    cur = parent[cur]
                cycle.append(v)
                cycle.reverse()
                return True
            if color[v] == WHITE:
                parent[v] = u
                if dfs(v):
                    return True
        color[u] = BLACK
        return False

    for n in nodes:
        if color[n] == WHITE and dfs(n):
            return cycle
    return []


def longest_seq_chain(nodes: list[str], edges: list[dict]) -> tuple[int, list[str]]:
    """
    Build SEQ-only subgraph and return (max chain length in node count, example path).
    A SEQ chain of length k means k nodes connected by k-1 consecutive SEQ edges.
    """
    seq_adj: dict[str, list[str]] = {n: [] for n in nodes}
    for e in edges:
        if e.get("type") == "SEQ":
            f, t = e.get("from"), e.get("to")
            if f in seq_adj and t in seq_adj:
                seq_adj[f].append(t)

    memo: dict[str, tuple[int, list[str]]] = {}

    def longest_from(u: str, stack: set[str]) -> tuple[int, list[str]]:
        if u in memo:
            return memo[u]
        best_len, best_path = 1, [u]
        for v in seq_adj[u]:
            if v in stack:
                continue  # cycle handled elsewhere
            stack.add(v)
            ln, pth = longest_from(v, stack)
            stack.remove(v)
            if ln + 1 > best_len:
                best_len = ln + 1
                best_path = [u] + pth
        memo[u] = (best_len, best_path)
        return memo[u]

    overall_len, overall_path = 0, []
    for n in nodes:
        ln, pth = longest_from(n, {n})
        if ln > overall_len:
            overall_len = ln
            overall_path = pth
    return overall_len, overall_path


def validate(dag: dict, r: Report) -> None:
    # top-level
    if not isinstance(dag, dict):
        r.err("root: must be object")
        return

    version = dag.get("version")
    if version != 1:
        r.err(f"root.version: must be 1 (got {version!r})")

    for key in ("base_branch", "upstream_branch"):
        if not isinstance(dag.get(key), str) or not dag.get(key):
            r.err(f"root.{key}: must be non-empty string")

    nodes = dag.get("nodes")
    if not isinstance(nodes, list) or len(nodes) < 1:
        r.err("root.nodes: must be non-empty array")
        nodes = []

    edges = dag.get("edges")
    if not isinstance(edges, list):
        r.err("root.edges: must be array")
        edges = []

    or_groups = dag.get("or_groups", [])
    if not isinstance(or_groups, list):
        r.err("root.or_groups: must be array")
        or_groups = []

    # per-node schema
    for i, node in enumerate(nodes):
        validate_node(node, f"nodes[{i}]", r)

    # per-edge schema
    for i, edge in enumerate(edges):
        validate_edge(edge, f"edges[{i}]", r)

    # collect ids (only valid-typed ones)
    node_ids = [n.get("id") for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), str)]
    id_set = set(node_ids)
    if len(node_ids) != len(id_set):
        dup = [x for x in node_ids if node_ids.count(x) > 1]
        r.err(f"nodes: duplicate ids {sorted(set(dup))}")

    # edge referential integrity
    for i, e in enumerate(edges):
        if not isinstance(e, dict):
            continue
        f, t = e.get("from"), e.get("to")
        if f not in id_set:
            r.err(f"edges[{i}].from='{f}': not a known node id")
        if t not in id_set:
            r.err(f"edges[{i}].to='{t}': not a known node id")
        if f == t:
            r.err(f"edges[{i}]: self-loop on '{f}'")

    # or_groups referential integrity + OR edge coverage
    og_ids: set[str] = set()
    for i, og in enumerate(or_groups):
        if not isinstance(og, dict):
            r.err(f"or_groups[{i}]: must be object")
            continue
        ogid = og.get("id")
        if not isinstance(ogid, str) or not ogid:
            r.err(f"or_groups[{i}].id: must be non-empty string")
            continue
        og_ids.add(ogid)
        q = og.get("question")
        if not isinstance(q, str) or not q:
            r.err(f"or_groups[{i}].question: must be non-empty string")
        if og.get("or_type") not in OR_TYPES:
            r.err(f"or_groups[{i}].or_type: must be 'A' or 'B'")
        cands = og.get("candidates", [])
        if not isinstance(cands, list) or len(cands) < 2:
            r.err(f"or_groups[{i}].candidates: must have >= 2 node ids")
        else:
            for j, c in enumerate(cands):
                if c not in id_set:
                    r.err(f"or_groups[{i}].candidates[{j}]='{c}': not a known node id")
        decided = og.get("decided")
        if decided is not None and decided not in id_set:
            r.err(f"or_groups[{i}].decided='{decided}': not a known node id")
        rejected = og.get("rejected", [])
        if isinstance(rejected, list):
            for j, rj in enumerate(rejected):
                if rj not in id_set:
                    r.err(f"or_groups[{i}].rejected[{j}]='{rj}': not a known node id")

    for i, e in enumerate(edges):
        if isinstance(e, dict) and e.get("type") == "OR":
            og = e.get("or_group")
            if og not in og_ids:
                r.err(f"edges[{i}].or_group='{og}': not declared in root.or_groups[]")

    # abort structural topology checks if the graph is already broken
    if not r.ok():
        return

    # cycles
    cyc = detect_cycle(node_ids, edges)
    if cyc:
        r.err(f"cycle detected: {' -> '.join(cyc)}")
        return  # downstream checks assume DAG

    # orphans: nodes with no incoming edge AND not roots in any sensible sense.
    # We flag the count, but allow multiple roots — a DAG can legitimately
    # start with several COMMON nodes. Just warn on fully-isolated nodes
    # (no incoming AND no outgoing edges) when there is more than one node.
    if len(node_ids) > 1:
        has_in = {n: False for n in node_ids}
        has_out = {n: False for n in node_ids}
        for e in edges:
            if isinstance(e, dict):
                if e.get("to") in has_in:
                    has_in[e["to"]] = True
                if e.get("from") in has_out:
                    has_out[e["from"]] = True
        for n in node_ids:
            if not has_in[n] and not has_out[n]:
                r.err(f"node '{n}': isolated (no incoming or outgoing edges)")

    # SEQ chain length
    chain_len, chain_path = longest_seq_chain(node_ids, edges)
    if chain_len > MAX_SEQ_CHAIN:
        r.err(
            f"SEQ chain exceeds {MAX_SEQ_CHAIN} nodes "
            f"(length {chain_len}): {' -> '.join(chain_path)}. "
            f"Break with AND/OR, challenge whether each SEQ is a real dependency, "
            f"or split into sub-features."
        )


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path(".auto-dev/dag.json")
    if not path.exists():
        print(f"validate_dag: no such file: {path}", file=sys.stderr)
        return 2

    try:
        with path.open("r", encoding="utf-8") as f:
            dag = json.load(f)
    except json.JSONDecodeError as ex:
        print(f"validate_dag: JSON parse error in {path}: {ex}", file=sys.stderr)
        return 2

    r = Report()
    validate(dag, r)

    if r.ok():
        print(f"validate_dag: OK ({path})")
        return 0

    print(f"validate_dag: FAIL ({path})", file=sys.stderr)
    for e in r.errors:
        print(f"  - {e}", file=sys.stderr)
    print(f"  ({len(r.errors)} error(s))", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
