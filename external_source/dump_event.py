#!/usr/bin/env python3
"""Dump all data for events inside a zone event DAT.

Event DATs are flat per-zone files (eventheader_t + eventblock_t[]), NOT the
section-headered format. This is a faithful standalone port of the plugin's
container parser (event/EventFile.cpp) and opcode-size table
(event/EventDisassembler.cpp), so the disassembly here matches the engine.

Usage:
    dump_event.py --zone 184 --event 22            # resolve zone DAT via FTABLE/VTABLE
    dump_event.py <file.DAT>                       # list every block + event
    dump_event.py <file.DAT> --event 0x0A          # dump event id 0x0A (all blocks)
    dump_event.py <file.DAT> --event 10 --actor 0x7FFFFFF0
    dump_event.py <file.DAT> --block 0             # dump every event in block 0
    dump_event.py <file.DAT> --event 0x0A --bytes  # include raw hex per instruction
    dump_event.py --zone 184 --event 22 --md       # write a markdown table file

Notes:
    * Event ids and actor numbers accept decimal or 0x-hex.
    * Wildcard event id 0xFFFE matches any requested id (kept as a real match).
    * Opcode names/descriptions are read (best-effort) from
      research/XiEvents/OpCodes/*.md if that tree can be located.
"""

import argparse
import os
import re
import struct
import sys

# Byte-verified 2026-08: retail zone/master blocks carry 0x7FFFFFF0 at block
# level (253/253 zone event DATs); 0x7FFFFFFF never occurs as a block actor id.
ZONE_EVENT_ACTOR = 0x7FFFFFF0
WILDCARD_EVENT_ID = 0xFFFE

# --- opcode sizing (ported verbatim from EventDisassembler.cpp) ----------------

# Fixed instruction size per opcode (0x00..0xD9). 0 = variable-length / N/A.
FIXED_SIZES = [
    1, 3, 8, 5, 3, 3, 3, 5, 5, 5, 5, 3, 3, 5, 5, 5,
    5, 5, 3, 5, 5, 5, 7, 7, 7, 5, 3, 1, 3, 3, 5, 0,
    2, 1, 2, 1, 7, 1, 1, 7, 7, 7, 6, 7, 13, 13, 1, 6,
    1, 0, 3, 2, 3, 3, 7, 9, 3, 3, 7, 11, 7, 7, 7, 7,
    9, 9, 1, 2, 5, 17, 0, 0, 3, 7, 9, 7, 1, 1, 6, 3,
    13, 13, 15, 13, 13, 15, 5, 3, 1, 0, 0, 0, 0, 5, 5, 0,
    0, 2, 17, 3, 11, 11, 0, 5, 1, 4, 7, 9, 9, 7, 7, 1,
    1, 0, 0, 11, 2, 0, 5, 5, 1, 0, 0, 5, 6, 3, 0, 1,
    5, 6, 7, 3, 1, 1, 6, 2, 2, 3, 1, 25, 0, 5, 1, 1,
    1, 3, 6, 3, 6, 3, 1, 5, 1, 5, 1, 1, 3, 0, 2, 17,
    15, 15, 15, 15, 2, 2, 0, 0, 6, 3, 17, 0, 0, 12, 0, 8,
    12, 4, 0, 0, 0, 4, 0, 0, 27, 8, 13, 17, 15, 15, 3, 0,
    3, 5, 0, 7, 11, 17, 15, 15, 7, 1, 0, 0, 0, 17, 15, 15,
    17, 15, 15, 6, 0, 17, 15, 15, 0, 2,
]

