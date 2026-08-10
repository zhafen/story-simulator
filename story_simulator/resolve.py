"""The judgment resolver: `resolve_base_event`'s way of getting a real
decision, regardless of who ends up answering it.

Same request shape (`JudgmentRequest`) at every call site, dispatched by
`responder`. Only "host" (the connected/hosting agent itself decides,
autonomously) is reachable today -- "human" (a real player's answer) still
exists here as a responder value `resolve()` accepts, kept for whichever
character-facing code eventually returns from `shelved/` (see
docs/architecture.md) and needs it again, but nothing currently calls this
with anything but "host". "subagent" (a nested specialist call on
story-simulator's own key, no MCP round-trip, via
`TurnReplay.resolve_preferring_subagent`) was removed along with its only
caller (`get_character_input`) and its dependency on `story_simulator.agents`
(now shelved too) -- see git history to bring it back.

"human"/"host" are reached by raising `NeedsExternalInput`, resumed
through MRTR (Multi Round-Trip Requests, MCP spec 2026-07-28) rather than
MCP sampling. Sampling would have offered a third option -- the connected
client's own model/provider, not ours -- but it's gone: deprecated
protocol-wide by that same spec revision, not just unsupported by this
project's actual client (Claude Code CLI 2.1.222 declared no `sampling`
capability, confirmed live before the deprecation).

Raising is what lets a judgment call reach either from any nesting depth
without every intervening function having to be a generator (`yield from`
chains would work too, but would require every function between a deep
nested call and the tool boundary to *all* be generators, whether or not
that particular call path ever pauses -- the classic "function coloring"
problem). An ordinary Python exception propagates through arbitrary plain
function calls for free.

Resuming does not mean resuming a suspended stack frame -- there isn't
one, the stack already unwound. It means re-running the whole turn from
the top of the event loop with the answers-so-far now available (see
`TurnReplay`), replaying each already-answered judgment call instead of
re-asking it. That's only correct because everything upstream of a
judgment call is a pure registry read -- the same idempotence already
required for a paused turn to survive an MCP disconnect without losing
anything but the in-flight decision (see CLAUDE.md's disconnect-recovery
section). This module doesn't introduce that requirement, it spends one
already paid for.

The answers-so-far themselves travel in an opaque token
(`mcp_server._encode_token`/`_decode_token`), not server-side session
state -- see `mcp_server.advance_simulation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JudgmentRequest:
    """One judgment ask, in the same shape no matter which responder answers it.

    Swapping a call site from `responder="human"` to `responder="subagent"`
    (see `mcp_server._build_npc_decision_prompt` for the sibling "spec"
    pattern this needs) is then a one-word change at the call site, not a
    rewrite of the request itself.
    """

    prompt: str
    system_prompt: str = ""

    def render(self) -> str:
        """Flatten to plain text for responder="human"/"host" -- no separate
        system/user split there, just a prompt returned to the connected
        agent as an ordinary tool result."""
        return f"{self.system_prompt}\n\n{self.prompt}" if self.system_prompt else self.prompt


class NeedsExternalInput(Exception):
    """Raised to unwind to the tool boundary when this can only be answered
    outside story-simulator's own process.

    `responder` is "human" (a real player) or "host" (the connected agent
    deciding autonomously, e.g. standing in for a missing subagent key) --
    carried through to `mcp_server.advance_simulation`'s returned result so
    whichever host answers it knows whether to relay this to an actual
    human or just decide it itself.
    """

    def __init__(self, prompt: str, responder: str):
        super().__init__(prompt)
        self.prompt = prompt
        self.responder = responder


@dataclass
class TurnReplay:
    """One turn's replay pass: a call-index counter plus the answer bank so far.

    A single turn can hit more than one judgment call before it's done --
    encounter order within a deterministic replay makes `answers[i]`
    unambiguous: the i-th judgment call in any replay of this exact turn
    is always the same call, since nothing upstream of it has a side
    effect. `advance_simulation` creates one with `answers=[]` for a fresh
    turn, or with the decoded token's answers plus the newest to resume
    one -- either way, re-running the turn from the top.
    """

    answers: list[str] = field(default_factory=list)
    call_index: int = field(default=0, init=False)

    async def resolve(self, request: JudgmentRequest, *, responder: str) -> str:
        i, self.call_index = self.call_index, self.call_index + 1
        if i < len(self.answers):
            return self.answers[i]
        if responder in ("human", "host"):
            raise NeedsExternalInput(prompt=request.render(), responder=responder)
        raise ValueError(f"unknown responder {responder!r}")
