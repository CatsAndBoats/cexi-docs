"""
Search pol_decompressed.bin for the gear model_id → file_id lookup function.

Known offsets (file_id - model_id) derived from retail BigDats JSON files.
Each race has 3 sub-ranges within the main-hand slot (model_ids 24640+).
We search for the most distinctive constants and disassemble surrounding code.
"""

import struct
import capstone

BIN_IN   = r'D:\cexi-tools\pol_decompressed.bin'
OUT_MD   = r'D:\cexi-tools\pol_gear_formula.md'
IMAGE_BASE = 0x10000000
TEXT_VA    = IMAGE_BASE + 0x1000   # .text VA

print('Loading decompressed binary...')
with open(BIN_IN, 'rb') as f:
    text = f.read()
print(f'  {len(text):,} bytes\n')

# ── Known race offsets (range 1: model_ids 24640–25087) ──────────────────────
# Derived from retail gear JSON files (file_id - model_id for first entry each race)
RACE_OFFSETS_R1 = {
    'hume_male':     -16184,   # 0xFFFFC0C8
    'hume_female':   -13008,   # 0xFFFFCD30
    'elvaan_male':    -9832,   # 0xFFFFD998
    'elvaan_female':  -6656,   # 0xFFFFE600
    'galka':          +3096,   # 0x00000C18
    'mithra':           -80,   # 0xFFFFFFB0
    'taru_male':      -3480,   # 0xFFFFF268
    'taru_female':    -3480,   # 0xFFFFF268  (same as taru_male)
}

# Range 2 (model_ids 25088–25279) and range 3 (25280+) offsets
RACE_OFFSETS_R2 = {
    'hume_male':    38555, 'hume_female':  39003,
    'elvaan_male':  39451, 'elvaan_female': 39899,
    'galka':        41243, 'mithra':        40795,
    'taru_male':    40347, 'taru_female':   40347,
}
RACE_OFFSETS_R3 = {
    'hume_male':    47311, 'hume_female':  48847,
    'elvaan_male':  50383, 'elvaan_female': 51919,
    'galka':        56527, 'mithra':        54991,
    'taru_male':    53455, 'taru_female':   53455,
}

# ── Search helpers ────────────────────────────────────────────────────────────
def find_all(needle, limit=20):
    hits = []
    pos = 0
    while len(hits) < limit:
        idx = text.find(needle, pos)
        if idx == -1:
            break
        hits.append(idx)
        pos = idx + 1
    return hits


def offset_to_bytes(value):
    """Pack a signed 32-bit int as little-endian bytes."""
    return struct.pack('<i', value)


def disasm_context(file_off, before=48, after=96):
    start = max(0, file_off - before)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = False
    chunk = text[start: file_off + after]
    return list(md.disasm(chunk, TEXT_VA + start))


def format_context(file_off, insns, mark_offset=None):
    lines = []
    for i in insns:
        marker = ' <<<' if mark_offset is not None and i.address == TEXT_VA + mark_offset else ''
        lines.append(f'    {i.address:08X}:  {i.bytes.hex():<20}  {i.mnemonic} {i.op_str}{marker}')
    return '\n'.join(lines)


# ── Search each race offset ───────────────────────────────────────────────────
all_hits = {}   # file_offset → set of matching labels

for label, off in RACE_OFFSETS_R1.items():
    needle = offset_to_bytes(off)
    hits = find_all(needle)
    tag = f'{label}_r1({off:+d})'
    print(f'{tag}: {len(hits)} hits  needle={needle.hex()}')
    for h in hits:
        all_hits.setdefault(h, set()).add(tag)

print()
for label, off in RACE_OFFSETS_R2.items():
    needle = offset_to_bytes(off)
    hits = find_all(needle)
    tag = f'{label}_r2(+{off})'
    print(f'{tag}: {len(hits)} hits  needle={needle.hex()}')
    for h in hits:
        all_hits.setdefault(h, set()).add(tag)

print()
for label, off in RACE_OFFSETS_R3.items():
    needle = offset_to_bytes(off)
    hits = find_all(needle)
    tag = f'{label}_r3(+{off})'
    print(f'{tag}: {len(hits)} hits  needle={needle.hex()}')
    for h in hits:
        all_hits.setdefault(h, set()).add(tag)

# ── Find hotspots — offsets where MULTIPLE race constants cluster nearby ──────
print('\n=== Clustering: file offsets where multiple race constants appear within 512 bytes ===\n')

sorted_hits = sorted(all_hits.keys())
clusters = []   # (anchor_offset, set_of_file_offsets, set_of_labels)

used = set()
for i, h in enumerate(sorted_hits):
    if h in used:
        continue
    nearby = [h2 for h2 in sorted_hits if abs(h2 - h) <= 512]
    if len(nearby) >= 3:
        labels = set()
        for h2 in nearby:
            labels |= all_hits[h2]
            used.add(h2)
        clusters.append((h, nearby, labels))

for anchor, offsets, labels in clusters:
    va = TEXT_VA + anchor
    print(f'  Cluster @ ~0x{va:08X}  ({len(offsets)} hits, {len(labels)} tags)')
    for lbl in sorted(labels):
        print(f'    {lbl}')

# ── Disassemble the most promising clusters ───────────────────────────────────
print('\n=== Disassembly of top clusters ===')

md_sections = []
md_sections.append('# FFXiMain.dll — Gear Model ID → File ID Formula\n')
md_sections.append('Searched `pol_decompressed.bin` for race-specific FTABLE offsets derived from retail BigDats JSON files.\n')

for rank, (anchor, offsets, labels) in enumerate(clusters[:5]):
    va = TEXT_VA + anchor
    print(f'\n--- Cluster {rank+1} @ 0x{va:08X} ---')
    insns = disasm_context(anchor, before=64, after=128)
    block = format_context(anchor, insns, mark_offset=anchor)
    print(block)

    md_sections.append(f'\n## Cluster {rank+1} — VA 0x{va:08X}\n')
    md_sections.append(f'Matched tags: {", ".join(sorted(labels))}\n')
    md_sections.append('```asm\n' + block + '\n```\n')

# ── Also: search for the sub-range boundary model_ids 25088 / 25280 ──────────
print('\n=== CMP with range boundaries 25088 (0x6200) and 25280 (0x6300 - actually 0x62C0) ===\n')
# 25088 = 0x6200, 25280 = 0x6280... let me recalc
# 25088 = 0x6200
# 25280 = 25088 + 192 = 0x6200 + 0xC0 = 0x62C0
for val, label in [(25088, '25088=0x6200'), (25280, '25280=0x62C0'), (24640, '24640=0x6040')]:
    needle = struct.pack('<I', val)
    hits = find_all(needle)
    print(f'  {label}: {len(hits)} hits at {[hex(TEXT_VA+h) for h in hits[:6]]}')
    for h in hits[:2]:
        insns = disasm_context(h, before=32, after=64)
        block = format_context(h, insns, mark_offset=h)
        print(block)
        md_sections.append(f'\n## CMP {label} @ 0x{TEXT_VA+h:08X}\n')
        md_sections.append('```asm\n' + block + '\n```\n')
    print()

# ── Write markdown ────────────────────────────────────────────────────────────
with open(OUT_MD, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md_sections))
print(f'\nMarkdown written: {OUT_MD}')
