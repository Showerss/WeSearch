#!/usr/bin/env python3
"""lab: model-agnostic enforcement for WeSearch. Needs only Python 3 and PyYAML."""
import argparse, fnmatch, glob, hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
CLAIMS = "research/claims/claims.yaml"
ASSUMP = "research/assumptions.yaml"
REVIEWS = "research/logs/reviews"
AUDIT = "research/logs/audit.jsonl"
VERDICTS = ("VERIFIED", "GAP", "UNSUPPORTED", "REFUTED")


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return yaml.safe_load(f) or default


def save(path, data):
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def audit(event, **kw):
    os.makedirs(os.path.dirname(AUDIT), exist_ok=True)
    with open(AUDIT, "a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **kw}) + "\n")


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def claims_doc():
    d = load(CLAIMS, {"claims": []})
    d.setdefault("claims", [])
    return d


def get_claim(cid):
    for c in claims_doc()["claims"]:
        if c["id"] == cid:
            return c
    die(f"no such claim: {cid}")


def ladder_for(claim, req):
    return req[claim["kind"]]["ladder"]


# ---------- model calls ----------

def call_model(role, system, user):
    cfg = load("lab.yaml", {})
    tier = cfg.get("roles", {}).get(role)
    if not tier:
        die(f"role '{role}' not mapped to a tier in lab.yaml")
    t = cfg["tiers"][tier]
    if t["model"] == "CHANGE_ME":
        die(f"tier '{tier}' in lab.yaml still has model: CHANGE_ME")
    key = os.environ.get(t["api_key_env"], "")
    if not key:
        die(f"set environment variable {t['api_key_env']}")
    body = json.dumps({
        "model": t["model"],
        "max_tokens": cfg.get("max_tokens", 4000),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode()
    req = urllib.request.Request(t["base_url"].rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)["choices"][0]["message"]["content"], t["model"]
    except urllib.error.HTTPError as e:
        die(f"model call failed: HTTP {e.code} {e.read()[:300]!r}")
    except Exception as e:
        die(f"model call failed: {e}")


def role_prompt(role):
    p = f"roles/{role}.md"
    if not os.path.exists(p):
        die(f"unknown role: {role}")
    return read("LAB.md") + "\n\n---\n\n" + read(p)


def cmd_run(a):
    # Trigger 0: the promised artifact must exist afterwards, or the run failed.
    text, model = call_model(a.role, role_prompt(a.role), a.task)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as f:
        f.write(text)
    ok = os.path.exists(a.out) and os.path.getsize(a.out) > 0
    audit("run", role=a.role, model=model, out=a.out, ok=ok)
    if not ok:
        die("FAILED: promised artifact missing or empty")
    print(f"wrote {a.out}")


# ---------- packets and reviews ----------

def build_packet(claim, hide_reasoning=True):
    assumptions = {x["id"]: x for x in (load(ASSUMP, {"assumptions": []}).get("assumptions") or [])}
    parts = [f"# Claim {claim['id']} ({claim['kind']}, status: {claim['status']})", claim["text"], "", "## Assumptions"]
    for aid in claim.get("assumptions", []):
        x = assumptions.get(aid, {"text": "MISSING FROM LEDGER", "status": "unknown"})
        parts.append(f"- {aid}: {x['text']} [{x.get('status', 'unverified')}]")
    parts.append("\n## Evidence files")
    for p in claim.get("evidence", []):
        if os.path.isdir(p):
            files = sorted(f for f in glob.glob(p + "/**", recursive=True) if os.path.isfile(f))
        else:
            files = [p]
        for f in files:
            if os.path.exists(f):
                parts.append(f"\n### {f}\n```\n{read(f)[:20000]}\n```")
            else:
                parts.append(f"\n### {f}\nMISSING")
    packet = "\n".join(parts)
    return packet, hashlib.sha256(packet.encode()).hexdigest()


def parse_verdict(text):
    m = re.search(r"verdict\W*[:\-]?\W*(VERIFIED|GAP|UNSUPPORTED|REFUTED)", text, re.I)
    return m.group(1).upper() if m else None


def latest_reviews(cid):
    out = {}
    for f in sorted(glob.glob(f"{REVIEWS}/{cid}/*.md")):
        head = read(f).split("---", 2)
        if len(head) < 3:
            continue
        meta = yaml.safe_load(head[1]) or {}
        out[meta["role"]] = {**meta, "file": f}
    return out


def cmd_review(a):
    claim = get_claim(a.claim)
    packet, h = build_packet(claim)
    os.makedirs("research/logs/packets", exist_ok=True)
    with open(f"research/logs/packets/{a.claim}-{h[:8]}.md", "w") as f:
        f.write(packet)
    text, model = call_model(a.role, role_prompt(a.role), packet)
    verdict = parse_verdict(text)
    if not verdict:
        verdict = "UNSUPPORTED"
        text += "\n\n[lab] No parseable verdict; recorded as UNSUPPORTED."
    d = f"{REVIEWS}/{a.claim}"
    os.makedirs(d, exist_ok=True)
    path = f"{d}/{time.strftime('%Y%m%d-%H%M%S')}-{a.role}.md"
    meta = {"role": a.role, "verdict": verdict, "packet_hash": h, "model": model, "claim_status": claim["status"]}
    with open(path, "w") as f:
        f.write("---\n" + yaml.safe_dump(meta) + "---\n" + text)
    audit("review", claim=a.claim, role=a.role, verdict=verdict, model=model)
    print(f"{a.role}: {verdict}  ({path})")


# ---------- claims ----------

def cmd_claim_add(a):
    req = load("gates/requirements.yaml")
    d = claims_doc()
    if any(c["id"] == a.id for c in d["claims"]):
        die("claim id exists")
    d["claims"].append({"id": a.id, "text": a.text, "kind": a.kind, "status": "idea", "rigor": a.rigor,
                        "novelty": a.novelty, "charter_item": a.charter, "assumptions": [], "evidence": []})
    save(CLAIMS, d)
    audit("claim_add", id=a.id)
    print(f"added {a.id} (status: idea; ladder: {' > '.join(req[a.kind]['ladder'])})")


def _edit_list(a, field):
    d = claims_doc()
    for c in d["claims"]:
        if c["id"] == a.claim:
            for v in a.values:
                if v not in c[field]:
                    c[field].append(v)
            save(CLAIMS, d)
            audit("claim_edit", id=a.claim, field=field, values=a.values)
            print("ok (existing reviews for this claim are now stale)")
            return
    die("no such claim")


def check_rung(claim, target, req, cfg_rigor):
    """Return a list of blocking problems for moving claim to `target`."""
    r = req[claim["kind"]]
    ladder = r["ladder"]
    problems = []
    cur = ladder.index(claim["status"])
    if target not in ladder:
        return [f"{target} is not on the {claim['kind']} ladder"]
    ti = ladder.index(target)
    if ti != cur + 1:
        problems.append(f"must move one rung at a time (now {claim['status']}, next is {ladder[min(cur + 1, len(ladder) - 1)]})")
    rigor = claim.get("rigor") or cfg_rigor
    if rigor == "solo" and ti > ladder.index(r["solo_max"]):
        problems.append(f"rigor 'solo' cannot pass {r['solo_max']}")
    need = r["requires"].get(target, {})
    reviewers = list(need.get("reviewers", []))
    if rigor == "full" and ti >= 2 and "adversarial-reviewer" not in reviewers:
        reviewers.append("adversarial-reviewer")
    if claim.get("novelty") and ti >= 2 and rigor != "solo" and req["novelty_reviewer"] not in reviewers:
        reviewers.append(req["novelty_reviewer"])
    _, h = build_packet(claim)
    reviews = latest_reviews(claim["id"])
    for role in reviewers:
        rv = reviews.get(role)
        if not rv:
            problems.append(f"no review by {role}")
        elif rv["packet_hash"] != h:
            problems.append(f"review by {role} is stale (claim, assumptions or evidence changed)")
        elif rv["verdict"] != "VERIFIED":
            problems.append(f"{role} verdict is {rv['verdict']}")
    for role, rv in reviews.items():
        if rv["packet_hash"] == h and rv["verdict"] != "VERIFIED":
            problems.append(f"open {rv['verdict']} from {role}: {rv['file']}")
    ev = claim.get("evidence", [])
    if need.get("needs_evidence") and not ev:
        problems.append("claim lists no evidence")
    for p in ev:
        if not os.path.exists(p):
            problems.append(f"evidence missing: {p}")
    for g in need.get("run_files", []):
        for p in ev:
            if p.startswith("research/runs/") and os.path.isdir(p) and not glob.glob(os.path.join(p, g)):
                problems.append(f"{p} lacks {g}")
    for g in need.get("evidence_glob", []):
        if not glob.glob(g.format(id=claim["id"])):
            problems.append(f"no file matches {g.format(id=claim['id'])}")
    anyg = [g.format(id=claim["id"]) for g in need.get("evidence_any_glob", [])]
    if anyg and not any(glob.glob(g) for g in anyg):
        problems.append("none of these exist: " + ", ".join(anyg))
    return problems


def cmd_promote(a):
    req = load("gates/requirements.yaml")
    cfg = load("lab.yaml", {})
    d = claims_doc()
    claim = next((c for c in d["claims"] if c["id"] == a.claim), None)
    if not claim:
        die("no such claim")
    problems = check_rung(claim, a.status, req, cfg.get("rigor", "lean"))
    if problems:
        audit("promote_refused", id=a.claim, to=a.status, problems=problems)
        print(f"REFUSED: {a.claim} stays '{claim['status']}'")
        for p in problems:
            print("  -", p)
        sys.exit(2)
    old = claim["status"]
    claim["status"] = a.status
    save(CLAIMS, d)
    os.makedirs("research/logs", exist_ok=True)
    with open("research/logs/decisions.md", "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {a.claim}: {old} -> {a.status}. {a.reason}\n")
    audit("promote", id=a.claim, old=old, new=a.status)
    print(f"{a.claim}: {old} -> {a.status}")


def cmd_status(a):
    d = claims_doc()
    if not d["claims"]:
        print("no claims yet")
    for c in d["claims"]:
        reviews = latest_reviews(c["id"])
        _, h = build_packet(c)
        rv = ", ".join(f"{r}:{v['verdict']}{'' if v['packet_hash'] == h else '(stale)'}" for r, v in reviews.items()) or "none"
        print(f"{c['id']:<12} {c['kind']:<9} {c['status']:<16} reviews: {rv}")


def cmd_impact(a):
    hit = [c["id"] for c in claims_doc()["claims"] if a.assumption in c.get("assumptions", [])]
    print(f"claims depending on {a.assumption}: " + (", ".join(hit) or "none"))
    if hit:
        print("their existing reviews are stale if the assumption text changed; re-run `lab review`.")


# ---------- citations ----------

DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>|)\]]+)", re.I)
ARXIV = re.compile(r"(?:arxiv[:\s/]*)(\d{4}\.\d{4,5})(?:v\d+)?", re.I)


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "WeSearch-lab/0.1 (mailto:none)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def check_doi(doi):
    doi = doi.rstrip(".,;")
    try:
        data = json.loads(http_json("https://api.crossref.org/works/" + urllib.parse.quote(doi)))
        return "OK", " ".join(data["message"].get("title", [""]))
    except urllib.error.HTTPError as e:
        return ("FAIL", "not found") if e.code == 404 else ("ERROR", f"HTTP {e.code}")
    except Exception as e:
        return "ERROR", str(e)


