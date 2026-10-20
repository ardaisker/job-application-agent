"""Find NEW boards (companies) to scan. Every command adds the live boards it finds to boards.json.

  discover.py names "Acme Robotics" "Foo GmbH" ...   guess board slugs from company names and probe each ATS
  discover.py names --file companies.txt             one company name per line (e.g. from a web search, a fair list)
  discover.py text <file-or-url> [...]               pull ATS board links out of any page or saved text
  discover.py wayback <ats> [--limit 400]            boards the Internet Archive has seen on that ATS (big pool)
  discover.py hn                                     boards linked in the last two Hacker News "Who is hiring" threads
  discover.py getro "<query>" ["<query>" ...]        search VC portfolio job boards; prints matching postings
  discover.py workable "<query>" ["<country>"]       Workable's cross-company search; prints matching postings

Search engines also work well: restrict a web search to one ATS host, for example
  site:jobs.ashbyhq.com "mechanical engineer" Berlin      site:jobs.smartrecruiters.com "Konstrukteur"
then feed the result URLs to 'discover.py text'. Indexes can be stale: the scan checks that each posting is live.
"""
import concurrent.futures as cf
import pathlib
import re
import sys
import time

from boards import NOT_SLUGS, PATTERNS, boards_in_text, list_jobs
from common import BOARDS, Filters, die, get, load_json, load_profile, norm, save_json


def known():
    return {(a, s.lower()) for a, s in load_json(BOARDS, [])}


def save_new(found):
    boards = load_json(BOARDS, [])
    have = {(a, s.lower()) for a, s in boards}
    new = [[a, s] for a, s in found if (a, s.lower()) not in have]
    save_json(BOARDS, boards + new)
    for a, s in new:
        print("  +", a, s)
    print(f"{len(new)} new boards, {len(boards) + len(new)} total")


def live(cands, workers=16):
    """Keep (ats, slug) pairs whose board has at least one posting."""
    with cf.ThreadPoolExecutor(workers) as ex:
        return [c for c, jobs in zip(cands, ex.map(lambda c: list_jobs(*c), cands)) if jobs]


def slugs_for(name):
    base = re.sub(r"\(.*?\)|\|.*|,.*| gmbh| ab$| ltd\.?| plc| inc\.?| b\.v\.| ag$| se$| s\.a\.| a\.ş\.| group$|"
                  r" technologies$| labs$| ai$|\.ai$|\.io$|\.com$", "", name.lower()).strip()
    out = []
    for s in (re.sub(r"[^a-z0-9]+", "", base), re.sub(r"[^a-z0-9]+", "-", base).strip("-"),
              re.sub(r"[^a-z0-9]+", "", name.lower()), name.replace(" ", "")):
        if s and len(s) > 2 and s not in out:
            out.append(s)
    return out


def from_names(names):
    k = known()
    cands = []
    for n in names:
        for s in slugs_for(n):
            for a in ("ashby", "greenhouse", "lever", "workable", "recruitee", "personio", "smartrecruiters"):
                if (a, s.lower()) not in k:
                    cands.append((a, s))
    print(f"probing {len(cands)} slug guesses for {len(names)} names", file=sys.stderr)
    found = live(cands)
    # one board per company and ATS is enough
    seen, keep = set(), []
    for a, s in found:
        if (a, norm(s)) not in seen:
            seen.add((a, norm(s)))
            keep.append((a, s))
    save_new(keep)


def from_text(sources):
    found = set()
    for src in sources:
        t = get(src, raw=True) if src.startswith("http") else pathlib.Path(src).read_text(encoding="utf-8", errors="ignore")
        found |= boards_in_text(t or "")
        found |= boards_in_text(src)
    k = known()
    save_new(live([f for f in found if (f[0], f[1].lower()) not in k]))


WAYBACK_HOST = {"ashby": "jobs.ashbyhq.com", "greenhouse": "job-boards.greenhouse.io", "lever": "jobs.lever.co",
                "smartrecruiters": "jobs.smartrecruiters.com", "workable": "apply.workable.com"}


def from_wayback(ats, limit):
    if ats not in WAYBACK_HOST:
        die(f"wayback supports {list(WAYBACK_HOST)}")
    url = (f"http://web.archive.org/cdx/search/cdx?url={WAYBACK_HOST[ats]}/*&output=txt&fl=original"
           f"&collapse=urlkey&from=2025&limit=80000")
    t = get(url, raw=True, timeout=120) or ""
    slugs = {m.group(1) for m in re.finditer(PATTERNS[ats], t)} - NOT_SLUGS
    k = known()
    cands = [(ats, s) for s in sorted(slugs) if (ats, s.lower()) not in k and "%" not in s][:limit]
    print(f"archive lists {len(slugs)} {ats} boards; probing {len(cands)} unknown ones", file=sys.stderr)
    save_new(live(cands, 20))


