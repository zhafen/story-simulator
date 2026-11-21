# Strike trajectory profiles: end-effector position/velocity vs time

How the striking fist/foot moves from movement onset to contact, and which simple
analytic shape a game model should use. Companion to `b3_strike_energies.md` and
`b1_b2_human_performance.md`.

**Source caveat.** This sandbox's network policy blocked full-text fetches from every
academic host tried (pmc.ncbi.nlm.nih.gov, www.ncbi.nlm.nih.gov, frontiersin.org,
ojs.ub.uni-konstanz.de, clok.uclan.ac.uk). **Every number below comes from search-engine
abstracts or snippets, not from reading the papers' tables or figures.** Each row cites the
URL the snippet came from. Some snippets were ambiguous; those cases are flagged. No paper
whose full time series could be digitised was reachable, so the shape conclusions combine
scalar timing markers (time-to-peak as % of movement, peak vs contact speed, acceleration vs
deceleration durations) with motor-control theory.

---

## 1. Measured kinematics

### 1.1 Punches

| Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|
| Lead straight (jab), **peak** fist velocity, elite vs junior | 7.16 ± 0.48 vs 6.32 ± 0.42 | m/s | Vicon mocap + force plates, 16 boxers | https://pmc.ncbi.nlm.nih.gov/articles/PMC9798280/ (Liu et al. 2022, Front Physiol 13:1015154) |
| Lead straight, **contact** velocity, elite vs junior | 5.56 ± 0.61 vs 4.87 ± 0.39 | m/s | same | same (group order inferred from snippet) |
| Contact / peak speed ratio (derived) | ≈ 0.78 (elite), 0.77 (junior) | – | derived from the two rows above | same |
| Authors' interpretation | "sequential acceleration-braking"; deceleration rate is a measured index | – | same | same |
| Single maximal punch, contact speed (all types pooled) | 9.26 ± 2.09 | m/s | 3-D mocap, 10 competitors | https://sponet.de/sponet/Record/4021264?lng=en (Piorkowski, Lees & Barton 2011, Sports Biomech) |
| Same, combination punches | 7.49 – 8.01 (± ~2.4) | m/s | same | same |
| Hooks vs straights | hooks faster at contact; jab/cross delivery time significantly shorter | – | same | same |
| Straight punch delivery time / fist speed (review summary) | 357 ± 178 ms; 5.9 – 8.22 m/s | ms; m/s | review of mocap studies | https://core.ac.uk/download/189160975.pdf |
| Hook delivery time / fist speed (review summary) | 477 ± 203 ms; 8 – 11 m/s | ms; m/s | same | same |
| Lead hook peak fist velocity | 11.95 ± 1.84 | m/s | mocap + force plates | https://ideas.repec.org/a/taf/rpanxx/v18y2018i5p835-854.html (Int J Perf Anal Sport 2018) |
| Jab delivery time | "405 ± 0.15 ms" (units garbled in snippet) | ms | same | same |
| Olympic boxers, straight punch hand velocity at impact | 9.14 ± 2.06 | m/s | high-speed video, Hybrid III dummy, 7 boxers | https://pubmed.ncbi.nlm.nih.gov/16183766/ (Walilko, Viano & Bir 2005) |
| Effective punch mass | 2.9 ± 2.0 | kg | same | same |
| Fist velocity just before impact / effective mass | 11.5 m/s; ≈ 4.1 kg | m/s; kg | bag momentum method | https://arxiv.org/pdf/2607.18276 (snippet quoting a boxing study) |
| Karate gyaku-zuki: punch time, peak wrist velocity (two clusters) | 0.26 ± 0.04 s, 6.93 ± 1.12 m/s; 0.27 ± 0.04 s, 7.65 ± 0.86 m/s | s; m/s | 3-D video 150 Hz, 8–9 elite athletes, 39 trials | https://ojs.ub.uni-konstanz.de/cpa/article/view/3410 (Suwarganda et al., ISBS) |
| Gyaku-zuki duration and fist speed | < 400 ms; ≈ 8 m/s | ms; m/s | ISBS 2008, 3 athletes | https://ojs.ub.uni-konstanz.de/cpa/article/view/1937 |
| **Time of peak wrist velocity, % of movement time** (reverse punch, 4 styles) | 80 % (Shotokan, 8.58 m/s); 94 % (TKD, 9.97 m/s); 95 % (Kempo); one other 84 % (3.81 m/s) | % of MT | 100 Hz film, 1 black belt per style | https://ojs.ub.uni-konstanz.de/cpa/article/view/1805 (Stull & Barham 1988); attribution of individual values to styles is inconsistent between snippets |
| Time of peak shoulder velocity, same study | 53 – 84 % (Kung-fu 3.23 m/s at 80 %) | % of MT | same | same |
| Time of peak hip velocity (Kempo) | 1.11 m/s at 75 % | % of MT | same | same |
| **Accel vs decel duration**: positive-acceleration phase > 50 % of punch | in 96.4 % of trials | % trials | accelerometer, 5 karateka | https://ojs.ub.uni-konstanz.de/cpa/article/view/1161 (Emmermacher, Witte & Hofmann 2005) |
| Phase model of gyaku-zuki | 4 phases; phase III = fist deceleration to velocity minimum | – | ISBS 2008 | https://ojs.ub.uni-konstanz.de/cpa/article/view/1161/1049 (snippet) |
| Elite vs sub-elite gyaku-tsuki | elite brake in less time | – | mocap | https://doaj.org/article/55b0ac82a4e14f2b8bfa10d454174754 (Biomechanics 2023) |
| Proximal-to-distal sequencing in punches | legs → pelvis → trunk → arm, "peaking at the fist" | – | review | https://pmc.ncbi.nlm.nih.gov/articles/PMC7739747 |
| Karate punch: activity inside ≈ 400 ms, proximal-to-distal activation | – | ms | kinematics + EMG | https://dspace.uevora.pt/rdpc/bitstream/10174/10609/1/Brito_Fernandes_2011_21_1023_JEKinesiology_Kinematic-and-electromyographic-analyses-of-a-karate-punch.pdf (Vences-Brito et al. 2011) |
| Elite karate: sequential vs simultaneous joint-peak clusters | both patterns occur; sequential cluster is male-dominated (83 %) and faster | – | 3-D video | https://ojs.ub.uni-konstanz.de/cpa/article/view/3410 |

