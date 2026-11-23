"""Provision the experimental direct firmware locally over USB, without a file."""
import argparse
import getpass
import json
from pathlib import Path
import time

import serial
from serial.tools import list_ports
from private_config import ConfigError, load_keys


def wait_for(device, responses, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = device.readline().strip()
        # Never print arbitrary serial output: it can contain private data.
        if line in responses:
            return line
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', required=True)
    parser.add_argument('--serial', required=True, help='USB serial from device discovery')
    parser.add_argument('--env', default=str(Path(__file__).resolve().parents[1] / '.env'))
    args = parser.parse_args()
    try:
        keys = load_keys(args.env)
    except ConfigError as e:
        raise SystemExit(str(e)) from None
    matches = [p for p in list_ports.comports() if p.device == args.port and
               (p.serial_number or '').lower() == args.serial.lower() and
               p.vid == 0x303a and p.pid == 0x1001]
    if len(matches) != 1:
        raise SystemExit('The selected USB port and serial do not match the ESP32-S3.')
    try:
        device = serial.Serial(port=None, baudrate=115200, timeout=0.5, write_timeout=5)
        device.port = args.port
        device.dtr = False
        device.rts = False
        with device:
            device.reset_input_buffer()
            device.write(b'{"command":"direct_status"}\n')
            device.flush()
            state = wait_for(device, {b'DIRECT_SETUP_READY', b'DIRECT_SETUP_INACTIVE'}, 5)
            if state != b'DIRECT_SETUP_READY':
                raise SystemExit('Direct USB setup is not active. Hold A for 10 seconds and retry.')
            payload = {'command': 'configure_direct', 'ssid': input('2.4 GHz Wi-Fi name: '),
                       'password': getpass.getpass('Wi-Fi password: '),
                       'venice_key': keys['VENICE_API_KEY'],
                       'surplus_key': keys['SURPLUS_API_KEY']}
            encoded = (json.dumps(payload, ensure_ascii=False) + '\n').encode('utf-8')
            if len(encoded) > 2048:
                raise SystemExit('Configuration exceeds the device limit.')
            device.write(encoded)
            device.flush()
            result = wait_for(device, {b'DIRECT_CONFIG_SAVED', b'DIRECT_CONFIG_INVALID'}, 15)
            if result != b'DIRECT_CONFIG_SAVED':
                raise SystemExit('Configuration was rejected or not acknowledged; check the device before retrying.')
            print('Configuration saved on device.')
    except serial.SerialException:
        raise SystemExit('Could not use the USB serial port; close other serial monitors and retry.')


if __name__ == '__main__':
    main()
