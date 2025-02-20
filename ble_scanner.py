#!/usr/bin/env python3

import asyncio
from bleak import BleakScanner
from blessed import Terminal
import math
import sys
import select
import time

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
        # Non-blocking keyboard input check
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            if key == 'd':
                self.display_mode = 'detailed' if self.display_mode == 'basic' else 'basic'
            elif key == '\x03':  # Ctrl+C
                self.running = False
                return True
        return False

    async def scan_devices(self):
        try:
            self.scanner = BleakScanner()
            with self.term.fullscreen(), self.term.hidden_cursor(), self.term.cbreak():
                while self.running:
                    try:
                        # Check for keyboard input
                        if self.check_keyboard():
                            break

                        # Start scanning
                        await self.scanner.start()
                        await asyncio.sleep(1.0)
                        await self.scanner.stop()
                        
                        # Get discovered devices
                        devices = self.scanner.discovered_devices
                        
                        # Update devices dictionary
                        current_time = time.time()
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

                        # Remove old devices
                        self.devices = {k: v for k, v in self.devices.items() 
                                      if current_time - v['last_seen'] <= 10}

                        # Clear screen and print header
                        print(self.term.home + self.term.clear)
                        print(f"BLE Device Scanner - Press Ctrl+C to exit | Press 'd' to toggle detail view")
                        print("-" * self.term.width)

                        # Sort devices by signal strength
                        sorted_devices = sorted(self.devices.items(), 
                                             key=lambda x: x[1]['rssi'], 
                                             reverse=True)

                        if self.display_mode == 'basic':
                            # Basic view
                            print(f"{'Device Name':<{self.max_name_length}} | {'Address':<{self.max_addr_length}} | {'Signal':<{self.bar_length}} | RSSI")
                            print("-" * self.term.width)
                            for addr, device in sorted_devices:
                                name = device['name'][:self.max_name_length]
                                name = f"{name:<{self.max_name_length}}"
                                address = f"{device['address']:<{self.max_addr_length}}"
                                bar = self.db_to_bar(device['rssi'])
                                rssi = device['rssi']
                                print(f"{name} | {address} | {bar} | {rssi} dBm")
                        else:
                            # Detailed view
                            for addr, device in sorted_devices:
                                print(f"\nDevice: {device['name']}")
                                print(f"Address: {device['address']}")
                                print(f"Signal: {self.db_to_bar(device['rssi'])} ({device['rssi']} dBm)")
                                print(f"Type: {device['appearance']}")
                                print(f"Services: {device['services']}")
                                print(f"Manufacturer: {device['manufacturer']}")
                                print("-" * self.term.width)

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

async def main():
    scanner = BLEScanner()
    await scanner.scan_devices()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass