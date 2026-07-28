# cexi model json --free

Scans the custom entity model range (monsters, NPCs, objects) (modelid 15,000–20,000) across all
FTABLE/VTABLE pairs and reports:

- the next free modelid and its file_id
- the `mob_pools` binary blob ready to paste
- a summary of how many slots are used vs remaining
- a table of all currently registered custom entries

Run this before assigning custom model IDs manually, or after `cexi ftable
delete` to confirm a slot was freed. New reproducible packages should prefer
`cexi dats build`, which stores allocations in `dats/locks.json`.

---

## Usage

```
uv run cexi model json --free
```

No options.

---

## Example output

```
==============================================================
  FFXI Custom Monster Model - Next Available Slot
==============================================================

  Next free model ID : 15000
  File ID            : 113239  (modelid + 98239)
  mob_pools blob     : 0x0000983A00000000000000000000000000000000

  Custom range       : modelid 15000 - 20000
  Slots used         : 0
  Slots remaining    : 5001

  No custom slots registered yet.

  To package new content:  cexi dats prepare ... && cexi dats build

==============================================================
```

With some slots in use:

```
  Registered custom slots:
  --------  --------  -----  ------------------------------
   modelid   file_id    rom  dat
  --------  --------  -----  ------------------------------
     15000    113239  ROM10  ROM10/1/0.DAT
     15001    113240  ROM10  ROM10/1/1.DAT
```

---

## The mob_pools blob

The `mob_pools blob` value is the 20-byte `look_t` binary literal for the
`mob_pools.modelid` column. Paste it directly into SQL:

```sql
UPDATE mob_pools SET modelid = 0x0000983A00000000000000000000000000000000 WHERE poolid = 25000;
```

The format is:
```
bytes 0–1  : uint16 LE  size    = 0  (monster type, not humanoid)
bytes 2–3  : uint16 LE  modelid = <modelid>
bytes 4–19 : zeros       (equipment slots, unused for monsters)
```

→ See [../dats/README.md](../dats/README.md) for the reproducible package flow.

---

## Why the range is 15,000 – 20,000

The last retail monster modelid is **11,241** (file_id 109,480). The custom
range starts at **15,000** — giving a ~3,758-slot buffer above the retail cap
to absorb any future retail expansion without collision. The upper bound of
20,000 is simply the default FTABLE expansion size (118,240 entries):

```
max_file_id  = 118240 - 1 = 118239
max_modelid  = 118239 - 98239 = 20000
```

It is not a hard limit — expand to a higher `--target-modelid` and the ceiling
rises with it (also bump `MODEL_SAFE_END` in `src/cexi/entity/xi_core.py`).

→ See [reference/model-file-ids.md](../reference/model-file-ids.md) for the
full custom range derivation and the file_id space map.

→ If the range is full, run `cexi ftable expand --target-modelid 30000` (or
higher) and the range ceiling will rise accordingly. See
[ftable/expand.md](../ftable/expand.md).

---

## Related commands

- **`cexi dats build`** — package/register new content from a manifest
- **`cexi ftable delete`** — free a slot if you need to replace a model
- **`cexi model json`** — full dump of all registered models (retail + custom)
