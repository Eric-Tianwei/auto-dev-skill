#!/usr/bin/env python3
"""auto-dev — CLI for .auto-dev/ orchestration.

Shapes dag.json / state.json / node md files so the AI writes
decisions (node add, edge add, or decide) rather than JSON.
Every write prints an event line to stdout and appends one line to
.auto-dev/events.log.

Direct edits to .auto-dev/** remain valid; this CLI is sugar, not a wall.

Exit codes:
  0 ok
  1 usage error
  2 state error (.auto-dev missing, would leave dag inconsistent)
  3 not found
  4 conflict (exists / already decided / would cycle)
  5 validate failed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_NODE = SKILL_DIR / "templates" / "node.md"
TEMPLATE_SCHEMA = SKILL_DIR / "templates" / "dag.schema.json"

DOT = Path(".auto-dev")
DAG_PATH = DOT / "dag.json"
STATE_PATH = DOT / "state.json"
NODES_DIR = DOT / "nodes"
SCHEMA_PATH = DOT / "schema" / "dag.schema.json"
EVENTS_LOG = DOT / "events.log"

NODE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
NODE_STATUSES = ("pending", "dev", "done", "blocked", "abandoned")
PHASES = ("plan", "dev", "review-gate")


# ---------- io helpers ----------

def die(code: int, msg: str) -> None:
    print(f"! {msg}", file=sys.stderr)
    sys.exit(code)


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_dot() -> None:
    if not DOT.exists():
        die(2, ".auto-dev/ not found. Run `auto-dev init` first.")


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(2, f"{path}: not found")
    except json.JSONDecodeError as ex:
        die(2, f"{path}: JSON parse error: {ex}")
    return {}  # unreachable


def save_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def emit(line: str, *, log: bool = True) -> None:
    """Print event line to stdout and (optionally) append to events.log."""
    print(line)
    if log and DOT.exists():
        EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{iso_now()} {line}\n")


# ---------- dag helpers ----------

def validate_id(nid: str, *, field: str = "id") -> None:
    if not isinstance(nid, str) or not NODE_ID_RE.match(nid or ""):
        die(1, f"{field}={nid!r}: must match ^[a-z0-9][a-z0-9-]*$")


def node_ids(dag: dict) -> list[str]:
    return [n["id"] for n in dag.get("nodes", []) if isinstance(n, dict) and "id" in n]


def find_node(dag: dict, nid: str) -> dict | None:
    for n in dag.get("nodes", []):
        if isinstance(n, dict) and n.get("id") == nid:
            return n
    return None


def find_or_group(dag: dict, gid: str) -> dict | None:
    for g in dag.get("or_groups", []):
        if isinstance(g, dict) and g.get("id") == gid:
            return g
    return None


def edges_touching(dag: dict, nid: str) -> list[dict]:
    return [e for e in dag.get("edges", [])
            if isinstance(e, dict) and (e.get("from") == nid or e.get("to") == nid)]


def has_cycle(nodes: list[str], edges: list[dict]) -> bool:
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    for e in edges:
        if isinstance(e, dict):
            f, t = e.get("from"), e.get("to")
            if f in adj and t in adj:
                adj[f].append(t)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}

    def dfs(u: str) -> bool:
        color[u] = GRAY
        for v in adj[u]:
            if color[v] == GRAY:
                return True
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False

    return any(color[n] == WHITE and dfs(n) for n in nodes)


def consistency_check(dag: dict) -> list[str]:
    """Lightweight post-write check: references + no cycle.

    Does NOT enforce schema's minItems rules (nodes>=1, candidates>=2)
    because those are legitimately violated mid-plan.
    """
    errs: list[str] = []
    ids = set(node_ids(dag))
    if len(ids) != len([n for n in dag.get("nodes", []) if isinstance(n, dict) and "id" in n]):
        errs.append("duplicate node ids")
    for i, e in enumerate(dag.get("edges", [])):
        if not isinstance(e, dict):
            errs.append(f"edges[{i}]: not an object")
            continue
        f, t = e.get("from"), e.get("to")
        if f not in ids:
            errs.append(f"edges[{i}].from={f!r}: unknown node")
        if t not in ids:
            errs.append(f"edges[{i}].to={t!r}: unknown node")
        if f == t:
            errs.append(f"edges[{i}]: self-loop on {f!r}")
    for i, g in enumerate(dag.get("or_groups", [])):
        if not isinstance(g, dict):
            errs.append(f"or_groups[{i}]: not an object")
            continue
        for j, c in enumerate(g.get("candidates", []) or []):
            if c not in ids:
                errs.append(f"or_groups[{i}].candidates[{j}]={c!r}: unknown node")
        if g.get("decided") is not None and g["decided"] not in ids:
            errs.append(f"or_groups[{i}].decided={g['decided']!r}: unknown node")
    if not errs and has_cycle(list(ids), dag.get("edges", [])):
        errs.append("cycle detected")
    return errs


def save_dag_checked(dag: dict) -> None:
    errs = consistency_check(dag)
    if errs:
        die(2, "would leave dag inconsistent: " + "; ".join(errs))
    save_json_atomic(DAG_PATH, dag)


# ---------- frontmatter mutation ----------

def _split_fm(md: str) -> tuple[list[str], list[str]]:
    """Return (fm_inner_lines, body_lines). '---' delimiters not included in fm."""
    lines = md.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], lines[i + 1:]
    return [], lines  # malformed; treat as no frontmatter


def _assemble(fm: list[str], body: list[str]) -> str:
    out = ["---", *fm, "---", *body]
    return "\n".join(out) + ("\n" if not body or body[-1] != "" else "")


def rewrite_deps(md: str, new_deps: list[str]) -> str:
    fm, body = _split_fm(md)
    new_line = f"deps: [{', '.join(new_deps)}]"
    replaced = False
    for i, line in enumerate(fm):
        if line.startswith("deps:"):
            fm[i] = new_line
            replaced = True
            break
    if not replaced:
        fm.append(new_line)
    return _assemble(fm, body)


def set_or_candidate_of(md: str, group: str | None) -> str:
    """If group is not None, set or_candidate_of line. If None, remove it."""
    fm, body = _split_fm(md)
    fm = [ln for ln in fm if not ln.lstrip("# ").startswith("or_candidate_of:")]
    if group is not None:
        fm.append(f"or_candidate_of: {group}")
    return _assemble(fm, body)


def read_deps(md_path: Path) -> list[str]:
    fm, _ = _split_fm(md_path.read_text(encoding="utf-8"))
    for line in fm:
        if line.startswith("deps:"):
            rest = line[len("deps:"):].strip()
            if rest.startswith("[") and rest.endswith("]"):
                inside = rest[1:-1].strip()
                if not inside:
                    return []
                return [x.strip() for x in inside.split(",") if x.strip()]
    return []


def read_fm_field(md: str, key: str) -> str | None:
    fm, _ = _split_fm(md)
    prefix = f"{key}:"
    for line in fm:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def extract_bullets(md: str, header: str) -> list[str]:
    """Return bullet items under `## <header>` until the next `## ` or EOF."""
    items: list[str] = []
    in_section = False
    for line in md.splitlines():
        if line.startswith("## "):
            in_section = (line.strip() == f"## {header}")
            continue
        if in_section:
            stripped = line.lstrip()
            if stripped.startswith("- "):
                items.append(stripped[2:].rstrip())
    return items


# ---------- node md generation ----------

def template_body() -> str:
    md = TEMPLATE_NODE.read_text(encoding="utf-8")
    _, body = _split_fm(md)
    return "\n".join(body).lstrip("\n")


def gen_node_md(nid: str, name: str | None, desc: str | None,
                deps: list[str], branch: str, or_of: str | None,
                body: str | None = None) -> str:
    fm = [
        f"name: {name or nid}",
        f"description: {desc or '<one-line purpose>'}",
        f"deps: [{', '.join(deps)}]",
        f"branch: {branch}",
    ]
    if or_of:
        fm.append(f"or_candidate_of: {or_of}")
    body_text = body if body is not None else template_body()
    return _assemble(fm, body_text.splitlines())


# ---------- state helpers ----------

def read_skill_version() -> str:
    p = SKILL_DIR / "SKILL.md"
    if not p.exists():
        return "unknown"
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^version:\s*(\S+)\s*$", line)
        if m:
            return m.group(1)
    return "unknown"


# ---------- commands ----------

def cmd_init(args: argparse.Namespace) -> int:
    if DOT.exists() and not args.force:
        die(4, ".auto-dev/ already exists (use --force to overwrite)")
    DOT.mkdir(exist_ok=True)
    NODES_DIR.mkdir(exist_ok=True)
    (DOT / "schema").mkdir(exist_ok=True)

    dag = {
        "version": 2,
        "base_branch": args.base,
        "upstream_branch": args.upstream,
        "nodes": [],
        "edges": [],
        "or_groups": [],
    }
    save_json_atomic(DAG_PATH, dag)

    state = {
        "phase": "plan",
        "base_branch": args.base,
        "upstream_branch": args.upstream,
        "last_upstream_sync": None,
        "current_node": None,
        "current_branch": args.base,
        "retry_count": 0,
        "dag_cursor": None,
        "last_tag": None,
        "skill_version": read_skill_version(),
    }
    save_json_atomic(STATE_PATH, state)

    if TEMPLATE_SCHEMA.exists():
        SCHEMA_PATH.write_text(TEMPLATE_SCHEMA.read_text(encoding="utf-8"), encoding="utf-8")

    EVENTS_LOG.touch()
    emit(f"+ repo base={args.base} upstream={args.upstream}")
    return 0


def cmd_node_add(args: argparse.Namespace) -> int:
    require_dot()
    validate_id(args.id)
    deps = [d.strip() for d in args.deps.split(",") if d.strip()] if args.deps else []
    for d in deps:
        validate_id(d, field="dep")
    dag = load_json(DAG_PATH)

    if find_node(dag, args.id):
        die(4, f"node:{args.id} already exists")
    ids = set(node_ids(dag))
    for d in deps:
        if d not in ids:
            die(3, f"dep node:{d} not found")

    or_of = args.or_of
    if or_of is not None:
        g = find_or_group(dag, or_of)
        if g is None:
            die(3, f"or_group:{or_of} not found (create it first with `or create`)")

    branch = args.branch or dag.get("base_branch", "ai-main")

    dag.setdefault("nodes", []).append({
        "id": args.id,
        "status": "pending",
        "completion_tag": None,
    })
    for d in deps:
        dag.setdefault("edges", []).append({"from": d, "to": args.id})

    if or_of is not None:
        g = find_or_group(dag, or_of)
        if args.id not in g["candidates"]:
            g["candidates"].append(args.id)

    save_dag_checked(dag)

    body = sys.stdin.read() if args.body_stdin else None

    md_path = NODES_DIR / f"{args.id}.md"
    md_path.write_text(
        gen_node_md(args.id, args.name, args.desc, deps, branch, or_of, body=body),
        encoding="utf-8",
    )

    body_marker = " body=stdin" if args.body_stdin else ""
    emit(f"+ node:{args.id} deps=[{','.join(deps)}] branch={branch}{body_marker}")
    for d in deps:
        emit(f"+ edge:{d}→{args.id}")
    if or_of is not None:
        emit(f"~ or:{or_of} candidates+={args.id}")
    return 0


def cmd_node_rm(args: argparse.Namespace) -> int:
    require_dot()
    dag = load_json(DAG_PATH)
    if find_node(dag, args.id) is None:
        die(3, f"node:{args.id} not found")

    touched = edges_touching(dag, args.id)
    dag["nodes"] = [n for n in dag["nodes"] if n.get("id") != args.id]
    dag["edges"] = [e for e in dag["edges"] if e not in touched]

    # neighboring node md deps: remove args.id where it appears
    child_ids = [e["to"] for e in touched if e.get("from") == args.id]
    for child in child_ids:
        child_md = NODES_DIR / f"{child}.md"
        if child_md.exists():
            current = read_deps(child_md)
            new = [d for d in current if d != args.id]
            if new != current:
                child_md.write_text(rewrite_deps(child_md.read_text(encoding="utf-8"), new),
                                    encoding="utf-8")

    dropped_groups: list[str] = []
    for g in list(dag.get("or_groups", [])):
        if args.id in g.get("candidates", []):
            g["candidates"] = [c for c in g["candidates"] if c != args.id]
            if g.get("decided") == args.id:
                g["decided"] = None
            g["rejected"] = [r for r in g.get("rejected", []) if r != args.id]
            if len(g["candidates"]) < 2:
                dag["or_groups"].remove(g)
                dropped_groups.append(g["id"])

    save_dag_checked(dag)

    md_path = NODES_DIR / f"{args.id}.md"
    if md_path.exists():
        md_path.unlink()

    # clear stale state refs
    if STATE_PATH.exists():
        state = load_json(STATE_PATH)
        changed = False
        if state.get("dag_cursor") == args.id:
            state["dag_cursor"] = None
            changed = True
        if state.get("current_node") == args.id:
            state["current_node"] = None
            changed = True
        if changed:
            save_json_atomic(STATE_PATH, state)

    emit(f"- node:{args.id} (+ {len(touched)} edges)")
    for g in dropped_groups:
        emit(f"- or:{g} (dropped below 2 candidates)")
    return 0


def cmd_node_status(args: argparse.Namespace) -> int:
    require_dot()
    dag = load_json(DAG_PATH)
    n = find_node(dag, args.id)
    if n is None:
        die(3, f"node:{args.id} not found")
    if args.status_value not in NODE_STATUSES:
        die(1, f"status must be one of {NODE_STATUSES}")
    n["status"] = args.status_value
    if args.tag is not None:
        if args.status_value != "done":
            die(1, "--tag only valid when setting status=done")
        n["completion_tag"] = args.tag
    save_dag_checked(dag)
    tag_part = f" tag={args.tag}" if args.tag else ""
    emit(f"> node:{args.id} status={args.status_value}{tag_part}")
    return 0


def cmd_edge_add(args: argparse.Namespace) -> int:
    require_dot()
    dag = load_json(DAG_PATH)
    ids = set(node_ids(dag))
    if args.frm not in ids:
        die(3, f"node:{args.frm} not found")
    if args.to not in ids:
        die(3, f"node:{args.to} not found")
    if args.frm == args.to:
        die(4, f"self-loop on {args.frm}")
    for e in dag.get("edges", []):
        if e.get("from") == args.frm and e.get("to") == args.to:
            die(4, f"edge:{args.frm}→{args.to} already exists")

    dag.setdefault("edges", []).append({"from": args.frm, "to": args.to})
    if has_cycle(list(ids), dag["edges"]):
        die(4, f"edge:{args.frm}→{args.to} would create a cycle")

    save_dag_checked(dag)

    child_md = NODES_DIR / f"{args.to}.md"
    if child_md.exists():
        current = read_deps(child_md)
        if args.frm not in current:
            new = current + [args.frm]
            child_md.write_text(rewrite_deps(child_md.read_text(encoding="utf-8"), new),
                                encoding="utf-8")

    emit(f"+ edge:{args.frm}→{args.to}")
    return 0


def cmd_edge_rm(args: argparse.Namespace) -> int:
    require_dot()
    dag = load_json(DAG_PATH)
    before = len(dag.get("edges", []))
    dag["edges"] = [e for e in dag.get("edges", [])
                    if not (e.get("from") == args.frm and e.get("to") == args.to)]
    if len(dag["edges"]) == before:
        die(3, f"edge:{args.frm}→{args.to} not found")

    save_dag_checked(dag)

    child_md = NODES_DIR / f"{args.to}.md"
    if child_md.exists():
        current = read_deps(child_md)
        if args.frm in current:
            new = [d for d in current if d != args.frm]
            child_md.write_text(rewrite_deps(child_md.read_text(encoding="utf-8"), new),
                                encoding="utf-8")

    emit(f"- edge:{args.frm}→{args.to}")
    return 0


def cmd_or_create(args: argparse.Namespace) -> int:
    require_dot()
    if not args.id or not args.id.strip():
        die(1, "or group id required")
    cands = [c.strip() for c in args.candidates.split(",") if c.strip()]
    if len(cands) < 2:
        die(1, "or group needs >= 2 candidates")
    dag = load_json(DAG_PATH)
    if find_or_group(dag, args.id):
        die(4, f"or:{args.id} already exists")
    ids = set(node_ids(dag))
    for c in cands:
        if c not in ids:
            die(3, f"candidate node:{c} not found")

    dag.setdefault("or_groups", []).append({
        "id": args.id,
        "candidates": cands,
        "decided": None,
        "rejected": [],
    })
    save_dag_checked(dag)

    for c in cands:
        md_path = NODES_DIR / f"{c}.md"
        if md_path.exists():
            md_path.write_text(
                set_or_candidate_of(md_path.read_text(encoding="utf-8"), args.id),
                encoding="utf-8",
            )

    emit(f"+ or:{args.id} candidates=[{','.join(cands)}]")
    return 0


def cmd_or_decide(args: argparse.Namespace) -> int:
    require_dot()
    dag = load_json(DAG_PATH)
    g = find_or_group(dag, args.id)
    if g is None:
        die(3, f"or:{args.id} not found")
    if g.get("decided") is not None:
        die(4, f"or:{args.id} already decided={g['decided']}")
    if args.winner not in g.get("candidates", []):
        die(1, f"winner {args.winner} not in candidates {g.get('candidates', [])}")

    g["decided"] = args.winner
    losers = [c for c in g["candidates"] if c != args.winner]
    g["rejected"] = losers
    for nid in losers:
        n = find_node(dag, nid)
        if n is not None:
            n["status"] = "abandoned"

    save_dag_checked(dag)
    emit(f"> or:{args.id} decided={args.winner} rejected=[{','.join(losers)}]")
    return 0


def cmd_phase_set(args: argparse.Namespace) -> int:
    require_dot()
    if args.phase not in PHASES:
        die(1, f"phase must be one of {PHASES}")
    state = load_json(STATE_PATH)
    old = state.get("phase")

    if args.phase == "dev":
        dag = load_json(DAG_PATH)
        # transition to dev requires a structurally sound graph
        from validate_dag import validate as vd_validate  # type: ignore
        errs = vd_validate(dag)
        if errs:
            die(5, "validate failed; fix before phase=dev:\n  " + "\n  ".join(errs))
        # compute first ready node
        status_by_id = {n["id"]: n["status"] for n in dag.get("nodes", [])}
        parents: dict[str, list[str]] = {}
        for e in dag.get("edges", []):
            parents.setdefault(e["to"], []).append(e["from"])
        ready = sorted(
            nid for nid, st in status_by_id.items()
            if st == "pending" and all(status_by_id.get(p) == "done" for p in parents.get(nid, []))
        )
        state["dag_cursor"] = ready[0] if ready else None
    else:
        state["dag_cursor"] = None

    state["phase"] = args.phase
    save_json_atomic(STATE_PATH, state)

    cursor_part = f" cursor={state['dag_cursor']}" if state.get("dag_cursor") else ""
    emit(f"> phase:{old}→{args.phase}{cursor_part}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    require_dot()
    sys.path.insert(0, str(SCRIPT_DIR))
    from validate_dag import validate as vd_validate  # type: ignore
    dag = load_json(DAG_PATH)
    errs = vd_validate(dag)
    if not errs:
        n = len(dag.get("nodes", []))
        m = len(dag.get("edges", []))
        k = len(dag.get("or_groups", []))
        emit(f"✓ validate: {n} nodes, {m} edges, {k} or_groups", log=False)
        return 0
    for e in errs:
        print(f"! validate: {e}", file=sys.stderr)
    return 5


def cmd_status(args: argparse.Namespace) -> int:
    require_dot()
    dag = load_json(DAG_PATH)
    state = load_json(STATE_PATH)

    status_by_id = {n["id"]: n["status"] for n in dag.get("nodes", [])}
    parents: dict[str, list[str]] = {}
    for e in dag.get("edges", []):
        parents.setdefault(e["to"], []).append(e["from"])
    ready = sorted(
        nid for nid, st in status_by_id.items()
        if st == "pending" and all(status_by_id.get(p) == "done" for p in parents.get(nid, []))
    )
    pending_or = sorted(g["id"] for g in dag.get("or_groups", []) if g.get("decided") is None)
    counts: dict[str, int] = {}
    for st in status_by_id.values():
        counts[st] = counts.get(st, 0) + 1

    if args.json:
        out = {
            "phase": state.get("phase"),
            "cursor": state.get("dag_cursor"),
            "base": state.get("base_branch"),
            "upstream": state.get("upstream_branch"),
            "current_node": state.get("current_node"),
            "retry_count": state.get("retry_count"),
            "ready": ready,
            "pending_or": pending_or,
            "counts": counts,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    print(f"? phase={state.get('phase')} cursor={state.get('dag_cursor') or '-'} "
          f"base={state.get('base_branch')} upstream={state.get('upstream_branch')}")
    print(f"? ready=[{','.join(ready)}]")
    cur = state.get("current_node")
    if cur:
        print(f"? current={cur} retry={state.get('retry_count', 0)}")
    print(f"? pending-or=[{','.join(pending_or)}]")
    counts_str = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"? counts {counts_str}" if counts_str else "? counts (empty)")
    return 0


def cmd_nodes(args: argparse.Namespace) -> int:
    """Dense per-node summary for edge-wiring decisions.

    Per node: id / status / branch / deps / or group / name / desc +
    bullet items from ## Entry (needs) and ## Completion (produces).
    """
    require_dot()
    dag = load_json(DAG_PATH)

    parents_of: dict[str, list[str]] = {}
    for e in dag.get("edges", []):
        parents_of.setdefault(e["to"], []).append(e["from"])
    or_of: dict[str, str] = {}
    for g in dag.get("or_groups", []):
        for c in g.get("candidates", []):
            or_of[c] = g["id"]

    want_status = args.filter
    records = []
    for n in dag.get("nodes", []):
        if want_status and n["status"] != want_status:
            continue
        nid = n["id"]
        md_path = NODES_DIR / f"{nid}.md"
        name = desc = branch = None
        needs: list[str] = []
        produces: list[str] = []
        if md_path.exists():
            md = md_path.read_text(encoding="utf-8")
            name = read_fm_field(md, "name")
            desc = read_fm_field(md, "description")
            branch = read_fm_field(md, "branch")
            needs = extract_bullets(md, "Entry")
            produces = extract_bullets(md, "Completion")
        records.append({
            "id": nid,
            "status": n["status"],
            "branch": branch,
            "deps": parents_of.get(nid, []),
            "or": or_of.get(nid),
            "name": name,
            "desc": desc,
            "needs": needs,
            "produces": produces,
        })

    if args.json:
        print(json.dumps(records, indent=2, ensure_ascii=False))
        return 0

    print(f"? nodes ({len(records)} shown)")
    for r in records:
        parts = [f"{r['id']} [{r['status']}]"]
        parts.append(f"branch={r['branch'] or '-'}")
        parts.append(f"deps=[{','.join(r['deps'])}]")
        if r['or']:
            parts.append(f"or={r['or']}")
        print("─ " + " ".join(parts))
        if r['name']:
            print(f"    name: {r['name']}")
        if r['desc']:
            print(f"    desc: {r['desc']}")
        if r['needs']:
            print("    needs:")
            for item in r['needs']:
                print(f"      • {item}")
        if r['produces']:
            print("    produces:")
            for item in r['produces']:
                print(f"      • {item}")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    if not EVENTS_LOG.exists():
        die(3, f"{EVENTS_LOG}: not found")
    lines = EVENTS_LOG.read_text(encoding="utf-8").splitlines()
    if args.head is not None:
        out = lines[: args.head]
    else:
        out = lines[-args.tail:] if args.tail > 0 else lines
    for ln in out:
        print(ln)
    return 0


# ---------- main ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="auto-dev",
        description="auto-dev orchestration CLI. Treat this script as opaque: "
                    "use `<cmd> --help` for args, SKILL.md for capabilities. "
                    "Do not read the source when running the skill.",
    )
    sub = p.add_subparsers(dest="cmd", required=True, metavar="<cmd>")

    i = sub.add_parser("init", help="initialize .auto-dev/ skeleton")
    i.add_argument("--base", default="ai-main", help="AI base branch (default: ai-main)")
    i.add_argument("--upstream", default="main", help="human upstream branch (default: main)")
    i.add_argument("--force", action="store_true", help="overwrite existing .auto-dev/")
    i.set_defaults(func=cmd_init)

    node = sub.add_parser("node", help="node ops (add / rm / status)")
    node_sub = node.add_subparsers(dest="node_cmd", required=True, metavar="<op>")
    na = node_sub.add_parser("add", help="create node md + register in dag.json")
    na.add_argument("id", help="kebab-case node id")
    na.add_argument("--deps", default="", help="comma-separated dep ids (edges auto-created)")
    na.add_argument("--branch", default=None,
                    help="git branch for this node (default: base_branch). "
                         "Conventions: or/<desc> for OR head, and/<parent>-<desc> for AND member")
    na.add_argument("--or-of", dest="or_of", default=None,
                    help="attach to an existing OR group (group must be created first)")
    na.add_argument("--name", default=None, help="frontmatter name (default: <id>)")
    na.add_argument("--desc", default=None, help="frontmatter description")
    na.add_argument("--body-stdin", dest="body_stdin", action="store_true",
                    help="read node body (sections after frontmatter) from stdin; "
                         "use with a heredoc to write Entry/Completion/etc in one call")
    na.set_defaults(func=cmd_node_add)
    nr = node_sub.add_parser("rm", help="remove node; cascades to edges, child deps, OR groups")
    nr.add_argument("id")
    nr.set_defaults(func=cmd_node_rm)
    ns_cmd = node_sub.add_parser("status", help="set node status (done / dev / abandoned / ...)")
    ns_cmd.add_argument("id")
    ns_cmd.add_argument("status_value", choices=NODE_STATUSES, metavar="status")
    ns_cmd.add_argument("--tag", default=None,
                        help="completion_tag (only with status=done)")
    ns_cmd.set_defaults(func=cmd_node_status)

    edge = sub.add_parser("edge", help="edge ops (add / rm); syncs child md deps")
    edge_sub = edge.add_subparsers(dest="edge_cmd", required=True, metavar="<op>")
    ea = edge_sub.add_parser("add", help="add edge from→to (refuses cycles)")
    ea.add_argument("frm", metavar="from")
    ea.add_argument("to")
    ea.set_defaults(func=cmd_edge_add)
    er = edge_sub.add_parser("rm", help="remove edge from→to")
    er.add_argument("frm", metavar="from")
    er.add_argument("to")
    er.set_defaults(func=cmd_edge_rm)

    og = sub.add_parser("or", help="OR-group ops (create / decide)")
    og_sub = og.add_subparsers(dest="or_cmd", required=True, metavar="<op>")
    oc = og_sub.add_parser("create", help="create OR group from existing candidate nodes")
    oc.add_argument("id", help="or-group id")
    oc.add_argument("--candidates", required=True, help="comma-separated node ids (>= 2)")
    oc.set_defaults(func=cmd_or_create)
    od = og_sub.add_parser("decide", help="pick winner; losers auto-marked abandoned")
    od.add_argument("id", help="or-group id")
    od.add_argument("winner", help="winning candidate id")
    od.set_defaults(func=cmd_or_decide)

    ph = sub.add_parser("phase", help="phase ops (plan / dev / review-gate)")
    ph_sub = ph.add_subparsers(dest="phase_cmd", required=True, metavar="<op>")
    ps = ph_sub.add_parser("set", help="set phase; dev runs validate first + computes cursor")
    ps.add_argument("phase", choices=PHASES)
    ps.set_defaults(func=cmd_phase_set)

    v = sub.add_parser("validate", help="run schema/topology validator (exit 5 on failure)")
    v.set_defaults(func=cmd_validate)

    st = sub.add_parser("status", help="current phase / cursor / ready / counts")
    st.add_argument("--json", action="store_true")
    st.set_defaults(func=cmd_status)

    nl = sub.add_parser("nodes",
                        help="dense per-node view: id + status + deps + needs + produces")
    nl.add_argument("--json", action="store_true")
    nl.add_argument("--filter", choices=NODE_STATUSES, default=None,
                    help="show only nodes with this status")
    nl.set_defaults(func=cmd_nodes)

    lg = sub.add_parser("log", help="print events.log (causal history)")
    lg.add_argument("--tail", type=int, default=50, help="show last N lines (default 50)")
    lg.add_argument("--head", type=int, default=None, help="show first N lines")
    lg.set_defaults(func=cmd_log)

    return p


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv[1:])
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
