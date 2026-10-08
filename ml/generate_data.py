"""Synthetic dataset generator (ported from finished1.ipynb).

NOTE: this is *synthetic* data used to develop/demo the pipeline. Replace it with
real sensor + lab-measured phosphorus data for any real-world use:

    python -m ml.train --data path/to/your.csv

Required CSV columns: timestamp, Soil_Temperature, Soil_Humidity,
Electrical_Conductivity, pH, Air_Temperature, Air_Humidity, Light_Intensity,
Phosphorus
"""
import argparse
import numpy as np
import pandas as pd


def generate(hours: int = 2000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    time = pd.date_range("2024-01-01", periods=hours, freq="h")
    t = np.arange(hours)
    daily = np.sin(2 * np.pi * t / 24)
    monthly = np.sin(2 * np.pi * t / 720)

    soil_temp = 17.5 + 2.5 * daily + rng.normal(0, 0.3, hours)
    soil_hum = 31 + 3 * monthly + rng.normal(0, 0.4, hours)
    ec = 48 + 2 * soil_hum / 10 + rng.normal(0, 0.5, hours)
    ph = 7.1 + 0.15 * monthly + rng.normal(0, 0.03, hours)
    air_temp = 20 + 4 * daily + rng.normal(0, 0.3, hours)
    air_hum = 75 + 10 * monthly + rng.normal(0, 1.0, hours)
    light = 60000 + 30000 * np.maximum(daily, 0) + rng.normal(0, 3000, hours)

    p = np.zeros(hours)
    p[0] = 3.0
    for i in range(1, hours):
        p[i] = (0.94 * p[i - 1] + 0.06 * soil_hum[i] + 0.05 * ec[i]
                + 0.03 * air_temp[i] + 0.02 * light[i] / 10000
                + rng.normal(0, 0.08))

    return pd.DataFrame({
        "timestamp": time, "Soil_Temperature": soil_temp, "Soil_Humidity": soil_hum,
        "Electrical_Conductivity": ec, "pH": ph, "Air_Temperature": air_temp,
        "Air_Humidity": air_hum, "Light_Intensity": light, "Phosphorus": p,
    })


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/phosphorus_timeseries.csv")
    ap.add_argument("--hours", type=int, default=2000)
    a = ap.parse_args()
    generate(a.hours).to_csv(a.out, index=False)
    print("saved", a.out)
