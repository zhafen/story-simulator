# B1/B2 — Human reaction time, strike timing, and mechanical power output

Research notes for a physics-grounded combat system. Every number has a source URL.

**How this was gathered, and its limits.** Full-text page fetching was blocked by
the session's network policy (ncbi.nlm.nih.gov, pmc.ncbi.nlm.nih.gov, core.ac.uk,
clok.uclan.ac.uk all failed to resolve). All values come from **abstracts and
search-result excerpts** of the cited papers, not tables read from the full text.
Values marked **(verify)** looked suspicious or came from a secondary summary.
Values marked **[derived]** are my own arithmetic from cited inputs, not
published figures.

Abbreviations: RT = reaction time; SRT/CRT = simple/choice RT; MT = movement
time; PP = peak power; MP = mean power; BM = body mass; WAnT = Wingate anaerobic test.

---

## B1. Reaction time

### B1.1 Simple and choice RT (lab, button-press style)

| Quantity | Value / range | Units | Method | Population | Source |
|---|---|---|---|---|---|
| Simple visual RT | ~331 (mean) | ms | Computer visual vs auditory SRT task | 14 college students | [Shelton & Kumar 2010](https://coachsci.sdsu.edu/csa/vol191/shelton.htm) |
| Simple auditory RT | ~284 (mean) | ms | same | same | [Shelton & Kumar 2010](https://coachsci.sdsu.edu/csa/vol191/shelton.htm) |
| Auditory advantage over visual | 20–40 | ms | Review statement citing Shelton & Kumar and others | general adults | [Frontiers Hum Neurosci 2021](https://www.frontiersin.org/articles/10.3389/fnhum.2021.779343/full) |
| Simple visual RT, athletes | 193 ± 15 (R hand), 191 ± 24 (L hand) | ms | Hand-response SRT | U17 male national football players | [Dergipark football study](https://dergipark.org.tr/tr/download/article-file/3219492) |
| Simple auditory RT, athletes | 171 ± 26 (R), 165 ± 27 (L) | ms | same | same | [same](https://dergipark.org.tr/tr/download/article-file/3219492) |
| Simple visual RT | 194 ± 17 (cadets), 185 ± 17 (juniors) | ms | Mean of best 3 of 5 trials | Serbian female handball players | [FU Phys Ed Sport](https://casopisi.junis.ni.ac.rs/index.php/FUPhysEdSport/article/download/5007/3008) |
| SRT, karate expert vs novice | 204 vs 238 | ms | Simple RT task (secondary citation of Fontani et al. 2006) **(verify)** | karateka | [Konstanz review](https://kops.uni-konstanz.de/server/api/core/bitstreams/4b6acc5e-d254-400d-857c-fe9d69d6510d/content) |
| SRT, dominant hand, elite karate vs non-athletes | ~292 vs ~335 | ms | Light-based reaction system (includes a reach-to-target movement) | elite karateka vs non-athletes | [Simple and choice RT karate](https://lida.sport-iat.de/ta/Record/4054547?lng=en) |
| SRT, amateur boxers | ~247 | ms | Bianco et al. 2011, reported in s | male amateur boxers | [Neuropsychological testing in boxing](https://lida.sport-iat.de/dbv/Record/4025482?lng=en) |
| CRT, athletes | 403 ± 16 (team-sport), 390 ± 8 (individual-sport); non-athletes 407 ± 8 | ms | Choice RT task; groups not significantly different | college athletes vs non-athletes | [Riedesel & Mahoney poster](https://www.tamuk.edu/education/_files_COED/2013riedeselTACSMposter.pdf) |
| SRT, non-athletes (same study) | 282 ± 8 | ms | Simple RT; athletes significantly faster (p ≈ .016–.018) | non-athletes | [same](https://www.tamuk.edu/education/_files_COED/2013riedeselTACSMposter.pdf) |
| Hick–Hyman slope | 150–200 | ms per bit (per doubling of alternatives) | RT = a + b·log₂(n+1); task-dependent, decreases with practice | general | [Hick's law (overview)](https://en.wikipedia.org/wiki/Hick%27s_law), [Mental chronometry](https://static.hlt.bme.hu/semantics/external/pages/pszichometriai_g-faktor/en.wikipedia.org/wiki/Mental_chronometry.html) |
| Hick intercept (simple RT baseline) | ~170–200 | ms | textbook summary **(verify)** | general | [Nail IB SEHS notes](https://nailib.com/ib-resources/ib-sehs-sl/notes/65d07d873947a7496e1b3950) |

Notes:
- Expertise mostly shows up in **choice RT** with sport-specific stimuli, not in
  simple RT. Mori, Ohtani & Imanaka (2002, *Hum Mov Sci* 21:213–230; n = 6
  experts, 7 novices) found expert–novice CRT differences but no SRT
  difference ([KAKEN record](https://kaken.nii.ac.jp/en/grant/KAKENHI-PROJECT-13610095);
  [PeerJ 2023 discussion](https://peerj.com/articles/14764)). The PeerJ paper
  calls the karate expert-RT literature "contradictory".
- Measured RT depends a lot on the response: a key press is shorter than "first
  wrist movement", which is shorter than "foot leaves force plate". The
  ~290–330 ms karate/student values include more motor delay than the
  ~165–195 ms athlete values.

### B1.2 Sprint-start reaction and the 0.100 s false-start rule

| Quantity | Value / range | Units | Method | Population | Source |
|---|---|---|---|---|---|
| False-start threshold | < 0.100 after gun | s | World Athletics/IAAF rule; RT measured by force-sensing blocks | all sprinters | [Pain & Hibbs 2007](https://repository.lboro.ac.uk/articles/journal_contribution/Sprint_starts_and_the_minimum_auditory_reaction_time/9629570); [UL review](https://researchrepository.ul.ie/server/api/core/bitstreams/e85a9779-1739-429f-a842-b8a4b475b40f/content) |
| Earlier threshold (pre-1990) | 0.120 | s | same rationale | — | [Pain & Hibbs 2007](https://repository.lboro.ac.uk/articles/journal_contribution/Sprint_starts_and_the_minimum_auditory_reaction_time/9629570) |
| Basis of the rule | assumption that simple auditory RT is "rarely < 100 ms" | — | older lab SRT studies | — | same |
| Starts < 100 ms (non-anticipatory) | 5 of 9 athletes averaged < 100 ms in ≥1 condition; 20% of starts in two conditions were < 100 ms | — | Force-transducer blocks + 13-muscle surface EMG (n = 2) | 9 trained sprinters | [Pain & Hibbs 2007](https://dspace.lboro.ac.uk/2134/6600) |
| Neuromuscular SRT floor | < 85 | ms | same | same | same |
| EMG latency floor | < 60 | ms | same | same | same |
| Mean of fastest RT, Beijing 2008 | 166 (men), 189 (women) | ms | Official start-system data | Olympic sprinters | [Lipps et al. 2011 (PMC3198384)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3198384) |
| Sex difference artefact | women can false-start by up to 21 ms undetected | ms | Same force threshold used for both sexes | — | same |
| Suggested sex-specific thresholds | 115 (men), 119 (women) | ms | 1999–2014 championship data | elite | [UL repository](https://researchrepository.ul.ie/server/api/core/bitstreams/e85a9779-1739-429f-a842-b8a4b475b40f/content) |
| World-Champs 100 m finalist mean RT | 0.141 (1999), 0.142 (2005), 0.166 (2011) | s | Official results | WC finalists | [AFEPUC 2022](https://reference-global.com/download/article/10.2478/afepuc-2022-0007.pdf) |
| Effect of zero-tolerance false-start rule (2010) | mean RT up by ~0.03 s (~20%), 1997→2011 | s | Results analysis | elite 100 m | [False-start rule effects](https://lida.sport-iat.de/ta/Record/4043608?lng=en) |
| Elite vs novice auditory-start RT | 50–100 (elite) vs 120–160 (novice) **(verify — implausibly low elite range)** | ms | Review statement | sprinters | [Frontiers Physiol 2018](https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2018.01138/pdf) |
| Mero & Komi decomposition | total RT = premotor (gun→EMG onset) + motor (EMG→force +10%) | — | Force platform + EMG, 3 m starts | 8 male sprinters | [Mero & Komi 1990](https://springerlink.bibliotecabuap.elogim.com/content/pdf/10.1007/BF00236697.pdf) |

**Takeaway:** a rested, cued elite athlete's auditory reaction floor is about
**85–120 ms**. The official threshold is 100 ms. Typical race RTs are
**130–190 ms**.

### B1.3 Reacting to incoming strikes and projectiles: anticipation

| Quantity | Value / range | Units | Method | Population | Source |
|---|---|---|---|---|---|
| Penalty-kick ball flight time (11 m) | < 450 (at 25–30 m/s); "as little as 500" | ms | Kinematic estimate | professional football | [Frontiers 2024 GK](https://frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2024.1356340/pdf); [Springer GER 2018](https://link.springer.com/doi/10.1007/s12662-018-0506-3) |
| GK must commit before ball-flight info is usable | qualitative | — | Review / simulation | GKs | same |
| Ball flight, pitcher/bowler → batter | ≤ 500 | ms | Review | baseball / softball / cricket | [PMC4743964](https://pmc.ncbi.nlm.nih.gov/articles/PMC4743964) |
| Swing duration once committed | ≤ 300 (bat to ~31 m/s) | ms | Kinematics | baseball | same |
| Decision window | 125–225 **(secondary, verify)** | ms | Vision-care blog | baseball | [Good Eyes](https://www.goodeyes.com/blog/science-of-seeing-hitting-fastball/) |
| Hits with vision occluded at ball release | ~60% of balls hit | % | Temporal occlusion | elite cricket batsmen | [PMC4626325](https://pmc.ncbi.nlm.nih.gov/articles/PMC4626325); Müller & Abernethy 2012 review |
| Reaction to light, taekwondo roundhouse | 498 ± 90 (short dist.), 521 ± 111 (normal), 602 ± 121 (long) | ms | LED → foot leaves force plate | 49 taekwondo athletes | [Estevan/Falco group (Biol Sport)](https://termedia.pl/Original-paper-MECHANICAL-ANALYSIS-OF-THE-ROUNDHOUSE-KICK-ACCORDING-TO-HEIGHT-AND-DISTANCE-IN-TAEKWONDO,78,23359,0,0.html); [PMC3944546](https://pmc.ncbi.nlm.nih.gov/articles/PMC3944546) |
| Boxing jab vs cross RT to light | jab significantly faster than cross (p < 0.001); ms values not retrieved | ms | Light cue → first wrist movement; best 6 of 10 | 22 Brazilian national-team boxers | [Loturco et al. 2015](https://lida.sport-iat.de/ta/Record/4037692?lng=en) |
| Fencers' RT to light targets | ~350 (mean) | ms | Light-target lunge/touch | elite fencers | [Fencing Reactions JSCR](https://repository.mdx.ac.uk/download/ec169dfdfe5bad0dc05736676fe43b03a4f76f0214225c7b9edae3af4c3e3380/818040/Fencing_Reactions_JSCR.pdf) |
| Expert boxers' perception of attack postures | experts' responses map to their own counter-action; novices' to a defensive pattern | — | Simon-like key-press task | expert / beginner / non-boxers | [Unibo postprint](https://cris.unibo.it/retrieve/038a2f93-7184-4e88-8b9a-52aaba65cec9/What%20boxing-related%20stimuli%20reveal%20about%20response%20behaviour_postprint.pdf) |

**Takeaway for combat.** A jab takes about 0.2–0.4 s to arrive (see B1.4). A
purely reactive defense needs about 0.2 s of CRT plus about 0.1–0.2 s of
movement, so it is marginal against a straight punch. Experts close that gap
by **anticipating** from preparatory cues such as stance, shoulder, and run-up,
not by having faster raw RT. This is the same mechanism penalty keepers and
cricket batsmen rely on.

### B1.4 Strike movement time (initiation → contact)

| Quantity | Value / range | Units | Method | Population | Source |
|---|---|---|---|---|---|
| Jab delivery time | 405 (reported SD "0.15" — likely typo) **(verify)** | ms | 3D motion capture, max-effort vs bag | 15 male amateur boxers (6.3 ± 2.8 y exp.) | [Stanley et al. 2018](https://ideas.repec.org/a/taf/rpanxx/v18y2018i5p835-854.html); [Chester repo](https://chesterrep.openrepository.com/entities/publication/0acdae9d-e8be-48cf-816e-ed9c667981b3) |
| Lead hook peak fist velocity | 11.95 ± 1.84 | m/s | same | same | same |
| Straight punch delivery (lit. summary) | 357 ± 178; fist 5.9–8.2 m/s | ms | Review of prior studies | mixed | [core.ac.uk 189160975 (Stanley ms.)](https://core.ac.uk/download/189160975.pdf) |
| Hook delivery (lit. summary) | 477 ± 203; fist 8–11 m/s | ms | same | mixed | same |
| Single maximal cross, projection → contact | 223 ± 99 **(verify, text extract)** | ms | 8-camera optoelectronic | 10 competition boxers | [Piorkowski, Lees & Barton 2011](https://knowledge.lancashire.ac.uk/id/eprint/3757/1/piorkowski-et-al-2011-punch-kinematics.pdf) |
| Cross cycle time within a combination | 132 ± 21 **(verify)** | ms | same | same | same |
| Ordering | jab, cross < hook (delivery time); hooks have higher contact speed | — | same | same | [PubMed 21560747](https://pubmed.ncbi.nlm.nih.gov/21560747/) |
| Contact speed, single vs out-of-sync combo | 9.26 vs 7.49 | m/s | same | same | [Piorkowski 2011](https://www.researchgate.net/publication/51115734_Single_maximal_versus_combination_punch_kinematics) |
| Olympic straight punch hand velocity | 9.14 ± 2.06 | m/s | Instrumented Hybrid III dummy face | 7 Olympic boxers, 5 weight classes | [Walilko, Viano & Bir 2005](https://pmc.ncbi.nlm.nih.gov/articles/PMC1725037) |
| Taekwondo roundhouse execution time | 261 ± 69 (short), 306 ± 105 (normal), 350 ± 106 (long distance) (abstract units "ms/m" — likely ms) | ms | Foot-off force plate → target impact | 49 taekwondo athletes | [Estevan/Falco (Biol Sport)](https://termedia.pl/Original-paper-MECHANICAL-ANALYSIS-OF-THE-ROUNDHOUSE-KICK-ACCORDING-TO-HEIGHT-AND-DISTANCE-IN-TAEKWONDO,78,23359,0,0.html) |
| Total response time (RT + execution), roundhouse | ≈ 760–950 [derived from the two rows above] | ms | sum | same | same |
| Roundhouse execution, whole-movement definition | Muay Thai 1.02 ± 0.15; Taekwondo 1.54 ± 0.52 | s | 3D motion capture, full kick cycle | 24 black belts (8/discipline) | [Gavagan & Sayers 2017, PLoS ONE](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5571909/) |
| Knee-extension angular velocity | Karate −947 ± 94; TKD −943 ± 106 | deg/s | same | same | same |
| Roundhouse peak foot linear velocity | 18.3 | m/s | Review of kicking studies | trained | [Biol Sport / search excerpt](https://ojs.ub.uni-konstanz.de/cpa/article/view/4811/4451) **(verify)** |

Practical game numbers [derived summary]:
- Jab ≈ 0.20–0.40 s
- Cross ≈ 0.25–0.40 s
- Hook ≈ 0.35–0.50 s
- Roundhouse kick contact phase ≈ 0.25–0.35 s from foot-off (about 1 s or more
  for the full chamber-and-return cycle)

Combination follow-ups are faster than lead punches (cross about 0.13 s
in-sync).

---

## B2. Mechanical power output

### B2.0 Mechanical vs metabolic power, and efficiency

- **Mechanical (external) power** is the rate of work done on the
  environment, such as pedals, the ground reaction × centre-of-mass velocity,
  or a barbell. **Metabolic power** is the rate of chemical energy use
  (from VO₂/VCO₂). Efficiency = mechanical / metabolic.
- Heat = metabolic − mechanical. At about 20% efficiency, a 300 W cyclist
  is spending about 1.5 kW metabolically and dumping about 1.2 kW as heat
  [derived].

| Quantity | Value / range | Units | Method | Population | Source |
|---|---|---|---|---|---|
| Gross efficiency (GE), cycling | 19.9 (men), 22.5 ± 2.1 (women) at 150 W | % | Indirect calorimetry on an ergometer | trained cyclists | [Hopker et al. (Kent)](https://kar.kent.ac.uk/id/document/25296) |
| Work efficiency, trained vs untrained | 28.0 ± 0.5 vs 27.7 ± 0.8 (no difference) | % | Work efficiency (baseline subtracted) | 9 trained, 9 untrained men | [PMC1805795 review](https://pmc.ncbi.nlm.nih.gov/articles/PMC1805795) |
| Delta efficiency, cycling vs running | 25 vs 42 | % | ΔWork/ΔEnergy | — | [Bijker et al. 2002, cited in JSSM](https://www.jssm.org/jssm-09-332.xml-Fulltext) |
| Max muscle efficiency (estimate) | ~29 | % | Cavanagh & Kram 1985, as cited | — | same |
| Delta efficiency vs cadence | 20.6 → 23.8 | % | Constant work rate, rising cadence | — | [PMC1805795](https://pmc.ncbi.nlm.nih.gov/articles/PMC1805795) |
| Efficiency vs fibre type | higher % type I fibres → higher efficiency | — | Muscle biopsy + GE/DE | trained cyclists | Coyle et al. 1992, MSSE 24:782 (cited in [PMC1805795](https://pmc.ncbi.nlm.nih.gov/articles/PMC1805795)) |

Use **GE ≈ 18–23%** for whole-body cycling and **≈ 25%** for delta/muscle
efficiency. Running's apparent delta efficiency above 40% comes from elastic
energy return; it does not mean the muscles are more efficient.

### B2.1 Peak instantaneous power (< 1 s)

| Quantity | Value / range | Units | Method | Population | Source |
|---|---|---|---|---|---|
| Wilkie's single-movement ceiling | up to ~6 hp (~4.5 kW) | hp / W | Literature synthesis | champion athletes | [Wilkie 1960, *Ergonomics* 3:1–8](https://scilit.com/publications/508e131d620d926e02f79c9869f89d01) |
| CMJ peak propulsive power | 64.1 (100 m), 59.4 (400 m); absolute 4030 vs 3504 W | W/kg | Force-plate CMJ | professional female sprinters (n = 8, 6) | [Frontiers 2025](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2025.1672028/pdf) |
| Sayers SJ peak power equation | PP(W) = 60.7·h(cm) + 45.3·BM(kg) − 2055; SEE 355 W | W | Regression vs force plate | 108 college athletes and non-athletes | [Sayers 1999 (text)](https://www.unm.edu/%7errobergs/478SayersText.doc) |
| Equation agreement vs force plate | ±6% (Sayers CMJ eq.) | % | Ratio limits of agreement | 25 elite junior basketball players (74 ± 12 kg) | [Basketball validation](https://lida.sport-iat.de/twm/Record/4015446?lng=en) |
| Example, 75 kg man jumping 40 cm | ≈ 3800 W ≈ 51 W/kg [derived, Sayers SJ eq.] | W | — | — | — |
| Example, 75 kg man jumping 60 cm | ≈ 5000 W ≈ 67 W/kg [derived] | W | — | — | — |
| Olympic lifts, whole pull | 28–35 | W/kg | Film/kinematic analysis of competition lifts | elite male weightlifters | [Garhammer 1980/85 abstract](https://www.bisp-surf.de/Record/PU198603025449) |
| Second pull only | 1.5–2× the whole-pull value (≈ 42–70 W/kg [derived]) | W/kg | Competition analysis | elite men and women | [Garhammer 1991](https://www.bisp-surf.de/Record/PU199111051037) |
| Second pull, absolute | up to ~5500 **(secondary, verify)** | W | — | elite male lifters | [Breaking Muscle](https://breakingmuscle.com/weightlifting-and-figure-skating-an-odd-fit-or-are-all-olympians-doing-it/) |
| Track-sprint cyclist Pmax | 1600 ± 116 at 130 ± 5 rpm; T_opt 118.5 ± 9.8 N·m | W | Torque–velocity test on ergometer | 12 elite (world-class) track sprinters | [Dorel et al. 2005](https://www.thieme-connect.de/products/ejournals/abstract/10.1055/s-2004-830493) |

### B2.2 Short burst (≈ 5–30 s): Wingate

| Quantity | Value / range | Units | Method | Population | Source |
|---|---|---|---|---|---|
| WAnT peak power | 1084 ± 137 W; 12.9 ± 1.5 W/kg | W, W/kg | 30 s WAnT, 0.085 kp/kg | NCAA D-IA male power athletes (football, T&F) | [Coppin et al. 2012](https://digitalcommons.usu.edu/hper_facpub/164) |
| WAnT mean power (30 s) | 777 ± 81 W; 9.3 ± 0.9 W/kg | W, W/kg | same | same | same |
| PP classification | > 13.6 high; 12.4–13.6 medium; < 12.4 low | W/kg | tertiles | same | same |
| Untrained adult PP | ~8–10 (men) **(weak source)**; < 6 "untrained male" (calculator site) **(conflicting)** | W/kg | — | untrained | [Pabau](https://pabau.com/blog/wingate-test/); [Topend Sports](https://www.topendsports.com/testing/tests/wingate.htm) |
| Pro cyclists, 30 s record power | ~14 | W/kg | SRM field power files | male professionals (n = 144) | [GSSI summary of Valenzuela 2022](https://www.gssiweb.org/sports-science-exchange/article/nutrition-for-successful-cycling-performance) |
| Wilkie / Davies, 5 s and 10 s | ~1200 W (5 s), ~800 W (10 s); up to 4 kW for 0.2 s | W | Literature synthesis | champion athletes | [Evans, "The human power plant"](https://www.humanpoweredflight.co.uk/hpfMedia/media/7/Evans-the-human-power-plant.pdf) |
| Wilkie 0.1–5 min band | ~2 → 0.5 hp (~1.5 kW → 370 W) | hp | synthesis | champion athletes | [Wilkie 1960](https://scilit.com/publications/508e131d620d926e02f79c9869f89d01) |
| Protocol sensitivity | load 7.5% BM (untrained) vs 8.5–10% (trained) | — | — | — | [Topend Sports](https://www.topendsports.com/testing/tests/wingate.htm) |

### B2.3 Sustained power (~1 h, FTP)

| Quantity | Value / range | Units | Method | Population | Source |
|---|---|---|---|---|---|
| Pro male, 60 min record power | "nearly 6" (top riders); > 5.5 needed for 75th percentile | W/kg | Record power profile from 129,262 race/training files | 144 male professionals (4 teams, 8 yr) | [Valenzuela et al. 2022, IJSPP 17:701](https://velo2max.com/wp-content/uploads/2024/08/ijspp-article-p701.pdf); [GSSI](https://www.gssiweb.org/sports-science-exchange/article/nutrition-for-successful-cycling-performance) |
| Pro thresholds, other durations | > 6.3 (20 min), 4.9 (120 min), 4.4 (240 min) | W/kg | same | same | [wattkg summary](https://www.wattkg.com/power-records/) |
| Trained cyclists, 60 min (different cohort) | 4.2 ± 0.4 | W/kg | Lab/field | trained (sub-pro) | [RPP: Fatigue Matters](https://www.researchgate.net/publication/358979528_The_Record_Power_Profile_of_Male_Professional_Cyclists_Fatigue_Matters) |
| Hour-record-level FTP (Wiggins) | ~6.4–6.6 **(secondary estimate)** | W/kg | — | world-class | [Rouvy](https://rouvy.com/blog/what-is-a-good-ftp-cycling) |
| FTP classification, men | < 2.23 "untrained"; ≥ 5.05 "superior" | W/kg | Consumer classification table | — | [Garmin](https://www8.garmin.com/manuals-apac/webhelp/fenixe/EN-SG/GUID-BCF7F912-F80A-4951-81C1-F5A3635731FB-849.html) |
| FTP classification, women | < 1.90 untrained; ≥ 4.30 superior | W/kg | same | — | same |
| Untrained men, incremental peak power | 305 ± 14 W (→ 315 ± 16 after strength training) | W | Incremental ergometer test (peak, not 1 h) | previously untrained men | [PubMed 16015143](https://pubmed.ncbi.nlm.nih.gov/16015143/) |
| Untrained sedentary VO₂max | 35.5 vs trained 63.8 | mL·kg⁻¹·min⁻¹ | Lab test | 6 untrained vs 6 trained | [Simon et al.](https://data.zhenzhi.com/details/1/983718503) |
| Untrained 1 h power estimate | ~1.5–2.2 [derived: VO₂max 35–45 × ~65% at threshold × ~20% GE] | W/kg | — | sedentary men | — |
| Wilkie steady-state band (5–150 min) | ~0.5 → 0.4 hp (≈ 370 → 300 W) | hp | synthesis | champion athletes | [Wilkie 1960](https://scilit.com/publications/508e131d620d926e02f79c9869f89d01) |
| All-day work | ~0.2 hp (~150 W); ordinary people < 70–80% of champion values | hp | synthesis | — | same |
| Elite VO₂max | 70–75 (pro), 68–75 (elite), 65–73 (amateur) | mL·kg⁻¹·min⁻¹ | review | cyclists | [PMC6835290](https://pmc.ncbi.nlm.nih.gov/articles/PMC6835290) |

### B2.4 Single punch and kick: force, energy, "power"

| Quantity | Value / range | Units | Method | Population | Source |
|---|---|---|---|---|---|
| Straight punch peak force | 3427 ± 811 | N | Hybrid III dummy face, load cells | 7 Olympic boxers | [Walilko et al. 2005](https://pmc.ncbi.nlm.nih.gov/articles/PMC1725037) |
| Hand velocity at impact | 9.14 ± 2.06 | m/s | same | same | same |
| Effective punch mass | 2.9 ± 2.0 | kg | Momentum transfer | same | same |
| Punch kinetic energy at impact | ≈ ½·2.9·9.14² ≈ 120 J [derived] | J | — | — | — |
| Highest kick mean force (review) | 9015 vs highest punch mean 3427 **(secondary)** | N | Review of force studies (different devices) | various | [AgentMMA summary](https://agentmma.com/mma-lab/how-hard-mma-fighters-hit) |
| Device "impact power" (strikes) | 5782 ± 230 (level, centre); 4864 ± 119 (off-centre); 4500 ± 220 (inclined); 3390 ± 151 (inclined, off-centre) | W | Commercial instrumented pad (proprietary "power") | trained strikers | [Del Vecchio et al. 2022, *Sports*](https://doaj.org/article/beef9bf4c9914890a183773f3946dd86) |
| Work/power in karate reverse punch | differs between 4 karate styles | — | Kinematics | karateka | Stull & Barham (cited in [Konstanz CPA](https://ojs.ub.uni-konstanz.de/cpa/article/view/1806/1679)) |
| Average mechanical power accelerating the fist [derived] | KE ≈ 120 J over ~0.1–0.2 s of acceleration → ~0.6–1.2 kW average body output into the arm/fist segment; peak higher | W | — | — | — |

Interpreting "punch power":
- Device "impact power" in watts is usually force × velocity during contact, or
  a proprietary metric. It is **not** comparable to the metabolic or ergometer
  watts above.
- For game physics, model a strike by **effective mass × impact velocity**
  (momentum ≈ 26 kg·m/s, energy ≈ 120 J for an Olympic straight punch).
- Kicks have about 2× the foot speed (≈ 18 m/s) and a larger effective
  mass. The resulting forces are about 2–3× a punch's, but the kick is
  slower to deliver.

---

## Suggested game parameters [derived from the above]

| Parameter | Untrained | Trained | Elite |
|---|---|---|---|
| Simple RT (visual) | 250–330 ms | 190–230 ms | 160–200 ms |
| Simple RT (auditory) | 200–280 ms | 160–190 ms | 120–170 ms (floor ~85–100) |
| Choice RT (2–4 options) | 350–450 ms | 300–400 ms | 250–350 ms; experts gain mainly via anticipation of opponent cues |
| Jab / cross MT | 400 ms | 300 ms | 200–250 ms (in-combo ~130 ms) |
| Hook MT | 500 ms | 400 ms | 350 ms |
| Roundhouse kick (foot-off → contact) | 450 ms | 350 ms | 260 ms |
| Peak instantaneous power (jump) | 30–45 W/kg | 45–55 W/kg | 60–70 W/kg |
| 5–30 s power (Wingate PP / MP) | 8 / 6 W/kg | 11 / 8 W/kg | 13–14+ / 9–10 W/kg |
| 1 h power (mechanical) | 1.5–2.2 W/kg | 3–4.2 W/kg | 5.5–6.5 W/kg |
| Gross efficiency | ~18–20% | ~20–22% | ~20–23% |
