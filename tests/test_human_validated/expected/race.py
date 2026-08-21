"""Known-correct final state for tests/data/scenarios/race, shared by both
the connected-model-driven test (test_race_placement_live.py) and the
keyed_subagent-driven one (test_race_placement_via_keyed_subagent.py) --
same scenario, same known-correct outcome (car_b finishes first, car_c
second, car_a third), different responder answering each event's
resolve/plan judgment call. See each test module's own docstring for why
the two are kept separate rather than one parametrized test.
"""

# alias -> expected race_placement.value (1-indexed finishing position).
race_placement = {"car_b": 1, "car_c": 2, "car_a": 3}

# alias -> expected event_state.value, once the whole race has resolved.
event_state = {
    "car_b_trip": "complete",
    "car_c_trip": "complete",
    "car_a_trip": "complete",
}
