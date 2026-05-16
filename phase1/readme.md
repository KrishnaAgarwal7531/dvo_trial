# Phase 1 — Person Research Pipeline

## What It Does
Given a person's name (and optionally their company), this pipeline automatically finds and extracts:
- **Age**
- **Nationality**
- **Net Worth**
- **Education** (degree + university)

---

## File Structure

```
phase1/
├── phase_1.py            ← START HERE — main file you run
├── phase_1_search.py     ← searches the web for relevant pages
├── phase_1_extract.py    ← sends each page to the local LLM for extraction
├── phase_1_aggregate.py  ← picks the best answer per field using logic
└── phase_1_utils.py      ← shared config, API keys, and helper functions
```

---

## Before Running — Set Your API Keys

Open `phase_1_utils.py` and replace the placeholder values at the top:

```python
TINYFISH_API_KEY = "your_tinyfish_key_here"
TAVILY_API_KEY   = "your_tavily_key_here"
```

These are the only two keys needed. Ollama runs locally so no key is required for the LLM.

---

## How It Works

**Step 1 — Search** (`phase_1_search.py`)

Two searches run in parallel:
- **TinyFish** — searches the web, finds up to 15 URLs, then fetches the full content of each page
- **Tavily** — runs 7 targeted queries (DOB, nationality, net worth, education etc.) and returns cached snippets

Both results are combined and deduplicated — if the same URL appears in both, the longer version is kept.

**Step 2 — Extract** (`phase_1_extract.py`)

Every page is sent to the local LLM (Qwen2.5:7b via Ollama) in parallel. Each LLM call reads one page and returns a structured JSON with whatever it finds:
```json
{
  "dob": "November 01, 1960",
  "age": 65,
  "article_year": 2024,
  "nationality": "United States",
  "net_worth": "$2.9 Billion",
  "net_worth_year": 2025,
  "degree": "Bachelor of Science in Industrial Engineering",
  "institution": "Auburn University"
}
```
If a field is not on that page, it returns `null` — the LLM is instructed never to guess.

**Step 3 — Aggregate** (`phase_1_aggregate.py`)

Python logic picks the best answer per field from all the extractions:
- **Age** — DOB entries and age numbers are all normalised to the current year, then the most frequent value wins. If 2+ sources agree on the same DOB, that takes priority.
- **Nationality** — simple frequency vote, most mentioned country wins.
- **Net Worth** — credible sources (Forbes, Bloomberg, Reuters, WSJ) always win. Among credible sources, the most recent year wins.
- **Education** — degrees are grouped by university. If multiple sources give different names for the same degree at the same university, the LLM is called once more to resolve them into a clean canonical name. Python also ensures no two entries at the same level (Bachelor/Master/PhD) survive from the same university.

**Step 4 — Display** (`phase_1.py`)

Final results are printed cleanly with the source URL for each field.

---

## How To Run

**Prerequisites**
- Ollama installed and running with `qwen2.5:7b` pulled
- Python packages: `requests`

**Run Phase 1**
```bash
python phase_1.py
```

Or pass the name and company directly:
```bash
python phase_1.py "Tim Cook" "Apple"
python phase_1.py "Daniel Teo Tong How" "Hong How Group"
python phase_1.py "Sun Xiushun"
```

To change the default name, open `phase_1.py` and edit the top two lines:
```python
NAME    = "Chen Tianqiao"
COMPANY = "Shanda Group"
```

**Run Phase 2**

Phase 1 output feeds directly into Phase 2. Once Phase 1 finishes, run:
```bash
python phase_2.py
```

Phase 2 takes the fields that Phase 1 could not find (marked as `Not found`) and runs a deeper search on them.

---

**Expected output**
```
=================================================================
  PHASE 1 — Person Research Pipeline
  Name   : Tim Cook
  Company: Apple
=================================================================

  STEP 1/4 — Searching for relevant pages...
  STEP 2/4 — Extracting structured data from each page...
  STEP 3/4 — Aggregating results...
  STEP 4/4 — Final results:

=================================================================
  RESULTS: Tim Cook
=================================================================
  Age         : 65 | britannica.com
  Nationality : United States | en.wikipedia.org
  Net Worth   : $2.9 Billion (2025) | forbes.com
  Education   :
    - Bachelor of Science in Industrial Engineering, Auburn University | apple.com
    - Master of Business Administration, Duke University | wikipedia.org
=================================================================
```
