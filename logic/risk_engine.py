from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# -----------------------------
# Utilities
# -----------------------------

RISK_RANK = {"GREEN": 0, "AMBER": 1, "RED": 2}
RISK_BY_RANK = {v: k for k, v in RISK_RANK.items()}


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def casefold(s: str) -> str:
    return (s or "").casefold()


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def excerpt(s: str, max_chars: int = 240) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 3].rstrip() + "..."


def escalate_one_level(risk: str) -> str:
    return RISK_BY_RANK[min(RISK_RANK[risk] + 1, 2)]


def risk_max(a: str, b: str) -> str:
    return a if RISK_RANK[a] >= RISK_RANK[b] else b


# -----------------------------
# Rating bands + quadrant
# -----------------------------

def band_from_rating(rating: Optional[int], band_spec: dict, unknown_key: str) -> str:
    if rating is None:
        return unknown_key
    try:
        r = int(rating)
    except Exception:
        return unknown_key

    for band_key, band in band_spec.items():
        if band_key == unknown_key:
            continue
        if "min" in band and "max" in band and band["min"] <= r <= band["max"]:
            return band_key
    return unknown_key


def quadrant_from_bands(ed_band: str, med_band: str, rules: dict) -> Tuple[str, str]:
    quadrants = rules["bdst_v1"]["quadrant_classification"]["quadrants"]

    # unknown shortcut
    if ed_band.endswith("unknown") or med_band.endswith("unknown"):
        q = "Q_unknown"
        return q, quadrants[q]["label"]

    # Evaluate in the defined order (Q1->Q4->Q_unknown)
    order = ["Q1_dual_purpose", "Q2_medicinal_only", "Q3_food_oriented", "Q4_low_use"]
    for q in order:
        cond = quadrants[q]["condition"]
        if ed_band in cond.get("edibility_band_in", []) and med_band in cond.get("medicinal_band_in", []):
            return q, quadrants[q]["label"]

    q = "Q_unknown"
    return q, quadrants[q]["label"]


# -----------------------------
# Token normalization (medicinal properties)
# -----------------------------

@dataclass
class TokenNormalizer:
    phrase_rules: List[Tuple[str, str]]
    synonym_lookup: Dict[str, str]
    stopset: set

    @staticmethod
    def from_yaml(token_norm_yaml: dict) -> "TokenNormalizer":
        cfg = token_norm_yaml["token_normalization"]

        # phrase_rules list of dicts: {pattern, canonical}
        phrase_rules = []
        for rule in cfg.get("phrase_rules", []):
            phrase_rules.append((casefold(rule["pattern"]), rule["canonical"]))

        # synonym_map dict: canonical -> [variants...]
        synonym_lookup: Dict[str, str] = {}
        synmap = cfg.get("synonym_map", {})
        for canonical, variants in synmap.items():
            for v in variants:
                synonym_lookup[casefold(v)] = canonical

        stopset = set(casefold(t) for t in cfg.get("stoplist", {}).get("tokens", []))
        return TokenNormalizer(phrase_rules, synonym_lookup, stopset)

    def normalize_props_to_tokens(self, text: str) -> List[str]:
        s = casefold(text)
        s = normalize_whitespace(s)

        # Apply phrase rules first (substring-based)
        for pattern, canonical in self.phrase_rules:
            if pattern and pattern in s:
                s = s.replace(pattern, canonical)

        # Replace separators with commas
        s = re.sub(r"[;/|•/]+", ",", s)
        # Keep letters/numbers/underscore/comma/space/hyphen
        s = re.sub(r"[^a-z0-9_,\-\s]", " ", s)
        s = normalize_whitespace(s)

        # Split
        chunks = [c.strip() for c in s.split(",")]
        tokens: List[str] = []
        for c in chunks:
            if not c:
                continue
            # optionally split on " and " when safe
            parts = [p.strip() for p in c.split(" and ") if p.strip()]
            for p in parts:
                if not p or p in self.stopset:
                    continue
                # Map single-token synonyms
                canonical = self.synonym_lookup.get(p, p)
                if canonical and canonical not in self.stopset:
                    tokens.append(canonical)

        # Deduplicate preserving order
        seen = set()
        out = []
        for t in tokens:
            if t not in seen:
                out.append(t)
                seen.add(t)
        return out


# -----------------------------
# Hazard normalization + keyword matching
# -----------------------------

