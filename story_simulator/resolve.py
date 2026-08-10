"""The judgment resolver: `character_communication`/`resolve_event`'s shared way
of getting a real decision, regardless of who -- or what -- ends up answering it.

Same request shape (`JudgmentRequest`) at every call site, dispatched by
`responder`:

1. "subagent" -- a nested specialist call on story-simulator's own key, no
   MCP round-trip, via `story_simulator.agents.complete`. Requires
   story-simulator's own API key configured -- not guaranteed for every
   deployment.
2. "human" -- a real human's answer, needed. Hands control back to the
   connected agent via the `NeedsExternalInput` exception below, resumed
   through MRTR (Multi Round-Trip Requests, MCP spec 2026-07-28) rather
   than MCP sampling (see docs/manifest/history.yaml:
   project_history.mcp_sampling_deprecated_before_project_adoption). The
   only responder that guarantees a real human answered, and the only one
   that tolerates the player disappearing indefinitely between rounds.
3. "host" -- the connected/hosting agent decides autonomously, no real
   human involved -- same MRTR mechanism as "human", but standing in for
   "subagent" when no key is configured rather than for a real player.
   See `TurnReplay.resolve_preferring_subagent`.

"human"/"host" are reached by raising, not by every intervening function
being a generator -- generators would require every function between a
deep nested call and the tool boundary to be one, whether or not that
path ever pauses (the "function coloring" problem). A plain exception
propagates through ordinary function calls for free, reaching from any
nesting depth.

Resuming doesn't mean resuming a suspended stack frame -- there isn't
one, the stack already unwound. It means re-running the whole turn from
the top with the answers-so-far available (see `TurnReplay`), replaying
each already-answered judgment call from cache instead of re-asking it.
Only correct because everything upstream of a judgment call is a pure
registry read -- the same idempotence a paused turn already needs to
survive an MCP disconnect (see CLAUDE.md's disconnect-recovery section).

The answers-so-far travel in an opaque token
(`mcp_server._encode_token`/`_decode_token`), not server-side session
state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from story_simulator.agents import AgentSpec, complete
from story_simulator.config import resolve_anthropic_api_key


@dataclass
class JudgmentRequest:
    """One judgment ask, in the same shape no matter which responder answers it.

    Swapping a call site from `responder="human"` to `responder="subagent"`
    is then a one-word change, not a rewrite of the request itself.
    """

    prompt: str
    system_prompt: str = ""

    def render(self) -> str:
        """Flatten to plain text for responder="human"/"host" -- no separate
        system/user split, just a prompt returned as an ordinary tool result."""
        return f"{self.system_prompt}\n\n{self.prompt}" if self.system_prompt else self.prompt


class NeedsExternalInput(Exception):
    """Raised to unwind to the tool boundary when this can only be answered
    outside story-simulator's own process.

    `responder` is "human" (a real player) or "host" (the connected agent
    deciding autonomously) -- carried through to
    `mcp_server.advance_simulation`'s result so whichever host answers it
    knows whether to relay this to an actual human or decide it itself.
    """

    def __init__(self, prompt: str, responder: str):
        super().__init__(prompt)
        self.prompt = prompt
        self.responder = responder


async def _via_subagent(request: JudgmentRequest, spec: AgentSpec) -> str:
    """Same pattern as `TerrainAgent.generate`/`PhysicsAgent.resolve`, via
    `story_simulator.agents.complete`.

    `spec.system` carries the subagent's standing identity; `request.system_prompt`
    (if any) is folded into the message content rather than a second
    system message -- `complete` only carries one.
    """
    content = f"{request.system_prompt}\n\n{request.prompt}" if request.system_prompt else request.prompt
    response = complete(spec, [{"role": "user", "content": content}], api_key=resolve_anthropic_api_key())
    return response.choices[0].message.content or ""


@dataclass
class TurnReplay:
    """One turn's replay pass: a call-index counter plus the answer bank so far.

    A single turn can hit more than one judgment call before it's done --
    encounter order within a deterministic replay makes `answers[i]`
    unambiguous, since nothing upstream of a judgment call has a side
    effect. `advance_simulation` creates one with `answers=[]` for a fresh
    turn, or with the decoded token's answers plus the newest to resume
    one -- either way, re-running the turn from the top.
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
        if it fails (e.g. no API key configured). Not every deployment has
        story-simulator's own subagent key set up, so an NPC-facing call
        site should reach for this instead of committing to "subagent"
        outright.

        Safe across a replay: only a successful return (or a "host"
        pause's eventual answer) is ever cached in `TurnReplay.answers`,
        so a resumed replay's same call finds its answer already cached
        and returns it directly, without re-attempting subagent.
        """
        try:
            return await self.resolve(request, responder="subagent", spec=spec)
        except Exception:
            return await self.resolve(request, responder="host")
