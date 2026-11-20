# Collision energy partition: deformation/damage vs. post-impact kinetic energy

**Question.** When body 1 (striker) hits body 2 (target), how much of the impact energy
goes into deformation and damage, and how much stays as kinetic energy (target knocked
back, striker rebounds)? How can the post-collision kinetic energies, and so the damage
energy, be predicted from the masses and velocities before impact?

**Short answer.** Use momentum conservation plus a coefficient of restitution *e*.
Only the kinetic energy in the centre-of-mass frame, ½·μ·v_rel², can ever be dissipated,
where μ is the reduced mass. The fraction (1−e²) of it is lost to deformation, heat and
damage. Everything else stays as kinetic energy. For a light striker hitting a heavy target,
μ ≈ m_striker, so almost all of the striker's kinetic energy is available to cause damage.
For equal masses, only half of a moving striker's kinetic energy is available. The hard
parameter is not *e*, which is roughly 0–0.4 for flesh-on-flesh, flesh-on-wall and
vehicle crashes. It is the **effective mass** of each body at the contact point over the
short (~10–20 ms) contact duration.

**Sourcing caveat.** The sandbox blocked full-text fetches from pmc.ncbi.nlm.nih.gov,
bjsm.bmj.com, arxiv.org, core.ac.uk and en.wikipedia.org. Every literature number below
comes from search-result abstracts or snippets, and the cited URL is the page the snippet
came from. Values marked **[derived]** are my own calculations from cited numbers.
Values marked **[std]** are textbook mechanics with no fetched source. Values marked
**[judgment]** are design choices, not measurements.

---

## 1. Core mechanics

### 1.1 Two-body central (normal) impact

Notation: m1 and m2 are the masses (or effective masses) at the contact point, along the
contact normal. u1 and u2 are pre-impact normal velocities. v_rel = u1 − u2 is the
closing speed.

- Momentum: m1·u1 + m2·u2 = m1·v1 + m2·v2
- Restitution (Newton): v2 − v1 = e·(u1 − u2), with 0 ≤ e ≤ 1
- Reduced mass: μ = m1·m2/(m1+m2)
- Centre-of-mass velocity: v_cm = (m1·u1 + m2·u2)/(m1+m2). This is unchanged by the impact.
- Post-impact velocities:
  - v1 = v_cm − e·(m2/(m1+m2))·v_rel
  - v2 = v_cm + e·(m1/(m1+m2))·v_rel
- Velocity changes (delta-V):
  - Δv1 = −(1+e)·(μ/m1)·v_rel
  - Δv2 = +(1+e)·(μ/m2)·v_rel
  - The impulse is J = (1+e)·μ·v_rel.
- Energy split [std]:
  - KE_before = ½(m1+m2)·v_cm² + ½·μ·v_rel². The first term is the centre-of-mass motion
    and can never be lost. The second is the relative motion and is the only part
    available to lose.
  - **ΔE_loss = ½·μ·v_rel²·(1 − e²)**. This is deformation, heat, damage and sound.
  - KE_after = ½(m1+m2)·v_cm² + e²·½·μ·v_rel²

| Quantity | Value / range | Units | Method | Source URL |
|---|---|---|---|---|
| Two-body effective mass m_eff = (1/m_a + 1/m_b)⁻¹ | — | kg | Rigid-body collision response | https://euclideanspace.com/physics/dynamics/collision/index.htm |
| Normal restitution + tangential impulse ratio as Brach's two planar-impact coefficients; energy loss split into normal (crush) and tangential parts | — | — | Planar impact mechanics (vehicle) | https://saemobilus.sae.org/content/2007-01-0737 |
| Impulse-momentum energy-loss estimates vs. measured (RICSAC crash tests) | −33 % to 0 % (consistently low) | % | Brach 1987, crash tests | https://saemobilus.sae.org/papers/energy-loss-vehicle-collisions-871993 |
| Planar impact equations rederived in centre-of-mass frame; energy-loss scale factors vs impulse ratio | — | — | Scurlock & Ipser 2014 | https://arxiv.org/pdf/1404.0250 |

**Fraction of the striker's kinetic energy available for damage** when the target is
initially at rest [derived from the formulas above]:

    f_avail = ½μv²/(½m1v²) = m2/(m1+m2)
    f_damage = (1−e²)·m2/(m1+m2)

| m2/m1 | f_avail | f_damage at e = 0.2 | Target KE / striker KE = (1+e)²·m1·m2/(m1+m2)² at e = 0.2 |
|---|---|---|---|
| 0.5 | 0.33 | 0.32 | 0.32 |
| 1 | 0.50 | 0.48 | 0.36 |
| 2 | 0.67 | 0.64 | 0.32 |
| 5 | 0.83 | 0.80 | 0.20 |
| 20 | 0.95 | 0.91 | 0.065 |
| ∞ (wall) | 1.00 | 0.96 | 0 |

Consequence: a light, fast striker against a heavy target converts almost all of its
kinetic energy into damage. The kinetic energy imparted to the target (knockback) peaks
when the two masses are equal. So knockback energy and damage energy are not
proportional to each other.

### 1.2 Effective (apparent) mass at the contact point

A body that can rotate, or that is a chain of segments joined by compliant joints,
presents a smaller mass at the contact point than its total mass.

- Single rigid body [std], with r⊥ the moment arm of the contact normal about the centre
  of mass:

      1/m_eff = 1/m + r⊥²/I_cm

  Check: a uniform rod struck at its end, perpendicular to the rod, gives m_eff = M/4.
  The patent gives this as m_eff = M/(1+L²/ρg²), with ρg the radius of gyration
  (https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7367212).
