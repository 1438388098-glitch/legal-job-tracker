# Legal Job Tracker

English · [简体中文](./README.zh-CN.md)

A **legal-job collector and application tracker** that runs on your own computer. It automatically collects law-firm / public-sector / in-house / internship / SOE postings (including provincial first-tier and second-tier companies) from 33 official sources covering the Pearl River Delta + Shaoguan, deduplicates them strictly, and serves a local web app where you filter and read postings, track applications, get deadline reminders, and export summary sheets. It is explainable end to end: strict cross-source deduplication ("prefer missing a merge over a wrong merge"), resume-to-job match scoring where every point has a stated reason, and education hard-thresholds. Runs locally on FastAPI + SQLite; no data ever leaves the machine.

- Single-machine: all data lives in a local SQLite file; nothing is uploaded anywhere
- No Node / frontend build chain; one command to start
- Collectors are driven by "config + selectors": when an official site redesigns, you edit config, not code

## Screenshots

Job list — the overview stats bar (actionable / closing in 3 or 7 days / fresh today / no deadline), the filter row, and per-row urgency bars with deadline coloring:

![Job list page (demo data)](docs/screenshots/jobs-list.png)

> The screenshot uses **self-written demo data only** (five fictional postings titled with "demo"); no real postings or personal application records are included.

---

## Quick start

```bash
# 1) Create a venv and install dependencies (first time only)
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install fastapi "uvicorn[standard]" jinja2 httpx \
    selectolax apscheduler python-multipart openpyxl pytest

# 2) Initialize the database + seed the 33 sources
.venv/Scripts/python.exe scripts/seed_sources.py

# 3) First collection (33 sources; slow sites get a 90-second budget; typically 2~5 minutes)
.venv/Scripts/python.exe -c "import sys;sys.path.insert(0,'.');from app import db;from app.collect.runner import Runner;c=db.connect('data/job.db');db.init_db(c);print(Runner(c).run_all())"

# 4) Start the local web app
.venv/Scripts/python.exe -m uvicorn app.web.main:create_app --factory --port 8642
```

Then open **http://127.0.0.1:8642** in your browser.

**Day-to-day on Windows**: double-click `start.bat` — it checks the environment, starts the service, and opens the browser. `start.bat dev` is debug mode (scheduled collection disabled).

> Once the service is up, it collects automatically every day at 08:05 (incremental, ~10 seconds measured). Set the environment variable `APP_DISABLE_SCHEDULER=1` to turn scheduled collection off.

---

## Resume & job matching

Upload your resume on `/profile` (PDF / Word / plain text — **stored only in the local database**). It parses out education, skills, internship experience types, and target cities into an **editable** personal profile; `/recommend` ranks jobs by match score, and every point has a reason:

- Target city ±26 / job type ±22 / skill hits (**title hits weigh ×2**, capped at 26) / relevant experience +14 / education satisfied +8 / has a clear deadline +6 — max 100, no baseline
- **Hard education threshold**: job requires a master's and the profile holds a bachelor's → sharply down-weighted, with the reason explicitly stated as "education below requirement"
- **Experience requirements**: the body asks for "X+ years" and the profile's years are clearly short → down-weighted; satisfied +6; explicitly welcomes new graduates and you are one +6

Parsing works section by section — the education section only yields degrees (school/degree/major are **paired line by line**, taking the highest degree, so a resume with both bachelor's and master's never mispairs a school), and only the internship/work sections yield experience and work years, so years of study never count as work experience. Target cities preferentially read the "job objective" section (an internship in Dongguan does not mean you want Dongguan); job types are also inferred from the objective section. Jobs you already track, and expired jobs, never enter recommendations; on equal scores, higher-priority sources (the "Five Institutes & Four Departments" law schools, etc.) show first.

## Notice snapshots

Every job's detail-page body is **archived locally** (`app/snapshot.py`) — if the source site deletes the post, you can still read it. A snapshot is not a raw text dump but a **structured layout** (`app/web/snapshot_view.py`):

- **Key-info card on top**: application deadlines / signup windows, contact info, education requirements, pay, and other key lines are listed first (≤8 lines) — no scrolling around to find them
- **Tiered body**: official-document numbering ("一、二、") is recognized as section headings; everything else renders as paragraphs; the raw text is kept collapsed, and one click switches between the structured view and the original
- **Safety**: snapshots come from the public internet; everything is HTML-escaped before output

---

## Daily use

