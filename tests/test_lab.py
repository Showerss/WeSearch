#!/usr/bin/env python3
"""End-to-end test of lab enforcement on a scratch copy, with a fake model server.
Run: python3 tests/test_lab.py"""
import http.server, json, os, shutil, subprocess, sys, tempfile, threading

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VERDICT = {"v": "Verdict: VERIFIED"}
REQUESTS = []


class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if "/arxiv" in self.path:
            if "id_list=9999.99999" in self.path:
                xml = "<feed xmlns='http://www.w3.org/2005/Atom'></feed>"
            else:
                xml = (
                    "<feed xmlns='http://www.w3.org/2005/Atom'><entry>"
                    "<id>http://arxiv.org/abs/2305.12345v1</id>"
                    "<published>2023-05-20T00:00:00Z</published>"
                    "<title>Test-Time Scaling Laws</title>"
                    "<summary>We study test-time compute scaling.</summary>"
                    "<author><name>Alice Smith</name></author>"
                    "</entry></feed>"
                )
            self.send_response(200); self.send_header("Content-Type", "application/atom+xml"); self.end_headers(); self.wfile.write(xml.encode())
        elif "/crossref" in self.path:
            if "10.9999/bad" in self.path:
                self.send_response(404); self.end_headers(); return
            if "?query=" in self.path:
                body = json.dumps({"message": {"items": [{
                    "DOI": "10.1038/s41586-023-00001-1",
                    "title": ["Verifier Guided Search"],
                    "author": [{"given": "Bob", "family": "Jones"}],
                    "published-print": {"date-parts": [[2023]]},
                    "container-title": ["Nature"],
                    "abstract": "<jats:p>Verifier search improves accuracy.</jats:p>",
                }]}}).encode()
            else:
                body = json.dumps({"message": {"title": ["Verifier Guided Search"]}}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        REQUESTS.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        body = json.dumps({"choices": [{"message": {"content": VERDICT["v"] + "\n1. nothing"}}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    def log_message(self, *a): pass


srv = http.server.HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
tmp = tempfile.mkdtemp()
work = os.path.join(tmp, "w")
shutil.copytree(SRC, work, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"))
cfg = open(f"{work}/lab.yaml").read().replace("https://api.openai.com/v1", f"http://127.0.0.1:{srv.server_port}").replace("CHANGE_ME", "fake")
open(f"{work}/lab.yaml", "w").write(cfg)
env = {
    **os.environ,
    "LAB_STRONG_KEY": "x",
    "LAB_STANDARD_KEY": "x",
    "LAB_REVIEWER_KEY": "x",
    "LAB_ARXIV_URL": f"http://127.0.0.1:{srv.server_port}/arxiv",
    "LAB_CROSSREF_URL": f"http://127.0.0.1:{srv.server_port}/crossref",
}
fails = []


def lab(*args, expect=0):
    r = subprocess.run([sys.executable, f"{work}/scripts/lab.py", *args], capture_output=True, text=True, env=env)
    ok = r.returncode == expect
    print(("PASS" if ok else "FAIL"), " ".join(args)[:70], "->", r.returncode)
    if not ok:
        fails.append(" ".join(args)); print(r.stdout, r.stderr)
    return r.stdout + r.stderr


lab("claim", "add", "T1", "Sorting runs in O(n log n).", "--kind", "formal", "--charter", "H1")
lab("promote", "T1", "derived", "--reason", "skip", expect=2)  # one rung at a time
# Explicit handoff contains the only role-specific source files sent to the model.
os.makedirs(f"{work}/research/handoffs", exist_ok=True)
os.makedirs(f"{work}/research/decisions", exist_ok=True)
open(f"{work}/research/decisions/h1.md", "w").write("PI decision: search prior work.")
open(f"{work}/research/evidence.md", "w").write("Evidence: charter supports H1.")
open(f"{work}/research/unlisted.md", "w").write("DO NOT SEND THIS")
handoff = {
    "recipient": "literature-scout",
    "charter_item": "H1",
    "charter_source": "research/charter.md",
    "decisions": [{"decision": "Search prior work.", "reason": "Establish novelty.", "source": "research/decisions/h1.md"}],
    "evidence": ["research/evidence.md"],
    "task": "Find closely related research.",
    "expected_output": "research/literature/h1.md",
    "completion_test": "List sources and unresolved questions.",
}
handoff_path = f"{work}/research/handoffs/h1.yaml"
open(handoff_path, "w").write(json.dumps(handoff))
lab("run", "literature-scout", "--handoff", "research/handoffs/h1.yaml", "--out", "research/literature/h1.md")
sent = REQUESTS[-1]["messages"][1]["content"]
assert "PI decision: search prior work." in sent and "Evidence: charter supports H1." in sent, sent
assert "DO NOT SEND THIS" not in sent and "prior agent conversations" in sent, sent
audit_events = [json.loads(line) for line in open(f"{work}/research/logs/audit.jsonl")]
run_event = next(e for e in reversed(audit_events) if e["event"] == "run")
assert run_event["charter_item"] == "H1" and run_event["task"] == handoff["task"], run_event
assert "research/decisions/h1.md" in run_event["source_sha256"], run_event
handoff["recipient"] = "writer"
open(handoff_path, "w").write(json.dumps(handoff))
before = len(REQUESTS)
lab("run", "literature-scout", "--handoff", "research/handoffs/h1.yaml", "--out", "research/literature/h1.md", expect=1)
assert len(REQUESTS) == before, "invalid handoff reached model"
handoff["recipient"] = "literature-scout"
handoff["evidence"] = [os.path.join(tmp, "outside.md")]
open(handoff_path, "w").write(json.dumps(handoff))
open(os.path.join(tmp, "outside.md"), "w").write("outside repo")
lab("run", "literature-scout", "--handoff", "research/handoffs/h1.yaml", "--out", "research/literature/h1.md", expect=1)
assert len(REQUESTS) == before, "outside-repository source reached model"
lab("promote", "T1", "conjecture", "--reason", "stated")
lab("promote", "T1", "sketch", "--reason", "no review", expect=2)  # needs reviewer
lab("review", "T1", "adversarial-reviewer")
lab("promote", "T1", "sketch", "--reason", "reviewed")
os.makedirs(f"{work}/research/claims/T1")
open(f"{work}/research/claims/T1/proof.md", "w").write("proof")
lab("claim", "evidence", "T1", "research/claims/T1/proof.md")
out = lab("promote", "T1", "derived", "--reason", "x", expect=2)  # stale + missing proofauditor
assert "stale" in out and "proof-auditor" in out, out
lab("review", "T1", "proof-auditor"); lab("review", "T1", "adversarial-reviewer")
lab("promote", "T1", "derived", "--reason", "audited")
VERDICT["v"] = "Verdict: GAP"
lab("review", "T1", "adversarial-reviewer")
out = lab("promote", "T1", "machine-checked", "--reason", "x", expect=2)
assert "GAP" in out, out
VERDICT["v"] = "Verdict: VERIFIED"
lab("claim", "add", "E1", "Method beats baseline.", "--kind", "empirical", "--charter", "H1")
lab("promote", "E1", "observation", "--reason", "x", expect=2)  # needs evidence
open(f"{work}/d.md", "w").write("We achieve 93.4% accuracy.\nWe prove optimality [claim:T1].\n")
out = lab("draft-check", "d.md", expect=6)
assert "no [run:" in out and "exceeds status" in out, out
# preregistration
lab("prereg", expect=2)  # template placeholders must be refused
lab("prereg", "--check", expect=1)
lab("claim", "add", "E2", "Run works.", "--kind", "empirical", "--charter", "H1", "--rigor", "lean")
lab("claim", "evidence", "E2", "d.md")
lab("promote", "E2", "observation", "--reason", "x")
out = lab("promote", "E2", "single-run", "--reason", "x", expect=2)
assert "not frozen" in out, out
for f, secs in (("protocol.md", "Hypotheses under test|Datasets and provenance|Methods and baselines|Metrics|Seeds, compute and budget|Statistical analysis plan|Stopping rules and exclusions|Threats to validity|Negative-result plan|Ethics, licensing and responsible use|Reproducibility and artifacts"),
                ("lit-protocol.md", "Research questions for the review|Sources|Search strings|Inclusion criteria|Exclusion criteria|Snowballing|Contradicting evidence|Quality and recency")):
    open(f"{work}/research/{f}", "w").write("# T\n" + "".join(f"\n## {s}\nConcrete filled in text for this section.\n" for s in secs.split("|")))
lab("prereg")
lab("prereg", expect=1)  # already frozen
lab("prereg", "--check")
open(f"{work}/research/protocol.md", "a").write("\nextra change\n")
lab("prereg", "--check", expect=1)
lab("prereg", "--amend", "added note")
lab("prereg", "--check")
# citation auditor required when evidence is a literature file
os.makedirs(f"{work}/research/literature", exist_ok=True)
open(f"{work}/research/literature/t.md", "w").write("| Title | UNVERIFIED |\n")
lab("claim", "add", "L1", "Prior work shows X.", "--kind", "formal", "--charter", "H1")
lab("claim", "evidence", "L1", "research/literature/t.md")
lab("promote", "L1", "conjecture", "--reason", "x")
lab("review", "L1", "adversarial-reviewer")
out = lab("promote", "L1", "sketch", "--reason", "x", expect=2)
assert "citation-auditor" in out, out
lab("review", "L1", "citation-auditor")
lab("promote", "L1", "sketch", "--reason", "x")
lab("drift", expect=4)  # empty charter must not report on-track
lab("gate", "charter", expect=7)
# Phase 0 (scout) handoffs, drift, and gate before charter is filled
os.makedirs(f"{work}/research/reports", exist_ok=True)
open(f"{work}/research/reports/scaling-brief.md", "w").write("# Scouting Brief: scaling\nExplore test-time scaling.")
scout_handoff = {
    "recipient": "literature-scout",
    "phase": "scout",
    "charter_item": "SCOUT:scaling",
    "charter_source": "research/reports/scaling-brief.md",
    "decisions": [{"decision": "Scout test-time scaling.", "reason": "Pre-charter exploration.", "source": "research/reports/scaling-brief.md"}],
    "evidence": [],
    "task": "Scout papers on test-time scaling.",
    "expected_output": "research/literature/scaling.md",
    "completion_test": "Non-empty literature table.",
}
open(f"{work}/research/handoffs/scout-scaling.yaml", "w").write(json.dumps(scout_handoff))
lab("run", "literature-scout", "--handoff", "research/handoffs/scout-scaling.yaml", "--out", "research/literature/scaling.md")
audit_events = [json.loads(line) for line in open(f"{work}/research/logs/audit.jsonl")]
scout_run = next(e for e in reversed(audit_events) if e["event"] == "run")
assert scout_run["phase"] == "scout" and scout_run["charter_item"] == "SCOUT:scaling", scout_run
open(f"{work}/research/session-state/checkpoint.md", "w").write(
    "# Checkpoint\nCurrent phase: scout\nCurrent task: Scouting scaling literature\nCharter item served: SCOUT:scaling\n"
)
lab("drift", expect=0)
lab("gate", "scout", "--topic", "scaling", expect=7)  # missing pathways/review/report
open(f"{work}/research/pathways.md", "w").write("# Pathways\n1. Pathway A")
open(f"{work}/research/logs/pathway-review.md", "w").write("Verdict: PURSUE")
open(f"{work}/research/reports/scaling.md", "w").write("# Report: scaling\nSynthesized findings.")
lab("gate", "scout", "--topic", "scaling", expect=0)
# Native subagent --prepare and --record / --from-file flows (no HTTP calls)
before_native = len(REQUESTS)
scout_handoff["expected_output"] = "research/literature/native-scout.md"
open(f"{work}/research/handoffs/native-scout.yaml", "w").write(json.dumps(scout_handoff))
lab("run", "literature-scout", "--handoff", "research/handoffs/native-scout.yaml",
    "--out", "research/literature/native-scout.md", "--prepare", "research/logs/packets/native-prompt.md")
assert len(REQUESTS) == before_native, "prepare should not call HTTP"
prepared_prompt = open(f"{work}/research/logs/packets/native-prompt.md").read()
assert "DO NOT SEND THIS" not in prepared_prompt and "Scouting Brief: scaling" in prepared_prompt, prepared_prompt
lab("run", "literature-scout", "--handoff", "research/handoffs/native-scout.yaml",
    "--out", "research/literature/native-scout.md", "--record", expect=1)  # missing output file fails
open(f"{work}/research/literature/native-scout.md", "w").write("| Paper | arxiv:2301.00001 |\n")
lab("run", "literature-scout", "--handoff", "research/handoffs/native-scout.yaml",
    "--out", "research/literature/native-scout.md", "--record")
assert len(REQUESTS) == before_native, "record should not call HTTP"
audit_events = [json.loads(line) for line in open(f"{work}/research/logs/audit.jsonl")]
native_run = next(e for e in reversed(audit_events) if e["event"] == "run")
assert native_run["model"] == "native-subagent" and native_run["out"] == "research/literature/native-scout.md", native_run
# Reject self-review by lab-lead
lab("review", "L1", "lab-lead", expect=1)
lab("claim", "add", "N1", "Native claim.", "--kind", "formal", "--charter", "H1")
lab("promote", "N1", "conjecture", "--reason", "stated")
lab("review", "N1", "adversarial-reviewer", "--prepare", "research/logs/packets/n1-review-packet.md")
assert len(REQUESTS) == before_native, "review --prepare should not call HTTP"
review_pkt = open(f"{work}/research/logs/packets/n1-review-packet.md").read()
assert "Native claim." in review_pkt and "DO NOT SEND THIS" not in review_pkt, review_pkt
open(f"{work}/research/logs/packets/n1-verdict.md", "w").write("Defects: none.\nVerdict: VERIFIED\n")
lab("review", "N1", "adversarial-reviewer", "--from-file", "research/logs/packets/n1-verdict.md")
assert len(REQUESTS) == before_native, "review --from-file should not call HTTP"
lab("promote", "N1", "sketch", "--reason", "reviewed by native subagent")
# lit-search and cite-check with local mock endpoints
lit_out = lab("lit-search", "test-time scaling", "--max", "4", "--out", "research/literature/search-results.md")
assert "arxiv:2305.12345" in lit_out and "doi:10.1038/s41586-023-00001-1" in lit_out, lit_out
lab("cite-check", "research/literature/search-results.md", expect=0)
# report-check: missing sections, missing glossary term, unverified citation, and passing report
bad_report = f"{work}/research/reports/bad.md"
open(bad_report, "w").write("# Incomplete Report\n## 1. Mental Model\nNo diagram or other sections.\n")
rep_err = lab("report-check", "research/reports/bad.md", expect=8)
assert "missing required section" in rep_err and "missing a diagram" in rep_err, rep_err
good_report = f"{work}/research/reports/scaling.md"
report_body = """# Research Report: scaling

## 1. Mental Model (Explain Like I'm 5)
Thinking longer helps solve harder puzzles [VERIFIED].
```mermaid
flowchart LR
  A["Prompt"] --> B["Verifier Search"]
```

## 2. What Has Already Been Done
Prior work studies scaling (`arxiv:2305.12345` and `doi:10.1038/s41586-023-00001-1`) [VERIFIED].

### Jargon Decoder
| Academic Term | Plain-English Meaning | Everyday Analogy |
|---|---|---|
| Process Reward Model | Step-by-step grader | Math teacher checking each line |

## 3. Where the Holes Are (Reviewer Critique)
Verifiers fail on out-of-distribution steps [INFERRED].

## 4. Original Research Ideas & DIY Kill-Tests
1. **Pathway 1:** Test verifier calibration [INFERRED].

## 5. Active Learning Check-In
Your turn: restate why step-by-step grading fails [UNKNOWN].
"""
open(good_report, "w").write(report_body)
# Fails before glossary has "Process Reward Model"
rep_glossary_err = lab("report-check", "research/reports/scaling.md", expect=8)
assert "Process Reward Model" in rep_glossary_err, rep_glossary_err
open(f"{work}/research/glossary.md", "a").write("| Process Reward Model | Step-by-step grader | Math teacher |\n")
lab("report-check", "research/reports/scaling.md", expect=0)
# Fails if an unverified citation is added without UNVERIFIED tag
open(good_report, "w").write(report_body + "\nBad ref: doi:10.9999/bad\n")
rep_cite_err = lab("report-check", "research/reports/scaling.md", expect=8)
assert "10.9999/bad" in rep_cite_err, rep_cite_err
shutil.rmtree(tmp)
print("ALL PASSED" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
