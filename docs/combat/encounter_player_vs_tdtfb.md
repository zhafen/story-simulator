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

Rewound once: the first version of t = 0.1 used continuous power-to-motion
(superseded by rules v0 power/storage section); TDTFB's turn was replayed.

### t = 0.0 s — player's turn
Action: player launches whole body at TDTFB with all 300 J stored; then stores at 600 W.

| Entity | Position (x, y) m | Velocity (vx, vy) | KE | Stored | Absorbed |
|---|---|---|---|---|---|
| Player | (0.00, 0.00) | (2.83, 0) | 300 J | 0 J | 0 J |
| TDTFB | (2.00, 0.00) | (0, 0) | 0 J | 0 J | 0 J |

### t = 0.1 s — TDTFB's turn (first poll)
Perceived: player 1.72 m away, closing at 2.83 m/s.
Action: no physical action; begins storing energy, stays balanced to go either way.
Stated plan (not binding — no queued actions):
- t = 0.3 (120 J): if player has not sped up, sidestep across the line with ~90 J
  (1.55 m/s, ~0.6 m clear by contact), keep ~30 J; if sped up, sidestep with all 120 J (1.79 m/s).
- t = 0.5: if followed, second sidestep; if player is passing, release the
  store into a whole-arm or whole-leg strike to the flank (e.g. 150 J → arm at 8.9 m/s).

| Entity | Position (x, y) m | Velocity (vx, vy) | KE | Stored | Absorbed |
|---|---|---|---|---|---|
| Player | (0.28, 0.00) | (2.83, 0) | 300 J | 60 J | 0 J |
| TDTFB | (2.00, 0.00) | (0, 0) | 0 J | 0 J | 0 J |

### t = 0.2 s — player's turn
Perceived: TDTFB standing still, 1.43 m ahead.
Action: no physical action; keeps storing (does not want to just crash in).

| Entity | Position (x, y) m | Velocity (vx, vy) | KE | Stored | Absorbed |
|---|---|---|---|---|---|
| Player | (0.57, 0.00) | (2.83, 0) | 300 J | 120 J | 0 J |
| TDTFB | (2.00, 0.00) | (0, 0) | 0 J | 60 J | 0 J |

Gap: 1.43 m. Contact at current speed: t ≈ 0.71 s.

### t = 0.3 s — TDTFB's turn (pending)

| Entity | Position (x, y) m | Velocity (vx, vy) | KE | Stored | Absorbed |
|---|---|---|---|---|---|
| Player | (0.85, 0.00) | (2.83, 0) | 300 J | 180 J | 0 J |
| TDTFB | (2.00, 0.00) | (0, 0) | 0 J | 120 J | 0 J |

Gap: 1.15 m. Contact at current speed: t ≈ 0.71 s (0.41 s away).
