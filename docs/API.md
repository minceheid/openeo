# OpenEO Config Server API Documentation

The Config Server module (`configserver.py`) provides a comprehensive REST API for monitoring, configuring, and managing the OpenEO charger. It runs as a threaded HTTP server on the configured port (default: 80).

## Base URL

```
http://<charger-ip>/
http://openeo.local/
```

## API Endpoints

### Status & Monitoring Endpoints

#### GET `/getstatus`
Returns the current state and metrics of the charger as recorded in the global state dictionary.

**Response**: JSON object containing all public state variables

**Example Response**:
```json
{
  "eo_serial_number": "12345678",
  "eo_amps_requested": 16,
  "eo_charger_state_id": 12,
  "eo_charger_state": "charging",
  "eo_session_joules": 45000000,
  "eo_session_kwh": 12.5,
  "eo_session_timestamp": 1692345600,
  "eo_session_seconds_charged": 3600,
  "eo_session_cost": 2.50,
  "eo_current_site": 32.5,
  "eo_current_vehicle": 16.0,
  "eo_current_solar": 8.2
}
```

**Notes**:
- Variables prefixed with `_` (private) are excluded from the response
- All numerical values included in the response
- State snapshot is refreshed on each request

---

#### GET `/metrics`
Exports charger metrics in Prometheus format for time-series monitoring and visualization.

**Response**: Plain text in Prometheus exporter format

**Example Response**:
```
# HELP eo_charger_state_id charging
# TYPE eo_charger_state_id gauge
eo_charger_state_id{} 12
# TYPE eo_amps_requested gauge
eo_amps_requested{} 16
# TYPE eo_current_site gauge
eo_current_site{} 32.5
# TYPE eo_current_vehicle gauge
eo_current_vehicle{} 16.0
# TYPE eo_session_kwh gauge
eo_session_kwh{} 12.5
```

**Usage**: Configure Prometheus scrape job:
```yaml
scrape_configs:
  - job_name: 'openeo'
    static_configs:
      - targets: ['openeo.local']
    metrics_path: '/metrics'
```

**Notes**:
- Only numeric values are exported
- Boolean values are converted to integers (0/1)
- The charger state ID includes a HELP comment with the state description
- Compatible with Grafana for visualization

---

#### GET `/api`
Returns charger status for Home Assistant integration.

**Response**: JSON object with charger state and metrics

**Example Response**:
```json
{
  "eo_charger_state": {
    "id": 12,
    "status": "charging"
  },
  "eo_amps_requested": 16,
  "eo_current_site": 32.5,
  "eo_current_vehicle": 16.0,
  "eo_current_solar": 8.2,
  "eo_session_kwh": 12.5
}
```

**Usage**: Configure Home Assistant MQTT/REST integration to pull from this endpoint

**Notes**:
- Includes descriptive charger state (both ID and string)
- Suitable for Home Assistant REST sensors

---

### Configuration Endpoints

#### GET `/getconfig`
Retrieves the current configuration of all active modules.

**Response**: JSON object with module configurations

**Example Response**:
```json
{
  "chargeroptions": {
    "enable": true,
    "max_current": 32,
    "min_current": 6
  },
  "scheduler": {
    "enabled": true,
    "schedule_1_start": "07:00",
    "schedule_1_end": "22:00",
    "schedule_1_amps": 16
  },
  "solar": {
    "enabled": false,
    "ct_ratio": 2000,
    "grid_voltage": 230
  },
  "loadmanagement": {
    "enabled": true,
    "site_max_current": 100
  }
}
```

**Notes**:
- Private configuration keys (starting with `_`) are excluded
- Returns configurations from all loaded plugin modules
- Reflects the live running configuration

---

#### POST `/setsettings`
Updates configuration settings via form-encoded POST variables.

**Request**: Form-encoded POST data with module:key pairs

**Example Request**:
```
Content-Type: application/x-www-form-urlencoded

chargeroptions:max_current=20&scheduler:schedule_1_amps=16&solar:enabled=true
```

**Response**: JSON with status and updated configuration

**Example Response**:
```json
{
  "status": "success",
  "config": {
    "chargeroptions": {
      "enable": true,
      "max_current": 20
    },
    "scheduler": {
      "enabled": true,
      "schedule_1_amps": 16
    },
    "solar": {
      "enabled": true
    }
  }
}
```

**Notes**:
- Format: `module:key=value&module:key=value`
- Multiple settings can be updated in a single request
- All modules are reconfigured after settings are applied
- Changes are persisted to the SQLite configuration database
- CORS headers included for development versions

---

### User Settings Endpoints

#### GET `/get_user_settings`
Retrieves the user-configurable settings schema for all modules.

**Response**: JSON object with settings definitions for each module

