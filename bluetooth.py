import subprocess
import re
import asyncio
from typing import List, Dict, Optional


def get_paired_bluetooth_devices() -> List[Dict[str, any]]:
    """Get all paired Bluetooth devices"""
    try:
        result = subprocess.run(
            ['bluetoothctl', 'devices', 'Paired'],
            capture_output=True,
            text=True,
            timeout=5
        )

        devices = []
        for line in result.stdout.split('\n'):
            if line.strip():
                match = re.match(r'Device\s+([0-9A-F:]+)\s+(.+)', line)
                if match:
                    mac, name = match.groups()
                    # Check if connected
                    is_connected = check_device_connected(mac)

                    devices.append({
                        'mac': mac,
                        'name': name,
                        'connected': is_connected
                    })

        return devices
    except Exception as e:
        print(f"Error getting Bluetooth devices: {e}")
        return []


def check_device_connected(mac: str) -> bool:
    """Check if a Bluetooth device is connected"""
    try:
        info_result = subprocess.run(
            ['bluetoothctl', 'info', mac],
            capture_output=True,
            text=True,
            timeout=5
        )
        return 'Connected: yes' in info_result.stdout
    except Exception as e:
        print(f"Error checking device connection: {e}")
        return False


async def scan_for_devices(duration: int = 15) -> List[Dict[str, str]]:
    """Scan for nearby Bluetooth devices"""
    try:
        print("Starting Bluetooth scan...")

        # Start scanning in background
        scan_proc = subprocess.Popen(
            ['bluetoothctl', 'scan', 'on'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for devices to be discovered
        print(f"Waiting {duration} seconds for device discovery...")
        await asyncio.sleep(duration)

        # Get the list of devices
        print("Getting device list...")
        result = subprocess.run(
            ['bluetoothctl', 'devices'],
            capture_output=True,
            text=True,
            timeout=5
        )

        print(f"Device list output:\n{result.stdout}")

        # Stop scanning
        print("Stopping scan...")
        subprocess.run(['bluetoothctl', 'scan', 'off'], timeout=2, capture_output=True)
        scan_proc.terminate()

        # Parse devices
        devices = []
        seen_macs = set()

        for line in result.stdout.split('\n'):
            line = line.strip()
            if line:
                # Format: Device XX:XX:XX:XX:XX:XX Device Name
                match = re.match(r'Device\s+([0-9A-F:]+)\s+(.+)', line, re.IGNORECASE)
                if match:
                    mac, name = match.groups()
                    mac = mac.upper()
                    if mac not in seen_macs:
                        seen_macs.add(mac)
                        devices.append({
                            'mac': mac,
                            'name': name.strip()
                        })
                        print(f"Found: {name.strip()} ({mac})")

        print(f"Total unique devices found: {len(devices)}")
        return devices

    except Exception as e:
        print(f"ERROR during Bluetooth scan: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


async def pair_device(mac: str, name: str) -> Dict[str, str]:
    """Pair with a Bluetooth device"""
    try:
        print(f"Attempting to pair with {name} ({mac})")

        # Pair
        print("Running bluetoothctl pair command...")
        pair_result = subprocess.run(
            ['bluetoothctl', 'pair', mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(f"Pair result - returncode: {pair_result.returncode}")
        print(f"Pair stdout: {pair_result.stdout}")
        print(f"Pair stderr: {pair_result.stderr}")

        if pair_result.returncode != 0 and 'AlreadyExists' not in pair_result.stderr:
            return {"status": "error", "message": f"Pairing failed: {pair_result.stderr}"}

        # Trust
        print("Running bluetoothctl trust command...")
        trust_result = subprocess.run(
            ['bluetoothctl', 'trust', mac],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"Trust result - returncode: {trust_result.returncode}")

        # Connect
        print("Running bluetoothctl connect command...")
        connect_result = subprocess.run(
            ['bluetoothctl', 'connect', mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(f"Connect result - returncode: {connect_result.returncode}")
        print(f"Connect stdout: {connect_result.stdout}")
        print(f"Connect stderr: {connect_result.stderr}")

        if connect_result.returncode == 0 or 'Connection successful' in connect_result.stdout:
            await asyncio.sleep(3)
            return {"status": "ok", "message": "Paired and connected successfully"}
        else:
            return {"status": "partial", "message": "Paired but connection failed"}

    except subprocess.TimeoutExpired as e:
        print(f"ERROR: Bluetooth operation timeout: {e}")
        return {"status": "error", "message": "Operation timeout"}
    except Exception as e:
        print(f"ERROR during Bluetooth pairing: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


async def connect_device(mac: str, name: str) -> Dict[str, str]:
    """Connect to a paired Bluetooth device"""
    try:
        print(f"Connecting to {name} ({mac})")
        result = subprocess.run(
            ['bluetoothctl', 'connect', mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(f"Connect result - returncode: {result.returncode}")
        print(f"Connect stdout: {result.stdout}")
        print(f"Connect stderr: {result.stderr}")

        if result.returncode == 0 or 'Connection successful' in result.stdout:
            # Wait for audio sink to appear
            await asyncio.sleep(3)
            return {"status": "ok", "message": "Connected successfully"}
        else:
            return {"status": "error", "message": f"Connection failed: {result.stderr}"}

    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Connection timeout"}
    except Exception as e:
        print(f"ERROR connecting to device: {type(e).__name__}: {str(e)}")
        return {"status": "error", "message": str(e)}