# Combat design notes

Exploratory design direction (not settled rules). Rules in force: `rules.md`.

## 1. Calibrate for a casual game: one strong vs many weak
- The game is casual: it should not have the tension of always fighting
  someone at your own level.
- Calibrate around the player fighting **a number of significantly weaker
  combatants**, not two evenly matched professionals (the player-vs-TDTFB
  walkthrough so far assumed equal stats).

## 2. Canonical units (dimensional-analysis style)
- Express everything in canonical units per entity:
  - canonical **distance**
  - canonical **time**
  - canonical **energy**
  - canonical **mass**
  - possibly other canonical quantities later.
- The canonical **time scale** is shared by movement, reflexes (polling /
  reaction time) and other actions.
- **Energy** sets durability, together with the coefficient of restitution.

## 3. The exponent n acts as a second time scale
- With the power-law profile x = D·(t/T)^n, distance and time can be set
  independently of energy: n = (T/D)·√(2E/m) absorbs the mismatch.
- Interpretation: n effectively introduces a secondary time scale, the time
  over which most of the energy is actually acquired.
  - Note (worked out after the fact): kinetic energy grows as (t/T)^(2(n−1)), so
    half the final energy is gained in the last fraction 1 − 0.5^(1/(2(n−1)))
    of T. For the punch (n ≈ 5, T = 0.32 s), that is the last ~8%, ≈ 0.027 s.
- Consequences unknown. Keep in mind.

## 4. Character growth: decouple stats from their side effects
- If a character puts points into **speed**, energy rises too (E = ½mv²),
  so speed gains would also buy power for free.
- Possible fix: penalise by the energy that the speed gain would add, using
  the partial derivative ∂E/∂v = m·v, i.e. subtract ΔE ≈ m·v·Δv.
- Same idea for other coupled quantities.

## Working decisions from the profile exploration
- Strikes: power-law profile with n ≈ 5 (punch-calibrated) plus the leg
  swing correction (rigid rod pivoting at the hip: KE = ⅙·m·v_tip², i.e. ⅓ of leg mass).
- Whole-body movement: constant power (n = 1.5); one n does not carry over
  from strikes to steps.
