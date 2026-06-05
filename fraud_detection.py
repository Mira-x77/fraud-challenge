"""
Défi — Détection de fraude financière.

Vous devez implémenter la fonction `detect_fraud`.
La fonction `load_transactions` vous est FOURNIE (ne la modifiez pas).
"""

import csv
import math
from collections import defaultdict
from datetime import datetime, timezone

COUNTRY_CENTROIDS = {
    "FR": (46.23, 2.21),
    "TG": (8.62, 0.82),
    "NG": (9.08, 8.68),
    "US": (37.09, -95.71),
    "GB": (55.38, -3.44),
    "DE": (51.17, 10.45),
    "SN": (14.50, -14.45),
    "CI": (7.54, -5.55),
    "GH": (7.95, -1.02),
    "CN": (35.86, 104.20),
}

TRAVEL_KEYWORDS = ("airline", "flight", "travel", "airport")

SIGNAL_ORDER = (
    "cnp",
    "velocity",
    "geo",
    "amount",
    "ato",
    "refund",
    "structuring",
    "duplicate",
)


def load_transactions(path):
    """Lit un fichier CSV de transactions et renvoie une liste de dicts."""
    transactions = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            transactions.append(_clean_row(row))
    return transactions


def _clean_row(row):
    def get(key):
        v = row.get(key)
        return v.strip() if isinstance(v, str) and v.strip() != "" else None

    amount_raw = get("amount")
    try:
        amount = float(amount_raw) if amount_raw is not None else None
    except ValueError:
        amount = None

    card_raw = get("card_present")
    if card_raw is None:
        card_present = None
    else:
        card_present = card_raw.lower() in ("true", "1", "yes", "oui")

    return {
        "transaction_id": get("transaction_id"),
        "timestamp": get("timestamp"),
        "user_id": get("user_id"),
        "amount": amount,
        "currency": get("currency"),
        "merchant": get("merchant"),
        "country": get("country"),
        "card_present": card_present,
    }


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    r = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat1 - lat2
    dlon = lon1 - lon2
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def _parse_timestamp(ts):
    if ts is None or not isinstance(ts, str):
        return None
    try:
        normalized = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return None


def _build_user_index(transactions):
    index = defaultdict(list)
    for txn in transactions:
        user_id = txn.get("user_id")
        if user_id is not None:
            index[user_id].append(txn)
    return index


def _sorted_user_txns(user_txns, parsed_ts):
    return sorted(
        user_txns,
        key=lambda t: (
            parsed_ts.get(t.get("transaction_id")) or datetime.min.replace(tzinfo=timezone.utc),
            t.get("transaction_id") or "",
        ),
    )


def _detect_level1(txn):
    signals = []
    amount = txn.get("amount")

    if txn.get("timestamp") is None or _parse_timestamp(txn.get("timestamp")) is None:
        signals.append((0.90, "Missing timestamp field"))

    if txn.get("user_id") is None:
        signals.append((0.90, "Missing user_id field"))

    if amount is None:
        signals.append((0.90, "Missing or invalid amount field"))
    elif amount < 0:
        signals.append((0.95, "Negative amount detected"))
    elif amount == 0:
        signals.append((0.85, "Zero amount detected"))

    return signals


def _fuse_level1(signals):
    score = max(s for s, _ in signals)
    reason = "; ".join(r for _, r in signals)
    return score, reason


def _most_frequent_country(user_txns):
    counts = defaultdict(int)
    for txn in user_txns:
        country = txn.get("country")
        if country:
            counts[country] += 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def _travel_exception(txn, user_txns):
    country = txn.get("country")
    merchant = (txn.get("merchant") or "").lower()
    if not country or not any(kw in merchant for kw in TRAVEL_KEYWORDS):
        return False

    mode_country = _most_frequent_country(user_txns)
    if mode_country is None or country == mode_country:
        return False

    other_countries = {
        t.get("country")
        for t in user_txns
        if t.get("transaction_id") != txn.get("transaction_id") and t.get("country")
    }
    other_countries.discard(mode_country)
    return len(other_countries) == 0


def _detect_cnp(txn):
    if txn.get("card_present") is not False:
        return None
    amount = txn.get("amount")
    if amount is None or amount <= 500:
        return None
    score = 0.92 if amount > 1000 else 0.80
    return ("cnp", score, f"Card Not Present: amount {amount}")