# {opcode: (fallback_size, {subcode: size})} for variable-length opcodes.
_SUB_TABLES = {
    0x59: (0, {0: 4, 1: 8, 2: 4, 3: 8, 4: 8, 5: 7, 6: 6, 7: 4, 8: 8}),
    0x8C: (0, {0: 8, 1: 2, 2: 12, 3: 10, 4: 10, 5: 14}),
    0x9D: (8, {0: 8, 1: 8, 2: 6, 3: 8, 4: 8, 5: 8, 6: 8, 7: 6, 8: 23,
               9: 9, 0xA: 10, 0xB: 10, 0xC: 8, 0xD: 10, 0xE: 10, 0xF: 10, 0x10: 10}),
    0xAC: (0, {0: 4, 1: 4, 2: 6, 3: 6, 4: 8}),
    0xAE: (6, {0: 6, 1: 8, 2: 8, 3: 8, 4: 8, 5: 10, 6: 6, 7: 10, 8: 10}),
    0x71: (0, {0: 2, 1: 2, 2: 2, 3: 4, 0x10: 4, 0x11: 4, 0x13: 4, 0x12: 6,
               0x20: 16, 0x21: 2, 0x30: 4, 0x31: 4, 0x32: 6, 0x40: 4, 0x41: 8}),
    0x5F: (0, {0: 2, 1: 2, 2: 6, 3: 16, 4: 16, 5: 18, 6: 18, 7: 14}),
    0x7A: (0, {0: 6, 1: 7, 2: 6, 3: 2, 4: 8, 5: 6}),
    0x7E: (6, {0: 6, 1: 6, 2: 6, 3: 16, 4: 6, 5: 6, 6: 18, 7: 8, 8: 6}),
    0xB3: (2, {0: 4, 1: 14, 2: 2, 3: 4, 4: 4, 5: 18, 6: 4, 7: 4, 8: 2, 9: 4}),
    0xB4: (0, {0: 20, 1: 6, 2: 6, 3: 2, 4: 6, 5: 3, 6: 3, 7: 4, 8: 2, 9: 4,
               0xA: 4, 0xB: 2, 0xC: 4, 0xD: 2, 0xE: 2, 0xF: 6, 0x10: 6, 0x11: 6,
               0x12: 6, 0x13: 20, 0x14: 12, 0x15: 2}),
    0xB6: (4, {0: 4, 1: 4, 2: 4, 3: 4, 4: 4, 5: 4, 6: 4, 7: 4, 8: 4, 9: 4,
               0xA: 4, 0xB: 20, 0xC: 4, 0xD: 14, 0xE: 16, 0xF: 4, 0x10: 2, 0x11: 4,
               0x12: 2, 0x13: 2, 0x14: 6, 0x15: 6}),
    0xB7: (0, {0: 10, 1: 8, 2: 8, 3: 8, 4: 8}),
    0xCC: (4, {0: 10, 1: 10, 2: 14, 3: 10, 0x10: 6, 0x11: 4, 0x20: 4}),
    0xD4: (2, {0: 2, 1: 8, 2: 2, 3: 6, 4: 12, 5: 12}),
    0xD8: (6, {0: 6, 1: 8, 2: 8, 3: 8, 4: 12}),
}


def variable_opcode_size(opcode, sub):
    # Closed-form cases first (mirror the switch in variableOpcodeSize()).
    if opcode == 0x1F:
        return 8 if sub == 0 else 2
    if opcode == 0x31:
        return 10 if sub == 0 else 2
    if opcode == 0x46:
        return 4 if sub == 2 else 2
    if opcode == 0x47:
        return 10 if sub == 0 else 2
    if opcode == 0x5A:
        return 8 if sub == 0 else 2
    if opcode in (0x5B, 0x66):
        return 15
    if opcode == 0x5C:
        return 4 if sub <= 7 else 6
    if opcode == 0x60:
        return 4 if sub <= 1 else (6 if sub == 2 else 2)
    if opcode == 0x72:
        return 4 if sub == 0 else 6
    if opcode == 0x75:
        return 4 if sub == 0 else 2
    if opcode == 0x79:
        return 12 if sub == 1 else 10
    if opcode == 0xA6:
        return 4 if sub == 2 else 2
    if opcode == 0xA7:
        return 4 if sub == 1 else 2
    if opcode == 0xAB:
        return 4 if sub == 0x11 else 2
    if opcode == 0xB2:
        return 2 if sub == 0 else 4
    if opcode == 0xBF:
        return 8 if (sub == 0 or sub == 0x60) else 10
    if opcode == 0xC2:
        return 4 if sub == 1 else (6 if sub == 2 else 2)
    if opcode in _SUB_TABLES:
        fallback, table = _SUB_TABLES[opcode]
        return table.get(sub, fallback)
    return 0  # 0xCA / 0xCB are N/A; unknown opcodes have no size.


def opcode_size(opcode, subcode):
    if opcode >= 0xDA:
        return 0
    fixed = FIXED_SIZES[opcode]
    if fixed != 0:
        return fixed
    return variable_opcode_size(opcode, subcode)


# --- container parse (ported from EventFile.cpp) ------------------------------

class ParseError(Exception):
    pass


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def u32(self):
        if self.p + 4 > len(self.d):
            raise ParseError(f"u32 read past end at {self.p}")
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def u16(self):
        if self.p + 2 > len(self.d):
            raise ParseError(f"u16 read past end at {self.p}")
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v


def align4(v):
    return (v + 3) & ~3


