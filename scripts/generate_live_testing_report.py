#!/usr/bin/env python3
"""Generate an HTML report of the human_validated_test_framework
alternating requirement/solution tree (docs/manifest/story-simulator.yaml):
a minimal table of contents (section headers only, linking down the page),
then a requirement-first document sourced from that exact same tree -- one
section per requirement, listing every solution that satisfies it (both
directly nested under that requirement and any solution of: cross-links
onto it), each expandable to show its own pros and cons. Followed by a
solution-first "Solutions" section -- every candidate solution listed
once, with which requirement(s) it solves shown inside its own expandable
entry, for the solutions that cover more than one requirement and would
otherwise only show up once per requirement above. A solution serving
multiple requirements is one node either way -- same name, same
description, listed under each requirement it solves, never duplicated
under a second name. Finally, a "Dependencies" section -- every concrete
implementation entity a selected solution still needs built, linked via
`dependence of:` relations and gathered here once each (again never
duplicated under a second name when more than one solution needs the
same one), so they can be reviewed and organized as their own body of
work.

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
from pathlib import Path

from emc2p.registrar import Registrar

DEFAULT_OUTPUT = Path("/tmp/live_testing_framework_report.html")

NEW_TREE_ENTITY_KEY = "human_validated_test_framework"
NEW_TREE_MANIFEST_PATH = Path("docs/manifest/story-simulator.yaml")

# The dependencies: subtree holds implementation entities (see
# load_dependencies_data), not requirements/solutions -- excluded from the
# requirement/solution graph's own node collection below so it doesn't
# leak in as bogus requirement-typed nodes (every entity with a parent and
# no explicit requirement/solution tag defaults to "requirement" there).
DEPENDENCIES_KEY = "dependencies"
DEPENDENCIES_MARKER = f".{NEW_TREE_ENTITY_KEY}.{DEPENDENCIES_KEY}"

# On a real D3.js graph viz, if a graph visualization of this tree is ever
# wanted again (an earlier revision of this report rendered one, since
# replaced by the plain table of contents below -- see git history): this
# report gets published as a Claude Artifact, whose CSP blocks CDN script
# loads outright (Google Fonts is the one exception) -- a normal
# <script src="https://d3js.org/..."> tag would silently fail to load
# there. The fix isn't to drop D3, it's to vendor it: paste D3's full
# built bundle (e.g. https://d3js.org/d3.v7.min.js, ~280KB) directly into
# a <script> tag with no src attribute, so nothing is fetched externally
# -- that satisfies the Artifact's "fully self-contained" rule and unlocks
# real D3 (animated collapse/expand, zoom/pan, force layouts).


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
        if (marker in clean(p) or clean(p).endswith(NEW_TREE_ENTITY_KEY))
        and DEPENDENCIES_MARKER not in clean(p)
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


def load_dependencies_data(registrar: Registrar) -> dict:
    """The dependencies: subtree -- concrete implementation entities that
    selected solutions above need built, linked to them via `dependence
    of:` relations. Kept separate from load_new_tree_graph_data/
    build_new_tree_report_data because these entities aren't
    requirements or solutions themselves (see DEPENDENCIES_MARKER's
    exclusion from the graph's own node collection above).

    Returns {"entities": {key: {"description", "work_state"}},
    "solution_to_dependencies": {solution_key: [dep_key, ...]},
    "dependency_to_solutions": {dep_key: [solution_key, ...]}}, keyed by
    each entity's own short key. A dependency needed by more than one
    solution (e.g. split_fixtures_between_emc2p_and_story_simulator's own
    fixtures) is one entity, listed under each solution that needs it --
    same "shared name, not duplicated" convention as the requirement/
    solution graph.
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

    container_prefix = f"{DEPENDENCIES_MARKER}."
    entity_keys: dict[str, str] = {}
    for eid, p in path_of.items():
        cp = clean(p)
        idx = cp.find(container_prefix)
        if idx == -1:
            continue
        rest = cp[idx + len(container_prefix):]
        if "." in rest:
            continue  # only direct children of dependencies:, not further-nested entities
        entity_keys[eid] = rest

    descriptions: dict[str, str] = {}
    for _, row in registrar.get("description").execute().iterrows():
        eid = str(row["entity_id"])
        if eid in entity_keys:
            descriptions[entity_keys[eid]] = str(row["value"])

    work_states: dict[str, str] = {}
    for _, row in registrar.get("work_state").execute().iterrows():
        eid = str(row["entity_id"])
        if eid in entity_keys:
            work_states[entity_keys[eid]] = str(row["value"])

    entities = {
        key: {
            "description": descriptions.get(key, ""),
            "work_state": work_states.get(key, "unknown"),
        }
        for key in entity_keys.values()
    }

    def short_key(eid: str) -> str:
        return clean(path_of[eid]).rsplit(".", 1)[-1]

    solution_to_dependencies: dict[str, list[str]] = {}
    dependency_to_solutions: dict[str, list[str]] = {}
    dep_df = resolved.get("dependence")
    if dep_df is not None:
        for _, row in dep_df.to_pandas().iterrows():
            src_eid = str(row["entity_id"])
            tgt_eid = row.get("value_eid")
            if tgt_eid is None or (isinstance(tgt_eid, float) and tgt_eid != tgt_eid):
                continue
            tgt_eid = str(tgt_eid)
            if tgt_eid not in entity_keys or src_eid not in path_of:
                continue
            dep_key = entity_keys[tgt_eid]
            sol_key = short_key(src_eid)
            solution_to_dependencies.setdefault(sol_key, [])
            if dep_key not in solution_to_dependencies[sol_key]:
                solution_to_dependencies[sol_key].append(dep_key)
            dependency_to_solutions.setdefault(dep_key, [])
            if sol_key not in dependency_to_solutions[dep_key]:
                dependency_to_solutions[dep_key].append(sol_key)

    for d in (solution_to_dependencies, dependency_to_solutions):
        for k in d:
            d[k].sort()

    return {
        "entities": entities,
        "solution_to_dependencies": solution_to_dependencies,
        "dependency_to_solutions": dependency_to_solutions,
    }


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

    selected: dict[str, bool] = {}
    for _, row in registrar.get("selected").execute().iterrows():
        eid = str(row["entity_id"])
        if eid in subtree_ids:
            selected[key_of[eid]] = bool(row["value"])

    return {
        "requirements": sorted(key_of[rid] for rid in requirement_ids),
        "req_to_solutions": req_to_solutions,
        "solution_to_requirements": solution_to_requirements,
        "descriptions": {n["key"]: n["description"] for n in nodes},
        "work_states": {n["key"]: n["work_state"] for n in nodes if n["work_state"]},
        "code_examples": code_examples,
        "costs": costs,
        "pros_cons": pros_cons,
        "selected": selected,
    }


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
    is_selected = data["selected"].get(name, False)
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
    selected_class = " solution-selected" if is_selected else ""
    selected_badge = '<span class="selected-badge">Selected</span>' if is_selected else ""
    return f"""
      <details class="solution{selected_class}">
        <summary>
          {selected_badge}
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


def _requirement_anchor(name: str) -> str:
    return f"req-{name}"


def _render_toc_section(data: dict) -> str:
    """A table of contents: literally just section headers, one per
    requirement, linking down to that requirement's own section below --
    no descriptions, no solution names, no prose. The full detail lives in
    the requirement sections themselves (and the Solutions index), not
    here."""
    items_html = "".join(
        f'<li><a href="#{_requirement_anchor(r)}">{html.escape(_label(r))}</a></li>'
        for r in data["requirements"]
    )
    return f"""
  <div class="masthead">
    <p class="kicker">live_testing_framework &middot; table of contents</p>
    <h1>Contents</h1>
  </div>
  <nav class="toc"><ul class="toc-root">{items_html}</ul></nav>"""


def _render_requirement(name: str, data: dict) -> str:
    description = html.escape(data["descriptions"].get(name, ""))
    solution_names = data["req_to_solutions"].get(name, [])
    if solution_names:
        solutions_html = "".join(_render_solution(s, data) for s in solution_names)
    else:
        solutions_html = '<p class="no-solutions">No candidate solution currently solves this requirement.</p>'
    return f"""
  <section class="requirement" id="{_requirement_anchor(name)}">
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
    instead of repeated under each requirement it happens to cover. Split
    into Selected and Unselected -- once a requirement has a chosen
    solution, distinguishing "the decided plan" from "the rest of the
    candidates" matters more than a single flat list."""
    solution_names = sorted(data["solution_to_requirements"])
    selected_names = [s for s in solution_names if data["selected"].get(s, False)]
    unselected_names = [s for s in solution_names if not data["selected"].get(s, False)]
    selected_html = "".join(
        _render_solution(s, data, show_requirements=True) for s in selected_names
    ) or '<p class="no-solutions">None yet.</p>'
    unselected_html = "".join(
        _render_solution(s, data, show_requirements=True) for s in unselected_names
    ) or '<p class="no-solutions">None -- every candidate solution has been selected.</p>'
    return f"""
  <div class="masthead">
    <p class="kicker">live_testing_framework &middot; solution index</p>
    <h1>Solutions</h1>
    <p class="subtitle">
      Every candidate solution once, regardless of how many requirements it
      covers. Expand a solution to see what it solves, its pros and cons.
    </p>
  </div>
  <h2 class="solutions-subheading">Selected</h2>
  {selected_html}
  <h2 class="solutions-subheading">Unselected</h2>
  {unselected_html}"""


def _render_dependency(key: str, dependencies_data: dict) -> str:
    entity = dependencies_data["entities"][key]
    description = html.escape(entity["description"])
    work_state = entity["work_state"]
    solution_names = dependencies_data["dependency_to_solutions"].get(key, [])
    chips = "".join(
        f'<span class="req-chip">{html.escape(_label(s))}</span>' for s in solution_names
    ) or '<span class="req-chip req-chip-none">none currently</span>'
    return f"""
      <details class="solution">
        <summary>
          <span class="solution-name">{html.escape(_label(key))}</span>
          <span class="work-state work-state-{html.escape(work_state.replace(' ', '-'))}">{html.escape(work_state)}</span>
        </summary>
        <div class="solution-body">
          <p class="solution-description">{description}</p>
          <p class="section-label">Needed by</p>
          <div class="req-chips">{chips}</div>
        </div>
      </details>"""


def _render_dependencies_section(dependencies_data: dict) -> str:
    """Every unique implementation entity the selected solutions above
    depend on, once each -- gathered here (rather than left scattered
    across each solution that needs one) so they can be reviewed and
    organized as their own body of work."""
    keys = sorted(dependencies_data["entities"])
    items_html = "".join(_render_dependency(k, dependencies_data) for k in keys)
    return f"""
  <div class="masthead">
    <p class="kicker">live_testing_framework &middot; dependencies</p>
    <h1>Dependencies</h1>
    <p class="subtitle">
      Concrete entities the selected solutions above still need built,
      gathered here once each -- a shared dependency (e.g. one needed by
      both a requirement's own solution and
      split_fixtures_between_emc2p_and_story_simulator) is listed once,
      under every solution that needs it.
    </p>
  </div>
  {items_html}"""


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

  nav.toc { margin-bottom: 2.75rem; }
  ul.toc-root { list-style: none; margin: 0; padding: 0; }
  ul.toc-root li { border-top: 1px solid var(--border); }
  ul.toc-root li:last-child { border-bottom: 1px solid var(--border); }
  ul.toc-root a {
    display: block; padding: 0.65rem 0.1rem;
    font-family: "IBM Plex Mono", ui-monospace, monospace; font-weight: 600;
    font-size: 0.95rem; color: var(--fg); text-decoration: none;
  }
  ul.toc-root a:hover { color: var(--accent); }

  .requirement { margin-bottom: 2.75rem; scroll-margin-top: 1.5rem; }
  .eyebrow {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--accent); margin: 0 0 0.3rem;
  }
  .requirement h2 {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 1.25rem; font-weight: 600; margin: 0 0 0.5rem;
    text-wrap: balance; letter-spacing: -0.01em;
  }
  .requirement-description { color: var(--muted); margin: 0 0 0.9rem; max-width: 62ch; }
  .no-solutions { color: var(--muted-2); font-style: italic; margin: 0 0 0.9rem; }

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
  details.solution.solution-selected { border-color: var(--pro); background: var(--pro-bg); }
  details.solution.solution-selected summary::before { color: var(--pro); }
  .selected-badge {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 0.66rem; font-weight: 600; letter-spacing: 0.04em;
    padding: 0.12rem 0.5rem; border-radius: 5px;
    background: var(--pro); color: var(--accent-fg); white-space: nowrap;
  }
  .solutions-subheading {
    font-family: "IBM Plex Mono", ui-monospace, monospace;
    font-size: 1.05rem; font-weight: 600; margin: 1.8rem 0 0;
  }
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
"""

_TITLE = "Live Testing Framework"

_BODY_TEMPLATE = """<title>{title}</title>
{fonts_link}
<style>{style}</style>
  {requirements_html}
