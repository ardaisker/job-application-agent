# Form mechanics per applicant tracking system

These notes come from several hundred real submissions with the Claude in Chrome extension. Forms change, so
when a step fails, take a screenshot and adapt. Never resubmit blindly.

## Rules for every form
- **Upload the CV first**, wait, then take a screenshot before typing. Several systems parse the CV and overwrite
  or clear fields typed before the upload finished.
- Only the Chrome extension's `file_upload` can attach a file. Other browsers in the app cannot.
- Typing: click the field for real, or focus it with JS and then click it. Type with real key events. Setting
  `value` through JS often does not register with React forms. After the last field press a real Tab so the
  framework saves it.
- Read each value back (JS `value`, or a screenshot) before Submit. For radios and checkboxes check
  `aria-checked` on `[role=radio]` or `[role=checkbox]`. A hidden input's `checked` can lie.
- Scroll with `el.scrollIntoView({block:'center', behavior:'instant'})`. With smooth scrolling the next click
  lands on the wrong element.
- After a CV parse, delete wrong autofill, for example a "current company" when the person no longer works there,
  or wrong education months. If a widget cannot be cleared, note it in `answers`.
- Cookie banners: choose the most privacy-preserving option, such as "reject non-essential". Some banners swallow
  typing until closed, and some only close with a coordinate click.
- Confirmation: look for the success state (green box, "Thank you for applying", "application received") before
  recording `applied`. Some systems take 20-30 s, so do not press Submit twice.

## Ashby (`jobs.ashbyhq.com/<slug>/<id>/application`)
- "Page not found" while the API still lists the job: the board is embedded on the company site. Add
  `?embed=js` to the application URL.
- Location box: the first click only opens it. Click again, type the city, wait about 3 s, then click the
  matching option. Afterwards the page may jump back to it, so run `document.activeElement.blur()` before the
  next field.
- Fill from the bottom up when fields shift. Yes/No buttons: one click. If "Missing entry" shows, click the other
  option and then back.
- Date fields: type `MM/DD/YYYY`, then click the day in the calendar.
- Submit: wait about 3 s after the last field. "We're updating your application" means wait 3-4 s and click
  again.
- Coordinates from JS can be off by a constant zoom factor on some screens. Calibrate once per session with a
  screenshot.

## Greenhouse (`job-boards.greenhouse.io/embed/job_app?for=<slug>&token=<id>`; EU boards on `job-boards.eu.greenhouse.io`)
- The first interaction must be a real click on an input. After that, JS focus plus typing works.
- The first click after a file upload is swallowed. Click a field, type, read it back, and repeat if it is empty.
- React-select dropdowns (country, yes/no, "how did you hear"): type, wait 1 s, press Return. The country is often
  found by its first letters.
- `input_text` answers are often limited to 255 characters. Check `maxLength`.
- Record the canonical link `https://job-boards.greenhouse.io/<slug>/jobs/<id>`, not the embed link. Embed links
  all look alike once the query string is removed.

## Lever (`jobs.lever.co/<slug>/<id>/apply`; EU: `jobs.eu.lever.co`)
- The CV parse fills "Current company". Check it.
- Location: pick from the suggestion list. Free text is sometimes rejected.
- hCaptcha sometimes appears on submit. That is the user's job, so record the posting as `ready`.

## Workable (`apply.workable.com/<account>/j/<code>/apply/`, or `apply.workable.com/j/<code>/apply` when the account is unknown)
- After the CV upload, take a screenshot before typing, or the typed text does not land.
- JS focus does not work. Scroll the field to the centre, click its returned coordinates, then type.
- Phone: type the number without the country code when a flag selector is present.
- Workable returns HTTP 429 for an hour or more after heavy scanning. Queue those postings and come back later.

## SmartRecruiters (`jobs.smartrecruiters.com/<Company>/<id>`)
- Often two pages. The second page at larger companies asks for declarations (criminal record, side jobs,
  degree scans). Those belong to the user (`ready`).
- Some companies require an SR account ("Sign in to apply"). That also belongs to the user.

## Personio (`<slug>.jobs.personio.de/job/<id>#apply`)
- Native inputs and selects. `form_input` with the element ref works well.
- Salary expectation is often required as a number. Follow the profile's salary rules.

## Recruitee (`<slug>.recruitee.com/o/<offer>`) and Teamtailor (`<slug>.teamtailor.com/jobs/<id>`)
- Recruitee forms often ask a required salary number and a visa-situation choice. Answer from the profile or ask.
- Teamtailor: fields can sit side by side, so click the coordinates of the field itself, not the column centre.
  Sliders take a click on the track at the wanted position.

## JazzHR, BambooHR, Breezy, Pinpoint and other small systems
- They usually work like plain HTML forms. JazzHR asks for a street address and shows a visible "I'm not a robot"
  box, so it always ends as `ready`.

## Workday, SuccessFactors, Taleo, iCIMS, Oracle Recruiting
- All need an account. Record `ready`, missing "account creation + submit", with the direct posting link. Give
  the user a list of these at the end of the session.
