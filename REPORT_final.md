# V4 final report (v4_run_ctx.py + v4_rules.yaml)

Written for the V4 project. All runs were made in one local working folder. `v4_run.py`, `out_txsd`, `out_ctx_txsd`, the V2 / V3 results and the V3 repo were only read. Nothing was deleted or committed.

## Read this first: problems found in the final TXSD output

The step checks all passed, but the final TXSD output still has these problems. The pilot resolution check does not catch them.

1. **First-name-only judge IDs, caused by the step 6 docket patterns.**
   - A docket name with a middle initial but no dot ("Judge Ronald G Morgan") is cut after the first word. The surname-only logic then treats "ronald" as a surname.
   - Result: judge IDs such as "ronald" (3,844 mentions), "andrew" (3,847), "peter" (5,560), "ricardo" (3,558), "lynn" (2,016), "frances" (2,629), "juan" (2,714), "hilda" (1,151).
   - Two-word names were also split from the full name: "nelva gonzales" (3,488) vs "nelva gonzales ramos" (6,282); "dena hanovice" vs "dena hanovice palermo".
   - Trailing words were captured: "Ronald G. Morgan Depositions", "Rolando Olvera Deft".
   - On the pilot, judge **extraction** F1 fell from 0.835 to 0.812. Judge **resolution** stayed 1.000.
   - **Suggested fix (not applied):** allow an undotted single-letter middle initial in the docket name pattern; never treat a captured single word as a surname when it is a common first name; strip a trailing word that is not a name (vocabulary).
2. **Interpreters listed as counsel:** "Brownsville Interpreter" (2,826 counsel IDs), "Houston Interpreter" (1,082), "X Case Manager …". They have no contact info and no middle initial, so the step 5 rules keep them apart.
3. **Non-firms in the firm list:** "Attorney at Law" (796 firm IDs, 8,667 mentions) and "State Bar Information" (83).
4. **Non-parties in the party list:** "Incorrectly Filed" (516 party IDs). "John Doe" (348) is one per case, by design.
5. **Officials are still split:** Lorie Davis has 197 party IDs. Step 3 was skipped because titles are mostly missing (below).

## Steps and checks

| Step | Tests | Pilot resolution F1 (judge / party / firm) | TXSD entities: judge / party / counsel / firm / total | TXSD time, peak memory |
|---|---|---|---|---|
| baseline (out_ctx_txsd, V4ctx4) | 13/13 | 1.000 / 0.973 / 0.893 | 769 / 113,844 / 33,240 / 9,122 / 156,975 | 130.5 s, 2.76 GB |
| 1 audit -> v4_rules.yaml | 14/14 | 1.000 / 0.973 / 0.893 (pilot output byte-identical) | 769 / 113,844 / 33,240 / 9,122 / 156,975 (all 4 files byte-identical) | 116.8 s, 2.89 GB |
| 2 judges (typo, title evidence, surname-only levels + unresolved, non-name drop) | 20/20 | 1.000 / 0.973 / 0.893 (judge extraction 0.831 -> 0.835) | **517** (+13 unresolved records, 110 mentions) / 113,844 / 33,240 / 9,122 / 156,736; 671 non-name judge entries dropped | 119.5 s, 2.89 GB |
| 3 officials | - | skipped: titles mostly missing (21.9% of mentions of the top-30 person parties; field parties[].entity_info.raw_info; step3_titles.json) | no code change, no rerun | - |
| 4 agencies (revised acronym rule) | 27/27 | **FAIL: party 0.973 -> 0.959** (P 0.998 -> 0.980, R 0.949 -> 0.938); judge 1.000, firm 0.893 unchanged | not run (stopped) | - |
| 4 trial fix (try_step4_fix/, not applied) | not run | party 0.97323 -> 0.96824 (drop 0.00499); judge 1.000, firm 0.893 | not run | - |
| 4 agencies (with fixes a, b, c; option 2) | 28/28 | 1.000 / **0.96950** (drop 0.00373) / 0.893 | 517 (+13 unresolved) / **113,411** / 33,240 / 9,122 / 156,303. TDCJ IDs 252 -> 220 (187 of the 220 are officials with the title in the name, person rule; the department itself: 1 main ID, 158 mentions); UTMB 68 -> 61 | 126.7 s, 2.93 GB |
| 5 lawyers (pro se = existing flag; no-contact counsel rules) | 32/32 | 1.000 / 0.96950 / 0.893 (no change: counsel not in the key) | 517 (+13) / 113,411 / **23,229** / 9,122 / 146,292; uncertain pairs 57,485 -> 27,490 | 103.4 s, 2.96 GB |
| 6 docket judges (3 general phrase patterns + keep rule: case fields / FJC / 3+ cases) | 36/36 | 1.000 / 0.96950 / 0.893 (judge **extraction** F1 0.835 -> 0.812: 451 docket-only judge mentions dropped by the keep rule on the pilot) | **402** (+10 unresolved) / 113,411 / 23,229 / 9,122 / 146,174; judge mentions now include the new docket phrases (712,188 -> 799,428 mentions); 17,841 non-name entries and 572 docket-only judges dropped | 138.0 s, 3.09 GB |