- Contact-point effective inertia M_c in the rigid-body impact equations: the same
  quantity in matrix form (https://arxiv.org/pdf/1710.05947).
- Articulated humans: during a 10–20 ms strike, the target's effective mass is roughly
  the struck segment plus whatever is stiffly coupled to it through the neck or joints.
  It is not the whole body. The striker's effective mass is the fist plus part of the
  arm and trunk, depending on technique.

| Quantity | Value / range | Units | Method | Source URL |
|---|---|---|---|---|
| Rod-end effective mass | M/4 | kg | Rigid-body formula | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7367212 |
| Racket effective mass < static mass | — | — | Patent model | (same search; racket patent 11173362) https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11173362 |
| Effective punch mass, Olympic straight punch | 2.9 ± 2.0 | kg | Hybrid III and high-speed video, momentum/equilibrium | https://pubmed.ncbi.nlm.nih.gov/16183766/ |
| Effective mass, definition F_peak/a_fist (different definition) | 31.2 ± 16.2 (cross); 30.4 ± 15.1 (jab) | kg | Kacprzak et al. 2025, Appl. Sci. 15:4008 | https://mdpi.com/2076-3417/15/7/4008 |
| Effective fist mass derived from Smith & Hamill heavy-bag momentum | ~4.1 | kg | Bag momentum / fist velocity | https://ojs.ub.uni-konstanz.de/cpa/article/view/1470/1328 |
| Effective mass range by technique | fist mass up to fist + forearm + upper arm + trunk | — | Review | https://www.sponet.de/sponet/Record/4034356?lng=en |

The ~30 kg "effective mass" values (F/a) are not comparable to the ~3 kg momentum-based
values. Lenetsky (sponet record above) notes that punching adds force during contact,
which inflates any effective-mass estimate. For momentum and energy bookkeeping, use the
momentum-based value of about 3–4 kg.

### 1.3 Oblique impacts

Resolve the closing velocity into a normal part v_n and a tangential part v_t.

- Apply *e* to the normal component only.
- Tangential impulse J_t = clamp(−μ_t-required, ±μ_f·J_n). Brach's "impulse ratio"
  formulation (https://saemobilus.sae.org/content/2007-01-0737) works this way. Sliding
  occurs if the required ratio exceeds the friction coefficient μ_f; otherwise the
  contact sticks and the tangential relative velocity ends at zero.
- Tangential energy loss is at most ½·μ·v_t² if the contact sticks. If it slides, the loss
  is μ_f·J_n times the sliding distance [std].
- For game purposes [judgment]: glancing blows count only v_n for damage. Add a
  tangential-loss term only if the game needs grazing or abrasion damage.
- Vehicle-crash practice partitions residual crush energy into normal and tangential
  losses (https://saemobilus.sae.org/content/2007-01-0737).

---

## 2. Vehicle crash reconstruction

### 2.1 Methods

- **Momentum-based reconstruction.** Combine momentum conservation with the energy
  dissipated as crush to solve for closing speed and delta-V
  (https://core.ac.uk/download/216390982.pdf). In practice:
  - E_crush = ½·μ·v_rel²·(1−e²)
  - so v_rel = √(2·E_crush/(μ(1−e²)))
  - then ΔV_i = (1+e)·(μ/m_i)·v_rel
- **Crush energy (Campbell / CRASH3).** Force per unit width is linear in residual crush
  C: F/w = A + B·C. Then:
  - E_crush = ∫ (A·C + B·C²/2 + G) dw, with G = A²/(2B) [std CRASH3 form]
  - Campbell's b0 is the no-damage speed, the intercept of the barrier-speed vs. crush
    line. b1 is the slope.
  - Barrier-equivalent velocity: BEV = √((C + A/B)·W_C·B/m)
  - Sources: https://www.arxiv.org/pdf/1408.4614 and https://journal.nafe.org/ojs/index.php/nafe/article/download/519/489/1494
  - Critique: the energy formulation includes extraneous A/G terms
    (https://www.arxiv.org/pdf/1408.4614).
  - Generic stiffness categories cause inaccuracy
    (https://core.ac.uk/download/216390982.pdf).
- **EES (energy equivalent speed)** = √(2·E_crush/m). This is the speed into a rigid
  barrier, with no rebound, that would produce the same crush energy [std].
- **WinSMASH and CRASH-family tools** assume e = 0. Adding restitution improved frontal
  delta-V estimates to within ~1% (PMC review via search,
  https://pmc.ncbi.nlm.nih.gov/articles/PMC3217484).

### 2.2 Restitution vs. closing speed

| Quantity | Value / range | Units | Method | Source URL |
|---|---|---|---|---|
| e, vehicle-to-vehicle bumper impacts, ΔV 2–5 mph | 0.2–0.4 (clustered) | — | Staged low-speed crashes (Howard 1993) | https://saemobilus.sae.org/papers/vehicle-restitution-response-low-velocity-collisions-931842 |
| Closing-speed range studied for e(v) | 0.8–5.4 | m/s | 30 low-speed collisions (Cipriani 2002) | https://saemobilus.sae.org/content/2002-01-0540 |
| e correlation for bumper impacts | correlation exists vs closing speed; barrier data too scattered for a fit | — | Antonetti 1998 | https://saemobilus.sae.org/content/980552 |
| Empirical fit (patent, from Howard data) | e = 0.1 + 0.9·exp(−0.34·V_c[mph]); e→1 at 0, floor 0.1 | — | Regression (secondary source) | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7197444 |
| e vs speed, frontal barrier | generally decreases with speed; slight rise and then fall for some engine layouts | — | NHTSA crash tests (Monson & Germane 1999) | https://saemobilus.sae.org/papers/determination-mechanisms-motor-vehicle-structural-restitution-crash-test-data-1999-01-0097 |
| e at high-severity full-frontal barrier | → ~0 | — | 47 NHTSA vehicles (Wood model) | https://saemobilus.sae.org/papers/structural-rebound-characteristics-car-population-frontal-impacts-2000-01-0461 |
| e, >100 modern vehicle-to-barrier tests | analysed vs weight, wheelbase, bumper | — | Olberding 2023 | https://saemobilus.sae.org/papers/coefficient-restitution-collision-pulse-duration-low-speed-vehicle-barrier-impacts-2023-01-0624 |

Evaluating the patent fit [derived]:

| V_c (mph) | V_c (m/s) | e |
|---|---|---|
| 2 | 0.9 | 0.55 |
| 5 | 2.2 | 0.26 |
| 10 | 4.5 | 0.13 |
| 30 | 13.4 | 0.10 (floor) |

### 2.3 How much closing kinetic energy becomes crush

From §1.1, the crush fraction of the *relative* kinetic energy is (1−e²):

| e | Crush fraction of ½μv_rel² |
|---|---|
| 0.4 (low speed) | 84 % |
| 0.2 | 96 % |
| 0.1 (≥ 30 mph) | 99 % |

The fraction of the *total* kinetic energy that becomes crush also depends on the mass
ratio and the frame of reference. Two examples:

- Equal masses meeting head-on at equal and opposite speeds: v_cm = 0, so ~all kinetic
  energy is crush at high speed.
- Car into a parked car of equal mass: at most 50% of the kinetic energy becomes crush.

### 2.4 Delta-V as the injury predictor

- Delta-V, not crush energy, is the usual severity proxy. Energy scales with v² and
  momentum with v.
- Severe injuries can occur with little crush, and minor injuries with large crush
  (AAFS abstract, https://www.aafs.org/sites/default/files/media/documents/AAFS-2013-C22.pdf).
- Delta-V combined with the mean and peak acceleration (pulse duration) drives injury
  potential (same search set; https://saemobilus.sae.org/papers/relationship-delta-v-injury-933111).
- Lesson for the game: damage to *occupants* (the "brain inside the head") follows Δv
  and pulse duration. Damage to *structure* (crush, fracture of the struck surface)
  follows the dissipated energy ΔE.

---

## 3. Human-body impacts

### 3.1 Strikes on instrumented targets

| Quantity | Value / range | Units | Method | Source URL |
|---|---|---|---|---|
| Olympic straight punch: hand velocity / effective mass / force | 9.14 ± 2.06 / 2.9 ± 2.0 / 3427 ± 811 | m/s / kg / N | Hybrid III frangible face, video, equilibrium | https://pubmed.ncbi.nlm.nih.gov/16183766/ |
| Same punches: head translational / rotational accel.; neck shear | 58 g; 6343 rad/s²; 994 N | — | same | https://pubmed.ncbi.nlm.nih.gov/16183766/ |
| Fist KE at contact (mean values) | ½·2.9·9.14² ≈ 121 | J | [derived] | from above |
| Walilko "energy transfer" | 17.2 (unit not visible in snippet; presumably J) | J? | Hybrid III | https://www.semanticscholar.org/paper/Biomechanics-of-the-head-for-Olympic-boxer-punches-Walilko-Viano/edbd929ed7812c983b4780fc106ecdf716b58a30 (via sibling report b3_strike_energies.md; full text blocked) |
| Walilko punch power | 6574 ± 3453 | W | same | same (via b3_strike_energies.md) |
| Atha 1985 pro heavyweight punch | 8.9 m/s; 4096 N peak in 14 ms; 53 g target head; "equated to 6320 N on a human head" | — | Ballistic-pendulum padded target, single subject | https://pubmed.ncbi.nlm.nih.gov/3936571/ |
| Heavy-bag momentum | gloves > bare/karate; higher skill → more bag momentum at same fist speed (attributed to effective mass) | — | High-speed film (Smith & Hamill) | https://ojs.ub.uni-konstanz.de/cpa/article/view/1470/1328 |
| Same protocol (P. Smith): skill did not raise bag momentum in karate | — | — | replication | https://ojs.ub.uni-konstanz.de/cpa/article/view/1519/1424 |
| NFL concussive helmet impacts: impact speed / struck head ΔV | 9.3 ± 1.9 / 7.2 ± 1.8 | m/s | Video reconstruction + Hybrid III lab replay | https://link.springer.com/doi/10.1007/1-4020-3796-1_12 |

**Energy-partition check on Walilko [derived; full text not read].** The fist kinetic energy
is ≈121 J and the reported energy transfer is ≈17 J, so 14% of the fist kinetic energy
ends up as target kinetic energy. Under the §1.1 model, target KE / striker KE =
(1+e)²·m1·m2/(m1+m2)². With m1 = 2.9 kg:

| e | Implied target effective mass m2 |
|---|---|
| 0 | ≈ 18 kg |
| 0.2 | ≈ 23 kg |

That is much more than the ~4.5 kg dummy head alone, which is consistent with the head
being coupled through the neck to the torso during the contact. The rest of the energy,
≈ 121 − 17 − (fist rebound KE, a few J) ≈ 100 J, or ~80%, is dissipated in the glove,
the frangible face, the neck and the hand. **This is the best available anchor for "how
much of a punch moves the target vs. deforms it": roughly 15% moves it and 80–85% is
dissipated.** Treat it as unverified until the full text is read. It is unclear whether
"energy transfer" in the paper means head kinetic energy or work done.

**NFL check [derived].** A head ΔV of 7.2 m/s at a 9.3 m/s closing speed gives
ΔV/v_rel = 0.77 = (1+e)·m1/(m1+m2). For equal effective masses this would need
e ≈ 0.55. For a striker with greater effective mass (torso-driven, head-down tackle) and
e ≈ 0.2–0.3, m1/m2 ≈ 1.6–1.8. Helmets are padded shells, so this does not transfer to
bare strikes.

### 3.2 Pedestrian impacts (vehicle ≫ pedestrian)

- **Trajectories.**
  - Forward projection: the pedestrian's centre of gravity is below the vehicle's leading
    edge, and the pedestrian is pushed ahead of it.
  - Wrap: the pedestrian folds over the bonnet, usually with the vehicle braking.
  - Source: https://arxiv.org/pdf/0803.2402
- **Launch speed vs. impact speed.**
  - Forward-projection "efficiency" is ~100%. The pedestrian is accelerated to "nearly
    equal or less than" the vehicle impact speed (Toor, cited in
    https://www.jsheld.com/uploads/Pedestrian-Impact-Analysis-of-Side-Swipe-and-Minor-Overlap-Conditions.pdf).
  - For wrap, a launch factor η ≈ 0.9 is used in a worked example
    (https://arxiv.org/pdf/0803.2402).
  - With m_vehicle ≫ m_ped, μ ≈ m_ped. Momentum theory gives v_ped = (1+e)·v_car, so
    η ≤ 1 implies e ≈ 0 for vehicle-pedestrian impacts [derived]. The pedestrian sticks
    to the vehicle and does not bounce off it.
- **Searle throw formula** (SAE 930659; form [std], derivation in
  https://arxiv.org/pdf/0803.2402):

      v = √(2μ_f·g·s) / (cosθ + μ_f·sinθ)

  The minimum over θ is v_min = √(2μ_f·g·s/(1+μ_f²)). Searle says the vehicle speed
  is ~20% higher than this (https://saemobilus.sae.org/content/930659/, via search
  snippet).
- **Worked example.** Launch 11.85 m/s for a 16 m throw (η = 0.9); minimum launch speed
  11.45 m/s at 30.96° (https://arxiv.org/pdf/0803.2402).
- **Energy partition [derived].** With e ≈ 0 and m_car ≫ m_ped, the pedestrian receives
  ½·m_ped·v_car², and roughly the same amount, ½μv² ≈ ½·m_ped·v_car², is dissipated in
  the contact. Splitting the work into "deformation" and "kinetic" gives about 50/50 of
  2× the pedestrian's final kinetic energy. Most of the pedestrian's later kinetic energy
  is lost in ground sliding and tumbling, which is a separate, often injurious, impact.

### 3.3 Restitution values on human or surrogate targets

| Contact | e | Method | Source URL |
|---|---|---|---|
| Football (ball) on head-like force plate | 0.7 ± 0.11 (cf. 0.8 Townend; 0.8 Schneider & Zernicke) | Pendulum heading, 3.6–4.1 m/s; ball restitution dominates | https://ojs.ub.uni-konstanz.de/cpa/article/view/3900/3617 |
| Gel padding effect on ball COR | −21.7 % | Drop test | https://libmast.utm.my/Record/UMPir5533/Description |
| Vehicle-pedestrian | ≈ 0 [derived from η ≤ 1] | Reconstruction | https://arxiv.org/pdf/0803.2402 |
| Head-surface COR used to infer peak head velocity (Viano & Parenteau) | value not in snippet | Cadaver | https://arxiv.org/pdf/2608.15418 |
| Fist on head/torso; foot on torso; body on wall | **No direct measurement found.** Inferred 0–0.3 from the Walilko partition above, plus soft-tissue damping studies (pendulum on deltoid: stiffness and damping depend strongly on striker mass) | — | https://digitalcommons.unl.edu/imsediss/8 ; https://journals.ku.edu.kw/jer/index.php/JER/article/view/181 |

- Soft-tissue "wobbling mass" dissipates large amounts of energy. Examples: thigh up to
  <50 J horizontal per running impact; heel pad and shank damping
  (https://www.ncbi.nlm.nih.gov/pubmed/11182123 ;
  https://www.lboro.ac.uk/microsites/ssehs/biomechanics/impact/soft-tissue-motion.html).
- This supports low *e* for flesh. Elastic rebound of a muscular target is small next to
  viscous loss.

---

## 4. Rate and stiffness effects: is a fixed e reasonable?

| Regime | Law | Source URL |
|---|---|---|
| Low speed, viscoelastic | 1 − e ∝ v^(1/5) | https://ar5iv.labs.arxiv.org/html/cond-mat/0312005 |
| Above yield (plastic) | e ∝ v^(−1/4); e ≈ 1.18·(v/v_y)^(−1/4) for v > v_y (Johnson) | https://arxiv.org/pdf/cond-mat/0209490 ; https://ar5iv.labs.arxiv.org/html/cond-mat/0312005 |
| Plastic onset (metals) | ~5 m/s (v_0 = 0.3 m/s for steel spheres in another model) | same |
| Non-monotonic e(v) observed | yes | https://arxiv.org/pdf/cond-mat/0209490 |
| Vehicles | e falls from ~0.5 near 1 m/s to ~0.1 by 13 m/s; ~0 at high severity | §2.2 |
| e generally decreases with velocity (head-impact context) | — | https://arxiv.org/pdf/2608.15418 |

**Verdict.**

- For a game, a fixed e per material pair is adequate. Damage energy goes as (1−e²), so
  errors in e are damped: e = 0.1 vs 0.3 changes damage energy by only 8%. Knockback
  velocity goes as (1+e), so the same error changes it by ±18%.
- The effective-mass assumption shifts results far more than e does.
- If speed dependence is wanted cheaply, use e(v) = e_min + (e_0 − e_min)·exp(−v/v_c).
  This is the patent's vehicle form, with e_0 ≈ 0.5, e_min ≈ 0.1 and v_c ≈ 3 m/s for
  flesh and padding [judgment].
- Bone and armour may be locally stiffer (higher e) until they fracture. Fracture is
  a plastic event, which drives e toward 0. For a game this is a reason to model e as
  low once a damage threshold is exceeded, not to raise it.

---

## Suggested game rule

**Inputs**

- m_a: attacker effective mass, the striking part
  - fist ≈ 3 kg, 1–5 kg by technique
  - kick ≈ 3.5 kg
  - knee ≈ 5 kg
  - weapons: use the rigid-body formula 1/m_eff = 1/m + r⊥²/I
- m_d: defender's whole mass
- v: relative closing speed along the contact normal (m/s)
- defender state: free, braced, or against a wall

**Step 1 — defender effective mass M** [judgment, calibrated loosely to the Walilko
partition in §3.1]

| Defender state | M | Rationale |
|---|---|---|
| Free-standing, head strike | ≈ 0.25·m_d (≈ 18 kg for 75 kg) | Head + neck + part of torso coupled during a ~15 ms contact; matches the ~14% Walilko energy transfer |
| Free-standing, torso strike | ≈ 0.5·m_d | Torso is most of the mass and stiffly connected |
| Free-standing, whole-body shove or tackle (long contact > 100 ms) | m_d | Full coupling |
| Braced on ground | M_free × 2, plus the ground absorbs knockback up to a friction limit μ_f·m_d·g·t_contact; knockback beyond the limit slides or staggers | Feet couple the body to the Earth; partial |
| Against a wall | ∞ (μ = m_a) | Wall supplies the reaction; no knockback |

**Step 2 — collision**

- μ = m_a·M/(m_a+M); for a wall, μ = m_a.
- **E_damage = ½·μ·v²·(1 − e²)**. Split this between attacker and defender in
  proportion to compliance; default 100% to the defender for a fist on flesh, and some
  to the attacker for a fist on a wall.
- **Defender knockback velocity: Δv_d = (1+e)·m_a·v/(m_a + M)**.
  - Optionally convert to whole-body velocity by momentum: v_body = J/m_d, where
    J = (1+e)·μ·v. Use this for stagger and throw distance.
  - The head-level Δv_d over the contact is what drives concussion (§2.4).
- **Attacker rebound: Δv_a = −(1+e)·M·v/(m_a + M)**. A strike attached to a body ends
  with its velocity reversed by e·v approximately when M ≫ m_a.
- Wall case: Δv_a = −(1+e)·v and E_damage = ½·m_a·v²·(1−e²). This all lands in the
  attacker's fist (or the wall), so punching a wall is self-damage.
- Defender thrown into a wall: run the same rule with the defender as the striker,
  m_a = m_d, M = ∞.

**Recommended e**

| Contact | e (default) | Range | Basis |
|---|---|---|---|
| Fist, foot or knee on human, bare | 0.2 | 0.0–0.4 | Walilko partition; soft-tissue damping; vehicle analogy at ~10 m/s |
| Gloved or padded strike on human | 0.3 | 0.2–0.5 | Padding stores and returns more energy elastically (ball COR 0.7–0.8 is the high limit) |
| Human body into wall, or fist into wall | 0.1 | 0.0–0.3 | Flesh dominates; high-speed vehicle-barrier e → 0 |
| Vehicle on human | 0.0 | 0–0.1 | η ≤ 1 in pedestrian reconstruction |
| Hard object (weapon, armour) on armour | 0.4 | 0.2–0.6 | Elastic until yield; drop to ~0.1 once deformation or fracture occurs |

### Worked example: 3.75 kg fist at 11.3 m/s hitting a free-standing 75 kg defender

Fist kinetic energy = ½·3.75·11.3² = **239.4 J**.

**(a) Taking the defender as a literal free 75 kg rigid body (M = 75 kg), e = 0.2**

- μ = 3.75·75/78.75 = **3.571 kg**
- ½μv² = 228.0 J available, so E_damage = 228.0·(1−0.04) = **218.9 J** (91% of fist KE)
- v_cm = 3.75·11.3/78.75 = 0.538 m/s
- Defender: v_d = (1+e)·v_cm = **0.646 m/s**, KE_d = ½·75·0.646² = **15.6 J** (6.5%)
- Fist: v_a = 0.538 − 0.2·(75/78.75)·11.3 = **−1.61 m/s** (rebounds), KE_a = **4.9 J**
- Check: 218.9 + 15.6 + 4.9 = 239.4 J ✓
- Sensitivity to e:

  | e | E_damage (J) | v_d (m/s) | KE_d (J) |
  |---|---|---|---|
  | 0 | 228.0 | 0.538 | 10.9 |
  | 0.4 | 191.5 | 0.753 | 21.3 |

**(b) Head strike using the rule's effective mass M = 0.25·75 = 18.75 kg, e = 0.2**

- μ = 3.75·18.75/22.5 = 3.125 kg, so ½μv² = 199.5 J and E_damage = **191.5 J** (80%)
- Head-level Δv = 1.2·3.75·11.3/22.5 = **2.26 m/s**; local KE = ½·18.75·2.26² = **47.9 J** (20%)
- Whole-body velocity after the system re-equilibrates: J/m_d = (1.2·3.125·11.3)/75 =
  42.4/75 = **0.565 m/s**, so ~12 J of whole-body knockback. The ~36 J difference from
  the local KE is soaked up by the neck and joints, which is extra soft-tissue loading.
- Fist rebound: Δv_a = −1.2·18.75·11.3/22.5 = −11.3 m/s, so v_a ≈ 0.0 m/s. The fist
  stops dead.

**(c) The same punch against a defender pinned to a wall**

- μ = 3.75 kg, so E_damage = 0.96·239.4 = **229.8 J** and there is no knockback.
- This is about 5% more damage energy than the free case (a) and 20% more than the
  head-effective case (b). Pinning a target against a wall increases damage, which
  matches intuition and the vehicle-barrier analogy.

**Interpretation for the game.**

- For a person-sized target, roughly 80–95% of a strike's kinetic energy becomes
  damage energy.
- Only 5–20% becomes knockback. Knockback is a few tenths of a m/s of whole-body
  velocity for a punch, which is a stagger, not a launch.
- Bracing or a wall moves the remaining few percent into damage.
- Knockback becomes large only when the striker's effective mass approaches the
  defender's: tackles, charges, vehicles.

---

### Open items / verification flags

- The meaning and unit of Walilko 2005's "energy transfer 17.2" are unverified; the
  full text was blocked. It is the key calibration of the M ≈ 0.25·m_d rule.
- No direct measurement was found of e for fist, foot or body on a human or wall. The
  values in this report are inferred.
- Pedestrian–road friction coefficients and the Searle formula's exact published form
  were not fetched. The form given here is the standard derivation.
- Unblocking pmc.ncbi.nlm.nih.gov, bjsm.bmj.com, arxiv.org and core.ac.uk would allow
  these checks.
