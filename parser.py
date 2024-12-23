import argparse
from dataclasses import dataclass
from typing import List, BinaryIO
from collections import Counter
import binascii
import warnings
from pprint import pprint
import struct
import re
import sys
import io
import string
import time

@dataclass(eq=True, frozen=True)
class Message:
    is_reply: bool
    flags: int
    payload_length: int
    unknowns: bytes
    payload: bytes
    
    def __str__(self):
        payload_hex = ' '.join(f'{b:02X}' for b in self.payload)
        return (f"{'Reply  ' if self.is_reply else 'Request'} "
                f"flags={self.flags:08b} "
                f"length={self.payload_length:02} "
                f"unknowns={self.unknowns.hex()} "
                f"payload={payload_hex}")

class MessageParser:
    def __init__(self, file: BinaryIO):
        self.file = file
        
    def read_bytes(self, count: int) -> bytes:
        data = self.file.read(count)
        if len(data) < count:
            raise EOFError(f"Expected {count} bytes, got {len(data)}")
        return data
    
    def parse_message(self) -> Message:
        # Read and verify header
        header = self.read_bytes(2)
        invalid = False
        while header[-2:] != b'\x01\x00':
            invalid = True
            header += self.read_bytes(1)
        if invalid:
            warnings.warn(f"Invalid header: {header.hex()}")
            
        # Parse message type and flags
        is_reply = self.read_bytes(1)[0] == 0x01
        flags = self.read_bytes(1)[0]
        
        # Parse payload length
        payload_length = self.read_bytes(1)[0]
        
        # Parse unknown fields
        unknowns = self.read_bytes(3)
        
        # Read payload
        payload = self.read_bytes(payload_length)
        
        return Message(
            is_reply=is_reply,
            flags=flags,
            payload_length=payload_length,
            unknowns=unknowns,
            payload=payload
        )
    
    def parse_all(self) -> List[Message]:
        messages = {}
        registers = {}
        while True:
            try:
                msg = self.parse_message()
                if msg.is_reply:
                    print(msg)
                    print("unexpected reply")
                    continue
                reply = self.parse_message()
                if not reply.is_reply:
                    print(reply)
                    print("unexpected request")
                    continue
                # parse known messages
                if msg.unknowns == b"\xfa\x00\x01": # register read?
                    key = msg.payload[0:3]
                    if key == b"\x30\x23\x00": # date time?
                        (ts, unk) = struct.unpack("<IH", reply.payload[3:-2])
                        t = time.gmtime(ts/1000)
                        tf = time.strftime("%H:%M:%S", t)
                        print(tf, unk, hex(unk))
                    elif key == b"\x56\x10\x00":
                        (tap,) = struct.unpack("<H", reply.payload[3:-2])
                        print("hot water #1:", tap/100)
                    elif key == b"\x36\x54\x01":
                        (tap,) = struct.unpack("<H", reply.payload[3:-2])
                        print("hot water #2:", tap/100)
                    
                    # fx seems to indicate response type, second byte number of values??
                    types = {
                        b"\xf8\x01": "<b", # 1
                        b"\xf7\x01": "<h", # 2
                        b"\xf5\x01": "<i", # 4
                        b"\xf5\x02": "<hh", # 2*2
                        b"\xf3\x01": "<ih", # 6??
                    }
                    typ = reply.unknowns[0:2]
                    if typ in types:
                        pattern = types[typ]
                        data = reply.payload[3:-2]
                        # diff = struct.calcsize(pattern)-len(data)
                        # padded = data+b"\x00"*diff
                        data = struct.unpack(pattern, data)
                        #print(reply.unknowns.hex(), reply.payload.hex(), data)
                        oldval = registers.get(key)
                        registers[key] = data
                        if oldval != data:
                            pass
                            print(key.hex(), oldval, data)
                    else:
                        print("unknown type", typ)
                        print(msg)
                        print(reply)
                elif msg.unknowns == b"\xf9\x04\x01": # modes
                    if msg.payload[0:3] == b"\x34\x1F\x01": # heating mode change
                        print("heater mode change:", ["schedule", "manual", "off"][msg.payload[3]])
                    if msg.payload[0:3] == b"\x36\x61\x01": # heating mode change
                        print("hot water mode change:", ["schedule", "comfort", "eco"][msg.payload[3]])
                    else:
                        print("f90401")
                        print(msg)
                        print(reply)
                elif msg.unknowns == b"\xf8\x04\x01": # temperatures
                    if msg.payload[0:3] == b"\x34\x13\x01": # temp change!!
                        (temp, crc) = struct.unpack("<HH", msg.payload[3:])
                        print("temprature change:", temp/10)
                    elif msg.payload[0:3] == b"\x54\x34\x01": # some other temp?
                        (temp, crc) = struct.unpack("<HH", msg.payload[3:])
                        print("current temperature:", temp/100)
                    else:
                        print("f80401")
                        print(msg)
                        print(reply)
                elif msg.unknowns == b"\xf4\x04\x01": # seen after temp adjustment
                    print("f40401")
                    print(msg)
                    print(reply)
                # print unknown messages
                # elif msg not in messages:
                #     print("new request")
                #     print(msg)
                #     print(reply)
                # elif messages[msg] != reply:
                #     print("new reply")
                #     print(msg)
                #     print(messages[msg])
                #     print(reply)
                messages[msg] = reply
                sys.stdout.flush()
            except EOFError:
                break

class HexFile(io.TextIOBase):
    def __init__(self, buffer):
        super().__init__()
        self.buffer = buffer

    def read(self, bytes):
        buf = ""
        while len(buf) < 2*bytes:
            byte = self.buffer.read(1)
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
