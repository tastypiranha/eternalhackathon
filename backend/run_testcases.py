"""Run every held-out test case through the predictor and print a scorecard.

    cd backend && python run_testcases.py            # all cases
    cd backend && python run_testcases.py TS5_t24h   # one case, full output
"""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("FRESHSENSE_MQTT_ENABLED", "0")
import predict  # noqa: E402

CASES = Path(__file__).parent / "testcases"


def load_cases():
    return [json.loads(p.read_text()) for p in sorted(CASES.glob("*.json"))]


def run_all():
    rows = []
    for case in load_cases():
        res = predict.predict(case["input"])
        rows.append(predict.score_case(case, res))
    return rows


if __name__ == "__main__":
    if len(sys.argv) > 1:
        case = json.loads((CASES / f"{sys.argv[1]}.json").read_text())
        print(json.dumps(predict.predict(case["input"]), indent=2))
        print("expected:", json.dumps(case["expected"], indent=2))
        sys.exit(0)
    rows = run_all()
    print(f"{'case':22s} {'expected':>8s} {'predicted':>9s} {'kinetic':>8s} {'gas':>6s} {'err':>5s}  stage (exp → pred)        pass")
    for r in rows:
        gas = "-" if r["gas_tvc"] is None else f"{r['gas_tvc']:.2f}"
        print(f"{r['id']:22s} {r['expected_tvc']:8.2f} {r['predicted_tvc']:9.2f} {r['kinetic_tvc']:8.2f} {gas:>6s} "
              f"{r['abs_error']:5.2f}  {r['expected_stage']:>10s} → {r['predicted_stage']:<10s}  {'✅' if r['pass'] else '❌'}")
    n = sum(r["pass"] for r in rows)
    mae = sum(r["abs_error"] for r in rows) / len(rows)
    print(f"\n{n}/{len(rows)} passed · mean absolute error {mae:.2f} log CFU/g")
