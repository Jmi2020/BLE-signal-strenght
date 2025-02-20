# BLE Signal Strength Scanner

A real-time Bluetooth Low Energy (BLE) device scanner that displays signal strength and device information in a terminal-based interface.

## Features

- Real-time scanning of nearby BLE devices
- Signal strength visualization with ASCII bar graphs
- Interactive device selection and detailed view
- Persistent device tracking (keeps inactive devices visible)
- Automatic logging of device data to CSV file (every 30 seconds)
- Smart device sorting:
  - Active devices sorted by signal strength
  - Inactive devices sorted by last seen time
- Visual indication of device status (active/inactive)
- Device age tracking and human-readable timestamps

## Requirements

- Python 3.7 or higher
- macOS, Linux, or Windows
- Bluetooth adapter with BLE support

## Installation

1. Create a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows
```

2. Install required packages:

```bash
pip install -r requirements.txt
```

## Usage

1. Run the scanner:

```bash
python ble_scanner.py
```

2. Controls:
   - Arrow keys (↑/↓) to navigate through devices
   - Enter to toggle detailed view for selected device
   - 'q' to return to list view
   - Ctrl+C to exit

3. Display Features:
   - Active devices shown with signal strength bars
   - Inactive devices shown dimmed with last seen time
   - Selected device highlighted
   - Devices remain visible for 5 minutes after last contact

4. Logging:
   - Device data is automatically logged to `ble_scan.log` in CSV format
   - Log entries are organized in scan blocks
   - Each block includes:
     - Block start delimiter (BEGIN SCAN BLOCK #)
     - Device entries with:
       - Timestamp (UTC)
       - Device Name
       - MAC Address
       - RSSI Value
     - Block end delimiter (END SCAN BLOCK #)
     - Empty line between blocks
   - New blocks are added every 30 seconds while the program runs

## Display Modes

### List View

Shows an interactive list of all devices with:

- Device Name
- MAC Address
- Signal Strength Bar (for active devices)
- Status:
  - Active devices: Current RSSI value in dBm
  - Inactive devices: Time since last seen

### Detail View

Shows comprehensive information for the selected device:

- Device Name
- MAC Address
- Signal Strength:
  - Active devices: Visual bar and dBm value
  - Inactive devices: Last seen timestamp
- Device Type
- Available Services
- Manufacturer Data

## Technical Notes

- Signal strength (RSSI) typically ranges from -30 dBm (strong) to -100 dBm (weak)
- Devices are considered inactive after 15 seconds without signal
- Devices are retained in the list for 5 minutes after last contact
- The scanner requires appropriate permissions to access the Bluetooth adapter
- On macOS, you need to grant Bluetooth permissions when prompted
- On Linux systems, you might need to run with sudo or add appropriate permissions

## Troubleshooting

1. **Bluetooth Access**
   - Ensure Bluetooth is enabled on your system
   - Check that your system has a BLE-compatible adapter
   - On Linux, you might need to run with sudo for Bluetooth access

2. **Permission Issues**
   - macOS: Accept Bluetooth permission requests when prompted
   - Linux: Run with sudo or add user to the bluetooth group:

     ```bash
     sudo usermod -a -G bluetooth $USER
     ```

   - Windows: Run as administrator if needed

3. **No Devices Found**
   - Verify that nearby BLE devices are advertising
   - Check if Bluetooth is enabled and permissions are granted
   - Ensure your Bluetooth adapter supports BLE