def check_arxiv(aid):
    try:
        xml = http_json(f"http://export.arxiv.org/api/query?id_list={aid}")
        m = re.search(r"<entry>.*?<title>(.*?)</title>", xml, re.S)
        return ("OK", re.sub(r"\s+", " ", m.group(1))) if m and "Error" not in m.group(1) else ("FAIL", "not found")
    except Exception as e:
        return "ERROR", str(e)


def cmd_cite_check(a):
    bad = 0
    for path in a.files:
        for n, line in enumerate(read(path).splitlines(), 1):
            if "UNVERIFIED" in line:
                continue
            ids = [("doi", m) for m in DOI.findall(line)] + [("arxiv", m) for m in ARXIV.findall(line)]
            if line.strip().startswith("|") and not ids and re.search(r"\d{4}", line) and "---" not in line and "Title" not in line:
                print(f"{path}:{n} NO-ID  entry has no DOI/arXiv id; mark UNVERIFIED or add one")
                bad += 1
            for kind, i in ids:
                st, info = check_doi(i) if kind == "doi" else check_arxiv(i)
                print(f"{path}:{n} {st:<5} {kind}:{i}  {info[:80]}")
                if st != "OK":
                    bad += 1
    audit("cite_check", files=a.files, problems=bad)
    if bad:
        die(f"{bad} citation problem(s). ERROR means the lookup failed (offline?), not that the citation is fake.", 3)
    print("all citations resolved (existence only; quotes still need a human or reviewer check)")


