#!/usr/bin/env python3
"""lab: model-agnostic enforcement for WeSearch. Needs only Python 3 and PyYAML."""
import argparse, fnmatch, glob, hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, xml.etree.ElementTree as ET
import yaml

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
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


def handoff_path(path):
    resolved = os.path.realpath(path)
    if os.path.commonpath((ROOT, resolved)) != ROOT:
        die(f"handoff source must be inside the repository: {path}")
    if not os.path.isfile(resolved):
        die(f"handoff source is not a file: {path}")
    return resolved


def load_handoff(path, role, out):
    try:
        packet = yaml.safe_load(read(handoff_path(path)))
    except yaml.YAMLError as e:
        die(f"invalid handoff YAML: {e}")
    if not isinstance(packet, dict):
        die("handoff must be a YAML mapping")
    required = ("recipient", "charter_item", "charter_source", "decisions", "evidence", "task",
                "expected_output", "completion_test")
    missing = [key for key in required if key not in packet]
    if missing:
        die("handoff missing required fields: " + ", ".join(missing))
    if packet["recipient"] != role:
        die(f"handoff recipient is '{packet['recipient']}', not '{role}'")
    for key in ("charter_item", "charter_source", "task", "expected_output", "completion_test"):
        if not isinstance(packet[key], str) or not packet[key].strip():
            die(f"handoff field '{key}' must be a non-empty string")
    if os.path.normpath(packet["expected_output"]) != os.path.normpath(out):
        die("handoff expected_output must match the --out path")
    if not isinstance(packet["decisions"], list) or not packet["decisions"]:
        die("handoff 'decisions' must be a non-empty list")
    if not isinstance(packet["evidence"], list):
        die("handoff 'evidence' must be a list")
    phase = packet.get("phase")
    if phase is not None and (not isinstance(phase, str) or not phase.strip()):
        die("handoff field 'phase' must be a non-empty string if present")
    if not phase:
        phase = "scout" if packet["charter_item"].upper().startswith("SCOUT:") else "charter"
    packet["phase"] = phase
    sources = [("charter source", packet["charter_source"])]
    for i, decision in enumerate(packet["decisions"], 1):
        if not isinstance(decision, dict) or any(
                not isinstance(decision.get(k), str) or not decision[k].strip()
                for k in ("decision", "reason", "source")):
            die(f"decision {i} must include non-empty decision, reason, and source")
        sources.append(("decision source", decision["source"]))
    sources.extend(("evidence", p) for p in packet["evidence"])
    context = []
    for label, source in sources:
        if not isinstance(source, str) or not source.strip():
            die(f"{label} path must be a non-empty string")
        resolved = handoff_path(source)
        context.append((source, read(resolved)))
    return packet, context


