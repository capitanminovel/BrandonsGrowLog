#!/usr/bin/env python3
"""
Fetch strain research directly from pigtailgardens.com and update research_cache.json.

Must be run from your LOCAL machine — pigtailgardens.com blocks cloud server IPs.

Setup (one time):
    pip install requests beautifulsoup4 anthropic playwright
    playwright install chromium

Usage:
    python scripts/fetch_ptg.py                  # fetch all known PTG strains
    python scripts/fetch_ptg.py --discover       # list all current PTG product URLs
    python scripts/fetch_ptg.py <ptg_url>        # fetch one specific PTG product page
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from anthropic import Anthropic

BASE = Path(__file__).parent.parent
STRAINS_FILE = BASE / "data" / "strains.json"
RESEARCH_FILE = BASE / "data" / "research_cache.json"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
}

# Known PTG product page URLs mapped to strain IDs in strains.json
# Add new entries here as you acquire more cuts from PTG
PTG_URLS = {
    "pineapples-in-space-4": "https://www.pigtailgardens.com/product-page/pineapples-in-space-4-pineapple-tart-x-space-runtz",
    "rainbow-runtz":          "https://www.pigtailgardens.com/product-page/rainbow-runtz-laughing-gas-x-runtz-crew",
    "jam-pack-2":             "https://www.pigtailgardens.com/product-page/jam-pack-2-preorder-pig-tail-gardens",
    "cherry-jealousy":        "https://www.pigtailgardens.com/product-page/cherry-jealousy-pig-tail-gardens",
    "limecicle":              "https://www.pigtailgardens.com/product-page/limecicle-zkittlez-x-strawberry-zkillato-duke-of-erb",
    "papayamosa":             "https://www.pigtailgardens.com/product-page/papayamosa-lcg-x-bluberry-mimosa-duke-of-erb",
    "cream-smoothie":         "https://www.pigtailgardens.com/product-page/cream-smoothie-fiya-farmer",
    "blue-nerdz":             "https://www.pigtailgardens.com/product-page/blue-nerdz-sherb-money-runtz-crew",
    "blue-dream":             "https://www.pigtailgardens.com/product-page/blue-dream-heirloom-cut-from-santa-cruz",
    "skywalker-og":           "https://www.pigtailgardens.com/product-page/skywalker-og-heirloom-cut-from-hollywood",
    "kush-mintz":             "https://www.pigtailgardens.com/product-page/kush-mints-rabid-hippie-cut",
}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_with_requests(url: str) -> str | None:
    """Simple requests fetch — works if PTG doesn't block your IP."""
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"    requests → HTTP {resp.status_code}")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Wix pages often return a JS shell with no real content when blocked
        if len(text) < 400 or "product" not in text.lower():
            print(f"    requests → got {len(text)} chars but no product content (likely JS-only shell)")
            return None
        return text
    except Exception as e:
        print(f"    requests → error: {e}")
        return None


def fetch_with_playwright(url: str) -> str | None:
    """Headless Chromium fetch via Playwright — handles JS-rendered pages."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("    playwright not installed. Run: pip install playwright && playwright install chromium")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=20000)
            # Wait for the product description to appear
            try:
                page.wait_for_selector("[data-testid='richTextElement'], .wixui-rich-text, p", timeout=8000)
            except Exception:
                pass
            content = page.inner_text("body")
            browser.close()
            if len(content) < 400:
                print(f"    playwright → only {len(content)} chars")
                return None
            return content
    except Exception as e:
        print(f"    playwright → error: {e}")
        return None


def fetch_page(url: str) -> str | None:
    """Try requests first, fall back to Playwright."""
    print(f"    Trying requests...")
    text = fetch_with_requests(url)
    if text:
        print(f"    Got {len(text)} chars via requests")
        return text
    print(f"    Trying Playwright (headless browser)...")
    text = fetch_with_playwright(url)
    if text:
        print(f"    Got {len(text)} chars via Playwright")
    return text


# ---------------------------------------------------------------------------
# Research extraction
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are extracting cannabis strain research data from a Pig Tail Gardens product page.

Strain ID: {strain_id}
Strain Name: {strain_name}

Page content:
{page_text}

Extract all available information and return ONLY valid JSON with these exact six keys:

{{
  "genetics_lineage": "3-4 sentences: parent strains, full genetic lineage, breeder background, provenance from PTG, what makes this cultivar sought after. Use exact wording from the page where possible.",
  "terpene_profile": "3-4 sentences: dominant and secondary terpenes, their aromas and synergies, how expression develops through cure.",
  "effects": "3-4 sentences: onset character, cerebral vs body balance, intensity, duration, best use cases.",
  "flavor_aroma": "3-4 sentences: inhale/exhale flavor, aroma at late flower, harvest, fresh cure, and long cure.",
  "grow_notes": "3-4 sentences: structure and stretch, flowering time, training recommendations, environmental preferences.",
  "rosin_extraction": "3-4 sentences: IWHE yield %, press temps in °F, wash water temp, what the finished rosin looks and smells like."
}}

Prioritize details directly from the PTG page. Fill any gaps with accurate knowledge about the genetics listed.
Context: this is for a craft grower and solventless hash maker — be technically precise.
Return only the JSON object, nothing else."""


