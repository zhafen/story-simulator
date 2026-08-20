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
- "keyed_subagent" -- answered directly, in-process, via
  `story_simulator.keyed_subagent.call_keyed_subagent` and
  `config.keyed_subagent_model()` (LiteLLM, DeepSeek by default -- see
  #89), with real registry tool access so it can actually persist what it
  decides. No MCP round-trip: never raises `NeedsExternalInput`, so a turn
  using it never pauses for this call the way "human"/"subagent"/"host"
  always do -- except once its own wall-clock time budget
  (`config.keyed_subagent_time_budget_seconds()`) runs out for this
  `advance_simulation` call, at which point it checks in with the host
  the same way "host" would, so an unattended run can't chain past Claude
  Code's own per-MCP-tool-call timeout.

A responder of this same name (a nested specialist call on
story-simulator's own API key, no MCP round-trip, via
`TurnReplay.resolve_preferring_keyed_subagent`) was removed along with its
only caller (`get_character_input`) and its dependency on
`story_simulator.agents` (now shelved too) -- see git history, and PR #42
("Rename responders and add isolated subagent delegation option") for the
fuller four-way design this is a subset of. The version above is a
narrower revival: no `AgentSpec`/YAML config, no NPC/character framing,
just a direct LiteLLM call with real registry tool access -- see
`story_simulator.keyed_subagent`'s own docstring.

"human"/"subagent"/"host" are reached by raising `NeedsExternalInput`, resumed
through MRTR (Multi Round-Trip Requests, MCP spec 2026-07-28) rather than
MCP sampling. Sampling would have offered a third option -- the connected
client's own model/provider, not ours -- but it's gone: deprecated
protocol-wide by that same spec revision, not just unsupported by this
project's actual client (Claude Code CLI 2.1.222 declared no `sampling`
capability, confirmed live before the deprecation). "keyed_subagent" is
the odd one out here: it answers inline, in the same `await`, without
ever raising (except its own deadline check-in, which does raise, framed
as "host") -- there is no host to round-trip to for this responder in the
ordinary case.

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

import time
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
        """Flatten to plain text -- no separate system/user split for any
        of "human"/"subagent"/"host".

        Just a prompt returned to the connected agent as an ordinary
        tool result. `_frame_for_responder` wraps this with per-responder
        instructions before it ever leaves this process.
        """
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
    "host" is about to read it.

    So they travel with the prompt text itself (survives an MRTR
    pause/resume, an MCP disconnect, a different host entirely
    reconnecting) rather than living only in `mcp_server`'s static tool
    descriptions, which a given client may or may not still have in view
    by the time it matters.
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
        # actually spawned an isolated subagent rather than just answering inline.
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
        # "orchestrator") this call expects but can't actually confirm.
        return (
            "Decide the answer yourself, standing in for whichever role "
            "this call needs (a player's own absent character, an NPC, a "
            "base-module entity whose end_time has been reached, ...) -- "
            "don't wait for input and don't hand this off.\n\n" + body
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
    # Absolute time.monotonic() value "keyed_subagent" must stop answering
    # inline by, for *this* advance_simulation call.
    deadline: float | None = None

    async def resolve(self, request: JudgmentRequest, *, responder: str, session=None) -> str:
        i, self.call_index = self.call_index, self.call_index + 1
        if i < len(self.answers):
            return self.answers[i]
        if responder == "keyed_subagent":
            # Budget check first: keyed_subagent never pauses on its own,
            # so with nothing bounding it, a call can chain unboundedly many round-trips.
            if self.deadline is not None and time.monotonic() >= self.deadline:
                checkin_prompt = (
                    "The \"keyed_subagent\" responder has reached its time budget "
                    "for this advance_simulation call without needing your input on "
                    "anything -- it's been answering judgment calls on its own. "
                    f"{self.call_index - 1} judgment call(s) already answered this way "
                    "so far this call (already reflected in the registry). Call "
                    "advance_simulation again with the same resume_token to keep the "
                    "simulation running from exactly where it left off, or stop here "
                    "if this is a reasonable checkpoint."
                )
                raise NeedsExternalInput(prompt=checkin_prompt, responder="host")
            # No NeedsExternalInput here -- nothing external to wait on. Framed
            # the same way "host" is, since that's about how the model should behave.
            from story_simulator.keyed_subagent import call_keyed_subagent

            answer = await call_keyed_subagent(_frame_for_responder(request, "host"), session)
            self.answers.append(answer)
            return answer
        if responder in ("human", "subagent", "host"):
            raise NeedsExternalInput(prompt=_frame_for_responder(request, responder), responder=responder)
        raise ValueError(f"unknown responder {responder!r}")
