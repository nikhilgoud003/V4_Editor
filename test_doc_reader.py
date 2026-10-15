"""Unit tests for the document reader. Examples are synthetic."""

import json
import tempfile
import unittest
from pathlib import Path

from doc_reader.case_id import cross_check, parse_filename
from doc_reader.chunk import block_inputs, windows
from doc_reader.clean import clean_pages
from doc_reader.detect import detect_kind
from doc_reader.gate import gate_decision
from doc_reader.records import V4_FIELDS, assign_ids, make_mention
from doc_reader.write_out import write_outputs


class CleanTests(unittest.TestCase):
    def test_drops_duplicate_text_and_overlap(self):
        pages = [
            {
                "page": 1,
                "blocks": [
                    {"class": "block", "confidence": 0.9, "bbox": [0, 0, 10, 10], "text": "Alpha line"},
                    {"class": "block", "confidence": 0.6, "bbox": [1, 1, 9, 9], "text": "Alpha line"},
                    {"class": "block", "confidence": 0.85, "bbox": [0, 0, 10, 10], "text": "Different words here"},
                    {"class": "block", "confidence": 0.88, "bbox": [100, 100, 110, 110], "text": "Other line"},
                    {"class": "block", "confidence": 0.7, "bbox": [300, 0, 310, 10], "text": "Filler one"},
                    {"class": "block", "confidence": 0.72, "bbox": [320, 0, 330, 10], "text": "Filler two"},
                    {"class": "block", "confidence": 0.74, "bbox": [340, 0, 350, 10], "text": "Filler three"},
                    {"class": "block", "confidence": 0.76, "bbox": [360, 0, 370, 10], "text": "Filler four"},
                    {"class": "block", "confidence": 0.78, "bbox": [380, 0, 390, 10], "text": "Filler five"},
                    {"class": "block", "confidence": 0.8, "bbox": [400, 0, 410, 10], "text": "Filler six"},
                    {"class": "block", "confidence": 0.01, "bbox": [200, 200, 210, 220], "text": "Too faint"},
                ],
            }
        ]
        kept, report = clean_pages(pages)
        texts = [row["text"] for row in kept]
        self.assertIn("Alpha line", texts)
        self.assertEqual(texts.count("Alpha line"), 1)
        self.assertNotIn("Different words here", texts)
        self.assertIn("Other line", texts)
        self.assertNotIn("Too faint", texts)
        self.assertGreaterEqual(report["dropped_duplicate"], 2)
        self.assertGreaterEqual(report["dropped_low_confidence"], 1)
        kept_alpha = next(row for row in kept if row["text"] == "Alpha line")
        self.assertEqual(kept_alpha["confidence"], 0.9)


class ChunkTests(unittest.TestCase):
    def test_windows_fit_the_word_cap(self):
        text = " ".join(f"w{i}" for i in range(23))
        parts = windows(text, 5)
        self.assertTrue(parts)
        self.assertTrue(all(len(part.split()) <= 5 for part in parts))
        self.assertEqual([word for part in parts for word in part.split()], text.split())

    def test_block_inputs_stay_under_both_caps(self):
        block = " ".join(f"b{i}" for i in range(12))
        prev = " ".join(f"p{i}" for i in range(8))
        nxt = " ".join(f"n{i}" for i in range(8))

        def count_tokens(text: str) -> int:
            return len(text.split())

        pieces = block_inputs(block, prev, nxt, max_words=5, max_tokens=5, count_tokens=count_tokens)
        self.assertGreaterEqual(len(pieces), 3)
        for model_input, focus in pieces:
            self.assertLessEqual(len(model_input.split()), 5)
            self.assertLessEqual(count_tokens(model_input), 5)
            self.assertTrue(focus)
            self.assertTrue(all(tok.startswith("b") for tok in focus.split()))


class CaseIdTests(unittest.TestCase):
    def test_double_semicolon_form(self):
        parsed = parse_filename("abcd;;9-99-cv-00099_4_u0000_t0000.json")
        self.assertEqual(parsed["ucid"], "abcd;;9:99-cv-00099")
        self.assertEqual(parsed["court"], "abcd")
        self.assertEqual(parsed["document_number"], "4")

    def test_underscore_form(self):
        parsed = parse_filename("efgh_8-98-cv-00111_22_u0000.json")
        self.assertEqual(parsed["ucid"], "efgh;;8:98-cv-00111")
        self.assertEqual(parsed["court"], "efgh")
        self.assertEqual(parsed["document_number"], "22")

    def test_same_case_shares_ucid(self):
        a = parse_filename("abcd;;9-99-cv-00099_4_aaa.json")
        b = parse_filename("abcd;;9-99-cv-00099_5_bbb.json")
        self.assertEqual(a["ucid"], b["ucid"])
        self.assertNotEqual(a["document_number"], b["document_number"])

    def test_text_cross_check(self):
        self.assertEqual(cross_check("9:99-cv-00099", "No. 9:99-cv-00099"), "match")
        self.assertEqual(cross_check("9:99-cv-00099", "No. 8:98-cv-00111"), "mismatch")