- **Step 3 (officials):** titles such as Director / Commissioner sit in `parties[].entity_info.raw_info` (HTML, e.g. `<i>Director of TDCJ</i>`). They are present in only **21.9%** of mentions of the 30 most repeated person-party names (941 of 4,301; Lorie Davis 23.9%). Mostly missing, so the step was **skipped** as instructed (`step3_titles.json`). Titles are more often inside the name itself ("Director of TDCJ CID Lorie Davis").
- **Step 4 revisions (option 2):** (a) a suffix made only of legal-form words is never a division; (b) single letters are joined only when they spell a legal form; (c) a single all-caps suffix ("-CID") is a division only if it is the acronym of an organisation or division name in the same court. An all-caps token counts as an organisation acronym only if it equals org initials in the same court, or carries such a division suffix. Lone "SMITH" / "USA" stay persons.

## 1. Time, memory, entity counts (full TXSD, 50,766 files)

| | Wall time | Peak memory | Judges | Unresolved judge records | Parties | Counsel | Firms | Total IDs |
|---|---|---|---|---|---|---|---|---|
| V4inc (`v4_run.py`, out_txsd) | 4,340 s | 1.83 GB | 672 | 0 | 104,312 | 18,787 | 7,365 | 131,136 |
| V4ctx (out_ctx_txsd) | 131 s | 2.76 GB | 769 | 0 | 113,844 | 33,240 | 9,122 | 156,975 |
| **final** (out_final_txsd) | 140 s | 3.09 GB | 402 | 10 | 113,411 | 23,229 | 9,122 | 146,164 |

- V4inc ran on the same Mac, alongside other work.
- The final run's output is byte-identical to the step 6 TXSD output.
- Final mentions: 799,428. The new docket patterns add judge mentions, so this is higher than V4ctx's 712,843.

## 2. Incremental vs all at once vs reversed order (TXSD)

Share of mentions whose whole group equals the all-at-once run (mention = case + type + raw name):

| | Counsel | Firms | Judges | Parties | All |
|---|---|---|---|---|---|
| first 40,000 then the rest | 208028/208028 (100.00%) | 159042/159042 (100.00%) | 264282/264295 (100.00%) | 168026/168063 (99.98%) | **799378/799428 (99.99%)** |
| reversed order | 205952/208028 (99.00%) | 147111/159042 (92.50%) | 255870/264295 (96.81%) | 164103/168063 (97.64%) | **773036/799428 (96.70%)** |

**Old IDs after adding the rest:**
- old mentions with the same entity ID: **640348/640348**;
- old entity IDs still present, same type and ID: **129079/129079**.

**Rerunning the same 10,766 files on the incremental output:** all output files byte-identical.

**Why the groups differ:**
- **4 mentions exist only in the all-at-once run.** A docket-only judge is kept when its name appears in 3+ cases (step 6). In the incremental run, a few names reached 3 cases only once the second batch arrived, and dropped mentions from the first batch are not added back.
- **Reversed order agrees 96.70%** (firms 92.50%). Linking is "first match wins": a firm or person-party mention links to the first saved entity it shares evidence with, so the order decides which mention starts an entity and what evidence it holds. Typo merges and surname-only levels also depend on what is saved first. Saved entities are never merged afterwards, so these differences stay.

## 3. Judges vs the FJC list (TXSD)

- **FJC judges who ever served in the Southern District of Texas: 59.** Many retired or died before these 2016-2020 cases.
- **Found in V4: 32** — with exactly 1 ID: **29**; with 2+ IDs: **3**: Nelva Gonzales Ramos (ent_SJ_000024, ent_SJ_000100); Janis Graham Jack (ent_SJ_000094, ent_SJ_000396); John David Rainey (ent_SJ_000097, ent_SJ_000113).
- **Judge IDs: 402** (plus 10 unresolved records, not counted). **Not on the FJC list: 187:**
  - **magistrate / bankruptcy (title seen): 53** — e.g. Ronald G. Morgan (5249); Ignacio Torteya (7900); Ronald (3844); Andrew (3847); Magistrate Judge Ronald G. (3); Peter E Ormsby (7110); Peter (5560); Frances H Stacy (3073)
  - **surname only (no FJC match possible, no title): 37** — e.g. Hilda (1151); Judge Rolando (11); Ricardo (3558); Judge Test (4); David (873); State Judge (3); Clinton (3); Alfred (1810)
  - **other (not FJC, no magistrate/bankruptcy title seen): 97** — e.g. Lynn (2016); Ronald G. Morgan Depositions (3); Nelva Gonzales (3488); Rolando Olvera Deft (84); Ronald G. Morgan Bond (4); Judge Diana Saldana (6688); Marina Garcia (3378); Fred Biery (8)
- **Note:** the "magistrate / bankruptcy" and "surname only" groups include the first-name-only IDs from problem 1 ("Ronald", "Andrew", "Peter", "Hilda", "Ricardo"). They are real magistrate or district judges cut to one word, not junk text. With the keyword check, no junk IDs remain (the step 2 vocabulary removed them).

