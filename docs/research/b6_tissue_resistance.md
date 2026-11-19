# B6 — Tissue & bone resistance to penetration and fracture

Research notes for a physics-grounded combat model in which an entity's
tissues/bones have an energy budget that impacts deplete. Every number
carries a URL. **Provenance caveat:** in this session direct page fetches
were blocked by the network sandbox (pmc.ncbi.nlm.nih.gov, arxiv.org,
vtechworks.lib.vt.edu, springermedicine.com all failed DNS), so values come
from search-engine extracts of the cited pages (abstracts/snippets), not
full-text reads. Values marked **(secondary)** were reported by a review or
summary rather than the primary paper. Treat all as order-of-magnitude
anchors with large inter-subject scatter (CV 20-60% is typical in cadaver
work).

Abbreviations: QS = quasi-static; PMHS = post-mortem human subject;
3PB = three-point bending; J-int = J-integral.

---

## 1. Sharp penetration (knives, glass, spikes)

| Target | Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|---|
| Skin simulant (biaxially tensioned), 4 knife types | Force to initiate penetration | 18-36 | N | Instrumented knife, biaxial tension rig | https://arxiv.org/pdf/0811.3955 |
| Skin simulant, 4 knife types | Energy to penetrate | ~0.25 (range 0.17-0.56) | J | Same | https://arxiv.org/pdf/0811.3955 |
| Skin, sharp knife | Minimum puncture force | 10-20 | N | Engineering review of stab mechanics | https://www.engineersireland.ie/Engineers-Journal/Mechanical/the-mechanics-of-stabbing-assessing-stab-penetration-forces |
| Skin, sharp glass shard (O'Callaghan et al.) | Energy for skin penetration | 7.7 | J | Drop/impact test, cited (secondary) | https://arxiv.org/pdf/0811.3955 |
| Skin + clothing system | Penetration force | >40 (vs ~20 bare for same knife) | N | Materials test machine into skin simulant (AAFS) | https://www.aafs.org/sites/default/files/media/documents/AAFS-2013-C26.pdf |
| Cotton T-shirt over simulant | Added penetration force | ~8 | N | Nolan, Hainsworth & Rutty 2013 JFS, MTS into foam-silicone simulant | https://www.ojp.gov/ncjrs/virtual-library/abstracts/forces-required-knife-penetrate-variety-clothing-types |
| T-shirt + jacket | Additional added force | ~21 | N | Same | https://www.ojp.gov/ncjrs/virtual-library/abstracts/forces-required-knife-penetrate-variety-clothing-types |
| Porcine rib (young adult), pocket knives | Energy for complete rib perforation | 11-16 | J | Drop-tower stab into porcine ribs | https://www.springermedicine.com/stabbing-energy-and-force-required-for-pocket-knives-to-pierce-r/22003220 |
| Skin vs. deeper tissue (Knight 1975) | Qualitative | Skin is the main resistance; fat/muscle need less; tip sharpness dominates | — | Spring-loaded stab device into cadavers (secondary) | https://link.springer.com/article/10.1007/s00414-017-1702-7 |
| Skin tension effect (Gilchrist & Keenan 2008) | Qualitative | Higher in-plane skin tension -> lower penetration force/energy/displacement | — | Biaxial skin-simulant rig | https://read.qxmd.com/read/18093771/measuring-knife-stab-penetration-into-skin-simulant-using-a-novel-biaxial-tension-device |

### Attacker-side stab energy (for context: what a human can deliver)

| Quantity | Value | Units | Method | Source |
|---|---|---|---|---|
| Straight / underarm stab, mean | 66.5-67.1 | J | Motion capture, volunteers | https://core.ac.uk/download/42144033.pdf |
| Overarm stab, mean | 92.8 | J | Same | https://core.ac.uk/download/42144033.pdf |
| 95th pct axial force / energy, 20 volunteers, near-max effort (thrust, sweep, overhand) | 1885 N / 69 J | N, J | Instrumented target | https://dspace.lib.cranfield.ac.uk/bitstream/1826/8735/1/Stab%20paper%20Full%20text.pdf |
| Delivered energy is mainly combined KE of knife + attacker's arm | — | — | Horsfall (Cranfield thesis) | https://dspace.lib.cranfield.ac.uk/items/a6d72e14-1102-4c2c-9351-ce21b7f2d3c0/full |

### Stab-armour standards (HOSDB 2007 / CAST)

| Level | E1 energy / max penetration | E2 energy / max penetration | Source |
|---|---|---|---|
| KR1 | 24 J / 7 mm | 36 J / 20 mm | https://www.ppss-group.com/wp-content/uploads/2017/04/PPSS-Stab-Resistant-Vest-Covert-KR1.pdf ; https://www.bodyarmornews.com/wp-content/uploads/2013/10/HOSDB__2007_-_part_3.pdf |
| KR2 | 33 J (E1) | (E2 ~1.5x E1 per scheme; not verified here) | https://eprints.whiterose.ac.uk/id/eprint/92387/1/15.11.30%20-%20HOSDB%20vs%20Utility_FinalAuthorVersion.pdf |
| KR3 | 43 J (E1) | — | same; also https://arxiv.org/pdf/0811.3955 |

Test method: instrumented drop of a weighted knife/spike carrier onto armour
over a backing simulant; 7 mm at E1 is the allowed depth (assumed safe for
organs); spikes must not penetrate at all. 43 J chosen as representative of
what an adult male can deliver with a knife (arXiv 0811.3955).

**Game takeaway:** a sharp blade's *skin* cost is tiny (~0.2-0.6 J, tens of N);
clothing adds tens of N; going *through* a rib costs ~10-16 J; human stabs
deliver ~60-95 J, so energy is rarely the limit — blade geometry/sharpness
and armour are.

---

## 2. Projectile skin perforation

| Projectile | Threshold | Units | Method | Source |
|---|---|---|---|---|
| .177 air-gun pellet, 8.25 gr (0.53 g) | 101 (331 ft/s) | m/s | Perforation of human lower-extremity skin (DiMaio & Copeland 1982, JFS 27(4)) | https://pubmed.ncbi.nlm.nih.gov/7175470/ |
| .22 pellet, 16.5 gr (1.07 g) | 75 (245 ft/s) | m/s | Same | https://pubmed.ncbi.nlm.nih.gov/7175470/ |
| .38 RN lead bullet, 113 gr (7.3 g) | 58 (191 ft/s) | m/s | Same | https://pubmed.ncbi.nlm.nih.gov/7175470/ |
| .177 pellet | always perforated at >= 365 ft/s (111 m/s) | m/s | Secondary summary of DiMaio | https://webpath.med.utah.edu/TUTORIAL/GUNS/GUNOTHR.html |
| Less-lethal impact munitions, 50% skin-penetration risk | thigh 12.62; anterior torso between ribs 22.3; lower back 28.6; scapula 33.3; posterior torso on ribs 34.3 | J/cm^2 | PMHS impacts, logistic risk curves (SAE Int. J. Transp. Safety) | https://saemobilus.sae.org/articles/evaluation-skin-penetration-less-lethal-impact-munitions-and-associated-risk-predictors-09-11-02-0011 |
| Rubber rounds, lowest mean energy density of penetrating impacts (between ribs) | 33.14 | J/cm^2 | 2005 PMHS study (NIJ) | https://www.ojp.gov/ncjrs/virtual-library/abstracts/skin-penetration-assessment-less-lethal-kinetic-energy-munitions |
| Analytic sphere (lead), age 50-80 skin | threshold ~4.6-5.2 (model-dependent; small-mass assumptions) | m/s | Strain-energy model from skin stress-strain curve (Def. Sci. J.) | https://publications.drdo.gov.in/ojs/index.php/dsj/article/download/4082/2355 |

Derived (own arithmetic, from DiMaio masses/velocities and calibre area):
.177 pellet KE ~2.7 J over 0.159 cm^2 -> ~17 J/cm^2; .22 pellet ~3.0 J over
0.245 cm^2 -> ~12 J/cm^2; .38 bullet ~12.3 J over 0.73 cm^2 -> ~17 J/cm^2.
So **~10-35 J/cm^2** is a consistent skin-perforation energy-density band
across pellets, bullets and blunt less-lethal rounds (lower for small light
projectiles' velocity framing, higher over bone/thick skin).

---

## 3. Blunt soft-tissue injury: bruising and laceration

| Injury | Quantity | Value | Units | Method | Source |
|---|---|---|---|---|---|
| Bruise (50% threshold), human limb | Transmitted impulse | 5.9 | N·s | Desmoulin & Anderson 2007, instrumented impacts on one volunteer — feasibility study, later called inconclusive | https://ibrc.osu.edu/wp-content/uploads/2014/01/Desmoulin_Abstract_2007.pdf |
| Bruise (50% threshold), human limb | Impact energy (F·d) | 3.2 | J | Same | https://ibrc.osu.edu/wp-content/uploads/2014/01/Desmoulin_Abstract_2007.pdf |
| Porcine minor contusion (healed by day 12) | Impact energy | 50 | J | Controlled blunt impacts on pigs | https://pmc.ncbi.nlm.nih.gov/articles/PMC11389484 |
| Scalp laceration (porcine head, frontoparietal) | Minimum force | ~4000 | N | Drop tower, Sharkey et al. 2012 Int J Legal Med 126(6) | https://discovery.dundee.ac.uk/en/publications/investigation-of-the-force-associated-with-the-formation-of-lacer/ |

Gap: no human-PMHS scalp-laceration energy threshold found. Behrens et al.
is credited as the first reliable human bruising experiment, but its numbers
weren't retrievable (see https://pmc.ncbi.nlm.nih.gov/articles/PMC9671306).

---

## 4. Material properties: tensile strength & fracture toughness

| Tissue | Quantity | Value / range | Units | Method | Source |
|---|---|---|---|---|---|
| Human skin (back) | UTS | 21.6 ± 8.4 | MPa | Uniaxial tension, 0.012 s^-1, n=56 (Ní Annaidh 2012) | https://arxiv.org/pdf/1302.3022 |
| Human skin (back) | Failure strain | 54 ± 17 | % | Same | https://arxiv.org/pdf/1302.3022 |
| Human skin, dynamic | UTS | 27.2 ± 9.3 | MPa | Tension at 1-2 m/s, donors 77-85 y (IRCOBI 2012) | https://researchrepository.ucd.ie/handle/10197/4772 |
| Human skin, dynamic | Failure strain / strain-energy density | 25.5 ± 5.1 % / 4.9 ± 1.5 | %, MJ/m^3 | Same | https://researchrepository.ucd.ie/handle/10197/4772 |
| Skin | Fracture toughness J_IIIc / J_Ic | ~20.4 / ~30.4 | kJ/m^2 | Tearing tests (2020 study, cited) | https://arxiv.org/pdf/2309.09161 |
| Pig skin | J_c | 17 ± 4 | kJ/m^2 | Trouser tear (Comley & Fleck 2010) | https://arxiv.org/pdf/2309.09161 |
| Skin (older compilation) | J_c | 1-20 | kJ/m^2 | Ashby-era review range | https://arxiv.org/pdf/2309.09161 |
| Skin, scissors cutting | Cutting energy | ~2 | kJ/m^2 | Cutting test (cited) | https://arxiv.org/pdf/2108.03014 |
| Porcine skeletal muscle | Fracture toughness | 0.84 ± 0.80 (exp.); 0.71 ± 0.76 (model) | kJ/m^2 | Fracture test + QLV model (J Mech Behav Biomed Mater 2022) | https://kris.kl.ac.at/en/publications/fracture-toughness-determination-of-porcine-muscle-tissue-based-o/ |
| Soft tissues generally | Note | Specimens often fail at UTS before a crack grows: highly flaw-tolerant; "toughness" often not truly measured | — | Review (Taylor et al. 2012) | https://www.tara.tcd.ie/items/f93b58f1-1bbb-42a0-b787-51952ea30742 |
| Skeletal muscle (goat) along fibres | UTS | 0.44 (45°: 0.234) | MPa | Uniaxial tension, n=5 | https://bmcmusculoskeletdisord.biomedcentral.com/track/pdf/10.1186/s12891-016-0998-7 |
| Skeletal muscle, stress at max stretch | 0.43 (cross-fibre) to 1.97 (fibre) | MPa | Tension, multiple orientations | https://pubmed.ncbi.nlm.nih.gov/25831858/ |
| Porcine muscle failure stretch | λ ≈ 1.65 (fibre) / 1.15 (cross-fibre) | — | Takaza et al. | https://www.tara.tcd.ie/bitstreams/747d4213-80ce-4774-8cea-7d8c257d254c/download |
| Human abdominal fat | UTS (biaxial) | 10-13 | kPa | Biaxial to failure (Sommer et al.), max stretch 1.21 | https://pmc.ncbi.nlm.nih.gov/articles/PMC9005403 |
| Fat | Fracture toughness | not found | — | — | — |
| Articular cartilage (bovine / canine patella) | Fracture toughness | 1.03 / 1.07 | kJ/m^2 | Modified single-edge notch | https://experts.umn.edu/en/publications/effect-of-specimen-thickness-on-fracture-toughness-of-bovine-pate/ |
| Articular cartilage (canine) | J-int toughness; trouser tear | 0.14-1.2; 0.24-0.8 | kJ/m^2 | Review table | https://pmc.ncbi.nlm.nih.gov/articles/PMC3752504/table/T1 |
| Human knee cartilage, superficial zone | Tensile strength (age 24-40 / 41-60 / 61-80) | ~35 / ~20 / ~15 (table labels ambiguous) | MPa | Kempson 1982 (secondary table) | https://simtk.org/websvn/wsvn/openknee/doc/tissue_mechanical_testing/technical-report-cartilage.pdf |
| Human cortical bone, transverse | J at 500 µm crack growth | ~31 (K ≈ 25 MPa√m); initiation 0.05-0.2 | kJ/m^2 | Short-crack R-curve, in situ (Koester et al. 2008) | https://escholarship.org/content/qt7fp4c420/qt7fp4c420.pdf |
| Bovine cortical bone | J_c | 3.2 (SENB) / 4.7 (CT); K_C 5.6-5.8 MPa√m | kJ/m^2 | EPFM (Libonati & Vergani 2014) | https://re.public.polimi.it/retrieve/handle/11311/964676/51487/Libonati%2c%20F.%2c%20Vergani%2c%20L.%2c%20Bone%20toughness%20and%20crack%20propagation....%2c%20Procedia%20Engineering%2074%2c%202014.pdf |
| Bovine cortical bone | Unnotched bending strength | ~217 | MPa | Same | same |
| Human rib cortical bone | Ultimate tensile stress / modulus | 124.2 / 13.9 GPa | MPa | Dynamic tension coupons (Kemper 2005) | https://saemobilus.sae.org/papers/material-properties-human-rib-cortical-bone-dynamic-tension-coupon-testing-2005-22-0010 |
| Human cortical bone | Long. tensile / compressive strength | 60-70 (DoITPoMS figure is low vs. most literature ~120-150) / 70-280 | MPa | Teaching compilation | https://www.doitpoms.ac.uk/tlplib/bones/bone_mechanical.php |
| Cortical bone (Reilly & Burstein-era) | Ultimate stress range for one condition | 219-283 (strain 1.6-3.3%) | MPa | Cited in Loughborough paper | https://repository.lboro.ac.uk/articles/Variability_and_anisotropy_of_mechanical_behavior_of_cortical_bone_in_tension_and_compression/9569954/files/17203202.pdf |

Toughness ordering (useful for a per-tissue "cut cost per area"):
skin (~2 kJ/m^2 cutting, 15-30 kJ/m^2 tearing) >> cortical bone crack growth
(0.05-0.2 initiation -> ~30 kJ/m^2 grown, transverse) > cartilage (~1 kJ/m^2)
≈ muscle (~0.8 kJ/m^2) > fat (not measured; UTS only ~10 kPa, i.e. ~1000x
weaker than skin). Cutting energy ≈ toughness × cut area: e.g. 2 kJ/m^2 × a
2 cm × 2 mm cut through skin face = 2000 × 4e-5 m^2 = 0.08 J — consistent
with the 0.17-0.56 J knife-entry measurements once friction/indentation are
added.

---

## 5. Whole-bone fracture

### 5a. Skull & face

| Bone / site | Quantity | Value / range | Units | Loading / impactor | Source |
|---|---|---|---|---|---|
| Skull, 5 sites (vertex, parietal, temporal, frontal, occipital), n=12 PMHS heads | Failure force QS / dynamic | 6.4 ± 1.1 / 11.9 ± 0.9 (overall range 4.5-14.1) | kN | Electrohydraulic; QS 2.5 mm/s; dynamic 7.1-8.0 m/s (Yoganandan 1995 J Neurotrauma 12:659) | https://pesquisa.bvsalud.org/bvsecuador/resource/es/mdl-8683617 |
| Same | Energy to failure QS / dynamic | 33.5 ± 8.5 / 28.0 ± 5.1 (range 14.1-68.5) | J | Same | https://pesquisa.bvsalud.org/bvsecuador/resource/es/mdl-8683617 |
| Same | Deflection / stiffness QS vs dyn | 12.0 mm, 812 N/mm vs 5.8 mm, 4023 N/mm | mm, N/mm | Same | same |
| Temporoparietal, 5 cm^2 circular plate | Mean fracture force; stiffness | ~5000; 1800 N/mm | N | Flat rigid impactor, 31 PMHS heads (Allsop et al. 1991, SAE 912907) | https://saemobilus.sae.org/content/912907 |
| Temporoparietal, 52 cm^2 rectangular plate | Mean fracture force; stiffness | ~12,500; 4200 N/mm | N | Same | https://saemobilus.sae.org/content/912907 |
| Frontal vs temporoparietal | Difference | Frontal ~3 kN stronger; lateral more fracture-prone at <4.1 m/s | kN | Meta-regression of multiple studies | https://journals.viamedica.pl/folia_morphologica/article/download/16148/12786 |
| Skull (all studies) | Force at 50% fracture risk | 1885-12,500 | N | Review: peak force alone insufficient criterion | https://journals.viamedica.pl/folia_morphologica/article/download/16148/12786 |
| Frontal bone | Tolerance relative | 3-4x mandible/zygoma | — | Cadaver comparison (secondary) | https://springerlink.bibliotecabuap.elogim.com/content/pdf/10.1007/s12663-011-0289-7.pdf |
| Frontal / maxilla / zygomatic arch / zygoma body / nasal | Tolerance groupings (Nahum/Hodgson compilation; source writes "Nm" but these are commonly force units) | 800-1600 / 150-300 / 200-400 / 200-650 / 25-75 | (see note) | PMHS impacts, various impactors (secondary slide summary) | https://www.slideshare.net/slideshow/facial-bone-fractures-an-overview/118873606 |
| Nasal bone | Minimal fracture | 25-75 lbf ≈ 110-335 N | N | Hodgson-era cadaver impacts (secondary) | https://www.scinapse.io/papers/1975230890 |
| Nasal bone | 50% fracture risk force | ~450-850 | N | Free-falling flat impactor, male PMHS; age significant | https://swov.nl/nl/publicatie/facial-impact-tolerance-and-response |
| Nasal region | 50% fracture risk energy | 53 (at ~2.53 m/s) | J | Reanalysis of Welbourne PMHS data | https://pmc.ncbi.nlm.nih.gov/articles/PMC3217371 |
| Nasal | Severe-pattern threshold | ~3 | kN | 11 unembalmed PMHS (SAE 861896) | https://saemobilus.sae.org/content/861896 |
| Nasal septum | Mean fracture force | ~100 | N | Cadaver septum | https://www.ovid.com/journals/othns/pdf/00006372-201012000-00009~fracture-patterns-of-the-nasal-septum |
| Zygoma | Fracture force for pulses >4 ms | ~200 lbf ≈ 890 | N | Over 1 in^2 (6.45 cm^2) area; shorter pulses tolerate more (secondary); load over whole bone raises tolerance 150-250% | https://www.scinapse.io/papers/1975230890 |
| Zygoma body | Range | 200-450 lbf ≈ 890-2000 | N | Review | https://www.scinapse.io/papers/1975230890 |
| Zygoma with soft tissue | Energy absorbed before fracture | +40-80% vs bare bone | — | Preliminary result | https://www.scinapse.io/papers/1975230890 |
| Mandible | Lowest tolerance (single condyle fracture) | 425 lbf ≈ 1900 | N | Cadaver impacts (secondary) | https://www.scinapse.io/papers/1975230890 |
| Mandible (various sites) | Peak fracture force | 1558-9670, mean 3733 ± 2056 | N | Blunt impacts on cadaver mandibles; midline hits -> symphyseal + condylar fractures (AAFS 2019 A139) | https://www.aafs.org/sites/default/files/media/documents/AAFS-2019-A139.pdf |
| Skull base via mandible/TMJ | Mean fracture load | 4300 ± 350 | N | n=4 PMHS (J Neurotrauma 1995) | https://pubmed.ncbi.nlm.nih.gov/8683618/ |
| Skull/face (Nahum 1968) | Note | Frontal, temporoparietal, zygomatic tolerances ~independent of pulse duration; female lower | — | SAE 680785 | https://saemobilus.sae.org/content/680785 |
| Skull fracture, 50% risk (cited in model paper) | Energy | 0.45-0.83 | J?? (reported as mJ-to-J; likely specific-energy measure — treat as unreliable) | Cited in KU Leuven model | https://lirias.kuleuven.be/retrieve/557872 |
| Spherical skull surrogate | Energy threshold fixed / free | 11.0 / 13.6 | J | Simplified bone+brain sphere model (Siegenthaler 2019) | https://boris.unibe.ch/135210/1/Siegenthaler_2019_IntJLegalMed_Online.pdf |

### 5b. Thorax, shoulder, limbs, hand

| Bone | Quantity | Value / range | Units | Loading | Source |
|---|---|---|---|---|---|
| Rib (adult) | Peak force, whole rib (Cormier et al., cited) | ~164 | N | Whole-rib bending | https://isml.ecm.uwa.edu.au/ISML/Publication/pdfs/2016wangwittekCMBBEnumerical.pdf |
| Rib | Kemper 2007: 48 dynamic 3PB + 46 tension tests, 172 mm/s; modulus 18.9-21.0 GPa | — | — | SAE 2007-22-0011 | https://saemobilus.sae.org/content/2007-22-0011 |
| Rib | Population trend | Force & displacement at fracture higher in young adults; 5th-pct female < 50th/95th male | — | 261 ribs/171 PMHS, dynamic A-P bending (Agnew et al.) | https://www-nrd.nhtsa.dot.gov/pdf/bio/proceedings/2016/Agnew%20et%20al-%20NHTSA%20wkshp%202016%20final.pdf |
| Rib (porcine) perforation by knife | Energy | 11-16 | J | see §1 | https://www.springermedicine.com/stabbing-energy-and-force-required-for-pocket-knives-to-pierce-r/22003220 |
| Clavicle (synthetic Sawbones intact) | 3PB failure | ~440 | N | Compared with plated cadaver 476 N | https://medicina.lsmuni.lt/wp-content/uploads/pdf/1502-07e.pdf |
| Clavicle (cadaveric, mode unclear) | Failure load | 3350 ± 1999 | N | 3D-print comparison; mode unverified | https://core.ac.uk/download/212669447.pdf |
| Femur mid-shaft | Peak bending moment L-M / P-A | ~352 / ~348 | N·m | Dynamic 3PB drop, 9.8 kg at 5 m/s (122 J input), n=45 (Kennedy 2004, VT) | https://vtechworks.lib.vt.edu/bitstream/10919/32216/1/EA_Kennedy_Thesis.pdf |
| Femur | 50% fracture risk moment, distal third / mid-shaft | ~372 / ~447 | N·m | Dynamic latero-medial bending, risk functions (Kerrigan et al.) | https://data.zhenzhi.com/details/1/911413090 |
| Femur | Kerrigan 2003 | 412 | N·m | Dynamic 3PB L-M, n=8 (summary table) | https://pmc.ncbi.nlm.nih.gov/articles/PMC3217417 |
| Femur (axial, via knee) | Mean fracture force; impact energy | 10.04 kN; 549 J | kN, J | Longitudinal knee impacts, seated PMHS (SAE 751160) | https://saemobilus.sae.org/content/751160 |
| Embalmed vs fresh bone | Embalmed ~44% weaker | — | — | Note in Funk et al. | https://pmc.ncbi.nlm.nih.gov/articles/PMC3217417 |
| Tibia mid-shaft | Fracture bending moment F / M | ~280 / ~320 | N·m | Static & dynamic 3PB, unembalmed (Nyquist 1985, SAE 851728) | https://saemobilus.sae.org/content/851728 |
| Tibia | Failure force range | 1.19-7.07 | kN | Assorted PMHS leg impacts (ESV) | https://www-nrd.nhtsa.dot.gov/pdf/esv/esv17/Proceed/00025.pdf |
| Tibia (cadaveric) | Mean fracture force; 10% risk | 4889; 3386 | N | 3PB, vs synthetic (Cameron 2020) | https://ir.lib.uwo.ca/boneandjointpub/1073 |
| Leg | Dynamic vs QS strength | +69% dynamic | — | Schreiber, UVA thesis | https://libraetd.lib.virginia.edu/public_view/tb09j6941 |
| Tibiofemoral (knee) | Fracture load single / repeated | 5.8 ± 1.5 (33% freq) / 8.0 ± 1.8 | kN | Flexed knee impacts | https://deepblue.lib.umich.edu/bitstream/2027.42/33139/1/0000525.pdf |
| Forearm (distal radius), 48 PMHS >= 65 y | Mean impact force | 2.26 | kN | Frykman 1967 (secondary) | https://arxiv.org/pdf/1807.03143 |
| Distal radius, forward-fall sim | Peak fracture force | 2.5 ± 1.3 | kN | Dynamic, n=8; off-axis 29% lower than axial | https://rcastoragev2.blob.core.windows.net/2a72908a8005821ee311e9ae418e44c2/PMC6451781.pdf |
| Radial head | Axial failure | 2.56 (1.30-7.32) | kN | Axial compression | https://www.springermedizin.de/proximal-radius-fracture-morphology-following-axial-force-impact/16625788 |
| Metacarpal (porcine, intact control) | 3PB max load; stiffness | 482.8 ± 104.8; 122 N/mm | N | 3PB (Sci World J 2011) | https://doaj.org/article/2656240821f14f24a239a3ff9013d041 |
| Metacarpal neck, human, fixed | IMN vs K-wire LTF | 546 vs 154 | N | 3PB, fixation constructs (not intact) | https://pmc.ncbi.nlm.nih.gov/articles/PMC9806540 |
| 5th metacarpal ("boxer's") intact human | — | **Not found** (88-bone native-strength study exists, abstract gives only ratios) | — | 3PB | https://orthobullets.com/evidence/35803782 |

---

## 6. Modelling notes for the energy-budget system

1. **Rate dependence is large.** Skull: dynamic force ~1.9x QS force but
   similar energy (28 vs 33.5 J), stiffness ~5x. Leg: +69% dynamic. Use
   impact-rate values for combat.
2. **Impactor area dominates force thresholds.** Temporoparietal: 5 kN at
   5 cm^2 vs 12.5 kN at 52 cm^2 (pressure ~10 MPa vs ~2.4 MPa). Model blunt
   fracture by force/pressure on a contact area, penetration by energy per
   area (J/cm^2), bruising by impulse/energy.
3. **Suggested baseline per-hit energies (50%-ish thresholds):**
   bruise ~3 J; knife through skin <1 J (+clothing tens of N);
   knife through rib 11-16 J; nasal fracture ~53 J (force 0.45-0.85 kN);
   skull fracture ~14-68 J (mean ~30 J), 5-12 kN depending on area;
   skin perforation by projectile ~10-35 J/cm^2; femur axial fracture
   ~550 J / 10 kN; femur bending ~350-450 N·m; tibia ~280-320 N·m,
   ~3.4-4.9 kN; distal radius ~2.3-2.5 kN; mandible ~1.9-3.7 kN.
4. **Variance:** use per-entity multipliers ~0.5-1.5x (cadaver CVs 20-60%),
   reduce with age (rib, skull, cartilage all decline), female ~lower
   (Nahum 1968).
5. **Soft tissue padding** raises bone tolerance (zygoma +40-80% energy).

## 7. Gaps (not found or unverified this session)

- Intact human clavicle, metacarpal (boxer's fracture) and whole-rib
  absolute force/energy means (Kemper 2007, Agnew 2018 tables not retrieved).
- Human scalp laceration threshold (only porcine 4 kN).
- Fat fracture toughness; consistent human muscle UTS.
- Knight 1975 numeric skin force (often quoted ~49 N) unconfirmed.
- Exact HOSDB KR2/KR3 E2 values; DoITPoMS cortical tensile (60-70 MPa) is
  lower than most literature (Kemper rib coupons 124 MPa).
- Full-text verification was impossible (network sandbox blocked fetches);
  re-verify before treating any value as authoritative.