### 1.2 Kicks

| Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|
| Roundhouse: proximo-distal pattern; foot takes longest to reach peak and has highest peak | p < 0.01 | – | 8-camera mocap + 2 force plates, 10 TKD athletes | https://johk.pl/?p=3440 (Estevan et al. 2015, J Hum Kinet 47:41) |
| ITF roundhouse, time to target: board vs air | 0.58 ± 0.01 vs 0.67 ± 0.01 | s | Smart-D, 6 athletes | https://pubmed.ncbi.nlm.nih.gov/26898602/ (Acta Bioeng Biomech 2015) |
| Same, **maximal** foot velocity: board vs air | 10.61 ± 0.86 vs 14.61 ± 0.67 | m/s | same | same |
| TKD maximal kick velocity | ≈ 16 | m/s | stereo photogrammetry | https://pmc.ncbi.nlm.nih.gov/articles/PMC10974023 (citing Moreira et al. 2016) |
| Combat-sport foot velocity range across 5 strikes; roundhouse highest | 5.2 – 18.3 | m/s | systematic review | https://pmc.ncbi.nlm.nih.gov/articles/PMC10974023 |
| Roundhouse execution time (TKD, including more than the strike phase) | 1.54 ± 0.52 | s | mocap, Gavagan & Sayers 2017 | https://pmc.ncbi.nlm.nih.gov/articles/PMC5571909 |
| Foot velocity at impact vs relative impact force | r = 0.66 | – | same | same |
| **Side kick peak foot velocity and its timing** | ≈ 5.65 m/s at ≈ **82 % of leg extension** | m/s; % | 3-D, ITF TKD (Wąsik) | https://johk.pl/?p=2136 |
| Side kick, older literature value | 12.84 – 16.26 | m/s | Pieter & Pieter 1995, cited in same | same |
| Side kick, experienced vs novice | foot peak linear velocity 28 % higher | – | mocap 2025 | https://www.frontiersin.org/articles/10.3389/fphys.2025.1708748 |
| High front kick dynamics | thigh decelerates through motion-dependent moments from shank, not by active braking; shank accelerated by knee-extensor moment plus thigh-velocity interaction | – | high-speed film + inverse dynamics + EMG, 17 TKD | https://pubmed.ncbi.nlm.nih.gov/8981287/ (Sørensen et al. 1996) |
| Shank max angular velocity at ≈ 60° knee flexion, thigh angular velocity ≈ 0 | – | deg | secondary summary of Sørensen | https://ojs.ub.uni-konstanz.de/cpa/article/view/2760 |
| Mae-geri peak phase duration (air / target / opponent) | 0.016 / 0.023 / 0.028 | s | Kyokushin mocap | https://pubmed.ncbi.nlm.nih.gov/31470588/ |
| Mae-geri whole kick | within ≈ 600 ms | ms | mocap + EMG | https://pmc.ncbi.nlm.nih.gov/articles/PMC6747486 |
| Jumping axe kick | **no** prevalent proximal-to-distal sequence | – | mocap, 22 athletes | https://jssm.org/15-1-92.p_d_f |

