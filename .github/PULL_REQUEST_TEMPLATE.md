## Summary

<!-- What changed and why, in a sentence or two. -->

## Key changes

-

## Test plan

- [ ] `uv run pytest -m "not live"` passes locally
- [ ] Submodule pointer check passes if `iacs` moved (`scripts/check-submodule-pointers.sh --staged`, or let the pre-commit hook catch it)
- [ ] Manually exercised the change (via `story-simulator-mcp`, or however it's reachable) if it touches tool behavior

## Related

<!-- Link the epic this belongs under (see #45's sub-issues), and/or the issue this closes. -->