| I want to… | Where to go |
|---|---|
| See which new jobs exist | Home `/`, by default **only open jobs**, sorted by deadline with the soonest on top; click "New today" in the overview bar to see only what was collected today |
| Look up a notice that closed long ago | Switch the top filter to "All posts", or keyword-search (result notices are hidden by default but always searchable) |
| Only see one type / city / employment kind | The filter bar (notice kind / type / city / **employment type** / status / keyword); "established post vs contract" is directly filterable |
| Only see jobs with no deadline to chase | The overview bar's "No deadline", or filter `rolling=1` (long-term / email-application jobs; the deadline column shows a green "rolling") |
| Deadline reminders | Top banner: red = closing within 3 days, yellow = within 7; **if desktop notifications are enabled, one notification pops after each daily collection** (including "N due today") |
| Track applications | Click "Track" right on a list row (no need to enter the detail page); or click "Track application" on the detail page; advance statuses on `/board` (to-apply / applied / written test / interview / offer / rejected) |
| Bulk tidy up | "Bulk" at the top right of the list → check rows → mark as read / archive |
| Recruitment info inside WeChat official accounts | `/paste` paste box: paste a link → the system fetches the body and extracts fields → you confirm and save |
| See which sources are failing | `/health` source-health page: each source's last success time, consecutive failure count, and last error; re-collect a single source immediately |
| Export to Excel | Top bar "Export open jobs" / "Export all posts", including the employment-type column |
| Fix a wrong field | Job detail page → "Edit fields" (title / city / deadline / type / notes; **notes are included in search**) |

**Two interaction conventions**:

- **Actions never lose context**: open a detail from a filtered list, mark read, add tracking — when you come back, the filters are still applied (previously every operation jumped back to the unfiltered home page)
- **Opened means read**: opening a detail page marks it read automatically; no separate "mark as read" click needed

**Search expands synonyms**: search "律所" and it also hits "律师事务所"; search "聘用制" and it hits "劳动合同制书记员"; search "选调" and it hits "选调生" — measured recall for "律所" went from 28 to 89 postings.

**Notice-kind filtering (important)**: a large share of posts on government channels are not "open for application" jobs but after-the-fact result announcements (proposed-hire name-list publications / written-test scores / cutoff lines / physical-exam reviews). In a measured first batch of 299 posts these made up 23%, and they naturally have no application deadline. The system sorts posts into three kinds — **open / result notice / other info** — and by default shows only the first, so unrelated information doesn't mix in. Procurement inquiries, hearing announcements, paper calls and the like — posts that contain the words "recruitment/open" but are not jobs at all — are also classified as "other info".

**Job types & org names (how it avoids "a pile of unclassified")**:

- Type classification uses **three-level priority**: source-level config (an entire HR-bureau column is public-sector) → title keywords → fallback to "other". Early on only title keywords were used; the lexicon lacked spellings like 大学/医院/管委会/辅导员, so 47% of HR-bureau items fell into "unclassified"; it is now measured at **2.8% (7/252)**
- **Org names are extracted from titles**: government-site list pages have no org field at all, but the org name sits at the head of the title (`广东省高级人民法院2026年度选调…`). `classify.extract_org()` anchors on organization suffixes and only accepts when body text immediately follows; if it cannot extract, it leaves the field **empty** (displaying half a sentence as an org name is worse than showing nothing). Org coverage on open jobs is **98%**
- The campus job boards and the ZUEL API are both tightened: GDUFS/GZHU on-site search is fuzzy matching (searching "法务" also brings back accounting specialists and sales-order management), so an extra local keyword filter is layered on; ZUEL's `majors` field lists every major an employer accepts (a single posting can list 38, law included), so using it as the filter would drag in bank tellers, supply chain and other generic jobs — instead it filters by **whether the job name contains legal role words**, and narrows the fetched position list down to the law-related few (`党工团干事,土木工程师,法务专员` → `法务专员`)

**Archive rule**: 7 days after the deadline a job automatically sinks (`status='archived'`); the home page no longer shows it, but search can always still recall it.

**Dedup rules (two layers)**:

1. **URL fingerprint**: the same URL enters the database only once; tracking parameters such as utm are ignored automatically;
2. **Cross-source merge**: when the same recruitment is posted on several channels, it merges into one card labeled "N sources", with all source links listed on the detail page. The merge conditions are strict — all four must hold: **different sources**, title long enough (≥10 characters), highly similar titles, and publish dates within 45 days of each other.

   Why so strict: an earlier version only compared title similarity, and merged different installments of the same announcement series (a town in Zhongshan publishing its hire list 6 times), same-named announcements from different years (a procuratorate's 2023/2024/2025 selection announcements), and generic job names (different firms' "律师助理") into one — genuine data loss. The rule now is: a missed merge (one extra card) is preferable to a wrong merge (swallowing a real job).

