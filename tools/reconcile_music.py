"""Acknowledge a device music job only after checking its provider outcome."""
import argparse
import serial
from serial.tools import list_ports
from configure_direct import wait_for


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True)
    parser.add_argument('--serial',required=True)
    args=parser.parse_args()
    matches=[p for p in list_ports.comports() if p.device==args.port and
             (p.serial_number or '').lower()==args.serial.lower() and
             p.vid==0x303a and p.pid==0x1001]
    if len(matches)!=1:raise SystemExit('USB port and serial do not match the selected ESP32-S3.')
    print('First check Surplus for the previous job and its charges. Clearing the device state permits a new paid song.')
    if input('Type RECONCILED only after that check: ').strip()!='RECONCILED':
        raise SystemExit('Music state was not changed.')
    try:
        device=serial.Serial(port=None,baudrate=115200,timeout=0.5,write_timeout=5)
        device.port=args.port;device.dtr=False;device.rts=False
        with device:
            device.reset_input_buffer();device.write(b'{"command":"direct_status"}\n');device.flush()
            if wait_for(device,{b'DIRECT_SETUP_READY',b'DIRECT_SETUP_INACTIVE'},5)!=b'DIRECT_SETUP_READY':
                raise SystemExit('Hold A for 10 seconds to enter USB setup, then retry.')
            device.write(b'{"command":"music_reconciled"}\n');device.flush()
            result=wait_for(device,{b'DIRECT_MUSIC_RECONCILED',b'DIRECT_MUSIC_RECONCILE_FAILED'},5)
            if result!=b'DIRECT_MUSIC_RECONCILED':raise SystemExit('Music state was not acknowledged.')
            print('Music state acknowledged on the device.')
    except serial.SerialException:
        raise SystemExit('Could not use the USB serial port.') from None


if __name__=='__main__':main()
