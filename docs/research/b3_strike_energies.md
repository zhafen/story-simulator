# B3 — Strike energies, forces and momenta (unarmed strikes and implements)

Research note for a physics-grounded combat model. Compiled 2026-11-19.

**Sourcing caveat (read first).** In the session that produced this note, direct page fetching was
blocked by network policy (pmc.ncbi.nlm.nih.gov, mdpi.com, wiki.ubc.ca were unreachable), so every
number below was taken from search-engine abstracts/snippets of the cited page, not from the full
paper text. Each number carries the URL it came from. Numbers marked **[derived]** are this note's
own arithmetic (KE = ½mv², p = mv) from cited inputs; numbers marked **[assumed]** are not from a
cited source and should be treated as placeholders. Values flagged **[unverified]** appeared in only
one secondary source and could not be cross-checked. Full-text verification of the key papers
(Walilko 2005, Corcoran 2024, Siegenthaler 2018, Sprenger 2016) is the obvious next step.

---

## 1. Concepts

### 1.1 Effective mass

A striking limb is not a rigid free body: at contact, only part of the body's mass is "coupled" to
the fist/foot through stiffened joints. **Effective mass** (m_eff) is the mass of an equivalent rigid
free projectile that would deliver the same momentum/force at the same velocity. It is measured as
m_eff = F_peak / a_fist (Lenetsky et al.; Wąsik et al. — method described in
https://mdpi.com/2076-3417/15/7/4008) or from momentum exchange with an instrumented target of known
mass (Walilko et al. 2005, https://pubmed.ncbi.nlm.nih.gov/16183766/).

- Elite Olympic boxers, straight punches: **2.9 ± 2.0 kg** (Hybrid III head, equilibrium method)
  — https://pubmed.ncbi.nlm.nih.gov/16183766/ . Heavier weight classes punched harder "due primarily
  to a higher effective mass", not higher speed.
- Experienced kung fu palm strike: **2.62 ± 0.3 kg** vs novices **~1.33 kg**
  (Neto, Magini & Saba 2007, J Appl Biomech 23:139) — via secondary citation,
  https://www.semanticscholar.org/paper/The-role-of-effective-mass-and-hand-speed-in-the-of-Neto-Magini/bc013a2dfb83f9bc6d7acb5f6bdd740767ee32d5 **[unverified exact values]**.
- For a forum-reported summary of Lenetsky 2015 ("Is effective mass in combat sports punching above
  its weight?", Hum Mov Sci 40:89): untrained m_eff ≈ 74–102 % of hand+forearm mass, trained ≈
  154–197 % — https://vsbattles.com/threads/is-effective-mass-being-accounted-for-in-our-standards-for-real-life-punch.114763 **[unverified, low-quality source]**.
- For implements, effective mass depends on the impact point. A bat struck away from its centre of
  mass rotates, so its effective mass is less than its actual mass (Cross 1999,
  https://www.physics.sydney.edu.au/~cross/baseball.html); for swords the point of maximum delivered
  energy is the percussion point relative to the apparent centre of rotation
  (https://www.tf.uni-kiel.de/matwis/amat/iss/kap_c/backbone/rc_4_4.html).

**Game rule of thumb:** strike KE = ½·m_eff·v². Training increases both v and, more strongly,
m_eff (≈1.3 → ~3 kg for hands), so trained strikers roughly double-to-triple delivered energy at
similar hand speed.

### 1.2 Why KE, force and momentum predict different things

| Quantity | What it governs | Evidence / threshold |
|---|---|---|
| **Kinetic energy** (J) | Work available to deform, crush, cut, fracture; armour penetration | Skull-fracture threshold ~**11.0 J** (fixed head) / **13.6 J** (free head) for blunt impactors (Siegenthaler group, 2019) — https://www.springermedicine.com/skull-fracture/threshold-of-the-skull-injury-for-blunt-force-impacts-under-free/21019652 ; ulna fracture from an axe ~**15 J** — https://link.springer.com/10.1007/s00414-019-02022-3 ; plate armour 1.5 mm ≈ 110 J, 2 mm ≈ 175 J, mail ≈ 200 J (Williams, secondary) — https://acoup.blog/2019/06/21/collections-punching-through-some-armor-myths/ |
| **Peak force / pressure** (N, N/m²) | Local fracture, laceration; depends heavily on contact area & padding | Skull fracture "5.1 kN" threshold used by Beránek et al. 2020 — https://www.mdpi.com/1660-4601/17/21/7782 |
| **Momentum / impulse** (kg·m/s, N·s) | Gross body/head ΔV → knockback, rotational head acceleration → concussion | Viano: boxers hit at similar speed to NFL concussive impacts, but much lower punch mass → much lower head ΔV — https://link.springer.com/doi/10.1007/1-4020-3796-1_12 |
| **Contact duration** (ms) | Converts impulse to force (F_avg ≈ Δp/Δt); short duration → high peak force but lower head ΔV / HIC | Boxing HIC < NFL concussion HIC "because of shorter duration acceleration" — https://bjsm.bmj.com/content/39/10/710.full |

Illustration **[derived]**: a 9 mm bullet carries ~500 J but only ~2.7 kg·m/s; an elite punch carries
~120 J but ~26 kg·m/s. The bullet concentrates energy into a tiny area (penetration); the punch moves
the head (concussion/knockdown). A game model therefore needs at least *energy* (penetrating /
fracturing damage), *momentum* (knockback, stun/concussion), and a *contact-area/sharpness* factor.

### 1.3 Measurement methods give very different numbers

| Method | What it actually measures | Typical bias |
|---|---|---|
| Instrumented dummy (Hybrid III head, load cells; equilibrium) | Force & acceleration of a ~human head/neck | Most biofidelic for head strikes; Hybrid III jaw biofidelity questioned — https://pubmed.ncbi.nlm.nih.gov/16183766/ |
| Boxing dynamometer / wall pad with triaxial load cell | Force into a rigid, heavy target | Higher peak forces than into a mobile head; Atha's 4096 N into target ⇒ estimated 6320 N "to the human head" — https://pubmed.ncbi.nlm.nih.gov/3936571/ |
| Accelerometer in hanging bag, F = m_bag·a | Bag CoM acceleration | Sensitive to bag mass/fill; can give very large values (e.g. ~6400–14 000 N for kicks) |
| Force plate under the striker | **Ground reaction**, not impact force | Much lower (~1–2 kN); not comparable to impact force |
| Motion capture / high-speed video | Limb/implement velocity | Peak segment velocity often occurs *before* impact |
| IMU suits | Velocity + model-estimated force | Force is an estimate, not a measurement |
| Ballistic pendulum (forensic) | Impact energy, target-independent | Best for implement energy (Siegenthaler/Sprenger studies) |

The 2024 kicking review explicitly attributes its 122.6–9015 N force spread to "diverse investigation
methodologies" — https://mdpi.com/2075-4663/12/3/74 .

---

## 2. Punches

### 2.1 Primary measurements

| Strike / population | Velocity (m/s) | m_eff (kg) | Peak force (N) | Other | Method | Source |
|---|---|---|---|---|---|---|
| Straight punch, 7 Olympic boxers, 5 weight classes (18 punches) | **9.14 ± 2.06** | **2.9 ± 2.0** | **3427 ± 811** | Energy transfer 17.2 (unit not visible in snippet; presumably J) ; power 6574 ± 3453 W; head 58 ± 13 g, 6343 ± 1789 rad/s²; neck shear 994 ± 318 N | Hybrid III head + high-speed video | https://pubmed.ncbi.nlm.nih.gov/16183766/ ; https://www.semanticscholar.org/paper/Biomechanics-of-the-head-for-Olympic-boxer-punches-Walilko-Viano/edbd929ed7812c983b4780fc106ecdf716b58a30 |
| Hook, 11 Olympic boxers 51–130 kg (78 blows incl. hooks, uppercuts, straights) | **11.0 ± 3.4** (ΔV of hand) | — | **4405 ± 2318** (highest of punch types) | Lower effective mass than football impacts ⇒ lower head ΔV | Hybrid III | Viano et al. 2005 (Neurosurgery, Part 10) via https://www.semanticscholar.org/paper/Biomechanics-of-the-head-for-Olympic-boxer-punches-Walilko-Viano/edbd929ed7812c983b4780fc106ecdf716b58a30 and https://link.springer.com/doi/10.1007/1-4020-3796-1_12 |
| Hook (pendulum-simulated heavyweight punches, 151 impacts) | — | — | **4289** | Duration **13.6 ms** (shortest); head 72.0 g; HIC 103.2. Oblique hook: 31.1 rad/s, neck force 1652 N. Cross: highest neck moment 99.8 N·m | Pendulum → Hybrid III | Bartsch et al. 2009 abstract — https://ibrc.osu.edu/wp-content/uploads/2014/01/Bartsch_Abstract_2009.pdf |
| Straight punch, 1 world-ranked heavyweight pro | **8.9** | — | **4096** peak (into target), reached within **14 ms**; estimated **6320** to a human head | — | Instrumented padded ballistic-pendulum target | Atha et al. 1985 — https://pubmed.ncbi.nlm.nih.gov/3936571/ |
| Lead hook, amateur boxers (6 punch types) | **11.95 ± 1.84** peak fist (highest) | — | — | Uppercuts: highest shoulder angular velocity | 3D motion capture | https://www.researchgate.net/publication/327906831_An_analysis_of_the_three-dimensional_kinetics_and_kinematics_of_maximal_effort_punches_among_amateur_boxers |
| Rear-hand straight: elite / intermediate / novice boxers (7/8/8) | — | — | **4800 ± 227 / 3722 ± 133 / 2381 ± 116** | — | Boxing dynamometer (triaxial load cell + manikin) | Smith et al. 2000, J Sports Sci 18:445 — https://www.sponet.de/sponet/Record/4004380?lng=en |
| Lead-hand straight (jab): elite / intermediate / novice | — | — | **2847 ± 225 / 2283 ± 126 / 1604 ± 97** | — | same | same |
| Muay Thai men (n=15, 67.7 kg): jab / cross | — | — | mean **3094 ± 69 / 5009 ± 76** | — | Load cell in wall bag | Kim et al. 2018, tabulated at https://pmc.ncbi.nlm.nih.gov/articles/PMC11769062/table/sports-13-00012-t001 |
| Trained boxers: cross vs jab | — | — | GRF **1709 vs 1177** (ground reaction, not impact) | Fist accel 94.3 vs 66.1 m/s² | Force plate + accelerometer | Mosler et al. 2024 — https://mdpi.com/2076-3417/14/7/2830 |
| Kung fu palm strike, experts vs non-practitioners | **6.67 ± 1.42 vs 5.04 ± 0.57** | **2.62 ± 0.3 vs ~1.33** | — | — | Accelerometer + video | Neto et al. 2007 (secondary) — https://www.semanticscholar.org/paper/The-role-of-effective-mass-and-hand-speed-in-the-of-Neto-Magini/bc013a2dfb83f9bc6d7acb5f6bdd740767ee32d5 **[unverified]** |
| Elite vs junior boxers (15/8), cross/hook/uppercut | elite faster for all three | — | elite higher for all three | — | 17-IMU suit (force estimated) | Dinu & Louis 2020 — https://www.frontiersin.org/articles/10.3389/fspor.2020.598861/full (tables not retrieved) |
| MMA ground-and-pound (kneeling), men: straight punch / palm / elbow | — | — | ~**3550 / 4750 / 4490** mean peak | ~36 % of men's elbow & palm strikes exceed 5.1 kN; elbow = highest impulse, palm = highest peak | Force plate target on floor | Beránek et al. 2020/2022 — https://www.mdpi.com/1660-4601/17/21/7782 ; https://mdpi.com/2075-4663/10/12/205 ; values via https://agentmma.com/mma-lab/how-hard-mma-fighters-hit **[unverified]** |

Untrained people: no measured peak-force figure was found. Lenetsky et al. 2018 measured untrained
participants (https://www.sponet.de/sponet/Record/4050179?lng=en) but the abstract gives no values.
Novice boxers (1604–2381 N) are an upper bound; a calculator site claims ">750 N" for untrained
(https://cache.omnicalculator.com/sports/human-punch-force, weak).

### 2.2 Derived punch energies and momenta **[derived]**

| Case | m_eff (kg) | v (m/s) | KE = ½mv² (J) | p = mv (kg·m/s) | Notes |
|---|---|---|---|---|---|
| Untrained / novice | 1.3 | 5.0 | **~16** | 6.5 | Neto novice inputs |
| Trained martial artist palm | 2.6 | 6.7 | **~58** | 17 | Neto expert inputs |
| Olympic straight (mean) | 2.9 | 9.14 | **~121** | 26.5 | Walilko means |
| Olympic straight, heavy class (+1 SD m_eff) | 4.9 | 9.14 | ~205 | 45 | **[assumed]** upper tail |
| Olympic hook | 2.9 **[assumed same]** | 11.0 | **~175** | 32 | Viano hook velocity |
| Jab | ~1.5–2 **[assumed]** | ~8–10 | ~50–100 | 12–20 | force ~60 % of cross (Smith 2000) |

Note Walilko's measured *energy transferred* to the head (~17 J) is ~15 % of the fist KE estimate:
most of the KE is absorbed by glove/fist/arm deformation and the head's motion, not delivered as
tissue work. Average force check: p/Δt = 26.5 / 0.014 s ≈ 1.9 kN average for ~3.4–4.1 kN peak —
consistent with a roughly half-sine pulse.

Contact duration: ~**14 ms** to peak for a heavyweight pro (Atha), **13.6 ms** for a hook (Bartsch);
glove-on-impactor time-to-peak ~16–19 ms (garbled snippet, https://epub.ub.uni-muenchen.de/76042/1/76042.pdf
and related Springer study https://link.springer.com/article/10.1007/s00414-020-02440-8: fist
punch had the *longest* impact duration, palm strike the shortest).

---

## 3. Kicks, knees, elbows, headbutt

| Strike / population | Velocity (m/s) | Force (N) | Energy / other | Method | Source |
|---|---|---|---|---|---|
| **All kicks (review of 88 studies)** | foot **5.2–18.3**; roundhouse fastest (**18.3**) | mean **122.6–9015**; side kick highest (**9015**) | — | mixed (heterogeneous) | Corcoran et al. 2024, Sports 12:74 — https://mdpi.com/2075-4663/12/3/74 |
| Taekwondo roundhouse & back kick | — | **8252 ± 720** / **8023 ± 836** | — | (2007 study cited in JSSM 2009) | https://www.jssm.org/jssm-08-CSSI3-13.xml>Fulltext (via search snippet) |
| Taekwondo turning kick | — | **~6400** | — | accelerometers in sandbag | same JSSM 2009 |
| ITF Taekwon-Do turning kick | toe **13.4 ± 1.6** | **292 ± 54** | — | dissertation, target method unspecified | https://www.members.itkd.co.nz/reference/essays/12-study_of_turning_kick.pdf |
| Elite TKD roundhouse (n=9) | — | front-leg vertical GRF ~1600 | — | **force plate** (GRF, not impact) | An Hsieh et al. 2012 — https://ojs.ub.uni-konstanz.de/cpa/article/view/5386 |
| Roundhouse: karate / Muay Thai / TKD | — | **1211 / 1400 / 1547** | — | (per review table) | https://pmc.ncbi.nlm.nih.gov/articles/PMC11769062/table/sports-13-00012-t001 |
| Muay Thai roundhouse (middle kick strongest) | ankle velocity r = .86 with peak force, r = .79 with impulse | **~14 000** peak **[unverified]** | — | triaxial accelerometer in bag + motion capture | Sidthilaw 1996/97 — https://openaccess.library.uitm.edu.my/Record/ndltd-ORGSU-oai-ir.library.oregonstate.edu-1957-34396 |
| Karate front kick (mae geri), black belts: elite vs sub-elite | **9.5 ± 0.8 vs 8.5 ± 0.8** | — | KE **155.9 ± 54.1 vs 124.4 ± 34.1 J** | motion capture (segment KE) | 2024 study — https://www.preprints.org/manuscript/202306.1519/v1/download (search-surfaced; exact paper ID uncertain) |
| Mae geri | up to **19.3** (other study) | **1082–1208** | — | karate review | same review snippet |
| Front vs roundhouse | — | front kick force > roundhouse at novice, sub-elite, elite levels | — | systematic review | Vagner et al. 2023 — https://research.stmarys.ac.uk/id/eprint/6037 |
| TKD reverse punch / roundhouse / side / spinning back kick (1988 US Olympic team) | roundhouse fastest | roundhouse ~92.5 kgf ≈ **907 N** (one subject) | spinning back kick reported as most forceful **[weak source]** | target dynamometer | Pieter & Pieter 1995 — https://pacificinternationaltaekwondo.com.au/?p=7715 ; https://gradesfixer.com/free-essay-examples/the-effects-of-taekwondo-striking/ |
| Muay Thai knee (n=15) | — | mean **9482 ± 153** (vs cross 5009) | — | load cell in wall bag | Kim et al. 2018 — https://pmc.ncbi.nlm.nih.gov/articles/PMC11769062/table/sports-13-00012-t001 |
| Muay Thai knee after core training | — | **1240 ± 89** | — | unclear | Lee 2016 — https://www.backfitpro.com/medical-scientific-articles/2016-2017/[1]-Lee,B.-(2016)-The-effect-of-core-training-on-distal-limb-performance-during-ballistic-maneuvers-[J.Sport-Sci.].pdf |
| MMA elbow (ground-and-pound) | — | ~**4490** mean peak (men); highest impulse of strikes | — | floor force plate | see §2.1 Beránek |
| Headbutt | measured (volunteers, with/without soccer heading experience; heading skill did not change velocity) — values not retrieved | — | "typical headbutt probably won't kill"; lethal cases occur | head → soccer-ball surrogate | Int J Legal Med study via https://www.smithsonianmag.com/smart-news/how-dangerous-is-hitting-another-human-being-with-your-head-925279/ |
| Head-to-head (football) | **1.5–3.0** | — | concussion risk up to 67 % | lab reconstruction | https://bjsm.bmj.com/content/39/suppl_1/i49.full |

Derived kick energies **[derived]**:
- Mae geri effective mass implied by its KE/velocity: 2·155.9 / 9.5² ≈ **3.5 kg** (elite).
- Roundhouse at 13–18 m/s with m_eff 3–5 kg **[assumed]**: **250–800 J** — upper bound; peak segment
  speeds precede impact, so delivered KE is likely nearer the lower end. Momentum 40–90 kg·m/s.
- Knee: m_eff 5–10 kg **[assumed]** at 4–6 m/s **[assumed]** → 40–180 J, but very high momentum
  (consistent with Kim's knee ≈ 2× cross force).
- Headbutt: head+neck m_eff 4–6 kg **[assumed]** at 2–4 m/s **[assumed]** → ~10–50 J; momentum 8–24 kg·m/s.
  Note the low end already reaches the 11–14 J skull-fracture energy, but forehead-to-face contact
  area/stiffness matter more than energy here.

---

## 4. Implements

| Implement | Mass (kg) | Velocity (m/s) | KE (J) | Momentum (kg·m/s) | Notes / method | Source |
|---|---|---|---|---|---|---|
| **Long sticks/pipes, men** (13 volunteers, 1170 strikes) | optimum ~1.3 kg (1 m object, CoM in far quarter) | — | **67.3–311.5** (means by object) | — | Horizontal strikes into heavy ballistic pendulum; energy peaks for 0.3–0.4 m objects | Sprenger et al. 2016, Int J Legal Med 130:835 — https://www.springermedicine.com/the-influence-of-striking-object-characteristics-on-the-impact-e/21018112 |
| same, women | optimum 1.65–2.2 kg | — | **30–202.6** | — | Men +84 % on average, driven by velocity, not mass | same |
| Combination wrench / Al pipe / golf club / spade, **men** (11 volunteers, 880 strikes) | — | — | **51.1 / 74.4 / 93.5 / 166.7** (means) | — | Pendulum; impact velocity × "fictive impact mass" | Siegenthaler et al. 2018, Int J Legal Med 132:211 — https://www.springermedicine.com/impact-energy-of-everyday-items-used-for-assault/21018962 |
| same, **women** | — | — | **33.0 / 41.0 / 56.5 / 76.8** | — | — | same |
| **Baseball bat (MLB swing)** | bat ~0.9 **[assumed, typical 32 oz]**; m_eff at sweet spot < actual mass | sweet-spot speed avg **~32** (71.5–72 mph); elite **37.4** (83.7 mph, Stanton) | **[derived]** m_eff 0.5–0.9 kg → **~260–460 J** (avg), up to ~630 J (elite, 0.9 kg) | 16–34 | Statcast bat tracking (sweet spot = 6 in from tip); bat–ball contact ~**0.5 ms** | https://www.mlb.com/news/mlb-bat-speed-leaders-for-2024 ; https://global.espn.com/mlb/story/_/id/40120458/mlb-statcast-bat-tracking-data-giancarlo-stanton-luis-arraez ; https://www.physics.sydney.edu.au/~cross/baseball.html ; collision time: https://lecdem.physics.umd.edu/tools-and-resources/lecdem-blog/502-bat-blog-oct2020.html |
| Bat used for assault (untrained, against a person) | — | — | likely in the Sprenger range (≈100–300 J) **[inference]** | — | Untrained horizontal strikes ≪ MLB bat speed | Sprenger 2016 above |
| **Framing hammer** (28 oz) | 1.09 | ~10 | **~55** | ~11 | Manufacturer illustrative figure, not a measurement | US patent 8534643 — https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/8534643 |
| **Sledgehammer** (16 lb) | 7.3 (head mass; m_eff lower for a two-handed swing) | 5–10 **[assumed]** | **[derived]** **~90–365** | 36–73 | No peer-reviewed swing-velocity measurement found | (arithmetic only; https://www.physicsforums.com/threads/how-much-energy-do-i-use-when-swinging-a-sledge-hammer.562004 is anecdotal) |
| **Sword / axe blow** | longsword ~1.2–1.5 **[assumed]**; m_eff at percussion point < total | tip ≤ ~**50** (practical ceiling); 1000–2000 °/s angular; cut arc < 50 ms | **60–130 J** (Williams estimate, sword or axe) | — | Secondary citation of A. Williams, *The Knight and the Blast Furnace* | https://acoup.blog/2019/06/21/collections-punching-through-some-armor-myths/ ; https://www.tf.uni-kiel.de/matwis/amat/iss/kap_c/backbone/rc_4_4.html ; https://science-and-fiction.org/swordfighting/cuts.html |
| Axe vs forearm (parry) | — | — | ulna fracture ~**15 J** | — | Axe-blade sections on sheep radii / synthetic bone | https://link.springer.com/10.1007/s00414-019-02022-3 |
| Machete / axe / cleaver on bone | — | — | high energy at impact, but flesh acts as shock absorber; secondary fractures reflect lower energy | — | Pig limbs (2009 J Forensic Sci) | https://ojp.gov/ncjrs/virtual-library/abstracts/microscopic-indicators-axe-and-hatchet-trauma-fleshed-and-defleshed |
| **Thrown baseball** (MLB 4-seam fastball) | 0.145 **[assumed, regulation 5–5.25 oz]** | **42.2** (94.5 mph, 2025) – **42.4** (94.8 mph, 2026 avg) | **[derived] ~130** | ~6.1 | Statcast radar/optical; humerus internal rotation > 9000 °/s (Roach 2013, Nature 498:483) | https://www.clickorlando.com/sports/2026/09/29/the-fast-get-faster-mlb-pitchers-again-set-fastball-velocity-record-by-averaging-948-mph/ ; https://phys.org/news/2013-06-fastest-articulated-motion-human.pdf |
| **Thrown rock** (hand-sized, 0.3–0.5 kg **[assumed]**) | 0.3–0.5 | 15–25 **[assumed]** | **[derived] ~35–155** | 4.5–12.5 | No measured release velocity retrieved. Cave of Hearths: 81 % of Acheulean spheroids can inflict "worthwhile damage" on an impala-sized animal at ≤ 25 m (expert-thrower simulation) | Wilson et al. 2016, Sci Rep — https://www.nature.com/articles/srep30614 |
| **9 mm pistol bullet** (115 gr FMJ) | 0.00745 | **343–390** (1125–1280 fps) | **~450–570** (335–418 ft·lbf) | ~2.6–2.9 | Manufacturer chronograph data | https://www.luckygunner.com/9mm-115-grain-fmj-american-ballistics-50-rounds ; https://www.opticsplanet.com/sellier-bellot-pistol-revolver-ammo-9mm-luger-115-gr-fmj.html ; https://le.vistaoutdoor.com/ammunition/federal/handgun/details.aspx?id=94 |

---

## 5. Consolidated scale (for game tuning)

Order-of-magnitude baselines. "Src" = directly measured in a cited study; others derived/assumed above.

| Strike | KE (J) | Momentum (kg·m/s) | Peak force (N) | Contact (ms) |
|---|---|---|---|---|
| Untrained punch | ~15–30 | ~6–10 | < 1600 (below novice boxers) | ~15–20 |
| Novice boxer cross | ~40–70 | ~12–18 | 2381 (src) | ~15 |
| Elite straight punch | ~120 (≈17 J delivered to head, src) | ~26 | 3400–4800 (src) | ~14 (src) |
| Elite hook | ~175 | ~32 | 4300–4400 (src) | 13.6 (src) |
| Elbow (MMA) | ~50–150 | — | ~4500 (src, unverified) | — |
| Front kick (karate elite) | ~156 (src) | ~33 | ~1100–1200 (src) | — |
| Roundhouse kick | ~250–800 (upper bound) | 40–90 | 1200–8250 (src, method-dependent) | — |
| Side kick | — | — | up to 9015 (src) | — |
| Muay Thai knee | ~40–180 | high | ~9500 into wall bag (src) | — |
| Headbutt | ~10–50 | 8–24 | — | — |
| Everyday item (wrench → spade), man | 51–167 (src) | — | — | — |
| Stick/pipe, man | 67–312 (src) | — | — | — |
| Sword/axe blow | 60–130 (secondary src) | — | — | — |
| Framing hammer | ~55 | ~11 | — | — |
| Sledgehammer | ~90–365 | 36–73 | — | — |
| Baseball bat (MLB) | ~260–630 | 16–34 | — | ~0.5 (vs ball) |
| Fastball | ~130 | ~6 | — | ~0.5 |
| Thrown rock | ~35–155 | 4–13 | — | — |
| 9 mm bullet | ~450–570 (src) | ~2.7 | — | — |

Damage thresholds for comparison: skull fracture ~11–14 J (blunt) or ~5.1 kN force; ulna fracture
~15 J (axe); 1.5 mm plate ~110 J, 2 mm plate ~175 J, mail ~200 J (edged, secondary source).

**Modelling implications.**
1. Use m_eff, not body mass, for unarmed strikes; scale m_eff with skill (≈1.3 → 3 kg hands; ~3.5 kg+ legs).
2. Force numbers from different methods are not interchangeable; prefer energy (pendulum/video) and
   momentum for game math, and treat "peak force" as an output of KE, contact stiffness and padding.
3. Separate damage channels: energy × sharpness/area → tissue/bone damage and armour penetration;
   momentum (and short contact time → rotational acceleration) → stagger/knockdown/concussion.
4. Implements win by raising v at the contact point (and, for hammers/axes, concentrating area), not
   by raising m_eff — Sprenger found impact energies peak for ~0.3–0.4 m, ~1.3 kg objects for men.

## 6. Gaps / to verify with full text
- Walilko 2005 per-weight-class table and the exact unit/definition of "energy transfer 17.2".
- Viano 2005 (Neurosurgery Part 10) hook/uppercut effective mass.
- Corcoran 2024 per-kick tables (roundhouse/front/side/back/axe ranges).
- Uppercut force/velocity: not found as a separate figure.
- Spinning back kick velocity: not found.
- Headbutt velocity (Int J Legal Med): not retrieved.
- Measured sledgehammer, sword, axe, machete swing velocities: not found in peer-reviewed form.
- Measured untrained-person punch force: not found (Lenetsky 2018 full text needed).
