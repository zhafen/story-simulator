# B5 — Energy/force to break, crack, or penetrate walls and barriers

Research for a physics-grounded combat system in which barriers have an energy budget that impacts use up.

**How this was gathered.** Only web-search result summaries were available. Every direct page fetch (TTU, structuremag.org, PMC, fib structuralcodes, Wikipedia, FEMA mirrors) failed because the session's network allowlist blocks those hosts. Every number below therefore comes from a search-surfaced standard, manufacturer, or paper excerpt, with its URL. Numbers marked **[derived]** are my own arithmetic from cited inputs (KE = ½mv², PE = mgh, G = K²/E). Numbers marked **[gen. knowledge, unverified]** were not confirmed by any source. Treat those as placeholders.

Unit conversions used: 1 ft·lbf = 1.3558 J; 1 lb = 0.4536 kg; 1 mph = 0.4470 m/s; 1 ft/s = 0.3048 m/s.

---

## 1. Standard impact tests: the impactor, the energy, and what counts as failure

### 1.1 Gypsum board / drywall: ASTM C1629 (abuse-resistant panels)

| Material | Thickness | Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|---|---|
| Gypsum panel, Level 1 / 2 / 3 | Not stated (in practice 12.7–15.9 mm boards) | Soft-body impact: minimum energy to structural failure | 122 / 265 / 408 (90 / 195 / 300 ft·lbf) | J | Heavy bag swung into the panel (blunt, large area) | ASTM C1629-06 table via search; Gyprock note: https://celumcsrcomaublobs.blob.core.windows.net/celum/33013_yConnect_Document_GYPROCK-WP-Specifying%20Impact%20Resistant%20Plasterboard%20for%20Commercial%20Applications.pdf ; https://dl.azmanco.com/standards/ASTM-C/ASTM-C-Series-Full/C/C1629.pdf |
| Gypsum panel, Level 1 / 2 / 3 | same | Hard-body impact: minimum energy for the impactor to penetrate the face | 68 / 136 / 204 (50 / 100 / 150 ft·lbf) | J | Annex A1 weighted swinging ram (hard, small-area nose) | PABCO QuietRock test report citing C1629-15: https://cds.vestranet.com/uploads/products/quietrock-530652418.pdf |
| Ordinary (non-abuse) gypsum board | 12.5 mm | Minimum bending breaking load | ≥300 parallel / ≥725 transverse | N | EN 520 / DIN 18180 3-point bend | https://produkte.rigips.de/downloads/engl_pdb_rigips_die_harte_12_5.pdf |

- The C1629 levels are minimums for abuse-resistant boards. Ordinary 1/2" board will sit at or below Level 1. My estimate is about 30–70 J to punch through with a hard nose **[gen. knowledge, unverified]**.
- **Per thickness [derived]:** Level 1–3 hard-body on 12.7–15.9 mm board works out to roughly **4–16 J/mm**.
- **Sharp vs blunt:** For the same board class, the blunt soft-body threshold is about 1.8–2.0× the hard-body penetration threshold (122/68, 265/136, 408/204).

### 1.2 Wood-frame walls, siding, brick veneer, CMU, steel: windborne-debris tests (ASTM E1996, ICC 500, FEMA P-361)