def extract_research(strain_id: str, strain_name: str, page_text: str, client: Anthropic) -> dict:
    prompt = EXTRACTION_PROMPT.format(
        strain_id=strain_id,
        strain_name=strain_name,
        page_text=page_text[:6000],
    )
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.content[0].text.strip()
    if content.startswith("```"):
        content = "\n".join(content.split("\n")[1:-1]).strip()
    result = json.loads(content)
    result["generated_at"] = datetime.now().isoformat()
    return result


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_ptg_urls() -> dict[str, str]:
    """Fetch pigtailgardens.com/list and extract all product page URLs."""
    list_url = "https://www.pigtailgardens.com/list"
    print(f"Fetching {list_url} ...")
    text = fetch_page(list_url)
    if not text:
        print("Could not fetch list page — try running with Playwright installed.")
        return {}
    resp = requests.get(list_url, headers=BROWSER_HEADERS, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")
    urls = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/product-page/" in href:
            full = href if href.startswith("http") else f"https://www.pigtailgardens.com{href}"
            slug = href.split("/product-page/")[-1].rstrip("/")
            urls[slug] = full
    return urls


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    client = Anthropic()

    with open(STRAINS_FILE) as f:
        strains_data = json.load(f)
    with open(RESEARCH_FILE) as f:
        research = json.load(f)

    strains_by_id = {s["id"]: s for s in strains_data["strains"]}

    # --discover mode
    if len(sys.argv) > 1 and sys.argv[1] == "--discover":
        print("Discovering all current PTG product URLs...\n")
        found = discover_ptg_urls()
        if found:
            print(f"Found {len(found)} product pages:\n")
            for slug, url in sorted(found.items()):
                match = "  (in vault)" if any(s_id in slug or slug in s_id for s_id in strains_by_id) else ""
                print(f"  {url}{match}")
        return

    # Single URL mode
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        url = sys.argv[1]
        slug = url.split("/product-page/")[-1].rstrip("/")
        strain_id = next((s for s in strains_by_id if s in slug or slug in s), None)
        if not strain_id:
            strain_id = input(f"Enter the strain ID (from strains.json) for this URL: ").strip()
        urls_to_fetch = {strain_id: url}
    else:
        # Default: all known PTG strains
        urls_to_fetch = PTG_URLS

    updated, failed = [], []

    for strain_id, url in urls_to_fetch.items():
        strain = strains_by_id.get(strain_id)
        name = strain["name"] if strain else strain_id
        print(f"\n{'─'*60}")
        print(f"  {name}  [{strain_id}]")
        print(f"  {url}")

        page_text = fetch_page(url)
        if not page_text:
            print(f"  FAILED — skipping. Check the URL is correct.")
            failed.append(strain_id)
            continue

        print(f"  Extracting research with Claude...")
        try:
            result = extract_research(strain_id, name, page_text, client)
            research[strain_id] = result
            updated.append(strain_id)
            print(f"  Done.")
        except Exception as e:
            print(f"  Extraction failed: {e}")
            failed.append(strain_id)

        time.sleep(1)

    with open(RESEARCH_FILE, "w") as f:
        json.dump(research, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  Updated : {', '.join(updated) or 'none'}")
    print(f"  Failed  : {', '.join(failed) or 'none'}")
    print(f"  Saved → {RESEARCH_FILE}")
    if updated:
        print(f"\n  Next: git add data/research_cache.json && git commit -m 'Update research from PTG' && git push")


if __name__ == "__main__":
    main()
