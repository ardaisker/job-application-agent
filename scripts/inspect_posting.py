"""Read a posting before deciding: description, red flags and the form's questions.

  inspect_posting.py ats:slug:id [ats:slug:id ...] [--chars 1800]
  inspect_posting.py --from runs/scan-XXXX.json [--chars 1800]   (all postings of a scan file)

Prints, per posting: title, location, pay (if public), the requirements part of the text, flagged sentences
(years of experience, visa/right to work, required languages, attestations such as "no AI help", salary,
clearance, relocation) and the application questions (* = required). Saves the full result to
runs/inspect/<ats>-<slug>-<id>.json so answers can be drafted from it.
"""
import concurrent.futures as cf
import json
import re
import sys

from boards import country
from common import RUNS, clean, get, load_json, load_profile, rx

STD = re.compile(r"^(first name|last name|name|full name|legal name|preferred (first )?name|email|phone|resume|"
                 r"resume/cv|cv|linkedin( profile)?|website|github|location|city)\b", re.I)
REQ_START = re.compile(r"(what you.ll bring|requirements|who you are|about you|what we.re looking for|qualifications|"
                       r"your profile|must.have|what you bring|you.ll need|you have|ideal candidate|"
                       r"we.re looking for|your skills|ihr profil|dein profil|aranan nitelikler)", re.I)
FLAGS = {
    "years": r"\d\+?\s*(?:-|to)?\s*\d*\s*\+?\s*years",
    "visa": r"sponsor|visa|right to work|work authori[sz]|work permit|citizen|eligible to work|clearance",
    "relocate": r"relocat|on.?site|in.?office|hybrid|days a week in",
    "attest": r"certif(y|ies)|personally (completed|written)|attest|without (the use of |using )?(ai|chatgpt)|"
              r"own words|ai.generated|generative ai tools",
    "salary": r"salary|compensation|expected pay|pay expectation|gehalt",
}
LANGS = r"\b(german|french|dutch|spanish|swedish|danish|norwegian|finnish|italian|polish|portuguese|arabic|" \
        r"turkish|czech|hungarian|romanian|greek|japanese|korean|mandarin|chinese|hebrew)\b"


def sentences(text, pattern, n=3, width=240):
    out = []
    for s in re.split(r"(?<=[.!?•;])\s+", text):
        if re.search(pattern, s, re.I):
            out.append(s.strip()[:width])
            if len(out) >= n:
                break
    return out


def q(label, required, kind="", options=None, group="", hint=""):
    return {"label": clean(label), "required": bool(required), "type": kind, "options": options or [],
            "group": group, "hint": clean(hint)[:300]}


def ashby(slug, pid):
    query = ("query ApiJobPosting($o: String!, $j: String!) { jobPosting(organizationHostedJobsPageName: $o, "
             "jobPostingId: $j) { title locationName descriptionHtml compensationTierSummary "
             "applicationForm { sections { title fieldEntries { ... on FormFieldEntry { field isRequired "
             "descriptionHtml } } } } } }")
    d = get("https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting",
            {"operationName": "ApiJobPosting", "variables": {"o": slug, "j": pid}, "query": query})
    p = ((d or {}).get("data") or {}).get("jobPosting")
    if not p:
        return None
    qs = []
    for sec in (p.get("applicationForm") or {}).get("sections") or []:
        for e in sec.get("fieldEntries") or []:
            f = e.get("field") or {}
            opts = [v.get("label") for v in f.get("selectableValues") or []]
            qs.append(q(f.get("title", ""), e.get("isRequired"), f.get("type", ""), opts, sec.get("title", ""),
                        e.get("descriptionHtml") or ""))
    return {"title": p["title"], "location": p.get("locationName"), "pay": p.get("compensationTierSummary"),
            "text": clean(p.get("descriptionHtml")), "questions": qs,
            "apply_url": f"https://jobs.ashbyhq.com/{slug}/{pid}/application"}