### 1.3 What the measurements say about shape

1. **The velocity peak is late.** The wrist peaks at 80–95 % of movement time
   ([Stull & Barham](https://ojs.ub.uni-konstanz.de/cpa/article/view/1805)) and the side-kick
   foot at ≈ 82 % of extension ([Wąsik](https://johk.pl/?p=2136)). The acceleration phase is
   longer than the deceleration phase in 96 % of reverse punches
   ([Emmermacher 2005](https://ojs.ub.uni-konstanz.de/cpa/article/view/1161)). This is far
   from a symmetric bell, where the peak falls at 50 %.
2. **The peak is often just before contact, not at contact.** For a jab against a target,
   contact speed is ≈ 78 % of peak speed
   ([Liu 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9798280/)). For a roundhouse, the peak
   is lower with a target than in air (10.6 vs 14.6 m/s,
   [Acta Bioeng Biomech 2015](https://pubmed.ncbi.nlm.nih.gov/26898602/)). Fighters brake
   before or at full extension to protect the elbow and knee, and possibly to stiffen the limb
   for effective mass. **Inference, not measured:** when the target sits short of full
   extension, contact falls near the peak. When contact is at full extension, a braking tail
   costs roughly 20 % of peak speed.
3. **Peak-speed-to-mean-speed ratio.** The ratio n = v_peak · T / D is the single number that
   separates the candidate shapes. Typical values (inference, assuming D ≈ 0.5–0.6 m for a
   punch, as no snippet reported reach distance):
   - karate 0.26 s, 7.65 m/s gives n ≈ 3.3–4.0;
   - straight punch 0.357 s, about 7 m/s gives n ≈ 4.2–5.0.

   For the ITF roundhouse, assuming a foot path of about 1.5–2 m: 0.58 s at 10.6 m/s gives
   n ≈ 3–4. A symmetric point-to-point reach has n = 1.875 (minimum jerk). Constant power has
   n = 1.5 and constant speed has n = 1. **Real strikes are strongly back-loaded (n ≈ 3–5).**
   Part of this comes from a preparation phase in which the trunk and hips rotate while the
   fist or foot barely moves along the strike line.
4. **Kinetic chain.** Segment peak speeds rise and peak in proximal-to-distal order for punches
   ([PMC7739747](https://pmc.ncbi.nlm.nih.gov/articles/PMC7739747)) and roundhouse kicks
   ([Estevan 2015](https://johk.pl/?p=3440)). Two exceptions: some elite punchers fire joints
   near-simultaneously ([Suwarganda](https://ojs.ub.uni-konstanz.de/cpa/article/view/3410)),
   and axe kicks do not follow the pattern ([JSSM](https://jssm.org/15-1-92.p_d_f)). In whip
   kicks, the thigh's slow-down is passive. It is caused by the accelerating shank
   ([Sørensen 1996](https://pubmed.ncbi.nlm.nih.gov/8981287/)). This is why the foot's speed
   keeps rising steeply until late in the kick.

---

## 2. Theory and motor-control models

| Model / result | Content | Shape implication | Source |
|---|---|---|---|
| Minimum jerk (Flash & Hogan 1985) | x(τ) = D(10τ³ − 15τ⁴ + 6τ⁵), τ = t/T; straight paths with bell-shaped speed | Peak at τ = 0.5, v_peak = 1.875 D/T (from differentiating the polynomial); v = 0 at the target | https://pmc.ncbi.nlm.nih.gov/articles/PMC6565116, https://pmc.ncbi.nlm.nih.gov/articles/PMC3470860 |
| Speed-dependent asymmetry (Nagasaki 1989) | relative time to peak k ≈ 0.5 at intermediate speed; **k > 0.5 for ballistic movements**, < 0.5 for slow; constrained minimum jerk explains it | Fast movements peak later | https://link.springer.com/doi/10.1007/BF00248865 |
| Asymmetry at high speed | bell is not always symmetric; peak shifts at very high speeds | – | https://core.ac.uk/download/213622184.pdf (Todorov 1998) |
| Hitting/interception | bell-shaped for fast targets in lab tasks. Hitting can be biphasic (back-swing, then strike), with impact velocity controlled separately from peak strike velocity. VITE-type models add explicit velocity-at-interception control | Strikes are not point-to-point: v(contact) ≠ 0 | https://research.vu.nl/en/publications/bi-phasic-hitting-with-constraints-on-impact-velocity-and-tempora/, https://brain.umn.edu/assets/story_file_104 |
| Optimal timing for throwing (Alexander 1991) | two-muscle models; an optimal proximal→distal activation delay maximises release speed. It can be longer than the delay that maximises total work | End-point speed rises late, through sequenced energy transfer | https://scilit.net/publications/c44663eb16956944d38ecd0be654a192 |
| Muscle-driven throw optimisation (Chowdhary & Challis) | proximal-to-distal activation appears in many but not all optimal throws; depends on projectile mass and anthropometry | – | https://pure.psu.edu/en/publications/the-biomechanics-of-an-overarm-throwing-task-a-simulation-model-e/ |
| Putnam 1993 (J Biomech 26 S1:125) | sequential segment motion explained by motion-dependent interaction moments. Proximal deceleration is largely a *reaction* to distal acceleration, not a deliberate braking. Upper-arm internal rotation breaks strict P→D order | Distal speed builds up multiplicatively and late | https://ojs.ub.uni-konstanz.de/cpa/article/view/2695 (secondary summary) |
| Summation of speed (Bunn 1972) | each successive segment faster than its predecessor; supported by punt-kick data, violated in a gymnastic dismount (Putnam 1980) | – | https://ojs.ub.uni-konstanz.de/cpa/article/view/3498/3291 (snippet) |
| Fitts' law | speed–accuracy trade-off for reaches that stop on a target | Applies to point-to-point reaches, not to impact-maximising strikes. Only relevant if a game wants accuracy to cost speed | (standard; no specific numbers used) |

**Theory summary.** Minimum-jerk and minimum-torque-change models describe reaches that come to
rest on a target. They predict a symmetric bell, with n = 1.875 and v = 0 at the end. Strikes
that aim to maximise speed at contact are a different optimisation problem: free terminal
velocity plus a kinetic chain. Both theory (Alexander, Putnam) and data (peak at 80–95 % of the
movement) give a monotone, sharply accelerating speed curve. The peak comes at or just before
contact, followed at most by a short braking tail. **Inference:** a speed-maximising
end-effector in a multi-segment chain behaves roughly like a "speed grows with what has
already been built up" process. This is why the exponential (v ∝ x) and high-order power laws
both fit the punch numbers.

---

## 3. Fitted analytic forms

No paper reachable through snippets published a closed-form fit (power law, polynomial,
exponential or logistic) to strike displacement or velocity versus time. The only published
analytic forms are the minimum-jerk quintic and its constrained or asymmetric variants
(Nagasaki 1989). The fits below are this document's own, calibrated to the targets.

---

## 4. Candidate shapes compared

Write the profile in normalised time s = t/T, with x(0) = 0 and x(T) = D. For any profile, the
ratio n = v(T)·T/D fixes how back-loaded it is.

| Shape | x(s) | v(T) | n | Punch (D = 0.6 m, T = 0.32 s) | Physical problems |
|---|---|---|---|---|---|
| Constant speed | D s | D/T | 1 | 1.9 m/s at contact | infinite acceleration at onset; nowhere near measured 7–12 m/s |
| Constant power | D s^1.5 | 1.5 D/T | 1.5 | 2.8 m/s | infinite acceleration at s = 0 (a ∝ s^−½); front-loaded, contradicts peak at 80–95 % |
| Exponential, τ = 0.063 s | D e^{(t−T)/τ} | D/τ | T/τ = 5.08 | 9.5 m/s; v(T/2) = 0.75 m/s; reaches 50 % of contact speed at 0.276 s | starts at x0 = 3.7 mm with v0 = 0.06 m/s, not from rest (cosmetic) |
| Minimum jerk (full) | D(10s³ − 15s⁴ + 6s⁵) | 0 | – | 0 m/s at contact | wrong task: a reach that stops on the target |
| **Power law, n ≈ 5** (recommended) | D s^n | n D/T | n | n = 5.07: 9.5 m/s; v(T/2) = 0.57 m/s; reaches 50 % of contact speed at 0.270 s | none for n ≥ 3: x, v and a are all 0 at onset |

**Punches.** The calibration targets need n ≈ 5, which agrees with the measured n of about
3.3–5. Constant speed and constant power cannot reach 9.5 m/s in 0.32 s over 0.6 m; they top
out at 1.9 and 2.8 m/s. The exponential fits because T/τ = 5.08 is the same back-loading as
n = 5. **The exponential is the best of the three for punches.** A power law s^5 is
numerically almost the same and starts exactly from rest.

**Kicks (D = 1.0 m, T = 0.3 s).** Constant power gives v(T) = 5 m/s. That matches the measured
side kick (≈ 5.65 m/s, [Wąsik](https://johk.pl/?p=2136)), but it is half to a third of
roundhouse and front-kick values (10.6 m/s against a target, 14.6 m/s in air, up to about
16–18 m/s). If constant power fit the kick calibration best, the kick target speed or energy is
probably about 5 m/s. That suits push-type kicks (side kick, teep). Whip kicks such as the
roundhouse are as back-loaded as punches: with a target, n ≈ 3 (10 m/s); in air, n ≈ 4.2
(14 m/s).

**Peak before contact.** The measured contact/peak speed ratio is ≈ 0.78 when contact is at or
near full extension. A game that always lands at full extension can either (a) treat v(T) as
the effective contact speed and calibrate to measured contact speeds, which is simplest, or
(b) add the braking tail described in §5.3.

---

## 5. Recommended form

### 5.1 Primary: power law in normalised time, shape exponent from speed

```
s = clamp(t / T, 0, 1)
x(t) = D * s**n
v(t) = (n * D / T) * s**(n - 1)
a(t) = (n * (n - 1) * D / T**2) * s**(n - 2)
n    = v_contact * T / D          # use n >= 3 so x, v, a all start at 0
```

This one-parameter family contains the other candidates:

- n = 1 is constant speed.
- n = 1.5 is exactly constant power.
- n ≈ T/τ reproduces the exponential to within a few mm and a few tenths of a m/s.

Changing one number moves a strike between "push" and "whip".

| Strike | D (m) | T (s) | v_contact (m/s) | n | a at contact (m/s²) | x(T/2) | v(T/2) (m/s) | time to reach 50 % of v_contact |
|---|---|---|---|---|---|---|---|---|
| **Punch** (calibration target) | 0.6 | 0.32 | 9.5 | **5.07** (use 5) | 121 | 18 mm | 0.57 | 0.270 s |
| Push kick / side kick | 1.0 | 0.3 | 5 | 1.5 (constant power; n < 2 gives an infinite onset acceleration) | 8 at contact | 0.354 m | 3.54 | 0.075 s |
| **Roundhouse / front kick, against a target** (recommended kick) | 1.0 | 0.3 | 10 | **3.0** | 67 | 0.125 m | 2.50 | 0.212 s |
| Roundhouse, harder (12 m/s) | 1.0 | 0.3 | 12 | 3.6 | 104 | 83 mm | 1.98 | 0.230 s |
| Roundhouse, near air-kick peak (14 m/s) | 1.0 | 0.3 | 14 | 4.2 | 149 | 54 mm | 1.52 | 0.242 s |

The punch's 170 J at 9.5 m/s implies an effective mass of 3.77 kg. That sits between the
measured 2.9 ± 2.0 kg ([Walilko 2005](https://pubmed.ncbi.nlm.nih.gov/16183766/)) and
≈ 4.1 kg ([arXiv snippet](https://arxiv.org/pdf/2607.18276)), so the energy and speed targets
are consistent with each other.

**Recommendation:** use n = 5 for punches and n = 3 for whip kicks (roundhouse or front kick
landing at about 10 m/s). Use n = 1.5 only for push kicks.

### 5.2 Alternative: delayed minimum-jerk truncated at peak velocity

This version is closer to the motor-control literature. The end-effector holds still for a
preparation phase t0, while the chain winds up. It then follows the first half of a
minimum-jerk profile, so it arrives at peak speed with zero acceleration:

```
σ = clamp((t - t0) / (T - t0), 0, 1)
x = 2 D * (10 (σ/2)**3 - 15 (σ/2)**4 + 6 (σ/2)**5)
v_contact = 1.875 * D / (T - t0)   =>   T - t0 = 1.875 D / v_contact
```

| Strike | active phase T − t0 | preparation t0 |
|---|---|---|
| Punch, 0.6 m, 9.5 m/s, T = 0.32 s | 0.118 s | 0.202 s |
| Kick, 1.0 m, 10 m/s, T = 0.3 s | 0.188 s | 0.112 s |
| Kick, 1.0 m, 12 m/s | 0.156 s | 0.144 s |

This form produces the late peak (100 % of the active phase), and acceleration is zero at
contact, matching "peak at or just before contact". The cost is a second parameter and a
visible dead time. The power law is preferred for simplicity. Its velocity curve is already
nearly flat until s ≈ 0.6, which looks like a preparation phase anyway.

### 5.3 Optional braking tail (peak before contact)

To model a peak that comes before full-extension contact, run the §5.1 profile to a peak at
s_p ≈ 0.85–0.9, then decelerate linearly so that v_contact ≈ 0.78 · v_peak
([Liu 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9798280/)). Scale D so the total distance
still lands at full extension. Only worth adding if the game distinguishes "target inside
reach" (contact near peak) from "target at full reach" (about 20 % speed loss).

---

## 6. Gaps

- No reachable source gave a digitisable fist or foot displacement or velocity time series, or
  a published analytic fit. A full-text read of Liu 2022 (peak time, deceleration rate), Estevan
  2015 (segment time-to-peak) and Piorkowski 2011 (per-punch speeds) would tighten n. These need
  pmc.ncbi.nlm.nih.gov, frontiersin.org, ojs.ub.uni-konstanz.de and clok.uclan.ac.uk allowed in
  the session's network settings.
- Reach distance D was not reported in any snippet, so the measured n values in §1.3 rest on an
  assumed D.
- Uppercut-specific timing data was not found.
