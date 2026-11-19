# Part A — How impact damage is modeled in practice

Scope: narrative on strike "power" metrics, injury criteria, and structural
impact resistance, plus an assessment of an energy-budget ("binding energy
that impacts deplete") model. Per-item value tables are in the sibling files
`b1_b2_human_performance.md`, `b3_strike_energies.md`,
`b4_knockouts_injury_thresholds.md`, `b5_wall_resistance.md`,
`b6_tissue_resistance.md`. A short appendix at the end keeps the Part B
numbers this pass happened to find.

Numbers marked *(unverified)* are common textbook values whose primary
source was not retrieved here.

---

## A1. Measuring strike "power": force, impulse, energy, effective mass

**Four metrics are in use, and they are not interchangeable:**

| Metric | What it is | Typical measurement | Main weakness |
|---|---|---|---|
| Peak force F_max (N) | Highest contact force | Force plate / load cell behind pad, instrumented dummy | Strongly depends on target stiffness and padding: a stiffer or thinner target gives a shorter, higher spike for the same blow |
| Impulse J = ∫F dt (N·s) ≈ momentum transferred | Change in target momentum | Ballistic pendulum, integrated load cell, high-speed video of target | Largely unaffected by padding ([USQ impulse-method paper](https://research.usq.edu.au/download/afe1550c32daf15b9ad5d410353f559014acc96d76e90316155648796abf2990/1281573/Validity%20and%20reliability%20of%20a%20novel%20impulse-based%20method%20to%20analyse%20human%20striking%20performance.pdf)); but doesn't say how fast it was delivered, which is what drives head acceleration |
| Kinetic energy KE = ½ m_eff v² (J) | Energy available at contact | Velocity from high-speed video × estimated effective mass | Effective mass is hard to measure and varies a lot; KE is energy *available*, not energy *delivered to the injury mechanism* |
| Effective mass m_eff (kg) | Mass of a free rigid body that would give the same momentum transfer, m_eff = J / Δv_hand | Derived from J and hand velocity | Not a constant: in punching the athlete keeps pushing during contact, so m_eff partly reflects force added during impact ([Lenetsky et al. 2015 abstract](https://lida.sport-iat.de/ta/Record/4034356?lng=en)) |

Representative values for scale:
- Olympic boxers' straight punches on a Hybrid III dummy averaged 3427 N
  peak force, hand velocity 9.14 ± 2.06 m/s, and effective mass 2.9 ± 2.0 kg.
  That works out to a KE of about **120 J** (½·2.9·9.14²; the effective-mass SD means the true value could be anywhere from about 40 to 200 J). Heavier weight classes hit harder mainly because of higher
  effective mass, not higher speed ([Walilko, Viano & Bir 2005, BJSM 39:710](https://pubmed.ncbi.nlm.nih.gov/16183766/)).
- Professional heavyweight (Frank Bruno) on a 7 kg padded ballistic pendulum:
  4096 N peak force reached within 14 ms, fist about 8.9 m/s, target accel 53 g.
  The same blow gives different peak forces depending on the method: 4130 N
  (corrected transducer), 3600 N (film), 4600 N (accelerometer)
  ([Atha et al. 1985, BMJ](https://pubmed.ncbi.nlm.nih.gov/3936571/); method
  comparison summarized in [UBC FIB book](https://wiki.ubc.ca/Documentation:FIB_book/Boxing_Injury_Biomechanics)).
- Kick impact forces reported across studies range from **123 to 9015 N** for
  foot velocities of 5.2–18.3 m/s. The spread comes mostly from heterogeneous
  measurement setups, not from the athletes
  ([2024 systematic review, Sports](https://pmc.ncbi.nlm.nih.gov/articles/PMC10974023)).

**What correlates best with knockout or injury?** For concussion and knockout
the outcome follows **head kinematics**, especially **rotational**
acceleration and velocity, more than any property of the strike itself. Any
strike metric matters only through how well it predicts head motion:
- Animal work going back to Denny-Brown & Russell, Holbourn (1943), and
  Ommaya & Gennarelli found that loss of consciousness came readily from
  head *rotation* but rarely from pure translation
  ([review, PMC3172883](https://pmc.ncbi.nlm.nih.gov/articles/PMC3172883);
  [UBC FIB book](https://wiki.ubc.ca/Documentation:FIB_book/The_Relative_Contributions_of_Rotational_Loading_and_Accelerations_in_the_Injury_Mechanisms_of_Traumatic_Brain_Injury)).
- Olympic hooks gave the highest force (4405 ± 2318 N), the highest Δv_hand
  (11.0 ± 3.4 m/s), and head accelerations of 71 ± 32 g and
  9306 ± 4485 rad/s². Boxing punches produce **proportionately more rotation
  than translation** compared with football concussions, with *lower* HIC
  because the pulse is shorter
  ([Viano et al. 2005, Neurosurgery 57:1154](https://pmc.ncbi.nlm.nih.gov/articles/PMC3944542)).
- In MMA bouts measured with instrumented mouthguards and verified on video,
  concussive impacts had about 25% higher peak angular acceleration and about
  189% higher "head impact power" than non-injurious ones. The best
  finite-element predictor was corpus-callosum shear stress/strain, with a
  mean strain of 0.27 in concussed fighters
  ([Tiernan et al. 2020, PMC10330963](https://pmc.ncbi.nlm.nih.gov/articles/PMC10330963);
  [Ansys summary](https://www.ansys.com/advantage-magazine/volume-xiv-issue-2-2020/simulating-mma-head-shots)).
- Practical upshot: **momentum/impulse delivered off-axis** (hooks, the jaw as
  a lever arm) is the strike-side quantity closest to KO risk. Peak force
  alone is a poor and method-dependent proxy. KE sets an upper bound on what
  can be done but is only weakly tied to the outcome.

## A2. Injury criteria (biomechanics / automotive)

- **HIC** = max over t1–t2 of (t2−t1)·[ (1/(t2−t1)) ∫ a(t) dt ]^2.5, with a in g.
  The window is capped at 15 ms (HIC15). **HIC15 = 700** is the
  US advanced-airbag (FMVSS 208) limit and corresponds to about a **5% risk of
  AIS 4+** head injury (Mertz et al. 1997, as cited by
  [IIHS](https://iihs-prod.iihs.org/media/dcc9d5d6-c301-4f92-a7b5-dad13ffc7766/6h8G8A/Ratings/Protocols/current/measures_frontal.pdf)).
  IIHS rating cut-offs are 560 / 700 / 840. HIC uses translational
  acceleration only, so it misses the rotation-driven mechanism that dominates
  boxing (see Viano 2005 above).
- **Concussion, linear and rotational:** there is no accepted universal
  threshold. Commonly cited risk curves (Zhang et al., from FE
  reconstruction of NFL impacts) put **25 / 50 / 80% concussion risk at
  66 g + 4600 rad/s², 82 g + 5900 rad/s², and 106 g + 7900 rad/s²**. Pellman's NFL
  reconstructions give a concussion mean of 98 ± 28 g and 6432 ± 1813 rad/s²,
  against 60 ± 24 g and 4029 ± 1438 rad/s² for non-injury
  ([review, PMC9652163](https://pmc.ncbi.nlm.nih.gov/articles/9652163);
  [Practical Neurology review](https://practicalneurology.com/articles/2015-apr/helmets-sensors-and-more-a-review)).
  Values from helmet sensors in the field often come out higher, and the
  distributions of concussed and non-concussed athletes overlap heavily.
- **Skull fracture** depends on loading rate when measured as force, but is
  roughly constant when measured as energy. In cadaver heads
  ([Yoganandan et al. 1995](https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_77752849)),
  fracture force rose from about 6.4 kN (quasi-static) to about 11.9 kN at
  7–8 m/s, while **energy to failure stayed at about 28–34 J**. Reported 50%-risk
  force thresholds span 1.9–12.5 kN depending on site and impactor
  (summarized in [KU Leuven paper](https://lirias.kuleuven.be/retrieve/557872)).
  This is direct evidence that an energy criterion can be more robust than a
  force criterion for brittle bone, with caveats below.
- **Long bone:** the FMVSS 208 femur limit is **10 kN** axial (Hybrid III
  50th male), which corresponds to about a 35% risk of AIS 2+ knee-thigh-hip injury
  ([NHTSA/KTH paper](https://corpora.tika.apache.org/base/docs/govdocs1/072/072737.pdf)).
  The older literature gives an average static femur fracture force of 8.9 kN,
  and tolerance rises for pulses shorter than about 20 ms
  ([Viano 1977, SAE 770925](https://saemobilus.sae.org/papers/considerations-a-femur-injury-criterion-770925)).
- **Thorax** criteria are deflection-based: the viscous criterion V·C and chest
  compression. Thresholds are in the NHTSA criteria documents
  ([rev_criteria.pdf](https://www.nhtsa.gov/sites/nhtsa.dot.gov/files/rev_criteria.pdf));
  no numeric value was confirmed in this pass.
- **Bone as a material:** cortical bone is anisotropic and has rising
  R-curve toughness, so linear-elastic fracture mechanics fits it poorly.
  "Work of fracture" (energy ÷ fractured area) depends on specimen geometry
  and is not comparable across studies
  ([Ritchie et al. review via search; thesis on Griffith balance in bone](https://openresearch.surrey.ac.uk/esploro/outputs/doctoral/The-fracture-mechanics-of-bone/99514860702346)).
  Izod impact energy for cortical bone was **about 18.8 ± 7.4 kJ/m²**
  ([IAENG WCE2011](https://www.iaeng.org/publication/WCE2011/WCE2011_pp2298-2302.pdf)).
  That is an impact energy per notch area, not a Griffith G_c.

## A3. Structural resistance to impact (engineering practice)

Engineering splits impact into **local** and **global** response and models
the two separately:

1. **Local (penetration, scabbing, perforation, punching shear):** for hard
   missiles this is handled with empirical formulae: Army Corps of Engineers (ACE, 1946), modified
   NDRC (1976), UKAEA (1990), and Petry. Modified NDRC is the US Air Force's
   recommended form. It uses penetrability K ∝ 1/√f_c and a nose-shape
   factor of 0.72 (flat), 0.84 (blunt), 1.0 (hemispherical), or 1.14 (sharp). Penetration depth
   x is computed first; scabbing and perforation thicknesses then follow as multiples
   of x ([review, IASJ](https://iasj.rdd.edu.iq/journals/uploads/2025/03/26/3bb7cd35070403e54624ad80ee277760.pdf);
   [Applied Sciences 10:4964](https://mdpi.com/2076-3417/10/14/4964/xml)).
   These formulae are calibrated to specific velocity and size ranges. NDRC
   overpredicts penetration in some datasets and handles bullets well but
   large missiles poorly.
2. **Global (bending, membrane response):** the **energy-balance method**
   (DOE-STD-3014 and similar) checks that the structure's
   deformation-energy capacity, up to an allowed ductility, exceeds the
   imparted KE. The imparted KE is computed with an *effective* missile mass,
   because a soft missile spends energy crushing itself
   ([DOE-STD-3014 energy balance](https://nuclearpowerradiation.tpub.com/std3014/Energy-Balance-Method-75.htm)).
   Combined local and global behavior is usually captured with a **two-mass,
   two-spring model**: one spring for local punching, one for global bending
   ([energy.gov dynamic-impact deck](https://www.energy.gov/sites/prod/files/2019/01/f58/5%20Integrated%20Approach%20to%20Dynamic%20Impact%20Loading.pdf);
   [NTNU review](https://ntnuopen.ntnu.no/ntnu-xmlui/bitstream/11250/2486011/2/review+paper_2001-2018.pdf)).
   For RC slabs, the punching cone is modeled as a mass on a nonlinear spring
   whose maximum dissipable energy is the "punching resistant energy". The
   method is valid for **hard, low-velocity impacts**.
3. **Material fracture energy G_F (J/m²):** this is the energy per unit *crack area*
   that cohesive-crack models use. For concrete, G_F is defined so that it
   doesn't depend on specimen size; that requires extrapolating through
   Bažant's size-effect law, σ_N ∝ (1 + D/D0)^−½
   ([Bažant & Pfeiffer, ACI](https://www.concrete.org/publications/internationalconcreteabstractsportal/m/details/id/2526)).
   Ordinary concrete G_F is about 100–150 N/m *(unverified, typical
   Model-Code order)*. Fibre reinforcement raises it substantially.
4. **Rate dependence:** concrete strength rises with strain rate. Tensile
   strength starts rising at about 1 s⁻¹ and compressive at about 10 s⁻¹.
   The tensile dynamic increase factor (DIF) is about 2 at 100 s⁻¹ (Malvar & Crawford) and can exceed
   10 at very high rates. Dynamic compressive strength can reach 3–4× the
   static value at the highest strain rates
   ([Malvar & Ross 1998 summary](https://trid.trb.org/View/498262);
   [dam-concrete review, PMC12735094](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12735094/)).

### Is an energy-budget model reasonable?

**Yes, as a first-order global model.** It is essentially the engineering
energy-balance method, and skull-fracture data show that energy-to-failure is
more stable than force-to-failure across rates. The known failure modes are
below; each one suggests a correction term for a game model.

| Failure mode | Why the pure budget fails | Evidence |
|---|---|---|
| **Area/concentration** | The same J spread over a fist versus a knife edge produces completely different damage. Local perforation is set by energy per area (or per perimeter × thickness), not by total energy | Skin-simulant penetration takes about 0.25 J with a knife ([arXiv 0811.3955](https://arxiv.org/pdf/0811.3955)), while a ~120 J punch never cuts skin; NDRC nose-shape factor |
| **Energy not delivered** | KE available at contact is not KE absorbed by the target's failure mode. Some goes into padding, rebound, the striker's own deformation, or whole-body motion of the target | A ~120 J punch versus ~30 J skull-fracture energy, yet punches rarely fracture skulls; the soft-missile effective mass in DOE-STD-3014 |
| **Mechanism mismatch** | KO/concussion is a *kinematic* (rotational accel) threshold, not damage accumulation. A small, well-placed impulse can KO; a large straight push may not | Viano 2005; Tiernan 2020; HIC misses rotation |
| **Rate dependence** | Brittle materials get stronger at high rates, and bone fracture *force* rises about 2× from quasi-static to 7 m/s, so the threshold changes with speed | Yoganandan 1995; concrete DIF |
| **Size effect** | Fracture energy per area is roughly constant, so the total energy needed to break something scales with **cracked area (∝ L²)**, not volume (∝ L³). Large brittle objects are relatively weaker | Bažant size-effect law |
| **Elastic vs dissipative** | Energy below the elastic limit is stored and returned (no damage). Only the energy above the threshold depletes the budget | Ductility allowance in the energy-balance method |
| **Non-additivity of repeated blows** | Sub-threshold blows don't sum linearly for fracture (fatigue aside). For the brain, cumulative effects are real but poorly quantified | No accepted cumulative-strike threshold |

---

## Implications for an energy-budget combat model

1. **Per entity, keep several pools rather than one HP-like number:** a
   *structural* pool (fracture/perforation, in J), a *consciousness* threshold
   that is kinematic (per-hit check against rotational accel, ~5000–6000
   rad/s² ≈ 50% risk), and a slower *cumulative trauma* pool.
2. **Delivered energy = KE × coupling.** Coupling < 1 and depends on padding,
   target mobility (a free head versus a head braced against a wall), and the
   striker/target mass ratio. Momentum is the better input for "knock back
   or stagger"; KE is the better input for "break".
3. **Per-hit threshold, then deplete.** A hit only depletes the structural pool
   by (E_delivered − E_elastic) if it exceeds a per-hit threshold. Otherwise
   it is absorbed elastically. This avoids "1000 pokes fell a wall".
4. **Area dependence.** Compare energy per contact area (J/cm²) or per edge
   length (J/mm for blades) against material thresholds. Blades and points
   bypass the bulk pool and go to a penetration check (skin ~ J-scale,
   stab armour rated 24–43 J).
5. **Walls and objects:** budget ≈ G_F × (crack area needed to make a
   hole), or use empirical perforation energy per thickness from
   `b5_wall_resistance.md`. Scale the budget with thickness² for brittle
   panels (punching-cone area), and roughly linearly with thickness for
   ductile/fibrous ones.
6. **Rate modifier:** apply a dynamic-increase multiplier (1–3×) to strengths
   for fast impacts. Optionally ignore it for simplicity, since energy
   thresholds are less rate-sensitive than force thresholds.

---

## Appendix — Part B values found incidentally (see sibling files for full tables)

| Quantity | Value | Units | Method | Source |
|---|---|---|---|---|
| Olympic straight punch: force / v / m_eff | 3427 / 9.14 ± 2.06 / 2.9 ± 2.0 | N / m/s / kg | Hybrid III + high-speed video | [Walilko 2005](https://pubmed.ncbi.nlm.nih.gov/16183766/) |
| ⇒ straight punch KE (derived) | ~120 (≈40–200) | J | ½ m_eff v² | derived from above |
| Olympic punch head response | 58 ± 13 g; 6343 ± 1789 rad/s² | — | Hybrid III | Walilko 2005 |
| Olympic hook | 4405 ± 2318 N; Δv 11.0 ± 3.4 m/s; 71 ± 32 g; 9306 ± 4485 rad/s² | — | Hybrid III | [Viano 2005](https://pmc.ncbi.nlm.nih.gov/articles/PMC3944542) |
| Pro heavyweight punch | 4096 N peak (method range 3600–4600), 8.9 m/s, 53 g on 7 kg target | — | Ballistic pendulum | [Atha 1985](https://pubmed.ncbi.nlm.nih.gov/3936571/) |
| Kicks, all types | 123–9015 N; foot 5.2–18.3 m/s (roundhouse fastest, side kick strongest) | — | Systematic review, mixed methods | [Sports 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10974023) |
| Roundhouse / back kick force | 8252 ± 720 / 8023 ± 836 | N | Force transducer (Chiu 2007, cited) | [JSSM 2009](https://www.jssm.org/jssm-08-CSSI3-13.xml>Fulltext) |
| TKD turning kick (low-force setup) | 292 ± 54 N; toe 13.4 ± 1.6 m/s | — | Instrumented bag | [ITKD study](https://www.members.itkd.co.nz/reference/essays/12-study_of_turning_kick.pdf) |
| Concussion risk 25/50/80% | 66 g+4600, 82 g+5900, 106 g+7900 | g, rad/s² | FE reconstruction (Zhang) | [PMC9652163](https://pmc.ncbi.nlm.nih.gov/articles/9652163) |
| NFL concussed vs not | 98 ± 28 vs 60 ± 24 g; 6432 ± 1813 vs 4029 ± 1438 rad/s² | — | Lab reconstruction w/ Hybrid III | Pellman, via same |
| Skull fracture (frontal, cadaver) | 6.4 → 11.9 kN (quasi-static → 7–8 m/s); energy 28–34 J | — | Cadaver drop/impact | [Yoganandan 1995 via KU Leuven](https://lirias.kuleuven.be/retrieve/557872) |
| Femur axial limit | 10 kN (~35% AIS2+ KTH); static fracture avg 8.9 kN | N | Dummy criterion / cadaver | [NHTSA KTH](https://corpora.tika.apache.org/base/docs/govdocs1/072/072737.pdf), [Viano 1977](https://saemobilus.sae.org/papers/considerations-a-femur-injury-criterion-770925) |
| Cortical bone Izod impact energy | 18.8 ± 7.4 | kJ/m² | Izod impact | [IAENG 2011](https://www.iaeng.org/publication/WCE2011/WCE2011_pp2298-2302.pdf) |
| Knife through skin simulant | ~0.25 | J | Biaxial instrumented stab | [arXiv 0811.3955](https://arxiv.org/pdf/0811.3955) |
| Stab-armour test energies (HOSDB KR1/2/3) | 24 / 33 / 43 | J | Drop tower, ≤7 mm penetration | [White Rose eprint](https://eprints.whiterose.ac.uk/id/eprint/92387/1/15.11.30%20-%20HOSDB%20vs%20Utility_FinalAuthorVersion.pdf), [OJP](https://www.ojp.gov/library/publications/taking-stab-out-stabbings) |
| HIC15 limit | 700 (~5% AIS4+) | — | Dummy criterion | [IIHS](https://iihs-prod.iihs.org/media/dcc9d5d6-c301-4f92-a7b5-dad13ffc7766/6h8G8A/Ratings/Protocols/current/measures_frontal.pdf) |
