import hashlib
import io
import json
import os
from pathlib import Path

import pandas as pd
from PIL import Image, UnidentifiedImageError
import streamlit as st

from agent import review_run
from analysis_tools import calculate_metrics, local_review, validate_record
from model_client import ModelClient, ModelError, extract_record

st.set_page_config(page_title="跑后 · Keep 跑步复盘", page_icon=":material/directions_run:", layout="wide")
for key, default in {"record": None, "version": 0, "report": None, "source": ""}.items():
    st.session_state.setdefault(key, default)

st.title("跑后 · 把一次跑步读明白")
st.caption("上传 Keep 截图 → 核对数据 → 查看复盘与下一次的关注点")

with st.sidebar:
    st.subheader("模型连接")
    st.caption("截图识别需要图片输入能力；AI 复盘需要工具调用能力。填写服务商实际提供的配置。")
    base_url = st.text_input("API Base URL", value=os.getenv("RUN_BASE_URL", ""), placeholder="https://服务商地址/v1")
    api_key = st.text_input("API Key", value=os.getenv("RUN_API_KEY", ""), type="password")
    vision_model = st.text_input("截图识别模型", value=os.getenv("RUN_VISION_MODEL", ""))
    review_model = st.text_input("复盘模型", value=os.getenv("RUN_REVIEW_MODEL", ""))
    st.caption("配置只保留在当前会话内。也可通过 RUN_* 环境变量配置。")
    if st.button("清空本次会话", key="clear"):
        st.session_state.clear()
        st.rerun()


def load_record(record, source):
    st.session_state.record = record
    st.session_state.version += 1
    st.session_state.report = None
    st.session_state.source = source