**Example Response**:
```json
{
  "scheduler": {
    "name": "Charging Scheduler",
    "fields": [
      {
        "type": "boolean",
        "name": "enabled",
        "label": "Enable Module",
        "default": true
      },
      {
        "type": "time",
        "name": "schedule_1_start",
        "label": "Schedule 1 Start Time",
        "default": "07:00"
      },
      {
        "type": "number",
        "name": "schedule_1_amps",
        "label": "Schedule 1 Amperage",
        "default": 16,
        "min": 6,
        "max": 32
      }
    ]
  },
  "solar": {
    "name": "Solar Integration",
    "fields": [
      {
        "type": "boolean",
        "name": "enabled",
        "label": "Enable Solar Charging",
        "default": false
      }
    ]
  }
}
```

**Notes**:
- Used by the web UI to dynamically generate configuration forms
- Each module implements `get_user_settings()` method
- Non-core plugins automatically include an "enabled" toggle
- Field types: boolean, string, number, time, etc.

---

### Session Data Endpoints

#### GET `/getsessiondata`
Retrieves historical charging session data from the chargersession module.

**Response**: JSON array of charging sessions

**Example Response**:
```json
[
  {
    "session_id": 1,
    "start_time": "2024-08-22 10:30:00",
    "end_time": "2024-08-22 11:30:00",
    "duration_seconds": 3600,
    "energy_kwh": 8.5,
    "cost": 2.13,
    "tariff_used": 0.25
  },
  {
    "session_id": 2,
    "start_time": "2024-08-22 14:00:00",
    "end_time": "2024-08-22 15:00:00",
    "duration_seconds": 3600,
    "energy_kwh": 10.2,
    "cost": 2.55,
    "tariff_used": 0.25
  }
]
```

**Notes**:
- Available only if the chargersession module is loaded
- Returns empty array if module is not active
- Includes cost calculations based on configured tariffs

---

### Chart Data Endpoints

#### GET `/getchartdata`
Retrieves historical chart data from the data logger for visualization.

**Query Parameters**:
- `type` (string): Format type - `plotly` or raw data
- `since` (datetime): Filter data since this timestamp (format: `YYYY-MM-DD HH:MM:SS.ffffff`)
- `series` (string): Comma-separated list of data series to retrieve

**Example Requests**:
```
GET /getchartdata?type=plotly&since=2024-08-22%2010:00:00.000000&series=eo_current_site,eo_current_vehicle
GET /getchartdata?type=raw&since=2024-08-22%2010:00:00.000000
```

**Response**: 
- `type=plotly`: JSON in Plotly format ready for visualization
- `type=raw`: Raw data points with timestamps

**Example Plotly Response**:
```json
{
  "data": [
    {
      "name": "Site Current",
      "x": ["2024-08-22T10:00:00", "2024-08-22T10:05:00"],
      "y": [32.5, 31.2],
      "type": "scatter"
    }
  ]
}
```

**Notes**:
- Available only if the data logger module is loaded
- Returns 404 if data logger is not available
- Datetime parsing is flexible; invalid dates result in `None` (returns all data)
- Series names should correspond to global state variable names

---

### System Management Endpoints

#### GET `/restart`
Requests a restart of the OpenEO application.

**Response**:
```json
{
  "status": "requested"
}
```

**Notes**:
- This is a potential DoS endpoint - consider access controls in production
- Introduces 1-second delay to allow response to be sent before restart
- Triggers `util.restart_python()` which cleanly restarts the application
- Configuration and database persist across restart

---

#### GET `/debugdata`
Retrieves system debug information and logs for troubleshooting.

**Response**: JSON object with system commands output

**Example Response**:
```json
{
  "whoami": "pi",
  "df -k": "Filesystem     1K-blocks    Used Available Use% Mounted on...",
  "netstat -4l": "Active Internet connections (only servers)...",
  "ps -ef | grep openeo": "pi 1234 1 0 10:00 ? 00:00:05 /usr/bin/python3",
  "free -h": "              total        used        free...",
  "systemctl status openeo --no-pager --output=short-precise": "● openeo.service - OpenEO Charger...",
  "ls -l /home/pi/releases/": "total 156...",
  "journalctl --list-boots": "-2 0b52d44e8ba344f0a51e8f87e2e97a47...",
  "journalctl -b 2": "[boot -2] ...",
  "journalctl -b 1": "[boot -1] ...",
  "journalctl": "[recent logs] ...",
  "log": "[2024-08-22 10:00:00] startup:v0.9.3.3..."
}
```

**Notes**:
- Captures output from multiple system commands
- Includes disk usage, network status, processes, memory, service status
- Includes release history and recent journal logs
- Returns command error messages if execution fails
- Useful for diagnostics and support

---

#### POST `/update`
Triggers a software update check and installation.

**Request**: JSON with action specification

