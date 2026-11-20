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

## Offense
- An entity releases stored energy into a body part, which moves at
  v = √(2·energy/mass) using the part's **actual** mass (no effective-mass factor).
- Charging time for a release = energy / P.

## Movement
- Launch: whole body starts with KE = released stored energy.
- While moving, P is added continuously as kinetic energy:
  ½mv² = E_launch + P·t. No speed cap, no friction or drag (deliberately
  unrealistic over long distances; revisit if it matters).
- Position: x(t) = (m / 3P)·[u(t)^1.5 − u0^1.5], u = v².

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
- Power budget: can P recharge stored energy while also powering movement?
  Proposed: P is one budget split between movement and recharging
  (TDTFB's first move assumed this).
- Turning while moving: cost of changing direction (rotate velocity at
  constant KE? or must the old component be cancelled with energy?).
- Collision resolution: what happens when the bodies meet (who deposits
  what into whom; momentum vs energy).
- Does the 0.5 s pre-launch charge (300 J at 600 W) count, and is it visible?