def parse_event_file(data, resource_name=""):
    r = Reader(data)
    block_count = r.u32()
    block_sizes = [r.u32() for _ in range(block_count)]
    header_size = 4 + block_count * 4
    if header_size + sum(block_sizes) != len(data):
        raise ParseError(
            f"event file size mismatch in '{resource_name}' "
            f"(header {header_size} + blocks {sum(block_sizes)} != file {len(data)})")

    blocks = []
    for bi in range(block_count):
        block_start = r.p
        block_end = block_start + block_sizes[bi]

        actor = r.u32()
        tag_count = r.u32()
        tag_offsets = [r.u16() for _ in range(tag_count)]
        event_ids = [r.u16() for _ in range(tag_count)]
        imed_count = r.u32()
        immediate = [r.u32() for _ in range(imed_count)]
        data_size = r.u32()

        data_start = r.p
        if data_start + align4(data_size) > block_end:
            raise ParseError(f"block {bi}: EventData overruns block")
        event_data = data[data_start:data_start + data_size]

        events = []
        for i in range(tag_count):
            start = tag_offsets[i]
            end = tag_offsets[i + 1] if i + 1 < tag_count else data_size
            if start > data_size or end > data_size or start > end:
                raise ParseError(f"block {bi}: TagOffset[{i}] out of range")
            events.append({"event_id": event_ids[i], "offset": start, "length": end - start})

        blocks.append({
            "index": bi, "actor": actor, "data_size": data_size,
            "immediate": immediate, "event_data": event_data, "events": events,
        })
        r.p = block_end  # skip alignment padding / trailing slack
    return {"resource": resource_name, "blocks": blocks}


# --- disassembly --------------------------------------------------------------

def disassemble(bytecode):
    out = []
    p = 0
    n = len(bytecode)
    while p < n:
        opcode = bytecode[p]
        subcode = bytecode[p + 1] if p + 1 < n else 0
        size = opcode_size(opcode, subcode)
        if size == 0 or p + size > n:
            out.append({"offset": p, "stopped": True, "opcode": opcode})
            break
        out.append({
            "offset": p, "opcode": opcode,
            "subcode": subcode if size >= 2 else 0, "size": size,
            "raw": bytecode[p:p + size],
        })
        p += size
    return out


# --- opcode docs (best-effort, from read-only research tree) ------------------

def find_opcode_dir(start):
    cur = os.path.abspath(start)
    while True:
        cand = os.path.join(cur, "research", "XiEvents", "OpCodes")
        if os.path.isdir(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


_YESNO_RE = re.compile(r"\*\*Sets `(RetFlag|ExecPointer)`\?\*\*\s*\|\s*`?(Yes|No)`?")
_PS2_RE = re.compile(r"//\s*PS2:\s*(.+)")
# Pseudo-code helper name, e.g. FUNC_XiEvent_CodeLOADSCHEDULER / FUNC_XiEvent_MESWAIT.
# Excludes the generic FUNC_XiEvent_OpCode_0xNNNN wrapper.
_CODEFN_RE = re.compile(r"FUNC_XiEvent_((?:Code|Mes)[A-Za-z0-9_]+)")


def load_opcode_meta(start):
    """Parse research/XiEvents/OpCodes/*.md into per-opcode metadata.

    Returns {opcode: {"desc": str, "desc_full": str, "retflag": bool|None,
    "exec": bool|None, "ps2": str|None}}. Empty dict if the docs tree is absent.
    """
    d = find_opcode_dir(start)
    meta = {}
    if not d:
        return meta
    for opcode in range(0x100):
        path = os.path.join(d, f"0x{opcode:04X}.md")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        lines = text.splitlines()

        # Description: the paragraph(s) under "## Description" up to the next heading.
        desc_lines = []
        for i, line in enumerate(lines):
            if line.strip() == "## Description":
                for body in lines[i + 1:]:
                    if body.startswith("## "):
                        break
                    if body.strip():
                        desc_lines.append(body.strip())
                break
        desc_full = " ".join(desc_lines)
        desc_short = desc_lines[0] if desc_lines else ""

        flags = {"RetFlag": None, "ExecPointer": None}
        for m in _YESNO_RE.finditer(text):
            flags[m.group(1)] = (m.group(2) == "Yes")

        ps2 = None
        pm = _PS2_RE.search(text)
        if pm:
            ps2 = pm.group(1).strip()

        code_fn = None
        cm = _CODEFN_RE.search(text)
        if cm:
            code_fn = cm.group(1)

        meta[opcode] = {
            "desc": desc_short,
            "desc_full": desc_full,
            "retflag": flags["RetFlag"],
            "exec": flags["ExecPointer"],
            "ps2": ps2,
            "code_fn": code_fn,
        }
    return meta


# --- opcode naming ------------------------------------------------------------
#
# A canonical short name per opcode, synthesized from every source we have, in
# priority order: the client's own PS2 name (research docs) -> the pseudo-code
# helper name -> the gameplay module's command/focus name -> a heuristic from the
# description. Names are the authentic client identifiers where known.

# Clean human names from the gameplay module (EEventCommandType in
# event/EventCommands.h, FocusKind in event/EventOps.h). Used when the docs give
# no PS2/pseudo name for an opcode the engine still decodes.
GAMEPLAY_NAMES = {
    0x2B: "ShowMessage", 0x48: "ShowMessage",
    0x45: "LoadCameraScheduler", 0x7D: "LoadCameraScheduler",
    0x34: "LoadEventMap", 0x35: "LoadEventMap",
    0x2C: "CreateZoneScheduler", 0x2D: "CreateZoneScheduler",
    0x63: "PlayEmote", 0x6E: "PlayEmote",
    0x24: "ShowChoices",
    0x22: "SetEntityVisible", 0x4E: "SetEntityVisible",
    0x6B: "StopAction",
    0x6C: "FadeEntity",
    0x4A: "LookAt", 0x79: "LookAt",
    0x36: "SetEventPos", 0x37: "SetEventPos",
    0x39: "SetEventDir",
    0x32: "SetCameraMode", 0x38: "SetCameraMode", 0x46: "SetCameraMode",
    0x69: "PlaySound",
    0x5C: "PlayMusic",
    0x67: "SetHud", 0x68: "SetHud",
    0x8B: "MapMarker",
    0xC8: "OpenMap",
    0x8A: "CloseMap",
    0x77: "LockClock",
    0x78: "RestoreClock",
    0xAF: "CameraCapture",
    0x01: "SetExecPointer",  # unconditional jump (docs: "Directly sets the ExecPointer position")
}

_NAME_STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "its", "it", "this", "that", "then",
    "into", "back", "current", "given", "for", "with", "on", "in", "is", "are",
    "as", "from", "by", "be", "or", "if",
}