# ---------- drift ----------

def charter_keywords():
    if not os.path.exists("research/charter.md"):
        return []
    t = read("research/charter.md")
    part = t.split("KEYWORDS:", 1)[-1] if "KEYWORDS:" in t else ""
    return [l.strip("- ").strip().lower() for l in part.splitlines() if l.strip("- ").strip()]


def cmd_drift(a):
    kws = charter_keywords()
    ck = read("research/session-state/checkpoint.md") if os.path.exists("research/session-state/checkpoint.md") else ""
    field = lambda n: (re.search(rf"^{n}:(.*)$", ck, re.M | re.I) or [None, ""])[1].strip()
    task, item = field("Current task"), field("Charter item served")
    if not kws:
        print("UNKNOWN: charter has no KEYWORDS yet. Complete the charter first.")
        sys.exit(4)
    if not task:
        print("UNKNOWN: checkpoint has no 'Current task'.")
        sys.exit(4)
    hit = [k for k in kws if k in task.lower()]
    if not item or item.startswith("("):
        state = "DRIFTING" if not hit else "ADJACENT"
        why = "task names no charter item" + (f", keywords matched: {hit}" if hit else " and matches no charter keyword")
    elif hit:
        state, why = "ON-TRACK", f"keywords matched: {hit}"
    else:
        state, why = "ADJACENT", "names a charter item but no charter keyword appears in the task; check it is not a stretch"
    print(f"{state}: {why}\n(keyword heuristic; the Guide must still confirm in plain words)")
    audit("drift", state=state)
    sys.exit(0 if state == "ON-TRACK" else 5)


