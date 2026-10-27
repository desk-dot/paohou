"""Deterministic running metrics. No model or network is needed."""
import math
import re


def number(value, label, *, optional=False, allow_zero=False):
    if value is None or value == "":
        if optional:
            return None
        raise ValueError(f"{label}不能为空")
    if isinstance(value, bool):
        raise ValueError(f"{label}必须是数字")
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是数字") from None
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{label}必须是{'非负' if allow_zero else '正'}有限数值")
    return value


def pace_seconds(value):
    """Accept M:SS, M'SS\" or Keep-style M′SS″; numeric seconds also allowed."""
    if isinstance(value, (int, float)):
        return number(value, "配速秒数")
    value = str(value).strip().replace("′", "'").replace("″", '"').replace("’", "'")
    match = re.fullmatch(r"(\d+)[:']([0-5]\d)\"?", value)
    if not match:
        raise ValueError(f"配速 {value!r} 应写为 分:秒，例如 6:05")
    return number(int(match[1]) * 60 + int(match[2]), "配速")


def format_pace(seconds):
    minutes, seconds = divmod(round(seconds), 60)
    return f"{minutes}:{seconds:02d}"


def validate_record(raw):
    if not isinstance(raw, dict):
        raise ValueError("记录必须是 JSON 对象")
    record = {}
    for key, label, zero in [
        ("total_distance_km", "总距离（km）", False),
        ("total_duration_s", "总用时（秒）", False),
        ("cadence_spm", "全程步频（步/分钟）", False),
        ("step_length_m", "全程单步步幅（米/步）", False),
        ("elevation_gain_m", "累计爬升（米）", True),
    ]:
        record[key] = number(raw.get(key), label, optional=True, allow_zero=zero)
    splits = raw.get("splits", [])
    if not isinstance(splits, list) or len(splits) > 500:
        raise ValueError("splits 必须是列表，最多 500 段")
    record["splits"] = []
    for i, split in enumerate(splits, 1):
        if not isinstance(split, dict):
            raise ValueError(f"第 {i} 段必须是对象")
        row = {
            "distance_km": number(split.get("distance_km"), f"第 {i} 段距离"),
            "pace_s_per_km": pace_seconds(split.get("pace")),
        }
        for key in ("cadence_spm", "step_length_m", "elevation_gain_m"):
            row[key] = number(split.get(key), f"第 {i} 段 {key}", optional=True,
                              allow_zero=key == "elevation_gain_m")
        record["splits"].append(row)
    if not splits and not (record["total_distance_km"] and record["total_duration_s"]):
        raise ValueError("请补充分段距离和配速，或同时提供总距离及总用时")
    uncertainties = raw.get("uncertainties", [])
    if not isinstance(uncertainties, list) or not all(isinstance(x, str) for x in uncertainties):
        raise ValueError("uncertainties 必须是字符串列表")
    record["uncertainties"] = uncertainties
    return record


def calculate_metrics(record):
    """Use reported totals when complete; otherwise use one consistent split scope."""
    splits = record["splits"]
    split_distance = sum(s["distance_km"] for s in splits)
    split_duration = sum(s["distance_km"] * s["pace_s_per_km"] for s in splits)
    warnings = list(record["uncertainties"])
    has_totals = bool(record["total_distance_km"] and record["total_duration_s"])
    distance = record["total_distance_km"] if has_totals else split_distance
    duration = record["total_duration_s"] if has_totals else split_duration
    scope = "截图全程汇总" if has_totals else "已录入分段（不一定覆盖全程）"
    if not has_totals:
        warnings.append("全程距离或用时缺失：均配速仅按已录入分段估算。")
    if splits and record["total_distance_km"]:
        if abs(split_distance - record["total_distance_km"]) > max(0.02, record["total_distance_km"] * 0.01):
            warnings.append("分段距离之和与全程距离不一致，请检查末段、重复行或漏图；分段走势仅代表已录入部分。")
    if splits and record["total_duration_s"]:
        if abs(split_duration - record["total_duration_s"]) > max(5, record["total_duration_s"] * 0.01):
            warnings.append("分段推算用时与总用时不一致，请检查暂停口径、配速识别或分段完整性。")
    if record["cadence_spm"] is None:
        warnings.append("全程平均步频缺失；不把部分分段步频当作全程平均值。")
    if record["step_length_m"] is None:
        warnings.append("全程平均步幅缺失；不据此判断跑姿。")
    if record["elevation_gain_m"] is None:
        warnings.append("全程累计爬升缺失；海拔、净高差不能替代累计爬升。")
    half_delta = None
    if len(splits) >= 2:
        midpoint = split_distance / 2
        position = first_time = 0.0
        for split in splits:
            overlap = max(0, min(split["distance_km"], midpoint - position))
            first_time += overlap * split["pace_s_per_km"]
            position += split["distance_km"]
        half_delta = ((split_duration - first_time) - first_time) / midpoint
    return {
        "distance_km": distance, "duration_s": duration,
        "average_pace_s_per_km": duration / distance,
        "average_pace": format_pace(duration / distance), "scope": scope,
        "split_distance_km": split_distance, "split_duration_s": split_duration,
        "second_minus_first_half_s_per_km": half_delta,
        "cadence_spm": record["cadence_spm"], "step_length_m": record["step_length_m"],
        "elevation_gain_m": record["elevation_gain_m"], "warnings": warnings,
        "splits": splits,
    }