## 4. Remaining splits: names with the most IDs (final TXSD)

**judge** (name: IDs / mentions): andrew s hanen 1/5127; ronald g morgan 1/5249; rolando olvera 1/5720; ignacio torteya 1/7900; hilda g tagle 1/2212; hilda 1/1151; fernando rodriguez jr 1/4866; ronald 1/3844; andrew 1/3847; rolando 1/11; ronald g 1/3; ricardo h hinojosa 1/7371; peter e ormsby 1/7110; peter 1/5560; ricardo 1/3558; lynn n hughes 1/4513; frances h stacy 1/3073; frances 1/2629; melinda harmon 1/1415; lynn 1/2016; micaela alvarez 1/7672; ronald g morgan depositions 1/3; nelva gonzales 1/3488; nelva gonzales ramos 1/6282; randy crane 1/7438; dorina ramos 1/2847; juan f alanis 1/3072; juan 1/2714; dena hanovice 1/1521; dena hanovice palermo 1/1793

**party** (name: IDs / mentions): incorrectly filed 516/524; john doe 348/349; lorie davis 128/1263; ed gonzalez 73/98; jane doe 51/51; bryan collier 48/99; william stephens 38/137; kirstjen nielsen 34/73; kim ogg 32/47; brian collier 31/37; brad livingston 30/53; robert lacy 27/45; jeff sessions 24/74; ken paxton 23/29; dir of tdcj parole bryan collier 22/30; marne boyle 22/25; bobby lumpkin 21/129; greg abbott 21/25; robert lacy jr 19/33; jeh johnson 18/34; david gutierrez 18/26; director tdcj cid 18/25; doe 1 18/18; doe 6 18/18; bret bradford 18/21; amicus curiae 17/27; director of tdcj cid lorie davis 17/91; doe 5 17/17; gregory wade brooks ii 17/23; mike pompeo 16/28

**counsel** (name: IDs / mentions): brownsville interpreter 2826/2941; houston interpreter 1082/1093; tigrinya interpreter 4/4; debra lynn bradberry 4/12; pooneh azandaryani momeni 3/8; michael lawrence orth 3/20; philip w danaher 3/54; christiana dijkman 3/10; ccusm 3/3; adam lloyd robertson 3/7; michael kevin burke 3/11; aisha japera dennis 3/59; marjorie mayers 3/3; jeffrey mangas smith 3/6; brenda hard wilson 3/18; blake earl bachtel 3/6; mary e baker 3/39; federal public 3/3; gayla corley 3/5; andrew paul barber 3/6; eliot burriss 3/4; cesar a amador 2/371; kyle blair welch 2/386; john m parras 2/165; james l turner 2/160; joshua bradley lake 2/239; x case manager miller 2/7; x case manager laredo 2/22; james daniel snyder 2/4; david clay wilkerson 2/6

**firm** (name: IDs / mentions): attorney at law 796/8667; state bar information 83/457; atty at law 7/169; morgan lewis bockius 5/104; jackson lewis p c 5/101; ogletree deakins 4/48; united states department of justice 4/22; omelveny myers 4/13; gordon rees scully mansukhani 4/80; harris county attorneys office 4/185; ogletree deakins nash smoak stewart 4/96; kirkland and ellis 4/56; fisherbroyles 3/12; mcguirewoods 3/93; holland knight 3/117; faegre drinker biddle reath 3/191; lewis brisbois bisgaard smith 3/303; u s department of justice 3/42; us department of justice 3/58; dinsmore shohl 3/11; baker hostetler 3/465; hunton williams 3/11; edwards law firm 3/18; greenberg traurig 3/135; state bar information 5th circuit information 3/3; thompson knight 3/40; orrick herrington sutcliffe 3/14; winston and strawn 3/23; katten muchin rosenman 3/10; attorney 3/3

**Named entities, V4ctx (before) vs final (after):**

| Name | Before: IDs / mentions | After: IDs / mentions |
|---|---|---|
| Lorie Davis | party: 197 / 1,582 | party: 197 / 1,582 |
| Nancy Berryhill | party: 18 / 176 | party: 18 / 176 |
| Jose Garcia (exact name) | party: 7 / 8 | party: 7 / 8 |
| Jose Garcia (any name with jose + garcia) | counsel: 3 / 12; party: 181 / 212 | counsel: 3 / 12; party: 181 / 212 |
| United States (party fold) | party: 1 / 28,493 | party: 1 / 28,493 |
| TDCJ | party: 252 / 627 | party: 220 / 627 |
| UTMB | party: 68 / 124 | party: 61 / 124 |
| U.S. Attorney's Office (firm) | firm: 1 / 55,650 | firm: 1 / 55,650 |
| Federal Public Defender (firm) | firm: 1 / 24,682 | firm: 1 / 24,682 |

- **TDCJ:** 187 of the 220 remaining IDs are officials with the title inside the name ("Director of TDCJ CID Lorie Davis"). These use the person rule. The department itself is one main ID (158 mentions) plus single-mention sub-units.

