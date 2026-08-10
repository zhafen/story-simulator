"""The judgment resolver: `character_communication`/`resolve_event`'s shared way
of getting a real decision, regardless of who -- or what -- ends up answering it.

Same request shape (`JudgmentRequest`) at every call site, dispatched by
`responder`:

1. "keyed_subagent" -- a nested specialist call on story-simulator's own key,
   no MCP round-trip. Exactly what `TerrainAgent`/`PhysicsAgent`/
   `advance_npc_turn`'s decide step already do via `story_simulator.agents.complete`.
   Requires story-simulator's own API key to actually be configured (see
   `story_simulator.config.resolve_anthropic_api_key`) -- not something
   every deployment can be assumed to have set up. (Formerly just
   "subagent" -- renamed once that name was needed for something else,
   see below.)

2. "subagent" -- also a specialist's answer, but without story-simulator
   needing its own key: the connected host is asked, via the same MRTR
   pause as "human"/"orchestrator" below, to answer using its OWN subagent
   mechanism (e.g. Claude Code's Agent/Task tool) instead of from its own
   accumulated conversation context -- see `_render_for_host`'s "subagent"
   branch for the exact wording asked of it. This is what actually gets
   story-sim "subagent-shaped" context isolation without requiring every
   deployment to configure its own key: whatever model access the
   connected host already has gets reused for free, the same way
   responder="orchestrator" already does, just framed to ask for a fresh,
   isolated subagent call instead of an inline decision. Nothing currently
   verifies the host actually did that rather than just answering inline
   -- see the TODO in `_render_for_host`.

3. "human" -- a real human's answer, needed. Hand control back to the
   connected host entirely, via the `NeedsExternalInput` exception
   below, resumed through MRTR (Multi Round-Trip Requests, MCP spec
   2026-07-28) rather than MCP sampling. Sampling would have offered a
   third option -- the connected client's own model/provider, not ours --
   but it's gone: deprecated protocol-wide by that same spec revision, not
   just unsupported by this project's actual client (Claude Code CLI
   2.1.222 declared no `sampling` capability, confirmed live before the
   deprecation). "human" is the only responder that can guarantee a real
   human actually answered, and the only one that tolerates the player
   disappearing indefinitely between rounds.

4. "orchestrator" -- the connected host itself decides, inline, from its
   own accumulated context, no real human and no isolated subagent call
   involved -- same MRTR mechanism as "human"/"subagent" (same exception,
   same pause/resume), but standing in for "keyed_subagent" wherever we
   can't assume the deployment has its own key configured, rather than
   standing in for a real player. See
   `TurnReplay.resolve_preferring_keyed_subagent`. (This specific
   responder value used to just be called "host" too -- renamed to
   "orchestrator" once "host" was already doing double duty as this
   project's general term for the connected entity, which every responder
   value routes through one way or another. "host" stays the general term;
   "orchestrator" now names only this one inline-decide mode, removing
   that overlap.)

"human"/"subagent"/"orchestrator" are reached by raising, not by every
intervening function being a generator (`yield from` chains would work
too, but would require `character_communication`, `process_event`, and
everything between a deep nested call and the tool boundary to *all* be
generators, whether or not that particular call path ever pauses -- the
classic "function coloring" problem). An ordinary Python exception
propagates through arbitrary plain function calls for free, which is what
lets a judgment call reach any of the three from any nesting depth --
`character_communication` included, nested two levels inside
`process_event`.

Resuming does not mean resuming a suspended stack frame -- there isn't
one, the stack already unwound. It means re-running the whole turn from
the top of the event loop with the answers-so-far now available (see
`TurnReplay`), replaying each already-answered judgment call (of any
responder -- a "keyed_subagent" call isn't re-issued, it's replayed from
cache same as "human"/"subagent"/"orchestrator") instead of re-asking it.
That's only correct because everything upstream of a judgment call is a
pure registry read -- the same idempotence already required for a paused
turn to survive an MCP disconnect without losing anything but the
in-flight decision (see CLAUDE.md's disconnect-recovery section). This
module doesn't introduce that requirement, it spends one already paid for.

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

    Swapping a call site from `responder="human"` to `responder="keyed_subagent"`
    (see `mcp_server._build_npc_decision_prompt` for the sibling "spec"
    pattern this needs) is then a one-word change at the call site, not a
    rewrite of the request itself.
    """

    prompt: str
    system_prompt: str = ""

    def render(self) -> str:
        """Flatten to plain text -- no separate system/user split outside
        "keyed_subagent"'s own direct API call. Every other responder gets
        this same flattened text, then framed differently per responder by
        `_render_for_host` before it ever leaves this process."""
        return f"{self.system_prompt}\n\n{self.prompt}" if self.system_prompt else self.prompt


