import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import pulsectl
from typing import List, Optional
import subprocess
import re

app = FastAPI()


class VolumeUpdate(BaseModel):
    volume: float


class DeviceSelection(BaseModel):
    device_name: str


class BluetoothDevice(BaseModel):
    mac: str
    name: str


# PulseAudio helper functions
def get_pulse():
    """Get PulseAudio connection"""
    try:
        return pulsectl.Pulse('audio-control')
    except Exception as e:
        print(f"PulseAudio connection error: {e}")
        return None


def get_active_sink():
    """Get the currently active audio sink"""
    pulse = get_pulse()
    if not pulse:
        return None
    try:
        server_info = pulse.server_info()
        default_sink_name = server_info.default_sink_name
        sinks = pulse.sink_list()
        for sink in sinks:
            if sink.name == default_sink_name:
                return {
                    'name': sink.name,
                    'description': sink.description,
                    'volume': round(sink.volume.value_flat * 100),
                    'muted': sink.mute == 1
                }
    except Exception as e:
        print(f"ERROR getting active sink: {type(e).__name__}: {str(e)}")
    finally:
        pulse.close()
    return None


def get_all_sinks():
    """Get all available audio sinks"""
    pulse = get_pulse()
    if not pulse:
        return []

    try:
        server_info = pulse.server_info()
        default_sink_name = server_info.default_sink_name
        sinks = pulse.sink_list()

        result = []
        for sink in sinks:
            is_bluetooth = 'bluez' in sink.name.lower()
            is_active = sink.name == default_sink_name

            device_info = {
                'name': sink.name,
                'description': sink.description,
                'volume': round(sink.volume.value_flat * 100),
                'muted': sink.mute == 1,
                'is_active': is_active,
                'is_bluetooth': is_bluetooth,
                'state': 'connected'
            }
            result.append(device_info)

        return result
    except Exception as e:
        print(f"Error getting sinks: {e}")
        return []
    finally:
        pulse.close()


