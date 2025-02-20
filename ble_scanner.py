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
        self.log_interval = 30  # Increased log interval to reduce I/O
        self.scan_count = 0
        self.selected_device_address = None  # Track device by address instead of index
        self.view_mode = 'list'  # 'list' or 'detail'
        self.last_screen_update = 0
        self.screen_update_interval = 0.2  # Screen refresh rate in seconds
        self.device_timeout = 300  # Keep devices for 5 minutes instead of removing them
        self.inactive_threshold = 15  # Consider device inactive after 15 seconds

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
            # Perform logging in a way that minimizes I/O operations
            log_entries = []
            utc_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            self.scan_count += 1
            
            log_entries.append([f'BEGIN SCAN BLOCK {self.scan_count}', '', '', '', ''])
            
            # Prepare all device entries
            for device in self.devices.values():
                log_entries.append([
                    '',  # Empty block column
                    utc_time,
                    device['name'],
                    device['address'],
                    device['rssi']
                ])
            
            log_entries.append([f'END SCAN BLOCK {self.scan_count}', '', '', '', ''])
            log_entries.append(['', '', '', '', ''])  # Empty line between blocks
            
            # Single file operation for all entries
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                # Write header if file is empty
                if f.tell() == 0:
                    writer.writerow(['Block', 'Timestamp', 'Device Name', 'Address', 'RSSI'])
                writer.writerows(log_entries)
            
            self.last_log_time = current_time

    def get_device_age(self, last_seen):
        """Convert last seen timestamp to human readable format"""
        age = time.time() - last_seen
        if age < 60:
            return f"{int(age)}s"
        elif age < 3600:
            return f"{int(age/60)}m"
        else:
            return f"{int(age/3600)}h"

    async def scan_devices(self):
        try:
            self.scan_count = 0
            self.scanner = BleakScanner()
            await self.scanner.start()  # Start scanner once and keep it running
            
            with self.term.fullscreen(), self.term.hidden_cursor(), self.term.cbreak():
                while self.running:
                    try:
                        if self.check_keyboard():
                            break

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

                        # Log devices less frequently
                        self.log_devices()

                        # Remove very old devices
                        self.devices = {k: v for k, v in self.devices.items() 
                                      if current_time - v['last_seen'] <= self.device_timeout}

                        # Update screen at controlled intervals
                        if current_time - self.last_screen_update >= self.screen_update_interval:
                            # Clear screen and print header
                            print(self.term.home + self.term.clear)
                            print(f"BLE Device Scanner - Press Ctrl+C to exit | Arrow keys to navigate | Enter to toggle details | 'q' for list view")
                            print(f"Logging to: {self.log_file}")
                            print("-" * self.term.width)

                            # Sort devices: active ones by signal strength, inactive ones by last seen
                            current_time = time.time()
                            active_devices = []
                            inactive_devices = []
                            
                            for addr, device in self.devices.items():
                                device_age = current_time - device['last_seen']
                                if device_age <= self.inactive_threshold:
                                    active_devices.append((addr, device))
                                else:
                                    inactive_devices.append((addr, device))
                            
                            # Sort active devices by signal strength
                            active_devices.sort(key=lambda x: x[1]['rssi'], reverse=True)
                            # Sort inactive devices by last seen time (most recent first)
                            inactive_devices.sort(key=lambda x: x[1]['last_seen'], reverse=True)
                            
                            sorted_devices = active_devices + inactive_devices

                            # Set initial selection if needed
                            if (not self.selected_device_address or 
                                self.selected_device_address not in self.devices) and sorted_devices:
                                self.selected_device_address = sorted_devices[0][0]

                            if self.view_mode == 'list':
                                self.display_list_view(sorted_devices, current_time)
                            else:
                                self.display_detail_view(current_time)

                            sys.stdout.flush()
                            self.last_screen_update = current_time

                        # Shorter sleep time for more responsive controls
                        await asyncio.sleep(0.05)

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

    def display_list_view(self, sorted_devices, current_time):
        print(f"{'Device Name':<{self.max_name_length}} | {'Address':<{self.max_addr_length}} | {'Signal':<{self.bar_length}} | {'Status'}")
        print("-" * self.term.width)
        
        for addr, device in sorted_devices:
            name = device['name'][:self.max_name_length]
            name = f"{name:<{self.max_name_length}}"
            address = f"{device['address']:<{self.max_addr_length}}"
            device_age = current_time - device['last_seen']
            
            if device_age <= self.inactive_threshold:
                # Active device
                bar = self.db_to_bar(device['rssi'])
                status = f"{device['rssi']} dBm"
            else:
                # Inactive device
                bar = "." * self.bar_length
                status = f"Last seen {self.get_device_age(device['last_seen'])} ago"
            
            line = f"{name} | {address} | {bar} | {status}"
            if addr == self.selected_device_address:
                print(self.term.reverse(line))
            else:
                if device_age > self.inactive_threshold:
                    print(self.term.dim(line))
                else:
                    print(line)

    def display_detail_view(self, current_time):
        if self.selected_device_address in self.devices:
            device = self.devices[self.selected_device_address]
            device_age = current_time - device['last_seen']
            
            print(f"\nDetailed View for Selected Device:")
            print("-" * self.term.width)
            print(f"Device Name: {device['name']}")
            print(f"Address: {device['address']}")
            
            if device_age <= self.inactive_threshold:
                print(f"Signal Strength: {self.db_to_bar(device['rssi'])} ({device['rssi']} dBm)")
            else:
                print(f"Signal Strength: No current signal (Last seen {self.get_device_age(device['last_seen'])} ago)")
            
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