st.subheader("1 · 导入一次跑步")
uploads = st.file_uploader("上传同一次跑步的总览、分段配速及步频/步幅截图", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
upload_signature = hashlib.sha256(b"".join(f.getvalue() for f in uploads)).hexdigest()
if st.session_state.get("upload_signature") != upload_signature:
    st.session_state.upload_signature = upload_signature
    st.session_state.record = None
    st.session_state.report = None
    st.session_state.version += 1
if uploads:
    with st.expander("查看已上传截图"):
        for uploaded in uploads[:6]:
            try:
                st.image(uploaded.getvalue(), caption=uploaded.name, width=320, alt="待识别的 Keep 跑步记录截图")
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                st.warning("有一张文件无法作为图片预览，请移除后重新上传。")
consent = st.checkbox("允许将这些截图发送至上方填写的模型服务商进行识别", key=f"consent_{upload_signature}")
with st.container(horizontal=True):
    recognize = st.button("识别截图", type="primary", disabled=not uploads or not consent, key="recognize")
    demo = st.button("体验示例数据", key="demo")
    manual = st.button("手动录入", key="manual")
if demo:
    load_record(json.loads((Path(__file__).parent / "examples/demo.json").read_text(encoding="utf-8")), "人工构造示例 · 非真实跑步记录")
if manual:
    load_record({"splits": [], "uncertainties": []}, "手动录入")
if recognize and consent and uploads:
    try:
        client = ModelClient(base_url, api_key, vision_model)
        images = []
        if len(uploads) > 6 or sum(f.size for f in uploads) > 20 * 1024 * 1024:
            raise ModelError("每次最多 6 张截图，总大小不超过 20 MB。")
        for uploaded in uploads:
            data = uploaded.getvalue()
            with Image.open(io.BytesIO(data)) as img:
                mime = Image.MIME.get(img.format)
                img.verify()
            images.append((data, mime))
        with st.spinner("正在提取截图中的数据，请稍候…"):
            load_record(extract_record(client, images), "Keep 截图识别 · 请逐项核对")
    except (ModelError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
        st.error("截图识别失败：请检查图片、模型名称、接口配置及图片输入能力；也可先手动录入。")

if st.session_state.record is None:
    st.info("先上传截图，或点击“体验示例数据”。未配置模型也能体验本地复盘。")
    st.stop()

st.subheader("2 · 对照原图确认数据")
st.caption(st.session_state.source)
raw = st.session_state.record
version = st.session_state.version
labels = {
    "total_distance_km": "总距离（km）", "total_duration_s": "总用时（秒）",
    "cadence_spm": "全程平均步频（步/分钟）", "step_length_m": "全程平均单步步幅（米/步）",
    "elevation_gain_m": "累计爬升（米）",
}
edited = {}
with st.container(horizontal=True):
    for key, label in labels.items():
        value = raw.get(key)
        edited[key] = st.text_input(label, value="" if value is None else str(value), key=f"{key}_{version}").strip() or None
st.caption("空白表示未知。用时填写秒，例如 31 分钟填 1860；步幅如显示 95 cm，应填 0.95。")
split_labels = {"distance_km": "本段距离（km）", "pace": "配速（分:秒/km）", "cadence_spm": "步频（步/分钟）", "step_length_m": "单步步幅（米/步）", "elevation_gain_m": "本段爬升（米）"}
rows = [{label: "" if row.get(key) is None else str(row[key]) for key, label in split_labels.items()}
        for row in raw.get("splits", []) if isinstance(row, dict)]
frame = pd.DataFrame(rows, columns=list(split_labels.values()), dtype=str)
table = st.data_editor(frame, num_rows="dynamic", hide_index=True, key=f"splits_{version}", alt="可核对和修改的逐段跑步数据")
edited["splits"] = []
for row in table.to_dict("records"):
    clean = {key: None if pd.isna(row[label]) or str(row[label]).strip() == "" else str(row[label]).strip()
             for key, label in split_labels.items()}
    if any(v is not None for v in clean.values()):
        edited["splits"].append(clean)
uncertainties = raw.get("uncertainties", [])
if not isinstance(uncertainties, list):
    uncertainties = [str(uncertainties)]
notes = st.text_area("识别疑点与核对说明（确认解决后可修改）", value="\n".join(str(x) for x in uncertainties), key=f"notes_{version}")
edited["uncertainties"] = [x for x in notes.splitlines() if x.strip()]
context = st.text_area("补充背景（可选）", placeholder="本次跑步目的、体感、近期训练量、天气或停顿情况", key=f"context_{version}")
signature = hashlib.sha256(json.dumps([edited, context, base_url, review_model], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
try:
    record = validate_record(edited)
    metrics = calculate_metrics(record)
except ValueError as exc:
    st.error(str(exc))
    st.stop()
with st.container(horizontal=True):
    st.metric("统计距离", f"{metrics['distance_km']:.2f} km")
    st.metric("平均配速", metrics["average_pace"] + " /km")
    st.metric("统计用时", f"{metrics['duration_s'] / 60:.1f} 分钟")
st.caption("统计口径：" + metrics["scope"])
for warning in metrics["warnings"]:
    st.warning(warning)
if record["splits"]:
    chart = pd.DataFrame([{"分段": i, "配速（秒/km，越低越快）": s["pace_s_per_km"]} for i, s in enumerate(record["splits"], 1)])
    st.line_chart(chart, x="分段", y="配速（秒/km，越低越快）", alt="各分段配速，数值越低表示速度越快")

confirmed = st.checkbox("我已对照原图核对数据，并了解以上缺失或不一致提示", key=f"confirmed_{signature}_{version}")
st.subheader("3 · 生成复盘")
st.caption("AI 复盘会将确认后的数据与补充背景发送给模型服务商。本地规则复盘不访问网络。")
with st.container(horizontal=True):
    local = st.button("生成本地复盘", disabled=not confirmed, key="local")
    online = st.button("生成 AI 复盘", type="primary", disabled=not confirmed, key="online")
if local and confirmed:
    st.session_state.report = {"signature": signature, "text": local_review(metrics), "trace": [{"step": "local_analysis", "result": metrics}]}
if online and confirmed:
    try:
        with st.spinner("正在调用分析工具并生成复盘…"):
            text, trace = review_run(ModelClient(base_url, api_key, review_model), edited, context)
        st.session_state.report = {"signature": signature, "text": "# AI 跑步复盘（请结合体感判断）\n\n" + text, "trace": trace}
    except ModelError as exc:
        st.error(str(exc))
        st.session_state.report = None
result = st.session_state.report
if result and result["signature"] == signature and confirmed:
    st.markdown(result["text"])
    st.download_button("下载复盘 Markdown", result["text"], file_name="running-review.md", mime="text/markdown")
    st.download_button("下载确认数据 JSON", json.dumps(edited, ensure_ascii=False, indent=2), file_name="confirmed-run.json", mime="application/json")
    with st.expander("查看分析执行记录"):
        st.json(result["trace"])
        st.download_button("下载执行记录", json.dumps(result["trace"], ensure_ascii=False, indent=2), file_name="agent-trace.json", mime="application/json")
