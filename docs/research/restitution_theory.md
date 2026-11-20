# Coefficient of restitution: how *e* follows from material and geometry

**Question.** Where does the coefficient of restitution *e* come from physically, and
how should it be parameterized in a combat system whose entities and walls have mass,
size and a binding energy H, the total energy they can absorb before failing (see
`docs/combat/rules.md`)? How much of each impact's energy should go into damage, and
how much should stay as kinetic energy?

**Scope.** This report covers theory only. Measured *e* values and crash or
human-impact data are in a sibling report. The impact algebra (momentum, delta-V,
energy split) is in `collision_energy_partition.md`, and wall and tissue failure
energies are in `b5_wall_resistance.md` and `b6_tissue_resistance.md`. This report
reuses those numbers rather than re-sourcing them.

**Short answer.**

- *e* is a property of the impact event, not of a single material: it summarises how
  much of the centre-of-mass kinetic energy the contact gives back. For a central,
  frictionless impact, e² = 1 − W_diss / (½ μ v_rel²).
- Each dissipation mechanism gives a characteristic *e*(v):
  - Purely elastic (Hertz): e = 1.
  - Linear viscous damping: *e* is constant.
  - Hertzian viscoelastic: 1 − e ∝ v^{1/5}.
  - Elastic-plastic, above a yield velocity V_Y: e ∝ (V_Y/v)^{1/4}.
  - Fracture or perforation: *e* falls to about 0, because the energy goes into new
    surface and the impactor passes through.
- In a layered or two-body contact, the most compliant part stores most of the energy,
  so its losses set *e*.
- **Recommendation for the game:** a per-material elastic baseline e₀, a
  Johnson-style softening above a material yield velocity V_Y, compliance-weighted
  mixing of the two bodies, and a local failure gate H_loc. Past that gate the contact
  becomes perforation (e = 0, Recht–Ipson residual velocity).
- **Worked example:** a 3.75 kg arm at 11.3 m/s into a free 75 kg torso gives
  e ≈ 0.30. Of the 228 J available in the centre-of-mass frame, about 207 J is
  dissipated and about 175 J of that counts as damage. The target is knocked back at
  only 0.70 m/s, about 18 J of KE.

**Sourcing key.**

- **[std]**: textbook result, mainly from Johnson, *Contact Mechanics* (CUP 1985),
  ch. 6 & 11; Stronge, *Impact Mechanics* (CUP 2000); and Goldsmith, *Impact* (1960).
  Reproduced from memory, not fetched.
- **[snip]**: confirmed from a search-result snippet or abstract. The URL is given.
- **[derived]**: my own algebra.
- **[judgment]**: a design choice.

arxiv.org and most publisher hosts were blocked by the sandbox. Johnson's constants
(26, 1.18) are textbook recollection, cross-checked only against snippets, as noted
where they appear.

---

## 1. Three definitions of *e* and when they differ

Notation: normal relative velocity v_n (positive = approaching). Normal impulse
P(t) accumulates during contact. Compression ends at the impulse P_c, where v_n = 0,
and P_f is the final impulse.

| Name | Definition | Character |
|---|---|---|
| Newton (kinematic) | e_N = −v_n(after) / v_n(before) | velocity ratio |
| Poisson (kinetic) | e_P = (P_f − P_c) / P_c | restitution impulse / compression impulse |
| Stronge (energetic) | e_S² = −W_r / W_c, where W_c = ∫₀^{P_c} v_n dP (work done during compression) and W_r = ∫_{P_c}^{P_f} v_n dP (work done during restitution) | sqrt of the energy ratio |

**[std]**

- **When they agree.** For a central, collinear, frictionless impact, or any impact
  where the normal and tangential motions decouple, all three are identical.
  v_n(P) is then linear in P (dv_n = dP/μ), so the impulse ratio, the velocity ratio
  and the square root of the work ratio coincide.
- **When they differ.** They diverge for eccentric impacts with friction where slip
  stops or reverses during contact, because v_n(P) becomes piecewise linear.
  - Newton's law can then predict an *energy gain*, which is unphysical.
  - Poisson's law can also gain energy with several frictional contacts.
  - Stronge's definition guarantees dissipation whenever e_S < 1, but it can imply
    e_P > 1.

  Sources: [snip] review summaries at https://mdpi.com/2673-8716/2/4/25 and
  https://doc.rero.ch/record/325312/files/11044_2013_Article_9387.pdf.
- **What it means for the game.** Impacts are treated as clean, central and
  frictionless (rules v0: "every impact is clean"), so the three definitions are the
  same and Newton's form is the easiest to implement. If glancing blows with friction
  are added later, define *e* energetically (Stronge) to keep the energy accounting
  safe.