---

## Sources (33, grouped by display priority)

| Category | Sources |
|---|---|
| Courts / procuratorate / military | Guangdong courts site, Guangdong provincial procuratorate, Military Talent Net (civilian recruitment exams; many legal posts, less competition) |
| HR system (public institutions / SOEs / public jobs) | Guangdong provincial HR dept, **provincial HR dept · SOE recruitment zone (JSON API)**, HR bureaus of Guangzhou, Shenzhen, Zhongshan, Zhuhai, Foshan, Dongguan, **Shaoguan ×2** |
| Civil service / selection transfer | Guangdong Organization Work Net · civil-service recruitment (provincial exam + selection-transfer announcements appear here first) |
| SOEs | **Provincial SASAC · "Million Talents Gather in South Guangdong" column** (one source covers dozens of first-tier groups and their second-tier companies), **Yuexiu Group (Dayi system JSON API, aggregates Yuexiu-system subsidiaries)**, Guangdong Energy Group |
| Law firms / bar industry | Foshan bar association (formerly "Guangdong Lawyer Net"), bar associations of Guangzhou / Shenzhen / Zhongshan / Jiangmen / Huizhou |
| University career sites | Guangdong University of Foreign Studies, Guangzhou University, Guangdong University of Finance, Guangzhou College of Commerce (same platform, on-site search by law keywords), **Five Institutes & Four Departments, 5 schools**: Southwest University of Political Science & Law (front-page increments), Tsinghua, Peking University, Wuhan University (frontpage JSON adapter — one reverse-engineering covers two schools), Northwest University of Political Science & Law (cross-node date normalization) |
| External career-center API | Zhongnan University of Economics and Law career center (JSON API, filtered to law jobs by job name) |

**Why SOEs rely on "aggregation columns + JSON APIs" instead of each group's own website**: sampling 9 provincial first-tier group sites showed 4 unreachable / anti-scraping, 4 JS-rendered (Beisen / Dayi / self-built), and only 2 statically scrapable; meanwhile policy requires SOE recruitment information to be published, so the provincial SASAC "Million Talents" column (178 【国企招聘】 announcements) and the provincial HR dept's SOE recruitment zone (a province-wide real-time job stream, server-side filterable by "employer nature = SOE" + job-name keywords) — two aggregation layers — already cover 20+ first-tier groups and their second-tier companies. When another group using Dayi (hotjob.cn) comes up, the adapter is reused by changing one line of config.

The complete list, verification status, and domain traps (which old domains are dead, which sites need an http downgrade or gb2312 decoding) are in [`docs/source-registry.md`](docs/source-registry.md).

Per-source yield (sampled snapshot of 2026-09-15, 543 posts in total; recomputed from the local SQLite database. 29 of the 33 sources were live at that time — only the four schools added later, Tsinghua / Peking / Wuhan / NWUPL, are absent):

| Source | Posts | Note |
|---|---|---|
| Guangdong University of Finance career site | 51 | on-site search with law keywords |
| Provincial HR dept · SOE zone | 48 | POST JSON API, server-side filtered by 6 terms such as 法务/法律 |
| Guangdong University of Foreign Studies career site | 45 | on-site search with law keywords |
| Shenzhen bar association | 40 | the list carries a deadline column directly |
| Dongguan HR bureau | 30 | fills the missing PRD cities |
| Provincial SASAC · Million Talents column | 30 | all 【国企招聘】 announcements, zero noise |
| Guangdong Lawyer Net (Foshan bar) | 30 | |
| Provincial HR dept · public institutions | 27 | |
| Guangdong provincial procuratorate | 25 | gb2312 + http downgrade (see tradeoff 3) |
| Foshan HR bureau | 20 | |
| Shenzhen HR bureau | 20 | runs over http (see tradeoff 2) |
| Zhuhai HR bureau | 20 | |
| Jiangmen bar association | 20 | |
| Yuexiu Group | 17 | Dayi JSON, positionName server-side filter |
| Zhongshan HR bureau | 16 | |
| Guangzhou College of Commerce | 15 | on-site search with law keywords |
| Guangzhou HR bureau | 13 | |
| Shaoguan HR · personnel & talent column | 12 | more focused than the former notices column |
| Guangdong courts site | 11 | |
| Huizhou bar association | 10 | |
| GD Organization Work Net · civil service | 8 | announcement class after title-keyword filtering |
| Zhongshan bar association | 8 | date split across two DOM nodes, now normalized |
| Guangzhou University career site | 7 | on-site search with law keywords |
| Guangdong Energy Group | 6 | law-related jobs after keyword filtering |
| ZUEL career center | 6 | JSON API, filtered to law jobs by job name |
| Guangzhou bar association | 3 | JSP fragment API |
| Military Talent Net | 2 | annual-style updates; the civilian unified-exam notice is exclusive information here |
| Shaoguan HR · notices column | 2 | mostly court service-of-process notices; recruitment posts are sparse |
| Southwest University of Political Science & Law | 1 | front-page increment block; Five & Four schools are high-quality employers |

