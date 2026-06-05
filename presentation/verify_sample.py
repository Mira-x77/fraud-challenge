import json
import sys

sys.path.insert(0, ".")
from fraud_detection import load_transactions, detect_fraud

expected = {e["transaction_id"]: e for e in json.load(open("data/sample_expected.json"))}
results = {r["transaction_id"]: r for r in detect_fraud(load_transactions("data/sample_transactions.csv"))}

ok = True
for tid, exp in expected.items():
    got = results[tid]
    match = (
        got["is_suspicious"] == exp["is_suspicious"]
        and got["reason"] == exp["reason"]
        and abs(got["fraud_score"] - exp["fraud_score"]) < 0.01
    )
    status = "OK" if match else "MISMATCH"
    if not match:
        ok = False
    print(f"{tid}: {status}")
    if not match:
        print(f"  expected: {exp}")
        print(f"  got:      {got}")

print("\nALL MATCH" if ok else "\nDIFFERENCES FOUND")
sys.exit(0 if ok else 1)