def _detect_velocity(txn, user_sorted, parsed_ts):
    tid = txn.get("transaction_id")
    if parsed_ts.get(tid) is None:
        return None

    times = []
    for t in user_sorted:
        t_ts = parsed_ts.get(t.get("transaction_id"))
        if t_ts is not None:
            times.append((t_ts, t.get("transaction_id")))

    best_count = 0
    for anchor_time, _ in times:
        window_txns = sorted(
            [(t_time, t_id) for t_time, t_id in times if 0 <= (t_time - anchor_time).total_seconds() < 60],
            key=lambda x: (x[0], x[1]),
        )
        ids = [t_id for _, t_id in window_txns]
        if len(window_txns) > 5 and tid in ids and ids.index(tid) >= 5:
            best_count = max(best_count, len(window_txns))

    if best_count == 0:
        return None

    return ("velocity", 0.90, f"velocity attack: {best_count} transactions in 60s window")


def _detect_geo(txn, user_sorted, parsed_ts):
    tid = txn.get("transaction_id")
    ts = parsed_ts.get(tid)
    country = txn.get("country")
    if ts is None or not country:
        return None

    prior = []
    for t in user_sorted:
        if t.get("transaction_id") == tid:
            break
        prior.append(t)

    if not prior:
        return None

    last = prior[-1]
    prev_country = last.get("country")
    if not prev_country or prev_country == country:
        return None

    if country not in COUNTRY_CENTROIDS or prev_country not in COUNTRY_CENTROIDS:
        return None

    prev_ts = parsed_ts.get(last.get("transaction_id"))
    if prev_ts is None:
        return None

    lat1, lon1 = COUNTRY_CENTROIDS[prev_country]
    lat2, lon2 = COUNTRY_CENTROIDS[country]
    distance = haversine(lat1, lon1, lat2, lon2)
    elapsed_hours = (ts - prev_ts).total_seconds() / 3600.0
    if elapsed_hours <= 0 or elapsed_hours >= distance / 900:
        return None

    minutes = int(round((ts - prev_ts).total_seconds() / 60.0))
    return (
        "geo",
        0.97,
        f"Geographic impossibility: {prev_country}→{country} in {minutes} minutes",
    )


def _detect_amount_anomaly(txn, user_txns):
    amount = txn.get("amount")
    if amount is None or amount <= 0:
        return None

    others = [
        t for t in user_txns if t.get("transaction_id") != txn.get("transaction_id")
    ]
    past_amts = [t["amount"] for t in others if isinstance(t.get("amount"), (int, float)) and t["amount"] > 0]
    if not past_amts:
        return None

    user_mean = sum(past_amts) / len(past_amts)
    if user_mean <= 0 or amount <= 3 * user_mean:
        return None

    score = min(1.0, (amount / user_mean) * 0.1)
    return ("amount", score, "Montant très supérieur à l'habitude du client")


def _detect_ato(txn, user_txns):
    merchant = txn.get("merchant")
    amount = txn.get("amount")
    if merchant is None or amount is None or amount <= 0:
        return None

    others = [
        t for t in user_txns if t.get("transaction_id") != txn.get("transaction_id")
    ]
    if not others:
        return None

    seen = {t.get("merchant") for t in others if t.get("merchant") is not None}
    if merchant in seen:
        return None

    threshold = 1000 if len(others) == 1 else 300
    if amount <= threshold:
        return None

    return ("ato", 0.85, f"new merchant {merchant}")


def _detect_refund(txn, user_txns, parsed_ts):
    amount = txn.get("amount")
    merchant = txn.get("merchant")
    tid = txn.get("transaction_id")
    ts = parsed_ts.get(tid)
    if amount is None or amount >= 0 or merchant is None or ts is None:
        return None

    refunds = []
    for t in user_txns:
        t_amt = t.get("amount")
        t_merchant = t.get("merchant")
        t_ts = parsed_ts.get(t.get("transaction_id"))
        if (
            t_amt is not None
            and t_amt < 0
            and t_merchant is not None
            and t_merchant.lower() == merchant.lower()
            and t_ts is not None
        ):
            refunds.append((t_ts, t))

    refunds.sort(key=lambda x: (x[0], x[1].get("transaction_id", "")))
    for i, (end_ts, end_txn) in enumerate(refunds):
        window = [
            t for t_ts, t in refunds
            if 0 <= (end_ts - t_ts).total_seconds() <= 86400
        ]
        if len(window) >= 3 and end_txn.get("transaction_id") == tid:
            return ("refund", 0.85, f"refund fraud at {merchant}")

    # Check if this refund is part of any qualifying 24h group
    for anchor_ts, anchor_txn in refunds:
        if anchor_txn.get("transaction_id") != tid:
            continue
        group = [
            t for t_ts, t in refunds
            if 0 <= (anchor_ts - t_ts).total_seconds() <= 86400
        ]
        if len(group) >= 3:
            return ("refund", 0.85, f"refund fraud at {merchant}")

    return None


