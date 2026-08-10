"""The judgment resolver: `character_communication`/`resolve_event`'s shared way
of getting a real decision, regardless of who -- or what -- ends up answering it.

Same request shape (`JudgmentRequest`) at every call site, dispatched by
`responder`:

1. "subagent" -- a nested specialist call on story-simulator's own key, no
   MCP round-trip. Exactly what `TerrainAgent`/`PhysicsAgent`/
   `advance_npc_turn`'s decide step already do via `story_simulator.agents.complete`.
   Requires story-simulator's own API key to actually be configured (see
   `story_simulator.config.resolve_anthropic_api_key`) -- not something
   every deployment can be assumed to have set up.
2. "human" -- a real human's answer, needed. Hand control back to the
   connected agent entirely, via the `NeedsExternalInput` exception below,
   resumed through MRTR (Multi Round-Trip Requests, MCP spec 2026-07-28)
   rather than MCP sampling, deprecated protocol-wide by that same spec
   revision before this project could adopt it -- see
   docs/manifest/history.yaml:
   project_history.mcp_sampling_deprecated_before_project_adoption.
   "human" is the only responder that can guarantee a real human actually
   answered, and the only one that tolerates the player disappearing
   indefinitely between rounds.
3. "host" -- the connected/hosting agent itself decides, autonomously, no
   real human involved -- same MRTR mechanism as "human" (same exception,
   same pause/resume), but standing in for "subagent" wherever we can't
   assume the deployment has its own key configured, rather than standing
   in for a real player. See `TurnReplay.resolve_preferring_subagent`.

"human"/"host" are reached by raising, not by every intervening function
being a generator (`yield from` chains would work too, but would require
`character_communication`, `process_event`, and everything between a deep
nested call and the tool boundary to *all* be generators, whether or not
that particular call path ever pauses -- the classic "function coloring"
problem). An ordinary Python exception propagates through arbitrary plain
function calls for free, which is what lets a judgment call reach either
from any nesting depth -- `character_communication` included, nested two
levels inside `process_event`.

Resuming does not mean resuming a suspended stack frame -- there isn't
one, the stack already unwound. It means re-running the whole turn from
the top of the event loop with the answers-so-far now available (see
`TurnReplay`), replaying each already-answered judgment call (of any
responder -- a "subagent" call isn't re-issued, it's replayed from cache
same as "human"/"host") instead of re-asking it. That's only correct
because everything upstream of a judgment call is a pure registry read --
the same idempotence already required for a paused turn to survive an MCP
disconnect without losing anything but the in-flight decision (see
CLAUDE.md's disconnect-recovery section). This module doesn't introduce
that requirement, it spends one already paid for.

The answers-so-far themselves travel in an opaque token
(`mcp_server._encode_token`/`_decode_token`), not server-side session
state -- see `mcp_server.advance_simulation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from story_simulator.agents import AgentSpec, complete
from story_simulator.config import resolve_anthropic_api_key


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


async def _via_subagent(request: JudgmentRequest, spec: AgentSpec) -> str:
    """Proven pattern -- same as `TerrainAgent.generate`/`PhysicsAgent.resolve`/
    `_advance_npc_turn_async`'s decide step, all via `story_simulator.agents.complete`.

    `spec.system` carries the subagent's own standing identity; `request.system_prompt`
    (if any) is this specific ask, folded into the message content rather
    than a second system message -- `complete` only carries one.
    """
    content = f"{request.system_prompt}\n\n{request.prompt}" if request.system_prompt else request.prompt
    response = complete(spec, [{"role": "user", "content": content}], api_key=resolve_anthropic_api_key())
    return response.choices[0].message.content or ""


@dataclass
class TurnReplay:
    """One turn's replay pass: a call-index counter plus the answer bank so far.

    A single turn can hit more than one judgment call before it's done
    (`get_character_input`, then separately `resolve_event`, possibly more
    nested under either) -- encounter order within a deterministic replay
    makes `answers[i]` unambiguous: the i-th judgment call in any replay of
    this exact turn is always the same call, since nothing upstream of it
    has a side effect. `advance_simulation` creates one with `answers=[]`
    for a fresh turn, or with the decoded token's answers plus the newest
    to resume one -- either way, re-running the turn from the top.
    """

    answers: list[str] = field(default_factory=list)
    call_index: int = field(default=0, init=False)

    async def resolve(
        self,
        request: JudgmentRequest,
        *,
        responder: str,
        spec: AgentSpec | None = None,
    ) -> str:
        i, self.call_index = self.call_index, self.call_index + 1
        if i < len(self.answers):
            return self.answers[i]
        if responder == "subagent":
            if spec is None:
                raise ValueError("responder='subagent' requires spec")
            return await _via_subagent(request, spec)
        if responder in ("human", "host"):
            raise NeedsExternalInput(prompt=request.render(), responder=responder)
        raise ValueError(f"unknown responder {responder!r}")

    async def resolve_preferring_subagent(self, request: JudgmentRequest, spec: AgentSpec) -> str:
        """Try responder="subagent" first, falling back to responder="host"
        if it fails -- e.g. no API key configured (see
        `story_simulator.config.resolve_anthropic_api_key`). We can't rely
        on every deployment having story-simulator's own subagent key set
        up, so an NPC-facing call site should reach for this instead of
        committing to "subagent" outright.

        Safe across a replay: a failed subagent attempt is never cached
        (only a successful return, or a "host" pause's eventual answer,
        ever lands in `TurnReplay.answers`), so a resumed replay's same
        call finds its answer already cached at this call's index -- via
        the ordinary `resolve` cache check -- and returns it directly,
        without re-attempting subagent or re-raising.
        """
        try:
            return await self.resolve(request, responder="subagent", spec=spec)
        except Exception:
            return await self.resolve(request, responder="host")
