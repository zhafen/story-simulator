#!/usr/bin/env python3
"""Generate a requirement-first HTML report of live_testing_framework's
candidate_solutions (docs/manifest/story-simulator.yaml): one section per
requirement, listing every solution that satisfies it, each expandable to
show its own pros and cons. Followed by a solution-first "Solutions"
section -- every candidate solution listed once, with which requirement(s)
it solves shown inside its own expandable entry, for the solutions that
cover more than one requirement and would otherwise only show up once per
requirement above.

Requirement-first rather than solution-first on purpose -- see
docs/manifest/prioritization_reflections.yaml's fourth installment
("2026-08-22_retrospective_on_the_scoring_approach"): checking "does this
requirement have a good solution" is the direction that's actually useful,
not "what does this solution cover." Pros/cons are plain qualitative
`pro`/`con` bare tags, not weighted consideration/consideration_rating
axes -- that scheme was tried first here but dropped: its weight*rating
formula kept producing a sign that didn't match a point's own actual
meaning (a clearly negative point could still net a "pro" if its axis and
rating happened to multiply positive). Each pro/con's text is shown as-is,
grouped pros-then-cons, in the order it was written -- no score to sort by.

Reuses find_live_testing_solution_covers.py's own requirement/solution
loading (same registrar tables, same prefixes, same `_leaf` helper) so
this can't silently drift out of sync with the coverage script. Prints
nothing to stdout; writes a single self-contained HTML file (no external
requests except the Google Fonts stylesheet) to --output, defaulting to a
scratch path outside the repo, matching find_live_testing_solution_covers.py's
own precedent of not committing generated output, only the generator.

--fragment writes just the title/style/body content, without the
surrounding <!doctype>/<html>/<head>/<body> tags -- for publishing as a
Claude Artifact, which wraps that skeleton on its own and rejects one of
its own. Omit --fragment for a normal, directly-openable standalone page.

Run: uv run python scripts/generate_live_testing_report.py [--output PATH] [--fragment]
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

from emc2p.registrar import Registrar

import find_live_testing_solution_covers as covers

REQUIREMENTS_PREFIX = covers.REQUIREMENTS_PREFIX
SOLUTIONS_PREFIX = covers.SOLUTIONS_PREFIX

DEFAULT_OUTPUT = Path("/tmp/live_testing_framework_report.html")


def load_report_data(registrar: Registrar) -> dict:
    """Everything the report needs, keyed by requirement/solution short
    name: which solutions satisfy each requirement, each entity's
    description, each solution's work_state/cost, and each solution's
    consideration_rating pros/cons (with their parent consideration's own
    description for context)."""
    requirements, solves = covers.load_solution_map(registrar)

    eids = registrar.get("entity_id").execute()
    path_of = dict(zip(eids["value"].astype(str), eids["path"].astype(str)))

    def name_of(eid, prefix: str) -> str | None:
        return covers._leaf(path_of[str(eid)].split(":", 1)[1], prefix)

    descriptions: dict[str, str] = {}
    for _, row in registrar.get("description").execute().iterrows():
        name = name_of(row["entity_id"], REQUIREMENTS_PREFIX) or name_of(
            row["entity_id"], SOLUTIONS_PREFIX
        )
        if name:
            descriptions[name] = str(row["value"])

    work_states: dict[str, str] = {}
    for _, row in registrar.get("work_state").execute().iterrows():
        name = name_of(row["entity_id"], SOLUTIONS_PREFIX)
        if name:
            work_states[name] = str(row["value"])

    costs: dict[str, list[tuple[str, float]]] = {}
    for _, row in registrar.get("cost").execute().iterrows():
        name = name_of(row["entity_id"], SOLUTIONS_PREFIX)
        if name:
            costs.setdefault(name, []).append((str(row["type"]), float(row["value"])))

    code_examples: dict[str, dict] = {}
    for _, row in registrar.get("code_example").execute().iterrows():
        name = name_of(row["entity_id"], SOLUTIONS_PREFIX)
        if name:
            code_examples[name] = {"language": str(row["language"]), "code": str(row["value"])}

    pros_cons: dict[str, list[dict]] = {}
    for sign in ("pro", "con"):
        for _, row in registrar.get(sign).execute().iterrows():
            name = name_of(row["entity_id"], SOLUTIONS_PREFIX)
            if name:
                pros_cons.setdefault(name, []).append({"sign": sign, "note": str(row["value"])})

    req_to_solutions: dict[str, list[str]] = {name: [] for name in requirements}
    for solution_name, req_names in solves.items():
        for req_name in req_names:
            req_to_solutions.setdefault(req_name, []).append(solution_name)

    return {
        "requirements": sorted(requirements),
        "req_to_solutions": {r: sorted(s) for r, s in req_to_solutions.items()},
        "solution_to_requirements": {s: sorted(r) for s, r in solves.items()},
        "descriptions": descriptions,
        "work_states": work_states,
        "code_examples": code_examples,
        "costs": costs,
        "pros_cons": pros_cons,
    }


NEW_TREE_ENTITY_KEY = "human_validated_test_framework"
NEW_TREE_MANIFEST_PATH = Path("docs/manifest/story-simulator.yaml")

# On a real D3.js graph viz, if that's ever wanted instead of the
# hand-rolled inline-SVG layout below: this report gets published as a
# Claude Artifact, whose CSP blocks CDN script loads outright (Google
# Fonts is the one exception) -- a normal <script src="https://d3js.org/...">
# tag would silently fail to load there. The fix isn't to drop D3, it's to
# vendor it: paste D3's full built bundle (e.g. https://d3js.org/d3.v7.min.js,
# ~280KB) directly into a <script> tag with no src attribute, so nothing is
# fetched externally -- that satisfies the Artifact's "fully self-contained"
# rule and unlocks real D3 (animated collapse/expand, zoom/pan, force
# layouts). Left this simpler layout in place for now since a 20-node
# static tree doesn't really need any of that; revisit if the graph grows
# or the interaction needs get fancier than click-to-collapse.


def load_new_tree_graph_data(registrar: Registrar) -> dict:
    """Node/edge data for the human_validated_test_framework subtree --
    zhafen's own alternating-tree redesign (each solution nests the
    requirement(s) it needs; each requirement nests its own candidate
    solutions) -- for the inline-SVG graph visualization. Built from the
    same resolved requirement/solution relations emc2p's own dataflow
    computes (parent_from_hierarchy + components_with_resolved_paths), not
    just raw YAML text, so a cross-link (e.g. one solution serving two
    requirements) shows up as a real edge.
    """
    from emc2p.dataflows.derive.resolve_paths import (
        components_with_resolved_paths,
        fields_of_type_entity_ref,
        parent_from_hierarchy,
    )

    entity_id = registrar.get("entity_id")
    field = registrar.get("field")
    components = registrar._registry._components
    hierarchy = parent_from_hierarchy(entity_id)
    resolved = components_with_resolved_paths(
        entity_id=entity_id,
        components=components,
        fields_of_type_entity_ref=fields_of_type_entity_ref(entity_id, field),
        parent_from_hierarchy=hierarchy,
    )

    eids = entity_id.execute()
    path_of = dict(zip(eids["value"].astype(str), eids["path"].astype(str)))

    def clean(path: str) -> str:
        return path.split(":", 1)[1]

    marker = f".{NEW_TREE_ENTITY_KEY}"
    subtree_path_of = {
        eid: clean(p)
        for eid, p in path_of.items()
        if marker in clean(p) or clean(p).endswith(NEW_TREE_ENTITY_KEY)
    }
    path_to_eid = {p: eid for eid, p in subtree_path_of.items()}

    descriptions: dict[str, str] = {}
    for _, row in registrar.get("description").execute().iterrows():
        eid = str(row["entity_id"])
        if eid in subtree_path_of:
            descriptions[eid] = str(row["value"])

    work_states: dict[str, str] = {}
    for _, row in registrar.get("work_state").execute().iterrows():
        eid = str(row["entity_id"])
        if eid in subtree_path_of:
            work_states[eid] = str(row["value"])

    types: dict[str, str] = {}
    for ctype in ("requirement", "solution"):
        for _, row in registrar.get(ctype).execute().iterrows():
            eid = str(row["entity_id"])
            if eid in subtree_path_of:
                types[eid] = ctype

    nodes = []
    parent_of: dict[str, str | None] = {}
    for eid, path in subtree_path_of.items():
        parent_path = path.rsplit(".", 1)[0] if "." in path else None
        parent_id = path_to_eid.get(parent_path) if parent_path else None
        parent_of[eid] = parent_id
        key = path.rsplit(".", 1)[-1]
        nodes.append({
            "id": eid,
            "key": key,
            "label": _label(key),
            "type": types.get(eid, "solution" if parent_id is None else "requirement"),
            "description": descriptions.get(eid, ""),
            "work_state": work_states.get(eid),
            "parent_id": parent_id,
        })

    cross_edges: list[tuple[str, str]] = []
    seen_cross = set()
    for ctype in ("requirement", "solution"):
        df = resolved[ctype].to_pandas()
        for _, row in df.iterrows():
            eid = str(row["entity_id"])
            if eid not in subtree_path_of:
                continue
            target = row.get("value_eid")
            if target is None or (isinstance(target, float) and target != target):
                continue
            target = str(target)
            if target not in subtree_path_of or target == parent_of.get(eid):
                continue
            pair = (eid, target)
            if pair not in seen_cross:
                seen_cross.add(pair)
                cross_edges.append(pair)

    return {"nodes": nodes, "cross_edges": cross_edges}


_GRAPH_NODE_W = 210
_GRAPH_NODE_H = 44
_GRAPH_H_GAP = 60
_GRAPH_V_GAP = 14


def _layout_tree(nodes: list[dict]) -> dict:
    """Left-to-right tidy-tree layout (root at the left, depth grows
    rightward, siblings stack vertically) -- a tall, narrow shape scrolls
    naturally with the page instead of needing wide horizontal scroll.
    Each leaf gets one row's worth of height, a parent's row is the
    average of its children's rows. Deterministic ordering by node key
    (not narration order -- pandas/emc2p row order isn't guaranteed,
    alphabetical is at least stable). Also returns each node's ancestor-id
    chain, used client-side for click-to-collapse."""
    by_id = {n["id"]: n for n in nodes}
    children: dict[str, list[str]] = {}
    roots = []
    for n in nodes:
        pid = n["parent_id"]
        if pid is None:
            roots.append(n["id"])
        else:
            children.setdefault(pid, []).append(n["id"])
    for pid in children:
        children[pid].sort(key=lambda nid: by_id[nid]["key"])
    roots.sort(key=lambda nid: by_id[nid]["key"])

    positions: dict[str, tuple[float, int]] = {}
    ancestors: dict[str, list[str]] = {}
    next_row = [0]

    def visit(node_id: str, depth: int, chain: list[str]) -> float:
        ancestors[node_id] = chain
        kids = children.get(node_id, [])
        if not kids:
            row = next_row[0]
            next_row[0] += 1
            y = row + 0.5
        else:
            ys = [visit(k, depth + 1, chain + [node_id]) for k in kids]
            y = sum(ys) / len(ys)
        positions[node_id] = (y, depth)
        return y

    for r in roots:
        visit(r, 0, [])

    max_row = next_row[0] or 1
    max_depth = max((d for _, d in positions.values()), default=0)
    width = (max_depth + 1) * (_GRAPH_NODE_W + _GRAPH_H_GAP)
    height = max_row * (_GRAPH_NODE_H + _GRAPH_V_GAP)
    pixel_positions = {
        nid: (
            depth * (_GRAPH_NODE_W + _GRAPH_H_GAP) + _GRAPH_H_GAP / 2,
            y * (_GRAPH_NODE_H + _GRAPH_V_GAP) + _GRAPH_V_GAP / 2,
        )
        for nid, (y, depth) in positions.items()
    }
    return {"positions": pixel_positions, "width": width, "height": height, "ancestors": ancestors}


def _render_new_tree_graph_section(graph_data: dict) -> str:
    nodes = graph_data["nodes"]
    if not nodes:
        return ""
    layout = _layout_tree(nodes)
    positions = layout["positions"]
    ancestors = layout["ancestors"]
    by_id = {n["id"]: n for n in nodes}
    has_children = {n["parent_id"] for n in nodes if n["parent_id"]}

    def anc_attr(node_id: str) -> str:
        chain = ancestors.get(node_id, [])
        return " ".join(chain) if chain else ""

    svg_parts = []
    # Tree edges (solid) drawn first, under the nodes. Belongs to its
    # child's subtree for collapse purposes.
    for n in nodes:
        pid = n["parent_id"]
        if pid is None or pid not in positions:
            continue
        x1, y1 = positions[pid]
        x2, y2 = positions[n["id"]]
        edge_anc = anc_attr(n["id"])
        svg_parts.append(
            f'<path class="graph-edge" data-anc="{edge_anc}" d="M {x1 + _GRAPH_NODE_W} {y1 + _GRAPH_NODE_H / 2} '
            f'C {x1 + _GRAPH_NODE_W + _GRAPH_H_GAP / 2} {y1 + _GRAPH_NODE_H / 2}, '
            f'{x2 - _GRAPH_H_GAP / 2} {y2 + _GRAPH_NODE_H / 2}, '
            f'{x2} {y2 + _GRAPH_NODE_H / 2}"/>'
        )
    # Cross edges (dashed) -- e.g. one solution also solving a second requirement.
    for from_id, to_id in graph_data["cross_edges"]:
        if from_id not in positions or to_id not in positions:
            continue
        x1, y1 = positions[from_id]
        x2, y2 = positions[to_id]
        sx, sy = x1 + _GRAPH_NODE_W, y1 + _GRAPH_NODE_H / 2
        tx, ty = x2 + _GRAPH_NODE_W, y2 + _GRAPH_NODE_H / 2
        bulge = 46
        edge_anc = " ".join({*ancestors.get(from_id, []), *ancestors.get(to_id, [])})
        svg_parts.append(
            f'<path class="graph-edge graph-edge-cross" data-anc="{edge_anc}" '
            f'd="M {sx} {sy} C {sx + bulge} {sy}, {tx + bulge} {ty}, {tx} {ty}" '
            f'marker-end="url(#graph-arrow)"/>'
        )
    # Nodes on top.
    for n in nodes:
        x, y = positions[n["id"]]
        node_type = n["type"]
        collapsible = n["id"] in has_children
        work_badge = ""
        if n["work_state"]:
            ws = html.escape(n["work_state"])
            work_badge = f'<text class="graph-node-badge" x="{_GRAPH_NODE_W - 8}" y="15" text-anchor="end">{ws}</text>'
        toggle = (
            f'<circle class="graph-node-toggle" cx="{_GRAPH_NODE_W}" cy="{_GRAPH_NODE_H / 2}" r="7"/>'
            f'<text class="graph-node-toggle-glyph" x="{_GRAPH_NODE_W}" y="{_GRAPH_NODE_H / 2 + 3.5}" text-anchor="middle">&#8722;</text>'
            if collapsible else ""
        )
        desc_attr = html.escape(n["description"].strip().replace("\n\n", " ").replace("\n", " "))
        node_class = f"graph-node graph-node-{node_type}" + (" graph-node-collapsible" if collapsible else "")
        svg_parts.append(f"""
      <g class="{node_class}" transform="translate({x},{y})" data-id="{n["id"]}" data-anc="{anc_attr(n["id"])}">
        <title>{html.escape(n["label"])}&#10;&#10;{desc_attr}</title>
        <rect width="{_GRAPH_NODE_W}" height="{_GRAPH_NODE_H}" rx="{8 if node_type == "requirement" else _GRAPH_NODE_H / 2}"/>
        <text class="graph-node-label" x="10" y="{_GRAPH_NODE_H / 2 + 4.5}">{html.escape(n["label"])}</text>
        {work_badge}
        {toggle}
      </g>""")

    svg = f"""
    <svg class="graph-svg" viewBox="0 0 {layout['width']} {layout['height']}" width="{layout['width']}" height="{layout['height']}">
      <defs>
        <marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" class="graph-arrowhead"/>
        </marker>
      </defs>
      {"".join(svg_parts)}
    </svg>"""

    script = """
    <script>
    (function() {
      var root = document.currentScript.closest('.yaml-preview');
      var collapsed = new Set();
      function apply() {
        root.querySelectorAll('[data-anc]').forEach(function(el) {
          var chain = (el.getAttribute('data-anc') || '').split(' ').filter(Boolean);
          var hidden = chain.some(function(a) { return collapsed.has(a); });
          el.style.display = hidden ? 'none' : '';
        });
        root.querySelectorAll('.graph-node-collapsible').forEach(function(g) {
          var id = g.getAttribute('data-id');
          var glyph = g.querySelector('.graph-node-toggle-glyph');
          if (glyph) glyph.textContent = collapsed.has(id) ? '+' : String.fromCharCode(8722);
        });
      }
      root.querySelectorAll('.graph-node-collapsible').forEach(function(g) {
        g.addEventListener('click', function() {
          var id = g.getAttribute('data-id');
          if (collapsed.has(id)) { collapsed.delete(id); } else { collapsed.add(id); }
          apply();
        });
      });
    })();
    </script>"""

    return f"""
  <details class="yaml-preview" open>
    <summary>
      <span class="yaml-preview-title">Alternating-tree redesign -- graph view (still being narrated)</span>
    </summary>
    <p class="graph-legend">
      <span class="graph-legend-item"><span class="graph-swatch graph-swatch-requirement"></span>requirement</span>
      <span class="graph-legend-item"><span class="graph-swatch graph-swatch-solution"></span>solution</span>
      <span class="graph-legend-item"><span class="graph-edge-sample"></span>nested (implied) relation</span>
      <span class="graph-legend-item"><span class="graph-edge-sample graph-edge-sample-cross"></span>additional solution of: link</span>
    </p>
    <div class="graph-scroll">{svg}</div>
    <p class="graph-hint">Hover a node for its full description. Click a node with a &#8722;/+ marker to collapse or expand its branch.</p>
    {script}
  </details>
  <hr class="section-divider">"""


def _label(name: str) -> str:
    return name.replace("_", " ")


def _render_pro_con(item: dict) -> str:
    sign_label = "Pro" if item["sign"] == "pro" else "Con"
    note = html.escape(item["note"])
    return f"""
        <li class="rating rating-{sign_label.lower()}">
          <div class="rating-head">
            <span class="sign-badge sign-{sign_label.lower()}">{sign_label}</span>
          </div>
          <p class="rating-note">{note}</p>
        </li>"""


def _render_solution(name: str, data: dict, show_requirements: bool = False) -> str:
    description = html.escape(data["descriptions"].get(name, ""))
    work_state = data["work_states"].get(name, "unknown")
    cost_items = data["costs"].get(name, [])
    cost_html = (
        ", ".join(f"{value:g} {ctype}" for ctype, value in cost_items) if cost_items else "none"
    )
    items = data["pros_cons"].get(name, [])
    pros = [r for r in items if r["sign"] == "pro"]
    cons = [r for r in items if r["sign"] == "con"]
    ratings_html = "".join(_render_pro_con(r) for r in pros + cons)
    requirements_html = ""
    if show_requirements:
        req_names = data["solution_to_requirements"].get(name, [])
        chips = "".join(
            f'<span class="req-chip">{html.escape(_label(r))}</span>' for r in req_names
        ) or '<span class="req-chip req-chip-none">none currently</span>'
        requirements_html = f"""
          <p class="section-label">Solves</p>
          <div class="req-chips">{chips}</div>"""
    code_example_html = ""
    example = data["code_examples"].get(name)
    if example:
        code_example_html = f"""
          <p class="section-label">Example</p>
          <pre class="code-example"><code class="language-{html.escape(example['language'])}">{html.escape(example['code'])}</code></pre>"""
    return f"""
      <details class="solution">
        <summary>
          <span class="solution-name">{html.escape(_label(name))}</span>
          <span class="work-state work-state-{html.escape(work_state.replace(' ', '-'))}">{html.escape(work_state)}</span>
          <span class="cost">cost: {html.escape(cost_html)}</span>
        </summary>
        <div class="solution-body">
          <p class="solution-description">{description}</p>
          {requirements_html}
          {code_example_html}
          <ul class="ratings">{ratings_html}</ul>
        </div>
      </details>"""


def _render_requirement(name: str, data: dict) -> str:
    description = html.escape(data["descriptions"].get(name, ""))
    solution_names = data["req_to_solutions"].get(name, [])
    if solution_names:
        solutions_html = "".join(_render_solution(s, data) for s in solution_names)
    else:
        solutions_html = '<p class="no-solutions">No candidate solution currently solves this requirement.</p>'
    return f"""
    <section class="requirement">
      <p class="eyebrow">Requirement</p>
      <h2>{html.escape(_label(name))}</h2>
      <p class="requirement-description">{description}</p>
      {solutions_html}
    </section>"""


def _render_solutions_section(data: dict) -> str:
    """A solution-first section: every candidate solution once, each showing
    which requirement(s) it solves. Requirement-first stays the primary view
    (see the module docstring for why), but a solution can solve more than
    one requirement -- this section is the place to see it listed once
    instead of repeated under each requirement it happens to cover."""
    solution_names = sorted(data["solution_to_requirements"])
    solutions_html = "".join(
        _render_solution(s, data, show_requirements=True) for s in solution_names
    )
    return f"""
  <div class="masthead">
    <p class="kicker">live_testing_framework &middot; solution index</p>
    <h1>Solutions</h1>
    <p class="subtitle">
      Every candidate solution once, regardless of how many requirements it
      covers. Expand a solution to see what it solves, its pros and cons.
    </p>
  </div>
  {solutions_html}"""


_FONTS_LINK = (
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600'
    '&family=IBM+Plex+Sans:wght@400;500;600&display=swap">'
)

_STYLE = """
  :root {
    color-scheme: light dark;
    --bg: #f7f6f2; --surface: #ffffff; --border: #e2ded2;
    --fg: #1e211d; --muted: #6b6f63; --muted-2: #8a8d80;
    --accent: #0f6e67; --accent-fg: #ffffff;
    --pro: #2e6b45; --pro-bg: #e4f1e7;
    --con: #a3392c; --con-bg: #f8e9e5;
    --chip-bg: #ece9dd; --chip-fg: #55584c;
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #161816; --surface: #1e211d; --border: #33362e;
      --fg: #eae8de; --muted: #a3a695; --muted-2: #7d8071;
      --accent: #4fb8ae; --accent-fg: #0d1513;
      --pro: #7bc794; --pro-bg: #1c2e21;
      --con: #e08b7c; --con-bg: #34211d;
      --chip-bg: #2a2d26; --chip-fg: #b9bcae;
    }
  }
  :root[data-theme="dark"] {
    --bg: #161816; --surface: #1e211d; --border: #33362e;
    --fg: #eae8de; --muted: #a3a695; --muted-2: #7d8071;
    --accent: #4fb8ae; --accent-fg: #0d1513;
    --pro: #7bc794; --pro-bg: #1c2e21;
    --con: #e08b7c; --con-bg: #34211d;
    --chip-bg: #2a2d26; --chip-fg: #b9bcae;
  }

  * { box-sizing: border-box; }

  body {
    background: var(--bg); color: var(--fg);
    font-family: "IBM Plex Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    max-width: 760px; margin: 0 auto; padding: 3rem 1.5rem 5rem;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
  }

  .masthead { margin-bottom: 2.75rem; }
  .kicker {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--accent); margin: 0 0 0.6rem;
  }
  h1 {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 1.7rem; font-weight: 600; margin: 0 0 0.6rem;
    text-wrap: balance; letter-spacing: -0.01em;
  }
  .subtitle { color: var(--muted); margin: 0; font-size: 0.95rem; max-width: 62ch; }

  .requirement { margin-bottom: 2.25rem; padding-bottom: 2.25rem; border-bottom: 1px solid var(--border); }
  .requirement:last-child { border-bottom: none; }
  .eyebrow {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.68rem; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--muted-2); margin: 0 0 0.35rem;
  }
  .requirement h2 {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 1.15rem; font-weight: 600; margin: 0; text-wrap: balance;
  }
  .requirement-description { color: var(--muted); margin: 0.5rem 0 1.1rem; max-width: 62ch; }
  .no-solutions { color: var(--con); font-style: italic; }

  details.solution {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    margin: 0.7rem 0; padding: 0 1.1rem;
  }
  details.solution summary {
    cursor: pointer; padding: 0.85rem 0; display: flex; align-items: center;
    gap: 0.7rem; list-style: none; font-weight: 600;
  }
  details.solution summary::-webkit-details-marker { display: none; }
  details.solution summary::before {
    content: "▸"; color: var(--muted-2); font-weight: normal; flex-shrink: 0;
    transition: transform 0.15s ease;
  }
  details.solution[open] summary::before { transform: rotate(90deg); }
  .solution-name { flex: 1; font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 0.95rem; }
  .work-state {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-weight: 500; font-size: 0.68rem; letter-spacing: 0.03em;
    padding: 0.2rem 0.55rem; border-radius: 999px;
    background: var(--chip-bg); color: var(--chip-fg); white-space: nowrap;
  }
  .cost {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
    font-size: 0.78rem; color: var(--muted); white-space: nowrap; font-weight: 400;
  }
  .solution-body { padding: 0 0 1.1rem 1.5rem; }
  .solution-description { color: var(--fg); margin-top: 0; }
  ul.ratings { list-style: none; margin: 0.6rem 0 0; padding: 0; }
  li.rating { padding: 0.6rem 0; border-top: 1px solid var(--border); }
  li.rating:first-child { border-top: none; }
  .rating-head { display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap; }
  .sign-badge {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.66rem; font-weight: 600; letter-spacing: 0.04em;
    padding: 0.12rem 0.5rem; border-radius: 5px;
  }
  .sign-pro { background: var(--pro-bg); color: var(--pro); }
  .sign-con { background: var(--con-bg); color: var(--con); }
  .rating-note { margin: 0.35rem 0 0; color: var(--muted); font-size: 0.92rem; max-width: 62ch; }

  .section-label {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.68rem; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--muted-2); margin: 0.9rem 0 0.4rem;
  }
  .req-chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
  .req-chip {
    font-size: 0.8rem; padding: 0.2rem 0.6rem; border-radius: 999px;
    background: var(--chip-bg); color: var(--chip-fg);
  }
  .req-chip-none { font-style: italic; }

  .code-example {
    background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
    padding: 0.85rem 1rem; overflow-x: auto; margin: 0;
  }
  .code-example code {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.8rem; line-height: 1.5; color: var(--fg); white-space: pre;
  }

  .section-divider { border: none; border-top: 1px solid var(--border); margin: 3rem 0 2.75rem; }

  details.yaml-preview {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 0 1.1rem; margin-bottom: 2.75rem;
  }
  details.yaml-preview summary {
    cursor: pointer; padding: 0.85rem 0; display: flex; align-items: center;
    gap: 0.7rem; list-style: none; font-weight: 600;
  }
  details.yaml-preview summary::-webkit-details-marker { display: none; }
  details.yaml-preview summary::before {
    content: "▸"; color: var(--muted-2); font-weight: normal; flex-shrink: 0;
    transition: transform 0.15s ease;
  }
  details.yaml-preview[open] summary::before { transform: rotate(90deg); }
  .yaml-preview-title {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 0.9rem;
  }

  .graph-legend {
    display: flex; flex-wrap: wrap; gap: 1.1rem; margin: 0 0 0.9rem;
    font-size: 0.78rem; color: var(--muted);
  }
  .graph-legend-item { display: inline-flex; align-items: center; gap: 0.4rem; }
  .graph-swatch {
    width: 0.85rem; height: 0.85rem; border-radius: 3px; display: inline-block;
    border: 1.5px solid var(--border);
  }
  .graph-swatch-requirement { background: var(--chip-bg); }
  .graph-swatch-solution { background: var(--surface); border-color: var(--accent); }
  .graph-edge-sample {
    width: 1.6rem; height: 0; border-top: 1.5px solid var(--muted-2); display: inline-block;
  }
  .graph-edge-sample-cross { border-top-style: dashed; border-top-color: var(--accent); }

  .graph-scroll { overflow-x: auto; padding-bottom: 0.5rem; }
  .graph-svg { display: block; }
  .graph-edge {
    fill: none; stroke: var(--muted-2); stroke-width: 1.5;
  }
  .graph-edge-cross { stroke: var(--accent); stroke-dasharray: 5 4; }
  .graph-arrowhead { fill: var(--accent); }
  .graph-node rect {
    stroke-width: 1.5; cursor: default;
  }
  .graph-node-requirement rect { fill: var(--chip-bg); stroke: var(--border); }
  .graph-node-solution rect { fill: var(--surface); stroke: var(--accent); }
  .graph-node-label {
    font-family: "IBM Plex Sans", -apple-system, sans-serif; font-size: 12px;
    fill: var(--fg); font-weight: 500;
  }
  .graph-node-badge {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 9.5px;
    fill: var(--muted-2); letter-spacing: 0.03em;
  }
  .graph-node-collapsible { cursor: pointer; }
  .graph-node-collapsible rect { cursor: pointer; }
  .graph-node-toggle { fill: var(--accent); stroke: var(--surface); stroke-width: 2; }
  .graph-node-toggle-glyph {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-size: 11px; font-weight: 600;
    fill: var(--accent-fg); dominant-baseline: middle; pointer-events: none;
  }
  .graph-hint { margin: 0.6rem 0 1.1rem; color: var(--muted-2); font-size: 0.78rem; font-style: italic; }
