# Encounter log: player vs. TDTFB

Rules: `rules.md` (draft v0). Coordinates: x along the player's initial
charge line (player starts at x = 0, TDTFB at x = 2.0 m); y perpendicular,
positive = TDTFB's left (the direction it dodged). Velocities in m/s.
"Stored" = energy held for release (cap 300 J). "Absorbed" = impact energy
taken so far (defeat at > 1500 J). KE = kinetic energy of whole-body motion.

## Setup
Both: 75 kg, ~1.7 m tall, P = 600 W, E = 300 J, H = 1500 J, t_r = 0.2 s.
Player charged 300 J before t = 0 (0.5 s at 600 W; not observed by TDTFB).
Turn order: player at t = 0, 0.2, 0.4 …; TDTFB at t = 0.1, 0.3, 0.5 ….

## History

### t = 0.0 s — player's turn
Action: player launches whole body at TDTFB with all 300 J stored; P → movement.

| Entity | Position (x, y) m | Velocity (vx, vy) | KE | Stored | Absorbed | P allocation |
|---|---|---|---|---|---|---|
| Player | (0.00, 0.00) | (2.83, 0) | 300 J | 0 J | 0 J | movement |
| TDTFB | (2.00, 0.00) | (0, 0) | 0 J | 300 J | 0 J | recharge (already full) |

### t = 0.1 s — TDTFB's turn (first poll)
Perceived: player 1.70 m away, closing at 3.1 m/s, accelerating.
Action: launches whole body sideways (+y) with 100 J; keeps 200 J in reserve;
P → sidestep movement. Plan: if the player follows, use reserve at t = 0.3/0.5
for a foot+shin side kick (200 J, 4.3 kg at 9.6 m/s) or an emergency block.

| Entity | Position (x, y) m | Velocity (vx, vy) | KE | Stored | Absorbed | P allocation |
|---|---|---|---|---|---|---|
| Player | (0.30, 0.00) | (3.10, 0) | 360 J | 0 J | 0 J | movement |
| TDTFB | (2.00, 0.00) | (0, 1.63) | 100 J | 200 J | 0 J | movement |

### t = 0.2 s — player's turn (pending)

| Entity | Position (x, y) m | Velocity (vx, vy) | KE | Stored | Absorbed | P allocation |
|---|---|---|---|---|---|---|
| Player | (0.62, 0.00) | (3.35, 0) | 420 J | 0 J | 0 J | movement |
| TDTFB | (2.00, 0.19) | (0, 2.07) | 160 J | 200 J | 0 J | movement |

Gap along x: 1.38 m. Projected contact if nothing changes: none —
TDTFB would be ~1.2 m off the line by t ≈ 0.57 s.