def _detect_structuring(txn, user_txns, parsed_ts):
    amount = txn.get("amount")
    tid = txn.get("transaction_id")
    ts = parsed_ts.get(tid)
    if amount is None or ts is None:
        return None

    for threshold in range(100, 10001, 100):
        if not (threshold - 10 <= amount < threshold):
            continue

        candidates = []
        for t in user_txns:
            t_amt = t.get("amount")
            t_ts = parsed_ts.get(t.get("transaction_id"))
            if (
                t_amt is not None
                and threshold - 10 <= t_amt < threshold
                and t_ts is not None
            ):
                candidates.append((t_ts, t))

        for anchor_ts, _ in candidates:
            group = sorted(
                [
                    (t_ts, t)
                    for t_ts, t in candidates
                    if 0 <= (t_ts - anchor_ts).total_seconds() <= 3600
                ],
                key=lambda x: (x[0], x[1].get("transaction_id", "")),
            )
            ids = [t.get("transaction_id") for _, t in group]
            if len(group) >= 3 and tid in ids:
                return ("structuring", 0.90, f"structuring near threshold {threshold}")

    return None


def _detect_duplicate(txn, user_txns, parsed_ts):
    tid = txn.get("transaction_id")
    amount = txn.get("amount")
    merchant = txn.get("merchant")
    ts = parsed_ts.get(tid)
    if amount is None or merchant is None or ts is None:
        return None

    same = []
    for t in user_txns:
        t_ts = parsed_ts.get(t.get("transaction_id"))
        if (
            t.get("amount") == amount
            and t.get("merchant") == merchant
            and t_ts is not None
        ):
            same.append((t_ts, t.get("transaction_id")))

    same.sort(key=lambda x: (x[0], x[1]))
    if len(same) < 2:
        return None

    first_ts, first_id = same[0]
    if tid == first_id:
        return None

    for other_ts, other_id in same:
        if other_id == tid:
            continue
        if abs((ts - other_ts).total_seconds()) <= 300:
            return ("duplicate", 0.95, f"duplicate charge at {merchant}")

    return None


def _collect_signals(txn, user_txns, user_sorted, parsed_ts):
    signals = []

    for detector in (
        lambda: _detect_cnp(txn),
        lambda: _detect_velocity(txn, user_sorted, parsed_ts),
        lambda: _detect_geo(txn, user_sorted, parsed_ts),
        lambda: _detect_amount_anomaly(txn, user_txns),
        lambda: _detect_ato(txn, user_txns),
        lambda: _detect_refund(txn, user_txns, parsed_ts),
        lambda: _detect_structuring(txn, user_txns, parsed_ts),
        lambda: _detect_duplicate(txn, user_txns, parsed_ts),
    ):
        result = detector()
        if result is not None:
            signals.append(result)

    if len(user_txns) == 1:
        signals = [s for s in signals if s[0] not in ("velocity", "amount")]

    return signals


def _fuse_signals(signals):
    if not signals:
        return 0.0, "No fraud pattern detected"

    ordered = sorted(signals, key=lambda s: SIGNAL_ORDER.index(s[0]))
    scores = [s[1] for s in ordered]
    n = len(scores)
    fused = min(1.0, max(scores) + 0.05 * (n - 1))
    reason = "; ".join(s[2] for s in ordered)
    return fused, reason


def _make_result(txn, score, reason):
    score = round(min(max(float(score), 0.0), 1.0), 2)
    return {
        "transaction_id": txn.get("transaction_id") or "UNKNOWN",
        "fraud_score": score,
        "is_suspicious": score >= 0.5,
        "reason": reason or "No fraud pattern detected",
    }


def detect_fraud(transactions):
    """Analyse une liste de transactions et renvoie un verdict pour chacune."""
    if not transactions:
        return []

    parsed_ts = {t.get("transaction_id"): _parse_timestamp(t.get("timestamp")) for t in transactions}
    user_index = _build_user_index(transactions)
    results = []

    for txn in transactions:
        level1 = _detect_level1(txn)
        if level1:
            score, reason = _fuse_level1(level1)
            results.append(_make_result(txn, score, reason))
            continue

        user_id = txn.get("user_id")
        user_txns = user_index.get(user_id, [txn])
        user_sorted = _sorted_user_txns(user_txns, parsed_ts)

        if _travel_exception(txn, user_txns):
            results.append(_make_result(txn, 0.0, "Transaction conforme au profil du client"))
            continue

        signals = _collect_signals(txn, user_txns, user_sorted, parsed_ts)
        score, reason = _fuse_signals(signals)
        if not signals:
            reason = "Transaction conforme au profil du client"
        results.append(_make_result(txn, score, reason))

    return results
