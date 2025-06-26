# app.py  —  Sensor dashboard with briquette grouping & annotations
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events
from sqlalchemy import create_engine
import io, time

# ─────────────── CONFIG ───────────────
ID_PREFIX, ID_PAD = "DWC", 3          # e.g. DWC20250701001
MYSQL_TABLE       = "briquette_annotations"

# ────────────── STREAMLIT SETUP ──────────────
st.set_page_config(page_title="Briquette Dashboard", layout="wide")
st.title("📈 Sensor Time-Series Dashboard")

# ─────────── 1. CSV UPLOAD ───────────
up_file = st.file_uploader("Upload CSV", type=["csv"])
if not up_file:
    st.info("⬆️  Drop a sensor CSV to start.")
    st.stop()

df_raw = pd.read_csv(io.StringIO(up_file.getvalue().decode("utf-8")))
df_raw.columns = df_raw.columns.str.strip()

if "timestamp" not in df_raw.columns:
    st.error("CSV must contain a column named **timestamp**.")
    st.stop()

# ─────────── 2. TIMESTAMP → SECONDS ───────────
def to_sec(ts):
    try:
        parts = [float(p) for p in str(ts).split(":")]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]             # mm:ss
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]  # hh:mm:ss
    except Exception:
        return None
df_raw["t_sec"] = df_raw["timestamp"].apply(to_sec)
df_raw = df_raw.sort_values("t_sec").reset_index(drop=True)

# ─────────── 3. SIDEBAR CONTROLS ───────────
st.sidebar.header("⚙️ Controls")

# 3a. Grouping toggle
group_on = st.sidebar.checkbox("Group briquettes by fixed rows", value=True)
rows_per_briq = st.sidebar.number_input("Rows per briquette", 1, len(df_raw), 20)

if group_on:
    df_raw["briq_idx"] = (df_raw.index // rows_per_briq)
else:
    df_raw["briq_idx"] = 0  # single group

# 3b. Elapsed-time slider
t_min, t_max = float(df_raw["t_sec"].min()), float(df_raw["t_sec"].max())
t_rng = st.sidebar.slider("Elapsed time (s)", t_min, t_max, (t_min, t_max), step=1.0)

# Filter view
view = df_raw[(df_raw["t_sec"] >= t_rng[0]) & (df_raw["t_sec"] <= t_rng[1])]

# 3c. Y-axis multiselect
num_cols = [c for c in view.columns if pd.api.types.is_numeric_dtype(view[c])
            and c not in ["t_sec", "briq_idx"]]
default_cols = [c for c in num_cols if "Power" in c] or num_cols[:3]
y_cols = st.sidebar.multiselect("Signals to plot", num_cols, default_cols)

if not y_cols:
    st.warning("Select at least one signal.")
    st.stop()

# ─────────── 4. SESSION STATE for IDs & ANNOTS ───────────
if "id_map" not in st.session_state:
    st.session_state.id_map = {}              # briq_idx → BriquetteID
if "annots" not in st.session_state:
    st.session_state.annots = pd.DataFrame(columns=[
        "BriquetteID", "briq_idx", "Signal", "t_sec", "Value", "Note"
    ])
if "id_seq" not in st.session_state:
    st.session_state.id_seq = 0

def next_briq_id():
    st.session_state.id_seq += 1
    return f"{ID_PREFIX}{time.strftime('%Y%m%d')}{st.session_state.id_seq:0{ID_PAD}}"

# ─────────── 5. PLOTLY CHART ───────────
fig = go.Figure(layout=go.Layout(
    template="plotly_dark",
    title="Sensor Signals",
    xaxis_title="Elapsed time (s)",
    yaxis_title="Value",
    height=550, dragmode="zoom",
    margin=dict(l=10, r=10, t=40, b=10),
))
for col in y_cols:
    fig.add_trace(go.Scatter(x=view["t_sec"], y=view[col], name=col, mode="lines"))

clicks = plotly_events(fig, click_event=True)
st.plotly_chart(fig, use_container_width=True)

# ─────────── 6. HANDLE CLICK & ANNOTATION ───────────
def mysql_engine():
    if "mysql" not in st.secrets:
        return None
    c = st.secrets["mysql"]
    uri = f"mysql+pymysql://{c.user}:{c.password}@{c.host}:{c.port}/{c.database}"
    return create_engine(uri, pool_recycle=3600)

ENG = mysql_engine()

if clicks:
    pt = clicks[0]
    sig   = y_cols[pt["curveNumber"]]
    x_val = pt["x"]; y_val = pt["y"]

    # Find briq_idx of the clicked point
    idx = view.iloc[(view["t_sec"] - x_val).abs().idxmin()]["briq_idx"]

    # Get or create BriquetteID for that group
    if idx not in st.session_state.id_map:
        st.session_state.id_map[idx] = next_briq_id()
    briq_id = st.session_state.id_map[idx]

    # Pop form
    with st.form(f"annot_{time.time()}", clear_on_submit=True):
        st.markdown(f"**{sig} @ {x_val:.1f}s** — Briquette ID `{briq_id}`")
        note_text = st.text_input("Add note")
        save = st.form_submit_button("Save")
        if save:
            new = {"BriquetteID": briq_id, "briq_idx": idx,
                   "Signal": sig, "t_sec": x_val, "Value": y_val, "Note": note_text}
            st.session_state.annots = pd.concat(
                [st.session_state.annots, pd.DataFrame([new])],
                ignore_index=True)

            # Add BriquetteID & Note to ALL rows in that segment
            mask = (df_raw["briq_idx"] == idx)
            df_raw.loc[mask, "BriquetteID"] = briq_id
            if note_text:
                df_raw.loc[mask, "Note"] = note_text

            # Upload single annotation row to MySQL
            if ENG is not None:
                try:
                    pd.DataFrame([new]).to_sql(MYSQL_TABLE, ENG, if_exists="append", index=False)
                    st.toast("Uploaded to MySQL", icon="✅")
                except Exception as e:
                    st.error(f"MySQL error: {e}")

            st.success("Annotation saved.")

# ─────────── 7. OUTPUT TABLES & DOWNLOADS ───────────
st.subheader("📝 Annotations so far")
st.dataframe(st.session_state.annots, use_container_width=True)

st.download_button(
    "Download annotations CSV",
    st.session_state.annots.to_csv(index=False).encode(),
    "annotations.csv", "text/csv"
)

st.download_button(
    "Download full data CSV",
    df_raw.to_csv(index=False).encode(),
    "data_with_briq_ids.csv", "text/csv"
)
