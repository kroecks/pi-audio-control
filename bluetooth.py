import asyncio
import subprocess
import re
import os

BLUETOOTH_MAC_FILE = os.path.expanduser("~/.bluetooth_mac")

def run_cmd(cmd, timeout=10):
    """Run a shell command and return (stdout, stderr, rc)."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Timeout expired", 1


async def scan_for_devices(duration=15):
    """Scan for nearby Bluetooth devices and return a list of dicts {mac, name}."""
    run_cmd(['bluetoothctl', 'power', 'on'])
    scan_proc = subprocess.Popen(['bluetoothctl', 'scan', 'on'],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)

    await asyncio.sleep(duration)

    stdout, _, _ = run_cmd(['bluetoothctl', 'devices'], timeout=5)
    run_cmd(['bluetoothctl', 'scan', 'off'], timeout=2)
    scan_proc.terminate()

    devices = []
    for line in stdout.splitlines():
        match = re.match(r'Device\s+([0-9A-F:]{17})\s+(.+)', line, re.IGNORECASE)
        if match:
            mac, name = match.groups()
            devices.append({'mac': mac, 'name': name.strip()})
    return devices


async def pair_device(mac, name):
    """Pair, trust, and connect to a Bluetooth device."""
    run_cmd(['bluetoothctl', 'power', 'on'])

    out, err, rc = run_cmd(['bluetoothctl', 'pair', mac], timeout=30)
    if rc != 0 and "AlreadyExists" not in err:
        return {"status": "error", "message": f"Pairing failed: {err}"}

    run_cmd(['bluetoothctl', 'trust', mac], timeout=5)

    out, _, rc = run_cmd(['bluetoothctl', 'connect', mac], timeout=30)
    if rc == 0 or "Connection successful" in out:
        with open(BLUETOOTH_MAC_FILE, "w") as f:
            f.write(mac + "\n")
        return {"status": "ok", "message": f"Paired and connected to {mac}"}
    else:
        return {"status": "partial", "message": "Paired but connection failed"}


async def connect_device(mac, name):
    """Connect to an already paired device."""
    run_cmd(['bluetoothctl', 'power', 'on'])

    out, _, rc = run_cmd(['bluetoothctl', 'connect', mac], timeout=30)
    if rc == 0 or "Connection successful" in out:
        return {"status": "ok", "message": f"Connected to {mac}"}
    else:
        return {"status": "error", "message": f"Failed to connect to {mac}"}
