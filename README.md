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
- Session logs with switchable kWh/cost views
- CSV export for detailed analysis and record-keeping
- Support for complex tariff structures

### 📊 Advanced Features
- **Load Balancing**: Manage total site current draw to prevent circuit breaker trips
- **CT Calibration**: Fine-tune current transformer readings with offset and scaling adjustments
- **Statistics Dashboard**: Comprehensive visualizations of charger operations
- **Home Assistant Integration**: Export data via `/api` endpoint
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

8. **Complete Setup**
   - Configure your home WiFi network
   - Set timezone for your installation
   - Optionally add SSH key for command-line access
   - **Note**: Configuration portal is active for 30 minutes after every reboot and once WiFi is configured can also be accessed via `http://<charger-ip>:81/`

9. **Access Main Interface**
   - Disconnect from OpenEO network and reconnect to your home WiFi
   - Access the dashboard at `http://openeo.local/` or `http://<charger-ip>/`

<p align="center">
<img src="https://github.com/user-attachments/assets/f9470a6f-b815-4cda-ac31-8901c7547a36" style="width:25%; height:auto;" />
</p>

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
Export charger data for Home Assistant integration:
- Endpoint: `http://<charger-ip>/api`
- Provides current charger state, power metrics, and session data

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