# ---------- draft check ----------

def cmd_draft_check(a):
    d = claims_doc()
    req = load("gates/requirements.yaml")
    by_id = {c["id"]: c for c in d["claims"]}
    strong = re.compile(r"\b(we prove|proves?|proved|we show that|solves?|guarantees?|state[- ]of[- ]the[- ]art|first to|outperforms?)\b", re.I)
    problems = []
    text = read(a.file)
    runs = set(os.listdir("research/runs")) if os.path.isdir("research/runs") else set()
    for n, line in enumerate(text.splitlines(), 1):
        if "TODO(evidence)" in line:
            problems.append(f"{n}: unresolved TODO(evidence)")
        has_num = re.search(r"(?<![\w\[:\-])\d+(\.\d+)?\s*(%|x|ms|s|fps|×)?(?![\w\]\-])", re.sub(r"\[(run|claim):[^\]]+\]", "", line))
        if has_num and not line.lstrip().startswith(("#", "```")) and not re.search(r"\[run:", line) and len(line) > 20:
            problems.append(f"{n}: contains a number but no [run:<id>] tag")
        for r in re.findall(r"\[run:([^\]]+)\]", line):
            if r not in runs:
                problems.append(f"{n}: run '{r}' not found in research/runs/")
        ids = re.findall(r"\[claim:([^\]]+)\]", line)
        for c in ids:
            if c not in by_id:
                problems.append(f"{n}: claim '{c}' not in ledger")
        if strong.search(line):
            if not ids:
                problems.append(f"{n}: strong wording without a [claim:<id>] tag")
            for c in ids:
                if c in by_id:
                    lad = ladder_for(by_id[c], req)
                    if lad.index(by_id[c]["status"]) < len(lad) - 1 and re.search(r"prove|guarantee|state[- ]of|first to|solves", line, re.I):
                        problems.append(f"{n}: wording exceeds status '{by_id[c]['status']}' of {c}")
        if re.match(r"\s*(!\[|Figure|Fig\.)", line) and "script:" not in line:
            problems.append(f"{n}: figure without 'script:<path>'")
    audit("draft_check", file=a.file, problems=len(problems))
    if problems:
        print("\n".join(problems))
        die(f"{len(problems)} problem(s)", 6)
    print("draft-check passed (mechanical checks only)")


