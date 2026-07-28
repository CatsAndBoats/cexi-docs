# Gear Inject Legacy

`cexi gear inject` is a hidden compatibility command. New distributable content
should be represented as `cexi dats` package actions as builders become available.

Create new gear model IDs with recolored textures. Unlike `gear edit`
(which overwrites the existing model via overlay), `gear inject` creates
a completely separate model_id so the original gear is unaffected.

## Prerequisites

1. **FTABLE expansion**: `cexi ftable expand` must have been run first
2. **Gear setup**: `cexi gear setup` (one-time, expands FTABLEs further
   and copies original armor DATs to ROM10)
3. **gearpatch addon**: Must be loaded in the Ashita client — the addon
   patches the gear lookup tables in memory at runtime

## Quick start

```bash
# One-time setup
cexi gear setup

# Inject a red Ridill (model 259 = Ridill)
cexi gear inject HumeMale main 259 --tint "#ff0000" --blend multiply

# Inject a green body armour
cexi gear inject HumeMale body 5 --hue 120
```

Then in SQL:
```sql
UPDATE item_equipment SET MId = 1196 WHERE itemId = 16555;
```

In-game: load the addon, restart the server, equip the item.
```
/addon load gearpatch
```

## How it works

### The problem

FFXI's gear lookup tables are hardcoded in FFXiMain.dll — 8 races, each
with 9 equipment slots, each with up to 6 groups mapping contiguous
model_id ranges to file_ids. All group slots for armor are full (6/6),
and the file_id ranges are packed with zero gaps.

Static DLL file patching does not work — the .data section values are
overwritten or ignored at runtime.

### The solution (three parts)

1. **`cexi gear setup`** (run once on the server/client machine):
   - Expands all FTABLEs from 118,240 to 126,552 entries
   - Copies 2,520 existing armor G5 DATs from ROM to ROM10
   - Registers new file_ids in all FTABLE/VTABLE pairs

2. **`cexi gear inject`** (run per custom model):
   - Recolors a source gear DAT
   - Places the result in ROM10
   - Registers the file_id in FTABLE/VTABLE
   - Assigns and tracks model_ids via state file

3. **`gearpatch` Ashita addon** (loaded at runtime):
   - Finds gear tables in FFXiMain.dll memory via pattern matching
   - Patches 72 group entries across all races and slots
   - Restores originals on unload

### Gear table structure (RE)

Located at file offset `0x34C80` in FFXiMain.dll (VA `0x1035B880`).
Race pointer array at `0x36784` (9 pointers, index 0 = fallback).

Each race table is 432 bytes: 9 slots x 6 groups x 8 bytes per group.
Each group: `base_file_id` (uint32) + `count` (uint32).

| Slot | Groups Used | Injection Strategy |
|------|------------|-------------------|
| face | 1/6 | Add G1 (new group) |
| head/body/hands/legs/feet | 6/6 | Relocate G5 to ROM10 |
| main/sub | 5/6 (G5=skip) | Replace G5 skip with ROM10 group |
| ranged | 1/6 | Add G1 (new group) |

### File_id allocation

Custom gear file_ids start at 118,240 (above entity model range) to
avoid collisions with entity models (file_ids 113,239–118,239).

| Slot type | File_id range | Model_id range | Per race |
|-----------|--------------|----------------|----------|
| Armor (x5) | 118,240–123,359 | 672–735 | 128 each |
| Weapons (x2) | 123,440–125,487 | 1,196–1,323 | 128 each |
| Face | 125,740–125,995 | 32–63 | 32 each |
| Ranged | 126,040–126,551 | 256–319 | 64 each |

## Custom model_id ranges

| Slot | Range | Capacity per race |
|------|-------|-------------------|
| face | 32–63 | 32 |
| head | 672–735 | 64 (first 64 are relocated originals) |
| body | 672–735 | 64 |
| hands | 672–735 | 64 |
| legs | 672–735 | 64 |
| feet | 672–735 | 64 |
| main | 1,196–1,323 | 128 |
| sub | 1,196–1,323 | 128 |
| ranged | 256–319 | 64 |

## Recolour options

Same as `cexi gear edit` (shared option-set):

| Option | Description |
|--------|-------------|
| `--hue N` | Hue shift (0–360) |
| `--saturation N` | Saturation adjust (-100 to 100) |
| `--lightness N` | Brightness adjust (-100 to 100) |
| `--tint "#RRGGBBAA"` | Tint colour |
| `--blend MODE` | normal, multiply, screen, overlay, add |
| `--hue-min/max` | Colour range targeting (hue) |
| `--sat-min/max` | Colour range targeting (saturation) |
| `--val-min/max` | Colour range targeting (brightness) |
| `--afterglow "#RRGGBB"` | Add afterglow particle aura (weapons only) |
| `--effects-from DAT` | Copy particle effects from another weapon DAT |
| `--particle-config FILE` | Apply particle editor JSON config |