def from_hn():
    d = get("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=8")
    stories = [h for h in (d or {}).get("hits", []) if "who is hiring" in h["title"].lower()][:2]
    found = set()
    for h in stories:
        page = 0
        while True:
            r = get(f"https://hn.algolia.com/api/v1/search_by_date?tags=comment,story_{h['objectID']}"
                    f"&hitsPerPage=1000&page={page}") or {}
            for c in r.get("hits", []):
                found |= boards_in_text(c.get("comment_text") or "")
            page += 1
            if page >= r.get("nbPages", 1):
                break
        print(h["title"], file=sys.stderr)
    k = known()
    save_new(live([f for f in found if (f[0], f[1].lower()) not in k]))


# VC portfolio boards on Getro: network id -> host. Extend freely.
GETRO = {"8672": "jobs.accel.com", "36986": "careers.atomico.com", "4186": "talent.seedcamp.com",
         "222": "jobs.generalcatalyst.com", "1680": "jobs.pointninecap.com", "617": "jobs.earlybird.com",
         "53552": "jobs.creandum.com", "947": "jobs.speedinvest.com", "228": "jobs.joinef.com",
         "3293": "jobs.headline.com", "44081": "talent.cherry.vc", "234": "jobs.hvcapital.com",
         "7715": "careers.antler.co", "10421": "portfoliojobs.partechpartners.com", "89": "jobs.techstars.com",
         "246": "jobs.insightpartners.com", "257": "jobs.khoslaventures.com", "9266": "jobs.hub71.com"}


def from_getro(queries):
    f = Filters(load_profile())
    out = {}
    for nid, host in GETRO.items():
        for qy in queries:
            for p in range(3):
                d = get(f"https://api.getro.com/api/v2/collections/{nid}/search/jobs",
                        {"hitsPerPage": 20, "page": p, "query": qy, "filters": {"page": p}},
                        {"Origin": "https://" + host, "Referer": "https://" + host + "/"}, timeout=25)
                jobs = ((d or {}).get("results") or {}).get("jobs") or []
                for j in jobs:
                    loc = " | ".join(str(l) for l in (j.get("searchable_locations") or j.get("locations") or []))
                    if f.title_ok(j.get("title", "")) and f.location_ok(loc):
                        out[j.get("url")] = [(j.get("organization") or {}).get("name"), j["title"], loc[:50], j.get("url")]
                if len(jobs) < 20:
                    break
                time.sleep(0.25)
        print(host, len(out), file=sys.stderr)
    for r in sorted(out.values(), key=lambda r: str(r[0])):
        print(f"{str(r[0])[:20]:20} | {r[1][:55]:55} | {r[2]:50} | {r[3]}")
    print("Feed the URLs to 'discover.py text' to add their boards, or inspect them directly.", file=sys.stderr)


def from_workable(query, country=""):
    f = Filters(load_profile())
    url = f"https://jobs.workable.com/api/v1/jobs?query={query.replace(' ', '+')}" + (
        f"&location={country.replace(' ', '+')}" if country else "")
    d = get(url, timeout=25)
    if d is None:
        die("Workable search refused (it rate-limits for about an hour after many requests); try later")
    for j in d.get("jobs", []):
        loc = " ".join(str(j.get("location", {}).get(k) or "") for k in ("city", "countryName")) + (
            " Remote" if j.get("workplace") == "remote" else "")
        if f.title_ok(j.get("title", "")) and f.location_ok(loc):
            print(f"{(j.get('company') or {}).get('title', '')[:22]:22} | {j['title'][:55]:55} | {loc[:30]:30} | "
                  f"{j.get('url')}")


def main():
    a = sys.argv[1:]
    if not a:
        die(__doc__)
    cmd, rest = a[0], a[1:]
    if cmd == "names":
        if rest[:1] == ["--file"]:
            rest = [l.strip() for l in open(rest[1], encoding="utf-8") if l.strip()]
        from_names(rest)
    elif cmd == "text":
        from_text(rest)
    elif cmd == "wayback" and rest:
        lim = int(rest[rest.index("--limit") + 1]) if "--limit" in rest else 400
        from_wayback(rest[0], lim)
    elif cmd == "hn":
        from_hn()
    elif cmd == "getro" and rest:
        from_getro(rest)
    elif cmd == "workable" and rest:
        from_workable(rest[0], rest[1] if len(rest) > 1 else "")
    else:
        die(__doc__)


if __name__ == "__main__":
    main()
