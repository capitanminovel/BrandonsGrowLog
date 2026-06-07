#!/usr/bin/env python3
"""
Fetch ONE strain page and save the text to scripts/ptg_pages/.

Must be run from your LOCAL machine — pigtailgardens.com blocks cloud server IPs.
No API key needed.

Setup (one time):
    pip install requests beautifulsoup4 playwright
    playwright install chromium

─────────────────────────────────────────────────────────────────────────────
ADDING A NEW STRAIN — step by step
─────────────────────────────────────────────────────────────────────────────

STEP 1 — Add the strain to PTG_URLS below (or OTHER_URLS if not a PTG strain):
    "your-strain-id": "https://www.pigtailgardens.com/product-page/your-strain-slug"

    The ID must match the "id" field you added in data/strains.json.
    Lowercase letters and hyphens only, e.g. "cherry-jealousy".

STEP 2 — Fetch the page for that one strain:
    python scripts/fetch_ptg.py --id your-strain-id

    This saves the page text to scripts/ptg_pages/your-strain-id.txt.

STEP 3 — Generate the research profile using Claude (free tier works fine):
    a. Open scripts/ptg_pages/your-strain-id.txt in a text editor.
    b. Copy the entire contents.
    c. Go to claude.ai and start a new chat.
    d. Paste this message (replace the bracketed parts):

    ──────────────────────────────────────────────────────────────────────
    Here is the product page text for a cannabis strain called
    "[Strain Name]" by [Breeder]. I need you to generate a research
    profile for it.

    Return ONLY valid JSON with exactly these six keys — no extra text,
    no markdown, just the raw JSON:

    {
      "genetics_lineage": "3-4 sentences: parent strains, full genetic lineage, breeder background, phenotype notes, what makes this cultivar sought after.",
      "terpene_profile": "3-4 sentences: dominant and secondary terpenes, aromas, synergistic interactions, how expression develops through cure.",
      "effects": "3-4 sentences: onset character, intensity, cerebral vs body, duration, mood profile, best use cases.",
      "flavor_aroma": "3-4 sentences: inhale/exhale flavor, aroma at grow stages (late flower, harvest, fresh cure, long cure).",
      "grow_notes": "3-4 sentences: structure and stretch, flowering time, training recommendations, environmental preferences, harvest indicators.",
      "rosin_extraction": "3-4 sentences: IWHE yield %, press temps in F, wash water temp, what the finished rosin looks and smells like."
    }

    Source text:
    [PASTE THE CONTENTS OF THE .txt FILE HERE]
    ──────────────────────────────────────────────────────────────────────

STEP 4 — Paste the JSON Claude gives you into data/research_cache.json:
    Add it as a new key using the strain ID. Example:

    {
      "existing-strain": { ... },
      "your-strain-id": {
        "genetics_lineage": "...",
        "terpene_profile": "...",
        "effects": "...",
        "flavor_aroma": "...",
        "grow_notes": "...",
        "rosin_extraction": "...",
        "generated_at": "2026-06-07T00:00:00"
      }
    }

STEP 5 — Commit and push:
    git add data/strains.json data/research_cache.json
    git commit -m "Add [Strain Name]"
    git push

─────────────────────────────────────────────────────────────────────────────
Other usage
─────────────────────────────────────────────────────────────────────────────
    python scripts/fetch_ptg.py --discover       # list all current PTG product URLs
    python scripts/fetch_ptg.py --all            # fetch every strain in PTG_URLS
    python scripts/fetch_ptg.py --other          # fetch non-PTG strains
    python scripts/fetch_ptg.py <url>            # fetch any page by URL directly
"""

import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE       = Path(__file__).parent.parent
STRAINS_FILE = BASE / "data" / "strains.json"
OUT_DIR    = Path(__file__).parent / "ptg_pages"

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
# Add new entries here when you acquire more cuts from PTG
# Tip: run --discover to list all current PTG product URLs and verify slugs
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
    "nana-glue":              "https://www.pigtailgardens.com/product-page/nana-glue-monroe-s-bedhead-cut",
    "lipsmackerz":            "https://www.pigtailgardens.com/product-page/lip-smackerz-cltvtd-x-good-greens",
    "pre-98-bubba-kush":      "https://www.pigtailgardens.com/product-page/bubba-kush-pre-98-99",
}

