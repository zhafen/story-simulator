"""Known-correct final state for tests/data/scenarios/race, shared by both
the connected-model-driven "race" case in test_scenario_resolution.py and
the keyed_subagent-driven test_race_placement_via_keyed_subagent.py --
same scenario, same known-correct outcome (car_b finishes first, car_c
second, car_a third), different responder answering each event's
resolve/plan judgment call. See test_race_placement_via_keyed_subagent.py's
own docstring for why it's kept as a separate test rather than folded into
test_scenario_resolution.py's own parametrization (a different axis --
which responder answers, not which scenario runs).
"""

# alias -> expected race_placement.value (1-indexed finishing position).
race_placement = {"car_b": 1, "car_c": 2, "car_a": 3}

# alias -> expected event_state.value, once the whole race has resolved.
event_state = {
    "car_b_trip": "complete",
    "car_c_trip": "complete",
    "car_a_trip": "complete",
}

# Order evidence: each car's race_placement write should be time-stamped
# with its own trip event's end_time (world time -- see
# core._next_time_stamp), confirming it was recorded while that car's own
# event resolved, not retroactively or out of turn.
write_order = {
    "component_type": "race_placement",
    "times": {"car_b": 1020, "car_c": 1080, "car_a": 1800},
}