COMPARE_FIELDS = ("average_pace", "cadence_spm", "step_length_m", "elevation_gain_m")
COMPARE_LABELS = {"average_pace": "均配速", "cadence_spm": "步频",
                  "step_length_m": "步幅", "elevation_gain_m": "爬升"}
_METRIC_KEY = {"average_pace": "average_pace_s_per_km"}


def _compare_tolerances(metrics):
    """Engineering tolerances per field; None when the field is missing."""
    pace = None if metrics["average_pace_s_per_km"] is None else \
        max(5, metrics["duration_s"] * 0.01) / metrics["distance_km"]
    cadence = metrics["cadence_spm"]
    step = metrics["step_length_m"]
    gain = metrics["elevation_gain_m"]
    return {
        "average_pace": pace,
        "cadence_spm": None if cadence is None else max(1, cadence * 0.01),
        "step_length_m": None if step is None else max(0.01, step * 0.01),
        "elevation_gain_m": None if gain is None else max(1, gain * 0.05),
    }


def _clean_number(value):
    value = round(value, 3)
    return int(value) if value == int(value) else value


def compare_runs(raw_runs):
    """Compare 2–20 confirmed run records pairwise using per-run tolerances.

    Verdict is "close" when the absolute difference does not exceed the sum of
    both runs' tolerances, "unknown" when either side is missing, otherwise
    "different". These are engineering tolerances, not sports-science thresholds.
    """
    if not isinstance(raw_runs, (list, tuple)) or not 2 <= len(raw_runs) <= 20:
        raise ValueError("compare_runs 需要 2 到 20 条已确认记录")
    runs = []
    for index, raw in enumerate(raw_runs, 1):
        metrics = calculate_metrics(validate_record(raw))
        runs.append({"metrics": metrics, "summary": {
            "index": index,
            "distance_km": metrics["distance_km"],
            "average_pace": metrics["average_pace"],
            "second_minus_first_half_s_per_km": metrics["second_minus_first_half_s_per_km"],
            "cadence_spm": metrics["cadence_spm"],
            "step_length_m": metrics["step_length_m"],
            "elevation_gain_m": metrics["elevation_gain_m"],
            "scope": metrics["scope"],
            "warnings": list(metrics["warnings"]),
            "tolerances": _compare_tolerances(metrics),
        }})
    comparisons = {field: [] for field in COMPARE_FIELDS}
    notes = ["前后半程差没有定义工程容差，仅返回数值，不参与 close/unknown 判定。"]
    for position_a in range(len(runs)):
        for position_b in range(position_a + 1, len(runs)):
            run_a, run_b = runs[position_a], runs[position_b]
            pair = [run_a["summary"]["index"], run_b["summary"]["index"]]
            if run_a["metrics"]["scope"] != run_b["metrics"]["scope"]:
                notes.append(f"第 {pair[0]} 次与第 {pair[1]} 次统计口径不同"
                             f"（{run_a['metrics']['scope']} vs {run_b['metrics']['scope']}），"
                             "均配速相关比较仅供参考。")
            for field in COMPARE_FIELDS:
                value_a = run_a["metrics"][_METRIC_KEY.get(field, field)]
                value_b = run_b["metrics"][_METRIC_KEY.get(field, field)]
                tol_a = run_a["summary"]["tolerances"][field]
                tol_b = run_b["summary"]["tolerances"][field]
                if None in (value_a, value_b, tol_a, tol_b):
                    comparisons[field].append({"pair": pair, "delta": None, "verdict": "unknown"})
                    notes.append(f"第 {pair[0]} 次与第 {pair[1]} 次有一方缺少{COMPARE_LABELS[field]}，比较标记为 unknown。")
                else:
                    verdict = "close" if abs(value_a - value_b) <= tol_a + tol_b else "different"
                    comparisons[field].append({"pair": pair,
                                               "delta": _clean_number(abs(value_a - value_b)),
                                               "verdict": verdict})
    for run in runs:
        index = run["summary"]["index"]
        if run["metrics"]["second_minus_first_half_s_per_km"] is None:
            notes.append(f"第 {index} 次分段不足 2 段，前后半程差未计算。")
        if run["summary"]["warnings"]:
            notes.append(f"第 {index} 次有 {len(run['summary']['warnings'])} 条数据警告，比较前请先核对。")
    return {"count": len(runs), "runs": [run["summary"] for run in runs],
            "comparisons": comparisons, "comparability_notes": notes}


