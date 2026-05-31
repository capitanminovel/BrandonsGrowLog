# Brandon's Grow Log

A personal cannabis strain vault and research tracker. Browse your collection, read detailed strain profiles (genetics, terpenes, effects, grow notes, rosin extraction), and track grow status — all from a single HTML file backed by plain JSON data files.

---

## Viewing the App

### GitHub Pages (recommended — no server needed)
1. Go to your repo on GitHub → **Settings → Pages**
2. Set Source to **Deploy from a branch**, branch `main`, folder `/ (root)`
3. Your app will be live at `https://[your-username].github.io/BrandonsGrowLog/`

The page loads `data/strains.json` and `data/research_cache.json` automatically. Just edit those files, commit, and push — the page updates within a minute.

### Local web server (no Python/FastAPI required)
```bash
python -m http.server 8080
# then open http://localhost:8080
```

### Full backend (enables add/edit/delete UI + AI research generation)
```bash
pip install fastapi uvicorn anthropic
uvicorn main:app --reload
# then open http://localhost:8000
```
Set your `ANTHROPIC_API_KEY` environment variable to use AI research generation.

---

## Adding or Editing Strains

Edit `data/strains.json`. Each strain is one object in the `"strains"` array:

```json
{
  "id": "my-new-strain",
  "name": "My New Strain",
  "breeder": "Breeder Name",
  "status": "Vault",
  "notes": "Cross info, source, any notes you want on the card.",
  "added": "2026-06-01"
}
```

**Status options:** `Vault` · `Active` · `Grow Log` · `Cured`

The `id` must be unique — lowercase letters and hyphens only, e.g. `"cherry-jealousy"`. It is also used to match the strain photo (see below).

---

## Adding or Editing Research Profiles

Edit `data/research_cache.json`. The key is the strain's `id`. Each entry has six fields:

```json
"my-new-strain": {
  "genetics_lineage": "3-4 sentences: parent strains, breeder background, phenotype notes, what makes it sought after.",
  "terpene_profile": "3-4 sentences: dominant and secondary terpenes, aromas, synergistic interactions, how expression develops through cure.",
  "effects": "3-4 sentences: onset character, intensity, cerebral vs body balance, duration, best use cases.",
  "flavor_aroma": "3-4 sentences: inhale/exhale flavor, aroma through grow stages (late flower, harvest, fresh cure, long cure).",
  "grow_notes": "3-4 sentences: structure and stretch, flowering time, training recommendations, environmental preferences.",
  "rosin_extraction": "3-4 sentences: IWHE yield %, press temps in °F, wash water temp, what the finished rosin looks and smells like.",
  "generated_at": "2026-06-01T12:00:00"
}
```

If a strain has no research entry, the app shows a **Generate Research** button (requires the FastAPI backend and an Anthropic API key).

---

## Adding Strain Photos

Drop a `.jpg` or `.png` named after the strain's `id` into `images/strains/`:

```
images/strains/rainbow-runtz.jpg
images/strains/jam-pack-2.png
```

The app displays it automatically on the card and in the detail modal.

---

## File Structure

```
BrandonsGrowLog/
├── index.html                  # The entire front-end app
├── main.py                     # Optional FastAPI backend
├── data/
│   ├── strains.json            # Your strain vault — edit this to add/change strains
│   └── research_cache.json     # Research profiles — edit this to add/change research
└── images/
    └── strains/                # Strain photos: [id].jpg or [id].png
```

---

## Deploying Changes

```bash
git add data/strains.json data/research_cache.json
git commit -m "Add [strain name]"
git push
```

GitHub Pages picks up the push within ~60 seconds.

---

## How the App Loads Data

The app tries three sources in order:

1. **FastAPI backend** at `/api/strains` — used when running `uvicorn main:app` locally
2. **Static JSON files** at `./data/strains.json` + `./data/research_cache.json` — used on GitHub Pages or any web server
3. **Browser localStorage** — last-resort fallback if neither is reachable

For most users on GitHub Pages, path 2 is always used and everything just works.