---

## 2. Elastic contact (Hertz): e = 1, but contact time is finite

Hertz contact of two spheres (or a sphere on a flat, with R₂ = ∞) **[std]**:

- Effective radius: 1/R = 1/R₁ + 1/R₂
- Contact modulus: 1/E* = (1−ν₁²)/E₁ + (1−ν₂²)/E₂
- Force law: F = (4/3) E* R^{1/2} δ^{3/2}, where δ is the approach of the two centres
- Peak contact pressure: p₀ = (2/π) E* (δ/R)^{1/2}
- Contact radius: a = (Rδ)^{1/2}

The force law is conservative: loading and unloading follow the same F(δ) curve, so
the work of compression is returned in full and **e = 1 exactly**. The impact still
lasts a finite time, set by the equation of motion μ δ̈ = −F(δ) with δ̇(0) = v.

- **Maximum approach:** δ_max = (15 μ v² / (16 E* R^{1/2}))^{2/5}
- **Peak force:** F_max = (4/3) E* R^{1/2} δ_max^{3/2} ∝ μ^{3/5} E*^{2/5} R^{1/5} v^{6/5}
- **Contact duration:** t_c ≈ 2.94 δ_max / v = 2.87 (μ² / (R E*² v))^{1/5}

**Scalings:** t_c ∝ v^{−1/5} R^{−1/5} E*^{−2/5} μ^{2/5}.

- For two equal spheres, μ ∝ ρR³, so t_c ∝ R (ρ/E*)^{2/5} v^{−1/5}.
- Faster impacts are shorter, but only weakly.
- Softer and denser materials give longer contacts.

**Linear-spring comparison [std].** With a linear contact spring k, as a crude stand-in
for a soft-tissue pad, the impact is half a period: t_c = π√(μ/k), independent of v,
and δ_max = v√(μ/k).

**Example [derived].** Arm into torso, μ = 3.57 kg, k ≈ 1×10⁵ N/m [judgment]:

- t_c ≈ 19 ms
- δ_max ≈ 6.8 cm
- F_max ≈ 6.8 kN (elastic upper bound)

This is in line with the 10–20 ms contact durations quoted in
`collision_energy_partition.md`.

**Takeaway.** Hertz explains *duration* and *peak force*, both relevant to injury
criteria. It cannot explain e < 1. Every e < 1 comes from a dissipation mechanism added
on top of it (sections 3–6).

---

## 3. Elastic-plastic impact (Johnson, Thornton)

### 3.1 Yield velocity

**[std]** Under Hertz loading, first yield occurs below the surface once the peak
pressure reaches p₀ ≈ 1.6 Y (Tresca/von Mises, ν ≈ 0.3), where Y is the uniaxial
yield stress. Putting this into the Hertz energy balance gives the impact speed at
which yield begins. Johnson's form for a sphere of density ρ striking a flat:

  ρ V_Y² / Y ≈ 26 (Y/E*)⁴,  so  V_Y ≈ 5.1 √(Y⁵ / (ρ E*⁴))

- The constant 26 is from Johnson (1985) §11.3, from memory; it is not fetched.
- Thornton writes the same threshold in terms of the limiting contact pressure p_y:
  V_Y = 1.56 √(p_y⁵ / (E*⁴ ρ)). With p_y = 1.6 Y this agrees with Johnson's form
  [derived].
- [snip] A related form (Thornton & Ning 1998), quoted in
  https://arxiv.org/pdf/1105.3909, is v_y = 6.4 √(p_y⁵ r³ / (E⁴ m)), written with
  mass and radius instead of density.

**V_Y depends only on material, not on size.** In the ρ-form, R cancels. This matters
for the game: the plastic threshold is a velocity, so the energy threshold
E_Y = ½ μ V_Y² scales with the bodies' mass.

**Numbers [derived].**

- Hard steel on steel (Y ≈ 1 GPa, E* ≈ 115 GPa, ρ = 7800): V_Y ≈ 0.14 m/s.
- Concrete-like (Y ≈ 30 MPa, E ≈ 30 GPa, ρ = 2400): V_Y ≈ 1 mm/s.

So **hard engineering solids start to yield locally at almost any game-relevant
speed.** Their "elastic" regime is negligible, and at fight speeds they sit in the
plastic regime below.

### 3.2 Johnson's fully plastic restitution

**[std]** Above V_Y, the plastic zone grows. Johnson's approximation:

- Loading follows a fully plastic indentation law: mean pressure p_m ≈ 3Y, constant,
  so F ≈ 3Y·π a².
- All work done during loading is lost except the elastic energy stored at maximum
  load.