def _heuristic_name(desc):
    """Last-resort name from the description. Leads with the first verb and, when
    the sentence names a backtick identifier early, pairs it with that identifier
    (e.g. "Sets the `CliEventUcFlag` flag value" -> "SetCliEventUcFlag");
    otherwise joins the first few significant words CamelCase."""
    if not desc:
        return None
    sentence = desc.split(".")[0]
    tokens = []  # (is_ident, text)
    for raw in re.findall(r"`([^`]+)`|([A-Za-z][A-Za-z0-9]*)", sentence):
        tokens.append((bool(raw[0]), (raw[0] or raw[1])))

    verb = next((t for is_id, t in tokens if not is_id and t.lower() not in _NAME_STOPWORDS),
                None)
    first_ident = next((t for i, (is_id, t) in enumerate(tokens) if is_id and i < 5), None)

    def cap(w):
        return w[:1].upper() + w[1:]

    parts = []
    if verb and first_ident:
        # Singularize a leading "Sets"/"Gets"-style verb for readability.
        v = verb[:-1] if verb.lower().endswith("s") and len(verb) > 3 else verb
        parts = [cap(v), first_ident]
    else:
        for is_id, t in tokens:
            if is_id:
                parts.append(t)
            elif t.lower() not in _NAME_STOPWORDS:
                parts.append(cap(t))
            if len(parts) >= 3:
                break

    # Drop an immediately repeated token (case-insensitive), e.g. "...Flag" + "flag".
    deduped = []
    for p in parts:
        if not deduped or deduped[-1].lower() != p.lower():
            deduped.append(p)
    name = "".join(deduped)
    return name[:32] if name else None


def _clean_client_name(s):
    """Normalize a PS2/pseudo name: drop XiEvent:: and a leading Code prefix."""
    s = s.split("::")[-1]
    if s.startswith("Code"):
        s = s[len("Code"):]
    return s


def opcode_name(opcode, meta):
    """Resolve the canonical name for an opcode from all sources."""
    m = meta.get(opcode) or {}
    if m.get("ps2"):
        return _clean_client_name(m["ps2"])
    if m.get("code_fn"):
        return _clean_client_name(m["code_fn"])
    if opcode in GAMEPLAY_NAMES:
        return GAMEPLAY_NAMES[opcode]
    h = _heuristic_name(m.get("desc"))
    if h:
        return h
    return f"Op_{opcode:02X}"


# --- zone -> event DAT path (FTABLE/VTABLE, ported from GameDataRepository) ----

