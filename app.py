
import json
import time
import threading
from datetime import datetime

import pandas as pd
import streamlit as st
import paho.mqtt.client as mqtt
from streamlit_autorefresh import st_autorefresh

BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "smartenergy/Gdev2509/telemetry"


@st.cache_resource
def start_mqtt():
    # Shared data store updated by the MQTT callback thread.
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
                store["error"] = f"MQTT connection refused: {reason_code}"

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        with store["lock"]:
            store["connected"] = False
            if reason_code != 0:
                store["error"] = f"MQTT disconnected: {reason_code}"

    def on_message(client, userdata, message):
        try:
            reading = json.loads(message.payload.decode("utf-8"))

            required = ["voltage", "current", "power", "energy"]
            if not all(key in reading for key in required):
                raise ValueError("Missing required reading")

            reading["received_at"] = datetime.now().strftime("%H:%M:%S")

            with store["lock"]:
                store["latest"] = reading
                store["history"].append(reading)
                store["history"] = store["history"][-150:]
                store["error"] = None

        except (ValueError, UnicodeDecodeError, TypeError) as exc:
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
        store["error"] = f"Cannot connect to MQTT broker: {exc}"

    return client, store


st.set_page_config(
    page_title="Smart Energy Monitoring",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Smart Energy Monitoring System")
st.caption("Virtual ESP32 → MQTT → Streamlit | Simulated electrical readings")

tariff = st.sidebar.number_input(
    "Tariff (₹/kWh)", min_value=0.0, value=8.0, step=0.5
)

alert_limit = st.sidebar.slider(
    "High-power alert (W)",
    min_value=100,
    max_value=2000,
    value=500,
    step=50,
)

st_autorefresh(interval=2000, key="mqtt_refresh")

client, store = start_mqtt()

with store["lock"]:
    connected = store["connected"]
    latest = dict(store["latest"]) if store["latest"] else None
    history = list(store["history"])
    error = store["error"]

if connected:
    st.success(f"MQTT connected · Topic: {TOPIC}")
else:
    st.warning("Waiting for an MQTT connection and ESP32 readings.")
    if error:
        st.code(error)

if latest is None:
    st.info(
        "Start your Wokwi simulation and wait for the first MQTT message."
    )
    st.stop()

voltage = float(latest["voltage"])
current = float(latest["current"])
power = float(latest["power"])
energy = float(latest["energy"])
cost = energy * tariff

c1, c2, c3, c4 = st.columns(4)
c1.metric("Voltage", f"{voltage:.1f} V")
c2.metric("Current", f"{current:.2f} A")
c3.metric("Power", f"{power:.1f} W")
c4.metric("Energy", f"{energy:.6f} kWh")

st.metric("Estimated Energy Cost", f"₹{cost:.4f}")

if power >= alert_limit:
    st.error(f"High power alert: {power:.1f} W")
else:
    st.success("Power is below the configured alert threshold.")

df = pd.DataFrame(history)

if not df.empty:
    st.subheader("Live Power Consumption")
    st.line_chart(df.set_index("received_at")[["power"]])

    st.subheader("Cumulative Energy")
    st.line_chart(df.set_index("received_at")[["energy"]])

    st.subheader("Latest MQTT Readings")
    st.dataframe(df.tail(10), use_container_width=True)

    st.download_button(
        "Download MQTT readings (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="smart_energy_readings.csv",
        mime="text/csv",
    )

st.caption(
    "Values are simulated. The dashboard displays the latest MQTT messages "
    "received while its MQTT listener is running."
)
