"""Length-independent overall risk score (v3).

Ideas (easy to explain in a viva):
  1. Count each risk CATEGORY once, not each clause. 50 "late payment" clauses
     are one late-payment risk, not 50 risks.
  2. Repeats add only a small, logarithmic bonus that is capped.
  3. Saturating curve 100 * (1 - e^(-raw/k)): grows quickly for the first
     serious risks, then slows down, and never reaches 100 by piling up flags.
  4. Severity ceiling and floor: the score stays between the floor and the
     ceiling of the WORST severity found. Only low risks -> max 25, so many low
     risks can't add up to "critical"; one critical risk -> at least 40, so a
     dangerous clause is never shown as "Low".
  5. Small density adjustment: the share of clauses that are risky moves the
     score by at most +/-10%, so a big contract is not punished just for being big.

All numbers come from the `scoring` section of configs/risk_rules.yaml.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_SCORING: dict[str, Any] = {
    "repeat_bonus_per_log": 0.15,
    "repeat_bonus_cap": 0.30,
    "saturation_k": 90,
    "severity_ceiling": {"low": 25, "medium": 55, "high": 80, "critical": 100},
    "severity_floor": {"low": 0, "medium": 0, "high": 30, "critical": 40},
    "density": {"enabled": True, "max_adjustment": 0.10, "reference_density": 0.25},
    "round_to": 1,
}
DEFAULT_WEIGHTS = {"low": 8, "medium": 16, "high": 28, "critical": 40}
SEVERITY_ORDER = ["low", "medium", "high", "critical"]


@dataclass
class ScoreBreakdown:
    overall_score: float
    raw_points: float
    base_score: float
    worst_severity: str | None
    ceiling: float
    density: float
    density_factor: float
    categories: list[dict[str, Any]] = field(default_factory=list)
    band: dict[str, Any] | None = None


def _get(flag: Any, name: str, default: Any = None) -> Any:
    if isinstance(flag, dict):
        return flag.get(name, default)
    return getattr(flag, name, default)


def _merge(defaults: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(defaults)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


def calculate_risk_score(
    flags: Iterable[Any],
    total_clauses: int,
    config: dict[str, Any] | None = None,
) -> ScoreBreakdown:
    """Compute the overall score from risk flags.

    flags: objects or dicts with flag_type, severity, confidence, clause_id.
    total_clauses: number of clauses in the whole contract (after segmentation).
    config: the parsed risk_rules.yaml (dict). Missing keys fall back to defaults.
    """
    config = config or {}
    weights = {**DEFAULT_WEIGHTS, **(config.get("severity_weights") or {})}
    sc = _merge(DEFAULT_SCORING, config.get("scoring"))
    unc = config.get("uncertainty") or {}
    threshold = float(unc.get("low_confidence_threshold", 0.55))
    penalty = float(unc.get("penalty", 4))

    # 1) group flags by category
    groups: dict[str, list[Any]] = defaultdict(list)
    for f in flags:
        groups[str(_get(f, "flag_type"))].append(f)

    if not groups:
        return ScoreBreakdown(0.0, 0.0, 0.0, None, 0.0, 0.0, 1.0, [], _band(0.0, config))

    raw = 0.0
    categories = []
    flagged_clauses: set[Any] = set()
    worst_idx = -1
    for flag_type, items in groups.items():
        severity = str(_get(items[0], "severity", "medium")).lower()
        weight = float(weights.get(severity, 10))
        best_conf = max(max(float(_get(f, "confidence", 0.5) or 0.5) for f in items), 0.25)
        clauses = {_get(f, "clause_id", id(f)) for f in items}
        flagged_clauses |= clauses
        n = len(clauses)

        # 2) small, capped, logarithmic repeat bonus
        bonus = min(sc["repeat_bonus_per_log"] * math.log(n), sc["repeat_bonus_cap"]) if n > 1 else 0.0
        points = weight * best_conf * (1 + bonus)
        if best_conf < threshold:
            points += penalty  # once per category
        raw += points
        if severity in SEVERITY_ORDER:
            worst_idx = max(worst_idx, SEVERITY_ORDER.index(severity))
        categories.append({
            "flag_type": flag_type, "severity": severity, "clauses": n,
            "best_confidence": round(best_conf, 3), "points": round(points, 2),
        })

    # 3) saturating curve
    k = float(sc["saturation_k"])
    base = 100.0 * (1.0 - math.exp(-raw / k))

    # 5) density adjustment (share of clauses that are risky), bounded +/- max_adjustment
    total = max(int(total_clauses or 0), len(flagged_clauses), 1)
    density = len(flagged_clauses) / total
    dcfg = sc["density"]
    factor = 1.0
    if dcfg.get("enabled", True):
        ref = float(dcfg["reference_density"])
        max_adj = float(dcfg["max_adjustment"])
        # density == ref -> 1.0 ; 0 -> 1-max_adj ; >= 2*ref -> 1+max_adj
        factor = 1.0 + max_adj * max(-1.0, min(1.0, (density - ref) / ref))
    score = base * factor

    # 4) severity ceiling
    worst = SEVERITY_ORDER[worst_idx] if worst_idx >= 0 else None
    ceiling = float(sc["severity_ceiling"].get(worst, 100)) if worst else 100.0
    floor = float(sc["severity_floor"].get(worst, 0)) if worst else 0.0
    score = max(floor, min(score, ceiling, 100.0))
    score = round(score, int(sc.get("round_to", 1)))

    categories.sort(key=lambda c: c["points"], reverse=True)
    return ScoreBreakdown(
        overall_score=score, raw_points=round(raw, 2), base_score=round(base, 2),
        worst_severity=worst, ceiling=ceiling, density=round(density, 3),
        density_factor=round(factor, 3), categories=categories, band=_band(score, config),
    )


def _band(score: float, config: dict[str, Any]) -> dict[str, Any] | None:
    bands = config.get("bands") or [
        {"name": "Low", "min": 0, "max": 30},
        {"name": "Medium", "min": 30, "max": 60},
        {"name": "High", "min": 60, "max": 80},
        {"name": "Critical", "min": 80, "max": 100},
    ]
    for b in bands:
        if b["min"] <= score < b["max"] or (score >= 100 and b["max"] >= 100):
            return b
    return None


def load_config(path: str | Path = "configs/risk_rules.yaml") -> dict[str, Any]:
    import yaml

    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def severity_breakdown(flags: Iterable[Any]) -> dict[str, int]:
    counts = {s: 0 for s in SEVERITY_ORDER}
    for f in flags:
        sev = str(_get(f, "severity", "medium")).lower()
        if sev in counts:
            counts[sev] += 1
        else:
            counts[sev] = 1
    return counts


def calculate_overall_risk_score(
    flags: Iterable[Any],
    config_path: str | Path = "configs/risk_rules.yaml",
    total_clauses: int | None = None,
) -> float:
    config = load_config(config_path)
    flag_list = list(flags)
    n_clauses = total_clauses if total_clauses is not None else len(flag_list)
    breakdown = calculate_risk_score(flag_list, total_clauses=n_clauses, config=config)
    return breakdown.overall_score


def severity_breakdown(flags: Iterable[Any]) -> dict[str, int]:
    counts = {s: 0 for s in SEVERITY_ORDER}
    for f in flags:
        sev = str(_get(f, "severity", "medium")).lower()
        if sev in counts:
            counts[sev] += 1
        else:
            counts[sev] = 1
    return counts


def calculate_overall_risk_score(
    flags: Iterable[Any],
    config_path: str | Path = "configs/risk_rules.yaml",
    total_clauses: int | None = None,
) -> float:
    config = load_config(config_path)
    flag_list = list(flags)
    n_clauses = total_clauses if total_clauses is not None else len(flag_list)
    breakdown = calculate_risk_score(flag_list, total_clauses=n_clauses, config=config)
    return breakdown.overall_score
