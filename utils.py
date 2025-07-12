
def to_hex(buffer):
    return " ".join("{:02x}".format(x) for x in buffer)

def decodeu(data: bytes):
    return int.from_bytes(data, byteorder='little', signed=False)

def decodes(data: bytes):
    return int.from_bytes(data, byteorder='little', signed=True)

def convert_mac_string_to_value(mac: str):
    return int.from_bytes(bytes([int(b, 16) for b in mac.split(":")]), 'big')