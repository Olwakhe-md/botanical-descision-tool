import json
from collections import Counter
from pathlib import Path

IN_PATH = Path("outputs/pfaf_bdst_v1_cards.json")
OUT_PATH = Path("outputs/pfaf_bdst_v1_summary.json")

def main():
    cards = json.loads(IN_PATH.read_text(encoding="utf-8"))

    risk_dist = Counter()
    hazard_tier_dist = Counter()
    quadrant_dist = Counter()
    bio_dist = Counter()
    triggers = Counter()
    error_count = 0

    for c in cards:
        if "error" in c:
            error_count += 1
            continue

        # Risk
        rb = c.get("risk_badge", {})
        risk_dist[rb.get("bdst_risk_level", "UNKNOWN")] += 1

        # Hazards
        hz = c.get("hazards", {})
        hazard_tier_dist[hz.get("hazard_tier", "UNKNOWN")] += 1

        # Quadrant / use profile
        up = c.get("use_profile", {})
        quadrant_dist[up.get("quadrant", "UNKNOWN")] += 1

        # Bioactivity
        bio = c.get("bioactivity_flags", {})
        bio_dist[bio.get("bioactivity_risk_level", "UNKNOWN")] += 1

        # Rationale triggers
        for t in c.get("rationale", {}).get("rules_triggered", []):
            triggers[t] += 1

    summary = {
        "records_total": len(cards),
        "records_errors": error_count,
        "records_ok": len(cards) - error_count,
        "risk_distribution": dict(risk_dist),
        "hazard_tier_distribution": dict(hazard_tier_dist),
        "quadrant_distribution": dict(quadrant_dist),
        "bioactivity_risk_distribution": dict(bio_dist),
        "top_rules_triggered": triggers.most_common(30),
    }

    OUT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Summary written to:", OUT_PATH)
    print("\nRisk distribution:")
    for k, v in risk_dist.most_common():
        print(f"  {k}: {v}")

    print("\nHazard tier distribution:")
    for k, v in hazard_tier_dist.most_common():
        print(f"  {k}: {v}")

    print("\nQuadrant distribution:")
    for k, v in quadrant_dist.most_common():
        print(f"  {k}: {v}")

    print("\nBioactivity risk distribution:")
    for k, v in bio_dist.most_common():
        print(f"  {k}: {v}")

    print(f"\nErrors: {error_count}")

if __name__ == "__main__":
    main()