| Material / assembly | Thickness | Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|---|---|
| ASTM E1996 Level D missile | — | 9 lb (4.08 kg) 2x4 at 50 ft/s (15.2 m/s, 34 mph) | KE ≈ **474 J**; p ≈ 62 kg·m/s **[derived]** | J | Air cannon, end-on lumber | https://www.engineeringexpress.com/wiki/astm-e1996-missile-levels-definition ; https://grahamwindows.com/wp-content/uploads/hi_test-methods.pdf |
| ASTM E1996 Level E missile | — | 9 lb 2x4 at 80 ft/s (24.4 m/s) | KE ≈ **1,210 J** **[derived]** | J | same | https://www.engineeringexpress.com/?p=20709 |
| ASTM E1996 small missile (glazing) | — | 2 g steel ball at 130 ft/s (39.6 m/s) | KE ≈ **1.6 J** **[derived]** | J | Air cannon | https://grahamwindows.com/wp-content/uploads/hi_test-methods.pdf |
| Wood stud wall: vinyl or fiber-cement siding, 1/2" OSB, 2x4 @ 16" with insulation, 1/2" gypsum | ≈ 115 mm total | Perforated by Level D missile | **perforated at 474 J** (upper bound for perforation) | J | TTU 2004 BIA-sponsored cannon test | https://www.masoncontractors.org/2004/11/17/hurricane-guidelines-homes-featuring-brick-veneer-far-exceed-strictest-hurricane-building-standards ; https://images.greenbuildingadvisor.com/app/uploads/2012/03/25025447/TT%20Debris%20Impact%20Testing.pdf |
| Same wall with brick veneer instead of siding | +~90 mm brick | 9 lb 2x4 at 34 mph bounced off, no interior damage. Perforation speed **>80 mph** | KE > **2,600 J** **[derived]** (9 lb at 35.8 m/s) | J | TTU cannon | same as above; https://landscapearchitect.com/landscape-articles/brick-stands-up-to-the-big-bad-wolf-and-hurricanes |
| Brick veneer alone, tornado missile | ~90 mm | Perforation speed ≈ 50 mph (80 km/h) for a 15 lb 2x4 | KE ≈ **1,700 J** **[derived]** (6.80 kg at 22.4 m/s) | J | TTU / McGinley paper (search excerpt) | https://canadamasonrydesigncentre.com/wp-content/uploads/13th_symposium/065-McGinley-Paper-2.pdf |
| ICC 500 / FEMA P-361 tornado wall criterion | — | 15 lb (6.80 kg) 2x4 at 100 mph (44.7 m/s); roof/falling-debris case 67 mph | **6,800 J** horizontal / **3,050 J** vertical **[derived]** | J | Cannon. Fail = any part of the missile enters the protected space | https://www.ul.com/thecodeauthority/knowledge/icc-500-certified-protective-storm-shelters-and-safe-rooms ; https://www.depts.ttu.edu/nwi/research/DebrisImpact/downloads/ProtocolsforDebrisImpactTesting10222015.pdf |
| Brick veneer + air cavity + 8" partially grouted CMU (hit on an ungrouted core) | ≈ 90 + 50 + 203 mm | 3 shots at ICC 500 speed: veneer broke, CMU undamaged | passes 6.8 kJ ×3 | J | TTU 2014 | https://www.structuremag.org/article/tornado-debris-impact-testing-and-masonry/ |
| Solidly grouted masonry wall | 8" (203 mm) | Earlier passing ICC 500 solutions were solidly grouted. Bare ungrouted CMU was not shown to pass | passes 6.8 kJ | J | TTU | same |
| Steel sheet | 12 gauge (≈2.66 mm) or heavier | "Never perforated" by 15 lb 2x4 at 100 mph in TTU lab tests (FEMA P-361, quoted second-hand) | resists ≥ **6.8 kJ** blunt | J | TTU cannon | https://www.sambuz.com/doc/shrc-shelters-ppt-presentation-546820 |
| FPL laminated 2x8 + 3/4" CDX plywood shelter wall | ≈ 57 mm | Took **6 shots clustered within ~18 in** to fail ICC 500. Only the plywood cracked | ~6 × 6.8 kJ cumulative | J | USDA FPL cannon | https://www.Apawood.Org/Data/Sites/1/documents/technicalresearch/rip/fplrip-4714-028-falk-saferoom-final.pdf ; https://www.asme.org/topics-resources/content/wooden-tornado-shelter-withstands-high-winds |

**Takeaway ladder (blunt, ~0.0034 m² end-on 2x4 face):**
- Light-frame wall with siding: < 474 J.
- Brick-veneer frame wall: 1.7–2.6 kJ.
- Grouted CMU, 8" RC, or 12 ga steel plate: > 6.8 kJ.

### 1.3 Glass (annealed, tempered, laminated)

