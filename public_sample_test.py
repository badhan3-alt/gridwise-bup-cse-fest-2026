"""Run the official public sample pack against a running GridWise service.

Usage:
    python public_sample_test.py --base-url http://127.0.0.1:8000

This DOES call the configured LLM through your service and may incur provider usage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent


def semantic_directive(d: dict):
    return {
        "note_index": d["note_index"],
        "applies": d["applies"],
        "directive_type": d["directive_type"],
        "structured_adjustment": d["structured_adjustment"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    pack = json.loads((ROOT / "public_sample_cases.json").read_text(encoding="utf-8"))

    with httpx.Client(timeout=30.0) as client:
        health = client.get(base + "/health")
        health.raise_for_status()
        print("health:", health.json())

        passed = 0
        for case in pack["cases"]:
            response = client.post(base + "/optimize-energy", json=case["input"])
            if response.status_code != 200:
                print(f"FAIL {case['id']}: HTTP {response.status_code} {response.text[:200]}")
                continue

            got = response.json()
            expected = case["expected_output"]
            got_directives = [semantic_directive(x) for x in got["directive_interpretation"]]
            exp_directives = [semantic_directive(x) for x in expected["directive_interpretation"]]
            directives_ok = got_directives == exp_directives
            cost_ok = abs(float(got["total_cost_bdt"]) - float(expected["total_cost_bdt"])) <= 0.01
            grid_ok = abs(float(got["total_grid_kwh"]) - float(expected["total_grid_kwh"])) <= 0.01

            if directives_ok and cost_ok and grid_ok:
                passed += 1
                print(f"PASS {case['id']}  cost={got['total_cost_bdt']}")
            else:
                print(f"FAIL {case['id']} directives={directives_ok} cost={cost_ok} grid={grid_ok}")
                if not directives_ok:
                    print("  expected directives:", exp_directives)
                    print("  got directives     :", got_directives)

    print(f"\nPassed {passed}/{len(pack['cases'])} public cases")
    raise SystemExit(0 if passed == len(pack["cases"]) else 1)


if __name__ == "__main__":
    main()
