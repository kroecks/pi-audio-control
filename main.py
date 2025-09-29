from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import asyncio

# Import our modules
import audio
import bluetooth

app = FastAPI()


# Request models
class VolumeUpdate(BaseModel):
    volume: float


class DeviceSelection(BaseModel):
    device_name: str


class BluetoothDevice(BaseModel):
    mac: str
    name: str


@app.get("/")
async def root():
    """Serve the main HTML page"""
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/devices")
async def get_devices():
    """Get all audio devices"""
    try:
        devices = audio.merge_audio_devices()
        return JSONResponse(content={"devices": devices})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/active")
async def get_active_device():
    """Get the currently active device"""
    try:
        active = audio.get_active_sink()
        if not active:
            raise HTTPException(status_code=404, detail="No active device found")
        return JSONResponse(content=active)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/volume")
async def set_volume(volume_update: VolumeUpdate):
    """Set volume for active device"""
    try:
        success = audio.set_volume(volume_update.volume)
        if success:
            return JSONResponse(content={"status": "ok", "volume": volume_update.volume})
        else:
            raise HTTPException(status_code=500, detail="Failed to set volume")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/device/select")
async def select_device(selection: DeviceSelection):
    """Set a device as the default audio sink"""
    try:
        success = audio.select_device(selection.device_name)
        if success:
            return JSONResponse(content={"status": "ok"})
        else:
            raise HTTPException(status_code=500, detail="Failed to select device")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bluetooth/connect")
async def connect_bluetooth(device: BluetoothDevice):
    """Connect to a Bluetooth device"""
    try:
        result = await bluetooth.connect_device(device.mac, device.name)
        if result["status"] == "ok":
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=500, detail=result["message"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bluetooth/scan")
async def scan_bluetooth():
    """Scan for nearby Bluetooth devices"""
    try:
        devices = await bluetooth.scan_for_devices(duration=15)
        return JSONResponse(content={"devices": devices})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bluetooth/pair")
async def pair_bluetooth(device: BluetoothDevice):
    """Pair with a Bluetooth device"""
    try:
        result = await bluetooth.pair_device(device.mac, device.name)
        if result["status"] == "ok":
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=500, detail=result["message"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)run(
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