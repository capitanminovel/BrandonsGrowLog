from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from anthropic import Anthropic
import json
import uuid
from datetime import datetime
from pathlib import Path

app = FastAPI(title="Captain's Terps Grows")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
STRAINS_FILE = DATA_DIR / "strains.json"
RESEARCH_FILE = DATA_DIR / "research_cache.json"

client = Anthropic()


def load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


@app.get("/")
def root():
    return FileResponse(BASE / "static" / "index.html")


@app.get("/api/strains")
def get_strains():
    return load_json(STRAINS_FILE)


class NewStrain(BaseModel):
    name: str
    breeder: str
    status: str = "Vault"
    notes: str = ""


@app.post("/api/strains")
def add_strain(strain: NewStrain):
    data = load_json(STRAINS_FILE)
    slug = strain.name.lower().replace(" ", "-")[:24]
    new_id = f"{slug}-{str(uuid.uuid4())[:4]}"
    new_strain = {
        "id": new_id,
        "name": strain.name,
        "breeder": strain.breeder,
        "status": strain.status,
        "notes": strain.notes,
        "added": datetime.now().strftime("%Y-%m-%d"),
    }
    data["strains"].append(new_strain)
    save_json(STRAINS_FILE, data)
    return new_strain


class StrainUpdate(BaseModel):
    status: str
    notes: str | None = None


@app.patch("/api/strains/{strain_id}")
def update_strain(strain_id: str, update: StrainUpdate):
    data = load_json(STRAINS_FILE)
    for strain in data["strains"]:
        if strain["id"] == strain_id:
            strain["status"] = update.status
            if update.notes is not None:
                strain["notes"] = update.notes
            save_json(STRAINS_FILE, data)
            return strain
    raise HTTPException(status_code=404, detail="Strain not found")


@app.delete("/api/strains/{strain_id}")
def delete_strain(strain_id: str):
    data = load_json(STRAINS_FILE)
    before = len(data["strains"])
    data["strains"] = [s for s in data["strains"] if s["id"] != strain_id]
    if len(data["strains"]) == before:
        raise HTTPException(status_code=404, detail="Strain not found")
    save_json(STRAINS_FILE, data)
    research = load_json(RESEARCH_FILE)
    research.pop(strain_id, None)
    save_json(RESEARCH_FILE, research)
    return {"deleted": strain_id}


@app.get("/api/research/{strain_id}")
def get_research(strain_id: str):
    research = load_json(RESEARCH_FILE)
    return research.get(strain_id, {})


@app.post("/api/research/{strain_id}")
def generate_research(strain_id: str):
    strains_data = load_json(STRAINS_FILE)
    strain = next((s for s in strains_data["strains"] if s["id"] == strain_id), None)
    if not strain:
        raise HTTPException(status_code=404, detail="Strain not found")

    research = load_json(RESEARCH_FILE)
    if strain_id in research:
        return research[strain_id]

    prompt = f"""You are a cannabis genetics expert and master craft cultivator specializing in solventless extraction — ice water hash, rosin, and living resin. You have deep knowledge of seed breeders, plant genetics, terpene chemistry, and pressing technique.

Generate a detailed research profile for the cannabis strain "{strain['name']}" by {strain['breeder']}.

Return ONLY valid JSON with exactly these six keys:

{{
  "genetics_lineage": "3-4 sentences: parent strains, full genetic lineage, breeder background and philosophy, phenotype notes, what makes this cultivar sought after",
  "terpene_profile": "3-4 sentences: dominant and secondary terpenes expected from this cultivar, their aromas and synergistic interactions, how the terpene expression develops through flower and into cure",
  "effects": "3-4 sentences: onset character, intensity level, balance of cerebral vs body, duration, mood profile, best use cases and time of day",
  "flavor_aroma": "3-4 sentences: detailed flavor notes on inhale and exhale, aroma at different grow stages (late flower, harvest, fresh cure, long cure), palate profile and mouthfeel",
  "grow_notes": "3-4 sentences: growth structure and stretch behavior, flowering time, yield potential, training method recommendations (topping, LST, ScrOG), environmental preferences (VPD, temp, humidity), and harvest window indicators",
  "rosin_extraction": "3-4 sentences: suitability for ice water hash and rosin pressing, expected solventless yield percentage, recommended press temperatures in °F, optimal wash water temps for IWHE, and what the final live rosin or hash rosin should look and smell like"
}}

Be technically precise and craft-focused. Include details a passionate home grower and solventless hash maker would value. Output only the JSON object, nothing else."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    content = response.content[0].text.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1]).strip()

    result = json.loads(content)
    result["generated_at"] = datetime.now().isoformat()

    research[strain_id] = result
    save_json(RESEARCH_FILE, research)
    return result


app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