Counts above sum to 543; derived fields (type / notice kind / long-term flag) reflect the current classification rules re-run on the same 543 posts.

Type distribution: public-sector 244 / law firm 136 / in-house 125 / internship 28 / other 10 (1.8%).
Notice kinds: open 422 / result notices 101 / other info 20.
Employment types: established (bianzhi) 81 / contract 18; long-term (email application) 42.

### Adding a new source

The vast majority of sources need no code — just add one config entry in `scripts/seed_sources.py`:

```python
dict(slug="xxx", **_html(
    "某某市人社局·招聘公告",
    _idx("https://xxx.gov.cn/zpgg/index.html", 2),   # list page (_idx expands pagination automatically)
    "ul.list li",              # item container
    title_attr="title",        # take the title from an attribute (avoids on-page "…" truncation)
    date_sel="span.time",      # publish date
    detail_sel="div.article",  # detail-page body container (empty = auto-pick the most body-like block)
    city="某市", job_type="public")),
```

Then run this "calibration trio":

```bash
.venv/Scripts/python.exe scripts/probe_sources.py          # infer container selector candidates from real pages
.venv/Scripts/python.exe scripts/peek.py <slug> <regex>      # print raw HTML fragments for comparison
.venv/Scripts/python.exe scripts/preview_parse.py <slug>    # preview whether the parsed result is right
.venv/Scripts/python.exe -m pytest tests/test_sources.py -q # fixture regression
```

Full documentation of the config fields is in the comment block at the top of `app/collect/generic_html.py`. Common fields: `list_urls` (multiple entries / pagination), `link_sel`, `title_sel`, `title_attr`, `date_sel`, `org_sel`, `detail_sel`, `no_detail`, `url_scheme`, `keep_keywords`, `title_keywords`, `exclude_url`, `max_age_days`, `detail_budget`, `notice_kind`, `encoding`, `verify`.

### Changed a classification rule?

Derived fields such as `notice_kind` / deadlines can be **recomputed from local snapshots, no re-scraping needed**:

```bash
.venv/Scripts/python.exe scripts/reclassify.py              # recompute everything
.venv/Scripts/python.exe scripts/reclassify.py --kind-only  # recompute notice kinds only (fastest)
.venv/Scripts/python.exe scripts/reclassify.py --refresh-org  # also re-extract org names
```

Org names are **sticky** by default: an org name explicitly given on a list page is more reliable than one guessed from a title, so existing values are never overwritten; only with `--refresh-org` are they re-extracted under the new rules (if extraction fails, the old value is kept).

<details>
<summary><strong>Interface design details</strong> (fonts, themes, motion, layout rules)</summary>

The app is positioned as a **single-machine, high-frequency tool**, so the layout is designed "density first" with no decoration:

- **First-screen overview numbers**: openable total / closing within 3 days / closing within 7 days / new today — you know what to look at today the moment the page opens (closing-within-3-days is red)
- **Lists align by column for scanning**: deadline / type / city / title / org / source, each row 34px, one screen (1000px tall) shows about 28 jobs; a 2px bar at the row head marks urgency (red = within 3 days, yellow = within 7), cheaper in space than text labels; type uses a 6px dot (law-firm purple / public-sector blue / in-house teal / internship amber), which saves width versus full color chips while keeping a scanning cue
- **Light and dark themes**: the tri-state button at the top right cycles **follow system → light → dark**, and the choice is stored in localStorage. The first frame's theme is pinned by an inline script inside `<head>`, so it **never flashes white/black**; both palettes were verified at 4.5:1 contrast for small text (`scripts/contrast_check.py` re-checks it)
- **Motion is restrained and meaningful**: list rows float up 160ms with a stagger (only the first 12 rows, ~300ms total), the left bar widens on row hover, buttons shift on press, cards lift slightly on hover, and the whole page cross-fades colors in 220ms when the theme changes. Large blocks (filter bar, overview bar, body, board) **deliberately get no fade-in** — they are the page's main content; if they render slowly, a page-wide "grey veil" is worse than nothing. All motion turns off automatically under `prefers-reduced-motion`
- **The design spec is written down** (converged in iteration 7 to a Linear/Notion-style minimal tool look; the rules live as comments in `style.css`, each checkable): control heights only come in two steps (28px standard / 24px inline); **numbers are always neutral-colored**, color is reserved for actionable semantics (within 3 days = red, within 7 = yellow); inline buttons default to neutral grey and light up only on hover; the filter bar is a panel, forming three layers with the overview bar and the list
- **Narrow screens (<880px)**: the list collapses into a two-line-per-row form with no information removed; dropdowns **filter the moment you pick** (no "Filter" button), and the search box submits on Enter

The typeface is **Noto Sans SC**, and it is **self-hosted**: `scripts/localize_font.py` downloads only the glyph slices the pages actually use, split by unicode-range (~72 slices / 2MB), so display works offline and nothing depends on a font CDN.

If you changed copy or added new postings and want to top up font coverage, just re-run it:

```bash
.venv/Scripts/python.exe scripts/localize_font.py     # recompute the character set and fill in missing slices
```

Styles and scripts live in `app/web/static/` (`style.css` + `app.js` + `i18n.js`); refresh the page after editing and they take effect (the links carry an mtime version, so the browser cache never holds you back). To actually see a visual change:

```bash
.venv/Scripts/python.exe scripts/dev_shots.py --theme light --out D:/shots \
    "list=/" 1400x1000 "detail=/jobs/1" 1280x700
.venv/Scripts/python.exe scripts/dev_shots.py --theme dark --out D:/shots "list=/"
```

</details>

---

## Project layout

```
app/
  db.py            SQLite schema, FTS full-text index, auto-archiving, column migration for old DBs
  dedup.py         URL fingerprint + cross-source merge rules
  dateparse.py     Chinese date parsing + deadline anchoring/extraction
  classify.py      Job type / city / notice kind / org-name extraction (extract_org)
  snapshot.py      Detail-page body snapshots (local archive; readable even if the source deletes the post)
  collect/
    http.py        Fetching with retries and a connection pool (4xx and hard TLS failures are not retried)
    generic_html.py Config-driven generic list adapter
    zuel.py        ZUEL JSON API adapter (filtered to law jobs by job name)
    pastebox.py    Paste box (paste a link, fetch the body)
    store.py       Saving and cross-source merging
    runner.py      Collection scheduling, source-level config injection, source health records, optional Windows notifications
  web/
    main.py        App entry + daily scheduled jobs + Jinja filters
    routes.py      All routes (list / detail / board / paste box / health / settings / export) + first-screen overview numbers
    snapshot_view.py Snapshot structured layout (key-info card / section headings / HTML escaping)
    static/        style.css (light+dark themes + design spec + motion), app.js (theme switch), i18n.js (UI language), local fonts
    templates/     Jinja2 templates
scripts/
  seed_sources.py      Source configs (**add sources here**)
  sync_fixtures.py     Record real pages as test fixtures
  probe_sources.py / peek.py / preview_parse.py   Selector calibration trio
  reclassify.py        Recompute derived fields from local snapshots
  localize_font.py     Download Noto Sans SC glyph slices by page character set (self-hosted)
  contrast_check.py    Verify both themes' palette contrast (WCAG AA)
  dev_shots.py         Batch screenshots to check visuals (can force light/dark)
  png_probe.py / png_crop.py  Sample/crop screenshots without installing Pillow, to verify colors really took effect
tests/                 192 tests, including real-page fixture regression for all 33 sources
docs/
  source-registry.md                     Full source list and domain traps
  iterations.md                          Iteration log (7 rounds, each with research/execution/verification)
  superpowers/specs/...-design.md        Design document
  superpowers/plans/...-legal-job-tracker.md  Implementation plan and acceptance records
```

---

## Performance & stability