def cmd_run(a):
    packet, context = load_handoff(a.handoff, a.role, a.out)
    sys_prompt = role_prompt(a.role)
    sections = [
        "Use only the explicit handoff below, this shared lab policy, and your role instructions. "
        "No prior agent conversations or unlisted files are provided.",
        f"Charter item: {packet['charter_item']}",
        "Decisions and rationale:\n" + "\n".join(
            f"- Decision: {d['decision']}\n  Reason: {d['reason']}\n  Source: {d['source']}"
            for d in packet["decisions"]),
        "Evidence sources:\n" + ("\n".join(f"- {p}" for p in packet["evidence"]) or "- None"),
    ]
    for source, contents in context:
        sections.append(f"## Explicit source: {source}\n{contents}")
    sections.extend((
        f"Task:\n{packet['task']}",
        f"Expected output: {packet['expected_output']}",
        f"Completion test:\n{packet['completion_test']}",
    ))
    task = "\n\n".join(sections)
    if getattr(a, "prepare", None):
        os.makedirs(os.path.dirname(a.prepare) or ".", exist_ok=True)
        with open(a.prepare, "w") as f:
            f.write(sys_prompt + "\n\n---\n\n" + task)
        print(f"prepared {a.prepare}")
        return
    if getattr(a, "record", False):
        model = "native-subagent"
    else:
        # Trigger 0: the promised artifact must exist afterwards, or the run failed.
        text, model = call_model(a.role, sys_prompt, task)
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w") as f:
            f.write(text)
    ok = os.path.exists(a.out) and os.path.getsize(a.out) > 0
    audit("run", role=a.role, model=model, out=a.out, ok=ok, handoff=a.handoff,
          phase=packet.get("phase", "charter"),
          charter_item=packet["charter_item"], decisions=packet["decisions"],
          evidence=packet["evidence"], task=packet["task"],
          expected_output=packet["expected_output"], completion_test=packet["completion_test"],
          handoff_sha256=hashlib.sha256(read(handoff_path(a.handoff)).encode()).hexdigest(),
          source_sha256={p: hashlib.sha256(contents.encode()).hexdigest()
                         for p, contents in context})
    if not ok:
        die("FAILED: promised artifact missing or empty")
    print(f"recorded {a.out}" if getattr(a, "record", False) else f"wrote {a.out}")


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
    if a.role in ("lab-lead", "guide", "pi", "postdoc"):
        die(f"role '{a.role}' cannot review claims; use an independent reviewer role")
    sys_prompt = role_prompt(a.role)
    claim = get_claim(a.claim)
    packet, h = build_packet(claim)
    os.makedirs("research/logs/packets", exist_ok=True)
    with open(f"research/logs/packets/{a.claim}-{h[:8]}.md", "w") as f:
        f.write(packet)
    if getattr(a, "prepare", None):
        os.makedirs(os.path.dirname(a.prepare) or ".", exist_ok=True)
        with open(a.prepare, "w") as f:
            f.write(sys_prompt + "\n\n---\n\n" + packet)
        print(f"prepared {a.prepare} (packet_hash: {h})")
        return
    if getattr(a, "from_file", None):
        if not os.path.isfile(a.from_file):
            die(f"review file not found: {a.from_file}")
        text, model = read(a.from_file), "native-subagent"
    else:
        text, model = call_model(a.role, sys_prompt, packet)
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
    ev_all = claim.get("evidence", [])
    cite_role = req.get("citation_reviewer")
    if cite_role and ti >= 2 and rigor != "solo" and any(p.startswith("research/literature/") for p in ev_all) \
            and cite_role not in reviewers:
        reviewers.append(cite_role)
    if need.get("prereg"):
        problems += prereg_problems()
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
    base = os.environ.get("LAB_CROSSREF_URL", "https://api.crossref.org/works").rstrip("/")
    try:
        data = json.loads(http_json(f"{base}/" + urllib.parse.quote(doi)))
        return "OK", " ".join(data["message"].get("title", [""]))
    except urllib.error.HTTPError as e:
        return ("FAIL", "not found") if e.code == 404 else ("ERROR", f"HTTP {e.code}")
    except Exception as e:
        return "ERROR", str(e)


def check_arxiv(aid):
    base = os.environ.get("LAB_ARXIV_URL", "http://export.arxiv.org/api/query")
    try:
        xml = http_json(f"{base}?id_list={aid}")
        m = re.search(r"<entry>.*?<title>(.*?)</title>", xml, re.S)
        return ("OK", re.sub(r"\s+", " ", m.group(1))) if m and "Error" not in m.group(1) else ("FAIL", "not found")
    except Exception as e:
        return "ERROR", str(e)