def greenhouse(slug, pid):
    for host, web in (("boards-api.greenhouse.io", "job-boards.greenhouse.io"),
                      ("boards-api.eu.greenhouse.io", "job-boards.eu.greenhouse.io")):
        j = get(f"https://{host}/v1/boards/{slug}/jobs/{pid}?questions=true&pay_transparency=true")
        if j and j.get("title"):
            qs = []
            for grp in ("questions", "location_questions", "compliance", "demographic_questions"):
                block = j.get(grp) or []
                if isinstance(block, dict):  # demographic_questions is {"header", "questions": [...]}
                    block = block.get("questions") or []
                for it in block:
                    if "fields" in it:
                        f = (it.get("fields") or [{}])[0]
                        qs.append(q(it.get("label", ""), it.get("required"), f.get("type", ""),
                                    [v.get("label") for v in f.get("values") or []], grp, it.get("description") or ""))
                    else:  # compliance blocks nest their own questions
                        for sub in it.get("questions") or []:
                            f = (sub.get("fields") or [{}])[0]
                            qs.append(q(sub.get("label", ""), sub.get("required"), f.get("type", ""),
                                        [v.get("label") for v in f.get("values") or []], grp))
            pay = "; ".join(f"{r.get('title', '')} {r.get('min_cents', 0) // 100}-{r.get('max_cents', 0) // 100} "
                            f"{r.get('currency_type', '')}" for r in j.get("pay_input_ranges") or [])
            return {"title": j["title"], "location": (j.get("location") or {}).get("name"), "pay": pay or None,
                    "text": clean(j.get("content")), "questions": qs,
                    "apply_url": f"https://{web}/embed/job_app?for={slug}&token={pid}"}
    return None


def lever(slug, pid):
    for host, web in (("api.lever.co", "jobs.lever.co"), ("api.eu.lever.co", "jobs.eu.lever.co")):
        j = get(f"https://{host}/v0/postings/{slug}/{pid}")
        if j and j.get("text"):
            text = " ".join([clean(j.get("description"))] + [clean(l.get("text", "") + ": " + l.get("content", ""))
                                                             for l in j.get("lists") or []]
                            + [clean(j.get("additional"))])
            page = get(f"https://{web}/{slug}/{pid}/apply", raw=True) or ""
            qs = []
            for chunk in re.split(r'class="application-question', page)[1:]:
                chunk = chunk.split('class="application-question')[0][:4000]
                m = re.search(r'class="text">(.*?)</div>', chunk, re.S) or re.search(
                    r'application-label[^>]*>(.*?)</div>', chunk, re.S)
                if not m:
                    continue
                label = re.sub(r"<span class=\"required\">.*?</span>", "", m.group(1), flags=re.S)
                opts = [clean(o) for o in re.findall(r'<option[^>]*value="[^"]+"[^>]*>(.*?)</option>', chunk)]
                opts += [clean(o) for o in re.findall(r'type="(?:radio|checkbox)"[^>]*>\s*<span[^>]*>(.*?)</span>',
                                                      chunk, re.S)]
                qs.append(q(label.replace("✱", ""), 'class="required"' in m.group(0) or "✱" in m.group(0), "", opts[:12]))
            sal = j.get("salaryRange") or {}
            pay = f"{sal.get('min')}-{sal.get('max')} {sal.get('currency')} {sal.get('interval')}" if sal else None
            return {"title": j["text"], "location": (j.get("categories") or {}).get("location"), "pay": pay,
                    "text": text, "questions": qs, "apply_url": f"https://{web}/{slug}/{pid}/apply"}
    return None


def smartrecruiters(slug, pid):
    d = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{pid}")
    if not d or not d.get("name"):
        return None
    s = (d.get("jobAd") or {}).get("sections") or {}
    text = " ".join(clean((s.get(k) or {}).get("text")) for k in
                    ("companyDescription", "jobDescription", "qualifications", "additionalInformation"))
    l = d.get("location") or {}
    return {"title": d["name"], "location": ", ".join(x for x in (l.get("city"), country(l.get("country"))) if x),
            "pay": None, "text": text, "questions": [], "note": "questions only visible inside the form",
            "apply_url": d.get("applyUrl") or d.get("postingUrl")}


def recruitee(slug, pid):
    d = get(f"https://{slug}.recruitee.com/api/offers/")
    for o in (d or {}).get("offers", []):
        if str(o["id"]) == str(pid):
            qs = [q(x.get("body") or x.get("title") or "", x.get("required"), x.get("kind", ""),
                    [c.get("body") for c in x.get("open_question_options") or []]) for x in o.get("open_questions") or []]
            sal = o.get("salary") or {}
            pay = f"{sal.get('min')}-{sal.get('max')} {sal.get('currency')} {sal.get('period')}" if sal.get("min") else None
            return {"title": o["title"], "location": o.get("location"), "pay": pay,
                    "text": clean((o.get("description") or "") + " " + (o.get("requirements") or "")), "questions": qs,
                    "apply_url": o.get("careers_apply_url") or o.get("careers_url")}
    return None


