# Step log (V4 finish job)

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
