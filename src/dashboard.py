from __future__ import annotations

from pathlib import Path
import subprocess
import sys

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


def detect_sustained_high_risk(
    alerts: pd.DataFrame,
    threshold: float = 0.7,
    min_duration_s: float = 60.0,
    max_gap_s: float = 8.0,
) -> tuple[bool, float]:
    if alerts.empty or "timestamp_s" not in alerts.columns or "risk_score" not in alerts.columns:
        return False, 0.0

    high = alerts[alerts["risk_score"] >= threshold].sort_values("timestamp_s")
    if high.empty:
        return False, 0.0

    best_span = 0.0
    start_t = float(high.iloc[0]["timestamp_s"])
    prev_t = start_t

    for _, row in high.iloc[1:].iterrows():
        t = float(row["timestamp_s"])
        if t - prev_t <= max_gap_s:
            prev_t = t
            best_span = max(best_span, prev_t - start_t)
            continue
        start_t = t
        prev_t = t

    return best_span >= min_duration_s, round(best_span, 1)


@st.cache_data(ttl=2, show_spinner=False)
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

    cols = ["timestamp_s", "frame_idx", "track_id", "risk_score", "event_type", "confidence", "explanation", "snapshot_path", "video_name"]
    alerts = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)
    return alerts, file_status


# ---------- File discovery ----------
logs_dir = Path("outputs/logs")
all_csv_files = sorted(logs_dir.glob("alerts*.csv"))
project_root = Path(__file__).resolve().parents[1]

recorded_files: list[Path] = []
live_files: list[Path] = []
for f in all_csv_files:
    vname = video_name_from_file(f)
    if vname.startswith("webcam_"):
        live_files.append(f)
    else:
        recorded_files.append(f)

recorded_footages_uploaded = len({video_name_from_file(f) for f in recorded_files})


# ---------- Sidebar Control ----------
mode = "Recorded"  # Default
with st.sidebar:
    st.header("View")
    mode = st.radio("Mode", ["Recorded", "Live"], index=0)
    live_config_path = st.text_input("Live Config", "config/config_demo.yaml")
    camera_index = st.number_input("Camera Index", min_value=0, max_value=10, value=0, step=1)
    # Use external OpenCV preview window for live mode.
    show_live_preview = True

# ---------- Header + Image ----------
st.title("ThreatSense AI-DVR")
st.caption("Threat summary by mode")

if mode == "Live":
    st.info("Live camera opens in a separate window. Press 'q' in that window to stop preview.")


if "live_proc" not in st.session_state:
    st.session_state.live_proc = None
if "last_live_file" not in st.session_state:
    st.session_state.last_live_file = None
if "live_session_file" not in st.session_state:
    st.session_state.live_session_file = None
if "live_existing_files" not in st.session_state:
    st.session_state.live_existing_files = set()


def _live_running() -> bool:
    proc = st.session_state.live_proc
    return proc is not None and proc.poll() is None


def _start_live() -> None:
    if _live_running():
        return
    
    # Auto-delete old webcam logs and snapshots to keep only "present footage"
    Path("outputs/live_feed.jpg").unlink(missing_ok=True)
    for f in logs_dir.glob("alerts_webcam_*.csv"):
        f.unlink(missing_ok=True)
    for f in logs_dir.glob("alerts_webcam_*.jsonl"):
        f.unlink(missing_ok=True)
    
    snap_dir = Path("outputs/snapshots")
    if snap_dir.exists():
        import shutil
        for d in snap_dir.glob("webcam_*"):
            if d.is_dir():
                shutil.rmtree(d, ignore_errors=True)

    st.session_state.live_existing_files = set()
    st.session_state.live_session_file = None
    st.session_state.last_live_file = None
    cmd = [
        sys.executable,
        "src/main.py",
        "--config",
        live_config_path,
        "--webcam",
        "--camera-index",
        str(int(camera_index)),
    ]
    if show_live_preview:
        cmd.append("--show-live")
    st.session_state.live_proc = subprocess.Popen(cmd, cwd=str(project_root))


def _stop_live() -> None:
    proc = st.session_state.live_proc
    if proc is None:
        return
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    st.session_state.live_proc = None

if mode == "Recorded":
    selected_files = recorded_files
    mode_label = "Recorded Footage"
    live_session_name = ""