"""

_TITLE = "Live Testing Framework"

_BODY_TEMPLATE = """<title>{title}</title>
{fonts_link}
<style>{style}</style>
  <div class="masthead">
    <p class="kicker">live_testing_framework &middot; requirement coverage</p>
    <h1>Requirements &amp; candidate solutions</h1>
    <p class="subtitle">
      One section per requirement, listing every candidate solution that
      satisfies it. Expand a solution to see its pros and cons.
    </p>
  </div>
  {requirements_html}
"""


def render_content(data: dict, graph_data: dict) -> str:
    """Title + fonts link + style + body content, no surrounding document
    tags -- for publishing as a Claude Artifact (which wraps its own
    <!doctype>/<html>/<head>/<body> and rejects one of its own)."""
    requirements_html = _render_new_tree_graph_section(graph_data)
    requirements_html += "".join(_render_requirement(r, data) for r in data["requirements"])
    requirements_html += f'<hr class="section-divider">{_render_solutions_section(data)}'
    return _BODY_TEMPLATE.format(
        title=html.escape(_TITLE), fonts_link=_FONTS_LINK, style=_STYLE, requirements_html=requirements_html
    )


def render_report(data: dict, graph_data: dict) -> str:
    """A full, directly-openable standalone HTML document."""
    new_tree_graph_html = _render_new_tree_graph_section(graph_data)
    requirements_html = "".join(_render_requirement(r, data) for r in data["requirements"])
    solutions_section_html = _render_solutions_section(data)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(_TITLE)}</title>
{_FONTS_LINK}
<style>{_STYLE}</style>
</head>
<body>
  <div class="masthead">
    <p class="kicker">live_testing_framework &middot; requirement coverage</p>
    <h1>Requirements &amp; candidate solutions</h1>
    <p class="subtitle">
      One section per requirement, listing every candidate solution that
      satisfies it. Expand a solution to see its pros and cons.
    </p>
  </div>
  {new_tree_graph_html}
  {requirements_html}
  <hr class="section-divider">
  {solutions_section_html}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--fragment", action="store_true",
        help="Write title/style/body content only, for publishing as a Claude Artifact.",
    )
    args = parser.parse_args()

    registrar = Registrar.from_manifest(["docs/manifest", "story_simulator"])
    data = load_report_data(registrar)
    graph_data = load_new_tree_graph_data(registrar)
    content = render_content(data, graph_data) if args.fragment else render_report(data, graph_data)
    args.output.write_text(content)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
