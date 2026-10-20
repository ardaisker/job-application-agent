"""Application tracker (applications.json + one package note per application).

  tracker.py check "<company>" [posting id or url]   CLEAN, or STOP with the matches. Run before EVERY form.
  tracker.py add < record.json                        record a submitted / ready / skipped application
  tracker.py skip ats:slug:id [reason]                never show this posting again
  tracker.py status <app-id> <status> [note]          e.g. rejected, interview, offer, withdrawn
  tracker.py list [status]                            table of applications
  tracker.py stats                                    counts per status
  tracker.py export                                   writes applications.md (readable table)
  tracker.py cv "<posting title>"                     which CV file to upload (profile [cv] rules)

record.json fields: company, role, location, link, ats, slug, posting_id, cv, status (applied|ready|skipped),
answers (markdown: every answer exactly as submitted), missing (for status=ready: what the user must fill),
note. Status values after that are free text (rejected, interview, offer ...).
"""
import datetime
import json
import re
import sys

import os

from common import APPS, PACKAGES, SEEN, company_key, die, load_json, load_profile, posting_key, save_json


def now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def check(company, ident=None):
    apps = load_json(APPS, [])
    ck = company_key(company)
    hits = []
    for a in apps:
        ak = company_key(a["company"])
        same_company = ck and ak and len(ak) > 2 and (ck == ak or (len(ck) > 3 and (ck in ak or ak in ck)))
        same_posting = ident and ident.lower() in json.dumps(a).lower()
        if same_company or same_posting:
            hits.append(a)
    for a in hits:
        print(f"FOUND {a['id']} | {a['company']} | {a['role']} | {a['status']} | {a['date']}")
    print("CLEAN" if not hits else "STOP: already in tracker (same company counts; ask the user before a second role)")


def add(rec):
    for f in ("company", "role", "link", "status"):
        if not rec.get(f):
            die(f"record is missing '{f}'")
    apps = load_json(APPS, [])
    key = posting_key(rec["ats"], rec["slug"], rec["posting_id"]) if rec.get("ats") and rec.get("slug") and rec.get(
        "posting_id") else None
    link = rec["link"].split("?")[0].rstrip("/")
    for a in apps:
        if (key and a.get("key") == key) or a["link"].split("?")[0].rstrip("/") == link:
            die(f"duplicate of {a['id']} ({a['company']} / {a['role']}); use 'status' to change it")
    n = max([int(a["id"][2:]) for a in apps] or [0]) + 1
    app = {"id": f"a-{n}", "key": key, "date": now(), "history": [{"status": rec["status"], "at": now()}],
           **{k: rec.get(k, "") for k in ("company", "role", "location", "link", "ats", "slug", "posting_id", "cv",
                                          "status", "missing", "note")}}
    apps.append(app)
    save_json(APPS, apps)
    if rec["status"] != "skipped":
        PACKAGES.mkdir(parents=True, exist_ok=True)
        p = PACKAGES / f"{slugify(rec['company'])}-{slugify(rec['role'])}.md"
        p.write_text(
            f"# {rec['company']} · {rec['role']} · {rec.get('location', '')}\n\n"
            f"- Posting: {rec['link']}\n- CV: {rec.get('cv', '')}\n- Status: **{rec['status']}** ({now()})\n"
            + (f"- Missing (user fills): {rec['missing']}\n" if rec.get("missing") else "")
            + (f"- Note: {rec['note']}\n" if rec.get("note") else "")
            + f"\n## Answers as submitted\n{rec.get('answers', '')}\n", encoding="utf-8")
        print(f"{app['id']} {rec['company']} | {rec['role']} | {rec['status']} -> {p}")
    else:
        print(f"{app['id']} {rec['company']} skipped")


def skip(key, reason=""):
    seen = load_json(SEEN, [])
    if key not in seen:
        seen.append(key)
        save_json(SEEN, seen)
    print("skipped", key, reason)


def status(app_id, st, note=""):
    apps = load_json(APPS, [])
    for a in apps:
        if a["id"] == app_id:
            a["status"] = st
            a["history"].append({"status": st, "at": now(), **({"note": note} if note else {})})
            save_json(APPS, apps)
            print(app_id, a["company"], "->", st)
            return
    die(f"no application {app_id}")


def pick_cv(title):
    cv = load_profile().get("cv", {})
    for r in cv.get("rules", []):
        if re.search(r["match"], title, re.I):
            return os.path.expanduser(r["file"])
    return os.path.expanduser(cv.get("default", ""))


def table(apps):
    rows = ["| id | date | company | role | location | status |", "|---|---|---|---|---|---|"]
    rows += [f"| {a['id']} | {a['date'][:10]} | {a['company']} | [{a['role']}]({a['link']}) | {a.get('location', '')} "
             f"| {a['status']} |" for a in apps]
    return "\n".join(rows)


def main():
    if len(sys.argv) < 2:
        die(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "check" and args:
        check(args[0], args[1] if len(args) > 1 else None)
    elif cmd == "add":
        add(json.load(sys.stdin))
    elif cmd == "skip" and args:
        skip(args[0], " ".join(args[1:]))
    elif cmd == "status" and len(args) >= 2:
        status(args[0], args[1], " ".join(args[2:]))
    elif cmd == "list":
        apps = [a for a in load_json(APPS, []) if not args or a["status"] == args[0]]
        print(table(apps))
    elif cmd == "stats":
        c = {}
        for a in load_json(APPS, []):
            c[a["status"]] = c.get(a["status"], 0) + 1
        print(json.dumps(c, ensure_ascii=False), "total", sum(c.values()))
    elif cmd == "cv" and args:
        path = pick_cv(args[0])
        print(path if os.path.exists(path) else f"{path}  (FILE NOT FOUND: fix [cv] in profile.toml)")
    elif cmd == "export":
        out = APPS.with_name("applications.md")
        out.write_text("# Applications\n\n" + table(load_json(APPS, [])) + "\n", encoding="utf-8")
        print(out)
    else:
        die(__doc__)


if __name__ == "__main__":
    main()
