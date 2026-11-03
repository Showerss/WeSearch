#!/usr/bin/env python3
"""End-to-end test of lab enforcement on a scratch copy, with a fake model server.
Run: python3 tests/test_lab.py"""
import http.server, json, os, shutil, subprocess, sys, tempfile, threading

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VERDICT = {"v": "Verdict: VERIFIED"}
REQUESTS = []


class H(http.server.BaseHTTPRequestHandler):
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
env = {**os.environ, "LAB_STRONG_KEY": "x", "LAB_STANDARD_KEY": "x", "LAB_REVIEWER_KEY": "x"}
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
shutil.rmtree(tmp)
print("ALL PASSED" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
