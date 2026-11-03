#!/usr/bin/env python3
"""End-to-end test of lab enforcement on a scratch copy, with a fake model server.
Run: python3 tests/test_lab.py"""
import http.server, json, os, shutil, subprocess, sys, tempfile, threading

SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VERDICT = {"v": "Verdict: VERIFIED"}


class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
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
lab("drift", expect=4)  # empty charter must not report on-track
lab("gate", "charter", expect=7)
shutil.rmtree(tmp)
print("ALL PASSED" if not fails else f"FAILED: {fails}")
sys.exit(1 if fails else 0)
