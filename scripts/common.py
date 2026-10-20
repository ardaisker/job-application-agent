"""Shared helpers: workspace paths, profile, HTTP, filters, tracker storage.

Workspace: $JOBAGENT_HOME (default ~/job-agent). It holds profile.toml, boards.json,
applications.json, seen.json, packages/ and runs/. Standard library only (Python 3.11+).
"""
import html
import json
import os
import pathlib
import re
import ssl
import sys
import tomllib
import urllib.request

HOME = pathlib.Path(os.environ.get("JOBAGENT_HOME", "~/job-agent")).expanduser()
PROFILE = HOME / "profile.toml"
BOARDS = HOME / "boards.json"
APPS = HOME / "applications.json"
SEEN = HOME / "seen.json"
PACKAGES = HOME / "packages"
RUNS = HOME / "runs"

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36",
      "Accept": "application/json"}
_CA = "/etc/ssl/cert.pem"  # python.org builds on macOS ship without a CA bundle
CTX = ssl.create_default_context(cafile=_CA) if os.path.exists(_CA) else ssl.create_default_context()


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_profile():
    if not PROFILE.exists():
        die(f"No profile at {PROFILE}. Copy templates/profile.example.toml there and fill it in.")
    with open(PROFILE, "rb") as f:
        return tomllib.load(f)


def get(url, data=None, headers=None, timeout=15, raw=False):
    """GET (or POST when data is given). Returns parsed JSON, text when raw=True, None on any error."""
    try:
        body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
        h = {**UA, **({"Content-Type": "application/json"} if body else {}), **(headers or {})}
        r = urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout, context=CTX)
        t = r.read().decode("utf-8", "ignore")
        return t if raw else json.loads(t)
    except Exception:
        return None


def clean(s):
    """HTML to one line of plain text."""
    s = html.unescape(s or "")
    s = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", " ", s, flags=re.I)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def company_key(s):
    return norm(re.sub(r"\(.*?\)|,.*| gmbh| ltd\.?| inc\.?| plc| ag$| b\.v\.| s\.a\.", "", (s or "").lower()))


def rx(words):
    """List of words/regexes -> one case-insensitive regex (None when empty)."""
    words = [w for w in (words or []) if w]
    return re.compile("|".join(f"(?:{w})" for w in words), re.I) if words else None


REMOTE = re.compile(r"remote|anywhere|worldwide|global|distributed|work from home", re.I)


class Filters:
    """Title and location rules from [targets] in profile.toml."""

    def __init__(self, profile):
        t = profile.get("targets", {})
        self.inc = rx(t.get("titles_include"))
        self.exc = rx(t.get("titles_exclude"))
        self.keep = rx(t.get("keep_even_if_excluded"))
        self.loc_inc = rx(t.get("locations_include"))
        self.loc_exc = rx(t.get("locations_exclude"))
        self.remote_ok = bool(t.get("remote_ok", True))
        self.skip = {company_key(c) for c in t.get("skip_companies", [])}
        if not self.inc:
            die("profile.toml [targets] titles_include is empty")

    def title_ok(self, title):
        if not self.inc.search(title or ""):
            return False
        if self.exc and self.exc.search(title) and not (self.keep and self.keep.search(title)):
            return False
        return True

    def location_ok(self, loc):
        """A named place from locations_include wins; "remote" counts only when remote_ok and no excluded
        region is named ("Remote - US" is out when "united states|\\bus\\b" is excluded)."""
        loc = loc or ""
        place = bool(self.loc_inc and self.loc_inc.search(loc))
        excluded = bool(self.loc_exc and self.loc_exc.search(loc))
        if place:
            return True
        return self.remote_ok and bool(REMOTE.search(loc)) and not excluded

    def company_ok(self, name):
        return company_key(name) not in self.skip


def load_json(path, default):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def posting_key(ats, slug, pid):
    return f"{ats.split('-')[0]}:{slug.lower()}:{pid}"


def known_posting_keys():
    """Keys of postings already applied to, prepared or skipped (never show them again)."""
    keys = {a.get("key") for a in load_json(APPS, [])}
    keys |= set(load_json(SEEN, []))
    return {k for k in keys if k}
