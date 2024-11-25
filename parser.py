import argparse
from dataclasses import dataclass
from typing import List, BinaryIO
from collections import Counter
import binascii
import warnings
from pprint import pprint
import struct
import re

@dataclass
class Message:
    is_reply: bool
    flags: int
    payload_length: int
    unknowns: bytes
    payload: bytes
    
    def __str__(self):
        payload_hex = ' '.join(f'{b:02X}' for b in self.payload)
        return (f"{'Reply' if self.is_reply else 'Request'} "
                f"flags={self.flags:08b} "
                f"length={self.payload_length} "
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
        messages = []
        while True:
            try:
                msg = self.parse_message()
                # print(msg)
                messages.append(msg)
            except EOFError:
                break
        return messages

def hex_string_to_bytes(hex_string: str) -> bytes:
    """Convert a string of hex values to bytes, ignoring whitespace."""
    hex_string = ''.join(hex_string.split())
    return binascii.unhexlify(hex_string)

def main():
    parser = argparse.ArgumentParser(description='Parse binary message format')
    parser.add_argument('input_file', type=str, help='Input file path')
    parser.add_argument('--hex', action='store_true', 
                       help='Input file contains hex strings instead of binary data')
    args = parser.parse_args()
    
    if args.hex:
        # Read as text and convert hex strings to binary
        with open(args.input_file, 'r') as f:
            hex_data = f.read()
        binary_data = hex_string_to_bytes(hex_data)
        from io import BytesIO
        file = BytesIO(binary_data)
    else:
        # Read as binary
        file = open(args.input_file, 'rb')
    
    try:
        parser = MessageParser(file)
        messages = parser.parse_all()
        
    finally:
        file.close()

    print(f"Found {len(messages)} messages:")
    for i, m in enumerate(messages):
        ascii_payload = ''.join([chr(b) if b >= 32 and b <= 126 else '.' for b in m.payload])
        if re.search(r'[^\.]{3}', ascii_payload):
            print('Reply' if m.is_reply else 'Request', m.unknowns.hex(), ascii_payload)
    
        
if __name__ == "__main__":
    main()