# Non-PTG strains — fetched from each breeder's own site or Leafly
OTHER_URLS = {
    "kryptochronic":  "https://www.compoundgenetics.com/strains/kryptochronic",
    "grease-monkey":  "https://exoticgenetix.com/product-category/seeds/grease-monkey/",
    "jet-fuel-og":    "https://www.leafly.com/strains/jet-fuel-og",
}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def fetch_with_requests(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"    requests -> HTTP {resp.status_code}")
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if len(text) < 400:
            print(f"    requests -> only {len(text)} chars (JS shell)")
            return None
        return text
    except Exception as e:
        print(f"    requests -> error: {e}")
        return None


def fetch_with_playwright(url: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("    playwright not installed. Run: pip install playwright && playwright install chromium")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="load", timeout=45000)
            try:
                page.wait_for_selector("[data-testid='richTextElement'], .wixui-rich-text, p", timeout=12000)
            except Exception:
                pass
            content = page.inner_text("body")
            browser.close()
            if len(content) < 400:
                print(f"    playwright -> only {len(content)} chars")
                return None
            return content
    except Exception as e:
        print(f"    playwright -> error: {e}")
        return None


def fetch_page(url: str) -> str | None:
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
# Discovery
# ---------------------------------------------------------------------------

def discover_ptg_urls() -> None:
    import json
    list_url = "https://www.pigtailgardens.com/list"
    print(f"Fetching {list_url} with Playwright (JS rendering)...")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(list_url, wait_until="networkidle", timeout=30000)
            # wait for product links to appear
            try:
                page.wait_for_selector("a[href*='/product-page/']", timeout=10000)
            except Exception:
                pass
            html = page.content()
            browser.close()
    except Exception as e:
        print(f"Playwright error: {e}")
        return

    soup = BeautifulSoup(html, "html.parser")
    urls = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/product-page/" in href:
            full = href if href.startswith("http") else f"https://www.pigtailgardens.com{href}"
            slug = href.split("/product-page/")[-1].rstrip("/")
            urls[slug] = full

    with open(STRAINS_FILE) as f:
        vault_ids = {s["id"] for s in json.load(f)["strains"]}

    print(f"\nFound {len(urls)} product pages:\n")
    for slug, url in sorted(urls.items()):
        tag = "  ← in vault" if any(v in slug or slug in v for v in vault_ids) else ""
        print(f"  {url}{tag}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(exist_ok=True)

    if len(sys.argv) > 1 and sys.argv[1] == "--discover":
        discover_ptg_urls()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--other":
        urls_to_fetch = OTHER_URLS
        label = "non-PTG"
    elif len(sys.argv) > 1 and sys.argv[1] == "--all":
        urls_to_fetch = PTG_URLS
        label = "PTG (all)"
    elif len(sys.argv) > 2 and sys.argv[1] == "--id":
        strain_id = sys.argv[2]
        all_urls = {**PTG_URLS, **OTHER_URLS}
        if strain_id not in all_urls:
            print(f"Error: '{strain_id}' not found in PTG_URLS or OTHER_URLS.")
            print("Add it to the PTG_URLS dict at the top of this script first.")
            sys.exit(1)
        urls_to_fetch = {strain_id: all_urls[strain_id]}
        label = "single"
    elif len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        url = sys.argv[1]
        slug = url.rstrip("/").split("/")[-1]
        urls_to_fetch = {slug: url}
        label = "custom"
    else:
        print("Usage: python scripts/fetch_ptg.py --id <strain-id>")
        print("       python scripts/fetch_ptg.py --all")
        print("       python scripts/fetch_ptg.py --other")
        print("       python scripts/fetch_ptg.py --discover")
        print("       python scripts/fetch_ptg.py <url>")
        print("\nFor adding one new strain, use --id. See the docstring for full instructions.")
        sys.exit(0)

    saved, failed = [], []

    for strain_id, url in urls_to_fetch.items():
        print(f"\n{'-'*60}")
        print(f"  [{strain_id}]  ({label})")
        print(f"  {url}")

        text = fetch_page(url)
        if not text:
            print(f"  FAILED — check the URL or install Playwright")
            failed.append(strain_id)
            continue

        out_file = OUT_DIR / f"{strain_id}.txt"
        out_file.write_text(text, encoding="utf-8")
        saved.append(strain_id)
        print(f"  Saved -> {out_file.relative_to(BASE)}")
        time.sleep(1)

    print("\n" + "="*60)
    print(f"  Saved  : {len(saved)} files in scripts/ptg_pages/")
    print(f"  Failed : {', '.join(failed) or 'none'}")


if __name__ == "__main__":
    main()