def search_arxiv(query, max_results=5):
    base = os.environ.get("LAB_ARXIV_URL", "http://export.arxiv.org/api/query")
    q = urllib.parse.quote(query)
    xml = http_json(f"{base}?search_query=all:{q}&start=0&max_results={max_results}")
    root = ET.fromstring(xml)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entries = root.findall("a:entry", ns) or root.findall("entry")
    out = []
    for e in entries:
        get_text = lambda tag: (e.findtext(f"a:{tag}", default="", namespaces=ns) or e.findtext(tag, default="")).strip()
        raw_id = get_text("id")
        m = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?$", raw_id)
        if not m:
            continue
        aid = m.group(1)
        title = re.sub(r"\s+", " ", get_text("title")).replace("|", "/")
        summary = re.sub(r"\s+", " ", get_text("summary")).replace("|", "/")
        pub = get_text("published")
        year = pub[:4] if len(pub) >= 4 else "unknown"
        authors = [
            (a.findtext("a:name", default="", namespaces=ns) or a.findtext("name", default="")).strip()
            for a in (e.findall("a:author", ns) or e.findall("author"))
        ]
        author_str = (", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")).replace("|", "/") or "Unknown"
        out.append({
            "title": title,
            "authors": author_str,
            "year": year,
            "venue": "arXiv",
            "peer_reviewed": "no (preprint)",
            "id": f"arxiv:{aid}",
            "abstract": summary[:280],
        })
    return out


def search_crossref(query, max_results=5):
    base = os.environ.get("LAB_CROSSREF_URL", "https://api.crossref.org/works").rstrip("/")
    q = urllib.parse.quote(query)
    data = json.loads(http_json(f"{base}?query={q}&rows={max_results}"))
    items = data.get("message", {}).get("items", [])
    out = []
    for it in items:
        doi = it.get("DOI", "").strip()
        if not doi:
            continue
        titles = it.get("title") or [""]
        title = re.sub(r"\s+", " ", titles[0] if titles else "").replace("|", "/")
        if not title:
            continue
        authors = []
        for a in it.get("author", []):
            fam = a.get("family") or a.get("name") or ""
            giv = a.get("given") or ""
            nm = f"{giv} {fam}".strip()
            if nm:
                authors.append(nm)
        author_str = (", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")).replace("|", "/") or "Unknown"
        year = "unknown"
        for k in ("published-print", "published-online", "issued", "created"):
            parts = (it.get(k) or {}).get("date-parts") or []
            if parts and parts[0]:
                year = str(parts[0][0])
                break
        venues = it.get("container-title") or []
        venue = (venues[0] if venues else it.get("publisher") or "CrossRef").replace("|", "/")
        raw_abs = re.sub(r"<[^>]+>", " ", it.get("abstract") or "")
        summary = re.sub(r"\s+", " ", raw_abs).strip().replace("|", "/")[:280] or "(no abstract in CrossRef metadata)"
        out.append({
            "title": title,
            "authors": author_str,
            "year": year,
            "venue": venue,
            "peer_reviewed": "yes",
            "id": f"doi:{doi}",
            "abstract": summary,
        })
    return out


