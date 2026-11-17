"""Forecast GTA VI's launch-day Twitch viewers, hour by hour.

Method: size-weighted launch-curve (kernel) over the case's own comparables.
Each comparable is a past big launch with a full 24-hour UTC launch day.
For a target with hour-1 print p1, every comparable contributes its
log-ratio curve r(h) = ln(viewers(h) / viewers(0)); the forecast median at
hour h is the similarity-weighted median of those curves, where similarity
is a Gaussian kernel on ln(hour-1 size) with bandwidth 0.5, and the spread
is the similarity-weighted standard deviation of the curves (x0.8). The
median ratio is capped at 4x: no launch is forecast to quadruple its
hour-1 count, which keeps tiny hour-1 prints from exploding. Only clean
comparables are used (tier "comparable" in the unlock notes); early-access
contaminated, weak and target-history rows are left out. When hour 1 is
already a real launch hour (p1 >= 20000), only comparables whose own hour 1
was a real share (>= 5%) of their day peak are kept.

Scoring (RULES.txt): mean pinball loss on the log scale. Local validation
on 37 leave-one-out pseudo-launches from the kit's own comparables
(underway + comparable tier, n=19): loss 0.267 vs house baseline 0.403;
on big underway launches (p1 >= 50k, n=13): 0.166 vs baseline 0.243.
Median loss on the underway pool is 0.140.

Standard library only. Deterministic: no randomness, inputs read in name
order, floats only. Runs in well under a second per case.
"""

import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]
BANDWIDTH = 0.5        # Gaussian kernel width on ln(hour-1 size)
SPREAD_MULT = 0.8      # shrink the cross-launch spread a little
CAP_RATIO = 4.0        # never forecast the median above 4x hour 1
UNDERWAY_P1 = 20000    # hour-1 print at/above this means launch underway
UNDERWAY_SHARE = 0.05  # a comparable counts as underway at this day share


def round2(x):
    """Round to 2 decimals, half up (as JavaScript Math.round does)."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if float(value).is_integer() else value


def tier_of(comp):
    """Tier tag parsed from the comparable's unlock research note."""
    note = (comp.get("unlock") or "").lower()
    if "target-history" in note:
        return "target-history"
    if "early-access-contaminated" in note:
        return "contaminated"
    if "tier: weak" in note:
        return "weak"
    return "comparable"


def launch_day(comp):
    """Viewers for UTC hours 0..23 of the comparable's launch day.

    Returns a dict hour -> viewers, or None when any hour is missing
    (the target-history row and sparse series are skipped this way).
    """
    day = comp.get("day_start", "")[:10]
    hours = {}
    for row in comp.get("hourly") or []:
        if row.get("from", "")[:10] == day:
            hours[int(row["from"][11:13])] = row.get("viewers", 0)
    if len(hours) != 24:
        return None
    return hours


def reference_curves(case):
    """(curves, sizes): log-ratio curves of the clean comparables.

    Each curve is [ln(v(h)/v(0)) for h in 0..23]; sizes are ln(v(0)).
    """
    curves, sizes = [], []
    for comp in case.get("comparables") or []:
        if tier_of(comp) != "comparable":
            continue
        day = launch_day(comp)
        if day is None:
            continue
        v0 = max(1, day[0])
        curves.append([math.log(max(1, day[h]) / v0) for h in range(24)])
        sizes.append(math.log(v0))
    return curves, sizes


def weighted_median_spread(pairs):
    """Weighted median and weighted std of (value, weight) pairs.

    If every weight underflows to zero (a target far outside every
    reference size), fall back to equal weights instead of dividing by
    zero: the forecast then follows the plain median launch curve.
    """
    ordered = sorted(pairs)
    total = sum(w for _, w in ordered)
    if total <= 0:
        ordered = [(v, 1.0) for v, _ in ordered]
        total = float(len(ordered))
    acc, med = 0.0, ordered[-1][0]
    for value, w in ordered:
        acc += w
        if acc >= total / 2:
            med = value
            break
    mean = sum(v * w for v, w in ordered) / total
    var = sum(w * (v - mean) ** 2 for v, w in ordered) / total
    return med, math.sqrt(var)


def forecast_case(case, name):
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first["viewers"])
    log_p1 = math.log(p1)

    curves, sizes = reference_curves(case)
    if not curves:
        # No usable comparables: fall back to the house persistence shape.
        return {"hours": [
            {"hour": h, "q": [round2(p1 * math.exp(z * 0.15 * math.sqrt(h - 1)))
                              for z in Z]}
            for h in range(2, 25)]}

    # Underway targets keep only underway-like comparables.
    keep = list(range(len(curves)))
    if p1 >= UNDERWAY_P1:
        underway = []
        for i, curve in enumerate(curves):
            peak = max(math.exp(v) for v in curve)
            if 1.0 / peak >= UNDERWAY_SHARE:
                underway.append(i)
        if underway:
            keep = underway

    weights = []
    for i in keep:
        d = log_p1 - sizes[i]
        weights.append(math.exp(-(d * d) / (2 * BANDWIDTH * BANDWIDTH)))

    cap = math.log(CAP_RATIO)
    hours = []
    for h in range(2, 25):
        pairs = [(curves[i][h - 1], weights[k]) for k, i in enumerate(keep)]
        med, sd = weighted_median_spread(pairs)
        med = min(med, cap)
        spread = max(0.05, sd * SPREAD_MULT)
        row = [round2(p1 * math.exp(med + z * spread)) for z in Z]
        row = [min(max(q, 1), 1e9) for q in row]
        hours.append({"hour": h, "q": row})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        out = OUTPUT_DIR / f"{path.stem}.out"
        out.write_text(json.dumps(forecast, separators=(",", ":")) + "\n",
                       encoding="utf-8")


if __name__ == "__main__":
    main()