# ---------- phase gates ----------

def cmd_gate(a):
    p, miss = a.phase, []
    t = read("research/charter.md") if os.path.exists("research/charter.md") else ""
    if p in ("charter", "protocol", "data", "analysis", "draft", "submission"):
        for need in ("Main question", "Hypotheses", "Out of scope"):
            sec = t.split(f"## {need}", 1)[-1].split("##", 1)[0] if f"## {need}" in t else ""
            if len(re.sub(r"\(.*?\)|[-*\s.:]|H1|Falsified if", "", sec)) < 10:
                miss.append(f"charter section '{need}' looks empty")
        if "Falsified if: ..." in t or "Falsified if:" not in t:
            miss.append("a hypothesis has no stated falsifier")
        if not charter_keywords():
            miss.append("charter has no KEYWORDS")
    if p in ("protocol", "data", "analysis", "draft", "submission") and not glob.glob("research/literature/*.md"):
        miss.append("no literature table in research/literature/")
    if p in ("analysis", "draft", "submission"):
        for c in claims_doc()["claims"]:
            _, h = build_packet(c)
            for role, rv in latest_reviews(c["id"]).items():
                if rv["packet_hash"] == h and rv["verdict"] != "VERIFIED":
                    miss.append(f"claim {c['id']}: open {rv['verdict']} from {role}")
    if p == "submission" and not os.path.exists("research/logs/decisions.md"):
        miss.append("no Integrity Officer decisions logged")
    audit("gate", phase=p, missing=len(miss))
    if miss:
        print(f"GATE '{p}' NOT PASSED")
        for m in miss:
            print("  -", m)
        print("Also required: reviewer verdicts per gates/phase-gates.md, and the user's own restatement to the Guide.")
        sys.exit(7)
    print(f"mechanical checks for '{p}' passed. Reviewer verdicts and the user's restatement are still required.")


def main():
    ap = argparse.ArgumentParser(prog="lab")
    s = ap.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("run", help="run a role; --out is the promised artifact")
    x.add_argument("role"); x.add_argument("task"); x.add_argument("--out", required=True); x.set_defaults(f=cmd_run)
    x = s.add_parser("review", help="send a claim packet to an independent reviewer")
    x.add_argument("claim"); x.add_argument("role"); x.set_defaults(f=cmd_review)
    c = s.add_parser("claim"); cs = c.add_subparsers(dest="sub", required=True)
    x = cs.add_parser("add"); x.add_argument("id"); x.add_argument("text")
    x.add_argument("--kind", choices=["formal", "empirical"], required=True)
    x.add_argument("--rigor", choices=["solo", "lean", "full"], default=None)
    x.add_argument("--novelty", action="store_true"); x.add_argument("--charter", required=True); x.set_defaults(f=cmd_claim_add)
    x = cs.add_parser("assume"); x.add_argument("claim"); x.add_argument("values", nargs="+"); x.set_defaults(f=lambda a: _edit_list(a, "assumptions"))
    x = cs.add_parser("evidence"); x.add_argument("claim"); x.add_argument("values", nargs="+"); x.set_defaults(f=lambda a: _edit_list(a, "evidence"))
    x = s.add_parser("promote"); x.add_argument("claim"); x.add_argument("status"); x.add_argument("--reason", required=True); x.set_defaults(f=cmd_promote)
    x = s.add_parser("status"); x.set_defaults(f=cmd_status)
    x = s.add_parser("impact"); x.add_argument("assumption"); x.set_defaults(f=cmd_impact)
    x = s.add_parser("cite-check"); x.add_argument("files", nargs="+"); x.set_defaults(f=cmd_cite_check)
    x = s.add_parser("drift"); x.set_defaults(f=cmd_drift)
    x = s.add_parser("draft-check"); x.add_argument("file"); x.set_defaults(f=cmd_draft_check)
    x = s.add_parser("gate"); x.add_argument("phase", choices=["charter", "protocol", "data", "analysis", "draft", "submission"]); x.set_defaults(f=cmd_gate)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