def local_review(metrics):
    """Transparent fallback: observations, no invented physiology or prescriptions."""
    def display(value, unit):
        return "未提供" if value is None else f"{value:g} {unit}"
    lines = ["# 跑步复盘（本地规则版）", "", f"统计口径：{metrics['scope']}。",
             f"- 距离：{metrics['distance_km']:.2f} km；用时：{metrics['duration_s']:g} 秒。",
             f"- 平均配速：{metrics['average_pace']} /km（用时 ÷ 距离）。",
             f"- 全程步频：{display(metrics['cadence_spm'], '步/分钟')}。",
             f"- 全程单步步幅：{display(metrics['step_length_m'], '米/步')}。",
             f"- 累计爬升：{display(metrics['elevation_gain_m'], '米')}。", "", "## 分段观察"]
    delta = metrics["second_minus_first_half_s_per_km"]
    if delta is None:
        lines.append("分段不足，无法比较前后半程。")
    else:
        lines.append(f"按已录入分段的距离等分，后半程比前半程{'慢' if delta >= 0 else '快'} {abs(delta):.1f} 秒/km。跨分段边界按段内匀速估算。")
    lines.extend(["", "## 下一次如何复盘", "记录本次跑步目的、主观疲劳程度、是否停顿，以及天气和路况；下次在相似条件下比较配速与体感。",
                  "单次记录不能确定变速原因，也不能据此判定体能退步、跑姿问题或伤病。步频和步幅不设统一达标值。",
                  "缺少近期训练量和恢复情况时，不生成具体加量或高强度训练处方。", "", "## 数据待核对"])
    lines.extend(f"- {w}" for w in metrics["warnings"])
    if not metrics["warnings"]:
        lines.append("当前字段未触发一致性提醒；仍需与原图核对。")
    return "\n".join(lines)


# 比较字段：容差键 -> runs 条目中的取值键。前后半程差没有给定容差口径，
# 只随单次结果返回，不参与两两判定。
COMPARE_FIELDS = [("pace_s_per_km", "average_pace_s_per_km"),
                  ("cadence_spm", "cadence_spm"),
                  ("step_length_m", "step_length_m"),
                  ("elevation_gain_m", "elevation_gain_m")]


def compare_runs(raw_runs):
    """Compare 2-20 confirmed running records pairwise with engineering tolerances.

    Per-run tolerance: pace max(5, duration*1%)/distance; cadence max(1, v*1%);
    step length max(0.01, v*1%); elevation gain max(1, v*5%).
    A field verdicts "close" when abs diff <= sum of both runs' tolerances,
    "unknown" when either side is missing, otherwise "different".
    Tolerances are engineering checks, not sport-science thresholds.
    """
    if not isinstance(raw_runs, (list, tuple)):
        raise ValueError("compare_runs 需要记录列表")
    if not 2 <= len(raw_runs) <= 20:
        raise ValueError(f"compare_runs 需要 2 到 20 条记录，实际 {len(raw_runs)} 条")
    runs = []
    for raw in raw_runs:
        metrics = calculate_metrics(validate_record(raw))
        duration, distance = metrics["duration_s"], metrics["distance_km"]
        cadence, step_length = metrics["cadence_spm"], metrics["step_length_m"]
        gain = metrics["elevation_gain_m"]
        runs.append({
            "distance_km": distance,
            "duration_s": duration,
            "average_pace_s_per_km": metrics["average_pace_s_per_km"],
            "average_pace": metrics["average_pace"],
            "second_minus_first_half_s_per_km": metrics["second_minus_first_half_s_per_km"],
            "cadence_spm": cadence,
            "step_length_m": step_length,
            "elevation_gain_m": gain,
            "scope": metrics["scope"],
            "warnings": metrics["warnings"],
            "tolerances": {
                "pace_s_per_km": max(5, duration * 0.01) / distance,
                "cadence_spm": None if cadence is None else max(1, cadence * 0.01),
                "step_length_m": None if step_length is None else max(0.01, step_length * 0.01),
                "elevation_gain_m": None if gain is None else max(1, gain * 0.05),
            },
        })
    comparisons = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            fields = {}
            for tol_key, value_key in COMPARE_FIELDS:
                a, b = runs[i][value_key], runs[j][value_key]
                if a is None or b is None:
                    fields[tol_key] = {"values": [a, b], "abs_diff": None,
                                       "tolerance_sum": None, "verdict": "unknown"}
                    continue
                diff = abs(a - b)
                tol_sum = runs[i]["tolerances"][tol_key] + runs[j]["tolerances"][tol_key]
                fields[tol_key] = {"values": [a, b], "abs_diff": diff,
                                   "tolerance_sum": tol_sum,
                                   "verdict": "close" if diff <= tol_sum else "different"}
            comparisons.append({"pair": [i, j], "fields": fields})
    return {"runs": runs, "comparisons": comparisons}