class NeedsExternalInput(Exception):
    """Raised to unwind to the tool boundary when this can only be answered
    outside story-simulator's own process.

    `responder` is "human" (a real human), "subagent" (the connected
    host should answer via its own isolated subagent mechanism,
    not its own accumulated context), or "orchestrator" (the connected
    host decides inline itself, e.g. standing in for a missing
    keyed_subagent) -- carried through to `mcp_server.advance_simulation`'s
    returned result so whichever host answers it knows what's
    actually being asked of it.
    """

    def __init__(self, prompt: str, responder: str):
        super().__init__(prompt)
        self.prompt = prompt
        self.responder = responder


async def _via_keyed_subagent(request: JudgmentRequest, spec: AgentSpec) -> str:
    """Proven pattern -- same as `TerrainAgent.generate`/`PhysicsAgent.resolve`/
    `_advance_npc_turn_async`'s decide step, all via `story_simulator.agents.complete`.

    `spec.system` carries the subagent's own standing identity; `request.system_prompt`
    (if any) is this specific ask, folded into the message content rather
    than a second system message -- `complete` only carries one.
    """
    content = f"{request.system_prompt}\n\n{request.prompt}" if request.system_prompt else request.prompt
    response = complete(spec, [{"role": "user", "content": content}], api_key=resolve_anthropic_api_key())
    return response.choices[0].message.content or ""


def _render_for_host(request: JudgmentRequest, responder: str) -> str:
    """Frame `request` for whichever of "human"/"subagent"/"orchestrator" is
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
    if responder == "orchestrator":
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
        if responder == "keyed_subagent":
            if spec is None:
                raise ValueError("responder='keyed_subagent' requires spec")
            return await _via_keyed_subagent(request, spec)
        if responder in ("human", "subagent", "orchestrator"):
            raise NeedsExternalInput(prompt=_render_for_host(request, responder), responder=responder)
        raise ValueError(f"unknown responder {responder!r}")

    async def resolve_preferring_keyed_subagent(self, request: JudgmentRequest, spec: AgentSpec) -> str:
        """Try responder="keyed_subagent" first, falling back to
        responder="orchestrator" if it fails -- e.g. no API key configured
        (see `story_simulator.config.resolve_anthropic_api_key`). We can't
        rely on every deployment having story-simulator's own subagent key
        set up, so an NPC-facing call site should reach for this instead of
        committing to "keyed_subagent" outright.

        Falls back to "orchestrator", not the newer "subagent" -- this
        method's own behavior is deliberately unchanged by that addition,
        so existing call sites keep their existing fallback shape. A call
        site that wants isolated-context delegation instead of an inline
        host decision can already reach for responder="subagent"
        directly via `resolve`, without going through this method at all.

        Safe across a replay: a failed keyed_subagent attempt is never
        cached (only a successful return, or an "orchestrator"/"subagent"
        pause's eventual answer, ever lands in `TurnReplay.answers`), so a
        resumed replay's same call finds its answer already cached at this
        call's index -- via the ordinary `resolve` cache check -- and
        returns it directly, without re-attempting keyed_subagent or
        re-raising.
        """
        try:
            return await self.resolve(request, responder="keyed_subagent", spec=spec)
        except Exception:
            return await self.resolve(request, responder="orchestrator")
