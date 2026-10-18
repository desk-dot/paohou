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
