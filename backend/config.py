"""Central configuration: paths, campus constants, building alias map.

Constants come from README_data_guide.md section 6 (Engineering Baselines).
"""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("ECOGRID_DATA", ROOT.parent / "P2P_DATASET"))
CACHE_DIR = ROOT / "cache"
WEB_DIR = ROOT / "web"
CACHE_DIR.mkdir(exist_ok=True)

# --- Engineering baselines (README §6) ---
CO2_KG_PER_KWH = 0.70
TARIFF_RS_PER_KWH = 8.00
WATER_KWH_PER_KL = 0.85
COMPOST_RATIO = 4.0          # 4 kg wet organic -> 1 kg compost
KG_PER_BAG = 8.0             # manual logs: ~8 kg per custodial bag

SENSOR_FEATURES = ["weight_g", "moisture_pct", "metal_signal", "transparency", "acoustic_hardness"]
WASTE_CLASSES = ["food_organic", "paper_cardboard", "plastic", "glass", "metal", "ewaste"]

# Circular routing: where each classified item should go
CIRCULAR_ROUTE = {
    "food_organic": "compost",
    "paper_cardboard": "recycle",
    "plastic": "recycle",
    "glass": "recycle",
    "metal": "recycle",
    "ewaste": "e-waste vendor",
}

# Building alias normalisation for manual field logs (README §5).
# Keys are lower-cased, punctuation-stripped tokens.
BUILDING_ALIASES = {
    "B01": ["b01", "academic block a", "acad a", "ab a", "block a", "aba", "ab1", "academic a"],
    "B02": ["b02", "academic block b", "acad b", "ab b", "block b", "abb", "ab2", "academic b"],
    "B03": ["b03", "central library", "library", "lib", "cl"],
    "B04": ["b04", "engineering labs & innovation centre", "engineering labs and innovation centre",
            "engineering labs", "eng labs", "labs", "lab complex", "innovation centre", "elic"],
    "B05": ["b05", "boys hostel", "boys hostle", "bh", "boys hostal", "boy hostel", "bhostel"],
    "B06": ["b06", "girls hostel", "girls hostle", "gh", "girls hostal", "girl hostel", "ghostel"],
    "B07": ["b07", "food court", "central mess", "mess", "canteen", "cafeteria", "fc", "foodcourt"],
    "B08": ["b08", "admin block", "admin", "administration", "admin office", "adm"],
}

# Real-world context: Chanakya University Global Campus, Haraluru-Polanahalli,
# Devanahalli, Bengaluru (near Kempegowda International Airport).
CAMPUS = {
    "name": "Chanakya University – Global Campus",
    "location": "Haraluru–Polanahalli, Devanahalli, Bengaluru",
    "lat": 13.2846,
    "lon": 77.6078,
}
