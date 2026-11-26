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
Action: releases the 120 J stored into forward motion toward TDTFB-1 (+x),
delivered at constant power (6000 W) from rest over 0.02–0.04 s. The store
keeps refilling at 6000 W during the movement.

### t = 0.04 s — player's turn
Action: releases the 120 J saved during the last movement into more forward
motion, again at constant power, over 0.04–0.06 s.

| Entity | Position (x, y) | Velocity | KE | Stored | Absorbed |
|---|---|---|---|---|---|
| Player | (0.024, 0.00) | (1.79, 0) | 120 J | 120 J | 0 J |
| TDTFB-1 | (3.00, 0.00) | (0, 0) | 0 J | 24 J | 0 J |
| TDTFB-2 | (2.30, 1.93) | (0, 0) | 0 J | 24 J | 0 J |
| TDTFB-3 | (2.30, −1.93) | (0, 0) | 0 J | 24 J | 0 J |

### t = 0.06 s — player's turn (pending)

| Entity | Position (x, y) | Velocity | KE | Stored | Absorbed |
|---|---|---|---|---|---|
| Player | (0.068, 0.00) | (2.53, 0) | 240 J | 120 J | 0 J |
| TDTFB-1 | (3.00, 0.00) | (0, 0) | 0 J | 36 J | 0 J |
| TDTFB-2 | (2.30, 1.93) | (0, 0) | 0 J | 36 J | 0 J |
| TDTFB-3 | (2.30, −1.93) | (0, 0) | 0 J | 36 J | 0 J |