else:
    with st.sidebar:
        if _live_running():
            st.success("CCTV Monitoring Active")
        else:
            # Auto-start CCTV if not running
            _start_live()
            st.rerun()

    all_csv_files = sorted(logs_dir.glob("alerts*.csv"))
    live_files = [f for f in all_csv_files if video_name_from_file(f).startswith("webcam_")]

    selected_live_file: Path | None = None
    if live_files:
        selected_live_file = max(live_files, key=lambda p: p.stat().st_mtime)

    if selected_live_file is not None:
        selected_files = [selected_live_file]
        live_session_name = video_name_from_file(selected_live_file)
    else:
        selected_files = []
        live_session_name = ""
    mode_label = "Live Session"

if not selected_files:
    if mode == "Recorded":
        st.warning("No recorded-footage logs found yet.")
        st.stop()
    else:
        # In Live mode, we continue to show the dashboard metrics (all 0) even if no session file exists yet.
        pass

alerts, file_status = load_alert_frames(selected_files)

if alerts.empty:
    st.info(f"{mode_label}: Active monitoring... No threats detected in the current session.")
else:
    st.success("Monitoring session active.")


# ---------- Prepare alert dataframe ----------
alerts = alerts.copy()
alerts["event_type"] = alerts["event_type"].apply(normalize_event)
alerts["risk_score"] = pd.to_numeric(alerts["risk_score"], errors="coerce").fillna(0.0)
alerts["timestamp_s"] = pd.to_numeric(alerts.get("timestamp_s", 0), errors="coerce").fillna(0.0)
alerts["snapshot_file"] = alerts["snapshot_path"].astype(str).apply(lambda x: Path(x).name)
alerts["event_badge"] = alerts["event_type"].map(EVENT_BADGE).fillna("🟢 Normal")
alerts = alerts.reset_index(drop=True)

# Automatic sustained-risk banner for CCTV-style continuous monitoring.
is_sustained, sustained_seconds = detect_sustained_high_risk(
    alerts,
    threshold=0.7,
    min_duration_s=60.0,
    max_gap_s=8.0,
)
if is_sustained:
    st.error(
        f"ALERT: Sustained high risk detected for {sustained_seconds}s "
        "(risk_score >= 0.70). Immediate security check recommended."
    )
else:
    st.success("No sustained high-risk pattern detected in the current view.")


# ---------- Threat summary ----------
if not alerts.empty:
    mean_risk = float(alerts["risk_score"].mean())
    max_risk = float(alerts["risk_score"].max())
    threat_score = round((0.4 * mean_risk + 0.6 * max_risk) * 100.0, 1)
else:
    threat_score = 0.0

overall_level = risk_level_from_score(threat_score / 100.0)
color = risk_color(overall_level)

subtitle = mode_label
if live_session_name:
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

if mode == "Recorded":
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Alerts", int(len(alerts)))
    c2.metric("High Risk Alerts", int((alerts["risk_score"] > 0.7).sum()))
    c3.metric("Running", int((alerts["event_type"] == "running").sum()))
    c4.metric("Loitering", int((alerts["event_type"] == "loitering").sum()))
    c5.metric("Footages Uploaded", int(recorded_footages_uploaded))
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Alerts", int(len(alerts)))
    c2.metric("High Risk Alerts", int((alerts["risk_score"] > 0.7).sum()))
    c3.metric("Running", int((alerts["event_type"] == "running").sum()))
    c4.metric("Loitering", int((alerts["event_type"] == "loitering").sum()))


# ---------- Trend ----------
st.subheader("Risk Trend")
if not alerts.empty:
    trend = alerts.sort_values("timestamp_s").copy()
    trend = trend[["timestamp_s", "risk_score"]].rename(columns={"timestamp_s": "time_s"})
    st.line_chart(trend.set_index("time_s"))
else:
    st.info("No risk data to plot yet.")


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
if not alerts.empty:
    idx = st.number_input("Select alert row", min_value=0, max_value=max(len(alerts) - 1, 0), value=0, step=1)
    row = alerts.iloc[int(idx)]
    snap = Path(str(row["snapshot_path"]))
    st.write(f"Event: {row['event_badge']} | Risk: {row['risk_score']:.2f} | Video: {row['video_name']}")
    st.write(f"Explanation: {row['explanation']}")
    if snap.exists():
        st.image(str(snap), caption=row["snapshot_file"], use_column_width=True)
    else:
        st.info("Snapshot not found for this alert.")
else:
    st.info("No snapshots available (no alerts detected).")

# ---------- Auto-Refresh ----------
import time
if mode == "Live":
    time.sleep(2)
    st.rerun()

