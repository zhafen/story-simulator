"""Known-correct final state for this directory's own scenario.yaml,
shared by both of test_scenario.py's tests: the connected-model-driven
test_resolves_correctly_via_host_responder and the keyed_subagent-driven
test_resolves_and_persists_via_keyed_subagent -- same scenario, same
known-correct outcome (car_b finishes first, car_c second, car_a third),
different responder answering each event's resolve/plan judgment call.
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