def cmd_lit_search(a):
    half = max(1, (a.max + 1) // 2)
    results, errors = [], []
    try:
        results.extend(search_arxiv(a.query, half))
    except Exception as e:
        errors.append(f"arXiv search failed: {e}")
    try:
        results.extend(search_crossref(a.query, max(1, a.max - len(results))))
    except Exception as e:
        errors.append(f"CrossRef search failed: {e}")
    results = results[:a.max]
    if not results and errors:
        die("; ".join(errors), 3)
    if a.out and a.out.endswith(".json"):
        text = json.dumps({"query": a.query, "results": results, "errors": errors}, indent=2) + "\n"
    else:
        lines = [
            f"# Literature search: {a.query}",
            f"Query: `{a.query}` | Date: {time.strftime('%Y-%m-%d')} | Hits: {len(results)}",
            "",
            "| Title | Authors | Year | Venue | Peer-reviewed? | DOI/arXiv | Abstract excerpt |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in results:
            lines.append(f"| {r['title']} | {r['authors']} | {r['year']} | {r['venue']} | {r['peer_reviewed']} | {r['id']} | {r['abstract']} |")
        text = "\n".join(lines) + "\n"
    if a.out:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        with open(a.out, "w") as f:
            f.write(text)
    print(text, end="")
    audit("lit_search", query=a.query, hits=len(results), out=a.out)


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
    task, item, phase = field("Current task"), field("Charter item served"), field("Current phase")
    is_scout = phase.lower() == "scout" or item.upper().startswith("SCOUT:")
    if is_scout and not kws:
        topic = item.split(":", 1)[1].strip() if ":" in item else phase
        kws = [w.lower() for w in re.split(r"[\s_\-]+", topic) if len(w) >= 2]
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
    elif hit or (is_scout and item.upper().startswith("SCOUT:")):
        state, why = "ON-TRACK", (f"keywords matched: {hit}" if hit else f"scouting active for {item}")
    else:
        state, why = "ADJACENT", "names a charter item but no charter keyword appears in the task; check it is not a stretch"
    print(f"{state}: {why}\n(keyword heuristic; the Lab Lead must still confirm in plain words)")
    audit("drift", state=state, phase="scout" if is_scout else "charter")
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


# ---------- report check ----------

REPORT_SECTIONS = (
    "## 1. Mental Model",
    "## 2. What Has Already Been Done",
    "## 3. Where the Holes Are",
    "## 4. Original Research Ideas & DIY Kill-Tests",
    "## 5. Active Learning Check-In",
)


def _known_literature_ids():
    known = set()
    for p in glob.glob("research/literature/*.md"):
        for line in read(p).splitlines():
            if "UNVERIFIED" in line:
                continue
            for m in DOI.findall(line):
                known.add(("doi", m.rstrip(".,;")))
            for m in ARXIV.findall(line):
                known.add(("arxiv", m))
    return known


def cmd_report_check(a):
    if not os.path.isfile(a.file):
        die(f"report file not found: {a.file}", 8)
    text = read(a.file)
    problems = []
    for sec in REPORT_SECTIONS:
        if sec not in text:
            problems.append(f"missing required section: '{sec}'")
    if "## 1. Mental Model" in text:
        sec1 = text.split("## 1. Mental Model", 1)[1].split("\n## 2.", 1)[0]
        if "```" not in sec1:
            problems.append("Section 1 ('## 1. Mental Model') is missing a diagram code block (```mermaid or ASCII ```)")
    if "### Jargon Decoder" not in text:
        problems.append("missing required '### Jargon Decoder' table in Section 2")
    else:
        jd_part = text.split("### Jargon Decoder", 1)[1]
        jd_lines = []
        in_table = False
        for line in jd_part.splitlines():
            s = line.strip()
            if s.startswith("|"):
                in_table = True
                jd_lines.append(s)
            elif in_table and not s:
                break
            elif in_table and s.startswith("#"):
                break
        terms = []
        for row in jd_lines:
            cols = [c.strip().strip("*_`") for c in row.strip("|").split("|")]
            if not cols or not cols[0]:
                continue
            first = cols[0]
            if re.match(r"^[-:\s]+$", first) or first.lower() in ("term", "academic term", "jargon", "jargon term"):
                continue
            terms.append(first)
        if not terms:
            problems.append("'### Jargon Decoder' table has no decoded term rows")
        glossary = read("research/glossary.md").lower() if os.path.exists("research/glossary.md") else ""
        for term in terms:
            if term.lower() not in glossary:
                problems.append(f"decoded term '{term}' is missing from research/glossary.md")
    if not re.search(r"\b(VERIFIED|INFERRED|UNKNOWN)\b", text):
        problems.append("report contains no certainty labels (VERIFIED, INFERRED, UNKNOWN)")
    known_ids = _known_literature_ids()
    cited_count = 0
    for n, line in enumerate(text.splitlines(), 1):
        if "UNVERIFIED" in line:
            continue
        ids = [("doi", m.rstrip(".,;")) for m in DOI.findall(line)] + [("arxiv", m) for m in ARXIV.findall(line)]
        for kind, ident in ids:
            cited_count += 1
            if (kind, ident) in known_ids:
                continue
            st, info = check_doi(ident) if kind == "doi" else check_arxiv(ident)
            if st != "OK":
                problems.append(f"line {n}: unverified citation {kind}:{ident} ({st}: {info})")
    if cited_count == 0:
        problems.append("report contains no verified citations (doi:... or arxiv:...)")
    audit("report_check", file=a.file, problems=len(problems))
    if problems:
        for p in problems:
            print(f"{a.file}: {p}")
        die(f"{len(problems)} report problem(s)", 8)
    print("report-check passed")


# ---------- preregistration ----------

PREREG = "research/prereg.lock.yaml"
PREREG_FILES = ["research/protocol.md", "research/lit-protocol.md"]
PROTOCOL_SECTIONS = ["Hypotheses under test", "Datasets and provenance", "Methods and baselines", "Metrics",
                     "Seeds, compute and budget", "Statistical analysis plan", "Stopping rules and exclusions",
                     "Threats to validity", "Negative-result plan", "Ethics, licensing and responsible use",
                     "Reproducibility and artifacts"]
LIT_SECTIONS = ["Research questions for the review", "Sources", "Search strings", "Inclusion criteria",
                "Exclusion criteria", "Snowballing", "Contradicting evidence", "Quality and recency"]


def sha(path):
    return hashlib.sha256(read(path).encode()).hexdigest()


def section_problems(path, sections):
    if not os.path.exists(path):
        return [f"{path} does not exist"]
    t, out = read(path), []
    for s in sections:
        body = t.split(f"## {s}", 1)[1].split("\n## ", 1)[0] if f"## {s}" in t else None
        if body is None:
            out.append(f"{path}: missing section '{s}'")
        elif len(re.sub(r"\(.*?\)|\s", "", body, flags=re.S)) < 20:
            out.append(f"{path}: section '{s}' is empty or still a placeholder")
    return out


def git_head():
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "no-git"


def prereg_problems():
    lock = load(PREREG)
    if not lock:
        return ["protocol not frozen: run `scripts/lab prereg`"]
    return [f"{p} changed since freeze (amend with `lab prereg --amend`)" for p, h in lock["files"].items()
            if not os.path.exists(p) or sha(p) != h]


def cmd_prereg(a):
    lock = load(PREREG)
    if a.amend:
        if not lock:
            die("nothing to amend: not frozen yet")
        changed = {p: (lock["files"][p], sha(p)) for p in lock["files"] if sha(p) != lock["files"][p]}
        if not changed:
            die("no file differs from the frozen version")
        with open("research/amendments.md", "a") as f:
            f.write(f"\n## {time.strftime('%Y-%m-%d %H:%M')} (commit {git_head()[:8]})\nReason: {a.amend}\n")
            for p, (o, n) in changed.items():
                f.write(f"- {p}: {o[:12]} -> {n[:12]}\n")
        lock["files"].update({p: n for p, (o, n) in changed.items()})
        lock.setdefault("amendments", []).append({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "reason": a.amend})
        save(PREREG, lock)
        audit("prereg_amend", reason=a.amend)
        print("amended; reviewers must re-check claims that depend on the protocol")
        return
    if a.check:
        probs = prereg_problems()
        print("\n".join(probs) or "protocol frozen and unchanged")
        sys.exit(1 if probs else 0)
    if lock:
        die("already frozen. Use --amend to record a deviation.")
    probs = section_problems(PREREG_FILES[0], PROTOCOL_SECTIONS) + section_problems(PREREG_FILES[1], LIT_SECTIONS)
    if probs:
        print("REFUSED: protocol is incomplete")
        print("\n".join("  - " + p for p in probs))
        sys.exit(2)
    save(PREREG, {"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "git_commit": git_head(),
                  "files": {p: sha(p) for p in PREREG_FILES}})
    audit("prereg_freeze")
    print(f"frozen {', '.join(PREREG_FILES)}. Commit {PREREG} so the timestamp is in git history.")


# ---------- phase gates ----------

def _nonempty_file(path):
    return os.path.isfile(path) and os.path.getsize(path) > 0


def cmd_gate(a):
    p, miss = a.phase, []
    t = read("research/charter.md") if os.path.exists("research/charter.md") else ""
    if p == "scout":
        topic = getattr(a, "topic", None)
        if not topic:
            miss.append("phase 'scout' requires --topic <topic>")
        else:
            lit = f"research/literature/{topic}.md"
            if not _nonempty_file(lit):
                miss.append(f"missing or empty literature file: {lit}")
            pathways = [f"research/pathways-{topic}.md", "research/pathways.md"]
            if not any(_nonempty_file(x) for x in pathways):
                miss.append("missing or empty pathways file: research/pathways.md")
            reviews = [f"research/logs/pathway-review-{topic}.md", "research/logs/pathway-review.md"]
            if not any(_nonempty_file(x) for x in reviews):
                miss.append("missing or empty pathway review: research/logs/pathway-review.md")
            rep = f"research/reports/{topic}.md"
            if not _nonempty_file(rep):
                miss.append(f"missing or empty synthesized report: {rep}")
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
    if p in ("protocol", "data", "analysis", "draft", "submission"):
        miss += section_problems(PREREG_FILES[1], LIT_SECTIONS)
        if p != "protocol" or os.path.exists(PREREG):
            miss += prereg_problems()
        else:
            miss += section_problems(PREREG_FILES[0], PROTOCOL_SECTIONS) + ["protocol not frozen: run `scripts/lab prereg`"]
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
    x = s.add_parser("run", help="run a role using an explicit handoff packet")
    x.add_argument("role"); x.add_argument("--handoff", required=True)
    x.add_argument("--out", required=True)
    g = x.add_mutually_exclusive_group()
    g.add_argument("--prepare", metavar="PROMPT_FILE", help="write context-isolated prompt for a native subagent without calling HTTP API")
    g.add_argument("--record", action="store_true", help="verify and record output produced by a native subagent")
    x.set_defaults(f=cmd_run)
    x = s.add_parser("review", help="send a claim packet to an independent reviewer")
    x.add_argument("claim"); x.add_argument("role")
    g = x.add_mutually_exclusive_group()
    g.add_argument("--prepare", metavar="PACKET_FILE", help="write blind review packet for a native reviewer subagent")
    g.add_argument("--from-file", dest="from_file", metavar="REVIEW_FILE", help="record review verdict from a native reviewer subagent output file")
    x.set_defaults(f=cmd_review)
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
    x = s.add_parser("lit-search", help="query arXiv and CrossRef for verifiable papers")
    x.add_argument("query"); x.add_argument("--max", type=int, default=10)
    x.add_argument("--out", default=None, help="optional output path (.md or .json)"); x.set_defaults(f=cmd_lit_search)
    x = s.add_parser("drift"); x.set_defaults(f=cmd_drift)
    x = s.add_parser("draft-check"); x.add_argument("file"); x.set_defaults(f=cmd_draft_check)
    x = s.add_parser("report-check", help="validate a 5-part ELI5 + Jargon Decoder research report")
    x.add_argument("file"); x.set_defaults(f=cmd_report_check)
    x = s.add_parser("prereg", help="freeze (hash + timestamp) the protocol before any run")
    x.add_argument("--amend", metavar="REASON"); x.add_argument("--check", action="store_true"); x.set_defaults(f=cmd_prereg)
    x = s.add_parser("gate"); x.add_argument("phase", choices=["scout", "charter", "protocol", "data", "analysis", "draft", "submission"])
    x.add_argument("--topic", default=None, help="scouting topic name for phase 'scout'"); x.set_defaults(f=cmd_gate)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