**Example Request**:
```json
{
  "action": "check"
}
```

**Response**:
```json
{
  "status": "checking",
  "message": "Checking for updates..."
}
```

**Notes**:
- Delegates to `lib.configserver_updater.OpenEO_updater` class
- Possible actions: `check`, `install`, `rollback` (depending on implementation)
- Update process runs in background thread
- Progress can be monitored via `/debugdata` endpoint

---

### Static File Serving

#### GET `/static/*`
Serves static web interface files.

**Supported File Types**:
- `.html` - HTML templates (served as text/html)
- `.js` - JavaScript files (text/javascript)
- `.css` - CSS stylesheets (text/css)
- `.png` - PNG images (image/png)
- `.svg` - SVG vectors (image/svg+xml)
- `.ico` - Icon files (image/icon)

**Example Requests**:
```
GET /                          # Redirects to /static/index.html
GET /static/index.html         # Web interface
GET /static/settings.html      # Settings page
GET /static/js/app.js          # JavaScript application
GET /static/css/style.css      # Stylesheet
GET /static/images/logo.svg    # Vector graphic
```

**Notes**:
- Directory traversal attempts (`..` in paths) are blocked with 403 Forbidden
- Files not found return 404 Not Found
- Binary files (images, icons) served in binary mode
- Text files encoded as UTF-8

---

## CORS Headers

CORS headers (`Access-Control-Allow-Origin: *`) are included in responses for development/testing versions (version `0.0` or `main`). This allows cross-origin requests from frontend development tools.

**Affected Endpoints**:
- `/getconfig`
- `/getstatus`
- `/get_user_settings`
- `/getsessiondata`
- `/getchartdata`
- `/metrics`
- `/update`
- `/setsettings`

---

## Error Handling

### 404 Not Found
Returned when:
- Endpoint does not exist
- Static file cannot be found
- Data logger is not available (for `/getchartdata`)

**Response**:
```
404 Not Found
```

### 403 Forbidden
Returned when:
- Path contains `..` (directory traversal attempt)

**Response**:
```
403 Forbidden - but, nice try
```

---

## Request/Response Format

### Headers
- **Content-Type**: `application/json` (for JSON endpoints), `text/plain` (for Prometheus), `text/html` (for HTML)
- **Accept**: Not required (server determines format based on endpoint)
- **Content-Length**: Required for POST requests

### Encoding
- All JSON responses are UTF-8 encoded
- Binary files (images) handled natively
- Form-encoded POST data UTF-8 decoded

---

## Module Integration

The Config Server interacts with loaded plugin modules through the global state dictionary. Each module can:

1. **Implement `get_user_settings()`** - Returns schema for configuration form generation
2. **Provide `pluginConfig`** - Configuration dictionary exposed via `/getconfig`
3. **React to `configure()`** - Called after `/setsettings` to apply changes
4. **Update `globalState.stateDict`** - State variables exposed via `/getstatus`, `/metrics`, `/api`

---

## Security Considerations

### Current Status
- No authentication/authorization implemented
- `/restart` endpoint is unprotected (potential DoS)
- CORS headers enabled for development versions
- Directory traversal attempts blocked

### Recommendations for Production
1. Implement network-level access control (firewall rules)
2. Add rate limiting to prevent DoS attacks
3. Consider adding API key or token-based authentication
4. Restrict `/restart`, `/update`, `/setsettings` endpoints to trusted clients
5. Review CORS configuration for development vs. production
6. Implement logging/auditing of configuration changes

---

## Examples

### Monitor Charging via Prometheus
```bash
curl http://openeo.local/metrics
```

### Get Current Charger Status
```bash
curl http://openeo.local/getstatus | jq .
```

### Update Charging Amperage
```bash
curl -X POST http://openeo.local/setsettings \
  -d 'chargeroptions:max_current=20'
```

### Retrieve Last 6 Hours of Data
```bash
SINCE=$(date -u -d '6 hours ago' '+%Y-%m-%d %H:%M:%S.%f')
curl "http://openeo.local/getchartdata?type=raw&since=${SINCE}"
```

### Check for Updates
```bash
curl -X POST http://openeo.local/update \
  -H 'Content-Type: application/json' \
  -d '{"action":"check"}' | jq .
```

### Get Debug Information
```bash
curl http://openeo.local/debugdata | jq .
```

---

## Version Information

**Current API Version**: 1.0 (as of OpenEO v0.9.3.3)

**Endpoints Added Over Time**:
- Core endpoints (`/getstatus`, `/metrics`, `/api`, `/getconfig`, `/setsettings`): v0.1
- Module settings (`/get_user_settings`): v0.5
- Session data (`/getsessiondata`): v0.7
- Chart data (`/getchartdata`): v0.8
- Debug and update endpoints: v0.8+
