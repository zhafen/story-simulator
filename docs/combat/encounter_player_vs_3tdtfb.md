# Encounter log: player vs. 3 × TDTFB

Rules: `rules.md` (v0 + v1 working assumptions). Coordinates in metres,
player starts at the origin. Earlier 1-vs-1 encounter: `encounter_player_vs_tdtfb.md`.

## Setup

| Entity | P | E (cap) | H | t_r | Mass |
|---|---|---|---|---|---|
| Player | 6000 W | 3000 J | 15000 J | 0.02 s | 75 kg |
| TDTFB-1, -2, -3 | 600 W | 300 J | 1500 J | 0.2 s | 75 kg |

All entities start at rest with empty stores and poll for the first time at
t = 0. Player polls every 0.02 s; TDTFBs every 0.2 s (so all four coincide
every 0.2 s). Each TDTFB was played by an independent agent.

## History

### t = 0.00 s — everyone's first poll (simultaneous)
Player: no action possible (store empty).
TDTFB-1, -2, -3: no action (store empty); each holds position.

| Entity | Position (x, y) | Velocity | KE | Stored | Absorbed |
|---|---|---|---|---|---|
| Player | (0.00, 0.00) | (0, 0) | 0 J | 0 J | 0 J |
| TDTFB-1 | (3.00, 0.00) | (0, 0) | 0 J | 0 J | 0 J |
| TDTFB-2 | (2.30, 1.93) | (0, 0) | 0 J | 0 J | 0 J |
| TDTFB-3 | (2.30, −1.93) | (0, 0) | 0 J | 0 J | 0 J |

### t = 0.02 s — player's turn
Action: launches toward TDTFB-1 (+x) with a constant-power profile: the 120 J
stored is released as initial KE, then P = 6000 W goes into forward motion
(store does not fill while P drives movement). KE(τ) = 120 J + 6000 W·τ.
Projection if unchanged: x = 0.73 m, 5.7 m/s, 1200 J at t = 0.2 s; reaches
body contact with TDTFB-1 (x = 2.55 m) at t ≈ 0.45 s, 8.5 m/s, ~2700 J.

### t = 0.04 s — player's turn (pending)

| Entity | Position (x, y) | Velocity | KE | Stored | Absorbed |
|---|---|---|---|---|---|
| Player | (0.04, 0.00) | (2.53, 0) | 240 J | 0 J | 0 J |
| TDTFB-1 | (3.00, 0.00) | (0, 0) | 0 J | 24 J | 0 J |
| TDTFB-2 | (2.30, 1.93) | (0, 0) | 0 J | 24 J | 0 J |
| TDTFB-3 | (2.30, −1.93) | (0, 0) | 0 J | 24 J | 0 J |
