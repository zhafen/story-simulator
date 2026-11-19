# Force → impulse (momentum) → energy conversions

Impulse J = ∫F dt. Using **peak** force with a half-sine pulse: J = (2/π)·F_peak·t
(a rectangle would give F·t; a triangle 0.5·F·t, so ±30% from pulse shape alone).
Energy E = J²/(2m), or E = J·v/2 when striker speed v is measured (then m = J/v).
E is the striker kinetic energy needed to deliver J if fully stopped, **not** the
energy absorbed by the target (which is smaller: rebound, target motion, padding).

Contact times: 14 ms gloved punch (Atha 1985: 14 ms; Bartsch 2009: 13.6 ms, measured);
others **assumed** (10–15 ms). E ∝ t², so treat energies as ±2×.

## Strikes

| Strike | F_peak (N) | t (ms) | J (N·s = kg·m/s) | m_eff (kg) | E (J) |
|---|---|---|---|---|---|
| Olympic straight (Walilko) | 3427 | 14 | 30.5 | 3.3 (=J/v) | 140 |
| Atha pro punch | 4096 | 14 | 36.5 | 4.1 (=J/v) | 162 |
| Hook (Viano) | 4405 | 14 | 39.3 | 3.6 (=J/v) | 216 |
| Hook, pendulum (Bartsch) | 4289 | 13.6 | 37.1 | 2.9 (assumed) | 238 |
| Rear punch elite / int. / novice (Smith) | 4800 / 3722 / 2381 | 14 | 42.8 / 33.2 / 21.2 | 2.9 / 2.0 / 1.3 (assumed) | 316 / 275 / 173 |
| Lead punch elite / int. / novice | 2847 / 2283 / 1604 | 14 | 25.4 / 20.3 / 14.3 | 2.9 / 2.0 / 1.3 | 111 / 104 / 79 |
| In-fight punch (pro bouts) | 870–1150 | 14 | 7.8–10.2 | 2.9 | 10–18 |
| Karate front kick | 1082–1208 | 15 | 10.3–11.5 | 1.1–1.3 (=J/v, v≈9) | 46–52 |
| TKD roundhouse / back kick | 8252 / 8023 | 10 | 52.5 / 51.1 | 3.5 (assumed) | 394 / 373 |
| Muay Thai knee / cross (wall bag) | 9482 / 5009 | 15 | 90.5 / 47.8 | 5.0 / 2.9 (assumed) | 820 / 394 |
| MMA ground elbow | 4500 | 10 | 28.6 | 2.0 (assumed) | 205 |

Sanity check: Walilko J = 30.5 N·s vs m·v = 2.9×9.14 = 26.5 kg·m/s; E 140 J vs ½mv² = 121 J — consistent.
Inconsistencies: Smith elite rear (316 J) implies v ≈ 15 m/s, too fast → real contact likely ~10 ms (→ ~160 J).
Karate front-kick force implies m_eff ≈ 1.2 kg vs 3.5 kg from measured KE (124–156 J) → different
targets/instruments; force data from padded targets understate J. Wall-bag numbers (knee, cross) likely
overstate vs a head.

## Injury thresholds (force → impulse needed → striker KE for a 2.9 kg fist-like impactor)

| Threshold | F (N) | J @ 3 ms (bare/hard) | E @ 3 ms | J @ 14 ms (gloved) | E @ 14 ms |
|---|---|---|---|---|---|
| Skull, impact | 11900 | 22.7 | 89 | 106 | 1939 |
| Skull, quasi-static | 6400 | 12.2 | 26 | 57 | 561 |
| Temporoparietal (5 cm²) | 5000 | 9.5 | 16 | 45 | 342 |
| Nasal 50% | 650 | 1.2 | 0.3 | 5.8 | 6 |
| Zygoma | 1450 | 2.8 | 1.3 | 12.9 | 29 |
| Mandible | 3700 | 7.1 | 9 | 33 | 187 |
| Distal radius | 2400 | 4.6 | 4 | 21 | 79 |
| Tibia | 4900 | 9.4 | 15 | 44 | 329 |
| Femur axial | 10000 | 19.1 | 63 | 89 | 1370 |
| Chest, ~4 rib fractures | 6000 | 11.5 | 23 | 54 | 493 |
| Chest, extensive fractures | 8200 | 15.7 | 42 | 73 | 921 |
| Scalp laceration | 4000 | 7.6 | 10 | 36 | 219 |

Takeaway: bone thresholds are **force** (stress) limits; the momentum/energy needed to reach them grows with
contact time (padding). At hard-contact times (~3 ms) the derived energies land near the directly measured
fracture energies (skull 28–34 J absorbed; femur 549 J), which is the regime that matters for bare strikes.
Gloves (14 ms) raise the required striker energy ~20× — why gloved punches rarely fracture skulls.
