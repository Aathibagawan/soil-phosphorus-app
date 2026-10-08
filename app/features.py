"""Single source of truth for the model's input features.

Order matters: it must match the column order used at training time.
Ranges are *physical plausibility* limits used for request validation (reject
obviously wrong sensor values). They are deliberately wider than the training
range; the service separately warns when a value is outside what the model saw
during training.

Units for electrical conductivity / light are the sensor units of the training
data -- edit them here if your sensors report something different.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    key: str          # JSON / python name
    label: str        # human readable
    unit: str
    min: float        # hard validation limit
    max: float
    default: float    # sensible example value for the UI
    csv_aliases: tuple = ()


FEATURES: tuple[Feature, ...] = (
    Feature("soil_temperature", "Soil temperature", "°C", -10, 60, 17.5,
            ("soil_temperature", "soil_temp")),
    Feature("soil_humidity", "Soil humidity", "%", 0, 100, 31.0,
            ("soil_humidity", "soil_moisture", "soil_hum")),
    Feature("electrical_conductivity", "Electrical conductivity", "sensor units", 0, 2000, 54.0,
            ("electrical_conductivity", "ec")),
    Feature("ph", "Soil pH", "pH", 3, 10, 7.1, ("ph",)),
    Feature("air_temperature", "Air temperature", "°C", -30, 60, 20.0,
            ("air_temperature", "air_temp")),
    Feature("air_humidity", "Air humidity", "%", 0, 100, 75.0,
            ("air_humidity", "air_hum")),
    Feature("light_intensity", "Light intensity", "lux", 0, 200_000, 70_000.0,
            ("light_intensity", "light")),
)

FEATURE_KEYS: tuple[str, ...] = tuple(f.key for f in FEATURES)
N_FEATURES = len(FEATURES)
