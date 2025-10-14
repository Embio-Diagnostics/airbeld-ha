"""Constants for the Airbeld integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)

DOMAIN = "airbeld"

# Default configuration
DEFAULT_SCAN_INTERVAL = 180  # seconds (3 minutes)

# OAuth2 Configuration (embedded credentials for simplified user experience)
# Client ID is public and safe to include in code
OAUTH2_CLIENT_ID = "ZWPpC5dpPHKrunK2yy2KVl2tKiAhwk7n"
OAUTH2_AUTHORIZE = "https://auth.embiodiagnostics.eu/authorize"
OAUTH2_TOKEN = "https://auth.embiodiagnostics.eu/oauth/token"

# API Configuration
DEFAULT_API_BASE = "https://api.airbeld.com"

# Device class mapping for Home Assistant integration
# Maps sensor names from SDK to Home Assistant device classes
SENSOR_DEVICE_CLASSES = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "humidity": SensorDeviceClass.HUMIDITY,
    "pm1": SensorDeviceClass.PM1,
    "pm2p5": SensorDeviceClass.PM25,
    "pm4": SensorDeviceClass.PM10,  # No PM4 class in HA, use PM10
    "pm10": SensorDeviceClass.PM10,
    "co2": SensorDeviceClass.CO2,
    "voc": SensorDeviceClass.AQI,  # VOC Index as air quality index
    "nox": SensorDeviceClass.AQI,  # NOx Index as air quality index
}
