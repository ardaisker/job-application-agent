"""Public job-board endpoints of common applicant tracking systems (no login, no scraping of logged-in pages).

list_jobs(ats, slug) -> [{"ats","slug","id","title","location","url"}]   (empty list when the board is gone)
Supported ats: ashby, greenhouse, lever, smartrecruiters, recruitee, workable, personio.
"""
import re
import xml.etree.ElementTree as ET

from common import get

# ISO country codes some boards return instead of names, so location filters can stay in words.
COUNTRY = {"de": "Germany", "nl": "Netherlands", "at": "Austria", "ch": "Switzerland", "tr": "Türkiye",
           "fr": "France", "gb": "United Kingdom", "uk": "United Kingdom", "ie": "Ireland", "es": "Spain",
           "pt": "Portugal", "it": "Italy", "be": "Belgium", "lu": "Luxembourg", "dk": "Denmark", "se": "Sweden",
           "no": "Norway", "fi": "Finland", "pl": "Poland", "cz": "Czechia", "sk": "Slovakia", "hu": "Hungary",
           "ro": "Romania", "bg": "Bulgaria", "gr": "Greece", "rs": "Serbia", "hr": "Croatia", "si": "Slovenia",
           "ee": "Estonia", "lv": "Latvia", "lt": "Lithuania", "ae": "United Arab Emirates", "sa": "Saudi Arabia",
           "qa": "Qatar", "us": "United States", "ca": "Canada", "mx": "Mexico", "br": "Brazil", "in": "India",
           "cn": "China", "jp": "Japan", "kr": "South Korea", "sg": "Singapore", "au": "Australia", "il": "Israel"}


def country(code):
    return COUNTRY.get((code or "").lower(), code or "")


ATS = ("ashby", "greenhouse", "lever", "smartrecruiters", "recruitee", "workable", "personio")


def _ashby(slug):
    d = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    out = []
    for j in (d or {}).get("jobs", []):
        if not j.get("isListed", True):
            continue
        locs = [str(j.get("location") or "")] + [y.get("location", "") for y in j.get("secondaryLocations") or []]
        country = ((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry")
        if j.get("isRemote"):
            locs.append("Remote")
        out.append({"id": j["id"], "title": j["title"], "location": " | ".join(x for x in locs + [country or ""] if x),
                    "url": j.get("jobUrl") or f"https://jobs.ashbyhq.com/{slug}/{j['id']}"})
    return out


def _greenhouse(slug):
    for host, web in (("boards-api.greenhouse.io", "job-boards.greenhouse.io"),
                      ("boards-api.eu.greenhouse.io", "job-boards.eu.greenhouse.io")):
        d = get(f"https://{host}/v1/boards/{slug}/jobs")
        if d and d.get("jobs"):
            return [{"id": str(j["id"]), "title": j["title"], "location": (j.get("location") or {}).get("name", ""),
                     "url": f"https://{web}/{slug}/jobs/{j['id']}", "host": host} for j in d["jobs"]]
    return []


def _lever(slug):
    for host, web in (("api.lever.co", "jobs.lever.co"), ("api.eu.lever.co", "jobs.eu.lever.co")):
        d = get(f"https://{host}/v0/postings/{slug}?mode=json")
        if isinstance(d, list) and d:
            return [{"id": j["id"], "title": j["text"],
                     "location": " | ".join([(j.get("categories") or {}).get("location") or ""]
                                            + ((j.get("categories") or {}).get("allLocations") or [])
                                            + [j.get("workplaceType") or "", country(j.get("country"))]),
                     "url": j.get("hostedUrl") or f"https://{web}/{slug}/{j['id']}", "host": host} for j in d]
    return []


def _smartrecruiters(slug):
    out, offset = [], 0
    while offset < 5000:
        d = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}")
        content = (d or {}).get("content") or []
        for j in content:
            l = j.get("location") or {}
            out.append({"id": j["id"], "title": j["name"],
                        "location": " | ".join(x for x in (l.get("city"), l.get("region"), country(l.get("country")),
                                                           "Remote" if l.get("remote") else "") if x),
                        "url": f"https://jobs.smartrecruiters.com/{slug}/{j['id']}"})
        if len(content) < 100:
            break
        offset += 100
    return out


def _recruitee(slug):
    d = get(f"https://{slug}.recruitee.com/api/offers/")
    return [{"id": str(o["id"]), "title": o["title"],
             "location": " | ".join(x for x in (o.get("location"), o.get("country"), "Remote" if o.get("remote") else "")
                                    if x),
             "url": o.get("careers_url") or f"https://{slug}.recruitee.com/o/{o.get('slug')}"}
            for o in (d or {}).get("offers", [])]


def _workable(slug):
    d = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    return [{"id": j["shortcode"], "title": j["title"],
             "location": " | ".join(x for x in (j.get("city"), j.get("state"), j.get("country"),
                                                "Remote" if j.get("telecommuting") else "") if x),
             "url": j.get("url") or f"https://apply.workable.com/{slug}/j/{j['shortcode']}/"}
            for j in (d or {}).get("jobs", [])]


def _personio(slug):
    for tld in ("de", "com"):
        t = get(f"https://{slug}.jobs.personio.{tld}/xml", raw=True)
        if t and "<position" in t:
            try:
                root = ET.fromstring(t)
            except ET.ParseError:
                return []
            out = []
            for p in root.iter("position"):
                g = lambda k: (p.findtext(k) or "").strip()
                out.append({"id": g("id"), "title": g("name"), "location": " | ".join(
                    x for x in (g("office"), *(o.text or "" for o in p.iter("additionalOffice"))) if x),
                            "url": f"https://{slug}.jobs.personio.{tld}/job/{g('id')}"})
            return out
    return []


FETCH = {"ashby": _ashby, "greenhouse": _greenhouse, "lever": _lever, "smartrecruiters": _smartrecruiters,
         "recruitee": _recruitee, "workable": _workable, "personio": _personio}


def list_jobs(ats, slug):
    try:
        jobs = FETCH[ats](slug)
    except Exception:
        return []
    for j in jobs:
        j.update(ats=ats, slug=slug)
    return jobs


# Board URL patterns, used to pull ATS boards out of any text (HN posts, web pages, archives).
PATTERNS = {
    "ashby": r"jobs\.ashbyhq\.com/([A-Za-z0-9._-]+)",
    "greenhouse": r"(?:job-boards|boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9._-]+)",
    "lever": r"jobs(?:\.eu)?\.lever\.co/([A-Za-z0-9._-]+)",
    "smartrecruiters": r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9._-]+)",
    "recruitee": r"([A-Za-z0-9-]+)\.recruitee\.com",
    "workable": r"apply\.workable\.com/([A-Za-z0-9._-]+)",
    "personio": r"([A-Za-z0-9-]+)\.jobs\.personio\.(?:de|com)",
}
NOT_SLUGS = {"embed", "api", "v1", "boards", "job-board", "posting-api", "j", "jobs", "careers", "www", "static",
             "assets", "robots.txt", "favicon.ico", "sitemap.xml", "_next", "cdn-cgi", "internal", "oneclick-ui"}


def boards_in_text(text):
    found = set()
    for ats, pat in PATTERNS.items():
        for m in re.finditer(pat, text or ""):
            s = m.group(1)
            if s.lower() not in NOT_SLUGS and "%" not in s and len(s) > 1:
                found.add((ats, s))
    return found