- First full collection: **about 2~5 minutes** (33 sources, 6 concurrent detail fetches, a 90-second per-source detail budget as the backstop)
- Routine incremental collection: **about 10 seconds** (known URLs skip detail fetching; only new items are processed)
- **Collection timing**: one round at 08:05 and one at 20:05 daily (the evening round exists so announcements published that afternoon don't wait until the next day); **the service doesn't have to run every day** — at startup, if today's collection hasn't happened yet, it runs one immediately
- Slow-site protection: each source has a 90-second (60 for slow sites) detail-fetch budget; past the budget, remaining items keep only title/date with an empty body — this keeps slow sites like Shenzhen HR from dragging a full round from 1 minute to 10+ minutes
- Failure isolation: a single source's failure is only recorded to `/health` and does not affect other sources; with desktop notifications enabled, the post-collection notification also reports how many sources failed

## Known tradeoffs

1. **Selector drift**: a site redesign can break one source's parsing — `tests/test_sources.py` runs fixture regression on real pages and `/health` shows source health. Each of the 33 sources has a page recorded in 2026-09; after a redesign this fails first, prompting recalibration.
2. **Shenzhen HR runs over http**: its https handshake fails under this machine's OpenSSL 3 (BAD_ECPOINT), so the config forces a downgrade with `url_scheme: "http"`.
3. **Provincial procuratorate needs gb2312**: configured with `encoding: "gb2312"` + http downgrade.
4. **JS-rendered sites** (Shenzhen/Guangzhou intermediate courts, Dongguan bar association, China Southern Power Grid, etc.) are out of scope for now; coverage comes from upstream aggregation sources (Guangdong courts site / provincial HR dept) and the paste box.
5. **GDUFS/GZHU job boards** render detail pages in JS, so the "major requirements" field is unobtainable; instead the site's own `?keyword=` search is used to find law-related jobs, and because that search is fuzzy, a local keyword filter is layered on top.
6. **Shaoguan postings are sparse**: the Shaoguan HR columns are mostly court service-of-process notices, about 2 recruitment posts per page; Shaoguan jobs are mainly covered by the provincial HR dept's centralized recruitment announcements.
7. **ZUEL API keeps only law jobs**: the API's `majors` field lists all majors an employer accepts and cannot be used to filter for law; filtering is by whether the job name contains legal role words. The cost: records "aimed at law majors but with generic job names" (e.g. "management trainee") get dropped — in exchange the list no longer mixes in bank tellers, supply chain and other noise.
8. **Deadlines are never forced**: a date is taken only from sentences containing words like "deadline/signup/application"; if none, the field stays empty. An early version took the largest date in the whole text, mistaking physical-exam times, exam times and even "age cutoff is the signup start day" for application deadlines (70 of 213 clearly wrong). Now only 3 of 79 are suspect — **a wrong deadline is worse than no deadline**, because it creates fake red urgency alerts.
9. **Org name stays empty when extraction fails**: `extract_org` only accepts when it can confirm "organization suffix + body immediately following", so titles like "关于2025年度劳动合同制书记员招聘笔试安排的公告" that never name an org leave the column empty. Org coverage on open jobs is 98%; the remaining 2% genuinely have nothing to extract.
10. **"New today" is huge on day one**: the first collection counts everything stored that day; from the second day it falls back to normal.
11. **Merging only happens at save time**: duplicates stored before the cross-source merge was fixed do not merge automatically (auto-merging historical data is risky). Newly scraped duplicate jobs merge normally; for old data that looks duplicated, archive one of them manually.

---

## Testing

```bash
.venv/Scripts/python.exe -m pytest tests/ -q     # 192 passed
.venv/Scripts/python.exe scripts/contrast_check.py   # self-check contrast for both themes' palettes
```

- Unit tests: dedup (including 3 classes of false-merge regression + short-title-with-org merges), date parsing (including deadline-year anchoring), classification (including org extraction, employment type, long-term, and source-level config injection regressions), storage, HTTP retry strategy, resume parsing and match scoring, snapshot structuring (key-info card / section headings / HTML escaping), web routes and filters (including synonyms, bulk operations, filters-preserved-on-return, auto-mark-read), export
- Fixture regression: each of the 33 sources has a real recorded page, verifying the selectors still parse items
- Fixture recording time: 2026-09 (tests use a fixed baseline date, so they don't decay as real dates move)

---

## Open-source notes

- **License**: MIT (see [LICENSE](LICENSE))
- Resumes, profiles, the job library, and application records are **stored only locally** in `data/` (gitignored); the code itself contains no user data; `tests/fixtures/` are page fragments recorded from public official sites
- Issues / PRs welcome: adding a new source (just edit `scripts/seed_sources.py` config), fixing adapters, adding cities. Run `pytest tests/ -q` before a PR and keep it all green
