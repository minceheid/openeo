# Cloudless Software for the EO Smart Home Hub/Mini and Mini Pro 2 EV Charger

[![Latest Release](https://img.shields.io/github/v/release/minceheid/openeo)](https://github.com/minceheid/openeo/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/minceheid/openeo)](https://github.com/minceheid/openeo)
[![GitHub forks](https://img.shields.io/github/forks/minceheid/openeo)](https://github.com/minceheid/openeo/network)

EO Charging announced in July 2025 that their EO Smart Home app will be discontinued on November 30th, 2025. This would disable the ability for owners to set automated timed schedules and to directly manage their device, leaving chargers operating purely as basic "plug & play" units.

OpenEO is an open-source alternative that can be directly installed on EO Smart Home Hub and Mini Pro 2 devices to enable full local WiFi network control without relying on the manufacturer's cloud services.

<p align="center">
<img src="https://github.com/user-attachments/assets/e8eb317d-e411-4b7b-83f1-c2d1a450f97c" style="width:25%; height:auto;"/>
<img src="https://github.com/user-attachments/assets/d41a2b3e-8d2e-4806-81a4-dd613ddad66c" style="width:25%; height:auto;"/>
<img src="https://github.com/user-attachments/assets/72bbf639-530b-4743-a0a7-431bfc92eaa2" style="width:25%; height:auto;"/>
</p>

---

## 🎯 Key Features

### ⚡ Core Functionality
- **Local WiFi Control**: Manage your charger directly from your home network—no cloud required
- **Automated Scheduling**: Define multiple timed charging schedules with flexible start/end times and amperage settings
- **Real-Time Monitoring**: Live charger status, power metrics, and diagnostics
- **Session Logging**: Complete charging history with energy consumption (kWh) and cost analysis
- **Configuration Portal**: Web-based setup for WiFi, timezone, and SSH keys (accessible for 30 minutes after reboot)

### ☀️ Solar Integration
Smart charging based on solar generation with:
- Solar timers allowing selective charging during specific hours
- Live solar generation status visualization on the homepage
- Yellow sun icon when solar is active and sufficient
- Cloudy icon when solar generation is insufficient for charging

### 💰 Electricity Cost Tracking
- Automatic cost calculation based on configurable electricity tariffs
- Optional live pricing from Home Assistant (e.g. Intelligent Octopus or Agile), settled per half-hour, with automatic fallback to the tariff schedule ([details](#live-tariff-rate-from-home-assistant))
- Session logs with switchable kWh/cost views
- CSV export for detailed analysis and record-keeping
- Support for complex tariff structures

### 📊 Advanced Features
- **Load Balancing**: Manage total site current draw to prevent circuit breaker trips
- **CT Calibration**: Fine-tune current transformer readings with offset and scaling adjustments
- **Statistics Dashboard**: Comprehensive visualizations of charger operations
- **Home Assistant Integration**: MQTT auto-discovery with sensors, schedule and charging controls, and live tariff input
- **Prometheus Metrics**: Export operational metrics via `/metrics` endpoint

### 🌍 Remote Access (Optional)
OpenEO Cloud service allows secure internet access to your charger:
- Encrypted connection to remote webservice
- Access your charger from anywhere via https://openeo.uk
- 14 days free usage on first login (subscription required after)

---

## 📋 Technical Stack

- **Backend**: Python (47.8%) - Core application logic and charger control
- **Frontend**: JavaScript (44.5%) & HTML (4.8%) - Web-based user interface
- **Deployment**: Shell scripts (2.5%) - Automated setup and installation
- **Configuration**: SQLite database for persistent settings
- **License**: MIT

---

## 🏗️ Compatibility

This project is compatible with:
- ✅ **EO Smart Home Hub/Mini** ([Datasheet](https://github.com/user-attachments/files/22066221/EO_Home_Hub.pdf))
- ✅ **EO Mini Pro 2** ([Manual](https://github.com/user-attachments/files/22066224/eo-mini-pro-2-installation-and-userguide.pdf))
- ❌ **NOT** compatible with Mini Pro 3

<p align="center">
<img src="https://github.com/user-attachments/assets/1ad1ba51-ef88-4cb6-9a99-9f922e32f02c" style="width:25%; height:auto;" />
<img src="https://github.com/user-attachments/assets/5488462c-a5c6-44c0-843b-16ec874e846a" style="width:25%; height:auto;" />
</p>

---
## Homebridge / Apple Home Matter Plugin

[@wazza151](https://github.com/wazza151) has created a Homebridge/Apple Home Matter Plugin that works with OpenEO. This plugin shows an EO Mini Pro 2 or EO Smart Home Hub EV charger in Apple Home, when the charger runs OpenEO.

The plugin:
* talks to the charger on your home network - no account or cloud needed
* finds the charger on the network by itself
* shows a charge now on/off tile, a Car Connected sensor and a Charging Schedule switch
* shows a Charger Problem sensor, which alerts you if the charger reports a fault or goes offline
* can show live watts and kWh in the Home app, over Matter (Homebridge v2.2 or above)
* adds a status page with recent charging sessions to the plugin's settings page

https://github.com/homebridge-plugins/homebridge-openeo

---

## 🚀 Installation

### Prerequisites
- EO Smart Home Hub/Mini or Mini Pro 2 device
- Micro SD card (8GB or larger, Class 10 recommended)
- WiFi network with internet connectivity
- Ability to safely power down your EV charger

### Step-by-Step Installation

1. **Prepare SD Card**
   - Obtain an 8GB (or larger) Class 10 micro SD card

2. **Download SD Image**

   [![Download SD Image](https://img.shields.io/badge/download-SD%20image-blue)](https://github.com/minceheid/openeo/releases/latest/download/openeo_latest.img.xz) 
   [![SHA256](https://img.shields.io/badge/checksum-sha256-lightgrey)](https://github.com/minceheid/openeo/releases/latest/download/openeo_latest.img.xz.sha256)

3. **Write Image to SD Card**
   - Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/) or similar tool
   - Write the OpenEO image to your SD card
   - **Important**: Do not change the default username (`pi`) - the installation requires it

4. **Safely Power Down Your Charger**
   - Disconnect power by switching off the relevant breaker in your consumer unit
   - Ensure the device is completely powered down

5. **Install Raspberry Pi**
   - Open the EO enclosure by loosening the four captive screws on the front
   - Remove any rubber covers if present
   - Install the SD card into the Raspberry Pi
   - Secure the cable connection between Raspberry Pi and power board

6. **Boot**
   - Close the enclosure and apply power
   - The Raspberry Pi should boot

7. **Access Configuration Portal**
   - Look for "OpenEO" wireless network on your phone/tablet
   - Connect to it
   - Your browser should auto-redirect to the configuration interface
   - If not, navigate to `192.168.1.1`
<p align="center">
<img src="https://github.com/user-attachments/assets/f9470a6f-b815-4cda-ac31-8901c7547a36" style="width:25%; height:auto;" />
</p>

8. **Complete Setup**
   - Configure your home WiFi network
   - Set timezone for your installation
   - Optionally add SSH key for command-line access - the following openssh key types are accepted:

| Key type | Accepted prefix | Notes |
|---|---|---|
| DSA | `ssh-dss` | Legacy/deprecated DSA keys |
| ECDSA P-256 | `ecdsa-sha2-nistp256` | Only the NIST P-256 curve |
| FIDO/U2F ECDSA | `sk-ecdsa-sha2-nistp256@openssh.com` | Security-key-backed ECDSA |
| Ed25519 | `ssh-ed25519` | Standard Ed25519 |
| FIDO/U2F Ed25519 | `sk-ssh-ed25519@openssh.com` | Security-key-backed Ed25519 |
| RSA | `ssh-rsa` | Standard RSA public-key format |

   - **Note**: Configuration portal is active for 30 minutes after every reboot and once WiFi is configured can also be accessed via `http://<charger-ip>:81/`
   

9. **Access Main Interface**
   - Disconnect from OpenEO network and reconnect to your home WiFi
   - Access the dashboard at `http://openeo.local/` or `http://<charger-ip>/`



---

## 📖 Usage Guide

### Home Page & Status
- View current charger state and power metrics
- Navigate between multiple charging schedules
- Create new schedules or delete existing ones
- Each schedule displays as a separate clockface showing start, end, and amperage

### Charging Schedules
Multiple schedules can be defined independently:
- All defined timer schedules operate simultaneously
- Manual controls can override timers (disable all or manually switch)
- Scroll through schedules on the home page
- Set start time, end time, and charging amps (6-32A) for each schedule

### Session Logs
Access your charging history with:
- Energy consumption tracking (kWh)
- Electricity cost calculation
- Session duration and power delivery metrics
- Charts switchable between kWh and cost views
- Download data as CSV for spreadsheet analysis

**To configure electricity tariff**:
- Go to Settings → Session section
- Due to complexity, use a tablet or laptop for better visibility
- Defines cost per kWh based on time periods
- To cost sessions at a live rate from Home Assistant instead, turn on **Use live rate from Home Assistant** in the same section, or the charger's **Use Live Rate** switch in Home Assistant (see [Live tariff rate from Home Assistant](#live-tariff-rate-from-home-assistant))

<p align="center">
<img src="https://github.com/user-attachments/assets/721c6756-efaa-4548-bb86-0f258b9ddb57" style="width:50%; height:auto;"/>
<img src="https://github.com/user-attachments/assets/ab46eb7a-3565-4121-aadc-99f2e2a5db18" style="width:50%; height:auto;"/>
</p>

### Statistics
Full visualization of charger operations including:
- Historical performance data
- Energy consumption trends
- Load balancing metrics

<p align="center">
<img src="https://github.com/user-attachments/assets/fde895b3-f1b9-412e-b4d5-4eb02fb3200a" style="width:50%; height:auto;"/>
</p>

### Solar Integration
To enable solar-based charging:

1. Ensure CT clamp is measuring solar generation
2. Go to Settings and enable "Solar Charging Enabled"
3. Create "Solar Timers" on the home page to define hours when solar charging is active
4. If no solar timers are defined, solar charging is active at all times

**Solar Status Icons**:
- 🟡 Yellow sun: Solar is active and generating sufficient power
- ☁️ Cloud: Solar is enabled but generation is insufficient
- Green indication: Charger is actively drawing solar power

**Important Note**: The EO hardware cannot measure the difference between export and import current. If solar generation exceeds your charger's draw, excess power will flow to the grid (not into your home battery if you have one). Account for this in your scheduling.

<p align="center">
<img src="https://github.com/user-attachments/assets/55ec3fd4-405a-4253-8d5e-32bb0b3d41d3" style="width:25%; height:auto;"/>
<img src="https://github.com/user-attachments/assets/a3d75cb3-9722-4384-89bb-4f34ad93d9c4" style="width:33%; height:auto;"/>
</p>

### Load Balancing
Prevent circuit breaker trips on shared or looped supplies:

1. Install CT clamp on your inbound electricity supply (usually at meter)
2. Go to Settings → Load Management
3. Set site maximum current draw (default is appropriate for most installations)
4. OpenEO automatically limits charger current to stay within site limits

### CT Calibration
Fine-tune current transformer readings (recommended from tablet/laptop):

1. Go to Settings → CT Calibration
2. View rolling 15-minute chart of CT readings
3. Adjust using sliders:
   - **Offset**: Added to CT reading (-2A to +2A)
   - **Scaling**: Multiplied to CT reading (0.8 to 1.2, or -20% to +20%)
4. Observe visual changes in real-time
5. Click "Save" when satisfied

<p align="center">
<img src="https://github.com/user-attachments/assets/82ba7e4e-536d-4c29-9d55-d6973e2bc0b3" style="width:50%; height:auto;"/>
</p>

---

## 🔌 Integration with Home Automation

### Home Assistant
OpenEO connects to Home Assistant over MQTT. It uses MQTT discovery, so the charger appears in Home Assistant as a device with its sensors and controls, with no YAML to write.

**Set up**
1. In Home Assistant, set up an MQTT broker (for example the Mosquitto add-on) and the MQTT integration.
2. On the charger, in Settings → Home Assistant MQTT, set "Enable Module" to "Yes" and enter the broker host, port (normally 1883; TLS is not supported), and username and password if your broker needs them.
3. Optionally, change:
   - **Device Name in HA**: the name Home Assistant shows for the charger.
   - **Device ID**: must be unique for each charger on the same broker. Changing it creates a new device in Home Assistant.
   - **HA Discovery Prefix**: leave it as `homeassistant` unless you changed it in Home Assistant.
   - **Publish Interval**: 5-3600 seconds, default 300.

The charger then appears under Settings → Devices & services → MQTT. Its entities show as unavailable if the charger loses its MQTT connection.

**Sensors**
| Entity | What it shows |
|---|---|
| Charger State | the charger's current state, e.g. `idle`, `car-connected`, `charging` |
| Vehicle Connected, Cable Connected, Charging Active | binary sensors derived from the charger state |
| Amps Requested, Amps Limit | current requested from the car and the limit in force |
| Power Delivered, Power Requested | power to the car |
| Voltage, Mains Frequency | supply readings |
| Site Current, Vehicle Current, Solar Current | CT clamp readings |
| Session KWh, Session Cost | energy and cost for the current session |
| Current Rate, Rate Source, HA Rate Received | tariff rate in use and where it came from (see [Live tariff rate from Home Assistant](#live-tariff-rate-from-home-assistant)) |
| Wi-Fi Health | Wi-Fi status, with `code`, `message` and `since` attributes |
| Wi-Fi Pinned AP | the access point the charger is pinned to, or `none` |

**Controls**
- **Charging** switch: starts charging now at the **Current Limit** current, whatever the schedules say. Turning it off only stops this manual charge: charge and solar schedules still run while their own switches (**Timers**, **Solar Charging**) are on.
- **Current Limit**: the current the **Charging** switch charges at, from 6 A up to the charger's overall current limit. It does not limit schedules.
- **Timers** switch: turns the Scheduler module on or off.
- **Charge Schedule N Start / End / Current**, **Delete Charge Schedule N** and **Add Charge Schedule**: edit charging schedules. These are only available while Timers is on.
- **Solar Charging** switch: turns solar charging on or off (Site and Solar Load Management).
- **Solar Schedule N Start / End / Reservation**, **Delete Solar Schedule N** and **Add Solar Schedule**: edit solar schedules. These are only available while Solar Charging is on.
- **Use Live Rate** switch: see [Live tariff rate from Home Assistant](#live-tariff-rate-from-home-assistant).

When more than one of these asks to charge at the same time, the charger uses the highest current requested, capped by the overall current limit and site load management. To stop all charging, turn off **Charging**, **Timers** and **Solar Charging**.

Schedules added or removed in the charger's web UI appear in Home Assistant automatically.

**REST API.** If you don't use MQTT, `http://<charger-ip>/api` returns the charger state, power readings and session data as JSON.

### Live tariff rate from Home Assistant
Cost sessions at a live price (for example Intelligent Octopus or Agile) instead of the fixed tariff schedule. Home Assistant pushes the current rate to the charger over MQTT.

**Enable it**
1. Set up the [Home Assistant](#home-assistant) module first.
2. In Settings → Session, turn on **Use live rate from Home Assistant**, or turn on the charger's **Use Live Rate** switch in Home Assistant (it is the same setting). The change takes effect the next time the car is plugged in. If the car is already plugged in, unplug and re-plug it, or the change applies from midnight. **HA rate stale after** (10-60 min, default 15) sets how long a rate is trusted without an update; it must be longer than the blueprint's 5-minute heartbeat.
3. Import the blueprint: [![Open your Home Assistant instance and import the blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fminceheid%2Fopeneo%2Fmain%2Fhomeassistant%2Fblueprints%2Fopeneo_tariff_rate.yaml)
4. Create an automation from it, choose your rate sensor, and pick your charger from the **OpenEO charger** dropdown.

The blueprint publishes (not retained) to `openeo/<device_id>/command/tariff_rate/set` on every sensor change, every 5 minutes, when HA starts, and whenever the charger's MQTT `online` availability message arrives (so a restarted charger gets the rate within seconds). For manual testing you can publish a bare number (major currency per kWh), or `unavailable`.

**Supported units** are read from the sensor's unit of measurement (case and spaces ignored):

| Unit | Treated as |
|---|---|
| `GBP/kWh`, `EUR/kWh` (any 3-letter currency) | used as is |
| `p/kWh`, `pence/kWh`, `c/kWh`, `ct/kWh`, `¢/kWh`, `öre/kWh` | divided by 100 |
| `GBP/MWh` (any 3-letter currency) | divided by 1000 |

A missing or unrecognised unit is treated as unavailable: the schedule rate is used and a warning is logged once per unit. A rate below -1 or above 5 per kWh also logs a warning once per value, but is still used (negative Agile prices are valid).

**Half-hour settlement.** Suppliers settle in half-hour periods, and Intelligent Octopus prices a whole half-hour at the off-peak rate when a dispatch overlaps it. So energy costed from HA is settled per half-hour slot (HH:00-HH:29, HH:30-HH:59) at the last HA rate received in that slot. The live session cost is provisional for the open slot and can drop partway through it when the rate flips. Energy costed at the schedule rate is never deferred.

**Fallback.** The charger uses the schedule rate whenever the HA rate is stale (no update for the configured time), the sensor is unavailable, Home Assistant is reported offline, or MQTT is disconnected. Fallback is visible in:
- System Logs → App Events (and the journal), for example `Tariff: HA rate stale (no update for 15m) - falling back to schedule rate 0.27048`, and `Tariff: HA rate restored 0.07000`
- the session table detail: "x kWh costed at schedule rate (HA rate unavailable)"
- the Home Assistant **Rate Source** sensor (`ha` or `schedule`), whose `reason` attribute says why the schedule is in use (`stale`, `unavailable`, `ha_offline`, `mqtt_disconnected`, `no_data` or `disabled`); **Current Rate** shows the rate in use

**Home Assistant entities.** Besides **Rate Source** and **Current Rate**, the charger exposes:
- **Use Live Rate** switch: the same setting as Settings → Session; a change takes effect the next time the car is plugged in (or from midnight if it stays plugged in).
- **HA Rate Received** sensor: the last rate the charger received (GBP/kWh), with a `received_at` attribute. Check it after creating the automation to confirm the blueprint is working before you enable the feature.

**Optional Mosquitto ACL.** If your broker supports ACLs (such as the Mosquitto add-on), you can restrict that login so it cannot touch other devices' topics:
```
user <charger-mqtt-user>
topic readwrite openeo/#
topic readwrite homeassistant/#
```
`homeassistant` is the MQTT discovery prefix (adjust if you changed it). The charger publishes its discovery configs under it and reads `homeassistant/status` to see HA go offline, so it needs both.

**Session Cost sensor.** Its state class changed from `total_increasing` to `total` (with a `last_reset`) so that cost can fall during a slot. Home Assistant may show a one-time state class repair notice; long-term statistics sums are unaffected.

### Prometheus
Export metrics in Prometheus format for time-series monitoring:
- Endpoint: `http://<charger-ip>/metrics`
- Includes all operational metrics for visualization in Grafana or similar

---

## 🔄 Updating

OpenEO checks for new releases periodically and displays update availability on the home page.

### Update via Web Interface
1. Click the update notification on the home page
2. Follow the on-screen instructions

### Update via Command Line
```bash
curl -sSL https://github.com/minceheid/openeo/raw/refs/heads/main/openeo_download.py | python3 -
sudo reboot
```

---

## ☁️ OpenEO Cloud (Optional Remote Access)

Access your charger from anywhere via secure encrypted connection.

### Setup

1. Ensure your OpenEO charger is running the latest version
2. Find your charger identification number in Settings → OpenEO Cloud section
3. Sign into [https://openeo.uk](https://openeo.uk) using your Google Account
4. Paste your charger ID into the control panel and click "Save"
5. Copy the generated authorization token
6. Set "Enable Module" to "Yes" in the OpenEO Cloud settings on your charger
7. Paste token into OpenEO Cloud settings on your charger
8. The connection indicator on openeo.uk should turn green when charger connects

**Pricing**: 14 days free usage on first login, then subscription required

**Privacy Note**: All internet requests are transmitted via our webservice to your charger. Your charger initiates the connection, and you maintain full control over what data is shared.

<p align="center">
<img src="https://github.com/user-attachments/assets/c840e866-c1f3-4299-94b8-5d183af61c09" style="width:50%; height:auto;"/>
<img src="https://github.com/user-attachments/assets/dc4edc98-d51a-482d-9fd4-5ab8ee83ecf6" style="width:50%; height:auto;"/>
</p>

---

## 🔧 Advanced: openeo_download.py

Manage downloads and deployments via command line:

```bash
# List available releases and branches
python3 openeo_download.py --list

# Install specific release
python3 openeo_download.py --release v0.9.3.3

# Install from branch (for development purposes)
python3 openeo_download.py --release main
```

---

## 🧑‍💻 For Developers

### REST API Documentation
Complete API reference for the Config Server, including all available endpoints, request/response formats, and integration examples:

📖 **[API Documentation](docs/API.md)** - Full REST API reference

The Config Server provides a comprehensive REST API for:
- **Status Monitoring**: Real-time charger state and metrics
- **Configuration Management**: Get/set module configurations
- **Data Integration**: Prometheus metrics and Home Assistant compatibility
- **Session Data**: Historical charging session information
- **Chart Data**: Historical data with Plotly visualization support
- **System Management**: Restart, debug information, and software updates

**Quick API Examples**:
```bash
# Get current charger status
curl http://openeo.local/getstatus | jq .

# Retrieve Prometheus metrics
curl http://openeo.local/metrics

# Get Home Assistant compatible data
curl http://openeo.local/api | jq .

# Update charging settings
curl -X POST http://openeo.local/setsettings \
  -d 'chargeroptions:max_current=20'
```

### Contributing Code
Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Code style and standards
- Testing procedures
- Pull request process
- Release procedures

### Architecture
The codebase is organized as a plugin-based system:
- **Core Modules**: Configuration server, charger control, state management
- **Plugin System**: Extensible architecture for adding features (scheduler, solar, load balancing, etc.)
- **Configuration Database**: SQLite-based persistent storage
- **Web Interface**: Modern web UI for control and monitoring

For more details, explore the repository structure and module documentation.

---

## 🐛 Troubleshooting

### "Waiting" Message on Startup
Normal during initial boot—software is establishing communication with charger. If it persists:

1. Turn off power to charger at consumer unit
2. Remove enclosure cover
3. Verify cable connection between Raspberry Pi and power board is fully seated on both ends
4. Reassemble and power on

<p align="center">
<img src="https://github.com/user-attachments/assets/8cfa69fe-603f-45b7-bbae-3bec67837291" style="width:50%; height:auto;"/>
</p>

---

## 💚 Support & Contribution

### Reporting Issues
Found a bug? Have a feature request? [Open an issue](https://github.com/minceheid/openeo/issues) on GitHub.

### Contributing Code
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on submitting pull requests.

### Supporting Development
Several ways to support the project:

1. **Subscribe to OpenEO Cloud** - Primary way to support development while getting additional features
2. **Donate** - For those preferring not to use cloud services

<a href="https://donate.stripe.com/9B66oJ0Lb2AkbeZ9SF2oE00">
  <img src="https://github.com/user-attachments/assets/4e257c47-0f61-4faa-8883-8594fb428ef7" style="width:25%; height:auto;"/>
</a>

---

## 📄 License & Disclaimer

**License**: MIT License - see [LICENSE](LICENSE) file for details

**Disclaimer**: This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. This is an independent, open-source project and is not affiliated with EO Charging.

**Safety**: Ensure you understand the electrical safety implications of controlling an EV charger before installation. Use at your own risk.

Copyright © 2025 Mike Scott and contributors

---

## 📚 Additional Resources

- [GitHub Repository](https://github.com/minceheid/openeo)
- [Releases Page](https://github.com/minceheid/openeo/releases)
- [Issues Tracker](https://github.com/minceheid/openeo/issues)
- [Discussions](https://github.com/minceheid/openeo/discussions)
- [OpenEO Cloud Service](https://openeo.uk)
- [API Documentation](docs/API.md)

---

**Questions?** Check the [Issues](https://github.com/minceheid/openeo/issues) section or start a [Discussion](https://github.com/minceheid/openeo/discussions).
