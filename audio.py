import pulsectl
import subprocess
import re


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

    bt_with_sinks = set()
    for sink in sinks:
        if sink['is_bluetooth']:
            mac_match = re.search(
                r'([0-9A-F]{2}[_:][0-9A-F]{2}[_:][0-9A-F]{2}[_:][0-9A-F]{2}[_:][0-9A-F]{2}[_:][0-9A-F]{2})',
                sink['name'], re.IGNORECASE
            )
            if mac_match:
                mac = mac_match.group(1).replace('_', ':').upper()
                bt_with_sinks.add(mac)

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
