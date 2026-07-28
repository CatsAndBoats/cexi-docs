"""
Inspect the POL1 section of FFXiMain.dll.
- Show section layout
- Find the unpacker stub at the end of POL1
- Try to identify the bit-shift / XOR operation
"""
import pefile, struct

dll_path = r'D:\\cexi-tools\\misc\\FFXiMain.dll'
pe = pefile.PE(dll_path)

print('=== PE Sections ===\n')
for s in pe.sections:
    name = s.Name.rstrip(b'\x00').decode(errors='replace')
    print(f'  {name:<10}  VA=0x{s.VirtualAddress:08X}  '
          f'raw_off=0x{s.PointerToRawData:08X}  '
          f'raw_size=0x{s.SizeOfRawData:08X}  '
          f'virt_size=0x{s.Misc_VirtualSize:08X}  '
          f'flags=0x{s.Characteristics:08X}')

print()

# Find POL1 section
pol1 = next((s for s in pe.sections if b'POL1' in s.Name), None)
if not pol1:
    print('ERROR: POL1 section not found')
    exit(1)

print(f'=== POL1 section ===')
print(f'  Raw offset : 0x{pol1.PointerToRawData:08X}')
print(f'  Raw size   : 0x{pol1.SizeOfRawData:08X}  ({pol1.SizeOfRawData:,} bytes)')
print(f'  Virt addr  : 0x{pol1.VirtualAddress:08X}')
print()

# Read the raw data
with open(dll_path, 'rb') as f:
    f.seek(pol1.PointerToRawData)
    pol1_data = f.read(pol1.SizeOfRawData)

# The unpacker stub is described as being at the END of the POL1 section.
# Dump the last 256 bytes as both hex and attempt basic disassembly context.
print('=== Last 256 bytes of POL1 (unpacker stub region) ===\n')
stub = pol1_data[-256:]
for i in range(0, len(stub), 16):
    chunk = stub[i:i+16]
    hex_part   = ' '.join(f'{b:02X}' for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    off = pol1.PointerToRawData + pol1.SizeOfRawData - 256 + i
    print(f'  0x{off:08X}:  {hex_part:<47}  {ascii_part}')

# Also look for any XOR keys or shift amounts near the stub.
# Try to identify repeating byte patterns in the encrypted .text data
# that might reveal the XOR/shift key.
print()
print('=== First 64 bytes of POL1 (start of encrypted .text) ===\n')
head = pol1_data[:64]
for i in range(0, 64, 16):
    chunk = head[i:i+16]
    hex_part   = ' '.join(f'{b:02X}' for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    off = pol1.PointerToRawData + i
    print(f'  0x{off:08X}:  {hex_part:<47}  {ascii_part}')

# Try to find the .text section (should be zeroed or minimal in file, filled at runtime)
text_sec = next((s for s in pe.sections if s.Name.rstrip(b'\x00') == b'.text'), None)
if text_sec:
    print(f'\n=== .text section on disk ===')
    print(f'  Raw offset : 0x{text_sec.PointerToRawData:08X}')
    print(f'  Raw size   : 0x{text_sec.SizeOfRawData:08X}  ({text_sec.SizeOfRawData:,} bytes)')
    with open(dll_path, 'rb') as f:
        f.seek(text_sec.PointerToRawData)
        text_head = f.read(32)
    print(f'  First 32 bytes: {text_head.hex()}')
    non_zero = sum(1 for b in text_head if b != 0)
    print(f'  Non-zero in first 32 bytes: {non_zero}  (0 = zeroed out on disk as expected)')
