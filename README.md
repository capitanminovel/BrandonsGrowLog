# Brandon's Grow Log

A personal cannabis strain vault and research tracker. Browse your collection, read detailed strain profiles (genetics, terpenes, effects, grow notes, rosin extraction), and track grow status — all from a single HTML file backed by plain JSON data files.

---

## Viewing the App

### GitHub Pages (recommended — no server needed)
1. Go to your repo on GitHub → **Settings → Pages**
2. Set Source to **Deploy from a branch**, branch `main`, folder `/ (root)`
3. Your app will be live at `https://[your-username].github.io/BrandonsGrowLog/`

The page loads `data/strains.json` and `data/research_cache.json` automatically. Just edit those files, commit, and push — the page updates within a minute.

### Local preview (no install required)
```bash
python -m http.server 8080
# then open http://localhost:8080
```

---

## Adding a New Strain

### Step 1 — Add it to `data/strains.json`

Open `data/strains.json` and add a new object to the `"strains"` array:

```json
{
  "id": "my-new-strain",
  "name": "My New Strain",
  "breeder": "Breeder Name",
  "status": "Vault",
  "notes": "Cross info, source, any notes you want on the card.",
  "added": "2026-06-07"
}
```

**Status options:** `Vault` · `Active` · `Grow Log` · `Cured`

The `id` must be unique — lowercase letters and hyphens only, e.g. `"cherry-jealousy"`.

### Step 2 — Add a URL to `scripts/fetch_ptg.py` (PTG strains only)

Open `scripts/fetch_ptg.py` and add one line to `PTG_URLS`:

```python
"my-new-strain": "https://www.pigtailgardens.com/product-page/the-page-slug",
```

For non-PTG strains, add to `OTHER_URLS` instead.

### Step 3 — Fetch the page text

Run this from your local machine (pigtailgardens.com blocks cloud IPs):

```bash
pip install requests beautifulsoup4   # one-time setup
python scripts/fetch_ptg.py --id my-new-strain
```

This saves the page content to `scripts/ptg_pages/my-new-strain.txt`.

### Step 4 — Generate the research profile with Claude (free tier works)

1. Open `scripts/ptg_pages/my-new-strain.txt` in any text editor and copy everything.
2. Go to [claude.ai](https://claude.ai) and start a new chat.
3. Paste this message — fill in the strain name/breeder and paste the file contents at the bottom:

```
Here is the product page text for a cannabis strain called
"[Strain Name]" by [Breeder]. Generate a research profile for it.

Return ONLY valid JSON with exactly these six keys — no extra text,
no markdown, just the raw JSON object:

{
  "genetics_lineage": "3-4 sentences: parent strains, full genetic lineage, breeder background, phenotype notes, what makes this cultivar sought after.",
  "terpene_profile": "3-4 sentences: dominant and secondary terpenes, aromas, synergistic interactions, how expression develops through cure.",
  "effects": "3-4 sentences: onset character, intensity, cerebral vs body, duration, mood profile, best use cases.",
  "flavor_aroma": "3-4 sentences: inhale/exhale flavor, aroma at grow stages (late flower, harvest, fresh cure, long cure).",
  "grow_notes": "3-4 sentences: structure and stretch, flowering time, training recommendations, environmental preferences, harvest indicators.",
  "rosin_extraction": "3-4 sentences: IWHE yield %, press temps in F, wash water temp, what the finished rosin looks and smells like."
}

Source text:
[PASTE THE CONTENTS OF my-new-strain.txt HERE]
```

### Step 5 — Paste the JSON into `data/research_cache.json`

Add it as a new top-level key using the strain's `id`:

```json
{
  "existing-strain": { ... },
  "my-new-strain": {
    "genetics_lineage": "...",
    "terpene_profile": "...",
    "effects": "...",
    "flavor_aroma": "...",
    "grow_notes": "...",
    "rosin_extraction": "...",
    "generated_at": "2026-06-07T00:00:00"
  }
}
```

### Step 6 — Commit and push

```bash
git add data/strains.json data/research_cache.json
git commit -m "Add My New Strain"
git push
```

GitHub Pages picks up the push within ~60 seconds.

---

## Adding a Strain Photo

Drop a `.jpg` or `.png` into `images/strains/` named after the strain's `id`:

```
images/strains/my-new-strain.jpg
```

If your filename is different from the strain ID (e.g. all-caps), add a mapping entry to `STRAIN_IMAGES` in `index.html` so the app can find it:

```js
const STRAIN_IMAGES = {
  'my-new-strain': 'MY_NEW_STRAIN.png',
  // ...
};
```

The image appears automatically on the strain card and in the detail modal. Click it in the modal to view full-size.

---

## File Structure

```
BrandonsGrowLog/
├── index.html                  # The entire front-end app
├── data/
│   ├── strains.json            # Your strain vault — edit to add/change strains
│   └── research_cache.json     # Research profiles — edit to add/change research
├── images/
│   └── strains/                # Strain photos: [id].jpg or [id].png
└── scripts/
    └── fetch_ptg.py            # Fetches PTG/breeder pages for Claude to process
```

---

## How the App Loads Data

The app tries two sources in order:

1. **Static JSON files** at `./data/strains.json` + `./data/research_cache.json` — used on GitHub Pages or any web server
2. **Browser localStorage** — last-resort fallback if neither is reachable

On GitHub Pages, path 1 is always used and everything just works.
