import xml.etree.ElementTree as ET

def invert_bits(bits):
    return ''.join('1' if bit == '0' else '0' for bit in bits)

def extract_bytes(inverted_bits):
    bytes_list = []
    for i in range(0, len(inverted_bits), 10):
        frame = inverted_bits[i:i+10]
        if len(frame) == 10:
            start_bit, data, stop_bit = frame[0], frame[1:9], frame[9]
            assert start_bit == '0', f"Invalid start bit at position {i}"
            assert stop_bit == '1', f"Invalid stop bit at position {i+9}"
            byte = int(data, 2)
            bytes_list.append(byte)
    return bytes_list

# Parse the XML file
tree = ET.parse('protocol.proto.xml')
root = tree.getroot()

# Find all message elements
messages = root.findall('.//message')
# Iterate over all messages, invert bits, and extract bytes
for i, message in enumerate(messages, 1):
    bits = message.get('bits')
    inverted_bits = invert_bits(bits)
    
    try:
        extracted_bytes = extract_bytes(inverted_bits)
    except AssertionError as e:
        print(f"# Error in message {i}: {str(e)}\n# ", end="")
        for i in range(0, len(bits), 10):
            print(bits[i:i+10], end=" ")
        extracted_bytes = []
    
    # print(f"Message {i}:")
    # print(bits)
    # print(inverted_bits)
    print(' '.join(f'{byte:02X}' for byte in extracted_bytes))

print(f"# Total messages processed: {len(messages)}")