def get_paired_bluetooth_devices():
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
                    info_result = subprocess.run(
                        ['bluetoothctl', 'info', mac],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    is_connected = 'Connected: yes' in info_result.stdout

                    devices.append({
                        'mac': mac,
                        'name': name,
                        'connected': is_connected
                    })

        return devices
    except Exception as e:
        print(f"Error getting Bluetooth devices: {e}")
        return []


def merge_audio_devices():
    """Merge PulseAudio sinks with Bluetooth device info"""
    sinks = get_all_sinks()
    bt_devices = get_paired_bluetooth_devices()

    # Create a map of Bluetooth MACs that have audio sinks
    bt_with_sinks = set()
    for sink in sinks:
        if sink['is_bluetooth']:
            # Try to extract MAC from sink name
            mac_match = re.search(
                r'([0-9A-F]{2}[_:][0-9A-F]{2}[_:][0-9A-F]{2}[_:][0-9A-F]{2}[_:][0-9A-F]{2}[_:][0-9A-F]{2})',
                sink['name'], re.IGNORECASE)
            if mac_match:
                mac = mac_match.group(1).replace('_', ':').upper()
                bt_with_sinks.add(mac)

    # Add Bluetooth devices that are paired but don't have active sinks
    all_devices = list(sinks)
    for bt_dev in bt_devices:
        if bt_dev['mac'] not in bt_with_sinks:
            all_devices.append({
                'name': f"bt_{bt_dev['mac'].replace(':', '_')}",
                'description': bt_dev['name'],
                'volume': 0,
                'muted': False,
                'is_active': False,
                'is_bluetooth': True,
                'state': 'connected' if bt_dev['connected'] else 'offline',
                'mac': bt_dev['mac']
            })

    return all_devices


@app.get("/")
async def root():
    """Serve the main HTML page"""
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/devices")
async def get_devices():
    """Get all audio devices"""
    try:
        devices = merge_audio_devices()
        return JSONResponse(content={"devices": devices})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/active")
async def get_active_device():
    """Get the currently active device"""
    try:
        active = get_active_sink()
        if not active:
            raise HTTPException(status_code=404, detail="No active device found")
        return JSONResponse(content=active)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/volume")
async def set_volume(volume_update: VolumeUpdate):
    """Set volume for active device"""
    pulse = get_pulse()
    if not pulse:
        print("ERROR: Cannot connect to PulseAudio")
        raise HTTPException(status_code=500, detail="Cannot connect to PulseAudio")

    try:
        server_info = pulse.server_info()
        default_sink_name = server_info.default_sink_name
        print(f"Setting volume to {volume_update.volume}% for sink: {default_sink_name}")

        # Get the actual sink object
        sinks = pulse.sink_list()
        target_sink = None
        for sink in sinks:
            if sink.name == default_sink_name:
                target_sink = sink
                break

        if not target_sink:
            raise HTTPException(status_code=404, detail="Active sink not found")

        # Volume in pulsectl is 0.0 to 1.0 (or higher for boost)
        volume_val = volume_update.volume / 100.0
        pulse.volume_set_all_chans(target_sink, volume_val)

        print(f"Volume set successfully")
        return JSONResponse(content={"status": "ok", "volume": volume_update.volume})
    except Exception as e:
        print(f"ERROR setting volume: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pulse.close()


@app.post("/api/device/select")
async def select_device(selection: DeviceSelection):
    """Set a device as the default audio sink"""
    pulse = get_pulse()
    if not pulse:
        print("ERROR: Cannot connect to PulseAudio")
        raise HTTPException(status_code=500, detail="Cannot connect to PulseAudio")

    try:
        print(f"Selecting device: {selection.device_name}")
        pulse.sink_default_set(selection.device_name)

        # Move all existing streams to the new sink
        sink_inputs = pulse.sink_input_list()
        for sink_input in sink_inputs:
            try:
                pulse.sink_input_move(sink_input.index, selection.device_name)
                print(f"Moved stream {sink_input.index} to {selection.device_name}")
            except Exception as e:
                print(f"Could not move stream {sink_input.index}: {e}")

        print(f"Device selected successfully")
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        print(f"ERROR selecting device: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pulse.close()


@app.post("/api/bluetooth/connect")
async def connect_bluetooth(device: BluetoothDevice):
    """Connect to a Bluetooth device"""
    try:
        result = subprocess.run(
            ['bluetoothctl', 'connect', device.mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 or 'Connection successful' in result.stdout:
            # Wait a bit for audio sink to appear
            await asyncio.sleep(3)
            return JSONResponse(content={"status": "ok", "message": "Connected successfully"})
        else:
            raise HTTPException(status_code=500, detail=f"Connection failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Connection timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bluetooth/scan")
async def scan_bluetooth():
    """Scan for nearby Bluetooth devices"""
    try:
        print("Starting Bluetooth scan...")

        # Clear any stale devices from cache (optional, but helps)
        subprocess.run(['bluetoothctl', 'remove', '*'], capture_output=True, timeout=2)

        # Start scanning and capture output
        scan_proc = subprocess.Popen(
            ['bluetoothctl', '--', 'scan', 'on'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        discovered_devices = {}

        # Read scan output for 12 seconds
        print("Scanning for 12 seconds...")
        import time
        start_time = time.time()

        while time.time() - start_time < 12:
            if scan_proc.stdout:
                line = scan_proc.stdout.readline()
                if line:
                    # Look for "[NEW]" or "[CHG]" device lines
                    # Format: [NEW] Device XX:XX:XX:XX:XX:XX Device Name
                    if '[NEW] Device' in line or '[CHG] Device' in line:
                        match = re.search(r'Device\s+([0-9A-F:]+)\s+(.+)', line, re.IGNORECASE)
                        if match:
                            mac, name = match.groups()
                            mac = mac.upper()
                            name = name.strip()
                            if mac not in discovered_devices:
                                discovered_devices[mac] = name
                                print(f"Discovered: {name} ({mac})")
            await asyncio.sleep(0.1)

        # Stop scanning
        print("Stopping scan...")
        subprocess.run(['bluetoothctl', 'scan', 'off'], timeout=2)
        scan_proc.terminate()

        # Convert to list
        devices = [{'mac': mac, 'name': name} for mac, name in discovered_devices.items()]

        print(f"Total unique devices found: {len(devices)}")
        return JSONResponse(content={"devices": devices})

    except Exception as e:
        print(f"ERROR during Bluetooth scan: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bluetooth/pair")
async def pair_bluetooth(device: BluetoothDevice):
    """Pair with a Bluetooth device"""
    try:
        print(f"Attempting to pair with {device.name} ({device.mac})")

        # Pair
        print("Running bluetoothctl pair command...")
        pair_result = subprocess.run(
            ['bluetoothctl', 'pair', device.mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(f"Pair result - returncode: {pair_result.returncode}")
        print(f"Pair stdout: {pair_result.stdout}")
        print(f"Pair stderr: {pair_result.stderr}")

        if pair_result.returncode != 0 and 'AlreadyExists' not in pair_result.stderr:
            raise HTTPException(status_code=500, detail=f"Pairing failed: {pair_result.stderr}")

        # Trust
        print("Running bluetoothctl trust command...")
        trust_result = subprocess.run(
            ['bluetoothctl', 'trust', device.mac],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"Trust result - returncode: {trust_result.returncode}")

        # Connect
        print("Running bluetoothctl connect command...")
        connect_result = subprocess.run(
            ['bluetoothctl', 'connect', device.mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        print(f"Connect result - returncode: {connect_result.returncode}")
        print(f"Connect stdout: {connect_result.stdout}")
        print(f"Connect stderr: {connect_result.stderr}")

        if connect_result.returncode == 0 or 'Connection successful' in connect_result.stdout:
            await asyncio.sleep(3)
            return JSONResponse(content={"status": "ok", "message": "Paired and connected successfully"})
        else:
            return JSONResponse(content={"status": "partial", "message": "Paired but connection failed"})
    except subprocess.TimeoutExpired as e:
        print(f"ERROR: Bluetooth operation timeout: {e}")
        raise HTTPException(status_code=500, detail="Operation timeout")
    except Exception as e:
        print(f"ERROR during Bluetooth pairing: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)