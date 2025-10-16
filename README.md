<div align="center">
  <img src="images/airbeld.png" alt="Airbeld" width="200"/>

  # Airbeld Integration for Home Assistant

  **Official Home Assistant integration for Airbeld air quality monitoring devices**

  [![hacs_badge](https://img.shields.io/badge/HACS-Default-blue.svg)](https://github.com/hacs/integration)
  [![GitHub Release](https://img.shields.io/github/release/Embio-Diagnostics/airbeld-ha.svg)](https://github.com/Embio-Diagnostics/airbeld-ha/releases)
  [![License](https://img.shields.io/github/license/Embio-Diagnostics/airbeld-ha.svg)](LICENSE)

  Monitor your indoor air quality in real-time with temperature, humidity, PM2.5, CO2 sensors and more.

</div>

---

## Features

- **Real-time monitoring** of air quality metrics
- **OAuth2 authentication** via Auth0 - secure and easy setup
- **Automatic device discovery** - all your Airbeld devices appear automatically
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
4. Search for **"Airbeld"**
5. Click **"Download"**
6. Restart Home Assistant

### Manual Installation

1. Download the [latest release](https://github.com/Embio-Diagnostics/airbeld-ha/releases)
2. Extract the `airbeld` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"Airbeld"**
4. Click on **Airbeld** and follow the OAuth2 authentication flow
5. Log in with your Airbeld account
6. Your devices will appear automatically!

## Supported Devices

- All Airbeld air quality monitor models

## Requirements

- Home Assistant 2024.1.0 or newer
- Airbeld account with registered devices
- Internet connection (cloud-based integration)

## Troubleshooting

### Integration not found after installation
- Restart Home Assistant completely (not just reload integrations)
- Check that files are in `config/custom_components/airbeld/`
- Check Home Assistant logs for errors

### Authentication fails
- Verify your Airbeld account credentials
- Check that your devices are registered in the Airbeld app
- Ensure Home Assistant can reach the internet

### No devices appear
- Verify devices are online in the Airbeld mobile app
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

**Airbeld** is developed by [**Embio Diagnostics**](https://embiodiagnostics.eu), providing professional-grade air quality monitoring solutions for homes and businesses.

Learn more at [airbeld.com](https://airbeld.com)

</div>
