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

        # Volume in pulsectl is 0.0 to 1.0 (or higher for boost)
        volume_val = volume_update.volume / 100.0
        pulse.volume_set_all_chans(default_sink_name, volume_val)

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
        raise HTTPException(status_code=500, detail="Cannot connect to PulseAudio")

    try:
        pulse.sink_default_set(selection.device_name)

        # Move all existing streams to the new sink
        sink_inputs = pulse.sink_input_list()
        for sink_input in sink_inputs:
            try:
                pulse.sink_input_move(sink_input.index, selection.device_name)
            except:
                pass  # Some streams might not be movable

        return JSONResponse(content={"status": "ok"})
    except Exception as e:
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
        # Start scanning
        subprocess.run(['bluetoothctl', 'scan', 'on'], timeout=1)

        # Wait for devices to appear
        await asyncio.sleep(10)

        # Stop scanning
        subprocess.run(['bluetoothctl', 'scan', 'off'], timeout=1)

        # Get discovered devices
        result = subprocess.run(
            ['bluetoothctl', 'devices'],
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
                    devices.append({
                        'mac': mac,
                        'name': name
                    })

        return JSONResponse(content={"devices": devices})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bluetooth/pair")
async def pair_bluetooth(device: BluetoothDevice):
    """Pair with a Bluetooth device"""
    try:
        # Pair
        pair_result = subprocess.run(
            ['bluetoothctl', 'pair', device.mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        if pair_result.returncode != 0 and 'AlreadyExists' not in pair_result.stderr:
            raise HTTPException(status_code=500, detail=f"Pairing failed: {pair_result.stderr}")

        # Trust
        subprocess.run(['bluetoothctl', 'trust', device.mac], timeout=5)

        # Connect
        connect_result = subprocess.run(
            ['bluetoothctl', 'connect', device.mac],
            capture_output=True,
            text=True,
            timeout=30
        )

        if connect_result.returncode == 0 or 'Connection successful' in connect_result.stdout:
            await asyncio.sleep(3)
            return JSONResponse(content={"status": "ok", "message": "Paired and connected successfully"})
        else:
            return JSONResponse(content={"status": "partial", "message": "Paired but connection failed"})
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Operation timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)