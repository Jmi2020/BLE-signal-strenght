# BLE Signal Strength Scanner

A real-time Bluetooth Low Energy (BLE) device scanner that displays signal strength and device information in a terminal-based interface.

## Features

- Real-time scanning of nearby BLE devices
- Signal strength visualization with ASCII bar graphs
- Automatic logging of device data to CSV file (every 10 seconds)
- Two display modes:
  - Basic Mode: Compact view with device names, addresses, and signal strength
  - Detailed Mode: Comprehensive view including:
    - Device Name
    - MAC Address
    - Signal Strength (RSSI)
    - Device Type/Appearance
    - Advertised Services
    - Manufacturer Data
- Auto-refresh of device list
- Removal of inactive devices after 10 seconds
- Terminal-based UI with keyboard controls

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
   - Press 'd' to toggle between basic and detailed view
   - Press Ctrl+C to exit

3. Logging:
   - Device data is automatically logged to `ble_scan.log` in CSV format
   - Log entries are organized in scan blocks, with each block representing a 10-second scan
   - Each block includes:
     - Block start delimiter (BEGIN SCAN BLOCK #)
     - Device entries with:
       - Timestamp (UTC)
       - Device Name
       - MAC Address
       - RSSI Value
     - Block end delimiter (END SCAN BLOCK #)
     - Empty line between blocks
   - New blocks are added every 10 seconds while the program runs

## Display Modes

### Basic Mode
Shows a compact list of devices with:
- Device Name
- MAC Address
- Signal Strength Bar
- RSSI Value (in dBm)

### Detailed Mode
Shows comprehensive information for each device:
- Device Name
- MAC Address
- Signal Strength (with visual bar and dBm value)
- Device Type
- Available Services
- Manufacturer Data

## Technical Notes

- Signal strength (RSSI) typically ranges from -30 dBm (strong) to -100 dBm (weak)
- Devices that haven't been seen for 10 seconds are automatically removed from the display
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