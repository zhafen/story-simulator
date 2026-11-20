# Combat rules (draft v0)

Energy-based combat, worked out by playing player vs. TDTFB by hand.
Reference data: `docs/research/aggregated_table.md`.

## Entity parameters

| Symbol | Meaning | Default (professional, 75 kg) |
|---|---|---|
| P | Power supply: rate energy is gathered | 600 W |
| E | Energy capacity: max stored energy (and so max single release) | 300 J |
| H | Binding energy: total absorbed impact energy that defeats the entity | 1500 J (= 5 × E) |
| t_r | Reaction time = polling period | 0.20 s |
| m | Body mass; body parts use actual segment masses | 75 kg |

Segment masses (75 kg body): hand+forearm 1.65 kg, whole arm 3.75 kg,
foot+shin 4.3 kg, whole leg 12 kg, head 6 kg, whole body 75 kg.

## Power and storage
- P **never drives motion directly**. It only fills the energy store, at P,
  continuously (including while moving), up to the cap E.
- Every action is paid for from the store.
- An entity idle at rest before its first poll has an empty store (as of v0).
- One action per turn; actions cannot be queued for later turns.

## Offense
- An entity releases stored energy into a body part, which moves at
  v = √(2·energy/mass) using the part's **actual** mass (no effective-mass factor).
- Charging time for a release = energy / P.

## Movement
- A release of energy E_r into whole-body motion adds a velocity change of
  magnitude Δv = √(2·E_r/m) in any chosen direction (vector addition to the
  current velocity). Pushing forward gains more than E_r of KE; slowing down or
  reversing costs effort (backward Δv removes KE). From rest this is just
  KE = E_r.
- Reachable region after one step Δt: a disk centred on the coasting position,
  radius Δv·Δt (full release on the edge, partial releases inside).
- No friction or drag: a moving body keeps its velocity until it spends
  energy again. No speed cap (deliberately unrealistic over long distances;
  revisit if it matters).

## Defense
- Every impact is **clean**: its full kinetic energy is deposited in the target.
- Absorbed energy accumulates; when it exceeds H the entity is defeated.
- Dodging/blocking costs energy and power like any other action.

## Time and perception
- Each entity polls its surroundings once every t_r and may act on that poll.
- Entities have unlimited real time to decide (simulation time is frozen while deciding).
- Two entities with equal t_r are offset by t_r/2, so turns alternate every t_r/2 = 0.1 s.
- An entity sees others' positions and velocities, not their stored energy.

## Open questions
- Collision resolution: what happens when the bodies meet (who deposits
  what into whom; momentum vs energy).
- Does the 0.5 s pre-launch charge (300 J at 600 W) count, and is it visible?
