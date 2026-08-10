"""The judgment resolver: `character_communication`/`resolve_event`'s shared way
of getting a real decision, regardless of who -- or what -- ends up answering it.

Same request shape (`JudgmentRequest`) at every call site, dispatched by
`responder`:

1. "keyed_subagent" -- a nested specialist call on story-simulator's own
   key, no MCP round-trip, via `story_simulator.agents.complete`.
   Requires story-simulator's own API key configured -- not guaranteed
   for every deployment. (Formerly just "subagent", renamed once that
   name was needed for something else, see below.)
2. "subagent" -- also a specialist's answer, but without story-simulator
   needing its own key: the connected host is asked, via the same MRTR
   pause as "human"/"host", to answer using its own subagent mechanism
   (e.g. Claude Code's Agent/Task tool) instead of its own accumulated
   context -- see `_render_for_host`'s "subagent" branch for the exact
   wording. Gets real context isolation without requiring a configured
   key, reusing whatever model access the host already has. Trust-based
   for now -- nothing verifies the host actually delegated rather than
   answering inline (see the TODO in `_render_for_host`).
3. "human" -- a real human's answer, needed. Hands control back to the
   connected host via the `NeedsExternalInput` exception below, resumed
   through MRTR (Multi Round-Trip Requests, MCP spec 2026-07-28) rather
   than MCP sampling (see docs/manifest/history.yaml:
   project_history.mcp_sampling_deprecated_before_project_adoption). The
   only responder that guarantees a real human answered, and the only one
   that tolerates the player disappearing indefinitely between rounds.
4. "host" -- the connected host decides inline, from its own accumulated
   context, no real human or isolated subagent involved -- same MRTR
   mechanism as "human"/"subagent", but standing in for "keyed_subagent"
   when no key is configured. See
   `TurnReplay.resolve_preferring_keyed_subagent`. Named for what's
   guaranteed (*some* connected host answered), not the role it's
   playing -- nothing here confirms it's deciding on its own initiative
   rather than relaying to a human or delegating to a subagent.

"human"/"subagent"/"host" are reached by raising, not by every
intervening function being a generator -- generators would require every
function between a deep nested call and the tool boundary to be one,
whether or not that path ever pauses (the "function coloring" problem).
A plain exception propagates through ordinary function calls for free,
reaching any of the three from any nesting depth.

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

    Swapping a call site from `responder="human"` to
    `responder="keyed_subagent"` is then a one-word change, not a rewrite
    of the request itself.
    """

    prompt: str
    system_prompt: str = ""

    def render(self) -> str:
        """Flatten to plain text -- no separate system/user split outside
        "keyed_subagent"'s own direct API call. Every other responder gets
        this same flattened text, framed differently per responder by
        `_render_for_host` before it leaves this process."""
        return f"{self.system_prompt}\n\n{self.prompt}" if self.system_prompt else self.prompt


class NeedsExternalInput(Exception):
    """Raised to unwind to the tool boundary when this can only be answered
    outside story-simulator's own process.

    `responder` is "human" (a real human), "subagent" (the connected host
    should answer via its own isolated subagent mechanism, not its own
    accumulated context), or "host" (the connected host decides inline,
    e.g. standing in for a missing keyed_subagent) -- carried through to
    `mcp_server.advance_simulation`'s result so whichever host answers it
    knows what's being asked of it.
    """

    def __init__(self, prompt: str, responder: str):
        super().__init__(prompt)
        self.prompt = prompt
        self.responder = responder


async def _via_keyed_subagent(request: JudgmentRequest, spec: AgentSpec) -> str:
    """Same pattern as `TerrainAgent.generate`/`PhysicsAgent.resolve`, via
    `story_simulator.agents.complete`.

    `spec.system` carries the subagent's standing identity; `request.system_prompt`
    (if any) is folded into the message content rather than a second
    system message -- `complete` only carries one.
    """
    content = f"{request.system_prompt}\n\n{request.prompt}" if request.system_prompt else request.prompt
    response = complete(spec, [{"role": "user", "content": content}], api_key=resolve_anthropic_api_key())
    return response.choices[0].message.content or ""


def _render_for_host(request: JudgmentRequest, responder: str) -> str:
    """Frame `request` for whichever of "human"/"subagent"/"host" is
    about to read it, so the instructions travel with the prompt text
    itself (survives an MRTR pause/resume, an MCP disconnect, a different
    host entirely reconnecting) rather than living only in
    `mcp_server`'s static tool descriptions, which a given client may or
    may not still have in view by the time it matters.
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
        # inline itself. A real check would need the resumed `answer` to
        # prove a subagent ran it: e.g. mint a single-use nonce per call,
        # embed it in this rendered prompt with an instruction that the
        # subagent's own response must begin with it verbatim, then have
        # the caller that receives the resumed `answer`
        # (mcp_server.advance_simulation) verify the nonce is present and
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
        # Framed as "decide it yourself" rather than naming a role
        # (e.g. "orchestrator") this call expects but can't actually
        # confirm -- see this module's own docstring, responder 4.
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
        if responder == "keyed_subagent":
            if spec is None:
                raise ValueError("responder='keyed_subagent' requires spec")
            return await _via_keyed_subagent(request, spec)
        if responder in ("human", "subagent", "host"):
            raise NeedsExternalInput(prompt=_render_for_host(request, responder), responder=responder)
        raise ValueError(f"unknown responder {responder!r}")

    async def resolve_preferring_keyed_subagent(self, request: JudgmentRequest, spec: AgentSpec) -> str:
        """Try responder="keyed_subagent" first, falling back to
        responder="host" if it fails (e.g. no API key configured). Not
        every deployment has story-simulator's own subagent key set up,
        so an NPC-facing call site should reach for this instead of
        committing to "keyed_subagent" outright.

        Falls back to "host", not the newer "subagent" -- this method's
        behavior is deliberately unchanged by that addition. A call site
        that wants isolated-context delegation instead can reach for
        responder="subagent" directly via `resolve`.

        Safe across a replay: only a successful return (or a
        "host"/"subagent" pause's eventual answer) is ever cached in
        `TurnReplay.answers`, so a resumed replay's same call finds its
        answer already cached and returns it directly, without
        re-attempting keyed_subagent.
        """
        try:
            return await self.resolve(request, responder="keyed_subagent", spec=spec)
        except Exception:
            return await self.resolve(request, responder="host")
