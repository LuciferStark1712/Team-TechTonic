from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="ThreatSense Dashboard", layout="wide", initial_sidebar_state="expanded")

RISK_RED = "#ef4444"
RISK_AMBER = "#f59e0b"
RISK_GREEN = "#22c55e"

EVENT_BADGE = {
    "running": "🔴 Running",
    "loitering": "🟡 Loitering",
    "normal": "🟢 Normal",
}


def video_name_from_file(path: Path) -> str:
    name = path.stem
    if name == "alerts":
        return "single_run"
    if name.startswith("alerts_"):
        return name[len("alerts_") :]
    return name


def normalize_event(event: str) -> str:
    e = str(event).strip().lower()
    if "run" in e:
        return "running"
    if "loiter" in e:
        return "loitering"
    return "normal"


def risk_level_from_score(score: float) -> str:
    if score > 0.7:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def risk_color(level: str) -> str:
    if level == "HIGH":
        return RISK_RED
    if level == "MEDIUM":
        return RISK_AMBER
    return RISK_GREEN


def load_alert_frames(files: list[Path]) -> tuple[pd.DataFrame, list[dict]]:
    frames: list[pd.DataFrame] = []
    file_status: list[dict] = []

    for f in files:
        vname = video_name_from_file(f)
        try:
            df = pd.read_csv(f)
        except Exception:
            file_status.append({"file": f.name, "rows": "unreadable"})
            continue

        file_status.append({"file": f.name, "rows": len(df)})
        if df.empty:
            continue

        df["video_name"] = vname
        frames.append(df)

    alerts = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return alerts, file_status


# ---------- File discovery ----------
logs_dir = Path("outputs/logs")
all_csv_files = sorted(logs_dir.glob("alerts*.csv"))

if not all_csv_files:
    st.title("ThreatSense AI-DVR")
    st.info(
        "No alert logs found yet.\n\n"
        "Steps:\n"
        "1. Run inference on recorded video or webcam\n"
        "2. Confirm CSV logs exist in outputs/logs\n"
        "3. Reload dashboard"
    )
    st.stop()

recorded_files: list[Path] = []
live_files: list[Path] = []
for f in all_csv_files:
    vname = video_name_from_file(f)
    if vname.startswith("webcam_"):
        live_files.append(f)
    else:
        recorded_files.append(f)

recorded_footages_uploaded = len({video_name_from_file(f) for f in recorded_files})


# ---------- Header + mode ----------
st.title("ThreatSense AI-DVR")
st.caption("Threat summary by mode")

with st.sidebar:
    st.header("View")
    mode = st.radio("Mode", ["Recorded", "Live"], index=0)

if mode == "Recorded":
    selected_files = recorded_files
    mode_label = "Recorded Footage"
    live_session_name = ""
else:
    if live_files:
        latest_live_file = max(live_files, key=lambda p: p.stat().st_mtime)
        selected_files = [latest_live_file]
        live_session_name = video_name_from_file(latest_live_file)
    else:
        selected_files = []
        live_session_name = ""
    mode_label = "Latest Live Session"

if not selected_files:
    if mode == "Recorded":
        st.warning("No recorded-footage logs found yet.")
    else:
        st.warning("No live webcam session logs found yet.")
    st.stop()

alerts, file_status = load_alert_frames(selected_files)

if alerts.empty:
    st.warning(f"{mode_label} found, but there are no alert rows yet.")
    st.dataframe(pd.DataFrame(file_status), use_container_width=True)
    st.stop()


# ---------- Prepare alert dataframe ----------
alerts = alerts.copy()
alerts["event_type"] = alerts["event_type"].apply(normalize_event)
alerts["risk_score"] = pd.to_numeric(alerts["risk_score"], errors="coerce").fillna(0.0)
alerts["timestamp_s"] = pd.to_numeric(alerts.get("timestamp_s", 0), errors="coerce").fillna(0.0)
alerts["snapshot_file"] = alerts["snapshot_path"].astype(str).apply(lambda x: Path(x).name)
alerts["event_badge"] = alerts["event_type"].map(EVENT_BADGE).fillna("🟢 Normal")
alerts = alerts.reset_index(drop=True)


# ---------- Threat summary ----------
mean_risk = float(alerts["risk_score"].mean())
max_risk = float(alerts["risk_score"].max())
threat_score = round((0.4 * mean_risk + 0.6 * max_risk) * 100.0, 1)
overall_level = risk_level_from_score(threat_score / 100.0)
color = risk_color(overall_level)

subtitle = mode_label
if mode == "Live" and live_session_name:
    subtitle = f"{mode_label}: {live_session_name}"

st.markdown(f"**{subtitle}**")
st.markdown(
    f"""
    <div style=\"background:#0f172a;border:1px solid #1f2937;border-radius:12px;padding:16px;\">
      <div style=\"font-size:14px;color:#94a3b8;\">Overall Threat Score</div>
      <div style=\"font-size:40px;font-weight:700;color:{color};line-height:1.1;\">{threat_score}/100</div>
      <div style=\"font-size:16px;font-weight:600;color:{color};\">Risk Level: {overall_level}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Alerts", int(len(alerts)))
c2.metric("High Risk Alerts", int((alerts["risk_score"] > 0.7).sum()))
c3.metric("Running", int((alerts["event_type"] == "running").sum()))
c4.metric("Loitering", int((alerts["event_type"] == "loitering").sum()))
if mode == "Recorded":
    c5.metric("Footages Uploaded", int(recorded_footages_uploaded))
else:
    c5.metric("Live Sessions", int(len(live_files)))


# ---------- Trend ----------
st.subheader("Risk Trend")
trend = alerts.sort_values("timestamp_s").copy()
trend = trend[["timestamp_s", "risk_score"]].rename(columns={"timestamp_s": "time_s"})
st.line_chart(trend.set_index("time_s"))


# ---------- Alert table ----------
st.subheader("Recent Alerts")
show_cols = [
    "event_badge",
    "risk_score",
    "timestamp_s",
    "video_name",
    "track_id",
    "frame_idx",
    "snapshot_file",
    "explanation",
]
st.dataframe(alerts[show_cols].sort_values("timestamp_s", ascending=False), use_container_width=True, height=320)


# ---------- Snapshot ----------
st.subheader("Snapshot")
idx = st.number_input("Select alert row", min_value=0, max_value=max(len(alerts) - 1, 0), value=0, step=1)
row = alerts.iloc[int(idx)]
snap = Path(str(row["snapshot_path"]))
st.write(f"Event: {row['event_badge']} | Risk: {row['risk_score']:.2f} | Video: {row['video_name']}")
st.write(f"Explanation: {row['explanation']}")
if snap.exists():
    st.image(str(snap), caption=row["snapshot_file"], use_column_width=True)
else:
    st.info("Snapshot not found for this alert.")
