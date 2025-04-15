import argparse
from dataclasses import dataclass
from typing import List, BinaryIO
from datetime import datetime, UTC
import binascii
import struct
import sys
import io
import string
import time
import json

def warn(*a):
    print('[WARN]', *a, file = sys.stderr)

def parse_(fmt, id, data):
    size     = struct.calcsize(fmt)
    trailing = len(data) % size
    if trailing:
        warn(f'{trailing} trailing bytes while parsing {id}')
        data = data[:len(data) - trailing]
    return [ r[0] for r in struct.iter_unpack(fmt, data) ]

parse_U8  = lambda v, *a: parse_('<B', 'U8', v)
parse_U16 = lambda v, *a: parse_('<H', 'U16', v)
parse_U32 = lambda v, *a: parse_('<L', 'U32', v)
parse_I8  = lambda v, *a: parse_('<b', 'I8', v)
parse_I16 = lambda v, *a: parse_('<h', 'I16', v)
parse_I32 = lambda v, *a: parse_('<l', 'I32', v)

def parse_TimeOfDay(v, *a):
    # STRUCT OF
    #   UNSIGNED28 ms,
    #   VOID4      reserved,
    #   UNSIGNED16 days
    EPOCH        = 441763200 # 1984-01-01T00:00:00Z
    millis, days = struct.unpack('<LH', v)
    timestamp    = EPOCH + int(millis / 1000) + days * 24 * 60 * 60
    return (timestamp, datetime.fromtimestamp(timestamp, UTC).isoformat())

def parse_Enum(v, key):
    obj = OBJECTS[key]
    v   = str(parse_U8(v)[0])
    return obj['values'][v]['description'] if v in obj['values'] else v

def parse_VisibleString(v, *a):
    try:
        v = v.decode('ascii')
    except:
        warn('unable to convert bytes to ASCII')
        return v
    # visible strings seem to be NUL-padded
    return v.split('\0', 1)[0]

# https://stackoverflow.com/a/75328573
def crc16modbus(data:str) -> int:
    crc = 0xFFFF
    for n in range(len(data)):
        crc ^= data[n]
        for i in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

OBJECTS = json.load(open('object-dictionary.json'))
FORMATS = {
    'U8':            parse_U8,
    'U16':           parse_U16,
    'U32':           parse_U32,
    'I8':            parse_I8,
    'I16':           parse_I16,
    'I32':           parse_I32,
    'TimeOfDay':     parse_TimeOfDay,
    'Enum':          parse_Enum,
    'VisibleString': parse_VisibleString,
}

@dataclass(eq = True, frozen = True)
class Message:
    frame:          bytes
    is_reply:       bool
    flags:          int
    payload_length: int
    unknowns:       bytes
    index:          str
    subindex:       bytes
    data:           bytes
    checksum:       bytes
    crc:            bytes
    payload:        bytes

    def __str__(self):
        payload_hex = ' '.join(f'{b:02X}' for b in self.payload)
        return (f"{'Reply  ' if self.is_reply else 'Request'} "
                f"flags={self.flags:08b} "
                f"length={self.payload_length:02} "
                f"unknowns={self.unknowns.hex()} "
                f"index={self.index} "
                f"subindex={self.subindex:02} "
                f"data={self.data.hex()} "
                f"checksum={self.checksum.hex()} "
                f"crc={self.crc:04x} "
                f"payload={payload_hex} "
                f"frame={self.frame.hex()}"
        )

    def checksum_valid(self) -> bool:
        return self.checksum == self.crc

    @staticmethod
    def from_frame(frame):
        try:
            payload = frame[8:]
            return Message(
                frame          = frame,
                is_reply       = frame[2] == 0x01,
                flags          = frame[3],
                payload_length = frame[4],
                unknowns       = frame[5:8],
                index          = payload[0:2].hex().upper(),
                subindex       = payload[2], # XXX =  is this actually the subindex?
                data           = payload[3:-2],
                checksum       = payload[-2:],
                crc            = crc16modbus(frame[1:-2]),
                payload        = payload
            )
        except Exception as e:
            print(f'\n[INVALID FRAME] {frame.hex()} ({e})', file = sys.stderr)
            return None

class MessageParser:
    def __init__(self, file: BinaryIO):
        self.file = file

    def read_bytes(self, count: int) -> bytes:
        data = self.file.read(count)
        if len(data) < count:
            raise EOFError(f"Expected {count} bytes, got {len(data)}")
        return data

    def next_message(self):
        data = bytes()
        while True:
            data += self.read_bytes(1)
            if data[-2:] == b'\x01\x00':
                # extract request/reply frame
                frame = data[-2:]                # header
                frame += self.read_bytes(1)      # message type
                frame += self.read_bytes(1)      # flags
                frame += self.read_bytes(1)      # payload length
                length = frame[-1:][0]
                frame += self.read_bytes(3)      # unknowns
                frame += self.read_bytes(length) # payload

                # create message from frame and emit it
                message = Message.from_frame(frame)
                if message:
                    yield message

                # spurious data
                data = data[:-2]
                if len(data):
                    print(f'[SPURIOUS DATA] {data.hex()}', file = sys.stderr)

                # start over
                data = bytes()

    def parse_all(self):
        for msg in self.next_message():
            print(msg)
            if msg.index in OBJECTS:
                obj   = OBJECTS[msg.index]
                fmt   = obj['type']
                value = msg.data
                print(f'OBJ[{msg.index}][{fmt}]', f'"{obj['desc']}"', end = ' ')
                if msg.is_reply:
                    if fmt in FORMATS:
                        try:
                            value = FORMATS[fmt](value, msg.index)
                            if 'gain' in obj:
                                value = [ v * obj['gain'] for v in value ]
                            if obj['is_array']:
                                # validate array size
                                max_allowed = obj.get('max_array_size', 1)
                                if len(value) > max_allowed:
                                    warn(f'array size larger than allowed (size={len(value)}, max allowed={max_allowed})')
                            elif fmt != 'TimeOfDay':
                                value = value[0]
                        except Exception as e:
                            print('Error   formatting failed:', e)
                    else:
                        print(f"unhandled format '{fmt}'")
                    print(f'value={value}', f'unit={obj["unit"]}' if 'unit' in obj else '')
                else:
                    print()
            else:
                print(f'UNKNOWN OBJECT {msg.index}')
            print()

class HexFile(io.TextIOBase):
    def __init__(self, buffer):
        super().__init__()
        self.buffer = buffer

    def read(self, bytes):
        buf = ""
        while len(buf) < 2*bytes:
            byte = self.buffer.read(1)
            if len(byte) == 0:
                # EOF
                return ''
            if byte in string.hexdigits:
                buf += byte

        return binascii.unhexlify(buf)

def hex_string_to_bytes(hex_string: str) -> bytes:
    """Convert a string of hex values to bytes, ignoring whitespace."""
    hex_string = ''.join(hex_string.split("\n\r\t\f :"))
    return binascii.unhexlify(hex_string)

def main():
    parser = argparse.ArgumentParser(description='Parse binary message format')
    parser.add_argument('input', type=argparse.FileType('rb'), default=sys.stdin,
                       nargs='?', help='Input file path (or - for stdin)')
    parser.add_argument('--hex', action='store_true',
                       help='Input contains hex strings instead of binary data')
    args = parser.parse_args()

    try:
        if args.hex:
            file = HexFile(args.input)
        else:
            file = args.input

        parser = MessageParser(file)
        parser.parse_all()
    finally:
        args.input.close()

if __name__ == "__main__":
    main()
