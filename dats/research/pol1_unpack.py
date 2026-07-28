"""
Attempt to unpack the POL1 section of FFXiMain.dll.
- Locates the OEP (which points to the unpacker stub in POL1)
- Disassembles the stub to find the decryption algorithm
- Tries all bit-rotation amounts to find valid x86 output
"""
import pefile, struct, capstone

dll_path = r'D:\cexi-tools\misc\FFXiMain.dll'
pe = pefile.PE(dll_path)

image_base = pe.OPTIONAL_HEADER.ImageBase
oep_rva    = pe.OPTIONAL_HEADER.AddressOfEntryPoint
oep_va     = image_base + oep_rva

print(f'ImageBase : 0x{image_base:08X}')
print(f'OEP RVA   : 0x{oep_rva:08X}')
print(f'OEP VA    : 0x{oep_va:08X}')

# Which section does the OEP land in?
for s in pe.sections:
    if s.VirtualAddress <= oep_rva < s.VirtualAddress + s.Misc_VirtualSize:
        print(f'OEP section: {s.Name.rstrip(b"\\x00").decode(errors="replace")}')
        # Compute file offset of OEP
        oep_file_off = s.PointerToRawData + (oep_rva - s.VirtualAddress)
        print(f'OEP file offset: 0x{oep_file_off:08X}')
        break

print()

# Read and disassemble 256 bytes at the OEP (the unpacker stub)
with open(dll_path, 'rb') as f:
    f.seek(oep_file_off)
    stub_bytes = f.read(256)

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
md.detail = False
print(f'=== Unpacker stub at OEP (0x{oep_va:08X}) ===\n')
for insn in md.disasm(stub_bytes, oep_va):
    print(f'  {insn.address:08X}:  {insn.bytes.hex():<20}  {insn.mnemonic} {insn.op_str}')

print()

# ── Brute-force bit rotation on first 32 bytes of POL1 ─────────────
pol1 = next(s for s in pe.sections if b'POL1' in s.Name)
with open(dll_path, 'rb') as f:
    f.seek(pol1.PointerToRawData)
    enc = f.read(64)

def ror8(b, n):
    n &= 7
    return ((b >> n) | (b << (8 - n))) & 0xFF

def rol8(b, n):
    n &= 7
    return ((b << n) | (b >> (8 - n))) & 0xFF

print('=== Brute-force bit rotation on first 64 bytes of POL1 ===')
print('    (checking if result looks like valid x86 — expect 55 8B EC or similar)\n')

for amount in range(1, 8):
    for fn, name in [(ror8, 'ROR'), (rol8, 'ROL')]:
        dec = bytes(fn(b, amount) for b in enc)
        # Check first few bytes as x86
        insns = list(md.disasm(dec[:32], 0x10001000))
        # Count valid instructions (not just one-byte garbage)
        valid = sum(1 for i in insns if len(i.bytes) >= 2)
        preview = dec[:16].hex()
        flag = ' <<<' if valid >= 4 else ''
        print(f'  {name} {amount}: {preview}  valid_insns={valid}{flag}')

print()

# Also try simple XOR with common keys
print('=== XOR with single byte key ===\n')
for key in range(0, 256):
    dec = bytes(b ^ key for b in enc[:32])
    insns = list(md.disasm(dec, 0x10001000))
    valid = sum(1 for i in insns if len(i.bytes) >= 2)
    if valid >= 5:
        print(f'  XOR 0x{key:02X}: {dec[:16].hex()}  valid_insns={valid}')
        for i in insns[:6]:
            print(f'    {i.address:08X}: {i.mnemonic} {i.op_str}')
        print()
