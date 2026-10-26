
import json
import time
import threading
from datetime import datetime

import pandas as pd
import streamlit as st
import paho.mqtt.client as mqtt
from streamlit_autorefresh import st_autorefresh


# ---------------- CONFIGURATION ----------------

BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "smartenergy/Gdev2509/telemetry"


# ---------------- MQTT CONNECTION ----------------

@st.cache_resource
def start_mqtt():
    store = {
        "latest": None,
        "history": [],
        "connected": False,
        "error": None,
        "lock": threading.Lock(),
    }

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            with store["lock"]:
                store["connected"] = True
                store["error"] = None
            client.subscribe(TOPIC)
        else:
            with store["lock"]:
                store["connected"] = False
                store["error"] = f"Connection refused: {reason_code}"

    def on_disconnect(
        client, userdata, disconnect_flags, reason_code, properties
    ):
        with store["lock"]:
            store["connected"] = False
            if reason_code != 0:
                store["error"] = f"MQTT disconnected: {reason_code}"

    def on_message(client, userdata, message):
        try:
            reading = json.loads(message.payload.decode("utf-8"))

            for key in ("voltage", "current", "power", "energy"):
                if key not in reading:
                    raise ValueError(f"Missing field: {key}")

                reading[key] = float(reading[key])

            reading["received_at"] = datetime.now().strftime("%H:%M:%S")

            with store["lock"]:
                store["latest"] = reading
                store["history"].append(reading)
                store["history"] = store["history"][-150:]
                store["error"] = None

        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            with store["lock"]:
                store["error"] = f"Invalid MQTT message: {exc}"

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"streamlit-energy-{int(time.time())}",
        protocol=mqtt.MQTTv311,
    )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()
    except Exception as exc:
        store["error"] = f"Broker connection error: {exc}"

    return client, store


# ---------------- PAGE SETTINGS ----------------

st.set_page_config(
    page_title="Smart Energy Monitoring",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Smart Energy Monitoring System")
st.caption(
    "Virtual ESP32 • MQTT • Manual Testing • Energy Analysis"
)


# ---------------- MODE SELECTION ----------------

mode = st.sidebar.radio(
    "Select Operating Mode",
    [
        "Live MQTT",
        "Manual Test",
    ],
)

tariff = st.sidebar.number_input(
    "Electricity tariff (₹/kWh)",
    min_value=0.0,
    max_value=1000.0,
    value=8.0,
    step=0.5,
)

alert_limit = st.sidebar.number_input(
    "High-power alert threshold (W)",
    min_value=1.0,
    max_value=100000.0,
    value=500.0,
    step=50.0,
)


# ---------------- LIVE MQTT MODE ----------------

if mode == "Live MQTT":

    st.info(
        "LIVE MODE: Values come from MQTT messages published by Wokwi. "
        "Manual test inputs are not used."
    )

    st_autorefresh(interval=2000, key="live_refresh")

    client, store = start_mqtt()

    with store["lock"]:
        connected = store["connected"]
        latest = dict(store["latest"]) if store["latest"] else None
        history = [dict(row) for row in store["history"]]
        error = store["error"]

    if connected:
        st.success(f"MQTT connected | Topic: {TOPIC}")
    else:
        st.warning("Waiting for the MQTT broker connection.")
        if error:
            st.error(error)

    if latest is None:
        st.warning(
            "No readings received yet. Start Wokwi and check its Serial Monitor "
            "for 'MQTT sent:'."
        )
        st.stop()

    voltage = latest["voltage"]
    current = latest["current"]
    power = latest["power"]
    energy = latest["energy"]

    st.caption(f"Last received message: {latest['received_at']}")

    # Validate displayed data against the simplified model.
    st.caption(
        "Voltage and current are simulated. Power and energy are supplied "
        "by the ESP32 calculation."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Voltage", f"{voltage:.1f} V")
    c2.metric("Current", f"{current:.3f} A")
    c3.metric("Power", f"{power:.2f} W")
    c4.metric("Energy", f"{energy:.6f} kWh")

    cost = energy * tariff
    st.metric("Estimated Energy Cost", f"₹{cost:.4f}")

    if power >= alert_limit:
        st.error(f"High-power alert: {power:.2f} W")
    else:
        st.success("Power is below the configured threshold.")

    if history:
        df = pd.DataFrame(history)

        st.subheader("Live Power History")
        st.line_chart(df.set_index("received_at")[["power"]])

        st.subheader("Cumulative Energy History")
        st.line_chart(df.set_index("received_at")[["energy"]])

        st.subheader("Recent MQTT Readings")
        st.dataframe(df.tail(10), use_container_width=True)

        st.download_button(
            "Download Live Readings CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="live_energy_readings.csv",
            mime="text/csv",
        )


# ---------------- MANUAL TEST MODE ----------------

elif mode == "Manual Test":

    st.info(
        "MANUAL TEST MODE: These are values entered by you. "
        "They are not received from the ESP32 or MQTT."
    )

    st.subheader("Enter Your Test Values")

    col1, col2 = st.columns(2)

    with col1:
        voltage = st.number_input(
            "Voltage (V)",
            min_value=0.0,
            max_value=1000.0,
            value=230.0,
            step=1.0,
        )

        current = st.number_input(
            "Current (A)",
            min_value=0.0,
            max_value=1000.0,
            value=1.0,
            step=0.1,
        )

    with col2:
        energy = st.number_input(
            "Energy consumed (kWh)",
            min_value=0.0,
            max_value=1000000.0,
            value=2.5,
            step=0.1,
        )

        st.caption(
            "Energy is entered manually in this mode; it is not accumulated "
            "automatically."
        )

    # Simplified resistive-load calculation.
    power = voltage * current

    # Cost calculated from manually entered energy.
    cost = energy * tariff

    st.divider()
    st.subheader("Manual Test Results")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Test Voltage", f"{voltage:.1f} V")
    c2.metric("Test Current", f"{current:.2f} A")
    c3.metric("Calculated Power", f"{power:.2f} W")
    c4.metric("Entered Energy", f"{energy:.3f} kWh")

    st.metric("Estimated Energy Cost", f"₹{cost:.2f}")

    if power >= alert_limit:
        st.error(f"High-power alert: {power:.2f} W")
    else:
        st.success("Power is below the configured threshold.")

    st.caption(
        "Power = Voltage × Current, assuming a resistive load and power "
        "factor of 1. For AC loads with a different power factor, real power "
        "requires the power factor or an appropriate measurement."
    )

    manual_data = pd.DataFrame(
        [
            {
                "mode": "Manual Test",
                "voltage_V": voltage,
                "current_A": current,
                "power_W": power,
                "energy_kWh": energy,
                "tariff_Rs_per_kWh": tariff,
                "estimated_cost_Rs": cost,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        ]
    )

    st.subheader("Manual Test Record")
    st.dataframe(manual_data, use_container_width=True)

    st.download_button(
        "Download Manual Test CSV",
        data=manual_data.to_csv(index=False).encode("utf-8"),
        file_name="manual_energy_test.csv",
        mime="text/csv",
        )
                
