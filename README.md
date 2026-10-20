# job-application-agent

A [Claude Code](https://claude.com/claude-code) skill that applies to jobs for you. It finds openings on public
company job boards, filters them against your profile, reads each posting and its questions, fills the company's
own form in Chrome, records everything, and repeats. It works for any field: software, mechanical, electrical,
finance and others. You set the targets.

**What it will not do:** use LinkedIn, create accounts, type passwords, solve CAPTCHAs, enter ID numbers, or
invent experience. Those items are left for you, listed one by one.

## Install

```bash
git clone https://github.com/<you>/job-application-agent ~/.claude/skills/job-application-agent
mkdir -p ~/job-agent && cp ~/.claude/skills/job-application-agent/templates/profile.example.toml ~/job-agent/profile.toml
```

Requirements:
- Python 3.11 or newer (`python3 --version`). No packages to install.
- Claude Code with the **Claude in Chrome** extension connected. Only it can attach your CV to a form.
- Your CV as PDF (one or more variants).

## Use

Open Claude Code and say, for example:

- "Set up the job application agent with my CV at ~/Documents/CV.pdf" (first run: builds `profile.toml` with you)
- "Find mechanical design engineer openings in Germany and the Netherlands and apply"
- "Keep applying until I say stop" (autopilot; otherwise it asks before each Submit)
- "Which applications are waiting for me?" / "Update statuses from my inbox"

Everything lives in `~/job-agent/` (change it with `JOBAGENT_HOME`):

| File | What |
|---|---|
| `profile.toml` | you: targets, work authorization, salary policy, CV files, true facts for answers |
| `boards.json` | company job boards to scan |
| `applications.json`, `applications.md` | every application and its status |
| `packages/*.md` | the exact answers sent to each company (read before an interview) |
| `seen.json` | postings skipped on purpose |

## Scripts (also usable by hand)

```bash
cd ~/.claude/skills/job-application-agent
python3 scripts/discover.py names "Bosch Group" "Isar Aerospace" "Wingcopter"   # find their job boards
python3 scripts/scan.py                                                         # new matching postings
python3 scripts/inspect_posting.py greenhouse:isaraerospace:4943578101          # requirements + form questions
python3 scripts/tracker.py check "Isar Aerospace"                               # applied there before?
python3 scripts/tracker.py stats
```

Supported boards: Ashby, Greenhouse, Lever, SmartRecruiters, Workable, Recruitee and Personio. Workday and similar
systems need an account, so the agent prepares them and hands them to you.

## Türkçe kısa özet

Bu bir Claude Code skill'i. Şirketlerin kendi iş ilanı sayfalarını tarar ve profiline uyan ilanları seçer.
İlanı ve formdaki soruları okur, formu Chrome'da senin doğru bilgilerinle doldurur, her başvuruyu kaydeder ve
bir sonrakine geçer. Varsayılan olarak her "Gönder"den önce sana sorar. Sormadan göndermesi için açıkça
"onaysız devam et" demen gerekir. LinkedIn'e girmez, hesap açmaz, şifre girmez, CAPTCHA çözmez, kimlik numarası
yazmaz ve deneyim uydurmaz; bunları sana bırakır. Kurulum yukarıda. İlk seferde Claude'a "CV'm şurada, job
application agent'ı kur" demen yeterli.

## License

MIT
