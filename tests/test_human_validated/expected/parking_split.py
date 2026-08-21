"""Known-correct final state for tests/data/scenarios/parking_split --
same first-come-first-served facts as tests/data/scenarios/parking (car_b
arrives first, car_c second, car_a last), but with each car's drive and
its parking decision split into two separate, pre-planned events.
"""

# alias -> a substring that must appear in that car's recorded
# location.value (see helpers._parked_at) -- not an exact string, since a
# live model's own phrasing of "parked in parking_spot_1" reasonably varies.
location = {
    "car_b": "parking_spot_1",
    "car_c": "parking_spot_2",
    "car_a": "street",
}

# alias -> expected event_state.value, once every drive/park event has resolved.
event_state = {
    "car_a_drive": "complete",
    "car_a_park": "complete",
    "car_b_drive": "complete",
    "car_b_park": "complete",
    "car_c_drive": "complete",
    "car_c_park": "complete",
}