"""


def _render_body_sections(data: dict, dependencies_data: dict) -> str:
    toc_html = _render_toc_section(data)
    requirements_html = "".join(_render_requirement(r, data) for r in data["requirements"])
    solutions_html = _render_solutions_section(data)
    dependencies_html = _render_dependencies_section(dependencies_data)
    return (
        f'{toc_html}{requirements_html}<hr class="section-divider">{solutions_html}'
        f'<hr class="section-divider">{dependencies_html}'
    )


def render_content(data: dict, dependencies_data: dict) -> str:
    """Title + fonts link + style + body content, no surrounding document
    tags -- for publishing as a Claude Artifact (which wraps its own
    <!doctype>/<html>/<head>/<body> and rejects one of its own)."""
    return _BODY_TEMPLATE.format(
        title=html.escape(_TITLE),
        fonts_link=_FONTS_LINK,
        style=_STYLE,
        requirements_html=_render_body_sections(data, dependencies_data),
    )


def render_report(data: dict, dependencies_data: dict) -> str:
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
  {_render_body_sections(data, dependencies_data)}
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
    dependencies_data = load_dependencies_data(registrar)
    content = (
        render_content(data, dependencies_data)
        if args.fragment
        else render_report(data, dependencies_data)
    )
    args.output.write_text(content)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
