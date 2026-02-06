import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Your engine lives in logic/risk_engine.py
# This import assumes run_acceptance_tests.py is in the SAME folder (logic/)
from risk_engine import BDSTEngineV1  # type: ignore


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def safe_get(d: Any, path: List[str], default=None):
    """Safely read nested dict keys."""
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def contains_all(haystack: List[str], needles: List[str]) -> Tuple[bool, List[str]]:
    hs = set(haystack or [])
    missing = [n for n in (needles or []) if n not in hs]
    return (len(missing) == 0, missing)


def contains_none(haystack: List[str], forbidden: List[str]) -> Tuple[bool, List[str]]:
    hs = set(haystack or [])
    present = [f for f in (forbidden or []) if f in hs]
    return (len(present) == 0, present)


def eval_one(engine: BDSTEngineV1, test_case: dict) -> dict:
    test_id = test_case.get("id", "unknown")
    title = test_case.get("title", "")
    plant = test_case.get("input", test_case.get("plant", {}))
    expected = test_case.get("expected", {})

    ok = True
    reasons: List[str] = []
    card = None

    try:
        card = engine.evaluate(plant)
    except Exception as e:
        ok = False
        reasons.append(f"engine_exception:{str(e)}")

    # If engine crashed, return early with failure
    if card is None:
        return {
            "id": test_id,
            "title": title,
            "pass": False,
            "reasons": reasons,
            "input": plant,
            "expected": expected,
            "got": None,
        }

    # ---- Basic expected checks ----
    exp_risk = expected.get("bdst_risk_level")
    if exp_risk is not None:
        got_risk = safe_get(card, ["risk_badge", "bdst_risk_level"])
        if got_risk != exp_risk:
            ok = False
            reasons.append(f"bdst_risk_level expected={exp_risk} got={got_risk}")

    exp_hazard_tier = expected.get("hazard_tier")
    if exp_hazard_tier is not None:
        got_hazard_tier = safe_get(card, ["hazards", "hazard_tier"])
        if got_hazard_tier != exp_hazard_tier:
            ok = False
            reasons.append(f"hazard_tier expected={exp_hazard_tier} got={got_hazard_tier}")

    exp_quad = expected.get("quadrant")
    if exp_quad is not None:
        got_quad = safe_get(card, ["use_profile", "quadrant"])
        if got_quad != exp_quad:
            ok = False
            reasons.append(f"quadrant expected={exp_quad} got={got_quad}")

    exp_bio = expected.get("bioactivity_risk_level")
    if exp_bio is not None:
        got_bio = safe_get(card, ["bioactivity_flags", "bioactivity_risk_level"])
        if got_bio != exp_bio:
            ok = False
            reasons.append(f"bioactivity_risk_level expected={exp_bio} got={got_bio}")

    exp_uncat = expected.get("uncategorized_hazard_notes")
    if exp_uncat is not None:
        got_uncat = safe_get(card, ["hazards", "uncategorized_hazard_notes"])
        if got_uncat != exp_uncat:
            ok = False
            reasons.append(
                f"uncategorized_hazard_notes expected={exp_uncat} got={got_uncat}"
            )

    # ---- Rationale includes / excludes ----
    got_rules = safe_get(card, ["rationale", "rules_triggered"], default=[])
    if not isinstance(got_rules, list):
        got_rules = []

    exp_include = expected.get("must_include_rationale", []) or []
    if exp_include:
        good, missing = contains_all(got_rules, exp_include)
        if not good:
            ok = False
            reasons.append(f"missing_rationale:{missing}")

    exp_exclude = expected.get("must_not_include_rationale", []) or []
    if exp_exclude:
        good, present = contains_none(got_rules, exp_exclude)
        if not good:
            ok = False
            reasons.append(f"forbidden_rationale_present:{present}")

    # ---- Normalized properties tokens (debug) ----
    # Your engine may store these under debug.normalized_props_tokens
    exp_norm_props_inc = expected.get("normalized_props_must_include", []) or []
    if exp_norm_props_inc:
        got_norm = safe_get(card, ["debug", "normalized_props_tokens"], default=[])
        if not isinstance(got_norm, list):
            got_norm = []
        good, missing = contains_all(got_norm, exp_norm_props_inc)
        if not good:
            ok = False
            reasons.append(f"missing_normalized_props:{missing}")

    return {
        "id": test_id,
        "title": title,
        "pass": ok,
        "reasons": reasons,
        "input": plant,
        "expected": expected,
        "got": card,
    }


def run_tests(engine: BDSTEngineV1, tests_yaml: dict) -> Dict[str, Any]:
    # Your YAML has: bdst_v1_acceptance_tests -> tests
    root = tests_yaml.get("bdst_v1_acceptance_tests", tests_yaml)
    tests = root.get("tests", [])

    # If tests is not a list, treat as empty
    if not isinstance(tests, list):
        tests = []

    results = []
    passed = 0

    for t in tests:
        res = eval_one(engine, t)
        results.append(res)
        if res["pass"]:
            passed += 1

    return {
        "meta": root.get("meta", {}),
        "summary": {"total": len(results), "passed": passed, "failed": len(results) - passed},
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", required=True)
    parser.add_argument("--token_norm", required=True)
    parser.add_argument("--hazard_norm", required=True)
    parser.add_argument("--tests", required=True)
    parser.add_argument("--out", default="outputs/acceptance_test_report.json")
    args = parser.parse_args()

    rules = load_yaml(Path(args.rules))
    token_norm = load_yaml(Path(args.token_norm))
    hazard_norm = load_yaml(Path(args.hazard_norm))
    tests_yaml = load_yaml(Path(args.tests))

    engine = BDSTEngineV1(rules, token_norm, hazard_norm)

    report = run_tests(engine, tests_yaml)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    s = report["summary"]
    print(f"Acceptance tests: {s['passed']}/{s['total']} passed, {s['failed']} failed")
    print(f"Report written to: {out_path}")

    if s["failed"] > 0:
        failing = [r for r in report["results"] if not r["pass"]][:10]
        print("First failing tests:")
        for r in failing:
            print(f" - {r['id']}: {', '.join(r['reasons'])}")


if __name__ == "__main__":
    main()