def workable(slug, pid):
    d = get(f"https://apply.workable.com/api/v2/accounts/{slug}/jobs/{pid}")
    if not d or not d.get("title"):
        return None
    l = d.get("location") or {}
    return {"title": d["title"], "location": ", ".join(x for x in (l.get("city"), l.get("country")) if x),
            "pay": None, "text": clean(" ".join(d.get(k) or "" for k in ("description", "requirements", "benefits"))),
            "questions": [], "note": "questions only visible inside the form",
            "apply_url": f"https://apply.workable.com/{slug}/j/{pid}/apply/"}


def personio(slug, pid):
    for tld in ("de", "com"):
        t = get(f"https://{slug}.jobs.personio.{tld}/xml", raw=True)
        if t and f"<id>{pid}</id>" in t:
            block = t.split(f"<id>{pid}</id>")[1].split("</position>")[0]
            title = re.search(r"<name>(.*?)</name>", block, re.S)
            office = re.search(r"<office>(.*?)</office>", block, re.S)
            text = clean(" ".join(re.findall(r"<value>(.*?)</value>", block, re.S)).replace("<![CDATA[", "")
                         .replace("]]>", ""))
            return {"title": clean(title.group(1)) if title else "", "location": office.group(1) if office else "",
                    "pay": None, "text": text, "questions": [], "note": "questions only visible inside the form",
                    "apply_url": f"https://{slug}.jobs.personio.{tld}/job/{pid}#apply"}
    return None


READ = {"ashby": ashby, "greenhouse": greenhouse, "lever": lever, "smartrecruiters": smartrecruiters,
        "recruitee": recruitee, "workable": workable, "personio": personio}


def inspect(key):
    ats, slug, pid = key.split(":", 2)
    try:
        r = READ[ats.split("-")[0]](slug, pid)
    except Exception as e:
        r = {"error": str(e)[:200]}
    return key, r or {"error": "posting not found (closed?)"}


def report(key, r, chars, lang_ok):
    print(f"\n##### {key} | {r.get('title')} | {r.get('location')} | pay: {r.get('pay') or '-'}")
    if r.get("error"):
        print("   ", r["error"])
        return
    t = r.get("text") or ""
    m = REQ_START.search(t)
    start = max(0, (m.start() if m else 0) - 150)
    print("   ", t[start:start + chars])
    qtext = " ".join(x["label"] + " " + x["hint"] for x in r["questions"])
    for tag, pat in FLAGS.items():
        for s in sentences(t + " " + (qtext if tag in ("visa", "attest", "salary") else ""), pat):
            print(f"  [{tag}] {s}")
    for s in sentences(t, LANGS, 2):
        if not (lang_ok and all(lang_ok.search(w) for w in re.findall(LANGS, s, re.I))):
            print(f"  [language] {s}")
    if r.get("note"):
        print("  (note)", r["note"])
    for x in r["questions"]:
        if x["group"].startswith(("demographic", "location")) or (STD.search(x["label"]) and len(x["label"]) < 40):
            continue
        opts = (" [" + " / ".join(map(str, x["options"][:8])) + "]") if x["options"] else ""
        print(f"   {'*' if x['required'] else ' '} {x['label'][:200]} ({x['type']}){opts}")
    print("   apply:", r.get("apply_url"))


def main():
    a = sys.argv[1:]
    chars = 1800
    if "--chars" in a:
        i = a.index("--chars")
        chars = int(a[i + 1])
        del a[i:i + 2]
    if a and a[0] == "--from":
        keys = [j["key"] for j in load_json(a[1], [])]
    else:
        keys = a
    if not keys:
        print(__doc__)
        sys.exit(1)
    prof = load_profile()
    lang_ok = rx(prof.get("targets", {}).get("languages_ok"))
    out_dir = RUNS / "inspect"
    out_dir.mkdir(parents=True, exist_ok=True)
    with cf.ThreadPoolExecutor(6) as ex:
        for key, r in ex.map(inspect, keys):
            (out_dir / (key.replace(":", "-") + ".json")).write_text(json.dumps(r, ensure_ascii=False, indent=1),
                                                                     encoding="utf-8")
            report(key, r, chars, lang_ok)


if __name__ == "__main__":
    main()
