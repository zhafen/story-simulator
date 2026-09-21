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
  the same way "host" would, so an unattended run periodically surfaces
  what it's doing instead of chaining silently -- see #76 for replacing
  this with MCP progress notifications instead, the protocol-native
  mechanism for exactly this.

"human"/"subagent"/"host" are reached by raising `NeedsExternalInput`, resumed
through MRTR (Multi Round-Trip Requests, MCP spec 2026-07-28) rather than
MCP sampling: sampling is deprecated protocol-wide by that same spec
revision, not just unsupported by any one client, so it isn't an
available option regardless of what a connected client might otherwise
support. "keyed_subagent" is the odd one out here: it answers inline, in
the same `await`, without ever raising (except its own deadline
check-in, which does raise, framed as "host") -- there is no host to
round-trip to for this responder in the ordinary case.

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

The answers-so-far themselves are persisted into the registry, keyed to
the paused event's own alias (`core._save_pending`/`_load_pending`), not
this process's own session state -- see `core.advance_simulation`. The
`resume_token` handed back to the client is just that alias.
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
    # Which function constructed this request (e.g. "resolve_event" vs.
    # "plan_events") -- never folded into `prompt`/`render()`'s own text
    # (a responder has no need to know this to answer), but carried
    # through to whichever responder answers it so it lands in that
    # call's own trace instead of being unrecoverable after the fact.
    # "" (the default) matches call sites/tests that don't care to set it.
    origin: str = ""

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

    `is_checkpoint` marks keyed_subagent's own budget check-in pause (see
    `TurnReplay.resolve`) -- its reply is never game content, so `core.py`'s
    resume plumbing must not fold it into `TurnReplay.answers`.

    `origin` carries through the request's own `JudgmentRequest.origin`
    (which function raised this) -- not currently surfaced any further
    than this attribute (`core.py`'s host/subagent return path doesn't
    thread it into the JSON handed back to the client), but stored here
    rather than dropped so that's a small addition later, not a rewrite.
    """

    def __init__(self, prompt: str, responder: str, is_checkpoint: bool = False, origin: str = ""):
        super().__init__(prompt)
        self.prompt = prompt
        self.responder = responder
        self.is_checkpoint = is_checkpoint
        self.origin = origin


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
        # Framed as "nothing else this is routed to" rather than naming a
        # role (e.g. "orchestrator", "narrator") this call expects but
        # can't actually confirm -- and rather than enumerating examples
        # of what might be involved (a player's own character, an NPC, an
        # ordinary base-module entity), which read as a list of roles to
        # pick from rather than the plain fact that no one else is coming.
        return (
            "Decide this yourself, right now, from your own context and "
            "whatever you look up below -- there's no human player or "
            "subagent this has been routed to, so don't wait for further "
            "input and don't hand it off.\n\n" + body
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
        if responder == "keyed_subagent":
            # Cache check first, not gated on budget: an already-answered
            # call must keep replaying fast regardless of the deadline.
            i = self.call_index
            if i < len(self.answers):
                self.call_index += 1
                return self.answers[i]
            # A new call: check budget first. Doesn't consume call_index/
            # answers, so a resume retries this same call fresh (is_checkpoint).
            if self.deadline is not None and time.monotonic() >= self.deadline:
                checkin_prompt = (
                    "The \"keyed_subagent\" responder has reached its time budget "
                    "for this advance_simulation call without needing your input on "
                    "anything -- it's been answering judgment calls on its own. "
                    f"{i} judgment call(s) already answered this way "
                    "so far this call (already reflected in the registry). Call "
                    "advance_simulation again with the same resume_token to keep the "
                    "simulation running from exactly where it left off, or stop here "
                    "if this is a reasonable checkpoint."
                )
                raise NeedsExternalInput(
                    prompt=checkin_prompt, responder="host", is_checkpoint=True, origin=request.origin
                )
            self.call_index += 1
            # No NeedsExternalInput here -- nothing external to wait on. Framed
            # the same way "host" is, since that's about how the model should behave.
            from story_simulator.keyed_subagent import call_keyed_subagent

            answer = await call_keyed_subagent(
                _frame_for_responder(request, "host"), session, origin=request.origin
            )
            self.answers.append(answer)
            return answer
        i, self.call_index = self.call_index, self.call_index + 1
        if i < len(self.answers):
            return self.answers[i]
        if responder in ("human", "subagent", "host"):
            raise NeedsExternalInput(
                prompt=_frame_for_responder(request, responder), responder=responder, origin=request.origin
            )
        raise ValueError(f"unknown responder {responder!r}")
