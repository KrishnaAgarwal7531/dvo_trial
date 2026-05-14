import concurrent.futures
from phase_1_utils import ask_llm, fmt_source


def _build_validation_prompt(name: str, company: str, url: str, text: str) -> str:
    company_line = f"  - Known company/organisation: {company}" if company else ""
    return f"""You are checking whether a webpage is actually about a specific person.

Person we are researching:
  - Name: {name}{company_line}

Source URL: {url}

Page content (first 2000 chars):
{text[:2000]}

Your job is to decide: does this page contain real biographical or professional information
about THIS specific person — the one named above?

Rules:
- Return "yes" ONLY if the page clearly discusses the specific individual named above
  (e.g. their career, biography, net worth, education, business dealings, awards, interviews, etc.)
- Return "no" if:
    * The page is about a DIFFERENT person who happens to share the same name
    * The name appears only incidentally (e.g. in a list, passing mention, unrelated context)
    * The page is a generic directory, search results page, or placeholder with no real content
    * The page content is mostly irrelevant to the person (e.g. a company page where this
      person is only a footnote)
    * The page is clearly about a company/org but does NOT discuss this person personally
- If the company is provided and the page discusses that company AND the person together,
  that is a strong signal to return "yes"
- If the name is common and the page gives no clear signals it's the right person, return "no"

Return ONLY a JSON object, no explanation, no markdown:
{{
  "is_valid": true or false,
  "confidence": "high" or "medium" or "low",
  "reason": "one short sentence explaining your decision"
}}"""


def validate_page(page: dict, name: str, company: str) -> dict:
    """
    Returns the original page dict with two new keys added:
      - "_valid"      : bool  — whether this page is about the right person
      - "_val_reason" : str   — short explanation from the LLM
    """
    url    = page["url"]
    text   = page["text"]
    prompt = _build_validation_prompt(name, company, url, text)
    raw    = ask_llm(prompt)

    # Parse the JSON response
    import re, json
    raw = re.sub(r"```json|```", "", raw).strip()
    try:
        parsed = json.loads(raw)
        is_valid   = bool(parsed.get("is_valid", False))
        confidence = parsed.get("confidence", "low")
        reason     = parsed.get("reason", "")
    except Exception:
        # If LLM returned malformed JSON, fail safe — mark as invalid
        is_valid   = False
        confidence = "low"
        reason     = "could not parse LLM response"

    return {
        **page,
        "_valid":      is_valid,
        "_confidence": confidence,
        "_val_reason": reason,
    }


