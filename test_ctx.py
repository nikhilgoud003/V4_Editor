#!/usr/bin/env python3
"""Tests for v4_run_ctx.py. Writes only under ./tests_ctx/ (must not exist yet).

  1. "J Smith" judge and "John Smith" judge in the same court -> one ID
  2. "J Smith" party vs "John Smith" judge -> two IDs
  3. "John Smith" party in two unrelated cases -> two IDs
  4. the same with a shared firm -> one ID
  5. incremental 800 + 200 on the pilot keeps 100% of old IDs, and re-adding a file changes nothing
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "v4_run_ctx.py"
# Test 5 needs a folder of 1,000 real PACER case files; set V4_PILOT_DIR to run it (skipped otherwise).
PILOT = Path(os.environ["V4_PILOT_DIR"]).expanduser() if os.environ.get("V4_PILOT_DIR") else None
T = HERE / (sys.argv[1] if len(sys.argv) > 1 else "tests_ctx")  # test folder (must not exist)
results = []


def case(ucid, court, judge=None, parties=(), referred=()):
    return {"ucid": ucid, "court": court, "judge": judge, "referred_judges": list(referred), "docket": [],
            "parties": [{"name": n, "counsel": [{"name": cn, "entity_info": info} for cn, info in counsel]}
                        for n, counsel in parties]}


def write_cases(folder, cases):
    folder.mkdir(parents=True)
    for c in cases:
        (folder / (c["ucid"].replace(";;", "-").replace(":", "-") + ".json")).write_text(json.dumps(c))


def run(inputs, out, *extra):
    r = subprocess.run([sys.executable, str(SCRIPT), "--input", *map(str, inputs), "--output", str(out), *extra],
                       capture_output=True, text=True)
    if r.returncode:
        print(r.stdout, r.stderr)
        raise SystemExit("run failed")
    return r.stdout


def load(out):
    ents = [json.loads(l) for l in open(out / "entities.jsonl")]
    ments = {m["mention_id"]: m for m in map(json.loads, open(out / "mentions.jsonl"))}
    return ents, ments


def ids_for(ments, etype, raw):
    return sorted({m["entity_id"] for m in ments.values() if m["entity_type"] == etype and m["raw_name"] == raw})


def check(name, ok, detail):
    results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  ({detail})")


def info(office, addr, phone, email):
    return {"office_name": office, "address": addr, "phone": phone, "email": email}


if T.exists():
    raise SystemExit(f"{T} already exists; remove it or choose another folder")
T.mkdir()

# --- tests 1 and 2: judges, and party vs judge ---
write_cases(T / "in_judges", [
    case("nyed;;1:16-cv-00001", "nyed", judge="John Smith",
         parties=[("Acme Widgets Inc", [("Ann Lee", info("Lee LLP", "1 Main St, Brooklyn, NY 11201", "718-555-0101", "alee@lee.example.com"))])]),
    case("nyed;;1:16-cv-00002", "nyed", judge="J. Smith",
         parties=[("Beta Tools LLC", [("Bob Kim", info("Kim PC", "9 Elm St, Brooklyn, NY 11201", "718-555-0202", "bkim@kim.example.com"))])]),
    case("nyed;;1:16-cv-00003", "nyed", judge="John Smith",
         parties=[("J. Smith", [("Cara Diaz", info("Diaz Law", "5 Oak St, Queens, NY 11375", "718-555-0303", "cdiaz@diaz.example.com"))])]),
])
out = T / "out_judges"
run([T / "in_judges"], out)
_, m = load(out)
j_full, j_init = ids_for(m, "judge", "John Smith"), ids_for(m, "judge", "J. Smith")
check("1. J Smith judge + John Smith judge, same court -> one ID", len(j_full) == 1 and j_full == j_init, f"{j_full} / {j_init}")
p_js = ids_for(m, "party", "J. Smith")
check("2. J Smith party vs John Smith judge -> two IDs", len(p_js) == 1 and p_js != j_full, f"party {p_js} vs judge {j_full}")

# --- test 3: same party name, unrelated cases ---
write_cases(T / "in_parties_unrelated", [
    case("ilnd;;1:16-cv-00010", "ilnd", parties=[
        ("John Smith", [("Dana White", info("White Law Group", "100 W Madison St, Chicago, IL 60602", "312-555-1000", "dwhite@white.example.com"))]),
        ("Gamma Corp", [("Eli Stone", info("Stone LLP", "200 N State St, Chicago, IL 60601", "312-555-2000", "estone@stone.example.com"))])]),
    case("ilnd;;1:17-cv-00020", "ilnd", parties=[
        ("John Smith", [("Fay Gold", info("Gold & Partners", "300 S Wacker Dr, Chicago, IL 60606", "312-555-3000", "fgold@gold.example.com"))]),
        ("Delta Inc", [("Gus Hill", info("Hill PC", "400 E Ohio St, Chicago, IL 60611", "312-555-4000", "ghill@hill.example.com"))])]),
])
out = T / "out_parties_unrelated"
run([T / "in_parties_unrelated"], out)
_, m = load(out)
p3 = ids_for(m, "party", "John Smith")
check("3. John Smith party in two unrelated cases -> two IDs", len(p3) == 2, f"{p3}")

# --- test 4: same party name, shared firm ---
acme = info("Acme Law LLP", "50 Park Ave, Suite 10, New York, NY 10016", "212-555-5000", "")
write_cases(T / "in_parties_shared_firm", [
    case("nysd;;1:16-cv-00030", "nysd", parties=[
        ("John Smith", [("Hal Ives", acme)]), ("Epsilon LLC", [("Ida Jones", info("Jones PC", "60 Wall St, New York, NY 10005", "212-555-6000", "ijones@jones.example.com"))])]),
    case("nysd;;1:17-cv-00040", "nysd", parties=[
        ("John Smith", [("Jack Kerr", acme)]), ("Zeta Inc", [("Kim Long", info("Long LLP", "70 Pine St, New York, NY 10005", "212-555-7000", "klong@long.example.com"))])]),
])
out = T / "out_parties_shared_firm"
run([T / "in_parties_shared_firm"], out)
_, m = load(out)
p4, f4 = ids_for(m, "party", "John Smith"), ids_for(m, "firm", "Acme Law LLP")
check("4. John Smith party, two cases, shared firm -> one ID", len(p4) == 1, f"party {p4}, firm {f4}")

# --- test 6 (chaining guard): J Smith must not link John Smith and James Smith ---
write_cases(T / "in_chain", [
    case("nyed;;1:18-cv-00011", "nyed", judge="John Smith"),
    case("nyed;;1:18-cv-00012", "nyed", judge="J. Smith"),
    case("nyed;;1:18-cv-00013", "nyed", judge="James Smith"),
])
for order in ("name", "reverse"):
    out = T / f"out_chain_{order}"
    run([T / "in_chain"], out, "--order", order)
    _, m = load(out)
    jo, js, ja = ids_for(m, "judge", "John Smith"), ids_for(m, "judge", "J. Smith"), ids_for(m, "judge", "James Smith")
    # J. Smith joins whichever full name is saved first (John in name order, James in reverse order),
    # but John and James must never end up in one entity.
    check(f"6. chaining guard ({order} order): John and James never share an ID; J. Smith joins exactly one",
          len(jo) == 1 and len(ja) == 1 and ja != jo and len(js) == 1 and js[0] in (jo[0], ja[0]),
          f"John {jo}, J. {js}, James {ja}")

# --- test 7 (surname-only judges) ---
write_cases(T / "in_surname_only", [
    case("ilnd;;1:09-cv-00001", "ilnd", judge="Ruben Castillo", referred=["Judge Castillo"]),
    case("ilnd;;1:09-cv-00002", "ilnd", judge="Maria Castillo"),
    case("ilnd;;1:09-cv-00003", "ilnd", judge="Judge Castillo"),
])
out = T / "out_surname_only"
run([T / "in_surname_only"], out)
_, m = load(out)
rc, mc_ = ids_for(m, "judge", "Ruben Castillo"), ids_for(m, "judge", "Maria Castillo")
jc = {mm["entity_id"] for mm in m.values() if mm["entity_type"] == "judge" and mm["raw_name"] == "Judge Castillo"}
jc_case1 = {mm["entity_id"] for mm in m.values() if mm["raw_name"] == "Judge Castillo" and mm["ucid"] == "ilnd;;1:09-cv-00001"}
jc_case3 = {mm["entity_id"] for mm in m.values() if mm["raw_name"] == "Judge Castillo" and mm["ucid"] == "ilnd;;1:09-cv-00003"}
unc = [json.loads(l) for l in open(out / "uncertain_pairs.jsonl")]
check("7a. 'Judge Castillo' in the same case as Ruben Castillo -> Ruben's ID", jc_case1 == set(rc), f"{jc_case1} vs {rc}")
check("7b. 'Judge Castillo' alone, two Castillo judges in the court -> neither, logged uncertain",
      jc_case3 and not (jc_case3 & set(rc + mc_)) and any("surname-only" in u["reason"] for u in unc),
      f"case3 {jc_case3}, Ruben {rc}, Maria {mc_}, uncertain rows {len(unc)}")

# --- test 8 (counsel tags): "-DOJ" is not the surname ---
doj = info("U.S. Department of Justice", "950 Pennsylvania Ave NW, Washington, DC 20530", "202-555-0000", "")
write_cases(T / "in_counsel_tags", [
    case("txnd;;2:17-cr-00017", "txnd", parties=[("Alpha Co", [("Jared R Frost-DOJ", {**doj, "email": "jared.frost@example.gov"}),
                                                             ("Joel Kent Dale-DOJ", {**doj, "email": "joel.dale@example.gov"})])]),
    case("txnd;;4:16-cv-00102", "txnd", parties=[("Beta Co", [("J Neil Oster-DOJ", {**doj, "email": "j.oster@example.gov"}),
                                                             ("Jared R Frost-DOJ", {**doj, "email": "jared.frost@example.gov"})])]),
])
out = T / "out_counsel_tags"
run([T / "in_counsel_tags"], out)
_, m = load(out)
h, f_, w = ids_for(m, "counsel", "Jared R Frost-DOJ"), ids_for(m, "counsel", "Joel Kent Dale-DOJ"), ids_for(m, "counsel", "J Neil Oster-DOJ")
check("8. counsel '-DOJ' tag: Frost (2 cases, same email) one ID; Frost, Dale, Oster three IDs",
      len(h) == 1 and len({*h, *f_, *w}) == 3, f"Frost {h}, Dale {f_}, Oster {w}")

# --- test 9 (step 1): behaviour comes from v4_rules.yaml ---
import yaml
write_cases(T / "in_rules", [
    case("txsd;;1:16-cr-00001", "txsd", parties=[("USA", [("Ann Lee", info("Lee LLP", "1 Main St, Houston, TX 77002", "713-555-0101", "alee@lee.example.com"))])]),
    case("txsd;;1:16-cr-00002", "txsd", parties=[("USA", [("Bob Kim", info("Kim PC", "9 Elm St, Houston, TX 77002", "713-555-0202", "bkim@kim.example.com"))])]),
])
rules = yaml.safe_load(open(HERE / "v4_rules.yaml"))
rules["government_party_names"]["names"] = [n for n in rules["government_party_names"]["names"] if n != "usa"]
custom = T / "rules_without_usa.yaml"
custom.write_text(yaml.safe_dump(rules, sort_keys=False, allow_unicode=True))
run([T / "in_rules"], T / "out_rules_default")
run([T / "in_rules"], T / "out_rules_custom", "--rules", str(custom))
_, md = load(T / "out_rules_default")
_, mc = load(T / "out_rules_custom")
check("9. rules file drives behaviour: 'USA' folds with default rules, not when 'usa' is removed from the YAML",
      len(ids_for(md, "party", "USA")) == 1 and len(ids_for(mc, "party", "USA")) == 2,
      f"default {ids_for(md, 'party', 'USA')}, custom {ids_for(mc, 'party', 'USA')}")

# --- test 10 (step 2): judges ---
cases10 = [case(f"txsd;;7:16-cv-{i:05d}", "txsd", judge="Randy Crane") for i in range(1, 4)]
cases10 += [case("txsd;;7:16-cv-00010", "txsd", judge="Rndy Crane")]                               # typo -> Randy
cases10 += [case(f"txsd;;4:16-cv-{i:05d}", "txsd", judge="Gray Hollis") for i in range(1, 21)]    # 20+ each:
cases10 += [case(f"txsd;;4:17-cv-{i:05d}", "txsd", judge="Gary Hollis") for i in range(1, 21)]    # not merged
cases10 += [case("txsd;;1:16-cv-00001", "txsd", judge="Ana Lopez"),
            case("txsd;;2:16-cv-00001", "txsd", judge="Ben Lopez"),
            case("txsd;;1:17-cv-00002", "txsd", judge="Judge Lopez"),                              # division 1 -> Ana
            case("txsd;;3:16-cv-00001", "txsd", judge="Magistrate Judge Cora Diaz"),
            case("txsd;;3:16-cv-00002", "txsd", judge="District Judge Dan Diaz"),
            case("txsd;;3:17-cv-00003", "txsd", judge="Magistrate Judge Diaz"),                    # title -> Cora
            case("txsd;;5:16-cv-00001", "txsd", judge="Eve Ruiz"),
            case("txsd;;5:16-cv-00002", "txsd", judge="Finn Ruiz"),
            case("txsd;;5:17-cv-00003", "txsd", judge="Judge Ruiz"),                               # ambiguous -> unresolved
            case("txsd;;5:17-cv-00004", "txsd", judge="Judge Ruiz"),
            case("txsd;;6:16-cv-00001", "txsd", judge="Judge Unassigned", referred=["Jury Selection"])]
write_cases(T / "in_judges2", cases10)
out = T / "out_judges2"
run([T / "in_judges2"], out)
ents10, m = load(out)
eid = lambda raw, ucid=None: {mm["entity_id"] for mm in m.values() if mm["entity_type"] == "judge" and mm["raw_name"] == raw
                              and (ucid is None or mm["ucid"] == ucid)}
check("10a. typo: 'Rndy Crane' joins 'Randy Crane' (same court, same surname, 1 edit)", eid("Rndy Crane") == eid("Randy Crane") and len(eid("Randy Crane")) == 1,
      f"{eid('Rndy Crane')} vs {eid('Randy Crane')}")
check("10b. typo blocked: 'Gary Hollis' and 'Gray Hollis' both have 20+ mentions -> two IDs", eid("Gary Hollis") != eid("Gray Hollis"),
      f"{eid('Gary Hollis')} vs {eid('Gray Hollis')}")
check("10c. surname-only: 'Judge Lopez' in division 1 -> Ana Lopez (division 1), not Ben Lopez (division 2)", eid("Judge Lopez") == eid("Ana Lopez"),
      f"{eid('Judge Lopez')} vs Ana {eid('Ana Lopez')}, Ben {eid('Ben Lopez')}")
check("10d. title as evidence: 'Magistrate Judge Diaz' -> the magistrate Cora Diaz", eid("Magistrate Judge Diaz") == eid("Magistrate Judge Cora Diaz"),
      f"{eid('Magistrate Judge Diaz')} vs Cora {eid('Magistrate Judge Cora Diaz')}, Dan {eid('District Judge Dan Diaz')}")
unres = [e for e in ents10 if e.get("unresolved")]
ruiz = eid("Judge Ruiz")
check("10e. ambiguous surname-only -> one unresolved record per surname per court, flagged, no sjid",
      len(ruiz) == 1 and len(unres) == 1 and unres[0]["entity_id"] in ruiz and unres[0]["sjid"] is None
      and all(mm.get("unresolved") for mm in m.values() if mm["raw_name"] == "Judge Ruiz"),
      f"Judge Ruiz -> {ruiz}; unresolved records {[e['entity_id'] for e in unres]}")
check("10f. non-name judge entries dropped ('Judge Unassigned', 'Jury Selection')", not eid("Judge Unassigned") and not eid("Jury Selection"),
      f"{eid('Judge Unassigned')} {eid('Jury Selection')}")

# --- test 11 (step 4): agencies ---
write_cases(T / "in_agencies", [
    case("txsd;;4:16-cv-00001", "txsd", parties=[("Texas Department of Criminal Justice", [])]),
    case("txsd;;4:16-cv-00002", "txsd", parties=[("TDCJ", [])]),
    case("txsd;;4:16-cv-00003", "txsd", parties=[("Texas Dept. of Criminal Justice - Correctional Institutions Division", [])]),
    case("txsd;;4:16-cv-00004", "txsd", parties=[("TDCJ-CID", [])]),
    case("txsd;;4:16-cv-00005", "txsd", parties=[("University of Texas Medical Branch", [])]),
    case("txsd;;4:16-cv-00006", "txsd", parties=[("UTMB", [])]),
    case("nysd;;1:16-cv-00007", "nysd", parties=[("TDCJ", [])]),
    case("txsd;;4:16-cv-00008", "txsd", parties=[("Wal-Mart Stores Texas, L.L.C.", [])]),
    case("txsd;;4:16-cv-00009", "txsd", parties=[("Wal Mart Stores Texas LLC", [])]),
    case("txsd;;4:16-cv-00010", "txsd", parties=[("Smith & Wesson Corp", [])]),
    case("txsd;;4:16-cv-00011", "txsd", parties=[("Smith and Wesson Corporation", [])]),
])
out = T / "out_agencies"
run([T / "in_agencies"], out)
_, m = load(out)
pid = lambda raw, ucid=None: {mm["entity_id"] for mm in m.values() if mm["entity_type"] == "party" and mm["raw_name"] == raw
                              and (ucid is None or mm["ucid"] == ucid)}
tdcj = pid("Texas Department of Criminal Justice")
check("11a. TDCJ full name, 'TDCJ', 'Dept.' + division suffix, 'TDCJ-CID' (same court) -> one ID",
      len(tdcj) == 1 and pid("TDCJ", "txsd;;4:16-cv-00002") == tdcj
      and pid("Texas Dept. of Criminal Justice - Correctional Institutions Division") == tdcj and pid("TDCJ-CID") == tdcj,
      f"{tdcj} {pid('TDCJ', 'txsd;;4:16-cv-00002')} {pid('Texas Dept. of Criminal Justice - Correctional Institutions Division')} {pid('TDCJ-CID')}")
check("11b. 'UTMB' = initials of 'University of Texas Medical Branch' in the same court -> one ID",
      pid("UTMB") == pid("University of Texas Medical Branch"), f"{pid('UTMB')} vs {pid('University of Texas Medical Branch')}")
check("11c. 'TDCJ' in another court is not merged (acronyms are court-scoped)", not (pid("TDCJ", "nysd;;1:16-cv-00007") & tdcj),
      f"nysd {pid('TDCJ', 'nysd;;1:16-cv-00007')} vs txsd {tdcj}")
check("11d. punctuation / dotted legal form: 'Wal-Mart Stores Texas, L.L.C.' = 'Wal Mart Stores Texas LLC'",
      pid("Wal-Mart Stores Texas, L.L.C.") == pid("Wal Mart Stores Texas LLC"), "")
check("11e. '&' vs 'and': 'Smith & Wesson Corp' = 'Smith and Wesson Corporation'",
      pid("Smith & Wesson Corp") == pid("Smith and Wesson Corporation"), "")

# --- test 11f (step 4): both arrival orders ---
out = T / "out_agencies_reverse"
run([T / "in_agencies"], out, "--order", "reverse")
_, m = load(out)
tdcj_r = pid("Texas Department of Criminal Justice")
check("11f. reverse order (acronyms arrive first): same TDCJ and UTMB groups",
      len(tdcj_r) == 1 and pid("TDCJ", "txsd;;4:16-cv-00002") == tdcj_r and pid("TDCJ-CID") == tdcj_r
      and pid("Texas Dept. of Criminal Justice - Correctional Institutions Division") == tdcj_r
      and pid("UTMB") == pid("University of Texas Medical Branch") and not (pid("TDCJ", "nysd;;1:16-cv-00007") & tdcj_r),
      f"TDCJ {tdcj_r} / {pid('TDCJ', 'txsd;;4:16-cv-00002')} / {pid('TDCJ-CID')}; UTMB {pid('UTMB')} vs {pid('University of Texas Medical Branch')}")

# --- test 12 (step 4): a lone all-caps word stays a person ---
write_cases(T / "in_smith", [
    case("txsd;;4:18-cv-00001", "txsd", parties=[("SMITH", [("Ann Lee", info("Lee LLP", "1 Main St, Houston, TX 77002", "713-555-0101", "alee@lee.example.com"))])]),
    case("txsd;;4:18-cv-00002", "txsd", parties=[("SMITH", [("Bob Kim", info("Kim PC", "9 Elm St, Houston, TX 77002", "713-555-0202", "bkim@kim.example.com"))])]),
])
out = T / "out_smith"
run([T / "in_smith"], out)
_, m = load(out)
check("12. two 'SMITH' parties in different cases -> 2 IDs (not an acronym: no matching org initials, no division suffix)",
      len(ids_for(m, "party", "SMITH")) == 2, f"{ids_for(m, 'party', 'SMITH')}")

# --- test 13 (step 4 revision): a subsidiary suffix that is not a known acronym is not a division ---
write_cases(T / "in_grace", [
    case("paed;;2:08-cv-00001", "paed", parties=[("W. R. GRACE & CO.", [])]),
    case("paed;;2:08-cv-00002", "paed", parties=[("W.R. GRACE & CO.-CONN.", [])]),
])
out = T / "out_grace"
run([T / "in_grace"], out)
_, m = load(out)
g1, g2 = ids_for(m, "party", "W. R. GRACE & CO."), ids_for(m, "party", "W.R. GRACE & CO.-CONN.")
check("13. 'W.R. GRACE & CO.-CONN.' and 'W. R. GRACE & CO.' keep 2 IDs ('-CONN.' is no acronym of an org in this court)",
      len(g1) == 1 and len(g2) == 1 and g1 != g2, f"{g1} vs {g2}")

# --- test 14 (step 5): lawyers ---
nc = {"office_name": None, "address": None, "phone": None, "email": None}
def case_c(ucid, court, parties):
    c = case(ucid, court, parties=[(n, cl) for n, cl in parties])
    return c
c14 = [case_c("txsd;;4:19-cv-00001", "txsd", [("Alpha Person", [("John Q Public", nc)])]),
       case_c("txsd;;4:19-cv-00002", "txsd", [("Beta Person", [("John Q Public", nc)])]),
       case_c("txsd;;4:19-cv-00003", "txsd", [("Gamma Person", [("John Public", nc)])]),
       case_c("txsd;;4:19-cv-00004", "txsd", [("Delta Person", [("John Public", nc)])]),
       case_c("txsd;;4:19-cv-00005", "txsd", [("Acme Industries Inc", [("Mary Roe", nc)])]),
       case_c("txsd;;4:19-cv-00006", "txsd", [("Acme Industries Inc", [("Mary Roe", nc)])])]
c14.append({"ucid": "txsd;;4:19-cv-00007", "court": "txsd", "judge": None, "referred_judges": [], "docket": [],
            "parties": [{"name": "Pat Selfrep", "counsel": [{"name": "Pat Selfrep", "is_pro_se": True,
                                                              "entity_info": {"office_name": "PRO SE", "raw_info": "PRO SE"}}]}]})
write_cases(T / "in_lawyers", c14)
out = T / "out_lawyers"
run([T / "in_lawyers"], out)
_, m = load(out)
check("14a. no contact, same full name with middle initial, same court -> one ID", len(ids_for(m, "counsel", "John Q Public")) == 1,
      f"{ids_for(m, 'counsel', 'John Q Public')}")
check("14b. no contact, 'John Public' (no middle), different parties -> two IDs", len(ids_for(m, "counsel", "John Public")) == 2,
      f"{ids_for(m, 'counsel', 'John Public')}")
check("14c. no contact, same name representing the same party ID (Acme Industries) -> one ID", len(ids_for(m, "counsel", "Mary Roe")) == 1,
      f"{ids_for(m, 'counsel', 'Mary Roe')}, party {ids_for(m, 'party', 'Acme Industries Inc')}")
check("14d. pro se entry -> no counsel or firm mention", not ids_for(m, "counsel", "Pat Selfrep") and not ids_for(m, "firm", "PRO SE"),
      f"{ids_for(m, 'counsel', 'Pat Selfrep')} {ids_for(m, 'firm', 'PRO SE')}")

# --- test 15 (step 6): docket-text judges ---
def dcase(ucid, court, judge, texts):
    c = case(ucid, court, judge=judge)
    c["docket"] = [{"docket_text": t} for t in texts]
    return c
c15 = [dcase("txsd;;4:20-cv-00001", "txsd", "Zed Quill", ["Hearing held before Magistrate Judge Ann Vexx on 1/2/2020.",
                                                          "Motion hearing before Judge Quill. (jdoe)"]),
       dcase("txsd;;4:20-cv-00002", "txsd", "Zed Quill", ["ORDER signed by Judge Lynn N. Hughes on 2/3/2020."])]
c15 += [dcase(f"txsd;;4:20-cv-{i:05d}", "txsd", "Zed Quill", ["Case referred to Magistrate Judge Bo Krell for pretrial."]) for i in (3, 4, 5)]
write_cases(T / "in_docket", c15)
out = T / "out_docket"
run([T / "in_docket"], out)
_, m = load(out)
jn = lambda raw: {mm["entity_id"] for mm in m.values() if mm["entity_type"] == "judge" and mm["raw_name"] == raw}
check("15a. docket-only judge in 1 case, not on FJC, not in case fields -> dropped ('Ann Vexx')", not jn("Ann Vexx"), f"{jn('Ann Vexx')}")
check("15b. docket-only judge in 3 different cases -> kept ('Bo Krell', one ID)", len(jn("Bo Krell")) == 1, f"{jn('Bo Krell')}")
if (HERE / "data" / "judges_fjc.csv").exists():
    check("15c. docket-only judge on the FJC list -> kept ('Lynn N. Hughes')", len(jn("Lynn N. Hughes")) == 1, f"{jn('Lynn N. Hughes')}")
else:
    print("SKIP  15c. FJC list check (put the FJC judge list at data/judges_fjc.csv)")
check("15d. docket surname matching the case's own judge -> kept and joins him ('Quill' -> 'Zed Quill')",
      jn("Quill") and jn("Quill") == jn("Zed Quill"), f"{jn('Quill')} vs {jn('Zed Quill')}")

# --- test 5: incremental 800 + 200 on the pilot (needs V4_PILOT_DIR) ---
if PILOT is None:
    print("SKIP  5a-5d. incremental 800 + 200 (set V4_PILOT_DIR to a folder of 1,000 PACER JSON files)")
    print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed (test 5 skipped)")
    sys.exit(0 if all(ok for _, ok in results) else 1)
names = sorted(p.name for p in PILOT.glob("*.json"))
for sub, part in (("in_800", names[:800]), ("in_200", names[800:])):
    (T / sub).mkdir()
    for n in part:
        (T / sub / n).symlink_to(PILOT / n)
out = T / "out_800_200"
run([T / "in_800"], out)
ents800, m800 = load(out)
snap_m = {k: v["entity_id"] for k, v in m800.items()}
snap_e = {e["entity_id"]: (e["entity_type"], e.get("sjid") or e.get("spid") or e.get("scid") or e.get("sfid")) for e in ents800}
run([T / "in_200"], out)
ents, m = load(out)
kept_m = sum(m[k]["entity_id"] == v for k, v in snap_m.items())
now_e = {e["entity_id"]: (e["entity_type"], e.get("sjid") or e.get("spid") or e.get("scid") or e.get("sfid")) for e in ents}
kept_e = sum(now_e.get(k) == v for k, v in snap_e.items())
state = json.load(open(out / "state.json"))
check("5a. 800 + 200: old mentions keep their entity ID", kept_m == len(snap_m), f"{kept_m}/{len(snap_m)}")
check("5b. 800 + 200: old entity IDs all still present, same type and ID", kept_e == len(snap_e), f"{kept_e}/{len(snap_e)}")
check("5c. 800 + 200: 1,000 files recorded", len(state["processed_files"]) == 1000, f"{len(state['processed_files'])}")
before = {f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in ("entities.jsonl", "mentions.jsonl", "state.json", "uncertain_pairs.jsonl")}
run([PILOT / names[0]], out)
after = {f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in before}
check("5d. re-adding an already processed file changes nothing", before == after, "all 4 output files byte-identical" if before == after else "files changed")

print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
sys.exit(0 if all(ok for _, ok in results) else 1)
