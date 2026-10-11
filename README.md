# neoom BEAAM (local) for Home Assistant

Custom integration for the **neoom BEAAM** energy manager. It talks **only to the
local BEAAM API** (`http://<beaam-ip>/api/v1/...`), never to the neoom cloud.

## Features

- **Auto-discovery of everything on the BEAAM**: the site configuration is read at
  startup and every data point of every connected device (inverter, PV, battery,
  meter, charging point, heat pump, …) becomes an entity.
- **Devices**: one *BEAAM* device (energy flow: production, consumption, grid,
  storage, self-sufficiency, lifetime energy totals). Each connected device is
  its own HA device, linked to the BEAAM.
- **Energy dashboard ready**: `Wh` counters are `total_increasing` energy sensors
  shown in kWh.
- **Control**:
  - controllable numeric data points (`controllable: true`, e.g. battery
    `TARGET_POWER`, wallbox `MAX_CURRENT_CHARGE`) → `number` entities
  - controllable boolean data points (e.g. `ON_OFF`, `ENABLE_CHARGING`) → `switch`
  - device settings (`/things/{id}/settings`): booleans (e.g.
    `BATTERY_CHARGE_FROM_GRID_ALLOWED`) → `switch`, numbers → `number`, text →
    read-only sensor
- **Actions**: `neoom_beaam.send_command`, `neoom_beaam.update_setting`,
  `neoom_beaam.push_states` (feed values into a *Generic* device configured on
  connect.neoom.com, e.g. an HA-measured heat pump).
- Picks up changes automatically: when devices are added/removed on the BEAAM
  (config version changes), the integration reloads itself within 10 minutes.
- Re-authentication, reconfiguration (new IP), polling interval option,
  diagnostics download (API key and coordinates redacted).

Interpretation notes:
- Sign conventions are the BEAAM's: `POWER_GRID` positive = export, negative =
  import; `POWER_STORAGE` positive = discharging. Battery `TARGET_POWER`
  positive = charge, negative = discharge.
- The unitless `FRACTION_*` energy flow shares (0–1) are shown as %.
- Device settings are reported by the BEAAM as strings (`"true"`, `"1"`); they
  are mapped to switches/numbers and written back in the same string form.
- Data points without any value on your site (e.g. charging stations, heating
  when you have none) are created disabled.
- Array values (e.g. rack temperatures) become sensors that are disabled by default.
  The sensor state is the values as text, and the full list is in the `values` attribute.

## Installation

### HACS (custom repository)
1. Push this folder to a Git repository (e.g. GitHub).
2. HACS → ⋮ → *Custom repositories* → add the repo URL, category *Integration*.
3. Install **neoom BEAAM (local)** and restart Home Assistant.

### Manual
Copy `custom_components/neoom_beaam` into `<config>/custom_components/` and
restart Home Assistant.

## Setup

*Settings → Devices & services → Add integration → neoom BEAAM (local)*

- **Host**: IP of your BEAAM, e.g. `192.168.1.28`
- **API key**: the local BEAAM key (`sk_beaam_…`). How to get it: <https://neoom.com/developers>

Requires Home Assistant 2025.1 or newer (tested on 2026.10).

## Controlling the battery: be careful

Writing `TARGET_POWER` overrides the BEAAM's own energy management for that battery.
Keep that in mind before using it in automations. Value ranges for number entities are
estimates because the API does not publish limits. The BEAAM rejects values outside the
device's real limits, and the error appears in HA.

Example automation action:

```yaml
action: neoom_beaam.send_command
data:
  device_id: <battery device>
  key: TARGET_POWER
  value: -3000   # discharge with 3 kW
```

## Checking your BEAAM without Home Assistant

`scripts/beaam_check.py` makes read-only calls and lists every entity the integration would
create, with current values:

```bash
BEAAM_HOST=192.168.1.28 BEAAM_API_KEY=sk_beaam_... python3 scripts/beaam_check.py
```

## Development

```bash
uv venv && uv pip install pytest-homeassistant-custom-component
.venv/bin/python -m pytest
```

Tests run against a mocked BEAAM (`tests/conftest.py`).

API reference: <https://developer.neoom.com/reference/concepts-terms-1> (BEAAM API v2.13).