def validate_all(pages: list, name: str, company: str = "") -> list:
    """
    Runs validation in parallel across all pages.
    Returns two lists: (valid_pages, rejected_pages)
    Prints a summary table to stdout.
    """
    print(f"\n  [Validation] Checking {len(pages)} pages are actually about '{name}'...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(pages)) as executor:
        results = list(executor.map(
            lambda p: validate_page(p, name, company),
            pages
        ))

    print(f"\n{'='*65}")
    print(f"  VALIDATION RESULTS")
    print(f"{'='*65}")

    valid_pages    = []
    rejected_pages = []

    for r in results:
        src    = r.get("url", "")
        domain = src.split("/")[2] if src.count("/") >= 2 else src
        status = "✓ VALID   " if r["_valid"] else "✗ REJECTED"
        conf   = r["_confidence"].upper()
        reason = r["_val_reason"]
        print(f"  {status} [{conf:6s}] {src}")
        print(f"             → {reason}")
import concurrent.futures
from phase_1_utils import ask_llm, fmt_source


# ── VALIDATION PROMPT ─────────────────────────────────────────────────────────

def _build_validation_prompt(name: str, company: str, url: str, text: str) -> str:
    company_line = f"  - Known company/organisation: {company}" if company else ""
    return f"""You are checking whether a webpage is actually about a specific person.

Person we are researching:
  - Name: {name}{company_line}

Source URL: {url}

Page content (first 2000 chars):
{text[:2000]}

Your job is to decide: does this page contain real biographical or professional information
about THIS specific person — the one named above?

Rules:
- Return "yes" ONLY if the page clearly discusses the specific individual named above
  (e.g. their career, biography, net worth, education, business dealings, awards, interviews, etc.)
- Return "no" if:
    * The page is about a DIFFERENT person who happens to share the same name
    * The name appears only incidentally (e.g. in a list, passing mention, unrelated context)
    * The page is a generic directory, search results page, or placeholder with no real content
    * The page content is mostly irrelevant to the person (e.g. a company page where this
      person is only a footnote)
    * The page is clearly about a company/org but does NOT discuss this person personally
- If the company is provided and the page discusses that company AND the person together,
  that is a strong signal to return "yes"
- If the name is common and the page gives no clear signals it's the right person, return "no"

You MUST respond with ONLY this exact JSON on a single line, nothing else — no preamble, no explanation, no markdown, no backticks:
{{"is_valid": true, "confidence": "high", "reason": "your reason here"}}"""


# ── JSON PARSING WITH FALLBACKS ───────────────────────────────────────────────

def _parse_validation_response(raw: str):
    """
    Three-layer parsing:
      1. Direct JSON parse after stripping markdown fences
      2. Extract first JSON object via regex, then parse
      3. Keyword scan for true/false as last resort
    Returns (is_valid, confidence, reason)
    """
    import re, json

    # Layer 1 — strip markdown fences and try direct parse
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        parsed     = json.loads(cleaned)
        is_valid   = bool(parsed.get("is_valid", False))
        confidence = parsed.get("confidence", "low")
        reason     = parsed.get("reason", "parsed ok")
        return is_valid, confidence, reason
    except Exception:
        pass

    # Layer 2 — extract first {...} block and try again
    match = re.search(r'\{[^{}]+\}', cleaned, re.DOTALL)
    if match:
        try:
            parsed     = json.loads(match.group())
            is_valid   = bool(parsed.get("is_valid", False))
            confidence = parsed.get("confidence", "low")
            reason     = parsed.get("reason", "extracted from partial JSON")
            return is_valid, confidence, reason
        except Exception:
            pass

    # Layer 3 — keyword scan on raw text
    lower = raw.lower()
    if '"is_valid": true' in lower or '"is_valid":true' in lower:
        return True, "medium", "keyword fallback: is_valid true found in response"
    if '"is_valid": false' in lower or '"is_valid":false' in lower:
        return False, "medium", "keyword fallback: is_valid false found in response"

    # Total failure
    return False, "low", "could not parse LLM response"


# ── PER-PAGE VALIDATION ───────────────────────────────────────────────────────

def validate_page(page: dict, name: str, company: str) -> dict:
    """
    Returns the original page dict with new keys:
      - "_valid"      : bool — whether this page is about the right person
      - "_confidence" : str  — high / medium / low
      - "_val_reason" : str  — short explanation
    """
    url    = page["url"]
    text   = page["text"]
    prompt = _build_validation_prompt(name, company, url, text)

    # Attempt 1
    raw = ask_llm(prompt)
    is_valid, confidence, reason = _parse_validation_response(raw)

    # Retry once if parsing totally failed
    if reason == "could not parse LLM response":
        print(f"    [Validation] Parse failed for {url[:60]}... — retrying")
        raw = ask_llm(prompt)
        is_valid, confidence, reason = _parse_validation_response(raw)

    return {
        **page,
        "_valid":      is_valid,
        "_confidence": confidence,
        "_val_reason": reason,
    }


# ── BATCH VALIDATION ──────────────────────────────────────────────────────────

def validate_all(pages: list, name: str, company: str = "") -> list:
    """
    Runs validation in parallel across all pages.
    Returns two lists: (valid_pages, rejected_pages)
    Prints a summary table to stdout.
    """
    print(f"\n  [Validation] Checking {len(pages)} pages are actually about '{name}'...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(pages)) as executor:
        results = list(executor.map(
            lambda p: validate_page(p, name, company),
            pages
        ))

    # ── Print summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  VALIDATION RESULTS")
    print(f"{'='*65}")

    valid_pages    = []
    rejected_pages = []

    for r in results:
        src    = r.get("url", "")
        status = "✓ VALID   " if r["_valid"] else "✗ REJECTED"
        conf   = r["_confidence"].upper()
        reason = r["_val_reason"]
        print(f"  {status} [{conf:6s}] {src}")
        print(f"             → {reason}")

        if r["_valid"]:
            valid_pages.append(r)
        else:
            rejected_pages.append(r)

    print(f"\n  Summary: {len(valid_pages)} valid, {len(rejected_pages)} rejected "
          f"(from {len(pages)} total)")

    # ── Safety net — if everything got rejected, keep high/medium confidence ones ──
    if not valid_pages and rejected_pages:
        salvageable = [r for r in rejected_pages if r["_confidence"] in ("high", "medium")]
        if salvageable:
            print(f"\n  ⚠  All pages rejected — salvaging {len(salvageable)} medium/high-confidence pages")
            valid_pages    = salvageable
            rejected_pages = [r for r in rejected_pages if r not in salvageable]

    print(f"{'='*65}")
    return valid_pages, rejected_pages