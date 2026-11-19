# B4 — Knockouts, concussion thresholds, strike counts, and torso injury thresholds

Research notes for a physics-grounded combat/damage model. Every number carries a
source URL. **Verification level:** in this session direct page fetching
(PubMed/PMC/publisher sites) was blocked by the network sandbox, so values were
taken from search-engine abstract/snippet text of the cited pages, not from a
full-text read. Rows marked **[unverified]** are values commonly quoted in the
literature that could *not* be confirmed against an abstract here — treat them
as placeholders to re-check before relying on them.

Units: g = 9.81 m/s²; rad/s² = rotational (angular) acceleration; rad/s =
rotational velocity; AIS = Abbreviated Injury Scale (1 minor … 6 unsurvivable);
HIC = Head Injury Criterion (dimensionless, from linear accel. over a 15 or 36 ms
window); ATD = crash dummy (Hybrid III); PMHS = cadaver.

---

## 1. What physical quantity best predicts a knockout / concussion?

Short answer: **no single accepted threshold exists**; rotational kinematics
(angular velocity / acceleration, and the brain strain they produce) are the
mechanistically favoured predictors for loss of consciousness, while peak
**linear** acceleration and HIC remain empirically as good or better at
*classifying* helmeted football concussions. For a game, use a combined metric
(linear + rotational), and treat rotational velocity as the main driver of
"KO" (loss of consciousness) specifically.

| Finding | Detail | Method | Source |
|---|---|---|---|
| Rotation central to KO / unconsciousness | Classic Ommaya/Gennarelli work produced unconsciousness with rotational but not pure translational loading; 2020 review argues KO = tissue stretch from rotational acceleration, site still debated (brainstem ARAS vs cortex/thalamocortical) | Primate inertial loading; narrative review | https://www.frontiersin.org/journals/neurology/articles/10.3389/fneur.2020.570566/full ; https://practicalneurology.com/articles/2015-apr/helmets-sensors-and-more-a-review |
| FE modelling: KO blows strain cortex more than brainstem | Higher tissue strain in cerebral cortex than lower regions | Finite-element, cited in review | https://frontiersin.org/journals/neurology/articles/10.3389/fneur.2020.570566/full |
| Combined linear+rotational best overall | Rowson & Duma 2013 "combined probability of concussion" (CP) from 63,011 impacts / 37 concussions, adjusted for under-reporting; CP and linear accel. both beat rotational alone (not different from each other) | Multivariate logistic regression, helmet telemetry | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3624001/ |
| Linear accel. & HIC15 best for immediate dx | AUC = 0.983 for immediately diagnosed concussion (1,208 players) | Head Impact Telemetry, HS + college football | https://stacks.cdc.gov/view/cdc/29630 |
| Rotation / brain strain best in 6-DOF mouthguard data | Corpus-callosum peak principal strain strongest predictor, then peak rotational accel. and Head Impact Power; small n (2 concussions in >500 impacts; one with LOC) | Instrumented mouthguard + FE | https://web.stanford.edu/group/camlab/cgi-bin/wordpress/wp-content/uploads/Hernandez2015_Article_SixDegree-of-FreedomMeasuremen.pdf ; https://news.stanford.edu/2015/01/06/measure-concussion-forces-010615/ |
| Rotational velocity > rotational acceleration | Reviews cite Zhang 2004 et al. as showing rotational velocity a better metric than peak rotational accel. | Review characterisation | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9351374/ (search snippet) |
| Neck strength protective (association) | Each +1 lb neck strength → concussion odds × 0.95 (OR 0.95); n ≈ 6,704 HS athletes; not significant in females alone; observational | Pre-season dynamometry + prospective injury surveillance | https://link.springer.com/content/pdf/10.1007%2Fs10935-014-0355-2.pdf |

### 1a. Concussion thresholds (risk curves)

| Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|
| Concussed NFL player peak linear accel. | 98 ± 28 (15 ms half-sine) | g | Video-guided Hybrid III reconstruction, 31 NFL cases (Pellman 2003) | https://www.semanticscholar.org/paper/Concussion-in-Professional-Football:-Reconstruction-Pellman-Viano/8c011be3daa2c3e457bb5a82efdc2f6769758b8e |
| Uninjured struck NFL player | 60 ± 24 | g | same | same |
| Concussed NFL player impact speed | 9.3 ± 1.9 | m/s | same | https://pubmed.ncbi.nlm.nih.gov/14519212/ |
| Nominal concussion tolerance | SI 300; HIC 250 | — | same | https://pubmed.ncbi.nlm.nih.gov/14519212/ |
| Facemask impacts concuss at lower accel. | 78 ± 18 vs 107–117 other quadrants | g | Pellman Part 2 | https://pubmed.ncbi.nlm.nih.gov/14519212/ (search summary) |
| Concussed struck player (Part 14 reanalysis) | 94 ± 28 g; 6432 ± 1813 rad/s² | g; rad/s² | 25 reconstructed NFL impacts, Hybrid III | https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_68223377 |
| 50% concussion risk, rotational (Rowson 2012) | 6383 rad/s² with 28.3 rad/s | rad/s²; rad/s | Logistic regression; 335 players, 300,977 sub-concussive + 57 concussive impacts | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10465647/ |
| Mean concussive vs sub-concussive impact | 5022 rad/s², 22.3 rad/s vs 1230 rad/s², 5.5 rad/s | rad/s²; rad/s | same dataset | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10465647/ |
| 50% / 75% concussion, linear (as cited from Rowson-Duma line of work) | 65.1 / 88.5 | g | secondary citation — confirm | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3624001/ (search summary) |
| CP logistic model form | P = 1/(1+e^−(β0+β1·a+β2·α+β3·a·α)), a in g, α in rad/s² | — | Rowson & Duma 2013 | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3624001/ ; coefficients **[unverified]**: β0 ≈ −10.2, β1 ≈ 0.0433, β2 ≈ 0.000873, β3 ≈ −9.2e−7 |
| Zhang/Yang/King 2004 mTBI 25/50/80 % | linear 66/82/106 g; rotational 4600/5900/7900 rad/s²; HIC 151/240/369 | g; rad/s²; — | FE + NFL reconstructions | **[unverified]** — paper exists (J Biomech Eng 126(2):226) https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_71986764 |
| 10 % MTBI risk (2007 football study) | 165 g; HIC 400; 9000 rad/s² | g; —; rad/s² | Logistic regression of NFL data | https://vtechworks.lib.vt.edu/bitstream/10919/23819/1/Young.pdf (search snippet) |
| Ommaya primate-scaled 50 % concussion in man | > 50 rad/s and > 1800 rad/s² | rad/s; rad/s² | Primate tests scaled by brain mass (1970–71) — old, generally considered low | https://saemobilus.sae.org/papers/comparative-tolerances-cerebral-concussion-head-impact-whiplash-injury-primates-700401 |
| BrIC critical angular velocities (50th-% male) | ωx 66.25, ωy 56.45, ωz 42.87; BrIC = √Σ(ωᵢmax/ωᵢC)² | rad/s | FE-derived, NHTSA (Takhounts 2013) | https://www-nrd.nhtsa.dot.gov/pdf/ESV/Proceedings/25/25ESV-000072.pdf |
| HIC15 regulatory limit | 700 (HIC36 1000); HIC15 700 ≈ 5 % AIS 4+ (Mertz 1997) | — | FMVSS 208 / IIHS | https://www.IIHS.org/media/0256acaf-ba77-4691-94fc-8553c75d650a/dr5MlQ/Ratings/Protocols/archive/measures_frontal_0609.pdf |
| HIC vs AIS 4+ risk (alt. regression) | ~17 % at HIC15 700; ~55 % at HIC15 1100; ~5 % at 400 | % | logistic regression review | https://biomedgrid.com/fulltext/volume5/head-injury-criterion-mini-review.000957.php |

**Game takeaway:** concussion/KO 50 %-risk ≈ **80–100 g linear** or
**~5000–6500 rad/s² with ~25–30 rad/s** rotational velocity (helmeted football
calibration). Unhelmeted punches reach these levels with less linear
acceleration (see §2).

---

## 2. Head acceleration produced by punches

| Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|
| Olympic straight punch force | 3427 ± 811 | N | 7 Olympic boxers, 5 weight classes, 18 straight punches into Hybrid III frangible face (Walilko 2005) | https://pubmed.ncbi.nlm.nih.gov/16183766/ (abstract via search) |
| Hand velocity | 9.14 ± 2.06 | m/s | same | same |
| Effective punch mass | 2.9 ± 2.0 | kg | same; heavier classes higher force mainly via effective mass | same |
| Head translational accel. (straight) | 58 ± 13 (mean 58 confirmed; SD **[unverified]**) | g | same | https://www.semanticscholar.org/paper/Biomechanics-of-the-head-for-Olympic-boxer-punches-Walilko-Viano/edbd929ed7812c983b4780fc106ecdf716b58a30 |
| Head rotational accel. (straight) | 6343 ± 1789 (SD **[unverified]**) | rad/s² | same | same; https://www.mjssm.me/clanci/MJSSM_March_2021_Boroushak_31-35.pdf |
| Hook head accel. | 71.2 ± 32.2 g; 9306 ± 4485 rad/s² | g; rad/s² | 11 Olympic boxers, 78 blows (hooks, uppercuts, straights) to Hybrid III (Viano 2005, Part 10) | https://pubmed.ncbi.nlm.nih.gov/16331164/ |
| Uppercut rotational accel. | 3181 ± 1343 | rad/s² | same study, as tabulated in 2022 systematic review | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9351374/ |
| Interpretation | Hook levels "consistent with those causing concussion in NFL impacts"; punches have proportionally more rotation vs translation than football hits | — | same | https://pubmed.ncbi.nlm.nih.gov/16331164/ |
| Rear-hand straight max force, elite / intermediate / novice | 4800 ± 227 / 3722 ± 133 / 2381 ± 116 | N | Boxing dynamometer (Smith et al. 2000), 7/8/8 boxers | https://sponet.de/sponet/Record/4004380 |
| Lead-hand straight (same groups) | 2847 ± 225 / 2283 ± 126 / 1604 ± 97 | N | same | same |
| In-fight mean punch force (pro bouts) | 866.6 – 1149.2 (bout means) | N | Sensor gloves, 12 boxers, 6 pro bouts; far below lab values; no correlation with body mass | https://www.degruyterbrill.com/document/doi/10.2202/1559-0410.1004/html |
| MMA in-vivo mean head impact | 38.0 ± 24.3 g; 2567 ± 1739 rad/s² | g; rad/s² | 13 MMA fighters, Stanford MiG2.0 mouthguard (Tiernan 2020) | https://arrow.tudublin.ie/creaart/11/ |
| MMA highest-angular impact per bout | 86.7 ± 18.7 g; 7561 ± 3438 rad/s² | g; rad/s² | same | same |
| MMA concussion vs no injury | max angular accel. +24.7 %; Head Impact Power 20.6 vs 7.15 kW (+189 %) | %; kW | same; 451 impacts, 5 concussions in competition | https://arrow.tudublin.ie/creaart/11/ ; https://arrow.tudublin.ie/creaart/9/ |
| Throws/takedowns | Rotational accel. mostly below injury thresholds; direct strikes higher | — | Systematic review, 22 studies | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9351374/ |

**Game takeaway:** an elite power punch ≈ 3–5 kN, ~9 m/s fist, ~3 kg effective
mass, yielding ~60–70 g and 6000–9000 rad/s² at the dummy head — i.e. a
single clean hook already sits at roughly the 50 % concussion level. Real
in-fight average punches are ~1 kN (glancing, partially blocked), so most
landed strikes are sub-threshold.

---

## 3. Strike counts, fight outcomes, "chin"

| Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|
| UFC fights ending by KO (true LOC) | 12.7 % of matches; 6.4 / 100 athlete-exposures | % | Video review, UFC 2006–2012, 844 events (Hutchison 2014, AJSM) | https://read.qxmd.com/read/24658345 ; https://combatsportslaw.com/2014/03/27/university-of-toronto-study-finds-rates-of-kos-and-tkos-in-mma-are-higher-than-previously-reported/ |
| UFC fights ending by TKO from repetitive strikes | 19.1 %; 9.5 / 100 AE | % | same | same |
| Total match-ending head trauma | 31.9 %; 15.9 / 100 AE | % | same | same |
| KO strike location | 100 % of KOs from direct head blow; 53.9 % to jaw | % | same | same |
| KO-strike → stoppage | 3.5 s (0–20); 2.6 extra head strikes (0–20) | s; strikes | same | same |
| Strikes in final 30 s before TKO | 18.5 (5–46), 92.3 % to head | strikes | same | same |
| UFC 2000–2021 head-trauma finishes | 31.6 % of fights; head trauma = 88.1 % of KO/TKOs | % | 2,488 UFC fights (Mańka-Malara 2022, IJERPH) | https://www.mdpi.com/1660-4601/19/20/13050 |
| UFC head strikes absorbed | 6.30 head strikes/min, of which 2.41 significant | strikes/min | same, official UFC stats | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9603147/ |
| UFC outcome mix (all-time) | KO/TKO ~32 %, Sub ~19–20 %, Dec ~47–48 % | % | Non-peer-reviewed aggregations, ~8,000–8,600 bouts | https://agentmma.com/mma-lab/ufc-decision-rate ; https://joaogouveia89.github.io/ufc_report.html |
| UFC KO/TKO by division | HW 51.5 % vs women's strawweight 13.4 % | % | Non-peer-reviewed | https://thefightalgorithm.pages.dev/articles/division-meta |
| Most common UFC fight-ending punch | rear straight 29.2 %, lead hook 26.9 %, rear hook 23.9 % (n=271); hooks 50.8 % of 264 | % | Video coding of "critical punch" | https://lida.sport-iat.de/dbv/Record/4090466?lng=en ; https://agentmma.com/mma-lab/most-common-ufc-knockout-punch |
| Reach effect | +1 cm reach → odds finishing punch is a straight × 1.10 | OR | logistic regression | https://agentmma.com/mma-lab/most-common-ufc-knockout-punch |
| "Puncher's chance" | ~1:2000 completely outclassed; ~1:40 when landing 35–45 % of strikes | odds | Logistic regression on 1,815 UFC KO bouts 1997–2020 (Wild, JHSE 2022) | https://www.jhse.ua.es/article/view/2022-v17-n2-puncher-s-chance-professional-mixed-martial-arts-com |
| Pro boxing KO/TKO rate (2014–2024) | Men 47 % (15 KO + 32 TKO); women 29 % (5 + 24); per-minute gap ~1 % | % | ~237,000 BoxRec bouts (AAN 2025 abstract) | https://index.mirasmart.com/AAN2025/PDFfiles/AAN2025-005548.html |
| US pro boxing, 6 mo. 2017 | TKO 35.1 %, KO 18.1 %, decision 46.5 % | % | 1,690 bouts (AAN abstract) | https://aan.com/MSA/Public/Events/AbstractDetails/43571 |
| Pro boxing KO predictors | Heavyweights, males, debutants higher KO/TKO | — | BoxRec, Physician & Sportsmed 2024 | https://pubmed.ncbi.nlm.nih.gov/37990916/ |
| Pro boxing brain-injury deaths | ~1 / 5,000 bouts; 42 % after KO, 35 % after TKO | rate | BoxRec 2000–2019, 428,904 bouts | https://combatsportslaw.com/2022/06/10/one-in-5000-pro-boxing-bouts-end-in-death-by-brain-injury/ |
| CompuBox punches landed / round | ~13 (LHW) – 19 (LW) avg; elite outliers 40 | punches/round | CompuBox operator counts (not peer-reviewed) | https://www.boxingscene.com/articles/compubox-inside-numbers-sho-wars-gradovich ; https://ringmagazine.com/news/2Awk13nWfZQNDd1piXl8iX |
| CompuBox punches thrown / round | ~54 implied average (Olivares 83.8 was "nearly 30 above avg") | punches/round | same | https://www.boxingscene.com/articles/compuboxs-lists-top-performers-2013 |
| Elite total connect % | Hagler 43.2 % (career leader); power-punch connect 47 % | % | CompuBox | https://api2.compuboxdata.com/reports/49 |
| Knockdown survival (UFC) | Knocked-down fighter still won 34.4 % of fights continuing past that round | % | 3,005 fights, non-peer-reviewed | https://agentmma.com/mma-lab/ufc-knockdown-survival-rate |

### Chin variance / cumulative effects