- Unloading is Hertzian, with a modified radius set by the permanent dent.
- The energy recovered is W_el ∝ F_max^{5/3} / (E*^{2/3} R'^{1/3}).

Dividing by ½μv² gives

  e ∝ (Y/E*)^{1/2} (ρ v² / Y)^{−1/8},  equivalently  **e ≈ C (V_Y / v)^{1/4}** for v ≫ V_Y

- [snip] The prefactor C ≈ 1.18 is attributed to Johnson in Pöschel and co-workers'
  inelastic-sphere paper, which gives η_plastic(v) ≃ 1.18 (v/v_y)^{−1/4}:
  https://arxiv.org/pdf/cond-mat/0209490.
- [snip] An OSTI abstract independently states e ∝ v^{−1/4} for fully plastic
  indentation: https://www.osti.gov/biblio/175411.
- The 1.18 makes e > 1 near v ≈ V_Y, so the formula is valid only well above V_Y.
  Thornton's expression (below) joins smoothly to e = 1 at V_Y.

**Material dependence [derived].**

  e ≈ 1.5 (Y/E*)^{1/2} (v / √(Y/ρ))^{−1/4}

- *e* rises with **hardness relative to stiffness**, Y/E*: high-yield, compliant
  materials bounce.
- *e* falls weakly with **impact speed** (−1/4 power) and with **density** (+1/8 on
  ρ inside, so e ∝ ρ^{−1/8}).
- *e* is independent of **size**.

In energy form, the KE in the centre-of-mass frame is E = ½μv², so v ∝ E^{1/2} and

  e ∝ E^{−1/8},  e² ∝ E^{−1/4}

This is a very slow decay. Doubling the impact energy lowers *e* by only 8%.

**Caveat.** Measured *e* for hard steel balls is often higher than this formula
predicts, because the dynamic yield stress is higher than the static value, and
because work hardening and rate effects raise it further. Treat V_Y as an
*effective*, calibrated parameter, not a handbook Y.

### 3.3 Thornton (1997) closed form for elastic-perfectly-plastic spheres

**[snip]** Thornton, J. Appl. Mech. 64(2):383–386, doi:10.1115/1.2787319 (abstract
via https://scilit.com/publications/d79ae9fb5be0b308c6eb97213d414547).

Thornton truncates the Hertz pressure at the limiting pressure p_y, which gives a
force–displacement curve that is linear above yield, and unloads elastically. With
x = V_Y/v:

  e = √(6√3/5) · √(1 − x²/6) · [ x / ( x + 2√(6/5 − x²/5) ) ]^{1/4},  for v ≥ V_Y
  e = 1,  for v ≤ V_Y

- This form is from memory [std]. Its limit [derived] is consistent with the 1.18
  above: as x → 0, e → 1.185 x^{1/4}.
- At v = V_Y, e = 1 exactly, so the curve has no discontinuity.
- Typical values of e(v/V_Y) [derived]:

  | v/V_Y | 1 | 2 | 5 | 10 | 100 |
  |---|---|---|---|---|---|
  | e | 1.00 | 0.93 | 0.77 | 0.66 | 0.37 |

- Extensions:
  - Li, Wu & Thornton (2002) cover rigid-on-plastic and plastic-on-rigid contacts
    ([snip]
    https://researchportal.plymouth.ac.uk/en/publications/a-theoretical-model-for-the-contact-of-elastoplastic-bodies/).
  - Thornton & Ning (1998) add adhesion and a *sticking velocity* v_s, below which
    e = 0 ([snip] https://arxiv.org/pdf/1105.3909).
  - Jackson, Green & Marghitu (2010) refit the curve against finite-element analysis.

**For the game:** the Thornton/Johnson shape, constant up to a threshold and then
proportional to (V_Y/v)^{1/4}, is the principled "elastic up to a point, then
plastic" curve.

---

## 4. Viscoelastic impact

### 4.1 Linear spring–dashpot (Kelvin–Voigt)

**[std]**

- Equation of motion: μ δ̈ + c δ̇ + k δ = 0
- Natural frequency ω₀ = √(k/μ), damping ratio ζ = c / (2√(kμ)), damped frequency
  ω_d = ω₀√(1−ζ²)
- Contact ends at half a damped period: t_c = π/ω_d (if contact ends when δ returns
  to 0)

  **e = exp(−π ζ / √(1−ζ²))**,  inverse: ζ = −ln e / √(π² + ln² e)

**Properties:**

- *e* is **independent of impact speed** and of energy. This is the only standard
  model that gives a constant *e*.
- It has two known artifacts:
  1. The force jumps to c·v at first touch.
  2. The force goes negative (tensile) just before separation.

**Values [derived]:**

| e | 0.9 | 0.7 | 0.5 | 0.4 | 0.3 | 0.1 |
|---|---|---|---|---|---|---|
| ζ | 0.034 | 0.11 | 0.22 | 0.28 | 0.36 | 0.59 |

### 4.2 Hunt–Crossley (nonlinear damping)

**[std]**

- Force law: F = k δⁿ + λ δⁿ δ̇, with n = 3/2 for Hertzian contact.
- The damping scales with indentation, so the force starts at 0 and never becomes
  tensile, which removes both Kelvin–Voigt artifacts.
- For small damping, Hunt & Crossley (1975) linearised to e ≈ 1 − (2/3) α v, with
  λ = α k:

  **1 − e ∝ v**: *e* falls linearly with impact speed.
- Common ways to set λ from a target e at a given impact speed v⁻:

  | Source | λ |
  |---|---|
  | Hunt–Crossley | 3k(1−e) / (2 v⁻) |
  | Lankarani–Nikravesh (1990) | 3k(1−e²) / (4 v⁻), valid for e near 1 |
  | Flores et al. (2011) | 8k(1−e) / (5 e v⁻), better at low e |

  [snip] Recent closed forms are in Sun et al. 2018,
  https://www.doi.org/10.1016/j.ijimpeng.2018.07.007, and in Multibody Syst. Dyn.
  2020, https://link.springer.com/article/10.1007/s11044-020-09745-x.
- These are calibration recipes: pick an *e* you want at some reference speed, and
  the model then extrapolates *e*(v) linearly.

### 4.3 Kuwabara–Kono / Brilliantov (viscoelastic Hertz)

**[std]** This is the physically derived Hertzian dashpot. It assumes the bulk material
is linearly viscoelastic, with a dissipative function proportional to the strain rate.

- Force law: F = (2Y_m√R / (3(1−ν²))) (δ^{3/2} + (3/2) A √δ δ̇)
  - A is a dissipative time constant set by the material's bulk and shear
    viscosities.
  - Y_m here is Young's modulus.

Solving the equation of motion gives a series (Schwager & Pöschel, PRE 78, 051304,
2008):

  e = 1 − C₁ A κ^{2/5} v^{1/5} + C₂ A² κ^{4/5} v^{2/5} − …

- C₁ ≈ 1.153 and C₂ ≈ 0.798.
- κ = (3/2)^{3/2} Y_m √R / (m_eff (1−ν²)) (form from memory).

Consequences:

- **1 − e ∝ v^{1/5}**: *e* falls slowly with speed.
- **1 − e ∝ R^{−1}** [snip]: at equal speed, larger spheres are *more* elastic, which
  is the opposite of the plastic result. The same arXiv paper (cond-mat/0209490)
  contrasts the R-independent plastic η with the viscoelastic 1 − η ∝ 1/R.
- [snip] The 1/5 exponent and the coefficient 1.009 also appear in arxiv
  cond-mat/0312005.
- [snip] Willert (2020, Front. Mech. Eng.) shows that, for low-speed viscoelastic
  impacts, *e* depends mainly on the loss-to-storage-modulus ratio tan δ of the
  material at the contact frequency ~1/t_c:
  https://www.frontiersin.org/articles/10.3389/fmech.2020.00003/pdf.

  A quick rule of thumb [std, approximate]: 1 − e² ≈ π tan δ / 2 for small losses.

**Relevance to tissue.** Soft tissue is viscoelastic, so its damping depends on rate.
Thoracic injury criteria are velocity-based (the Lau & Viano viscous criterion,
V·C [std]; details belong to the sibling report). This is one reason a *velocity*
threshold suits flesh as well as metal.

---

## 5. The energy-balance view: *e* is the fraction of relative KE returned

**[std]/[derived].** Split the KE into its centre-of-mass (CM) and relative parts:

- KE = ½ M v_cm² + ½ μ v_rel²
- M = m₁ + m₂, μ = m₁m₂/M

Momentum conservation fixes v_cm, so **only the relative part ½ μ v_rel² can ever be
dissipated.** Newton's law v_rel' = −e v_rel then gives:

  ΔE_diss = ½ μ v_rel² (1 − e²)
  E_returned (relative KE after impact) = e² · ½ μ v_rel²

Equivalently, **e² = 1 − W_diss / E_rel**, where E_rel ≡ ½ μ v_rel². This holds
whatever the mechanism: plastic work, viscous heat, fracture surface energy, ejected
fragments, or vibration left in the bodies.

So *e* is just a different encoding of the fraction of the available energy that
deformation and damage absorb. Each model in sections 2–4 is a recipe for W_diss(E_rel):

| Mechanism | W_diss / E_rel = 1 − e² | Scaling of *e* |
|---|---|---|
| Hertz elastic | 0 | e = 1 |
| Kelvin–Voigt | constant | e constant |
| Hunt–Crossley | ≈ (4/3) α v | 1 − e ∝ v ∝ E^{1/2} |
| Kuwabara–Kono | ≈ 2 C₁ A κ^{2/5} v^{1/5} | 1 − e ∝ E^{1/10} |
| Johnson plastic (v ≫ V_Y) | 1 − C²(V_Y/v)^{1/2} | e ∝ E^{−1/8} |
| Perforation | E_fail / E_rel (Recht–Ipson, §6) | no rebound |

Practical consequences:

- **Light striker on a heavy target:** μ ≈ m_striker, so nearly all of the striker's
  KE is available to dissipate.
- **Equal masses, one at rest:** μ = m/2, so only half the moving body's KE is
  available. This holds however soft the target is.
- **Effect of *e* on the target:**
  - Momentum transferred: J = (1+e) μ v_rel. This varies only by a factor of 2
    between e = 0 and e = 1.
  - Energy dissipated: ½μv_rel²(1−e²). This varies from all of E_rel to none of it.
  - So **the choice of *e* mostly decides damage, not knockback.**

---

## 6. Fracture, penetration and fragmentation

**[std]** When a target cracks, energy goes into:

- new crack surface: G_c × the new area ΔA, where G_c is the fracture energy, about
  K_IC²/E′ for brittle solids;
- plastic work in the process zone;
- KE of ejected fragments;
- stress waves.

The rebound energy is whatever is left:

  e² = 1 − (W_plastic + W_visc + G_c ΔA + KE_frag + W_waves) / E_rel

The order of magnitude of G_c is in `b5_wall_resistance.md`: concrete ~100–150 J/m²,
glass ~8 J/m².

**Through-cracking or perforation.** Once a target is cracked through or perforated,
the contact force collapses: the target can no longer push back. So **e → 0** in the
rebound sense, even though the impactor keeps a forward velocity. The standard
ballistic-limit energy balance (Recht & Ipson 1963 [std]) for a rigid projectile
perforating a plate is

  v_r = a (v^p − v_bl^p)^{1/p}

- Pure energy balance, ignoring plug momentum, gives a = 1 and p = 2:
  **½ m v_r² = ½ m v² − E_bl**.
- E_bl = ½ m v_bl² is the perforation energy.
- If a plug of mass m_p is punched out, a = m/(m + m_p).

This is exactly the "local binding energy" gate a game wants:

- Below E_bl the target absorbs energy and the projectile rebounds with some e > 0.
- Above E_bl the target absorbs about E_bl, and the projectile passes through with the
  rest.

**Near the threshold.** Just below E_bl the target is cracking but not yet perforated:
damage and softening accumulate and *e* drops steeply, because the contact stiffness
falls as cracks grow. Sticking or crumbling contacts give e ≈ 0 without perforation:

- powders and aggregates, Thornton–Ning sticking velocity [snip];
- plaster and drywall crushing.

Brittle-material models (Grady–Kipp fragmentation, Holmquist–Johnson for concrete)
predict fragment size and the extent of damage. None gives *e* in closed form, but all
of them support the rule that **once fracture dominates W_diss, e ≈ 0–0.2** for the
impactor.

**Repeated sub-threshold hits.** Below the single-hit threshold, damage accumulates.
The ACI 544 drop test in `b5_wall_resistance.md` cracks concrete with many 20 J
blows. A per-entity cumulative H (rules v0) captures this. A per-hit *e* model needs
only the *local* failure threshold H_loc for the current hit.

---

## 7. Composite and layered bodies: series compliance

**[std]/[derived].** In a quasi-static view, which holds when t_c is much longer than
the time for elastic waves to cross each layer, the contact is a chain of springs in
series. Each spring carries the same force F, and spring i stores
U_i = F²/(2k_i). So

  energy fraction in part i:  c_i = (1/k_i) / Σ_j (1/k_j)

**The most compliant part (smallest k) takes most of the energy.** If each part
dissipates a fraction (1 − e_i²) of the energy it receives, the combined *e* is

  **1 − e² ≈ Σ_i c_i (1 − e_i²)**

Two consequences:

1. **Hard on soft.** A soft layer (flesh, padding, drywall) dominates *e* and takes
   most of the dissipation.
   - Concrete has c ≈ 0, so for a fist on concrete *e* is about e_fist.
   - The damage goes into the hand. That matches reality: punching a wall breaks
     knuckles, not the wall.
2. **Soft over hard.** For soft tissue over bone, or padding over a rigid core, the
   layer works as a compliant spring until it "bottoms out". At bottoming-out the
   effective k jumps, F spikes, the stiff core starts taking energy, and its failure
   mode (bone fracture) governs. This is why padding protects, and why it stops
   protecting above some energy.

   In a thin-layer contact model, the layer's stiffness grows as its thickness h
   shrinks: k ∝ E_layer·A/h for a uniaxial layer, or Johnson §5.8's bonded-layer
   solutions [std].

**Rate effects.** If t_c is comparable to the wave-transit time (very stiff, slender
bodies at high speed), energy also ends up as vibration left in the bodies. That
lowers *e* even for perfectly elastic materials, as with long rods and plates
(Zener's plate impact [std]). This is negligible for human strikes (t_c ~ 10–20 ms).

---

## 8. Parameterization options for the game

The game state is: masses m₁ and m₂ (or segment masses), v_rel, a material for each
body, a cumulative binding energy H (1500 J default), and the energy each entity has
absorbed so far, H_used.

### (a) Fixed *e* per material pair

e = e_pair(mat₁, mat₂). The model is Kelvin–Voigt in disguise.

**Pros:**

- Trivial to implement, and the KV damping ratio ζ derives from it if needed.
- Momentum and energy are always consistent.
- Matches the measurement tables the sibling report will produce.

**Cons:**

- N² table.
- No speed dependence: a 1 J tap dissipates the same *fraction* as a 1 kJ blow, and
  even a gentle push "damages" the target.
- No failure or perforation behaviour.
- Ignores the theory showing *e* falls with energy.

### (b) Johnson-like elastic → plastic curve from a material yield velocity

  e = e₀ for v ≤ V_Y,  e = e₀ (V_Y/v)^{1/4} for v > V_Y

**Variants:**

- Thornton's exact form (§3.3) can replace the simple power law.
- Energy form: e = e₀ (E_Y/E_rel)^{1/8}, with E_Y = ½ μ V_Y².

**Pros:**

- Physically derived.
- Per-material, not per-pair: combine the two bodies with §7.
- Gives a natural "harmless below threshold" regime.
- V_Y is size-independent, as in Johnson's theory, so heavier bodies get
  proportionally larger energy thresholds.

**Cons:**

- The −1/4 decay is gentle and never reaches 0, so it cannot model breaking or
  perforation alone.
- V_Y for flesh is a calibrated stand-in, not a literal yield stress.

### (c) *e* driven by the binding energy H or a per-hit threshold

For example, e² = e₀² · max(0, 1 − E_rel/H_loc), or a version using the remaining
budget H − H_used.

**Pros:**

- Ties *e* directly to the target's durability.
- Hits near the failure energy become fully absorbing, which captures the drop in
  *e* near fracture (§6).
- One parameter the game already has.

**Cons:**

- Using the whole-body H (1500 J) is the wrong scale: a body does not fail as a whole
  from a single local hit. With E_rel ~ 230 J this would barely move *e*.
- Using the remaining H makes a wounded entity "absorb" more and get knocked back
  less. That may suit the game, but it is not physical.
- Without a separate gate, it says nothing about what happens above the threshold:
  perforation versus a dead stop.

### (d) Viscoelastic damping ratio per material (KV or Hunt–Crossley)

**Pros:**

- Physically meaningful for tissue.
- Hunt–Crossley gives 1 − e ∝ v.
- Also yields t_c and F_max, which are useful for injury criteria based on force or
  acceleration.

**Cons:**

- It needs a contact stiffness k and a time integration, or the closed forms.
- Its speed dependence (*e* falls with v) overlaps with (b) without adding a
  damage/heat distinction.
- Still has no failure behaviour.

### Recommendation: (b) + series mixing + a local failure gate (borrowing the threshold from (c))

Per material, define four numbers: the elastic-regime restitution e₀, the yield
velocity V_Y, a contact stiffness class k, and a local failure energy H_loc. Resolve
each clean, central impact as follows.

1. **Energy available:** μ = m₁m₂/(m₁+m₂), E_rel = ½ μ v_rel².
2. **Split by compliance:** c_i = (1/k_i)/(1/k₁ + 1/k₂), and E_i = c_i E_rel.
3. **Per-body restitution,** evaluated at that body's share, with velocity-equivalent
   v_i = √(2E_i/μ):

     e_i = e₀,i · min(1, (V_Y,i / v_i)^{1/4})

   Thornton's form can be used instead for a smoother curve.
4. **Combined:** 1 − e² = Σ c_i (1 − e_i²).
   - Dissipated energy in body i: D_i = c_i E_rel (1 − e_i²).
   - Damage in body i: Dmg_i = D_i · max(0, 1 − V_Y,i²/v_i²). Dissipation below
     the yield threshold is harmless heat or bruise-free hysteresis.
5. **Failure gate:**
   - If Dmg_i ≥ H_loc,i (or ≥ H − H_used, whichever is lower), body i fails
     locally.
   - Set e = 0 for the contact.
   - The struck body absorbs H_loc,i, and the impactor continues with relative
     energy E_rel − H_loc,i. Apply Recht–Ipson with p = 2, using μ for a free target
     or m_striker for a fixed wall.
6. **Update state:**
   - Use Newton's law with *e* for the post-impact velocities:
     v₁' = v_cm − e (m₂/M) v_rel and v₂' = v_cm + e (m₁/M) v_rel.
   - Add Dmg_i to H_used.

   In v0 the attacker takes no damage, so skip Dmg for the striker, but keep its
   c_i share in the *e* calculation.

This keeps exact momentum conservation and energy accounting:

  ΔKE = Σ D_i = heat + damage

It reproduces the theory's main regimes:

- elastic and harmless at low speed;
- slowly softening above yield (e ∝ E^{−1/8});
- a sharp transition to e = 0 and perforation at local failure;
- "the soft part takes the hit" for mixed-material pairs.

Option (c)'s graded softening can be added as an extra factor if hits close to
H_loc should look more absorbing: e_i² ← e_i² · max(0, 1 − Dmg_i/H_loc,i).

**Typical parameter values (all [judgment], order of magnitude).** Calibrate e₀
against the sibling report's measurements. H_loc values come from
`b5_wall_resistance.md` and `b6_tissue_resistance.md`.

| Material | e₀ | V_Y (m/s) | k (N/m, local contact) | H_loc (J, per hit) | Notes |
|---|---|---|---|---|---|
| Human torso / soft tissue | 0.4 | 3 | 1×10⁵ | defer to b6. Entity-level H = 1500 J | V_Y ~3 m/s matches the onset of thoracic viscous-criterion injury [std]. ζ_KV ≈ 0.28 |
| Fist / knuckles (bare) | 0.4 | 3 | 1×10⁶ | ~50–150 (hand fracture, b6) | Bony and stiffer than the torso, so takes about 9% of a torso punch |
| Head (skull over thin scalp) | 0.5 | 3 | 5×10⁶ | defer to b4/b6 | Stiff, so the striker's softer part dominates |
| Drywall (12.7 mm gypsum) | 0.3 | 1 | 2×10⁵ (panel flex) | 30–70 hard nose; 122 blunt (C1629 L1, b5) | Crushes, so e falls fast. Perforation is common |
| Wood (door, planks, stud wall) | 0.5 | 2 | 1×10⁶ | ~200 per blow for a door (F476); < 474 for a stud wall (b5) | Splinters near H_loc |
| Brick (veneer) | 0.6 | 0.5 | 1×10⁷ | 1,700–2,600 (b5) | Effectively rigid to flesh |
| Concrete / grouted CMU | 0.7 | 0.5 | 1×10⁸ | > 6,800 (b5) | Literal Johnson V_Y is about 1 mm/s; 0.5 is an effective value. Hard-on-hard only |

- e₀ only matters when that material carries a meaningful share of c_i. For flesh on
  masonry, the flesh values govern.
- For walls, treat the mass as infinite: μ = m_striker and v_cm = 0, and a fixed wall
  never moves.

### Worked example: 3.75 kg arm, 11.3 m/s, into a free 75 kg torso [derived]

**Inputs:** m₁ = 3.75 kg and m₂ = 75 kg, so M = 78.75 kg and μ = 3.571 kg.

- Arm KE = ½·3.75·11.3² = 239.4 J.
- E_rel = ½·3.571·127.69 = **228.0 J**.
- v_cm = 3.75·11.3/78.75 = 0.538 m/s, so ½Mv_cm² = 11.4 J. This part cannot be
  dissipated.

**Split by compliance** (k_torso = 1e5 N/m, k_fist = 1e6 N/m):

| | Torso | Fist |
|---|---|---|
| c_i | 0.909 | 0.091 |
| E_i | 207.3 J | 20.7 J |
| v_i = √(2E_i/μ) | 10.77 m/s | 3.41 m/s |
| e_i = 0.4·(3/v_i)^{1/4} | 0.4·0.727 = 0.291 | 0.4·0.968 = 0.387 |
| 1 − e_i² | 0.915 | 0.850 |

**Combined restitution:** 1 − e² = 0.909·0.915 + 0.091·0.850 = 0.909, so
**e ≈ 0.30**. (Taking V_Y = 3.35 m/s instead, i.e. E_Y = 20 J, gives e ≈ 0.31.)

**Dissipation:**

- Total: 228.0·0.909 = **207 J**.
- Torso: D = 207.3·0.915 = 189.7 J.
  - Harmless part: V_Y²/v² = 9/116 = 0.078.
  - **Damage ≈ 189.7·0.922 = 175 J.**
- Fist: D = 17.6 J, of which ≈ 4 J is damage. It is ignored in v0.

**Failure gate:** 175 J is below the entity's H = 1500 J and below any plausible
single-hit torso H_loc, so the contact rebounds and there is no perforation. About
8–9 such punches would defeat a default entity (1500/175 = 8.6).

**Post-impact velocities** (e = 0.30):

- Torso: v₂' = 0.538 + 0.30·(3.75/78.75)·11.3 = **0.70 m/s** (KE 18.4 J).
- Arm: v₁' = 0.538 − 0.30·(75/78.75)·11.3 = **−2.69 m/s**, a small rebound
  (KE 13.6 J).

**Energy check:** 239.4 = 18.4 + 13.6 + 207.4 ✓.

**Sensitivity of the outcome to *e*:**

| e | Torso v₂' (m/s) | Dissipated (J) |
|---|---|---|
| 0 | 0.54 | 228 |
| 0.3 | 0.70 | 207 |
| 0.5 | 0.81 | 171 |

This confirms §5: *e* decides damage far more than knockback.

**Same arm into walls** (μ = 3.75 kg, E_rel = 239 J):

- **Drywall** (c_wall ≈ 0.83 vs the fist).
  - The wall's share is about 199 J, at v ≈ 10.3 m/s.
  - e_wall = 0.3·(1/10.3)^{1/4} ≈ 0.17, so wall damage ≈ 199·(1 − 0.17²)·(1 − 1/106) ≈ 192 J, far above H_loc ≈ 50 J, so
    the wall **perforates**.
  - Then e = 0, the wall absorbs about 50 J, and the arm continues at
    √(2·189/3.75) ≈ **10.0 m/s**.
- **Concrete** (c_fist ≈ 0.99).
  - e ≈ e_fist(239 J) = 0.4·(3/11.3)^{1/4} ≈ **0.29**.
  - About 220 J is dissipated, almost all of it in the hand: about 200 J of
    self-damage.
  - The wall is unharmed and the arm rebounds at −3.3 m/s.
  - This is the physical case for revisiting the v0 rule that the attacker takes no
    damage when striking walls.

---

## Sources

Fetched as search snippets or abstracts:

- Pöschel et al., inelastic sphere impact, plastic η ≃ 1.18 (v/v_y)^{−1/4}, viscoelastic
  1 − η ∝ 1/R: https://arxiv.org/pdf/cond-mat/0209490
- Thornton & Ning yield velocity form; sticking/yield velocity parametrization:
  https://arxiv.org/pdf/1105.3909
- Thornton 1997, J. Appl. Mech. 64:383:
  https://scilit.com/publications/d79ae9fb5be0b308c6eb97213d414547
- Li, Wu & Thornton 2002:
  https://researchportal.plymouth.ac.uk/en/publications/a-theoretical-model-for-the-contact-of-elastoplastic-bodies/
- e ∝ v^{−1/4} for fully plastic indentation: https://www.osti.gov/biblio/175411
- Johnson-style contents (ch. 6: restitution of elastic-plastic solids):
  https://assets.cambridge.org/97805216/32867/sample/9780521632867wsn01.pdf
- Hunt–Crossley damping vs e: https://www.doi.org/10.1016/j.ijimpeng.2018.07.007 ;
  https://link.springer.com/article/10.1007/s11044-020-09745-x
- Kuwabara–Kono 1/5 power: https://arxiv.org/pdf/cond-mat/0312005
- Willert 2020, viscoelastic COR vs loss modulus:
  https://www.frontiersin.org/articles/10.3389/fmech.2020.00003/pdf
- Newton/Poisson/Stronge comparison: https://mdpi.com/2673-8716/2/4/25 ;
  https://doc.rero.ch/record/325312/files/11044_2013_Article_9387.pdf

Textbook [std], not fetched:

- K.L. Johnson, *Contact Mechanics* (1985), §4.2 Hertz, §6 elastic-plastic, §11.3–11.4
  impact and restitution
- W.J. Stronge, *Impact Mechanics* (2000)
- Hunt & Crossley, J. Appl. Mech. 42 (1975)
- Kuwabara & Kono, Jpn. J. Appl. Phys. 26 (1987)
- Schwager & Pöschel, PRE 78 (2008)
- Lankarani & Nikravesh (1990)
- Flores et al. (2011)
- Recht & Ipson, J. Appl. Mech. 30 (1963)
- Lau & Viano viscous criterion (1986)