@dataclass
class HazardNormalizer:
    spelling_variants: Dict[str, str]
    phrase_rules: List[Tuple[str, str]]

    @staticmethod
    def from_yaml(hazard_norm_yaml: dict) -> "HazardNormalizer":
        cfg = hazard_norm_yaml["hazard_text_normalization"]
        spelling_variants = cfg.get("spelling_variants", {}) or {}

        phrase_rules = []
        for rule in (cfg.get("phrase_normalization", {}) or {}).get("rules", []):
            phrase_rules.append((casefold(rule["pattern"]), casefold(rule["canonical"])))

        return HazardNormalizer(spelling_variants=spelling_variants, phrase_rules=phrase_rules)

    def normalize(self, text: str) -> str:
        s = casefold(text)
        s = normalize_whitespace(s)

        # Normalize hyphenation: contra-indicated -> contraindicated
        s = s.replace("contra-indicated", "contraindicated")

        # Apply spelling variants (simple whole-word-ish replace)
        for src, dst in self.spelling_variants.items():
            s = re.sub(rf"\b{re.escape(casefold(src))}\b", casefold(dst), s)

        # Apply phrase normalization
        for pattern, canonical in self.phrase_rules:
            if pattern and pattern in s:
                s = s.replace(pattern, canonical)

        # Strip heavy punctuation (keep spaces)
        s = re.sub(r"[^a-z0-9_\s]", " ", s)
        s = normalize_whitespace(s)
        return s


def find_keywords(text: str, keywords: List[str]) -> List[str]:
    hits = []
    for kw in keywords:
        kw_cf = casefold(kw)
        if not kw_cf:
            continue
        if kw_cf in text:
            hits.append(kw)
    return sorted(set(hits))


# -----------------------------
# Main BDST Engine
# -----------------------------

class BDSTEngineV1:
    def __init__(self, rules_yaml: dict, token_norm_yaml: dict, hazard_norm_yaml: dict):
        self.rules = rules_yaml["bdst_v1"]
        self.token_norm = TokenNormalizer.from_yaml(token_norm_yaml)
        self.hazard_norm = HazardNormalizer.from_yaml(hazard_norm_yaml)

        # Pull keyword lists from rules
        tiers = self.rules["hazard_extraction"]["tiers"]
        self.H2_keywords = tiers["H2_high_severity"]["keywords"]
        self.H1_keywords = tiers["H1_moderate_severity"]["keywords"]

        # Bioactivity sets from rules
        mr = self.rules["medicinal_property_risk"]
        self.high_risk_tokens = set(mr["high_risk_bioactivities"]["tokens"])
        self.moderate_risk_tokens = set(mr["moderate_risk_bioactivities"]["tokens"])

    def evaluate(self, plant: Dict[str, Any]) -> Dict[str, Any]:
        scientific_name = plant.get("scientific_name") or plant.get("Scientific name") or plant.get("scientific name")
        if not scientific_name:
            raise ValueError("Missing scientific_name in plant record")

        ed_rating = plant.get("edibility_rating")
        med_rating = plant.get("medicinal_rating")
        props_text = plant.get("medicinal_props_text") or ""
        hazards_text = plant.get("known_hazards_text") or ""
        family = plant.get("family")

        # 1) Bands
        bands = self.rules["normalization"]["rating_bands"]
        ed_band = band_from_rating(ed_rating, bands["edibility"], "E_unknown")
        med_band = band_from_rating(med_rating, bands["medicinal"], "M_unknown")
        any_rating_unknown = (ed_band == "E_unknown") or (med_band == "M_unknown")

        # 2) Quadrant
        quadrant, quadrant_label = quadrant_from_bands(ed_band, med_band, {"bdst_v1": self.rules})

        # 3) Hazards
        hazard_text_present = bool(str(hazards_text).strip())
        normalized_haz = self.hazard_norm.normalize(hazards_text) if hazard_text_present else ""
        matched_H2 = find_keywords(normalized_haz, self.H2_keywords) if hazard_text_present else []
        matched_H1 = find_keywords(normalized_haz, self.H1_keywords) if hazard_text_present else []

        if matched_H2:
            hazard_tier = "H2"
        elif matched_H1:
            hazard_tier = "H1"
        else:
            hazard_tier = "H0"

        matched_count = len(matched_H2) + len(matched_H1)
        uncategorized_hazard_notes = hazard_text_present and (matched_count == 0)

        # 4) Medicinal properties -> tokens + bioactivity risk
        props_tokens = self.token_norm.normalize_props_to_tokens(props_text)
        high_hits = sorted(set(props_tokens).intersection(self.high_risk_tokens))
        mod_hits = sorted(set(props_tokens).intersection(self.moderate_risk_tokens))

        if high_hits:
            bio_level = "High"
            bio_triggers = high_hits
        elif mod_hits:
            bio_level = "Moderate"
            bio_triggers = mod_hits
        else:
            bio_level = "None"
            bio_triggers = []

        # 5) Base risk from hazard tier
        rationale = []
        if hazard_tier == "H2":
            risk = "RED"
            rationale.append("base_risk_from_hazards:H2")
        elif hazard_tier == "H1":
            risk = "AMBER"
            rationale.append("base_risk_from_hazards:H1")
        else:
            risk = "GREEN"
            rationale.append("base_risk_from_hazards:H0")

        # 6) Escalations
        if bio_level == "High":
            risk = escalate_one_level(risk)
            risk = risk_max(risk, "AMBER")
            rationale.append("ESC_01_high_risk_bioactivity")

        if quadrant == "Q2_medicinal_only" and med_band == "M2":
            risk = escalate_one_level(risk)
            risk = risk_max(risk, "AMBER")
            rationale.append("ESC_02_medicinal_only_high_medicinal")

        if uncategorized_hazard_notes:
            risk = risk_max(risk, "AMBER")
            rationale.append("HZ_UNCATEGORIZED_MIN_AMBER")
            
        if any_rating_unknown:
            risk = risk_max(risk, "AMBER")
            rationale.append("ESC_04_missing_ratings_uncertainty")
            
        
        amber_floor = False
        amber_floor = (
        (hazard_tier in ["H1", "H2"])
        or uncategorized_hazard_notes
        or (quadrant == "Q2_medicinal_only" and med_band == "M2")
        or (bio_level == "High")
        or any_rating_unknown
        
        )

        # 7) De-escalation (conservative)
        if risk != "RED":
            if risk == "AMBER" and not amber_floor:
                 risk = "GREEN"
                 rationale.append("DEESC_01_allow_amber_to_green")

        # 8) Invariants
        if hazard_tier == "H2":
            risk = "RED"
        if any_rating_unknown:
            risk = risk_max(risk, "AMBER")

        # 9) Plant card output
        risk_label = self.rules["risk_engine"]["risk_levels"][risk]["label"]

        return {
            "identity": {"scientific_name": scientific_name, "family": family},
            "use_profile": {
                "edibility_rating": ed_rating,
                "edibility_band": ed_band,
                "medicinal_rating": med_rating,
                "medicinal_band": med_band,
                "quadrant": quadrant,
                "quadrant_label": quadrant_label,
            },
            "risk_badge": {"bdst_risk_level": risk, "risk_label": risk_label},
            "rationale": {"rules_triggered": rationale},
            "hazards": {
                "hazard_text_present": hazard_text_present,
                "hazard_tier": hazard_tier,
                "hazard_keyword_matches": {"H2": matched_H2, "H1": matched_H1},
                "uncategorized_hazard_notes": uncategorized_hazard_notes,
                "hazard_notes_excerpt": excerpt(hazards_text, 240),
            },
            "bioactivity_flags": {"bioactivity_risk_level": bio_level, "bioactivity_triggers": bio_triggers},
            "debug": {
                "normalized_props_tokens": props_tokens,
                "normalized_hazards_text": normalized_haz,
            },
            "uncertainty_and_disclaimer": [
                "Non-clinical decision support; not medical advice.",
                "Absence of hazard warnings is not proof of safety.",
                "Information is dataset-derived and may be incomplete.",
            ],
        }


