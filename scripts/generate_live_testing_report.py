#!/usr/bin/env python3
"""Generate an HTML report of the human_validated_test_framework
alternating requirement/solution tree (docs/manifest/story-simulator.yaml):
a left-to-right collapsible graph, then a requirement-first document below
it sourced from that exact same tree -- one section per requirement,
listing every solution that satisfies it (both directly nested under that
requirement and any solution of: cross-links onto it), each expandable to
show its own pros and cons. Followed by a solution-first "Solutions"
section -- every candidate solution listed once, with which requirement(s)
it solves shown inside its own expandable entry, for the solutions that
cover more than one requirement and would otherwise only show up once per
requirement above. A solution serving multiple requirements is one node
either way -- same name, same description, listed under each requirement
it solves, never duplicated under a second name.

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

Prints nothing to stdout; writes a single self-contained HTML file (no
external requests except the Google Fonts stylesheet) to --output,
defaulting to a scratch path outside the repo, matching
find_live_testing_solution_covers.py's own precedent of not committing
generated output, only the generator.

--fragment writes just the title/style/body content, without the
surrounding <!doctype>/<html>/<head>/<body> tags -- for publishing as a
Claude Artifact, which wraps that skeleton on its own and rejects one of
its own. Omit --fragment for a normal, directly-openable standalone page.

Run: uv run python scripts/generate_live_testing_report.py [--output PATH] [--fragment]
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from emc2p.registrar import Registrar

DEFAULT_OUTPUT = Path("/tmp/live_testing_framework_report.html")

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


def build_new_tree_report_data(registrar: Registrar, graph_data: dict) -> dict:
    """The "Requirements & candidate solutions" body and "Solutions" index
    below the graph, sourced from the same human_validated_test_framework
    subtree the graph itself renders -- so the document actually reflects
    the graph (what solutions exist, and which requirement(s) each one
    solves), instead of the older mirrored requirements:/candidate_solutions:
    trees this report used to read from. Same return shape as the old
    load_report_data() had, keyed by each node's short `key` rather than
    a name derived from a fixed path prefix, so _render_requirement/
    _render_solution/_render_solutions_section all work unchanged.

    A solution nested under one requirement but also solution of: another
    (see the graph's cross_edges) is the same node either way -- it's
    listed under both requirements, but as one shared name/description/
    cost/pros-cons, never duplicated under a second name.
    """
    nodes = graph_data["nodes"]
    by_id = {n["id"]: n for n in nodes}
    key_of = {n["id"]: n["key"] for n in nodes}
    root_id = next((n["id"] for n in nodes if n["parent_id"] is None), None)

    requirement_ids = [n["id"] for n in nodes if n["type"] == "requirement"]
    solution_ids = [n["id"] for n in nodes if n["type"] == "solution" and n["id"] != root_id]

    req_to_solutions: dict[str, list[str]] = {key_of[rid]: [] for rid in requirement_ids}
    solution_to_requirements: dict[str, list[str]] = {key_of[sid]: [] for sid in solution_ids}

    def add_link(sol_id: str, req_id: str) -> None:
        req_key = key_of.get(req_id)
        sol_key = key_of.get(sol_id)
        if req_key not in req_to_solutions or sol_key is None:
            return
        if sol_key not in req_to_solutions[req_key]:
            req_to_solutions[req_key].append(sol_key)
        if req_key not in solution_to_requirements[sol_key]:
            solution_to_requirements[sol_key].append(req_key)

    for sid in solution_ids:
        parent_id = by_id[sid]["parent_id"]
        if parent_id and by_id.get(parent_id, {}).get("type") == "requirement":
            add_link(sid, parent_id)
    for from_id, to_id in graph_data["cross_edges"]:
        if by_id.get(from_id, {}).get("type") == "solution" and by_id.get(to_id, {}).get("type") == "requirement":
            add_link(from_id, to_id)
    for d in (req_to_solutions, solution_to_requirements):
        for k in d:
            d[k].sort()

    subtree_ids = set(by_id)
    costs: dict[str, list[tuple[str, float]]] = {}
    for _, row in registrar.get("cost").execute().iterrows():
        eid = str(row["entity_id"])
        if eid in subtree_ids:
            costs.setdefault(key_of[eid], []).append((str(row["type"]), float(row["value"])))

    pros_cons: dict[str, list[dict]] = {}
    for sign in ("pro", "con"):
        for _, row in registrar.get(sign).execute().iterrows():
            eid = str(row["entity_id"])
            if eid in subtree_ids:
                pros_cons.setdefault(key_of[eid], []).append({"sign": sign, "note": str(row["value"])})

    code_examples: dict[str, dict] = {}
    for _, row in registrar.get("code_example").execute().iterrows():
        eid = str(row["entity_id"])
        if eid in subtree_ids:
            code_examples[key_of[eid]] = {"language": str(row["language"]), "code": str(row["value"])}

    return {
        "requirements": sorted(key_of[rid] for rid in requirement_ids),
        "req_to_solutions": req_to_solutions,
        "solution_to_requirements": solution_to_requirements,
        "descriptions": {n["key"]: n["description"] for n in nodes},
        "work_states": {n["key"]: n["work_state"] for n in nodes if n["work_state"]},
        "code_examples": code_examples,
        "costs": costs,
        "pros_cons": pros_cons,
    }


_GRAPH_NODE_W = 210
_GRAPH_NODE_H = 44
_GRAPH_H_GAP = 60
_GRAPH_V_GAP = 14


def _render_new_tree_graph_section(graph_data: dict) -> str:
    """Left-to-right tree graph (root at the left, depth grows rightward,
    siblings stack vertically). Layout runs client-side, not in Python:
    the whole point of the -/+ collapse toggle is to make the diagram
    genuinely smaller when a branch is hidden, which means re-computing
    positions for whatever's currently visible and shrinking the SVG's own
    viewBox to match -- a build-it-once-in-Python-then-hide-elements
    approach can't do that, it just leaves blank space where the hidden
    subtree used to be. So Python only serializes the node/edge data;
    layoutTree()/render() below (plain JS, no framework) do the actual
    tidy-tree math and DOM building, called once on load and again on
    every toggle.
    """
    nodes = graph_data["nodes"]
    if not nodes:
        return ""

    payload = {
        "nodes": [
            {
                "id": n["id"],
                "key": n["key"],
                "label": n["label"],
                "type": n["type"],
                "description": n["description"].strip().replace("\n\n", " ").replace("\n", " "),
                "work_state": n["work_state"],
                "parent_id": n["parent_id"],
            }
            for n in nodes
        ],
        "cross_edges": [list(pair) for pair in graph_data["cross_edges"]],
    }
    # Embedded as its own application/json element rather than inlined into
    # a JS string literal -- description text is full of apostrophes
    # ("it's", "doesn't", ...) that would otherwise break out of whatever
    # quote character wrapped it. This way nothing needs JS-string
    # escaping at all, only the standard "</script" HTML-parser guard.
    data_json = json.dumps(payload).replace("</", "<\\/")

    script = f"""
    <script type="application/json" class="graph-data">{data_json}</script>
    <script>
    (function() {{
      var W = {_GRAPH_NODE_W}, H = {_GRAPH_NODE_H}, HGAP = {_GRAPH_H_GAP}, VGAP = {_GRAPH_V_GAP};
      var SVGNS = 'http://www.w3.org/2000/svg';
      var root = document.currentScript.closest('.yaml-preview');
      var svg = root.querySelector('.graph-svg');
      var data = JSON.parse(root.querySelector('.graph-data').textContent);
      var byId = {{}};
      data.nodes.forEach(function(n) {{ byId[n.id] = n; }});
      var childrenOf = {{}};
      var roots = [];
      data.nodes.forEach(function(n) {{
        if (n.parent_id) {{ (childrenOf[n.parent_id] = childrenOf[n.parent_id] || []).push(n.id); }}
        else {{ roots.push(n.id); }}
      }});
      Object.keys(childrenOf).forEach(function(pid) {{
        childrenOf[pid].sort(function(a, b) {{ return byId[a].key.localeCompare(byId[b].key); }});
      }});
      roots.sort(function(a, b) {{ return byId[a].key.localeCompare(byId[b].key); }});
      var collapsed = new Set();

      function layout() {{
        var positions = {{}};
        var nextRow = 0;
        function visit(id, depth) {{
          var kids = collapsed.has(id) ? [] : (childrenOf[id] || []);
          var y;
          if (kids.length === 0) {{
            y = nextRow + 0.5; nextRow += 1;
          }} else {{
            var ys = kids.map(function(k) {{ return visit(k, depth + 1); }});
            y = ys.reduce(function(a, b) {{ return a + b; }}, 0) / ys.length;
          }}
          positions[id] = {{x: depth * (W + HGAP) + HGAP / 2, y: y * (H + VGAP) - H / 2, depth: depth}};
          return y;
        }}
        roots.forEach(function(r) {{ visit(r, 0); }});
        var maxDepth = 0;
        Object.keys(positions).forEach(function(id) {{ maxDepth = Math.max(maxDepth, positions[id].depth); }});
        return {{positions: positions, width: (maxDepth + 1) * (W + HGAP), height: nextRow * (H + VGAP)}};
      }}

      function el(tag, attrs, text) {{
        var e = document.createElementNS(SVGNS, tag);
        for (var k in attrs) {{ e.setAttribute(k, attrs[k]); }}
        if (text !== undefined) {{ e.textContent = text; }}
        return e;
      }}

      function render() {{
        var lay = layout();
        var positions = lay.positions;
        svg.setAttribute('viewBox', '0 0 ' + lay.width + ' ' + lay.height);
        svg.setAttribute('width', lay.width);
        svg.setAttribute('height', lay.height);
        var content = svg.querySelector('.graph-content');
        content.innerHTML = '';

        data.nodes.forEach(function(n) {{
          var p = positions[n.parent_id];
          var here = positions[n.id];
          if (!p || !here) return;
          var x1 = p.x + W, y1 = p.y + H / 2, x2 = here.x, y2 = here.y + H / 2;
          content.appendChild(el('path', {{
            'class': 'graph-edge',
            d: 'M ' + x1 + ' ' + y1 + ' C ' + (x1 + HGAP / 2) + ' ' + y1 + ', ' + (x2 - HGAP / 2) + ' ' + y2 + ', ' + x2 + ' ' + y2,
          }}));
        }});
        data.cross_edges.forEach(function(pair) {{
          var a = positions[pair[0]], b = positions[pair[1]];
          if (!a || !b) return;
          var sx = a.x + W, sy = a.y + H / 2, tx = b.x + W, ty = b.y + H / 2, bulge = 46;
          content.appendChild(el('path', {{
            'class': 'graph-edge graph-edge-cross',
            d: 'M ' + sx + ' ' + sy + ' C ' + (sx + bulge) + ' ' + sy + ', ' + (tx + bulge) + ' ' + ty + ', ' + tx + ' ' + ty,
            'marker-end': 'url(#graph-arrow)',
          }}));
        }});
        data.nodes.forEach(function(n) {{
          var pos = positions[n.id];
          if (!pos) return;
          var hasKids = (childrenOf[n.id] || []).length > 0;
          var cls = 'graph-node graph-node-' + n.type + (hasKids ? ' graph-node-collapsible' : '');
          var g = el('g', {{'class': cls, transform: 'translate(' + pos.x + ',' + pos.y + ')', 'data-id': n.id}});
          var title = el('title', {{}}, n.label + '\\n\\n' + n.description);
          g.appendChild(title);
          g.appendChild(el('rect', {{width: W, height: H, rx: n.type === 'requirement' ? 8 : H / 2}}));
          g.appendChild(el('text', {{'class': 'graph-node-label', x: 10, y: H / 2 + 4.5}}, n.label));
          if (n.work_state) {{
            g.appendChild(el('text', {{'class': 'graph-node-badge', x: W - 8, y: 15, 'text-anchor': 'end'}}, n.work_state));
          }}
          if (hasKids) {{
            g.appendChild(el('circle', {{'class': 'graph-node-toggle', cx: W, cy: H / 2, r: 7}}));
            g.appendChild(el('text', {{
              'class': 'graph-node-toggle-glyph', x: W, y: H / 2 + 3.5, 'text-anchor': 'middle',
            }}, collapsed.has(n.id) ? '+' : String.fromCharCode(8722)));
            g.addEventListener('click', function() {{
              if (collapsed.has(n.id)) {{ collapsed.delete(n.id); }} else {{ collapsed.add(n.id); }}
              render();
            }});
          }}
          content.appendChild(g);
        }});
      }}

      render();
    }})();
    </script>"""

    return f"""
  <details class="yaml-preview" open>
    <summary>
      <span class="yaml-preview-title">Alternating-tree redesign -- graph view</span>
    </summary>
    <p class="graph-legend">
      <span class="graph-legend-item"><span class="graph-swatch graph-swatch-requirement"></span>requirement</span>
      <span class="graph-legend-item"><span class="graph-swatch graph-swatch-solution"></span>solution</span>
      <span class="graph-legend-item"><span class="graph-edge-sample"></span>nested (implied) relation</span>
      <span class="graph-legend-item"><span class="graph-edge-sample graph-edge-sample-cross"></span>additional solution of: link</span>
    </p>
    <div class="graph-scroll">
      <svg class="graph-svg">
        <defs>
          <marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" class="graph-arrowhead"/>
          </marker>
        </defs>
        <g class="graph-content"></g>
      </svg>
    </div>
    <p class="graph-hint">Hover a node for its full description. Click a node with a &#8722;/+ marker to collapse or expand its branch -- the diagram reflows and shrinks.</p>
    {script}
  </details>
  <hr class="section-divider">"""


def _label(name: str) -> str:
    return name.replace("_", " ")


# Only split where sentence-ending punctuation is followed by whitespace
# AND a capital letter/digit/quote/paren -- i.e. what a new sentence
# actually starts with. Without the lookahead, abbreviations like "e.g."
# get mis-split ("...from the host (e.g." | "claude) or a keyed subagent
# ..."), cutting a sentence off mid-parenthetical.
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9"\'(])')


def _sentences(text: str) -> list[str]:
    text = text.strip()
    return [s for s in _SENTENCE_SPLIT_RE.split(text) if s] if text else []


def _render_description(text: str, class_name: str = "description") -> str:
    """A description leads with its first sentence; the rest sits behind a
    small inline expand toggle -- unless the whole description is already
    3 sentences or fewer, in which case there's nothing meaningful to hide
    and it's just shown in full."""
    text = text.strip()
    if not text:
        return ""
    sentences = _sentences(text)
    if len(sentences) <= 3:
        return f'<div class="{class_name}">{html.escape(text)}</div>'
    summary = html.escape(sentences[0])
    rest = html.escape(" ".join(sentences[1:]))
    return (
        f'<div class="{class_name}">{summary} '
        f'<details class="description-more"><summary></summary>{rest}</details></div>'
    )


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
    description_html = _render_description(data["descriptions"].get(name, ""), "solution-description")
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
          {description_html}
          {requirements_html}
          {code_example_html}
          <ul class="ratings">{ratings_html}</ul>
        </div>
      </details>"""


def _render_toc_section(graph_data: dict) -> str:
    """A table of contents: the same alternating-tree structure the graph
    above already draws, as a plain-text outline instead -- one entry per
    requirement/solution/sub-requirement, each with its own description
    (leading sentence + expand for the rest). Replaces what used to be a
    full prose section per requirement, each with its solutions rendered
    in full: that duplicated the graph outright once the graph existed,
    just in a slower, heavier form. Full solution detail (cost, pros/cons,
    example code) lives one section down, in the Solutions index -- this
    section is deliberately just an outline."""
    nodes = graph_data["nodes"]
    by_id = {n["id"]: n for n in nodes}
    children: dict[str, list[str]] = {}
    for n in nodes:
        if n["parent_id"]:
            children.setdefault(n["parent_id"], []).append(n["id"])
    for pid in children:
        children[pid].sort(key=lambda nid: by_id[nid]["key"])

    also_solves: dict[str, list[str]] = {}
    for from_id, to_id in graph_data["cross_edges"]:
        also_solves.setdefault(from_id, []).append(to_id)
    for k in also_solves:
        also_solves[k].sort(key=lambda nid: by_id[nid]["key"])

    root_id = next((n["id"] for n in nodes if n["parent_id"] is None), None)

    def render_node(node_id: str) -> str:
        n = by_id[node_id]
        desc_html = _render_description(n["description"], "toc-description")
        extra = ""
        if node_id in also_solves:
            names = ", ".join(html.escape(_label(by_id[t]["key"])) for t in also_solves[node_id])
            extra = f'<p class="toc-also-solves">Also solves: {names}</p>'
        work = ""
        if n["work_state"]:
            ws = html.escape(n["work_state"])
            work = f'<span class="work-state work-state-{html.escape(n["work_state"].replace(" ", "-"))}">{ws}</span>'
        kids_html = "".join(render_node(k) for k in children.get(node_id, []))
        kids_wrap = f'<ul class="toc-children">{kids_html}</ul>' if kids_html else ""
        return f"""
      <li class="toc-item toc-item-{n["type"]}">
        <div class="toc-item-head">
          <span class="toc-item-badge toc-item-badge-{n["type"]}">{n["type"]}</span>
          <span class="toc-item-label">{html.escape(n["label"])}</span>
          {work}
        </div>
        {desc_html}
        {extra}
        {kids_wrap}
      </li>"""

    top_ids = sorted(children.get(root_id, []), key=lambda nid: by_id[nid]["key"])
    items_html = "".join(render_node(nid) for nid in top_ids)

    return f"""
  <div class="masthead">
    <p class="kicker">live_testing_framework &middot; table of contents</p>
    <h1>Requirements</h1>
    <p class="subtitle">
      Outline of the alternating-tree redesign shown in the graph above --
      expand a description for the rest of it. Full solution detail
      (cost, pros/cons, example code) is in the Solutions index below.
    </p>
  </div>
  <ul class="toc-root">{items_html}</ul>"""


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

  ul.toc-root, ul.toc-children { list-style: none; margin: 0; padding: 0; }
  ul.toc-children { padding-left: 1.4rem; margin-top: 0.6rem; border-left: 1px solid var(--border); }
  li.toc-item { margin-bottom: 1rem; }
  li.toc-item:last-child { margin-bottom: 0; }
  .toc-item-head { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .toc-item-label {
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-weight: 600;
    font-size: 0.95rem; text-wrap: balance;
  }
  .toc-item-requirement > .toc-item-head .toc-item-label { font-size: 1.05rem; }
  .toc-item-badge {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.62rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
    padding: 0.1rem 0.45rem; border-radius: 5px;
  }
  .toc-item-badge-requirement { background: var(--chip-bg); color: var(--chip-fg); }
  .toc-item-badge-solution { background: transparent; color: var(--accent); border: 1px solid var(--accent); }
  .toc-description { color: var(--muted); margin: 0.3rem 0 0; max-width: 62ch; font-size: 0.92rem; }
  .toc-also-solves { color: var(--muted-2); font-size: 0.8rem; font-style: italic; margin: 0.3rem 0 0; }
  .description { color: var(--fg); margin: 0; max-width: 62ch; }
  .description-more {
    display: inline; font-size: 0.9em;
  }
  .description-more summary {
    display: inline; cursor: pointer; color: var(--accent); list-style: none;
  }
  .description-more summary::-webkit-details-marker { display: none; }
  .description-more summary::before { content: "(more)"; }
  .description-more[open] summary::before { content: "(less)"; }

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
  {requirements_html}
"""


def _render_body_sections(data: dict, graph_data: dict) -> str:
    graph_html = _render_new_tree_graph_section(graph_data)
    toc_html = _render_toc_section(graph_data)
    solutions_html = _render_solutions_section(data)
    return f'{graph_html}{toc_html}<hr class="section-divider">{solutions_html}'


def render_content(data: dict, graph_data: dict) -> str:
    """Title + fonts link + style + body content, no surrounding document
    tags -- for publishing as a Claude Artifact (which wraps its own
    <!doctype>/<html>/<head>/<body> and rejects one of its own)."""
    return _BODY_TEMPLATE.format(
        title=html.escape(_TITLE),
        fonts_link=_FONTS_LINK,
        style=_STYLE,
        requirements_html=_render_body_sections(data, graph_data),
    )


def render_report(data: dict, graph_data: dict) -> str:
    """A full, directly-openable standalone HTML document."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(_TITLE)}</title>
{_FONTS_LINK}
<style>{_STYLE}</style>
</head>
<body>
  {_render_body_sections(data, graph_data)}
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
    graph_data = load_new_tree_graph_data(registrar)
    data = build_new_tree_report_data(registrar, graph_data)
    content = render_content(data, graph_data) if args.fragment else render_report(data, graph_data)
    args.output.write_text(content)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
