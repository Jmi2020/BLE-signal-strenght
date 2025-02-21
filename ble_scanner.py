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
        self.discovery_times = {}  # Track when devices are first discovered
        self.sort_mode = 'discovery'  # 'discovery' or 'signal'
        self.status_width = 30  # Width for the status column
        self.header_height = 5  # Height of the fixed header (title + info + column headers + separator)
        self.scroll_offset = 0  # Track scrolling position
        self.visible_lines = 0  # Track number of visible lines

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

    def sort_devices(self, devices, current_time):
        """Sort devices based on current sort mode and group by activity"""
        all_devices = sorted(devices.items(),
                           key=lambda x: (x[1]['discovery_time'] if self.sort_mode == 'discovery' 
                                        else (-x[1]['rssi'] if current_time - x[1]['last_seen'] <= self.inactive_threshold 
                                             else float('-inf'))))
        
        active_devices = []
        inactive_devices = []
        
        for addr, device in all_devices:
            device_age = current_time - device['last_seen']
            if device_age <= self.inactive_threshold:
                active_devices.append((addr, device))
            else:
                inactive_devices.append((addr, device))
        
        return active_devices, inactive_devices

    def check_keyboard(self):
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            if key == '\x1b':  # Arrow key prefix
                next_two = sys.stdin.read(2)
                current_time = time.time()
                active_devices, inactive_devices = self.sort_devices(self.devices, current_time)
                sorted_devices = active_devices + inactive_devices
                
                # Calculate content height
                content_height = self.term.height - self.header_height
                
                if next_two == '[A':  # Up arrow
                    if self.selected_device_address:
                        current_index = next((i for i, (addr, _) in enumerate(sorted_devices) 
                                           if addr == self.selected_device_address), 0)
                        new_index = max(0, current_index - 1)
                        self.selected_device_address = sorted_devices[new_index][0]
                        
                        # Adjust scroll if selection would be off screen
                        if new_index < self.scroll_offset:
                            self.scroll_offset = new_index
                
                elif next_two == '[B':  # Down arrow
                    if sorted_devices:
                        current_index = next((i for i, (addr, _) in enumerate(sorted_devices) 
                                           if addr == self.selected_device_address), 0)
                        new_index = min(len(sorted_devices) - 1, current_index + 1)
                        self.selected_device_address = sorted_devices[new_index][0]
                        
                        # Adjust scroll if selection would be off screen
                        if new_index >= self.scroll_offset + content_height:
                            self.scroll_offset = max(0, new_index - content_height + 1)
                
                elif next_two == '[5':  # Page Up
                    sys.stdin.read(1)  # Consume trailing ~
                    self.scroll_offset = max(0, self.scroll_offset - content_height)
                    if sorted_devices:
                        visible_start = self.scroll_offset
                        self.selected_device_address = sorted_devices[visible_start][0]
                
                elif next_two == '[6':  # Page Down
                    sys.stdin.read(1)  # Consume trailing ~
                    max_scroll = max(0, len(sorted_devices) - content_height)
                    self.scroll_offset = min(max_scroll, self.scroll_offset + content_height)
                    if sorted_devices:
                        visible_start = min(self.scroll_offset, len(sorted_devices) - 1)
                        self.selected_device_address = sorted_devices[visible_start][0]
            
            elif key in ['\r', '\n']:  # Enter key
                if self.selected_device_address and self.selected_device_address in self.devices:
                    self.view_mode = 'detail' if self.view_mode == 'list' else 'list'
            elif key == 's':  # Toggle sort mode
                self.sort_mode = 'signal' if self.sort_mode == 'discovery' else 'discovery'
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
            await self.scanner.start()
            self.scroll_offset = 0  # Initialize scroll position
            
            with self.term.fullscreen(), self.term.hidden_cursor(), self.term.cbreak():
                while self.running:
                    try:
                        if self.check_keyboard():
                            break

                        devices = self.scanner.discovered_devices
                        current_time = time.time()
                        
                        # Update devices dictionary without affecting scroll position
                        for device in devices:
                            if device.address not in self.discovery_times:
                                self.discovery_times[device.address] = current_time
                            
                            self.devices[device.address] = {
                                'name': device.name or 'Unknown',
                                'address': device.address,
                                'rssi': device.rssi,
                                'metadata': device.metadata,
                                'appearance': self.get_device_appearance(device.metadata),
                                'services': self.format_services(device.metadata),
                                'manufacturer': self.format_manufacturer(device.metadata),
                                'last_seen': current_time,
                                'discovery_time': self.discovery_times[device.address]
                            }

                        # Log devices less frequently
                        self.log_devices()

                        # Remove very old devices while preserving scroll position
                        current_devices = {k: v for k, v in self.devices.items() 
                                        if current_time - v['last_seen'] <= self.device_timeout}
                        removed_count = len(self.devices) - len(current_devices)
                        if removed_count > 0:
                            # Adjust scroll offset if devices were removed above current position
                            self.scroll_offset = max(0, self.scroll_offset - removed_count)
                        
                        self.discovery_times = {k: v for k, v in self.discovery_times.items()
                                              if k in current_devices}
                        self.devices = current_devices

                        # Sort devices for display
                        active_devices, inactive_devices = self.sort_devices(self.devices, current_time)
                        sorted_devices = active_devices + inactive_devices

                        # Update screen at controlled intervals
                        if current_time - self.last_screen_update >= self.screen_update_interval:
                            if self.view_mode == 'list':
                                self.display_list_view(sorted_devices, current_time)
                            else:
                                print(self.term.home + self.term.clear)
                                self.display_detail_view(current_time)

                            sys.stdout.flush()
                            self.last_screen_update = current_time

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
            print(self.term.exit_fullscreen())
            print(self.term.normal_cursor())
            print(self.term.change_scroll_region(0, self.term.height))
            print("\nScanning stopped by user")

    def display_list_view(self, sorted_devices, current_time):
        active_devices, inactive_devices = self.sort_devices(self.devices, current_time)
        total_active = len(active_devices)
        total_inactive = len(inactive_devices)
        
        # Calculate available display space
        content_height = self.term.height - self.header_height
        
        # Clear screen
        print(self.term.home + self.term.clear)
        
        # Fixed header section (always visible)
        with self.term.location(0, 0):
            print(self.term.clear_eos + f"BLE Device Scanner - Press Ctrl+C to exit | ↑/↓ navigate | PgUp/PgDn scroll | Home/End first/last | Enter toggle details | 's' sort ({self.sort_mode})")
            print(f"Logging to: {self.log_file}")
            print("-" * self.term.width)
            
            address_header = "ADDRESS" + " " * 11
            print(f"{'Device Name':<{self.max_name_length}} | {address_header:<{self.max_addr_length}} | {'Signal':<{self.bar_length}} | {'Status':<{self.status_width}}")
            print("-" * self.term.width)

        # Set up scrolling region below the header
        print(self.term.hide_cursor())
        print(self.term.change_scroll_region(self.header_height, self.term.height))
        print(self.term.move(self.header_height, 0))
        
        # Prepare all lines that will be displayed
        display_lines = []
        
        if active_devices:
            display_lines.append(f"\nActive Devices ({total_active}):")
            for addr, device in active_devices:
                name = device['name'][:self.max_name_length]
                name = f"{name:<{self.max_name_length}}"
                address = f"{device['address']:<{self.max_addr_length}}"
                bar = self.db_to_bar(device['rssi'])
                status = f"{device['rssi']} dBm"
                status = f"{status:<{self.status_width}}"
                
                line = f"{name} | {address} | {bar} | {status}"
                if addr == self.selected_device_address:
                    line = self.term.reverse(line)
                display_lines.append(line)
        
        if inactive_devices:
            display_lines.append(f"\nInactive Devices ({total_inactive}):")
            for addr, device in inactive_devices:
                name = device['name'][:self.max_name_length]
                name = f"{name:<{self.max_name_length}}"
                address = f"{device['address']:<{self.max_addr_length}}"
                bar = "." * self.bar_length
                status = f"Last seen {self.get_device_age(device['last_seen'])} ago"
                status = f"{status:<{self.status_width}}"
                
                line = f"{name} | {address} | {bar} | {status}"
                if addr == self.selected_device_address:
                    line = self.term.reverse(line)
                else:
                    line = self.term.dim(line)
                display_lines.append(line)
        
        if not display_lines:
            display_lines.append("\nNo devices found")

        # Calculate valid scroll range
        max_scroll = max(0, len(display_lines) - content_height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
        
        # Display visible portion of the list
        visible_lines = display_lines[self.scroll_offset:self.scroll_offset + content_height]
        print("\n".join(visible_lines))
        
        # Reset scroll region
        print(self.term.change_scroll_region(0, self.term.height))

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