| Material | Thickness | Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|---|---|
| Laminated security glass EN 356 P1A / P2A / P3A / P4A | P1A listed at ≥16 mm in one leaflet (typical P1A–P2A products are thinner; check) | 4.11 kg steel ball, 3 drops from 1.5 / 3 / 6 / 9 m. Pass = no penetration within 5 s | per drop **60 / 121 / 242 / 363 J** [derived]; P1A total 181 J | J | Ball drop, triangle pattern | https://www.specifiedby.com/toughglaze/tg-secure-laminated-glass-range-for-manual-attack/tg-secure-en356-leaflet_33ec493e.pdf |
| EN 356 P5A | — | 9 drops from 9 m | total **3,262 J** (9 × 363) | J | same | same |
| EN 356 P6B–P8B | P8B ≥18.5 mm | Hammer + axe strike counts (P8B: 71+ strikes) | strike counts, not J | strikes | Machine-held axe | same; https://www.pressglass.com/wp-content/uploads/2023/03/PG_SZYBY-BEZP_EN_12_2022.pdf |
| Safety glazing EN 12600 class 3 / 2 / 1 | any | 50 kg twin-tyre pendulum dropped 190 / 450 / 1200 mm | **93 / 221 / 589 J** [derived] | J | Soft-body pendulum on a 876×1938 mm pane. Rating also records breakage mode A/B/C | https://solarscreen.eu/en/blog/en-12600-safety-glazing-classes-pendulum-test-explained/ ; https://www.spevetro.it/en/portfolio/double-wheel-impact-test-pendulum-test/ |
| Safety glazing CPSC 16 CFR 1201 Cat I / Cat II (= ANSI Z97.1 B / A) | any | 100 lb bag dropped 18 / 48 in | **203 / 542 J** (150 / 400 ft·lbf) | J | Soft-body bag. Must not break dangerously (it may break) | https://www.gpo.gov/fdsys/pkg/CFR-2014-title16-vol2/pdf/CFR-2014-title16-vol2-sec1201-2.pdf ; https://idighardware.com/?p=14069 |
| Laminated glass (ASTM F3006/F3007) | — | 2.3 kg, 83 mm steel ball, user-chosen height | test frame only | — | Ball drop | https://webstore.ansi.org/standards/astm/astmf300625 |
| Soda-lime glass, annealed | material | K_IC | 0.75 (0.70–0.83) | MPa·m^½ | Indentation / fracture mechanics | https://www.makeitfrom.com/material-properties/Annealed-Soda-Lime-Glass ; https://www.gft.eng.cam.ac.uk/system/files/documents/overend-asce-paper-draft.pdf |
| Soda-lime glass | material | G_c = K²/E (E ≈ 70 GPa [gen. knowledge]) | ≈ **8 J/m²** [derived] | J/m² | LEFM | derived |
| Fully tempered glass | — | Surface compression, ASTM C1048 minimum | ≥69 (edge ≥67) | MPa | Residual stress | https://www.vitroglazings.com/media/acmdf3a5/vitro-td-138.pdf ; https://www.bdcnetwork.com/12-facts-about-heat-treated-glass-why-stronger-isnt-always-better |
| Heat-strengthened glass | — | Surface compression | 24–52 | MPa | same | same |
| Tempered vs annealed strength | — | Strength multiple | 4–5× (heat-strengthened ≈ 2×) | — | — | same |

- Glass breaks from stress at a flaw, not from energy budget. A 1.6 J steel ball is the E1996 standard glass-breaker for annealed glass. Soft-body tests need 90–590 J and mostly test *how* the pane breaks.
- **Sharp vs blunt:** Glass is the most impactor-sensitive material in this list. A hardened point concentrates stress and is famously effective on tempered glass. Since K_IC is the same, design-wise model glass as low HP with a stress threshold, not a J budget.
- **Grooved annealed glass** is about 79% weaker than plain glass under a 1/2 lb ball drop, so surface flaws dominate (https://www.vitroglazings.com/media/1prndvol/vitro-td-127.pdf).

### 1.4 Doors and forced entry (timed or energy-rated)

| Item | Quantity | Value | Units | Method | Source |
|---|---|---|---|---|---|
| ASTM F476 swinging door assembly | Door ram impact energy | **200 J** (148 ft·lbf) per blow | J | Horizontal ram, repeated blows. Grades 10–40 = more blows/energy | https://cdn.standards.iteh.ai/samples/114453/c536d5e758bf40268d9d1cfae739a565/ASTM-F476-23.pdf |
| ASTM F476 | Component ram / vertical knob impactor | **100 J** (74 ft·lbf) | J | Pendulum | https://cdn.standards.iteh.ai/samples/87203/51cd079d4e2240acb26a4e0f0341373c/ASTM-F476-14.pdf |
| F476 Grade 10 vs Grade 40 | Grade 10 = minimum, single-family low-crime; Grade 40 = small commercial, high-crime | — | — | Annex A2 | https://obc-342.pages.dev/volume-2/appendix-a/explanatory-b/b-9.7.5.2.(2)-appx |
| Human front kick (attacker benchmark) | 67% of 52 adults averaged >100 J; about 1 in 100 adults >215 J | 100–215 | J | Instrumented kick rig | https://lida.sport-iat.de/twm/Record/4049361?lng=en ; https://peeref.com/works/44735160 |
| ASTM F3038 forced-entry (doors, windows, panels) | Rated time against a mob with hand tools | 5 / 15 / 30 / 60 | min | Timed attack | https://steeldoor.org/wp-content/uploads/2020/04/Forced20Entry20Resistant.pdf ; https://cdn.standards.iteh.ai/samples/111025/11688ae8790647b98de91a46c4bc1db7/ASTM-F3038-21.pdf |
| EN 1627/1630 RC2 / RC3 / RC4 / RC5 / RC6 | Resistance (working) time | 3 / 5 / 10 / 15 / 20 | min | Manual attack. RC1 = kicks and pulls only (no time). RC4 adds axe and hammer. RC5–6 add an angle grinder | https://www.thermosash.co.nz/media/srfflvz1/202207_summary-resistance-classes-din-en-1627-1630_vk.pdf ; https://sitec.de/da/things-to-know/break-in-resistance |
| UL 752 Level 1 / 2 / 3 | Bullet muzzle energy resisted | 515–624 / 743–899 / 1,317–1,593 | J | Ballistic (very sharp, small area) | https://www.armorcore.com/wp-content/uploads/Armorcore_UL752_Specs_Para.pdf |
| UL 752 Level 4 / 5 / 8 | same | 3,498–4,929 / 3,416–4,133 / 3,416–4,133 (L8 = multi-shot) | J | same | same |
| UL 752 Level 10 | .50 BMG | ~16,870 | J | same | https://www.dkhardware.com/blog/ul-752-bullet-resistant-levels-explained/amp/ |

- **Game use.** A solid-core door holding up against 200 J blows is a reasonable F476-type benchmark. A strong kick of 100–215 J matches a single ram blow, so door durability is better counted in blows than in a single-hit threshold.
- I did not find a source for the energy to break a hollow-core door versus a solid wood door. My estimate for a hollow-core door is tens of J **[gen. knowledge, unverified]**.

### 1.5 Concrete: repeated drop weight (ACI 544-2R)

| Material | Thickness | Quantity | Value | Units | Method | Source |
|---|---|---|---|---|---|---|
| Concrete disk, Ø150 mm | 63.5 mm | Energy per blow | 4.54 kg × 0.457 m → **20.4 J/blow** [derived] | J | Repeated drop onto a 63.5 mm steel ball. Counts N₁ = blows to first visible crack, N₂ = blows to failure | https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9182244/ |
| Plain concrete reference | 63.5 mm | N₁, N₂ | typically on the order of 10–100 blows, with very large scatter (CoV often >50%) **[gen. knowledge, unverified]** | blows | same | same (could not fetch the full text) |

The ACI 544 result itself shows damage accumulating from impacts that are each below the threshold: every 20 J blow is far too weak to break the disk alone.

---

## 2. Material fracture properties (to convert impacts into an energy per area of new crack)

| Material | Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|---|
| Concrete (normal) | K_IC | 0.2–1.4 | MPa·m^½ | Fracture mechanics compilations | https://sv.rkriz.net/classes/MSE2094_NoteBook/97ClassProj/exper/gordon/www/fractough.html ; https://www.chemeurope.com/en/encyclopedia/Fracture_toughness.html |
| Concrete (normal, ~20–50 MPa) | Fracture energy G_F (work of fracture, RILEM 3-pt bend / wedge split) | ~100–150 typical; 25–200 literature span. One FE-validation specimen = 124.6 N/m | N/m (= J/m²) | RILEM TC50 notched beam | Ranges **[gen. knowledge, unverified]**; single value: https://lajss.org/index.php/LAJSS/article/download/109/103/106 |
| Concrete | G_F model | fib MC2010 Eq. 5.1-9, G_F = 73·f_cm^0.18 N/m (f_cm in MPa) → ≈ **135 N/m at 30 MPa** [derived]. Search did not reproduce the text verbatim | N/m | Code formula | https://fib-international.github.io/structuralcodes/api/codes/mc2010/material_concrete.html (blocked; formula from memory) |
| Concrete | LEFM G = K²/E at K=1, E=30 GPa | ≈ 33 [derived]. This is lower than G_F because it ignores the fracture process zone | J/m² | — | derived |
| Masonry (historic, mesoscale model) | Size-independent G_F | 33 (imperfect bond) – 64 (perfect bond) | N/m | Wedge-split simulation | https://arxiv.org/pdf/0804.3262 |
| Brick–mortar interface | Mode I G_f | ~5–20 per Lourenço-style micro-models **[gen. knowledge, unverified]**. The interface is the weak link | N/m | Bond wrench / direct tension | https://link.springer.com/article/10.1617/s11527-023-02144-6 (qualitative) |
| Norway spruce | Specific fracture energy (work of fracture, SENB) | 221 | J/m² | SENB WOF | https://link.springer.com/article/10.1007/s00226-024-01595-6 |
| Birch | same | 656 | J/m² | same | same |
| Wood (TL vs RL) | TL generally lower G_f than RL | — | — | — | same |
| Plywood vs OSB | Plywood absorbs impact better than OSB or solid wood at 10–98 J impacts | qualitative | — | Drop weight on small alder panels | https://fpj.kglmeridian.com/view/journals/fpro/71/4/article-p362.xml |
| Wood structural panels | ASTM D3499 pendulum toughness = energy to fail a beam specimen | method | J | Pendulum | https://standards.iteh.ai/catalog/standards/astm/79e7641b-a4dd-4a3e-a40a-d7879d5fcd94/astm-d3499-94 |
| Freshwater / sea ice | K_IC | ≈ 0.1 (100 kPa·m^½); insensitive to T near the surface | MPa·m^½ | Review (Schulson) | https://physicstoday.aip.org/features/ice-fracturing |
| Freshwater ice | K_IC trend | Falls with faster loading and nearer melt; liquid water lowers it | — | Compact tension, −1 to −46 °C | https://www.cambridge.org/core/services/aop-cambridge-core/content/view/058A5E818BC536BAF359F9FEDE823D5C/S0022143000014118a.pdf/fracture-toughness-of-fresh-water-ice.pdf |
| Ice | G = K²/E (E ≈ 9 GPa [gen. knowledge]) | ≈ **1 J/m²** [derived] | J/m² | LEFM | derived |
| Freshwater ice | Flexural strength | 1.67 ± 0.22 | MPa | Beam bend at 10⁻⁷ s⁻¹ | https://www.cambridge.org/core/product/C8EF64EC89D2D8D6FC3E2BCE9594630E/core-reader |
| Ice | Compressive/tensile strength ratio | ~8 (−10 °C) to ~15 (−50 °C). Compressive ~10 MPa order, so tensile ~1 MPa [inference] | — | Schulson group | same |
| Steel alloy | K_IC | ~50 (carbon steels 50–150) | MPa·m^½ | — | https://sv.rkriz.net/classes/MSE2094_NoteBook/97ClassProj/exper/gordon/www/fractough.html |
| Steel | G = K²/E (E = 200 GPa) | ≈ 12,500 (at K=50) [derived] | J/m² | LEFM | derived |
| Aluminium alloy / pure | K_IC | 36 / 14–28 | MPa·m^½ | — | same |
| Aluminium | G (E = 70 GPa) | ≈ 18,500 (K=36) [derived] | J/m² | LEFM | derived |

Note: for metals, perforation is dominated by plastic work (dishing, petalling, plugging), not by crack surface energy. Use the empirical 12 ga ≥ 6.8 kJ blunt benchmark from §1.2 rather than G. Ballistic-limit formulas (de Marre, Jacobs, Wierzbicki petalling) exist, but their coefficients were not verified (https://navweaps.com/index_nathan/Hstfrmla.php ; https://engineeringmechanics.cn/en/article/id/3399).

### Per-area / per-thickness conversion (G_f × crack area) **[derived]**

Energy to cut a through-hole of perimeter P in a wall of thickness t ≈ G_f · P · t. This is a lower bound: real impacts waste most energy on elastic and plastic deformation, friction, and spall.

| Material | G_f | 0.3 m × 0.3 m hole (P = 1.2 m) in thickness t | Energy |
|---|---|---|---|
| Glass, 6 mm | 8 J/m² | 1.2 × 0.006 m² | 0.06 J (shows that glass is stress-limited, not energy-limited) |
| Ice, 100 mm | 1 J/m² | 1.2 × 0.1 m² | 0.12 J |
| Concrete, 150 mm | 130 J/m² | 1.2 × 0.15 m² | 23 J |
| Spruce plank, 38 mm | 221 J/m² | 1.2 × 0.038 m² | 10 J |

These pure-fracture numbers are 1–3 orders of magnitude below the test-based thresholds in §1. Test thresholds (E1996, ICC 500, C1629) are the right calibration for a game. Fracture energy explains *scaling* only: required energy grows with thickness × crack length, so it grows faster than linearly when bigger holes also need thicker walls.

---

## 3. Plain and reinforced concrete versus hard missiles

- The modified Petry, BRL, ACE, modified NDRC, Degen, Hughes, and UKAEA (Barr) formulas predict penetration depth. Perforation thickness ≈ 1.2–1.3 × penetration depth; scabbing thickness ≈ 2 × penetration depth **[gen. knowledge, unverified]**. They depend on missile mass, diameter, velocity, and f_c' (https://pp.bme.hu/ci/article/download/8605/7152 ; https://typeset.io/pdf/a-review-local-failure-on-concrete-target-due-to-projectile-1c8yr9pp60.pdf ; https://carleton.ca/sadeghian/publications/prediction-of-perforation-velocity-of-hard-missile-impacts-on-reinforced-concrete-wall-panels).
- Calibration point: 6" (152 mm) reinforced concrete walls are standard FEMA P-361 / ICC 500 passing assemblies for 6.8 kJ blunt **[gen. knowledge, unverified — FEMA 320 tables not fetchable]**. Concrete-home literature claims the same: https://cement.org/cement-concrete/paving/buildings-structures/concrete-homes/technology-briefs/concrete-homes-built-in-safety

---

## 4. Impactor geometry (sharp vs blunt)

1. **Gypsum:** Penetrating with a hard nose takes about 0.5× the energy of a soft-body bag failing the board (C1629 ratios above).
2. **Glass:** A small hard steel ball at 1.6 J (E1996 small missile) breaks annealed glass. Soft-body safety tests use 93–589 J. Breakage is stress-at-flaw controlled, so sharp or hard contact wins by orders of magnitude.
3. **Masonry and walls:** The same 2x4 end-on (≈ 38×89 mm ≈ 0.0034 m²) perforates siding walls at 474 J. At 2.6 kJ it is still stopped by brick veneer.
4. **Metals and composites under bullets:** UL 752 shows that very small-area, high-velocity impactors need dedicated armor at 0.5–17 kJ. Sheet steel that stops a 6.8 kJ timber may not stop a 3.5 kJ rifle bullet **[inference]**.
5. **Modelling rule of thumb.** Use effective damage = E × (A_ref / A_contact)^α with α ≈ 0.3–0.5 **[gen. knowledge, unverified — design heuristic]**. Optionally add a hardness factor (impactor hardness / target hardness).

## 5. Do repeated sub-threshold impacts accumulate?

**Yes, for quasi-brittle and fibrous materials.**
- **ACI 544 concrete:** 20 J blows accumulate to first crack and then failure, with large scatter.
- **FPL wood wall:** Six clustered 6.8 kJ shots were needed, and clustering mattered (all within ~18 in).
- **EN 356:** Multiple 4.11 kg drops; the P5A rating requires 9.
- **EN 12600:** Records the number of impacts survived (e.g. "2(B)2").
- **ASTM F476 and EN 1630:** Repeated blows and timed attack, i.e. cumulative.
- **Brick-veneer-over-CMU:** Three shots hit; the veneer was sacrificial and absorbed most of the energy.

**Exceptions:**
- **Glass:** Little memory until a flaw grows. It fails abruptly once one hit exceeds the stress threshold, although surface damage (grooves, chips) cuts strength by up to ~79%.
- **Ice:** Flexural strength *rises* under cyclic loading (Schulson group, link above). Low-rate damage partly heals.

**Suggested game model:**
- Budget decrement = max(0, E_hit − E_floor) for each hit, with E_floor ≈ 5–20% of the single-hit threshold **[design suggestion]**.
- Track decrements locally (per wall cell). Clustered hits should drain the same cell.
- Glass: use a stress threshold with a flaw-severity multiplier instead.

---

## 6. Suggested single-hit thresholds for the game (blunt, ~0.003–0.01 m² contact)

| Barrier | Crack / visible damage | Penetrate / breach | Basis |
|---|---|---|---|
| Annealed window glass 3–6 mm | ~1–5 J (hard, small) | same, shatters | E1996 small missile 1.6 J |
| Tempered glass | ~4–5× annealed by stress | shatters fully | C1048, 4–5× |
| Laminated glass P1A–P2A | 60–120 J per hit, takes multiple hits | 180–360 J total | EN 356 |
| Ordinary 1/2" drywall | ~30 J | 30–70 J (hard) / ~120 J (bag) | C1629 Level 1 as upper anchor |
| Abuse-resistant drywall | 68–204 J | 122–408 J (soft) | C1629 |
| Wood-stud wall (siding + OSB + drywall) | <200 J | ≤474 J | E1996 D / TTU |
| Hollow-core / solid wood door | tens of J / 100–200 J | multiple 200 J blows | F476, kick data |
| Brick veneer (single wythe) | ~500 J | 1.7–2.6 kJ | TTU |
| 8" grouted CMU / 6" RC / 12 ga steel plate | ~1–2 kJ surface spall | >6.8 kJ (multi-hit for wood missiles) | ICC 500 / FEMA P-361 |
| Bullet-rated barrier UL 752 L1–L10 | — | 0.5–17 kJ (sharp) | UL 752 |
| Lake ice 100 mm | few J (tiny K_IC) | tens of J to break a slab | K_IC 0.1, flexural 1.7 MPa (scale estimate) |

All rows in §6 are design-level syntheses. Only the anchor columns are directly sourced.

## Gaps / not verified

- Full ASTM C1629-19 tables.
- F476 Grade 10–40 blow counts.
- F3038 tool lists.
- The exact fib MC2010 G_F formula text.
- ACI 544 plain-concrete blow counts.
- Masonry interface G_f.
- Per-thickness plywood and OSB penetration energy.
- Annealed-glass J thresholds by thickness.
- Ice impact-crushing data.

All need the blocked hosts (depts.ttu.edu, structuremag.org, pmc.ncbi.nlm.nih.gov, fib-international.github.io, en.wikipedia.org, gohsep.la.gov, canadamasonrydesigncentre.com) to be allowed in the session's network settings so the primary texts can be fetched.