class GateTests(unittest.TestCase):
    def test_person_agreement_keeps(self):
        self.assertEqual(gate_decision("judge", True, "Person", False), "keep")
        self.assertEqual(gate_decision("counsel", True, "Person", False), "keep")
        self.assertEqual(gate_decision("party", True, "Person", False), "keep")

    def test_disagreement_reviews(self):
        self.assertEqual(gate_decision("judge", True, "Unknown", False), "review")
        self.assertEqual(gate_decision("counsel", False, "Person", False), "review")

    def test_org_counsel_becomes_firm(self):
        self.assertEqual(gate_decision("counsel", False, "Corporation", True), "firm")

    def test_org_party_stays_party(self):
        self.assertEqual(gate_decision("party", False, "Corporation", True), "keep")

    def test_firm_stays(self):
        self.assertEqual(gate_decision("firm", False, "Unknown", False), "keep")


class OutputTests(unittest.TestCase):
    def test_mention_has_v4_fields_and_source(self):
        row = make_mention(
            raw_name="Example Name",
            entity_type="party",
            ucid="abcd;;9:99-cv-00099",
            court="abcd",
            role="plaintiff",
            side="plaintiff",
            email="",
            phone="",
            address="",
            firm="",
            page=1,
            bbox=[0, 0, 1, 1],
            block_confidence=0.8,
            model_score=0.7,
            source_text="Example Name, plaintiff",
            document_number="4",
            filename="abcd;;9-99-cv-00099_4.json",
            json_path="$.pages[1].blocks[0]",
        )
        for field in V4_FIELDS:
            self.assertIn(field, row)
        self.assertEqual(row["source"], "document")
        self.assertIsNone(row["entity_id"])
        assign_ids([row])
        self.assertEqual(row["mention_id"], "mnt_0")

    def test_files_written(self):
        row = make_mention(
            raw_name="Example Name",
            entity_type="judge",
            ucid="abcd;;9:99-cv-00099",
            court="abcd",
            role="judge",
            side="",
            email="",
            phone="",
            address="",
            firm="",
            page=1,
            bbox=None,
            block_confidence=0.9,
            model_score=0.9,
            source_text="Example Name",
            document_number="4",
            filename="f.json",
            json_path="$",
        )
        assign_ids([row])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_outputs(
                folder,
                [row],
                [],
                [{"file": "f.json", "kind": "ocr", "ucid": row["ucid"], "case_check": "match", "counts": {"judge": 1, "party": 0, "counsel": 0, "firm": 0}, "dropped": {"dropped_low_confidence": 0, "dropped_duplicate": 0, "confidence_threshold": 0.1}, "review_count": 0, "seconds": 0.01}],
                "unit-test",
            )
            line = json.loads((folder / "mentions.jsonl").read_text(encoding="utf-8").strip())
            self.assertEqual(line["entity_type"], "judge")
            self.assertEqual(line["source"], "document")
            csv_text = (folder / "review_docs.csv").read_text(encoding="utf-8")
            self.assertIn("correct?", csv_text.splitlines()[0])
            self.assertIn("source_text", csv_text)
            self.assertIn("Document reader report", (folder / "report.md").read_text(encoding="utf-8"))


class DetectTests(unittest.TestCase):
    def test_structure_not_name(self):
        ocr = {"filename": "x", "pages": [{"page": 1, "blocks": [{"text": "Hello", "confidence": 0.5, "bbox": [0, 0, 1, 1]}]}]}
        other = {"note": "a paragraph of text"}
        docket = {"ucid": "abcd;;9:99-cv-00099", "parties": [], "docket": []}
        self.assertEqual(detect_kind(ocr), "ocr")
        self.assertEqual(detect_kind(other), "generic")
        self.assertEqual(detect_kind(docket), "docket")


if __name__ == "__main__":
    unittest.main()