## Particle Effects

### Swap effects from another weapon

Copy particle effects (glows, flames, distortions) from one weapon onto
another. The target weapon keeps its 3D model but gets the source weapon's
particle system.

```bash
# Put Ragnarok AG's afterglow particles on Ridill
cexi gear inject HumeMale main 259 --effects-from ROM/352/107.DAT

# Combine with recoloring
cexi gear inject HumeMale main 259 --hue 200 --effects-from ROM/352/107.DAT
```

### Particle editor config

The web-based particle editor (`web/particleeditor/`) exports a JSON config
that captures the full weapon setup — model tinting, effects source, and
per-emitter particle overrides. Pass it directly to `inject`:

```bash
cexi gear inject HumeMale main 259 --particle-config ridill_config.json
```

The config file includes all settings (hue, saturation, tint, effects
source, particle overrides). CLI flags override config file values when
both are specified.

### Per-emitter overrides

The `particle_overrides` array in the config file modifies individual
particle generators within the weapon DAT. Each entry targets a generator
by its section ID and applies multipliers/adjustments to its opcode data.

| Override | Effect |
|----------|--------|
| `emissionRate` | Multiply emission frequency (2.0 = twice as fast) |
| `lifetime` | Multiply particle lifetime |
| `speed` | Multiply velocity and variance |
| `scale` | Multiply particle scale |
| `spread` | Multiply position spread radius |
| `hue` | Hue shift in degrees (0–360) |
| `color` | RGB multipliers `[r, g, b]` |
| `alpha` | Alpha multiplier |
| `enabled` | Set to `false` to disable a generator |
| `custom_texture` | Replace particle texture with custom PNG (base64) |

Custom textures are exported from the particle editor as base64-encoded
PNG in the config JSON. Requires **Pillow** (`uv add Pillow`) for
encoding to FFXI's DXT/paletted texture format.

## Afterglow

The `--afterglow` option wraps a weapon DAT with the relic afterglow
particle aura — the same glowing effect seen on completed relic/mythic
weapons. The hex color controls the glow tint.

```bash
# Blue afterglow Ridill
cexi gear inject HumeMale main 259 --afterglow "#3380ff"

# Red afterglow with recolored blade
cexi gear inject HumeMale main 259 --afterglow "#ff3300" --hue 0 --tint "#ff2200cc" --blend multiply

# Purple afterglow Ragnarok
cexi gear inject HumeMale main 319 --afterglow "#bb33ff"
```

The afterglow is applied after recoloring, so you can combine both.
See `docs/entity/recolor.md` for full afterglow details and color
reference.

## Server-side setup

After injecting, update `item_equipment.MId` for the target item:

```sql
-- Find the item
SELECT itemId, name, MId FROM item_basic b
JOIN item_equipment e ON e.itemId = b.itemid
WHERE name LIKE '%ridill%';

-- Set custom model
UPDATE item_equipment SET MId = 1196 WHERE itemId = 16555;
```

**Important**: The server must be restarted after changing `item_equipment.MId`.
The player must re-equip the item for `char_look` to update.

## gearpatch addon

Located in `addons/gearpatch/`. Copy to your Ashita addons directory.

### Commands

| Command | Description |
|---------|-------------|
| `/gearpatch status` | Show patch state and table address |
| `/gearpatch verify` | Check all 72 patches are still applied |
| `/gearpatch repatch` | Restore originals and re-apply patches |

### How it works

The addon uses `ashita.memory.find` to locate the gear tables in the
loaded FFXiMain.dll memory image via a 16-byte signature (HumeMale head
G0+G1). It then writes new base_fid and count values to 72 group
entries using `ashita.memory.write_uint8`.

On unload, all original values are restored.

### Without the addon

Custom model_ids (672+, 1196+, etc.) are not in the vanilla gear
tables, so the client cannot resolve them to file_ids. Equipment with
custom model_ids will be **invisible** — the weapon/armour simply
won't render.

## Races

All 8 races are supported. Each race needs its own injected model:

| Race | Name |
|------|------|
| HumeMale | Hume Male |
| HumeFemale | Hume Female |
| ElvaanMale | Elvaan Male |
| ElvaanFemale | Elvaan Female |
| TaruMale | Tarutaru Male |
| TaruFemale | Tarutaru Female |
| Mithra | Mithra |
| Galka | Galka |

## Limitations

- Gear models are per-race — inject each race separately
- Custom model_ids are only visible to clients running the gearpatch addon
- Armor slots have 64 custom models per race (after 64 relocated originals)
- Weapon slots have 128 custom models per race
- Face has 32 custom models per race
- Ranged has 64 custom models per race