## 5. Wrong merges: person-party IDs with more than one surname

**Definition:** a party ID where every name is a person name (not an organisation, government or placeholder, by V4's rules applied to each name) and the names have more than one distinct surname (last word after removing Jr / Sr / II …). Compound surnames ("garcia-lopez" vs "garcia") count as different, so this can over-count slightly.

| System | Party IDs | IDs with 2+ surnames | Examples |
|---|---|---|---|
| final | 113,411 | **0** |  |
| V2 (v2_txsd_results) | 103,926 | **577** | Michael J Cammon / Michael J. Cameron; DAVID BAECKER / David Backer / David Baker / David Barber; Richard Solar / Richard Soler |
| V3 (v3_txsd_bulk2/ec2_txsd_bulk2, name_variants) | 95,266 | **5,440** | alejandro ismael romero-martinez / armando perez-sanchez / daniel ismael villalba-gonzalez / eduardo lara ortega; armando guerrero-martinez / armando jimenez / armando martinez / armando serna; alfonso leos-hernandez / alfonso salazar / samuel alfonso reeves |

- V4 person parties merge only on identical names, so 0 is expected by design.
- The TXSD comparison report used a different, hand-checked definition for V2 / V3 (1,022 / 2,922).

## 6. review_sample.csv

`review_sample.csv` has an empty "correct?" column and 300 rows (seed 42):
- 50 random multi-mention entities per type, with all name variants, cases and evidence;
- 50 random uncertain pairs;
- 50 random same-surname pairs (judge / counsel / person party, same court) with different IDs.

## 7. Pilot score table (200-file answer key; P / R / F1)

| Type | Score | V2 | V3 bulk | V4inc | V4ctx (first context version) | V4ctx4 (start of this job) | **final** |
|---|---|---|---|---|---|---|---|
| judge | extraction | 1.000 / 0.515 / **0.680** | 0.958 / 0.975 / **0.966** | 0.879 / 0.789 / **0.831** | 0.879 / 0.789 / **0.831** | 0.879 / 0.789 / **0.831** | 0.924 / 0.724 / **0.812** |
| judge | resolution | 1.000 / 1.000 / **1.000** | 1.000 / 0.999 / **0.999** | 1.000 / 0.950 / **0.974** | 1.000 / 0.977 / **0.988** | 1.000 / 1.000 / **1.000** | 1.000 / 1.000 / **1.000** |
| party | extraction | 0.997 / 0.997 / **0.997** | 0.998 / 0.998 / **0.998** | 0.998 / 0.998 / **0.998** | 0.998 / 0.998 / **0.998** | 0.998 / 0.998 / **0.998** | 0.998 / 0.998 / **0.998** |
| party | resolution | 0.970 / 0.941 / **0.955** | 0.992 / 0.926 / **0.958** | 0.974 / 0.820 / **0.890** | 0.992 / 0.164 / **0.282** | 0.998 / 0.949 / **0.973** | 0.988 / 0.952 / **0.970** |
| firm | extraction | 0.884 / 0.985 / **0.932** | 0.979 / 0.982 / **0.980** | 0.979 / 0.982 / **0.980** | 0.979 / 0.982 / **0.980** | 0.979 / 0.982 / **0.980** | 0.979 / 0.982 / **0.980** |
| firm | resolution | 0.600 / 0.575 / **0.587** | 0.847 / 0.737 / **0.788** | 0.814 / 0.760 / **0.786** | 1.000 / 0.806 / **0.893** | 1.000 / 0.806 / **0.893** | 1.000 / 0.806 / **0.893** |

**Key disagreements** (every merge in the final pilot output that the answer key calls wrong; check by hand):

| Type | V4 ID | Key entities merged | Names in the V4 ID |
|---|---|---|---|
| party | ent_SP_002114 | P-ORG-armstrong world ind, P-ORG-armstrong world industries, P-ORG-awi | ARMSTRONG WORLD IND., INC., ARMSTRONG WORLD INDUSTRIES, ARMSTRONG WORLD INDUSTRIES INC, ARMSTRONG WORLD INDUSTRIES, INC,, ARMSTRONG WORLD INDUSTRIES, INC., AWI |
| party | ent_SP_002455 | P-ORG-crown cork and seal company usa, P-ORG-crown cork and seal usa | CROWN CORK & SEAL (USA) INC., CROWN CORK & SEAL COMPANY (USA) INC. |
| party | ent_SP_002744 | P-ORG-circor international, P-ORG-circor intl | CIRCOR INT'L, INC., CIRCOR INTERNATIONAL, INC. |
| party | ent_SP_003254 | P-ORG-phoenix specialty manufacturing, P-ORG-phoenix specialty mfg | PHOENIX SPECIALTY MANUFACTURING CO., INC., PHOENIX SPECIALTY MFG. CO., INC. |
| party | ent_SP_003371 | P-paed-2-11-cv-37241.json-creighton e miller, P-paed-2-11-cv-52640.json-creighton e miller | CREIGHTON E MILLER, CREIGHTON E. MILLER |
| party | ent_SP_003612 | P-paed-2-11-cv-46150.json-willard e bartel, P-paed-2-11-cv-48843.json-willard e bartel | WILLARD E. BARTEL |
| party | ent_SP_003613 | P-paed-2-11-cv-46150.json-david c peebles, P-paed-2-11-cv-48843.json-david c peebles | DAVID C. PEEBLES |

**My reading of these merges:**
- **Probably correct, but the key does not apply V4's normalisation:** the first 4 (Armstrong World Ind. / AWI = Armstrong World Industries; Crown Cork & Seal (USA) with and without "Company"; CIRCOR Int'l = International; Phoenix Specialty Mfg. = Manufacturing).
- **From the earlier rare-name rule:** the last 3 (same full name in two asbestos cases). The key never joins people across files.

