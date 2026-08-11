---
name: MCP release checklist
about: Checklist for cutting a story-simulator release
title: 'Release vX.Y.Z checklist'
labels: type:docs, area:mcp-packaging
assignees: ''
---

Reusable checklist for any story-simulator release, not just v1.0 -- see
[zhafen/story-simulator#49](https://github.com/zhafen/story-simulator/issues/49)
for the one this was cut from.

## Packaging & versioning
- [ ] Semantic version bump in `pyproject.toml`, matching CHANGELOG entry
- [ ] `CHANGELOG.md` maintained (Keep a Changelog format)
- [ ] `LICENSE` present and correct for intended use
- [ ] README quickstart followed on a genuinely clean clone -- no assumed tribal knowledge
- [ ] Installable via one documented command (`uvx`/`pip install`) or a published Docker image

## Correctness & safety
- [ ] Full suite green in CI, including a fresh-clone smoke test
- [ ] No secrets committed; `.env.example` matches what the code actually reads
- [ ] Every tool taking free-form input (e.g. `yaml_string`) validates it
- [ ] Documented failure modes -- what a client sees if Postgres is unreachable, etc.

## Docs
- [ ] Architecture doc current -- no stale claims about what's shelved vs. live
- [ ] Generated architecture diagrams regenerated, not just prose
- [ ] `CONTRIBUTING.md` still matches actual dev setup / test / branch conventions
- [ ] Tool-by-tool usage notes or an example transcript

## Distribution & connector readiness
- [ ] Works as a local stdio MCP server via one documented command
- [ ] Remote endpoint reachable by URL, addable as a Claude custom connector (if that's this release's distribution story)
- [ ] Auth/session-isolation story documented if remote or multi-tenant

## GitHub hygiene
- [ ] Issue and PR templates still accurate
- [ ] CI passing required as a branch-protection rule on `main`
- [ ] Release tagged and a GitHub Release published with real notes
