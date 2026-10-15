# V4: context-aware, incremental entity resolution for PACER dockets

V4 reads PACER case JSON files and gives stable IDs to the **judges, parties, counsel and firms** named in them.

- **One pass per file.** Every mention is matched against an index of saved entities, keyed by entity type and surname or name.
- **Merges need context.** Judges need the same court and a compatible name. Person parties need shared counsel, firm or co-party evidence. Counsel need shared contact details. Firms need a shared address, phone or email domain. Organisations merge on identical normalised names and acronyms.
- **Close but unproven pairs** are written to `uncertain_pairs.jsonl` and not merged.
- **Incremental.** Running again on the same output folder adds only new files (skipped by name + sha256). Old IDs never change, and saved entities are never merged together.
- **Rules live in a file.** Every word list, pattern and threshold is in `v4_rules.yaml`, with a `source:` note for each.

`REPORT_final.md` has the results and known problems, including a Step 6 judge bug: docket names with an undotted middle initial are cut to the first word. `steps_log.md` records each step and its checks.

## Setup

Requires Python 3.12+ (the code uses f-string forms that need it).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install rapidfuzz pyyaml
```

**Optional:** the FJC judge list, used to keep docket-only judges. Download the "Biographical Directory of Article III Federal Judges" export from fjc.gov and save it as `data/judges_fjc.csv`. Without it, docket-only judges are kept only when they match a judge in the case fields or appear in 3+ cases.

## Run

```bash
# first run: --input can be one or more .json files, a folder of .json files, or a .zip
python v4_run_ctx.py --input /path/to/json_folder --output /path/to/run_folder

# add new files later to the same output (already processed files are skipped, old IDs stay)
python v4_run_ctx.py --input /path/to/new_files --output /path/to/run_folder

# start fresh: use an output folder that does not exist yet
python v4_run_ctx.py --input /path/to/json_folder --output /path/to/new_run_folder

# other options
python v4_run_ctx.py --input ... --output ... --rules my_rules.yaml   # a different rules file
python v4_run_ctx.py --input ... --output ... --order reverse          # file order test
```

Output files, in the `--output` folder:

| File | Contents |
|---|---|
| `entities.jsonl` | one row per entity: ID, type, canonical name, name variants, courts, cases, mention IDs. Judge "unresolved" records (`"unresolved": true`) are not judges. |
| `mentions.jsonl` | one row per extracted name: mention ID, type, case ID, court, raw / clean name, entity ID, and the context used for matching |
| `state.json` | ID counters, processed files (name + sha256), docket-judge case counts |
| `uncertain_pairs.jsonl` | close pairs that were not merged, with the reason |

## Tests

```bash
python test_ctx.py tests_run1            # the folder name must not exist yet
```

- **Most tests use small synthetic case files** that the test writes itself.
- **Test 5** (incremental 800 + 200 and re-adding a file) needs a folder of 1,000 real PACER JSON files. Set `V4_PILOT_DIR=/path/to/pilot_json` to run it; otherwise it is skipped.
- **Test 15c** needs `data/judges_fjc.csv`; otherwise it is skipped.
- With both inputs present there are 36 checks.

## Document reader

`doc_reader` is separate from the docket pipeline. It reads OCR or layout JSON (pages of blocks with text, confidence, and a box) and writes entity mentions. Any other JSON is read as generic text fields. Docket JSON is skipped.

Python 3.13 is supported. `probablepeople` 0.5.6 installs on 3.13 and is the second person vote, together with spaCy. The extractor is GLiNER2 `fastino/gliner2-base-v1` on CPU. The first run downloads that model.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

```bash
python -m doc_reader --input /path/to/ocr_json --output /path/to/out_folder
python -m doc_reader --input /path/to/one.json --output /path/to/out_folder --model ollama --ollama-model qwen2.5:7b
python test_doc_reader.py
```

On a Mac, if spaCy and PyTorch both load OpenMP, set these before the command:

```bash
export KMP_DUPLICATE_LIB_OK=TRUE
export OMP_NUM_THREADS=1
```

The output folder gets `mentions.jsonl` (the same mention fields as `v4_run_ctx.py`, plus page, box, scores, and `source` set to `document`), `review.jsonl`, `review_docs.csv` (a `correct?` column left empty), and `report.md`.

## Scoring

`score.py` scores runs against a hand-made answer key folder (`answer_key_detail.csv`, `work/sample200.txt`). The key is not included.

```bash
python score.py --key /path/to/answer_key --v4dir V4=/path/to/run_folder --out score.json
```
