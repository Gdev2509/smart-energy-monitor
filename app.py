
import random
from datetime import datetime

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ---------------- PAGE CONFIGURATION ----------------
st.set_page_config(
    page_title="Smart Energy Monitor",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Smart Energy Monitoring System")
st.caption("Virtual Idea Lab Project | Simulated data — no physical meter")

# ---------------- SETTINGS ----------------
tariff = st.sidebar.number_input(
    "Electricity tariff (₹/kWh)",
    min_value=0.0,
    max_value=100.0,
    value=8.0,
    step=0.5
)

alert_limit = st.sidebar.slider(
    "High power alert threshold (W)",
    min_value=100,
    max_value=2000,
    value=500,
    step=50
)

if "records" not in st.session_state:
    st.session_state.records = []
    st.session_state.energy_kwh = 0.0
    st.session_state.last_time = datetime.now()

# Refresh the dashboard every 2 seconds
st_autorefresh(interval=2000, key="energy_refresh")

# ---------------- SIMULATE ELECTRICAL LOAD ----------------
now = datetime.now()
elapsed_seconds = (
    now - st.session_state.last_time
).total_seconds()

# Prevent a long browser pause from creating a huge energy jump
elapsed_seconds = min(max(elapsed_seconds, 0), 10)

voltage = 230.0
current = random.uniform(0.30, 2.00)

# Approximation for a resistive load, power factor = 1
power = voltage * current

# Energy in kWh = power in W x time in hours / 1000
st.session_state.energy_kwh += (
    power * elapsed_seconds / 3600000
)

st.session_state.last_time = now

energy = st.session_state.energy_kwh
cost = energy * tariff

st.session_state.records.append({
    "Time": now,
    "Voltage (V)": voltage,
    "Current (A)": round(current, 2),
    "Power (W)": round(power, 1),
    "Energy (kWh)": round(energy, 6),
    "Cost (₹)": round(cost, 4)
})

# Keep recent readings for charts
st.session_state.records = st.session_state.records[-150:]
df = pd.DataFrame(st.session_state.records)

# ---------------- LIVE METRICS ----------------
m1, m2, m3, m4 = st.columns(4)

m1.metric("Voltage", f"{voltage:.1f} V")
m2.metric("Current", f"{current:.2f} A")
m3.metric("Power", f"{power:.1f} W")
m4.metric("Energy", f"{energy:.6f} kWh")

st.metric("Estimated Energy Cost", f"₹{cost:.4f}")

# ---------------- ALERT ----------------
if power >= alert_limit:
    st.error(
        f"High power alert: {power:.1f} W "
        f"is above your {alert_limit} W threshold."
    )
else:
    st.success("Power is within the configured threshold.")

# ---------------- CHARTS ----------------
st.subheader("Live Power Consumption")
st.line_chart(
    df.set_index("Time")[["Power (W)"]]
)

st.subheader("Energy Consumption")
st.line_chart(
    df.set_index("Time")[["Energy (kWh)"]]
)

st.subheader("Recent Readings")
st.dataframe(df.tail(10), use_container_width=True)

# ---------------- DOWNLOAD ----------------
csv_data = df.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download Readings as CSV",
    data=csv_data,
    file_name="energy_readings.csv",
    mime="text/csv"
)

if st.button("Reset Energy Counter"):
    st.session_state.energy_kwh = 0.0
    st.session_state.records = []
    st.session_state.last_time = datetime.now()
    st.rerun()