# -----------------------------
# CLI helper (optional): run on CSV -> JSON
# -----------------------------

def main():
    """
    Example usage:
      python logic/risk_engine.py --csv data/processed/pfaf_clean.csv --out outputs/plant_cards.json

    You must ensure the CSV has columns matching:
      scientific_name, edibility_rating, medicinal_rating, medicinal_props_text, known_hazards_text, family(optional)
    """
    import argparse
    import pandas as pd

    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", default="bdst_v1_rules.yaml")
    parser.add_argument("--token_norm", default="rules_token_normalization.yaml")
    parser.add_argument("--hazard_norm", default="rules_hazard_text_normalization.yaml")
    parser.add_argument("--csv", required=False)
    parser.add_argument("--out", required=False, default="outputs/plant_cards.json")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    rules_yaml = load_yaml(Path(args.rules))
    token_yaml = load_yaml(Path(args.token_norm))
    hazard_yaml = load_yaml(Path(args.hazard_norm))

    engine = BDSTEngineV1(rules_yaml, token_yaml, hazard_yaml)

    if not args.csv:
        # quick demo record
        demo = {
            "scientific_name": "Demo plantus",
            "edibility_rating": 4,
            "medicinal_rating": 2,
            "medicinal_props_text": "mydriatic, tonic",
            "known_hazards_text": "",
            "family": "Demoaceae",
        }
        card = engine.evaluate(demo)
        print(json.dumps(card, indent=2, ensure_ascii=False))
        return

    df = pd.read_csv(args.csv)
    cards = []
    df_use = df if args.limit is None else df.head(args.limit)

    for _, row in df_use.iterrows():
        plant = {
        "scientific_name": row.get("scientific_name"),
        "edibility_rating": None if pd.isna(row.get("edibility_rating_search")) else int(row.get("edibility_rating_search")),
        "medicinal_rating": None if pd.isna(row.get("medicinal_rating_search")) else int(row.get("medicinal_rating_search")),
        "medicinal_props_text": "" if pd.isna(row.get("medicinal_properties")) else str(row.get("medicinal_properties")),
        "known_hazards_text": "" if pd.isna(row.get("known_hazards")) else str(row.get("known_hazards")),
        "family": None if pd.isna(row.get("family")) else str(row.get("family")),
    }
        try:
            cards.append(engine.evaluate(plant))
        except Exception as e:
            cards.append({"error": str(e), "raw_row_index": int(row.name)})


    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(cards)} plant cards to: {out_path}")

if __name__ == "__main__":
    main()
