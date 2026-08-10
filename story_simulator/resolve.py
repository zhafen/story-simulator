"""The judgment resolver: `resolve_event`'s way of getting a real
decision, regardless of who ends up answering it.

Same request shape (`JudgmentRequest`) at every call site, dispatched by
`responder`:

- "host" -- the connected agent decides inline, from its own accumulated
  context. `resolve_event`'s default (see
  `story_simulator.config.event_responder`).
- "subagent" -- also the connected agent, but asked (via `_frame_for_responder`)
  to answer through its own isolated subagent mechanism (e.g. Claude Code's
  Agent/Task tool) instead of from its own accumulated context, giving a
  base event's judgment call subagent-shaped context isolation without
  story-simulator needing an API key of its own. Opt into it via
  `STORY_SIM_RESPONDER=subagent`. Nothing here verifies the connected
  agent actually delegated rather than just answering inline -- see the
  TODO in `_frame_for_responder`.
- "human" (a real player's answer) still exists here as a responder value
  `resolve()` accepts, kept for whichever character-facing code eventually
  returns from `shelved/` (see docs/architecture.md) and needs it again,
  but nothing currently calls this with "human".

A fourth responder, "keyed_subagent" (a nested specialist call on
story-simulator's own API key, no MCP round-trip, via
`TurnReplay.resolve_preferring_keyed_subagent`) was removed along with its
only caller (`get_character_input`) and its dependency on
`story_simulator.agents` (now shelved too) -- see git history, and PR #42
("Rename responders and add isolated subagent delegation option") for the
fuller four-way design this is a subset of, to bring it back alongside the
character/npc module it served.

"human"/"subagent"/"host" are reached by raising `NeedsExternalInput`, resumed
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
(`core._encode_token`/`_decode_token`), not server-side session
state -- see `core.advance_simulation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class JudgmentRequest:
    """One judgment ask, in the same shape no matter which responder answers it.

    Swapping a call site from `responder="host"` to `responder="subagent"`
    (see `story_simulator.config.event_responder`) is then a one-word
    change at the call site, not a rewrite of the request itself.
    """

    prompt: str
    system_prompt: str = ""

    def render(self) -> str:
        """Flatten to plain text -- no separate system/user split for any of
        "human"/"subagent"/"host", just a prompt returned to the connected
        agent as an ordinary tool result. `_frame_for_responder` wraps this
        with per-responder instructions before it ever leaves this process."""
        return f"{self.system_prompt}\n\n{self.prompt}" if self.system_prompt else self.prompt


class NeedsExternalInput(Exception):
    """Raised to unwind to the tool boundary when this can only be answered
    outside story-simulator's own process.

    `responder` is "human" (a real player), "subagent" (the connected agent
    should answer via its own isolated subagent mechanism, not its own
    accumulated context), or "host" (the connected agent decides inline
    itself) -- carried through to `core.advance_simulation`'s
    returned result so whichever host answers it knows what's actually
    being asked of it.
    """

    def __init__(self, prompt: str, responder: str):
        super().__init__(prompt)
        self.prompt = prompt
        self.responder = responder


def _frame_for_responder(request: JudgmentRequest, responder: str) -> str:
    """Wrap `request` with instructions for whichever of "human"/"subagent"/
    "host" is about to read it, so they travel with the prompt text itself
    (survives an MRTR pause/resume, an MCP disconnect, a different host
    entirely reconnecting) rather than living only in `mcp_server`'s static
    tool descriptions, which a given client may or may not still have in
    view by the time it matters.
    """
    body = request.render()
    if responder == "human":
        return (
            "Relay the following to the connected human player, verbatim, "
            "and resume with their own actual reply -- don't answer on "
            "their behalf.\n\n" + body
        )
    if responder == "subagent":
        # TODO: this is trust-based -- nothing here verifies the host
        # actually spawned an isolated subagent rather than just answering
        # inline itself. A real check would need the resumed answer to
        # prove a subagent ran it: e.g. mint a single-use nonce per call,
        # embed it in this rendered prompt with an instruction that the
        # subagent's own response must begin with it verbatim, then have
        # the caller that receives the resumed answer
        # (core.advance_simulation) verify the nonce is present and
        # strip it before treating the rest as the real answer. On a
        # missing/wrong nonce, don't advance the turn -- raise
        # NeedsExternalInput again with a corrective prompt (same
        # resume_token/nonce) so the host gets re-prompted to actually
        # delegate this time, instead of silently accepting an inline
        # answer wearing a "subagent" label.
        return (
            "Answer this via your own subagent mechanism (e.g. Claude "
            "Code's Agent/Task tool), not from your own accumulated "
            "context: pass the text below as that subagent's entire "
            "prompt, run it in the foreground (you need its result before "
            "you can resume), and resume with its answer verbatim as your "
            "own answer.\n\n" + body
        )
    if responder == "host":
        # Framed as "decide it yourself" rather than naming a role (e.g.
        # "orchestrator") this call expects but can't actually confirm --
        # see this module's own docstring's "host" entry.
        return (
            "No human and no subagent is behind this -- decide the answer "
            "yourself, standing in for whichever role this call needed "
            "(a player's own absent character, an NPC, a base-module "
            "entity that's come due, ...).\n\n" + body
        )
    raise ValueError(f"unknown responder {responder!r}")


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
        if responder in ("human", "subagent", "host"):
            raise NeedsExternalInput(prompt=_frame_for_responder(request, responder), responder=responder)
        raise ValueError(f"unknown responder {responder!r}")
