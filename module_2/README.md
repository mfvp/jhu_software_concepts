# Module 2 — Web Scraping: Grad Cafe Applicant Data

**Name:** Mateus Pereira  
**JHED ID:** mpereira  
**Module:** Module 2 — Web Scraping with Python  
**Assignment:** Scraping Grad Cafe Applicant Data  
**Due Date:** See Canvas

---

## Approach

### Overview

This assignment scrapes publicly available graduate school applicant data from
[The Grad Cafe](https://www.thegradcafe.com/survey/) and produces a structured
JSON dataset of 30,000+ applicant entries. The data is then cleaned and
standardized using a locally hosted small language model (TinyLlama 1.1B via
`llama-cpp-python`) to normalize inconsistent program and university names.

### Scraping Workflow (Hybrid: urllib + Selenium + BeautifulSoup)

1. **urllib** — used to construct and inspect all URLs via
   `urllib.parse.urlencode`, check robots.txt via
   `urllib.robotparser.RobotFileParser`, and validate that we are allowed to
   scrape the survey pages before any requests are made.

2. **Selenium** — used to load each paginated survey results page in a headless
   Chrome browser. Grad Cafe uses a React frontend; the applicant data is only
   present in the DOM after JavaScript executes. Selenium Manager (bundled with
   Selenium 4+) automatically handles ChromeDriver setup — no manual driver
   download required.

3. **BeautifulSoup** — after Selenium renders the page, `driver.page_source` is
   passed to BeautifulSoup for HTML parsing. Column headers are extracted from
   `<thead>` to build a mapping of column name → cell index, which makes the
   per-row parsing robust to minor layout changes. Multiple CSS selector
   fallbacks are used to handle different page layouts.

4. **Polite scraping** — a random delay of 2.5–5.5 s is inserted between every
   page request (`random.uniform(MIN_DELAY, MAX_DELAY)`). The scraper also
   detects HTTP 429 / rate-limit language in the page text and stops
   immediately if the site signals it is being overloaded.

5. **Data is saved incrementally** every 50 pages so no progress is lost if the
   script is interrupted.

### Data Cleaning Workflow

`clean.py` applies the following cleaning passes to each entry:

- Strips leftover HTML tags and decodes HTML entities (e.g., `&amp;` → `&`).
- Normalises null-like strings (`"N/A"`, `"--"`, `""`) to Python `None`.
- Standardises `status` to one of: `Accepted`, `Rejected`, `Waitlisted`,
  `Interview`, `Other`.
- Standardises `degree` to `Masters` or `PhD`.
- Validates numeric scores: GPA ∈ [0.0, 4.5]; GRE total ∈ [260, 340];
  GRE V ∈ [130, 170]; GRE AW ∈ [0.0, 6.0].
- Ensures every entry has all expected keys (missing fields → `None`).
- The original `program` field is always preserved unchanged for
  traceability/reproducibility.

After `clean.py`, the LLM standardisation step is run:

```bash
python module_2/llm_hosting/app.py --file module_2/applicant_data.json --stdout > module_2/llm_extend_applicant_data.json
```

This appends two new fields to every entry:

| Field | Description |
|---|---|
| `llm-generated-program` | LLM-standardised program name (e.g., "Computer Science") |
| `llm-generated-university` | LLM-standardised university name (e.g., "MIT" → "Massachusetts Institute of Technology") |

### Scraping Tool Used

- **Browser/driver:** Chrome + Selenium Manager (automatic ChromeDriver download)
- **Mode:** headless Chrome (`--headless=new`)
- **Workflow:** urllib (URL management) → Selenium (page render) → BeautifulSoup (HTML parse)

---

## robots.txt Compliance

### Evidence

See `screenshot.jpg` in this folder. It shows:

1. The URL `https://www.thegradcafe.com/robots.txt` loaded in a browser-like
   environment.
2. The content of the robots.txt file confirming that the `/survey/` path is
   not disallowed for any user-agent.

The screenshot was generated automatically during the first run of `scrape.py`
via the `_take_robots_screenshot()` function, which uses Selenium to navigate to
the robots.txt URL and calls `driver.save_screenshot("screenshot.jpg")`.

### Programmatic Check

Before any scraping begins, `scrape.py` calls:

```python
rp = urllib.robotparser.RobotFileParser()
rp.set_url("https://www.thegradcafe.com/robots.txt")
rp.read()
allowed = rp.can_fetch("*", "https://www.thegradcafe.com/survey/")
```

If `allowed` is `False`, the scraper exits immediately without making any
further requests.

### Compliance Summary

- Only publicly accessible survey result pages are scraped.
- No login, CAPTCHA bypass, or access control circumvention is used.
- Random delays (2.5–5.5 s) are inserted between every page request.
- The scraper stops immediately if the site returns rate-limit signals.

---

## Setup & Installation

### Requirements

- Python 3.10 or later
- Google Chrome (for Selenium)

### Install dependencies

```bash
cd module_2
pip install -r requirements.txt
```

For the LLM cleaning step, install the additional dependencies:

```bash
cd module_2/llm_hosting
pip install -r requirements.txt
```

> **Note:** `llama-cpp-python` compiles a C extension. On Windows you may need
> Visual C++ Build Tools. The first run of `app.py` will automatically download
> the TinyLlama 1.1B GGUF model (~700 MB) from Hugging Face.

---

## Running the Scraper

```bash
# from the repo root
python module_2/scrape.py
```

This will:

1. Check robots.txt.
2. Take a screenshot of the robots.txt page → `module_2/screenshot.jpg`.
3. Scrape all paginated survey pages (up to 900 pages).
4. Save results to `module_2/applicant_data.json`.

Expected run time: 2–4 hours depending on network speed and site response.

---

## Running the Data Cleaner

```bash
python module_2/clean.py
```

Reads `applicant_data.json`, cleans all fields, and overwrites the file with
cleaned data.

---

## Running the LLM Standardiser

```bash
# from module_2/llm_hosting/
python app.py --file ../applicant_data.json --stdout > ../llm_extend_applicant_data.json
```

To run faster using all CPU cores:

```bash
python app.py --file ../applicant_data.json --stdout --workers 8 > ../llm_extend_applicant_data.json
```

---

## Output Files

| File | Description |
|---|---|
| `applicant_data.json` | Cleaned scraped data (30,000+ entries) |
| `llm_extend_applicant_data.json` | Same data + `llm-generated-program` and `llm-generated-university` fields |
| `screenshot.jpg` | Evidence that robots.txt was checked before scraping |

---

## JSON Structure

Each entry in `applicant_data.json` has these fields:

```json
{
  "program": "Computer Science, MIT  ",
  "program_name": "Computer Science",
  "university": "MIT",
  "degree": "PhD",
  "status": "Accepted",
  "decision_date": "15 Feb",
  "date_added": "Added on February 20, 2024",
  "semester": "Fall",
  "year": 2024,
  "applicant_type": "International",
  "gpa": 3.95,
  "gre_total": 329,
  "gre_v": 162,
  "gre_aw": 5.0,
  "comments": "Received email from POI a week before.",
  "url": "https://www.thegradcafe.com/result/935501"
}
```

`llm_extend_applicant_data.json` adds:

```json
{
  "llm-generated-program": "Computer Science",
  "llm-generated-university": "Massachusetts Institute of Technology"
}
```

Missing or unavailable values are represented as `null`.

---

## LLM Cleaning: Changes and Edge Cases

### Fixes required to get the original app running on Windows

The provided `llm_hosting/app.py` was written for Replit and needed several fixes before it would run locally on Windows:

- **HuggingFace deprecated arguments** — `hf_hub_download` was called with `force_filename` and `local_dir_use_symlinks`, both removed in newer versions of `huggingface_hub`. Removed both arguments.
- **Re-downloading model on every run** — `hf_hub_download` made a network request on every invocation even when the GGUF file was already on disk. Fixed `_load_llm()` to check `llm_hosting/models/` first and skip the download if the file exists.
- **Unicode encoding crash on Windows** — Writing Unicode characters (e.g., accented letters in university names) to stdout raised a `UnicodeEncodeError` because Windows defaults stdout to `cp1252`. Fixed by writing bytes directly to `sys.stdout.buffer` with explicit UTF-8 encoding.
- **No crash recovery** — The original code held all results in memory and only wrote the output file at the very end. A crash after hours of processing lost all progress. Added a `--checkpoint` file that saves each completed row to disk immediately so the next run resumes from where it left off.
- **Threading did not parallelize inference** — The original `ThreadPoolExecutor` approach was limited by `_LLM_LOCK`, which forced all threads to share a single model sequentially. Replaced with `ProcessPoolExecutor` so each worker process loads its own model instance and inference runs truly in parallel.

### Changes to canonical lists

- No structural changes were made to `canon_universities.txt` or
  `canon_programs.txt` — the provided lists are comprehensive.
- Additional abbreviation mappings were added to `app.py`'s `ABBREV_UNI` dict
  to handle common Grad Cafe shorthand: `JHU`, `MIT`, `CMU`, `UIUC`, `UMich`,
  `UCLA`, `UCB`, `UCSD`, `USC`, `NYU`, `GaTech`, `UPenn`, `BU`, `PSU`.

### Systematic edge cases observed

1. **Combined program+university fields** — Grad Cafe stores both in one string
   (e.g., `"Computer Science, MIT"`). The LLM correctly splits these in most
   cases; edge cases occur when the program name itself contains a comma
   (e.g., `"Statistics, Machine Learning, CMU"`).

2. **Abbreviated/misspelled universities** — Common short forms like `"McG"`,
   `"UBC"`, `"JHU"` are resolved correctly by the expanded `ABBREV_UNI` map
   before the LLM is even called.

3. **Remaining imperfections** — Very unusual or heavily abbreviated entries
   (e.g., `"Comp Sci, Somewhere U"`) may still produce generic outputs like
   `"Unknown"` for the university. These are a small minority of entries and
   will be investigated in Module 3 analysis.

---

## Known Bugs

- The scraper relies on BeautifulSoup selectors tuned to Grad Cafe's current
  HTML structure (verified during development). If the site undergoes a major
  redesign, the column-header detection in `_get_column_headers()` may need
  updating.
- Entries with no `program` text and no `url` field are silently dropped by
  `clean.py`. This is intentional (they carry no useful data) but means the
  final count may be slightly lower than the raw scraped count.
