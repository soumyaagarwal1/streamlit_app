# app.py — single interactive chart with annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events
import io, time

ID_PREFIX, ID_PAD = "DWC", 3        # Briquette ID format DWCYYYYMMDD001 …

st.set_page_config(page_title="Sensor Dashboard", layout="wide")
st.title("📈 Sensor Time-Series Dashboard")

# ────────────────── 1. Upload CSV ──────────────────
up = st.file_uploader("Upload CSV", type=["csv"])
if not up:
    st.info("⬆️  Upload a CSV to start.")
    st.stop()

df = pd.read_csv(io.StringIO(up.getvalue().decode("utf-8")))
df.columns = df.columns.str.strip()
if "timestamp" not in df.columns:
    st.error("CSV must have a column named **timestamp**.")
    st.stop()

# ─────────── 2. Parse timestamp → seconds ───────────
def to_sec(ts):
    try:
        p = [float(x) for x in str(ts).split(":")]
        return p[0]*60 + p[1] if len(p)==2 else p[0]*3600 + p[1]*60 + p[2]
    except Exception:
        return None
df["t_sec"] = df["timestamp"].apply(to_sec)
df = df.sort_values("t_sec").reset_index(drop=True)

# ─────────── 3. Sidebar controls ───────────
st.sidebar.header("⚙️ Display")
t_min, t_max = float(df["t_sec"].min()), float(df["t_sec"].max())
t_rng = st.sidebar.slider("Elapsed time (s)", t_min, t_max, (t_min, t_max), step=1.0)
view = df[(df["t_sec"] >= t_rng[0]) & (df["t_sec"] <= t_rng[1])]

num_cols = [c for c in view.columns if pd.api.types.is_numeric_dtype(view[c]) and c!="t_sec"]
default = [c for c in num_cols if "Power" in c] or num_cols[:3]
signals = st.sidebar.multiselect("Signals (multi-select)", num_cols, default)

if not signals:
    st.warning("Pick at least one signal.")
    st.stop()

# ─────────── 4. Session-state for annotations ───────────
if "annots" not in st.session_state:
    st.session_state.annots = pd.DataFrame(
        columns=["BriquetteID", "Signal", "t_sec", "Value", "Note"])
if "seq" not in st.session_state:
    st.session_state.seq = 0

def next_id():
    st.session_state.seq += 1
    return f"{ID_PREFIX}{time.strftime('%Y%m%d')}{st.session_state.seq:0{ID_PAD}}"

# ─────────── 5. Plot + click capture ───────────
fig = go.Figure(layout=go.Layout(
    template="plotly_dark",
    title="Sensor Signals",
    xaxis_title="Elapsed time (s)",
    yaxis_title="Value",
    height=500, margin=dict(l=10, r=10, t=40, b=40), dragmode="zoom")
)
for s in signals:
    fig.add_trace(go.Scatter(x=view["t_sec"], y=view[s], mode="lines", name=s))

clicks = plotly_events(fig, click_event=True)
st.plotly_chart(fig, use_container_width=True)

# ─────────── 6. Handle annotation ───────────
if clicks:
    pt = clicks[0]
    sig  = signals[pt["curveNumber"]]
    xval, yval = pt["x"], pt["y"]
    briq = next_id() if st.session_state.annots.empty else st.session_state.annots.iloc[-1]["BriquetteID"]
    with st.form("annot", clear_on_submit=True):
        st.markdown(f"**{sig} @ {xval:.1f}s**  Briquette ID: `{briq}`")
        note = st.text_input("Add note")
        if st.form_submit_button("Save"):
            st.session_state.annots = pd.concat(
                [st.session_state.annots,
                 pd.DataFrame([{"BriquetteID": briq, "Signal": sig,
                                "t_sec": xval, "Value": yval, "Note": note}])]
            ).reset_index(drop=True)
            st.success("✅ Saved!")

# ─────────── 7. Show / download annotations ───────────
st.subheader("📝 Annotations")
st.dataframe(st.session_state.annots, use_container_width=True)
st.download_button("Download annotations CSV",
                   st.session_state.annots.to_csv(index=False).encode(),
                   "annotations.csv", "text/csv")

# ─────────── 8. Download filtered data ───────────
st.download_button("Download filtered data CSV",
                   view.to_csv(index=False).encode(),
                   "filtered_data.csv", "text/csv")
