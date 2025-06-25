# -----------------------------------------------------------
# app.py  •  Upload → group/aggregate → click-annotate → export
# -----------------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from io import StringIO
from streamlit_plotly_events import plotly_events   # pip install streamlit-plotly-events

st.set_page_config(page_title="Sensor Annotator", layout="wide")
st.title("📈 Click-Annotate Sensor Dashboard")

# ---------- 1. Upload ----------
uploaded = st.file_uploader(
    "Upload your sensor file (CSV or TSV – first col must be 'timestamp')",
    type=["csv", "tsv", "txt"]
)
delimiter = st.sidebar.radio("Delimiter", {",": "Comma (,)", "\t": "Tab (\\t)", "auto": "Auto/Whitespace"}, index=1)

#up = st.file_uploader("Upload CSV", type=["csv"])

if uploaded:
    df_raw = pd.read_csv(uploaded, sep=",")         # ✅ enforce comma-split
    df_raw.columns = df_raw.columns.str.strip()  # ✅ clean col names
    st.write("Detected columns:", df_raw.columns.tolist())
    st.write(df_raw.head(1))                  # optional preview


if not uploaded:
    st.info("👈 Upload a file to get started")
    st.stop()

# ---------- 2. Read ----------
if delimiter == ",":
    df_raw = pd.read_csv(uploaded)
elif delimiter == "\t":
    df_raw = pd.read_csv(uploaded, sep=",")
else:
    df_raw = pd.read_csv(uploaded, sep=r"\s+", engine="python")  # whitespace / auto

# ---------- 3. Basic cleaning ----------
df = df_raw.copy()
st.write("Detected columns:", df_raw.columns.tolist())

if "timestamp" not in df.columns:
    st.error("First column must be named **timestamp**.")
    st.stop()

# Convert a m:ss.s style timestamp → seconds (float) so we can plot on numeric axis if desired
def to_seconds(ts):
    try:
        m, s = ts.split(":")
        return float(m) * 60 + float(s)
    except Exception:
        return np.nan

if "timestamp_s" not in df.columns:
    df["timestamp_s"] = df["timestamp"].astype(str).apply(to_seconds)

# ---------- 4. Grouping / aggregation ----------
st.sidebar.header("🗂 Segmentation")
group_size = st.sidebar.number_input("Rows per segment", min_value=1, max_value=len(df), value=1)
agg_func = st.sidebar.selectbox(
    "Aggregate function",
    ("none", "mean", "median", "max", "min", "std"),
    index=0
)

if agg_func != "none" or group_size > 1:
    grouped = df.groupby(np.arange(len(df)) // group_size)
    df_plot = getattr(grouped, agg_func if agg_func != "none" else "first")()
else:
    df_plot = df

# ---------- 5. Choose axes ----------
st.sidebar.header("📊 Plot controls")
x_axis = st.sidebar.selectbox("X-axis", ["timestamp", "timestamp_s"] + df_plot.columns.tolist(), index=0)
y_axis = st.sidebar.selectbox("Y-axis", df_plot.columns[1:], index=1)

# ---------- 6. Plot ----------
fig = px.line(df_plot, x=x_axis, y=y_axis, markers=True, title=f"{y_axis} vs {x_axis}")
fig.update_layout(margin=dict(l=20, r=20, t=40, b=20), dragmode="zoom")
clicked = plotly_events(fig, click_event=True, hover_event=False, select_event=False)
st.plotly_chart(fig, use_container_width=True)

# ---------- 7. Annotation store ----------
if "annotations" not in st.session_state:
    st.session_state.annotations = pd.DataFrame(columns=[x_axis, y_axis, "note"])

# ---------- 8. Capture click & note ----------
if clicked:
    pt = clicked[0]
    x_val, y_val = pt["x"], pt["y"]
    with st.form("add_note_form", clear_on_submit=True):
        st.markdown(f"**Add note for {x_axis} = `{x_val}` | {y_axis} = `{y_val}`**")
        note_text = st.text_input("Note")
        if st.form_submit_button("Save"):
            st.session_state.annotations.loc[len(st.session_state.annotations)] = [x_val, y_val, note_text]
            st.success("Annotation saved!")

# ---------- 9. Show & download annotations ----------
st.subheader("📝 Annotations")
st.dataframe(st.session_state.annotations, use_container_width=True)
csv = st.session_state.annotations.to_csv(index=False).encode()
st.download_button("Download CSV", csv, "annotations.csv", "text/csv")
