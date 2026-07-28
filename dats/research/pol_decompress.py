"""
FFXiMain.dll POL1 decompressor — standalone research script.

FFXiMain.dll stores its .text section compressed inside a custom PE section
named POL1.  The OEP stub decompresses POL1 into the .text VMA at load time
using a simple LZSS variant:

    Control byte, MSB-first:
      bit = 1  →  literal byte follows
      bit = 0  →  back-reference: 2 bytes encoding (length, offset)
                   offset = 0  →  end-of-stream sentinel

    SRC_SIZE  0x1E57B0  (1,988,528 bytes  — compressed)
    DST_SIZE  0x32716E  (3,305,838 bytes  — decompressed .text)

Output is a valid PE/DLL with .text restored on disk — load in Ghidra or IDA
(set image base 0x10000000).  The game will NOT run the unpacked DLL.

Dependencies: pefile, capstone (optional, for verification)

Usage:
    python pol_decompress.py FFXiMain.dll
    python pol_decompress.py FFXiMain.dll --output FFXiMain_unpacked.dll
"""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path

import pefile

SRC_SIZE = 0x1E57B0
DST_SIZE = 0x32716E


def lzss_decompress(src: bytes, dst_size: int) -> bytes:
    dst = bytearray(dst_size)
    si = di = 0
    while si < len(src) and di < dst_size:
        ctrl = src[si]; si += 1
        for _ in range(8):
            carry = (ctrl >> 7) & 1
            ctrl  = (ctrl << 1) & 0xFF
            if carry:
                if si >= len(src):
                    break
                dst[di] = src[si]; si += 1; di += 1
            else:
                if si + 1 >= len(src):
                    break
                b0 = src[si]; si += 1
                b1 = src[si]; si += 1
                offset = ((b0 << 8) | b1) & 0xFFF
                if offset == 0:
                    return bytes(dst[:di])
                length = (b0 >> 4) + 3
                for _ in range(length):
                    if di >= dst_size:
                        break
                    dst[di] = dst[di - offset]; di += 1
            if di >= dst_size:
                break
    return bytes(dst[:di])


def decompress(dll_path: Path, output_path: Path) -> None:
    pe = pefile.PE(str(dll_path))

    pol1     = next((s for s in pe.sections if b'POL1' in s.Name), None)
    text_sec = next((s for s in pe.sections if s.Name.rstrip(b'\x00') == b'.text'), None)

    if pol1 is None:
        raise ValueError('POL1 section not found — is this the correct FFXiMain.dll?')
    if text_sec is None:
        raise ValueError('.text section not found')

    print(f'POL1 raw offset : 0x{pol1.PointerToRawData:08X}')
    print(f'POL1 raw size   : 0x{pol1.SizeOfRawData:08X}')

    with open(dll_path, 'rb') as f:
        f.seek(pol1.PointerToRawData)
        src = f.read(SRC_SIZE)

    print('Decompressing...')
    text_data = lzss_decompress(src, DST_SIZE)
    print(f'  {len(text_data):,} bytes  (expected {DST_SIZE:,})')

    image_base = pe.OPTIONAL_HEADER.ImageBase
    text_va    = image_base + text_sec.VirtualAddress
    print(f'First 16 bytes  : {text_data[:16].hex()}')

    try:
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.detail = False
        print(f'\nFirst 10 instructions at VA 0x{text_va:08X}:')
        for insn in list(md.disasm(text_data[:64], text_va))[:10]:
            print(f'  {insn.address:08X}: {insn.bytes.hex():<20}  {insn.mnemonic} {insn.op_str}')
    except ImportError:
        print('(install capstone for disassembly verification)')

    print(f'\nWriting: {output_path}')
    shutil.copy2(dll_path, output_path)

    pe2   = pefile.PE(str(output_path))
    text2 = next(s for s in pe2.sections if s.Name.rstrip(b'\x00') == b'.text')

    with open(output_path, 'r+b') as f:
        f.seek(text2.PointerToRawData if text2.PointerToRawData else 0x400)
        f.write(text_data)
        hdr_off = text2.get_file_offset()
        f.seek(hdr_off + 16)  # SizeOfRawData field
        f.write(struct.pack('<I', len(text_data)))

    print('Done.')
    print('Load in Ghidra / IDA Pro with image base 0x10000000.')


def main() -> None:
    ap = argparse.ArgumentParser(description='Decompress FFXiMain.dll POL1 section')
    ap.add_argument('dll', type=Path, help='Path to FFXiMain.dll')
    ap.add_argument('--output', type=Path, default=None,
                    help='Output path (default: FFXiMain_unpacked.dll next to input)')
    args = ap.parse_args()

    dll    = args.dll
    output = args.output or dll.with_name('FFXiMain_unpacked.dll')
    decompress(dll, output)


if __name__ == '__main__':
    main()
