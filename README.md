<div align="center">
  <img src="custom_components/airbeld/brand/logo.png" alt="airbeld™" width="200"/>

  # airbeld™ Integration for Home Assistant

  **Official Home Assistant integration for airbeld™ air quality monitoring devices**

  [![hacs_badge](https://img.shields.io/badge/HACS-Default-blue.svg)](https://github.com/hacs/integration)
  [![GitHub Release](https://img.shields.io/github/release/Embio-Diagnostics/airbeld-ha.svg)](https://github.com/Embio-Diagnostics/airbeld-ha/releases)
  [![License](https://img.shields.io/github/license/Embio-Diagnostics/airbeld-ha.svg)](LICENSE)

  Monitor your indoor air quality in real-time with temperature, humidity, PM2.5, CO2 sensors and more.

</div>

---

## Features

- **Real-time monitoring** of air quality metrics
- **OAuth2 authentication** via Auth0 - secure and easy setup
- **Automatic device discovery** - owned, shared and organization devices appear
  on the existing 180-second poll. Offline/stale devices show unavailable, and
  three complete inventory absences remove only this account's device and sensors.
- **Cloud-based updates** - no local network configuration needed
- **Rich sensor data**:
  - Temperature
  - Humidity
  - PM2.5 (particulate matter)
  - CO2 levels
  - VOC (Volatile Organic Compounds)
  - NOx (Nitrogen Oxides)

## Installation

### HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed
2. In Home Assistant, go to **HACS** → **Integrations**
3. Click the **"+"** button
4. Search for **"airbeld™"**
5. Click **"Download"**
6. Restart Home Assistant

### Manual Installation

1. Download the [latest release](https://github.com/Embio-Diagnostics/airbeld-ha/releases)
2. Extract the `airbeld` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"airbeld™"**
4. Click on **airbeld™** and follow the OAuth2 authentication flow
5. Log in with your airbeld™ account
6. Your devices will appear automatically!

## Supported Devices

- All airbeld™ air quality monitor models

## Requirements

- Home Assistant 2025.10.0 or newer (test endpoints: 2025.10.0 and 2026.10.1;
  see [compatibility record](docs/ha-compatibility.md))
- airbeld™ account with registered devices
- Internet connection (cloud-based integration)

## Troubleshooting

### Upgrading from v0.1.2
- Older Home Assistant installations must keep v0.1.2 (the v1 integration).
- The candidate uses API v2 and real PKCE sign-in. If asked to reauthenticate,
  use the original account; signing in as another account is refused.
- Ordinary sensors migrate in place: their entity IDs, custom names, areas,
  disabled state and history remain. Unresolved legacy devices are left untouched
  and unavailable; a repair offers explicit removal.
- Different accounts each get their own device rows and sensors, including shared
  devices. For duplicate entries of the same account/environment, only the oldest
  loads; later entries get a repair notice.
- The original VOC/NOx AQI sensors are disabled with history intact. New VOC/NOx
  index sensors have separate entity IDs and fresh statistics (the one exception
  to entity-ID preservation). PM4 retains its statistic with the correct PM4 class.

### Integration not found after installation
- Restart Home Assistant completely (not just reload integrations)
- Check that files are in `config/custom_components/airbeld/`
- Check Home Assistant logs for errors

### Authentication fails
- Verify your airbeld™ account credentials
- Check that your devices are registered in the airbeld™ app
- Ensure Home Assistant can reach the internet

### No devices appear
- Verify devices are online in the airbeld™ mobile app
- Try removing and re-adding the integration
- Check Home Assistant logs for API errors

For more issues, please [open an issue](https://github.com/Embio-Diagnostics/airbeld-ha/issues).

## Support

- **Issues**: [GitHub Issues](https://github.com/Embio-Diagnostics/airbeld-ha/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Embio-Diagnostics/airbeld-ha/discussions)
- **Documentation**: [DEVELOPMENT.md](DEVELOPMENT.md) (for developers)

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) and [DEVELOPMENT.md](DEVELOPMENT.md) before submitting pull requests.

## License

This integration is licensed under the [MIT License](LICENSE).

---

<div align="center">

## About

<img src="images/EmbioDiagnostics.png" alt="Embio Diagnostics" width="120"/>

**airbeld™** is developed by [**Embio Diagnostics**](https://embiodiagnostics.eu), providing professional-grade air quality monitoring solutions for homes and businesses.

Learn more at [airbeld.com](https://airbeld.com)

</div>
