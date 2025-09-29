import asyncio
import subprocess
import re


async def connect_device(mac, name):
    """Connect to a Bluetooth device"""
    try:
        result = subprocess.run(
            ['bluetoothctl', 'connect', mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 or 'Connection successful' in result.stdout:
            await asyncio.sleep(3)
            return {"status": "ok", "message": "Connected successfully"}
        else:
            return {"status": "error", "message": f"Connection failed: {result.stderr}"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Connection timeout"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def scan_for_devices(duration=15):
    """Scan for nearby Bluetooth devices"""
    try:
        scan_proc = subprocess.Popen(
            ['bluetoothctl', 'scan', 'on'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        await asyncio.sleep(duration)

        result = subprocess.run(
            ['bluetoothctl', 'devices'],
            capture_output=True,
            text=True,
            timeout=5
        )

        subprocess.run(['bluetoothctl', 'scan', 'off'], timeout=2, capture_output=True)
        scan_proc.terminate()

        devices = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line:
                match = re.match(r'Device\s+([0-9A-F:]+)\s+(.+)', line, re.IGNORECASE)
                if match:
                    mac, name = match.groups()
                    devices.append({
                        'mac': mac,
                        'name': name.strip()
                    })
        return devices
    except Exception as e:
        return []


async def pair_device(mac, name):
    """Pair with a Bluetooth device"""
    try:
        pair_result = subprocess.run(
            ['bluetoothctl', 'pair', mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        if pair_result.returncode != 0 and 'AlreadyExists' not in pair_result.stderr:
            return {"status": "error", "message": f"Pairing failed: {pair_result.stderr}"}

        subprocess.run(['bluetoothctl', 'trust', mac], capture_output=True, text=True, timeout=5)

        connect_result = subprocess.run(
            ['bluetoothctl', 'connect', mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        if connect_result.returncode == 0 or 'Connection successful' in connect_result.stdout:
            await asyncio.sleep(3)
            return {"status": "ok", "message": "Paired and connected successfully"}
        else:
            return {"status": "partial", "message": "Paired but connection failed"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Operation timeout"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