## 8. Uncertain pairs (final TXSD)

**27,609 lines.** By type: firm 3,009, counsel 13,101, party 11,120, judge 379.

By reason:
- counsel: compatible name, no shared email / phone / address / office: 13,101
- party: same name in another case, no shared counsel / firm / co-party, name not rare: 11,045
- firm: same name, no shared address / phone / email domain: 3,009
- judge: surname-only mention, 2 judges with this surname in the same division; sent to the unresolved record: 176
- judge: surname-only mention, 2 judges with this surname in the same case; sent to the unresolved record: 144
- party: acronym matches the initials of more than one organisation in this court: 75
- judge: surname-only mention, 3 judges with this surname in the same division; sent to the unresolved record: 57
- judge: surname-only mention, 2 judges with this surname in the same court; sent to the unresolved record: 2

## v4_rules.yaml (full contents, with sources)

```yaml
# v4_rules.yaml: every word list, pattern and threshold used by v4_run_ctx.py.
# Each entry has a `source:` note. Sources:
#   notebook   = the Colab notebook "V4 (1).ipynb" (cells 5-8), copied unchanged
#   user       = an explicit instruction from the user (date / step noted)
#   data       = chosen from what the pilot / TXSD outputs showed (file noted)
#   choice     = my default, with the reason
#   reference  = public reference data file (path noted)
# Regexes are Python `re` syntax and are written as literal blocks (no YAML escaping).

matching_label: "context-aware v8 (step 6: docket judges)"   # written to state.json; source: choice (version tag)

entity_types:
  source: notebook (EXTRACTION_CONFIG, cell 5); json_paths are documentation only, extraction code walks the same fields
  judge:   {json_paths: [judge, referred_judges, "parties[].judge", "parties[].referred_judges"], docket_scan: true, id_prefix: SJ, id_key: sjid}
  party:   {json_paths: ["parties[].name"], docket_scan: false, id_prefix: SP, id_key: spid}
  counsel: {json_paths: ["parties[].counsel[].name"], skip_pro_se: true, docket_scan: false, id_prefix: SC, id_key: scid}
  firm:    {json_paths: ["parties[].counsel[].entity_info.office_name"], skip_pro_se: true, docket_scan: false, id_prefix: SF, id_key: sfid}

# ---------------------------------------------------------------- extraction
docket_judge_patterns:
  source: 'notebook (DOCKET_JUDGE_PATTERNS, cell 5) for the first two; the last three are general phrases added in step 6 (user -
    "before ... Judge X", "referred to Magistrate Judge X", "signed/ordered by Judge X"). V3 configs/judges.yaml was read: it finds
    docket judges with spaCy NER and uses regexes only to reject non-judges (probation officers, court reporters, clerks), which the
    non_judge_docket_keywords and judges.non_name_words lists cover here.'
  patterns:
    - |-
      (?:held before|before Judge|before Magistrate Judge|before)\s+(?:Judge|Magistrate Judge|District Judge|Senior Judge|Honorable)?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s*(?:Jr\.|Sr\.|III|II))?)
    - |-
      (?:Signed by|ORDER.*Signed by)\s+(?:Judge|Magistrate Judge|District Judge|Senior Judge|Honorable)?\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s*(?:Jr\.|Sr\.|III|II))?)
    - |-
      \bbefore\s+(?:the\s+)?(?:Honorable\s+|Hon\.?\s+)?(?:Chief\s+|Senior\s+)?(?:United\s+States\s+|U\.\s?S\.\s?)?(?:District\s+|Magistrate\s+|Bankruptcy\s+)?Judge\s+((?:[A-Z][a-z'\-]+|[A-Z]\.)(?:\s+(?:[A-Z][a-z'\-]+|[A-Z]\.)){0,3})
    - |-
      \breferred\s+to\s+(?:the\s+)?(?:Honorable\s+|Hon\.?\s+)?(?:United\s+States\s+|U\.\s?S\.\s?)?Magistrate\s+Judge\s+((?:[A-Z][a-z'\-]+|[A-Z]\.)(?:\s+(?:[A-Z][a-z'\-]+|[A-Z]\.)){0,3})
    - |-
      \b(?:[Ss]igned|[Oo]rdered|[Ee]ntered)\s+by\s+(?:the\s+)?(?:Honorable\s+|Hon\.?\s+)?(?:Chief\s+|Senior\s+)?(?:United\s+States\s+|U\.\s?S\.\s?)?(?:District\s+|Magistrate\s+|Bankruptcy\s+)?Judge\s+((?:[A-Z][a-z'\-]+|[A-Z]\.)(?:\s+(?:[A-Z][a-z'\-]+|[A-Z]\.)){0,3})

non_judge_docket_keywords:
  source: notebook (NON_JUDGE_DOCKET_KEYWORDS, cell 5); substring test on the lower-cased docket candidate
  words: ["court staff", "courtroom", "clerk", "chambers staff", "reporter", "recorder", "usa", "fpd"]

# ---------------------------------------------------------------- normalization
title_words:
  source: notebook (TITLE_PATTERN, cell 7); removed from every name before punctuation is stripped
  words: [honorable, judge, magistrate, district, senior, presiding, chief, "court staff", "pro se"]

apostrophes:
  source: notebook (clean_text_base, cell 7)
  pattern: |-
    ['’]

corp_suffix_words:
  source: notebook (CORP_SUFFIX_PATTERN, cell 7); removed from firm and party names for comparison
  words: [inc, incorporated, corp, corporation, llc, llp, ltd, limited, co, company, the, pc, apc, pllc, pa]

judge_title_words:
  source: user (judge titles step); removed from judge names only, after punctuation became spaces
  words: [hon, "u s d j", "u s m j", usdj, usmj, "magistrate judge", "chief judge", "senior judge"]

doe_pattern:
  source: notebook (DOE_PATTERN, cell 7)
  pattern: |-
    ^(john\s+doe|jane\s+doe|does?(\s+\d+.*)?|unknown\s+parties?|unnamed.*)$

name_suffixes:
  source: choice (standard generational suffixes); ignored when taking the surname, and a conflict blocks a merge
  words: [jr, sr, ii, iii, iv, v]

# ---------------------------------------------------------------- contact evidence
contact:
  source: choice (US phone numbers are 10 digits; a leading 1 is the country code; street number + ZIP is the
    same address evidence the answer key uses)
  phone_min_digits: 7
  phone_country_code: "1"
  zip_pattern: |-
    \b(\d{5})(?:-\d{4})?\b
  street_number_pattern: |-
    \b(\d+)\b

webmail_domains:
  source: choice (common US webmail providers; a shared webmail domain is not firm evidence, same rule as the answer key)
  domains: [gmail.com, yahoo.com, aol.com, hotmail.com, outlook.com, msn.com, comcast.net, icloud.com, me.com, live.com,
            att.net, sbcglobal.net, verizon.net, bellsouth.net, earthlink.net, mail.com, protonmail.com, ymail.com,
            cox.net, charter.net]

# ---------------------------------------------------------------- people
nickname_groups:
  source: choice (typed list of common English given-name / nickname pairs; no public list was found locally)
  groups:
    - william bill billy will willie
    - robert bob bobby rob robbie
    - james jim jimmy jamie
    - michael mike mikey
    - richard dick rick ricky rich
    - thomas tom tommy
    - joseph joe joey
    - daniel dan danny
    - david dave davey
    - charles chuck charlie chas
    - edward ed eddie ted ned
    - kenneth ken kenny
    - lawrence larry
    - patrick pat
    - patricia pat patty trish
    - susan sue susie
    - katherine kathryn catherine kate kathy katie cathy
    - elizabeth liz beth betsy betty lisa
    - margaret peggy maggie meg
    - anthony tony
    - andrew andy drew
    - stephen steven steve
    - christopher chris
    - christine chris christina
    - matthew matt
    - nicholas nick
    - ronald ron ronnie
    - donald don donnie
    - gregory greg
    - gerald jerry
    - jerome jerry
    - henry hank harry
    - john jack johnny jon
    - jonathan jon
    - samuel sam sammy
    - benjamin ben benny
    - albert al bert
    - alan al
    - frederick fred freddie
    - francis frank
    - franklin frank
    - harold harry hal
    - jeffrey jeff
    - timothy tim
    - peter pete
    - philip phillip phil
    - raymond ray
    - walter walt wally
    - douglas doug
    - jennifer jen jenny
    - cynthia cindy
    - rebecca becky
    - deborah debra deb debbie
    - victoria vicky tori
    - sandra sandy
    - terrence terence terry
    - theresa teresa terry tess
    - alexander alex
    - alexandra alex
    - nathaniel nate nat
    - nathan nate
    - zachary zach zack
    - gary garry
    - leonard len lenny
    - louis lou
    - eugene gene
    - vincent vince
    - mitchell mitch
    - randall randy
    - rodney rod
    - russell russ
    - abraham abe
    - pamela pam
    - barbara barb
    - dorothy dot dottie
    - judith judy
    - jacqueline jackie
    - melissa missy

counsel_tag_tokens:
  source: 'user (counsel step - strip trailing tags like "-DOJ", "(USAO)"); tokens seen as trailing tags in the pilot'
  words: [doj, usao, ausa, sausa, fpd, cja, usa, crm, civ, tax, enrd, atr, oag]

# ---------------------------------------------------------------- parties
government_party_names:
  source: user (fix 1, ctx2 step). NOTE - this names one specific entity (the federal government as a party); kept
    because the user asked for it explicitly, flagged against the "no specific entity" rule.
  names: ["united states of america", "united states", "usa", "us", "u s a", "u s", "united states america"]
  not_if_contains: "ex rel"

org_party_words:
  source: 'user (fix 2, ctx2 step - legal forms, government / agency words); word list is my choice; "lloyds" added in step 4
    (data - "Allstate Texas Lloyds", "ASI Lloyds" were in the TXSD top-30 person-rule names, step3_titles.json)'
  words: [inc, incorporated, corp, corporation, llc, llp, lp, ltd, limited, co, company, plc, pc, pllc, pa, na, ag, sa,
          department, dept, agency, administration, bureau, commission, commissioner, board, authority, office, service,
          services, government, commonwealth, county, city, state, village, town, township, municipality, police, sheriff,
          district, school, university, college, hospital, bank, insurance, trust, fund, association, assn, group,
          industries, products, systems, international, holdings, partners, center, foundation, union, council, society,
          institute, enterprises, technologies, manufacturing, motors, airlines, railroad, railway, energy,
          pharmaceuticals, laboratories, lloyds]
  of_words:
    source: user (fix 2 - "State of", "County of", "City of")
    words: [state, county, city]

placeholder_party:
  source: 'user (fix 2 - placeholders - Unknown, Defendant(s), et al, Doe)'
  words: [doe, does, unknown, unnamed, "et al"]
  exact_names: [defendant, defendants, "defendant s", plaintiff, plaintiffs, "plaintiff s"]

party_evidence:
  source: choice (ctx step); RARE_* and COPARTY_* are thresholds I picked, see REPORT_ctx.md
  rare_max_cases: 3
  rare_person_min_tokens: 3
  coparty_max_cases: 10
  coparty_max_parties_in_case: 200

# ---------------------------------------------------------------- firms
federal_offices:
  source: user (ctx step - "U.S. Attorney / Federal Public Defender kept per district, whole words"). NOTE - these name
    two specific office types; kept because the user asked for them explicitly, flagged against the "no specific
    entity" rule.
  usao_pattern: |-
    \b(?:united states|u s|us)\s+attorneys?\b|\busao\b
  fpd_pattern: |-
    \bfederal\s+(?:public\s+|community\s+)?defenders?\b|\bfpd\b

# ---------------------------------------------------------------- judges (step 2)
judges:
  strip_parenthetical:
    source: 'data (out_ctx_txsd judge audit - "Magistrate Judge Andrew M Edison (Settlement)"); bracketed text is not part of a judge name'
    pattern: |-
      \([^)]*\)
  title_typos:
    source: 'data (out_ctx_txsd same-surname audit - "Jude Bryan", "Judgte Morgan", "Juge Ormsby", "Judges Ellison"); removed like titles'
    words: [jude, judges, judgte, juge, jduge, judgee, magistrat]
  non_name_words:
    source: 'data (out_ctx_txsd judge audit, txsd_ctx_checks.json - "Judge Unassigned", "Jury Selection", "Docket Call", "Final Pretrial",
      "Minute Entry", "Status Conference", "X Court", "X Appearances") plus common docket event words. A judge entry with any of these
      words is dropped. Words that are also common surnames (bond, call, case, hearn, ...) are deliberately left out.'
    words: [unassigned, jury, selection, docket, pretrial, conference, minute, minutes, entry, status, court, courts, appearances,
            appearance, settlement, hearing, final, duty, immigration, trial, term, voir, dire, courtesy, reminder, motion, motions,
            order, orders, sealed, clerk, deputy, reporter, recorder, courtroom, staff, interpreter, probation, none, unknown,
            this, calendar, arraignment, sentencing, detention, plea, mediation, deadline, deadlines, scheduling, proceedings,
            transcript, ero, filed, signed, referred, assigned, reassigned, magistrates, chambers, defendant, plaintiff, counsel,
            government, notice, set, reset, regarding]
  title_evidence:
    source: 'user (step 2 - keep the title Magistrate / District / Bankruptcy as evidence); U.S.M.J. / U.S.D.J. are the standard abbreviations'
    titles:
      magistrate: [magistrate, "u s m j", usmj]
      district: [district, "u s d j", usdj]
      bankruptcy: [bankruptcy]
  typo:
    source: 'user (step 2 - same court + same surname + first name 1 edit apart, unless both spellings have 20+ mentions).
      "1 edit" uses optimal string alignment distance, so a swapped letter pair (Kieth / Keith) is one edit.
      min_first_name_length is my choice so initials never count as typos.'
    max_first_name_edits: 1
    min_first_name_length: 3
    both_frequent_min_mentions: 20
  surname_only:
    source: 'user (step 2 - same case, then same division (number before ":" in the case ID), then same court; else one unresolved record per surname per court)'
    levels: [case, division, court]
    unresolved_id_prefix: SJU

# ---------------------------------------------------------------- organisations / agencies (step 4)
organisations:
  abbreviations:
    source: 'user (step 4 - normalise abbreviations Dept, Dep''t, &, punctuation); expansions are standard US abbreviations (my list)'
    map: {dept: department, depts: departments, dpt: department, govt: government, assn: association, natl: national,
          intl: international, univ: university, admin: administration, cnty: county, hosp: hospital, ctr: center,
          svcs: services, svc: service, mgmt: management, mfg: manufacturing, bros: brothers, corr: correctional}
    drop_words: [and]
  collapse_single_letters:
    source: 'user (step 4 - punctuation; revised) - runs of single letters are joined ONLY when they spell a legal form
      ("L.L.C." -> "llc"); "A. W." and "B. F." stay as they are'
    enabled: true
  legal_forms:
    source: 'notebook corp_suffix_words + plc, lp, llp, na, sa, ag (common legal forms); a suffix made only of these is never a
      division (step 4 revision a)'
    extra_words: [plc, lp, llp, na, sa, ag]
  acronym:
    source: 'user (step 4, revised) - an all-caps token is an organisation acronym ONLY if it equals the initials of an organisation
      name in the same court (initials ignore initials_skip_words) or carries a division suffix such as "-CID"; otherwise it stays
      under the person rule. Initials are collected per court over saved data + the whole input batch before matching, so both
      arrival orders give the same result within a run. Lengths are my choice.'
    min_length: 3
    max_length: 8
    initials_skip_words: [of, the, and, for, on, in, at, to, a, an]
  division:
    source: 'user (step 4 - division suffixes kept as aliases of the parent; revised). A suffix after " - ", "-", "," or "/" counts
      as a division when it contains one of these words, or when it is a single all-caps token that is the acronym of an
      organisation or division name in the same court (e.g. "-CID" where "Correctional Institutions Division" appears). A suffix
      made only of legal-form words is never a division.'
    separator_pattern: |-
      \s*[-–—/,]\s*
    words: [division, divisions, unit, section, branch, bureau, office, program, facility, institution, institutions,
            region, regional, center, unit, department]
    acronym_max_length: 6

# ---------------------------------------------------------------- lawyers (step 5)
counsel:
  pro_se:
    source: 'data (TXSD) - the JSON flag parties[].counsel[].is_pro_se marks pro se entries (9,646 in TXSD) and they get no counsel
      or firm mention. Text "pro se" without the flag (11 entries) and counsel named like their own party (101) were checked: they
      are lawyers (e.g. attorneys who are parties), so no extra text rule is added.'
    rule: is_pro_se flag
  no_contact:
    source: 'user (step 5) - counsel with no email / phone / address / office: same full name including a middle initial in the same
      court, or the same name representing the same party ID -> one ID. "Same name" = same first and last name, middle names not
      conflicting (my reading). full_name_min_tokens = first + middle + last.'
    full_name_min_tokens: 3

# ---------------------------------------------------------------- docket-text judges (step 6)
docket_judges:
  keep_rule:
    source: 'user (step 6) - a judge found only in docket text is kept only if it matches a judge from the case fields, the FJC
      list, or appears in this many different cases (counted over saved data + the input batch; kept in state.json)'
    min_cases: 3
  fjc_list:
    source: 'reference - FJC Biographical Directory of Article III judges, copy in the V3 repo (read-only):
      data/judges_fjc.csv (4,074 judges). Match = first or middle name (or their
      initial) + last name.'
    path: data/judges_fjc.csv

# ---------------------------------------------------------------- logging / run
uncertain_log:
  source: choice (keeps uncertain_pairs.jsonl readable)
  max_candidates_per_mention: 3
  max_courts_shown: 10

progress_every:
  source: user (progress step)
  files: 500

removed_unused:
  source: audit (step 1) - defined in the code but never used; removed, behaviour unchanged
  items:
    - COMMON_NAMES (notebook's old Rule 4 list; the context matcher never used it)
    - ORG_WORDS (replaced by org_party_words in ctx2)
```

## Files

- **Code and rules:** `v4_run_ctx.py`, `v4_rules.yaml`, the `v4_run_ctx_before_step1/2/3/4/4b/5/6.py` copies, `test_ctx.py` (36 checks).
- **Step outputs:** `out_step{1,2,4c,5,6}_1000`, `out_step{1,2,4,5,6}_txsd`; logs in `run_step*_txsd.log`.
- **Final outputs:** `out_final_1000`, `out_final_txsd`, `out_final_inc` (+ `out_final_inc_snapshot40000`), `out_final_rev`; `final_runs.sh` / `final_runs.log`.
- **Analysis:** `final_analysis.py`, `analysis_final/report.json`, `review_sample.csv`, `score_final.json` / `score_final.txt`, `key_disagreements.json`, `txsd_checks_final.json`, `steps_log.md`.
- **Kept as asked:** `try_step4_fix/`.