def find_game_data_root(start):
    """Locate the game-data dir by walking up from `start`."""
    cur = os.path.abspath(start)
    while True:
        cand = os.path.join(cur, "game-data")
        if os.path.isdir(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _load_combined_table(root, base):
    """OR-combine base.DAT + ROM2/base2.DAT .. ROM9/base9.DAT, like FileTableManager.

    NB: this mirrors xim's combine model. External byte evidence (2026-06-24, ~33
    multi-volume file-ids) says the REAL client is volume-direct: the VTABLE byte
    names the ROM volume and update entries shadow the base — for registered ids
    both models resolve the same path, which is why this tool still works."""
    combined = bytearray()
    for i in range(1, 10):
        prefix = "" if i == 1 else f"ROM{i}"
        postfix = "" if i == 1 else str(i)
        path = os.path.join(root, prefix, f"{base}{postfix}.DAT")
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as f:
            data = f.read()
        if len(combined) < len(data):
            combined.extend(b"\0" * (len(data) - len(combined)))
        for j, b in enumerate(data):
            combined[j] |= b
    return combined


def resolve_dat_path(root, file_index):
    """file table index -> 'ROM[v]/folder/file.DAT' via VTABLE/FTABLE.

    Mirrors GameDataRepository::resolveDatPath: VTABLE byte = version (0 -> absent;
    the fallback ROM/{idx//100}/{idx%100}.DAT), FTABLE u16 packs folder=val>>7,
    file=val&0x7F. version 1 -> 'ROM', else 'ROM<version>'.
    """
    vt = _load_combined_table(root, "VTABLE")
    ft = _load_combined_table(root, "FTABLE")
    version = vt[file_index] if file_index < len(vt) else 0
    if version == 0:
        return f"ROM/{file_index // 100}/{file_index % 100}.DAT"
    off = file_index * 2
    value = struct.unpack_from("<H", ft, off)[0] if off + 1 < len(ft) else 0
    folder, num = value >> 7, value & 0x7F
    version_str = "" if version == 1 else str(version)
    return f"ROM{version_str}/{folder}/{num}.DAT"


def resolve_zone_event_dat(root, zone_id):
    """Zone id -> event DAT path. GameDataRepository::resolveZoneEventDat:
    file index = (zone < 0x100 ? 5820 : 84735) + zone."""
    file_index = (5820 if zone_id < 0x100 else 84735) + zone_id
    return file_index, resolve_dat_path(root, file_index)


# --- output -------------------------------------------------------------------

def parse_int(s):
    return int(s, 0)


def fmt_actor(a):
    label = "  (zone/player)" if a == ZONE_EVENT_ACTOR else ""
    return f"0x{a:08X}{label}"


def print_event(block, ev, meta, show_bytes):
    eid = ev["event_id"]
    imid = block["immediate"]
    wild = "  (wildcard)" if eid == WILDCARD_EVENT_ID else ""
    print(f"  event 0x{eid:04X} ({eid}){wild}  "
          f"offset={ev['offset']} length={ev['length']}")
    bytecode = block["event_data"][ev["offset"]:ev["offset"] + ev["length"]]
    instrs = disassemble(bytecode)
    for ins in instrs:
        if ins.get("stopped"):
            tail = bytecode[ins["offset"]:]
            print(f"    +{ins['offset']:<5} STOP @ opcode 0x{ins['opcode']:02X} "
                  f"(unsized/overrun; {len(tail)} bytes remain, likely jump table)")
            if show_bytes:
                print(f"            {tail.hex(' ')}")
            continue
        op = ins["opcode"]
        desc = (meta.get(op) or {}).get("desc", "")
        if desc and len(desc) > 48:
            desc = desc[:45] + "..."
        flags = instr_flags(op, meta)
        flag_str = f" [{flags}]" if flags else ""
        sub = f" sub=0x{ins['subcode']:02X}" if ins["size"] >= 2 else ""
        name = opcode_name(op, meta)
        line = (f"    +{ins['offset']:<5} 0x{op:02X}{sub} {name:<22} "
                f"size={ins['size']:<3}{flag_str} {desc}")
        print(line.rstrip())
        decode = decode_instruction(op, ins["subcode"], ins["size"], ins["raw"], imid)
        if decode:
            print(f"            ⇒ {decode}")
        if show_bytes:
            print(f"            {ins['raw'].hex(' ')}")


# --- semantic decode (ported from gameplay module: event/EventOps.cpp) ---------
#
# Mirrors decodeFocusOp / classifyWorkSelector / datIdHelper for the camera+scheduler
# "focus" opcodes, plus the GetActorIndex magic-id labels and the getworkofs operand
# model (research/XiEvents/Event VM Functions.md). Statically resolvable operands are
# the ImidData references (selector high bit 0x8000); runtime work-area slots are not.

MAIN_ACTION_ID = 0x6E69616D  # 'main'

# GetActorIndex hard-coded lookup values (Event VM Functions.md).
_ACTOR_MAGIC = {
    0x7FFFFFC0: "local player", 0x7FFFFFF0: "local player", 0x7FFFFFF9: "local player",
    0x7FFFFFF8: "event entity",
}
for _i, _v in enumerate((0x7FFFFFC1, 0x7FFFFFC2, 0x7FFFFFC3, 0x7FFFFFC4, 0x7FFFFFC5), start=1):
    _ACTOR_MAGIC[_v] = f"party member {_i}"
for _i, _v in enumerate((0x7FFFFFC6, 0x7FFFFFC7, 0x7FFFFFC8, 0x7FFFFFC9, 0x7FFFFFCA, 0x7FFFFFCB), start=10):
    _ACTOR_MAGIC[_v] = f"alliance member {_i}"
for _i, _v in enumerate((0x7FFFFFCC, 0x7FFFFFCD, 0x7FFFFFCE, 0x7FFFFFCF, 0x7FFFFFD0, 0x7FFFFFD1), start=20):
    _ACTOR_MAGIC[_v] = f"alliance member {_i}"


def label_actor(aid):
    if aid in _ACTOR_MAGIC:
        return f"0x{aid:08X} ({_ACTOR_MAGIC[aid]})"
    if aid & 0xFF000000:  # GetActorIndex default: a real NPC server id, index = id & 0x3FF
        return f"0x{aid:08X} (npc idx {aid & 0x3FF})"
    return f"0x{aid:08X}"


def datid_helper(p):
    if p >= 600:
        return p + 39643
    if p >= 300:
        return p + 25937
    return p


def ascii_tag(value):
    """4-char little-endian DatId tag as text when fully printable (e.g. 'fdo1')."""
    chars = [(value >> (8 * i)) & 0xFF for i in range(4)]
    if all(0x20 <= c < 0x7F for c in chars):
        return "".join(chr(c) for c in chars)
    return None


def fmt_action(value):
    tag = ascii_tag(value)
    return f"'{tag}'" if tag else f"0x{value:08X}"


def read16(b, off):
    return b[off] | (b[off + 1] << 8) if off + 1 < len(b) else 0


def read32(b, off):
    return (b[off] | (b[off + 1] << 8) | (b[off + 2] << 16) | (b[off + 3] << 24)
            if off + 3 < len(b) else 0)


def work_operand(raw, imid):
    """decodeWorkOperand: resolve a getworkofs selector against ImidData when it's a ref."""
    if raw & 0x8000:
        idx = raw & 0x7FFF
        if idx < len(imid):
            return f"imid[{idx}]=0x{imid[idx]:08X}"
        return f"imid[{idx}](oob)"
    return f"work@0x{raw:04X}"


FOCUS_OPCODES = {0x38, 0x46, 0xAF, 0x45, 0x7D, 0x55, 0x53, 0x54,
                 0x50, 0x51, 0x52, 0x2C, 0x2D, 0xAD}


def decode_focus(opcode, sub, raw, imid):
    """Port of decodeFocusOp -> one human-readable string, or None if not a focus op."""
    def two_entity(ai, bi, acti):
        return (f"actorA={label_actor(read32(raw, ai))} "
                f"actorB={label_actor(read32(raw, bi))} action={fmt_action(read32(raw, acti))}")

    def scheduler(base, use_helper, work_index):
        sel = read16(raw, work_index)
        parts = []
        if sel & 0x8000 and (sel & 0x7FFF) < len(imid):
            val = imid[sel & 0x7FFF]
            rid = base + (datid_helper(val) if use_helper else val)
            parts.append(f"res={rid}")
        else:
            parts.append(f"res=<runtime {work_operand(sel, imid)}>")
        return " ".join(parts)

    if opcode == 0x38:
        sel = read16(raw, 1)
        if sel & 0x8000 and (sel & 0x7FFF) < len(imid):
            mask = ((imid[sel & 0x7FFF] >> 8) & 0xFF) | 0x20
            return f"CameraMode mask=0x{mask:04X}"
        return f"CameraMode mask=<runtime {work_operand(sel, imid)}>"
    if opcode == 0x46:
        return "CameraControl " + ({1: "disable", 2: "query"}.get(sub, "enable"))
    if opcode == 0xAF:
        return "CameraCapture at(look)" if sub == 1 else "CameraCapture eye(pos)"
    if opcode == 0x45:
        return f"SchedulerLoad {scheduler(30704, True, 1)} {two_entity(3, 7, 11)}"
    if opcode == 0x7D:
        return f"SchedulerLoad {scheduler(5112, False, 1)} action='main'"
    if opcode in (0x55, 0x52):
        name = "SchedulerWait" if opcode == 0x55 else "SchedulerEnd"
        return f"{name} {scheduler(30704, True, 1)} {two_entity(3, 7, 11)}"
    if opcode in (0x53, 0x54):
        return f"SchedulerWait {two_entity(1, 5, 9)}"
    if opcode in (0x50, 0x51):
        return f"SchedulerEnd {two_entity(1, 5, 9)}"
    if opcode in (0x2C, 0x2D):
        return f"SchedulerCreate {two_entity(1, 5, 9)}"
    if opcode == 0xAD:
        return (f"SchedulerAction actorA={label_actor(read32(raw, 4))} "
                f"actorB={label_actor(read32(raw, 8))} {work_operand(read16(raw, 2), imid)}")
    return None


def generic_annotations(opcode, raw, imid):
    """Readable operand notes for any opcode: ImidData refs, actor magic ids, embedded text."""
    notes = []
    # 2-byte work selectors at even offsets after the opcode that resolve to a real ImidData
    # entry (high bit set, index in range). Filters out literals / 4-byte actor ids naturally.
    refs = []
    for off in range(1, len(raw) - 1, 2):
        w = raw[off] | (raw[off + 1] << 8)
        if w & 0x8000 and (w & 0x7FFF) < len(imid):
            refs.append(f"+{off}:imid[{w & 0x7FFF}]=0x{imid[w & 0x7FFF]:08X}")
    if refs:
        notes.append("refs " + " ".join(refs))
    # Actor magic ids embedded as 4-byte LE words.
    for off in range(1, len(raw) - 3):
        v = read32(raw, off)
        if v in _ACTOR_MAGIC:
            notes.append(f"+{off}:{_ACTOR_MAGIC[v]}")
    # Embedded printable ASCII run (>=3 chars), e.g. a map-marker name.
    run = bytearray()
    runs = []
    for byte in raw[1:]:
        if 0x20 <= byte < 0x7F:
            run.append(byte)
        else:
            if len(run) >= 3:
                runs.append(run.decode("ascii"))
            run = bytearray()
    if len(run) >= 3:
        runs.append(run.decode("ascii"))
    for r in runs:
        notes.append(f'"{r}"')
    return notes


def decode_instruction(opcode, sub, size, raw, imid):
    """Combined semantic decode for one instruction: focus decode + branch + generic notes."""
    parts = []
    if opcode in FOCUS_OPCODES:
        f = decode_focus(opcode, sub, raw, imid)
        if f:
            parts.append(f)
    tgt = branch_target(opcode, raw)
    if tgt is not None:
        parts.append(f"goto +{tgt}")
    if opcode not in FOCUS_OPCODES:
        parts.extend(generic_annotations(opcode, raw, imid))
    return "; ".join(parts)


# --- markdown output ----------------------------------------------------------

def branch_target(opcode, raw):
    """Decoded absolute branch target (offset within the event) for jump opcodes.

    0x01 (set ExecPointer) carries an LE16 target at bytes[1:3]; 0x02 (conditional
    if) carries the on-true jump as its trailing LE16. Both are offsets from the
    event start, so they line up directly with the Offset column.
    """
    if opcode == 0x01 and len(raw) >= 3:
        return raw[1] | (raw[2] << 8)
    if opcode == 0x02 and len(raw) >= 2:
        return raw[-2] | (raw[-1] << 8)
    return None


def md_escape(text):
    return text.replace("|", "\\|").replace("\n", " ").strip()


def instr_flags(opcode, meta):
    """Compact control-flow flags from the docs: B = sets ExecPointer (branch/yield),
    R = sets RetFlag (yields / blocks the stack)."""
    m = meta.get(opcode)
    if not m:
        return ""
    f = ""
    if m.get("exec"):
        f += "B"
    if m.get("retflag"):
        f += "R"
    return f


def build_markdown(dat_path, source_label, ef, selections, meta, show_bytes):
    """selections: list of (block, event) tuples already filtered."""
    out = []
    out.append(f"# Event dump — {source_label}")
    out.append("")
    out.append(f"- **File:** `{dat_path}` ({len(ef['blocks'])} blocks)")
    out.append("- **Flags:** `B` = sets ExecPointer (branch/jump/yield) · "
               "`R` = sets RetFlag (blocks the stack)")
    out.append("- **Decode** mirrors the gameplay module's focus-op decoder "
               "(scheduler/camera) plus ImidData refs, actor magic ids, and embedded text.")
    out.append("")

    for block, ev in selections:
        eid = ev["event_id"]
        imid = block["immediate"]
        wild = " *(wildcard)*" if eid == WILDCARD_EVENT_ID else ""
        out.append(f"## Block {block['index']} · actor `{fmt_actor(block['actor']).strip()}` "
                   f"· event `0x{eid:04X}` ({eid}){wild}")
        out.append("")
        out.append(f"Bytecode offset {ev['offset']}, length {ev['length']} bytes.")
        out.append("")

        header = ["Offset", "Op", "Name", "Sub", "Size", "Flags", "Decode"]
        if show_bytes:
            header.append("Bytes")
        header.append("Description")
        out.append("| " + " | ".join(header) + " |")
        out.append("|" + "|".join(["---"] * len(header)) + "|")

        bytecode = block["event_data"][ev["offset"]:ev["offset"] + ev["length"]]
        for ins in disassemble(bytecode):
            if ins.get("stopped"):
                tail = bytecode[ins["offset"]:]
                note = (f"**STOP** @ opcode `0x{ins['opcode']:02X}` — unsized/overrun; "
                        f"{len(tail)} bytes remain (likely embedded jump table)")
                row = [str(ins["offset"]), f"`0x{ins['opcode']:02X}`",
                       opcode_name(ins["opcode"], meta), "", "", "", ""]
                if show_bytes:
                    row.append(f"`{tail.hex(' ')}`")
                row.append(note)
                out.append("| " + " | ".join(row) + " |")
                break

            op = ins["opcode"]
            decode = decode_instruction(op, ins["subcode"], ins["size"], ins["raw"], imid)
            sub = f"`0x{ins['subcode']:02X}`" if ins["size"] >= 2 else ""
            row = [
                str(ins["offset"]),
                f"`0x{op:02X}`",
                f"**{opcode_name(op, meta)}**",
                sub,
                str(ins["size"]),
                instr_flags(op, meta),
                md_escape(decode),
            ]
            if show_bytes:
                row.append(f"`{ins['raw'].hex(' ')}`")
            row.append(md_escape((meta.get(op) or {}).get("desc", "")))
            out.append("| " + " | ".join(row) + " |")

        out.append("")
        if block["immediate"]:
            imm = " ".join(f"`0x{v:08X}`" for v in block["immediate"])
            out.append("<details><summary>Immediate-data table "
                       f"({len(block['immediate'])})</summary>")
            out.append("")
            out.append(imm)
            out.append("")
            out.append("</details>")
            out.append("")

    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Dump events from a zone event DAT.")
    ap.add_argument("file", nargs="?", help="path to the event DAT (or use --zone)")
    ap.add_argument("--zone", type=parse_int,
                    help="zone id (dec or 0x-hex); resolves the event DAT via FTABLE/VTABLE")
    ap.add_argument("--game-data", dest="game_data",
                    help="game-data root (default: auto-detected by walking up from this script)")
    ap.add_argument("--event", type=parse_int, help="event id to dump (dec or 0x-hex)")
    ap.add_argument("--actor", type=parse_int, help="filter to this actor number")
    ap.add_argument("--block", type=int, help="dump every event in this block index")
    ap.add_argument("--bytes", action="store_true", dest="show_bytes",
                    help="print raw hex for each instruction")
    ap.add_argument("--imm", action="store_true",
                    help="print the block's immediate-data reference table")
    ap.add_argument("--md", nargs="?", const="<auto>", metavar="PATH",
                    help="write a markdown table to PATH (default: auto-named in CWD)")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))

    dat_path = args.file
    if args.zone is not None:
        if args.file is not None:
            print("error: pass either a file path or --zone, not both", file=sys.stderr)
            return 2
        root = args.game_data or find_game_data_root(here)
        if not root:
            print("error: could not locate game-data root; pass --game-data", file=sys.stderr)
            return 2
        file_index, rel = resolve_zone_event_dat(root, args.zone)
        dat_path = os.path.join(root, rel)
        print(f"zone {args.zone} (0x{args.zone:X}) -> file index {file_index} -> {rel}")
        if not os.path.isfile(dat_path):
            print(f"error: resolved event DAT does not exist: {dat_path}", file=sys.stderr)
            return 1
    elif dat_path is None:
        ap.error("provide a DAT path or --zone")

    with open(dat_path, "rb") as f:
        data = f.read()

    try:
        ef = parse_event_file(data, os.path.basename(dat_path))
    except ParseError as e:
        print(f"parse error: {e}", file=sys.stderr)
        return 1

    meta = load_opcode_meta(here)

    print(f"file: {dat_path}  ({len(data)} bytes, {len(ef['blocks'])} blocks)")
    if meta:
        print(f"opcode docs: {len(meta)} opcodes (description + flags) loaded")
    print()

    # No selector: print an index of every block + event and exit.
    if args.event is None and args.block is None:
        for b in ef["blocks"]:
            ids = ", ".join(f"0x{e['event_id']:04X}" for e in b["events"])
            print(f"block {b['index']:>3}  actor {fmt_actor(b['actor'])}  "
                  f"events={len(b['events'])}  imm={len(b['immediate'])}  "
                  f"bytecode={b['data_size']}")
            if b["events"]:
                print(f"           ids: {ids}")
        print("\n(pass --event <id> and/or --block <n> to dump bytecode)")
        return 0

    # Collect the (block, event) selections once; reused by both outputs.
    selections = []
    for b in ef["blocks"]:
        if args.block is not None and b["index"] != args.block:
            continue
        if args.actor is not None and b["actor"] != args.actor:
            continue
        for e in b["events"]:
            if args.event is None or e["event_id"] in (args.event, WILDCARD_EVENT_ID):
                selections.append((b, e))

    if not selections:
        print("no matching events found", file=sys.stderr)
        return 1

    if args.md is not None:
        if args.md == "<auto>":
            if args.zone is not None:
                name = f"zone{args.zone}"
            else:
                name = os.path.splitext(os.path.basename(dat_path))[0]
            if args.event is not None:
                name += f"_event{args.event}"
            out_path = name + ".md"
        else:
            out_path = args.md
        source_label = (f"zone {args.zone}" if args.zone is not None
                        else os.path.basename(dat_path))
        if args.event is not None:
            source_label += f", event 0x{args.event:04X} ({args.event})"
        md = build_markdown(dat_path, source_label, ef, selections, meta, args.show_bytes)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"wrote {out_path}  ({len(selections)} event(s), {len(md)} bytes)")
        return 0

    for b, e in selections:
        print(f"block {b['index']}  actor {fmt_actor(b['actor'])}  "
              f"bytecode={b['data_size']} bytes")
        if args.imm:
            print(f"  immediate[{len(b['immediate'])}]: "
                  + " ".join(f"0x{v:08X}" for v in b["immediate"]))
        print_event(b, e, meta, args.show_bytes)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
