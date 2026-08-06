"""The tiered judgment resolver: `character_communication`/`resolve_event`'s shared way
of getting a real decision, regardless of who -- or what -- ends up answering it.

Three tiers, same request shape (`JudgmentRequest`) at every call site:

1. "subagent" -- a nested specialist call on story-simulator's own key, no
   MCP round-trip. Exactly what `TerrainAgent`/`PhysicsAgent`/
   `advance_npc_turn`'s decide step already do via `story_simulator.agents.complete`.
2. "sampling" -- MCP sampling (`ctx.session.create_message`): the connected
   client's own model/provider, not ours. Confirmed *unavailable* in this
   project's actual client (Claude Code CLI 2.1.222 declares no `sampling`
   client capability -- tested live this session two ways: through this
   session's own harness and through an independently spawned `claude -p`
   subprocess). Implemented anyway so a future client that does support it
   only needs `tier="sampling"` at a call site, not new code here.
3. "yield" -- hand control back to the connected agent entirely, via the
   `NeedsPlayerInput` exception below. The only tier that can guarantee a
   real human actually answered (see the design discussion this module
   codifies), and the only one that tolerates the player disappearing
   indefinitely between rounds.

Tier 3 is reached by raising, not by every intervening function being a
generator (`yield from` chains would work too, but would require
`character_communication`, `process_event`, and everything between a deep
nested call and the tool boundary to *all* be generators, whether or not
that particular call path ever pauses -- the classic "function coloring"
problem). An ordinary Python exception propagates through arbitrary plain
function calls for free, which is what lets a judgment call reach tier 3
from any nesting depth -- `character_communication` included, nested two
levels inside `process_event`.

Resuming does not mean resuming a suspended stack frame -- there isn't
one, the stack already unwound. It means re-running the whole turn from
the top of the event loop with the answer now available (see `TurnReplay`).
That's only correct because everything upstream of a judgment call is a
pure registry read -- the same idempotence already required for a paused
turn to survive an MCP disconnect without losing anything but the
in-flight decision (see CLAUDE.md's disconnect-recovery section). This
module doesn't introduce that requirement, it spends one already paid for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from story_simulator.agents import AgentSpec, complete
from story_simulator.config import resolve_anthropic_api_key


@dataclass
class JudgmentRequest:
    """One judgment ask, in the same shape no matter which tier answers it.

    Swapping a call site from `tier="yield"` to `tier="sampling"` (once/if
    a connected client actually supports it) is then a one-word change at
    the call site, not a rewrite of the request itself.
    """

    prompt: str
    system_prompt: str = ""
    max_tokens: int = 512

    def render(self) -> str:
        """Flatten to plain text for tier="yield" -- no separate system/user
        split there, just a prompt returned to the connected agent as an
        ordinary tool result."""
        return f"{self.system_prompt}\n\n{self.prompt}" if self.system_prompt else self.prompt


class NeedsPlayerInput(Exception):
    """Raised to unwind to the tool boundary when only tier 3 can answer this.

    `resume_index` is this judgment call's position in encounter order
    within one deterministic replay of a turn -- see `TurnReplay`.
    """

    def __init__(self, prompt: str, resume_index: int):
        super().__init__(prompt)
        self.prompt = prompt
        self.resume_index = resume_index


async def _via_subagent(request: JudgmentRequest, spec: AgentSpec) -> str:
    """Tier 1. Proven pattern -- same as `TerrainAgent.generate`/`PhysicsAgent.resolve`/
    `_advance_npc_turn_async`'s decide step, all via `story_simulator.agents.complete`.

    `spec.system` carries the subagent's own standing identity; `request.system_prompt`
    (if any) is this specific ask, folded into the message content rather
    than a second system message -- `complete` only carries one.
    """
    content = f"{request.system_prompt}\n\n{request.prompt}" if request.system_prompt else request.prompt
    response = complete(spec, [{"role": "user", "content": content}], api_key=resolve_anthropic_api_key())
    return response.choices[0].message.content or ""


async def _via_sampling(ctx: Any, request: JudgmentRequest) -> str:
    """Tier 2. The connected client's own model/provider, not ours -- see this
    module's docstring for why it's wired in but not reachable today."""
    result = await ctx.session.create_message(
        messages=[{"role": "user", "content": {"type": "text", "text": request.prompt}}],
        system_prompt=request.system_prompt or None,
        max_tokens=request.max_tokens,
    )
    content = result.content
    return content.text if hasattr(content, "text") else str(content)


@dataclass
class TurnReplay:
    """One turn's replay pass: a call-index counter plus the answer bank so far.

    A single turn can hit more than one judgment call before it's done
    (`get_character_input`, then separately `resolve_event`, possibly more
    nested under either) -- `resume_index` is just encounter order within a
    deterministic replay, so `answers[i]` is unambiguous: the i-th
    judgment call in any replay of this exact turn is always the same
    call, since nothing upstream of it has a side effect. `start_simulation`
    creates one with `answers=[]`; `submit_input` creates a fresh one with
    the stashed answers plus the newest, and re-runs the turn from the top.
    """

    answers: list[str] = field(default_factory=list)
    call_index: int = field(default=0, init=False)

    async def resolve(
        self,
        request: JudgmentRequest,
        *,
        tier: str,
        spec: AgentSpec | None = None,
        ctx: Any = None,
    ) -> str:
        i, self.call_index = self.call_index, self.call_index + 1
        if i < len(self.answers):
            return self.answers[i]
        if tier == "subagent":
            if spec is None:
                raise ValueError("tier='subagent' requires spec")
            return await _via_subagent(request, spec)
        if tier == "sampling":
            if ctx is None:
                raise ValueError("tier='sampling' requires ctx")
            return await _via_sampling(ctx, request)
        if tier == "yield":
            raise NeedsPlayerInput(prompt=request.render(), resume_index=i)
        raise ValueError(f"unknown tier {tier!r}")
