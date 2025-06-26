# app.py  –  Minimal dark-theme multi-trace dashboard (no annotations)

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io

st.set_page_config(
    page_title="Sensor Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📈 Sensor Time-Series Dashboard")

# --------------------------------------------------
# 1. Upload CSV (comma-separated)
# --------------------------------------------------
uploaded = st.file_uploader("Upload CSV file", type=["csv"])
if not uploaded:
    st.info("⬆️  Upload a CSV to get started.")
    st.stop()

# Read the bytes, decode to string, wrap in StringIO
csv_text = uploaded.getvalue().decode("utf-8", errors="ignore")
df_raw = pd.read_csv(io.StringIO(csv_text), sep=",")
st.dataframe(df_raw.head(5))  # display table
# --------------------------------------------------
# 2. Clean column names, validate timestamp
# --------------------------------------------------
df_raw.columns = df_raw.columns.str.strip()
if "timestamp" not in df_raw.columns:
    st.error("The CSV must have a first column named **timestamp**.")
    st.stop()

# --------------------------------------------------
# 3. DataFrame to plot (no grouping for now)
# --------------------------------------------------
df_grp = df_raw.copy()

# --------------------------------------------------
# 4. Sidebar controls
# --------------------------------------------------
st.sidebar.header("⚙️ Plot Settings")

# Only keep numeric columns for y-axis
numeric_cols = [
    c for c in df_grp.columns
    if pd.api.types.is_numeric_dtype(df_grp[c])
]

default_signals = [c for c in numeric_cols if "Power" in c] or numeric_cols[:2]

y_signals = st.sidebar.multiselect(
    "Y-axis signals (multi-select)",
    options=numeric_cols,
    default=default_signals
)

if not y_signals:
    st.warning("Select at least one signal.")
    st.stop()

# --------------------------------------------------
# 5. Build dark-theme Plotly figure
# --------------------------------------------------
fig = go.Figure(
    layout=go.Layout(
        template="plotly_dark",
        title="Sensor Signals",
        xaxis_title="Timestamp",
        yaxis_title="Value",
        height=550,
        dragmode="zoom",
        margin=dict(l=10, r=20, t=40, b=10),
    )
)
for sig in y_signals:
    fig.add_trace(
        go.Scatter(
            x=df_grp[x_axis],
            y=df_grp[sig],
            mode="lines",
            name=sig,
        )
    )



st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# 6. Optional preview table (toggle)
# --------------------------------------------------
with st.expander("Preview data (first 5 rows)"):
    st.dataframe(df_grp.head(), use_container_width=True)

# --------------------------------------------------
# 3. Create timestamp_s (seconds as float)
# --------------------------------------------------
# def parse_timestamp(ts_str: str | float) -> float | None:
#     """Convert m:ss.s or h:mm:ss.s to seconds (float)."""
#     try:
#         parts = str(ts_str).split(":")
#         parts = [float(p) for p in parts]
#         if len(parts) == 2:          # mm:ss
#             return parts[0] * 60 + parts[1]
#         if len(parts) == 3:          # hh:mm:ss
#             return parts[0] * 3600 + parts[1] * 60 + parts[2]
#     except Exception:
#         pass
#     return None
#st.dataframe(df_raw.head(5)) 
#df_raw["timestamp_s"] = df_raw["timestamp"].apply(parse_timestamp)
#df_raw["timestamp_s"] = df_raw["timestamp"].astype(str).apply(parse_timestamp)
#df_raw = df_raw.sort_values("timestamp_s").reset_index(drop=True)





