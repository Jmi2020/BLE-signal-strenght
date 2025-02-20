#!/usr/bin/env python3

import asyncio
from bleak import BleakScanner
from blessed import Terminal
import math
import sys
import select
import time
import csv
from datetime import datetime, timezone

class BLEScanner:
    def __init__(self):
        self.term = Terminal()
        self.devices = {}
        self.max_name_length = 20
        self.max_addr_length = 17
        self.bar_length = 20
        self.display_mode = 'basic'  # 'basic' or 'detailed'
        self.running = True
        self.scanner = None
        self.log_file = 'ble_scan.log'
        self.last_log_time = 0
        self.log_interval = 10  # Log every 10 seconds
        self.scan_count = 0
        self.selected_device_address = None  # Track device by address instead of index
        self.view_mode = 'list'  # 'list' or 'detail'

    def db_to_bar(self, rssi):
        # Convert RSSI to a visual bar (stronger signals will have more bars)
        # RSSI typically ranges from -100 (weak) to -30 (strong)
        strength = min(100, max(0, (100 + rssi)))  # Convert to 0-100 scale
        filled_length = math.ceil((strength / 100.0) * self.bar_length)
        bar = '█' * filled_length + '░' * (self.bar_length - filled_length)
        return bar

    def get_device_appearance(self, metadata):
        if not metadata or 'appearance' not in metadata:
            return 'Unknown'
        # Common BLE appearance values
        appearances = {
            0: 'Unknown',
            64: 'Generic Phone',
            128: 'Generic Computer',
            192: 'Generic Watch',
            193: 'Sports Watch',
            256: 'Generic Tag',
            832: 'Generic Heart Rate Sensor',
            960: 'Generic Blood Pressure',
        }
        return appearances.get(metadata.get('appearance'), 'Unknown')

    def format_services(self, metadata):
        if not metadata or 'uuids' not in metadata:
            return 'No services'
        return ', '.join(str(uuid)[:8] for uuid in metadata.get('uuids', []))[:40]

    def format_manufacturer(self, metadata):
        if not metadata or 'manufacturer_data' not in metadata:
            return 'No manufacturer data'
        # Format first manufacturer ID and data
        mfg_data = list(metadata['manufacturer_data'].items())
        if not mfg_data:
            return 'No manufacturer data'
        mfg_id, data = mfg_data[0]
        return f'ID: {mfg_id:04x}, Data: {data.hex()[:20]}'

    def check_keyboard(self):
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            if key == '\x1b':  # Arrow key prefix
                next_two = sys.stdin.read(2)
                sorted_devices = sorted(self.devices.items(), 
                                     key=lambda x: x[1]['rssi'], 
                                     reverse=True)
                
                # Find current index based on selected address
                current_index = 0
                if self.selected_device_address:
                    for idx, (addr, _) in enumerate(sorted_devices):
                        if addr == self.selected_device_address:
                            current_index = idx
                            break
                
                if next_two == '[A':  # Up arrow
                    new_index = max(0, current_index - 1)
                    if sorted_devices:
                        self.selected_device_address = sorted_devices[new_index][0]
                elif next_two == '[B':  # Down arrow
                    new_index = min(len(sorted_devices) - 1, current_index + 1)
                    if sorted_devices:
                        self.selected_device_address = sorted_devices[new_index][0]
            
            elif key in ['\r', '\n']:  # Enter key (handle both CR and LF)
                if self.selected_device_address and self.selected_device_address in self.devices:
                    self.view_mode = 'detail' if self.view_mode == 'list' else 'list'
            
            elif key == 'q':  # Back to list view
                self.view_mode = 'list'
            elif key == '\x03':  # Ctrl+C
                self.running = False
                return True
        return False

    def log_devices(self):
        """Log device information to CSV file"""
        current_time = time.time()
        if current_time - self.last_log_time >= self.log_interval:
            utc_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            self.scan_count += 1
            
            # Write to log file
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                # Write header if file is empty
                if f.tell() == 0:
                    writer.writerow(['Block', 'Timestamp', 'Device Name', 'Address', 'RSSI'])
                    writer.writerow(['BEGIN SCAN BLOCK 1', '', '', '', ''])
                else:
                    # Write block delimiter
                    writer.writerow([f'BEGIN SCAN BLOCK {self.scan_count}', '', '', '', ''])
                
                # Write data for each device
                for device in self.devices.values():
                    writer.writerow([
                        '',  # Empty block column
                        utc_time,
                        device['name'],
                        device['address'],
                        device['rssi']
                    ])
                
                # Write end block delimiter
                writer.writerow([f'END SCAN BLOCK {self.scan_count}', '', '', '', ''])
                writer.writerow(['', '', '', '', ''])  # Empty line between blocks
            
            self.last_log_time = current_time

    async def scan_devices(self):
        try:
            self.scan_count = 0
            self.scanner = BleakScanner()
            
            with self.term.fullscreen(), self.term.hidden_cursor(), self.term.cbreak():
                while self.running:
                    try:
                        if self.check_keyboard():
                            break

                        # Start scanning
                        await self.scanner.start()
                        await asyncio.sleep(1.0)
                        await self.scanner.stop()

                        devices = self.scanner.discovered_devices
                        current_time = time.time()
                        
                        # Update devices dictionary
                        for device in devices:
                            self.devices[device.address] = {
                                'name': device.name or 'Unknown',
                                'address': device.address,
                                'rssi': device.rssi,
                                'metadata': device.metadata,
                                'appearance': self.get_device_appearance(device.metadata),
                                'services': self.format_services(device.metadata),
                                'manufacturer': self.format_manufacturer(device.metadata),
                                'last_seen': current_time
                            }

                        # Log devices
                        self.log_devices()

                        # Remove old devices
                        self.devices = {k: v for k, v in self.devices.items() 
                                      if current_time - v['last_seen'] <= 10}

                        # Clear screen and print header
                        print(self.term.home + self.term.clear)
                        print(f"BLE Device Scanner - Press Ctrl+C to exit | Arrow keys to navigate | Enter to toggle details | 'q' for list view")
                        print(f"Logging to: {self.log_file}")
                        print("-" * self.term.width)

                        # Sort devices by signal strength
                        sorted_devices = sorted(self.devices.items(), 
                                             key=lambda x: x[1]['rssi'], 
                                             reverse=True)

                        # Set initial selection if needed
                        if (not self.selected_device_address or 
                            self.selected_device_address not in self.devices) and sorted_devices:
                            self.selected_device_address = sorted_devices[0][0]

                        if self.view_mode == 'list':
                            self.display_list_view(sorted_devices)
                        else:
                            self.display_detail_view()

                        sys.stdout.flush()
                        await asyncio.sleep(0.1)

                    except Exception as e:
                        print(f"Error during scan: {e}")
                        await asyncio.sleep(1)
                        continue

        except KeyboardInterrupt:
            pass
        finally:
            if self.scanner:
                await self.scanner.stop()
            print("\nScanning stopped by user")

    def display_list_view(self, sorted_devices):
        print(f"{'Device Name':<{self.max_name_length}} | {'Address':<{self.max_addr_length}} | {'Signal':<{self.bar_length}} | RSSI")
        print("-" * self.term.width)
        
        for addr, device in sorted_devices:
            name = device['name'][:self.max_name_length]
            name = f"{name:<{self.max_name_length}}"
            address = f"{device['address']:<{self.max_addr_length}}"
            bar = self.db_to_bar(device['rssi'])
            rssi = device['rssi']
            
            if addr == self.selected_device_address:
                print(self.term.reverse(
                    f"{name} | {address} | {bar} | {rssi} dBm"
                ))
            else:
                print(f"{name} | {address} | {bar} | {rssi} dBm")

    def display_detail_view(self):
        if self.selected_device_address in self.devices:
            device = self.devices[self.selected_device_address]
            print(f"\nDetailed View for Selected Device:")
            print("-" * self.term.width)
            print(f"Device Name: {device['name']}")
            print(f"Address: {device['address']}")
            print(f"Signal Strength: {self.db_to_bar(device['rssi'])} ({device['rssi']} dBm)")
            print(f"Device Type: {device['appearance']}")
            print(f"Services: {device['services']}")
            print(f"Manufacturer: {device['manufacturer']}")
            print(f"\nPress 'q' to return to list view")

async def main():
    scanner = BLEScanner()
    await scanner.scan_devices()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass