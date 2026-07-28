"""
Search the decompressed FFXiMain .text section for the monster model
ID -> file_id formula. Known facts:
  - offset 1300 (0x514) is confirmed for Tiger/modelid 308
  - range boundary 1500 (0x5DC) appears as CMP target in packed DLL
  - looking for ADD/CMP patterns with these constants near each other
"""
import pefile, struct, capstone

DLL_IN   = r'D:\cexi-tools\misc\FFXiMain.dll'
TEXT_BIN = None   # we'll decompress inline

# ── Decompress POL1 → .text ──────────────────────────────────────────
pe = pefile.PE(DLL_IN)
pol1 = next(s for s in pe.sections if b'POL1' in s.Name)
src_size = 0x1E57B0
dst_size = 0x32716E

with open(DLL_IN, 'rb') as f:
    f.seek(pol1.PointerToRawData)
    src = f.read(src_size)

def lzss_decompress(src, dst_size):
    dst = bytearray(dst_size)
    si = di = 0
    while si < len(src) and di < dst_size:
        ctrl = src[si]; si += 1
        for _ in range(8):
            carry = (ctrl >> 7) & 1
            ctrl = (ctrl << 1) & 0xFF
            if carry:
                if si >= len(src): break
                dst[di] = src[si]; si += 1; di += 1
            else:
                if si + 1 >= len(src): break
                b0 = src[si]; si += 1
                b1 = src[si]; si += 1
                offset = ((b0 << 8) | b1) & 0xFFF
                if offset == 0: return bytes(dst[:di])
                length = (b0 >> 4) + 3
                for _ in range(length):
                    if di >= dst_size: break
                    dst[di] = dst[di - offset]; di += 1
            if di >= dst_size: break
    return bytes(dst[:di])

print('Decompressing .text ...')
text = lzss_decompress(src, dst_size)
print(f'  {len(text):,} bytes ready\n')

IMAGE_BASE = pe.OPTIONAL_HEADER.ImageBase
TEXT_VA    = IMAGE_BASE + next(s for s in pe.sections
                               if s.Name.rstrip(b'\x00') == b'.text').VirtualAddress

# ── Search helpers ────────────────────────────────────────────────────
def find_all(needle, limit=50):
    hits = []
    pos = 0
    while len(hits) < limit:
        idx = text.find(needle, pos)
        if idx == -1: break
        hits.append(idx)
        pos = idx + 1
    return hits

def disasm_at(offset, n=20):
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = False
    va = TEXT_VA + offset
    chunk = text[offset:offset + n*6]
    return list(md.disasm(chunk, va))

def show_context(file_off, before=12, after=24, label=''):
    start = max(0, file_off - before)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = False
    chunk = text[start: file_off + after]
    insns = list(md.disasm(chunk, TEXT_VA + start))
    if label:
        print(f'\n  --- {label} ---')
    for i in insns:
        marker = ' <<<' if i.address == TEXT_VA + file_off else ''
        print(f'    {i.address:08X}:  {i.bytes.hex():<18}  {i.mnemonic} {i.op_str}{marker}')

# ── 1. CMP reg, 1500 (0x5DC) — range boundary ────────────────────────
print('=== CMP reg32, 1500 (0x5DC) ===\n')
patterns = [
    (b'\x3d\xdc\x05\x00\x00', 'CMP EAX, 1500'),
    (b'\x81\xf9\xdc\x05\x00\x00', 'CMP ECX, 1500'),
    (b'\x81\xfb\xdc\x05\x00\x00', 'CMP EBX, 1500'),
    (b'\x81\xff\xdc\x05\x00\x00', 'CMP EDI, 1500'),
    (b'\x81\xfe\xdc\x05\x00\x00', 'CMP ESI, 1500'),
    (b'\x81\xfa\xdc\x05\x00\x00', 'CMP EDX, 1500'),
]
cmp1500_hits = []
for needle, label in patterns:
    hits = find_all(needle)
    if hits:
        print(f'  {label}: {len(hits)} hits at {[hex(TEXT_VA+h) for h in hits[:5]]}')
        cmp1500_hits.extend(hits)

# ── 2. ADD reg, 1300 (0x514) ─────────────────────────────────────────
print('\n=== ADD reg32, 1300 (0x514) ===\n')
add_patterns = [
    (b'\x05\x14\x05\x00\x00',       'ADD EAX, 1300'),
    (b'\x81\xc1\x14\x05\x00\x00',   'ADD ECX, 1300'),
    (b'\x81\xc2\x14\x05\x00\x00',   'ADD EDX, 1300'),
    (b'\x81\xc3\x14\x05\x00\x00',   'ADD EBX, 1300'),
    (b'\x81\xc6\x14\x05\x00\x00',   'ADD ESI, 1300'),
    (b'\x81\xc7\x14\x05\x00\x00',   'ADD EDI, 1300'),
    (b'\x81\xe8\xec\xfa\xff\xff',   'SUB EAX, -1300 (ADD equivalent)'),
]
add1300_hits = []
for needle, label in add_patterns:
    hits = find_all(needle)
    if hits:
        print(f'  {label}: {len(hits)} hits at {[hex(TEXT_VA+h) for h in hits[:5]]}')
        add1300_hits.extend(hits)

# ── 3. MOV/CMP with 3000, 3500, 4000 ────────────────────────────────
print('\n=== CMP/MOV with range boundaries 3000, 3500, 4000 ===\n')
more_patterns = [
    (b'\x3d\xb8\x0b\x00\x00', 'CMP EAX, 3000'),
    (b'\x3d\xac\x0d\x00\x00', 'CMP EAX, 3500'),
    (b'\x3d\xa0\x0f\x00\x00', 'CMP EAX, 4000'),
    (b'\x81\xf9\xb8\x0b\x00\x00', 'CMP ECX, 3000'),
    (b'\x81\xf9\xac\x0d\x00\x00', 'CMP ECX, 3500'),
    (b'\x81\xf9\xa0\x0f\x00\x00', 'CMP ECX, 4000'),
]
boundary_hits = []
for needle, label in more_patterns:
    hits = find_all(needle)
    if hits:
        print(f'  {label}: {len(hits)} hits at {[hex(TEXT_VA+h) for h in hits[:5]]}')
        boundary_hits.extend(hits)

# ── 4. Show context for any hit that has BOTH add+cmp nearby ─────────
print('\n=== Code context around CMP 1500 hits ===')
for hit in cmp1500_hits[:5]:
    show_context(hit, before=48, after=64, label=f'CMP 1500 @ 0x{TEXT_VA+hit:08X}')

if add1300_hits:
    print('\n=== Code context around ADD 1300 hits ===')
    for hit in add1300_hits[:5]:
        show_context(hit, before=32, after=48, label=f'ADD 1300 @ 0x{TEXT_VA+hit:08X}')
