# Audio Control Web Interface

A web-based interface for controlling audio devices (USB, built-in, and Bluetooth) on your Linux system via Docker.

## Features

- 🎵 Control active audio device volume in real-time
- 🔄 Switch between audio devices (USB, built-in speakers/headphones)
- 📱 Pair and connect Bluetooth audio devices
- 🔍 Scan for nearby Bluetooth devices
- 🌐 Access from any device on your local network

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- PulseAudio running on the host system
- Bluetooth adapter (for Bluetooth features)

### Installation

1. Create a directory for the project:
```bash
mkdir ~/audio-control
cd ~/audio-control
```

2. Create the following files in this directory:
   - `docker-compose.yml`
   - `Dockerfile`
   - `requirements.txt`
   - `main.py`
   - `static/index.html` (create the `static` directory first)

3. Build and start the container:
```bash
docker-compose up -d
```

4. Access the web interface:
   - From the host: `http://localhost:8080`
   - From another device: `http://YOUR_SERVER_IP:8080`

## Project Structure

```
audio-control/
├── docker-compose.yml       # Docker compose configuration
├── Dockerfile              # Container image definition
├── requirements.txt        # Python dependencies
├── main.py                # FastAPI backend server
└── static/
    └── index.html         # Web frontend
```

## Configuration

### PulseAudio User ID

The default configuration assumes PulseAudio is running as user ID 1000. If your user ID is different:

1. Check your user ID: `id -u`
2. Update the volume mount in `docker-compose.yml`:
```yaml
- /run/user/YOUR_USER_ID/pulse:/run/user/1000/pulse:rw
```

### Bluetooth Permissions

The container runs in privileged mode to access Bluetooth hardware. If you want to restrict this:

1. Add your user to the `bluetooth` group on the host:
```bash
sudo usermod -a -G bluetooth $USER
```

2. Restart your session for changes to take effect

## Troubleshooting

### No audio devices showing

**Check PulseAudio is running:**
```bash
pactl info
```

**Check the volume mount:**
```bash
ls -la /run/user/$(id -u)/pulse/
```

**View container logs:**
```bash
docker-compose logs audio-control
```

### Bluetooth not working

**Check Bluetooth service:**
```bash
sudo systemctl status bluetooth
```

**Verify Bluetooth is enabled:**
```bash
bluetoothctl show
```

**Check container has access:**
```bash
docker-compose exec audio-control bluetoothctl list
```

### Volume control not working

**Test PulseAudio from container:**
```bash
docker-compose exec audio-control pactl list sinks short
```

**Check environment variables:**
```bash
docker-compose exec audio-control env | grep PULSE
```

## Using on OpenMediaVault (OMV)

1. Copy all files to your OMV server (via SSH or shared folder)
2. In OMV web interface, go to: **Services → Compose → Files**
3. Click "Add" or "+" to create a new compose file
4. Paste the contents of `docker-compose.yml`
5. Save and deploy the stack

## API Endpoints

The backend provides the following REST API endpoints:

- `GET /api/devices` - List all audio devices
- `GET /api/active` - Get currently active device
- `POST /api/volume` - Set volume (body: `{"volume": 75}`)
- `POST /api/device/select` - Select audio device (body: `{"device_name": "..."}`)
- `POST /api/bluetooth/scan` - Scan for Bluetooth devices
- `POST /api/bluetooth/pair` - Pair with device (body: `{"mac": "...", "name": "..."}`)
- `POST /api/bluetooth/connect` - Connect to paired device (body: `{"mac": "...", "name": "..."}`)

## Security Notes

- This service should only be exposed on a trusted local network
- The container requires privileged access for Bluetooth functionality
- No authentication is currently implemented

## Future Enhancements

- Add authentication/authorization
- Support for multiple PulseAudio servers
- Device profiles and presets
- Audio stream routing
- EQ controls

## License

MIT License - Feel free to modify and use as needed!