| Finding | Value | Method | Source |
|---|---|---|---|
| Prior KO/TKO predicts next KO/TKO | OR 1.13 (95 % CI 1.02–1.25) per prior KO; 22.7 % of 705 KO'd fighters lost next bout by KO/TKO; head strikes absorbed *not* independently significant | Retrospective UFC 2015–2023 | https://www.tandfonline.com/doi/full/10.1080/00913847.2026.2631369 ; https://agentmma.com/mma-lab/ufc-knockout-loss-repeat-risk |
| Raw repeat-KO rate | 29.3 % after 4th career KO loss vs 13.8 % never-stopped baseline | Descriptive, non-peer-reviewed | https://agentmma.com/mma-lab/ufc-knockout-loss-repeat-risk |
| Contrary evidence | Earlier study found no increase of future KO probability with number of KOs received | Retrospective | https://revistas.unileon.es/index.php/artesmarciales/article/download/7477/6135/37296 |
| Cumulative sub-concussive load (football) | 57 % of 105 concussions *not* tied to one identifiable impact; delayed-dx players took 32.9 ± 24.9 impacts on injury day and 69.7 ± 43.3 in prior 7 days (more than immediate-dx) | HIT helmet telemetry (Beckwith 2013) | https://pubmed.ncbi.nlm.nih.gov/23135364/ |
| Inter-individual threshold spread | Concussive impact rotational accel. SD ≈ ±28–35 % of mean (e.g. 6432 ± 1813 rad/s²; 94 ± 28 g) | Reconstruction spread | https://bvbvf1.bib-bvb.de/vufind/PrimoRecord/cdi_proquest_miscellaneous_68223377 |
| Neck strength | −5 % odds per lb neck strength | see §1 | https://link.springer.com/content/pdf/10.1007%2Fs10935-014-0355-2.pdf |

**Game takeaway:** model a per-fighter KO threshold as a distribution
(≈ lognormal, CV ≈ 0.3), lower it modestly with prior KOs (≈ ×1.13 odds each)
and within-fight accumulated damage, raise it with neck strength. In MMA,
~1 in 8 fights ends in true LOC, usually from one critical punch (jaw, hook or
rear straight), followed by ~2–3 extra strikes before the referee stops it;
TKOs instead follow a barrage (~18 strikes in 30 s).

---

## 4. Body-shot KOs (liver / solar plexus)

Evidence base is thin and mostly non-peer-reviewed; no controlled study of
"liver shot" force thresholds was found.

| Item | Value / description | Method | Source |
|---|---|---|---|
| Proposed liver-shot mechanism | Liver compression → vagal reflex → sudden hypotension/bradycardia (vasovagal-like); fighter typically stays conscious but cannot stand; pain ~30–60 s | Coaching/sports-medicine commentary, not controlled studies | https://www.wikipedia.com/wiki/Liver_shot ; https://dsps.wi.gov/Credentialing/BoxingMMA/2022-ABC-THE-ANATOMY-OF-THE-KNOcKOUT-FINAL.pdf |
| Liver = most-injured abdominal organ in blunt trauma | ~38 % of abdominal injuries in crashes | Epidemiology (Elhagediab & Rouhana 1998) | https://pmc.ncbi.nlm.nih.gov/articles/PMC3242546 |
| Force limiting does not prevent liver injury | Peak pressure cut to ~⅓, liver injury unchanged — compression *rate* matters | PMHS lateral abdominal impact (Rouhana 1986) | https://saemobilus.sae.org/content/861879 |
| Abdominal Viscous Criterion | VCmax 1.2 m/s ≈ 25 % risk of AIS ≥ 5 abdominal injury | Lau & Viano 1986 | https://saemobilus.sae.org/content/861882 |
| Commotio cordis (precordial blow → VF) | VF 7 % at 25 mph (11 m/s), 68 % at 40 mph (18 m/s), lower ≥ 50 mph; ≥ ~50 J energy; vulnerable window ~40 ms of cardiac cycle | Juvenile swine 8–25 kg, baseball impacts (Link 2003) | https://www.qxmd.com/r/12570951 ; https://en.wikipedia.com/wiki/Commotio_cordis |
| Solar plexus / "winded" | No peer-reviewed quantitative source found | — | — |
| Punch force available to the body | Same punch forces as §2 (≈1–5 kN); in UFC, *all* KOs (LOC) were head strikes — body shots end fights as TKO, not LOC | see §2/§3 | https://read.qxmd.com/read/24658345 |

**Game takeaway:** treat body shots as a separate "incapacitation" channel
(temporary inability to continue, consciousness intact, ~10–60 s), driven by
compression rate × depth over the liver (right lower ribs), not as a brain KO.

---

## 5. Thoracic / rib / abdominal thresholds

| Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|
| Viscous Criterion (thorax) | VCmax = 1.0 m/s ≈ 25 % risk AIS ≥ 4 (frontal) | m/s | PMHS + animal blunt impact (Lau & Viano 1986) | https://saemobilus.sae.org/content/861882 |
| VC regime | VC governs at deformation velocity > 3 m/s; compression criterion governs slow crush | m/s | Viano/Lau | https://aip.brightspotcdn.com/PTO.v42.i3.26_1.online.pdf |
| Lateral VC | VCmax 1.5 m/s ≈ 25 % serious injury | m/s | Pendulum study citing Viano | (same search; secondary) https://aip.brightspotcdn.com/PTO.v42.i3.26_1.online.pdf |
| Compression (C = deflection / chest depth) | 50 % risk any rib fracture: 35 % (age 30) vs 13 % (age 70) | % depth | 93 PMHS tests, age 17–86 (Kent & Patrie 2005) | https://www.stat.auckland.ac.nz/~lee/330/assigns.dir/kent.patrie.pdf |
| Compression, severe injury | 50 % risk: 43 % (age 30) vs 33 % (age 70) | % depth | same | same |
| Serious injury, frontal drop | ~30 % compression of chest breadth | % | Tarriere 1979 (secondary) | https://aip.brightspotcdn.com/PTO.v42.i3.26_1.online.pdf |
| Chest deflection vs rib fracture | None < 5.8 cm (2.3 in); frequent > 7.6 cm (3 in); deflection, not force, governs | cm | PMHS (Stalnaker & Mohan 1974) | https://saemobilus.sae.org/content/740589 |
| Whole-chest force for rib fracture onset | ~4 fractures at ~1340 lbf (≈ 6.0 kN); extensive at 1850 lbf (≈ 8.2 kN); 2.25 in deflection at 1545 lbf | lbf / kN | Seated PMHS frontal sled, 10–20 mph (Patrick, Kroell & Mertz 1967) | https://saemobilus.sae.org/content/670913 |
| Isolated rib/cartilage 3-pt bending failure | ~82–88 N (large SD ≈ 60–70 N) | N | Rib + costal cartilage specimens | https://stapp.org/wp-content/uploads/SC25-06.pdf |
| Rib structural variability | Age & sex alone insufficient to predict rib response | — | Dynamic A-P whole-rib bending | https://ibrc.osu.edu/wp-content/uploads/2017/03/Misicka-Poster-Injury-Biomechanics-Symposium-2017.compressed.pdf |
| Abdominal VC | 1.2 m/s ≈ 25 % AIS ≥ 5 | m/s | Lau & Viano 1986 | https://saemobilus.sae.org/content/861882 |

Note the force mismatch: a 3–5 kN punch is in the same range as the whole-chest
force for multiple rib fractures (~6 kN) but delivered over a fist-sized area,
so localised single-rib fractures (especially floating ribs 11–12) are
plausible from elite punches/kicks; whole-chest crush criteria (C, VC) assume a
broad impactor and are better suited to falls/blunt objects.

---

## 6. Suggested game parameters (derived, not sourced)

| Parameter | Suggested default | Basis |
|---|---|---|
| Brain-KO 50 % point (rotational) | α ≈ 6000 rad/s² *and/or* ω ≈ 28 rad/s; σ_ln ≈ 0.3 | §1a Rowson 2012, Part 14 spread |
| Brain-KO 50 % point (linear, if no rotation) | ≈ 90 g | §1a Pellman |
| Clean elite hook to jaw | ≈ 70 g, ≈ 9000 rad/s² → ~60–70 % KO chance on fresh chin | §2 Viano Part 10 |
| Average landed in-fight punch | ≈ 1 kN, well sub-threshold | §2 Pierce |
| Cumulative damage | each sub-threshold hit lowers remaining threshold slightly; prior career KOs OR ≈ 1.13 each | §3 |
| Body "liver" incapacitation | function of VC over liver; 25 % severe at VC 1.2 m/s; non-LOC 10–60 s | §4, §5 |
| Rib fracture | chest compression 35 % (young) / 13 % (old) for 50 % any-fracture; or local force ≳ few kN | §5 |

## Gaps / to re-verify with full text
- Zhang 2004 25/50/80 % values and Rowson–Duma 2013 CP coefficients (marked unverified).
- SDs on Walilko 2005 head accelerations.
- Peer-reviewed liver-shot / solar-plexus mechanism data (none found).
- Network sandbox blocked PubMed/PMC/publisher fetches; allow
  `pubmed.ncbi.nlm.nih.gov` / `pmc.ncbi.nlm.nih.gov` to verify against full text.
