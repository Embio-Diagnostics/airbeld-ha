# airbeld™ Integration

Monitor your indoor air quality with airbeld™ devices directly in Home Assistant.

## Features

- **Temperature** - Real-time temperature monitoring
- **Humidity** - Track humidity levels
- **PM2.5** - Particulate matter measurement
- **CO2** - Carbon dioxide levels
- **More sensors** - Additional air quality metrics

## Quick Setup

1. Add the integration in Settings → Devices & Services
2. Authenticate with your airbeld™ account (OAuth2)
3. Your devices will appear automatically

## Requirements

- airbeld™ account with registered devices
- Home Assistant 2025.10.0+ (see `docs/ha-compatibility.md` for exact test versions)
- Internet connection

Secure authentication via Auth0 OAuth2.

The v2 candidate upgrades ordinary sensors in place and uses PKCE sign-in.
Older HA installations keep v0.1.2 (v1). Each account has its own device and sensor
copies. Original VOC/NOx AQI rows are disabled with history intact; new index
entities start separate statistics. PM4 retains its entity and statistic.
New devices appear on the existing 180-second poll. Offline/stale devices show
unavailable; three complete inventory absences remove only this account's rows.
