"""Scan every known board and list NEW postings that pass the profile filters.

  scan.py                         scan all boards in boards.json -> runs/scan-<time>.json (+ printed table)
  scan.py --only ashby,lever      limit to some ATS
  scan.py add ats:slug ...        add boards by hand (e.g. greenhouse:acme  smartrecruiters:BoschGroup)
  scan.py boards                  list known boards

A posting is NEW when its key is not in applications.json or seen.json. Companies already in the tracker are
flagged, not hidden: the agent asks before a second role at the same company.
"""
import concurrent.futures as cf
import datetime
import sys

from boards import ATS, list_jobs
from common import APPS, BOARDS, RUNS, Filters, company_key, die, known_posting_keys, load_json, load_profile, \
    posting_key, save_json


def add_boards(items):
    boards = load_json(BOARDS, [])
    have = {(a, s.lower()) for a, s in boards}
    n = 0
    for it in items:
        ats, _, slug = it.partition(":")
        if ats not in ATS or not slug:
            die(f"bad board '{it}', use ats:slug with ats in {ATS}")
        if (ats, slug.lower()) not in have:
            boards.append([ats, slug])
            have.add((ats, slug.lower()))
            n += 1
    save_json(BOARDS, boards)
    print(f"added {n}, total {len(boards)} boards")


def scan(only=None):
    prof = load_profile()
    f = Filters(prof)
    boards = [b for b in load_json(BOARDS, []) if not only or b[0] in only]
    if not boards:
        die("boards.json is empty. Add boards with 'scan.py add' or discover.py first.")
    known = known_posting_keys()
    applied_companies = {company_key(a["company"]) for a in load_json(APPS, []) if a["status"] != "skipped"}
    hits, live = [], 0
    with cf.ThreadPoolExecutor(16) as ex:
        for jobs in ex.map(lambda b: list_jobs(*b), boards):
            live += bool(jobs)
            for j in jobs:
                k = posting_key(j["ats"], j["slug"], j["id"])
                if k in known or not f.title_ok(j["title"]) or not f.location_ok(j["location"]):
                    continue
                if not f.company_ok(j["slug"]):
                    continue
                j["key"] = k
                j["company_in_tracker"] = company_key(j["slug"]) in applied_companies
                hits.append(j)
    RUNS.mkdir(parents=True, exist_ok=True)
    out = RUNS / f"scan-{datetime.datetime.now():%Y%m%d-%H%M}.json"
    save_json(out, hits)
    for j in sorted(hits, key=lambda j: (j["slug"].lower(), j["title"])):
        flag = " [company already in tracker]" if j["company_in_tracker"] else ""
        print(f"{j['ats'][:10]:10} {j['slug'][:22]:22} | {j['title'][:60]:60} | {j['location'][:40]:40} | {j['key']}{flag}")
    print(f"\n{len(hits)} new postings from {live}/{len(boards)} live boards -> {out}", file=sys.stderr)


def main():
    a = sys.argv[1:]
    if a and a[0] == "add":
        add_boards(a[1:])
    elif a and a[0] == "boards":
        for b in load_json(BOARDS, []):
            print(*b)
    elif a and a[0] == "--only":
        scan(set(a[1].split(",")))
    elif not a:
        scan()
    else:
        die(__doc__)


if __name__ == "__main__":
    main()
