from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import audio
import bluetooth

app = FastAPI()


class VolumeUpdate(BaseModel):
    volume: float


class DeviceSelection(BaseModel):
    device_name: str


class BluetoothDevice(BaseModel):
    mac: str
    name: str


@app.get("/")
async def root():
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/devices")
async def get_devices():
    try:
        devices = audio.merge_audio_devices()
        return JSONResponse(content={"devices": devices})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/active")
async def get_active_device():
    try:
        active = audio.get_active_sink()
        if not active:
            raise HTTPException(status_code=404, detail="No active device found")
        return JSONResponse(content=active)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/volume")
async def set_volume(volume_update: VolumeUpdate):
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
    try:
        devices = await bluetooth.scan_for_devices(duration=15)
        return JSONResponse(content={"devices": devices})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/bluetooth/pair")
async def pair_bluetooth(device: BluetoothDevice):
    try:
        result = await bluetooth.pair_device(device.mac, device.name)
        if result["status"] == "ok":
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=500, detail=result["message"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
