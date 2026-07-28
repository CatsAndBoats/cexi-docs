# cexi dats

`cexi dats` builds reproducible DAT package trees from a JSON manifest. It is the
new home for **new content** and distributable patches.

Use domain commands for existing DAT edits:

```bash
uv run cexi gear export ROM/33/17
uv run cexi gear import ROM/33/17
uv run cexi zone import ROM/1/41 edited.glb
uv run cexi anim import ROM/37/13 poi
```

Use `cexi dats` when the result should be rebuilt from Git and published:

```bash
uv run cexi dats prepare workspaces/foo/zone-changes.json dats/update.json --target ROM10/2/0.DAT
uv run cexi dats plan dats/update.json
uv run cexi dats build dats/update.json
```

---

## Quick start: `cexi dats new` (interactive wizard)

When you **already have the built `.DAT` files** and just want to place them at new
model ids — no `mesh export` / GLB rebuild — run the wizard:

```bash
uv run cexi dats new
```

It walks you through, in order:

1. **Target check.** Reports each live target (`FFXI_DIR`, and `FFXI_PIVOT_DIR` if
   distinct) and whether its `FTABLE` is **expanded** for each content type (with sizes),
   warning about any that aren't:

   ```text
   CatsEyeXI pivot (FFXI_PIVOT_DIR): …\DATs\catseyexi
     FTABLE: 423,152 entries
       ✓ Mounts: file_ids up to 102,768
       ✓ Entity models: custom band from file_id 113,239
       ✓ Gear: window 4095 → needs 423,152 file_ids
   ```

   Mounts fit inside the retail range; **entity** and **gear** need the tables grown
   first with `cexi ftable expand entity` / `cexi ftable expand gear` on that install.

2. **Project name** (type-ahead autocomplete against existing `dats/*.json` names) → writes/updates
   `dats/<slug>.json`. Picking an **existing** project **preloads defaults** from its action of the
   same type — slot, model id, source folder (saved as `source_dir`), destination — so re-running just
   tweaks it, and gear re-uses each slot's destination block (overwrite in place).

3. **Content type** — `Gear`, `Mounts`, `Entity (NPC / Monster / Object)`, or
   `NPC (costume: race + gear + weapons)`.

4. **Type-specific questions** (see below), then it writes the manifest action and offers
   to build (with a dry-run preview first).

### Gear

Point it at a **folder** of gear DATs. It auto-detects each file's **race** and **slot**
and confirms each is a valid gear mesh — filename first (an explicit rename always wins),
then the codes embedded in the DAT's own section names:

- **Race**: filename prefix (`hm`, `hf`, `em`, `ef`, `tm`, `tf`, `m`, `g`;
  case-insensitive), else the race code inside the DAT (`1em_…` model / `em_…` texture
  headers).
- **Slot**: a slot word anywhere in the filename (`Loxley Hands.DAT`, `helm`, `boots`,
  …), else the slot digit FFXI puts ahead of the race code in the 0x01 model header
  (`1em_` = head). Weapons don't carry the digit, so main/sub/ranged fall back to the
  slot prompt.

```text
Found 5 .DAT Files:
- Elvaan Male - hands - 100 - Loxley Hands.DAT
- Elvaan Male - feet - 110 - Loxley Feet.DAT
  ...
>> Are these correct? [Y/n]
```

A folder can therefore hold a **full set** (one race, many slots), a per-race pack
(one slot, many races), or any mix — the wizard writes **one manifest action per slot**
(`gear.<project>.<slot>`) and the build places them all in one pass. If no slot is
detectable anywhere (e.g. weapons), it asks once, like before.

- A bare **`t`/`taru`** DAT is bound to **both** Taru genders automatically (they share
  one skeleton), each getting its own destination file + file_id.
- You then pick a destination ROM folder (e.g. `rom10/20` — filenames are auto-numbered
  into the first free consecutive block, one block per slot) and a single model id
  (recommend `3000+`) shared by the whole set — each slot has its own file_id window,
  so a set can sit at the same id in every slot.
- **Requires** `cexi ftable expand gear` first (per-race windowed file_ids).

### Mounts

Source DAT + destination DAT + mount id (recommend `39–63`, menu-visible) + optional key
item (EN/JP name & description). Reuses the mount record machinery (model + name/help +
key-item d_msg + server snippet).

### Entity

Source DAT + destination DAT + model id (recommend `20000+`;
`file_id = model_id + 98239`).

### NPC (costume — bake from race + gear + weapons)

Unlike the other types, this one has no prebuilt DAT to place — it **bakes one**. You pick
a **race + gender**, a **face**, and (optionally) a **DAT per armour slot** (head / body /
hands / legs / feet — skip a slot to use the race's naked base part) and **main / sub weapon
DATs**. The wizard flattens all of that into a single self-contained entity DAT at
`dats/custom/<project>.dat` — the same shape as retail "costume" NPCs such as `ROM/261/56`
(race skeleton `0x29` + every gear mesh `0x2A` + textures `0x20` + `wlk/idl/run` locomotion +
`mou4/eye3` face anims + `Info`). It then falls into the **Entity** flow (destination DAT +
model id) with that baked DAT as the source, so `dats build` places it like any other entity.

Pieces are pulled from the game's own data — race skeleton + part-0 locomotion + face anims
from the race-config DAT, part-1/2 locomotion via the `FFXiMain.dll` motion tables, face/gear
meshes via the gear tables (model id `0` = naked base). The **weapon mesh** is included;
weapon-typed **battle / weapon-skill** motions are a planned follow-up (the weapon's
`weaponAnimationType` is already read and recorded). Registering the baked model as a live
zone NPC is separate — use the editor's **Custom NPCs** browser or the `custom-npc` registry.
See [../entity/npc-look.md](../entity/npc-look.md).

---

## Building (`cexi dats build`)

A build writes the DATs and patches their file_ids **directly into one or more live
targets** — the CatsEyeXI pivot overlay (`FFXI_PIVOT_DIR`, default), the base install
(`FFXI_DIR`), and/or the HD overlay (`FFXI_HD_DIR`). There is no intermediate pack.

```bash
uv run cexi dats build --project gyokko_mask                    # into FFXI_PIVOT_DIR (default)
uv run cexi dats build --project gyokko_mask --target dir       # into FFXI_DIR instead
uv run cexi dats build --project gyokko_mask --target pivot,hd  # into both (comma-separated)
uv run cexi dats build --project gyokko_mask --dry-run          # preview only, writes nothing
```

A target with **no FTABLE** (the HD overlay is one) is a **DAT-only** drop — the DAT is
placed there but the file_id is registered in another target's tables (XIPivot resolves the
file_id via whichever overlay has the tables, then finds the DAT in the stack). At least one
chosen target must have tables.

- The target's `FTABLE`/`VTABLE` **must already exist and be expanded** for the custom
  models you're placing — run `cexi ftable expand entity` / `cexi ftable expand gear` on
  that install first. The wizard's opening step reports each target's expansion status.
- Each table is backed up once to `<name>.base` before the first patch (recoverable via
  `cexi ftable reset`).
- **`--dry-run`** prints the full per-DAT placement plan (every race for gear) and any
  file_id collisions, without touching disk.

The free-block finder for gear scans both `FFXI_DIR` and `FFXI_PIVOT_DIR`, so deleting a
project's DATs from the live install frees those slots again.

---

## Packaging for distribution (`cexi dats package`)

```bash
uv run cexi dats package gyokko_mask               # prompts which target to read from
uv run cexi dats package gyokko_mask --from pivot  # or name it (dir | pivot | hd)
```

You pick **one** source target (the prompt tags whichever the project was built into). Each
build records the targets it wrote to on every action's `result.targets`, so the manifest
tracks where a project has been deployed.

Zips, from the chosen target, everything needed to run one project as an overlay:

- every DAT the project's actions placed (read from each action's inline `result` — all
  per-race DATs for gear), plus the mount name/help/key-item string DATs for mount actions,
- the full `FTABLE`/`VTABLE` set (so the new file_ids resolve).

Files are laid out ROM-relative inside the zip, so it drops straight into an XIPivot overlay
folder. Build the project into that target first.

## Package layout

```text
dats/
  update.json
  locks.json
  resources/
    zone/
    mount/
    gear/
    mesh/
    anim/
    audio/
    tex/
    ui/
    event/
  catseyexi/
    FTABLE.DAT
    VTABLE.DAT
    ROM10/
      FTABLE10.DAT
      VTABLE10.DAT
      ...
  ffxi-hd/
    ROM/
    ROM10/
```

- `dats/resources` is the source tree you commit: GLBs, PNGs, `zone-changes.json`, imported JSON, mount DATs, etc.
- `dats/catseyexi` is the standard DAT output tree.
- `dats/ffxi-hd` is the HD DAT output tree.
- **Results are recorded inline** on each action (`action["result"]` = model_id → file_id → DAT,
  per-race `placements` for gear), so the manifest is self-describing. `cexi dats new` and
  `cexi dats build` write it; re-running just overwrites the same key (no duplicates, no side
  `*_changelog.json` file).

## Manifest

`dats/update.json` follows [`schema/package.json`](../../schema/package.json).
Individual action schemas live in [`schema/`](../../schema/).

Minimal zone action:

```json
{
  "schema": "cexi.dats.v1",
  "name": "catseyexi-update",
  "version": 1,
  "roots": {
    "standard": "dats/catseyexi",
    "hd": "dats/ffxi-hd",
    "resources": "dats/resources",
    "locks": "dats/locks.json"
  },
  "actions": [
    {
      "id": "zone.byakko_hideout",
      "type": "zone",
      "op": "update",
      "target": {"dat": "ROM10/2/0.DAT", "zone_id": 450},
      "resources": {"changes": "zone/byakko_hideout/zone-changes.json"},
      "options": {"apply_standard": true, "apply_hd": true}
    }
  ]
}
```

Minimal mount action source for `cexi dats prepare workspaces/cyakko/mount.json`:

```json
{
  "id": "mount.cyakko",
  "type": "mount",
  "op": "inject",
  "target": {"mount_id": 50, "model_dat": "auto"},
  "resources": {"model_dat": "model.DAT"},
  "text": {"name_en": "Cyakko", "key_item_name_en": "Cyakko Companion"},
  "server": {"emit": true}
}
```

Minimal mesh action source for `cexi dats prepare workspaces/crab/mesh.json`:

```json
{
  "id": "mesh.crab_custom",
  "type": "mesh",
  "op": "update",
  "target": {"dat": "ROM/128/79.DAT"},
  "resources": {"mesh": "crab.glb"}
}
```

For full action JSON, `prepare` preserves the action fields and copies referenced
resource files that live next to the source JSON into `dats/resources/<type>/<id>/`.

## Commands

| Command | What it does |
|---|---|
| `cexi dats new` | **Interactive wizard** — place prebuilt DATs (gear/mount/entity) at new model ids and write a manifest action |
| `cexi dats build [manifest]` | Build the manifest directly into one or more live targets (`--target pivot,dir,hd`; default `pivot`); `--dry-run` previews |
| `cexi dats package <project>` | Zip the project's built DATs + F/V tables (`--from pivot`/`dir`/`hd`) into `dats/packages/<project>.zip` (ROM-relative, XIPivot-ready) |
| `cexi dats release <project>` | Stage the project's DATs + full FTABLE/VTABLE set + patched `FFXiMain.dll` into `<release>\Game\FINAL FANTASY XI\…` (a launcher build folder). Prompts for the folder; `--to <path>`, `--no-dll` |
| `cexi dats undo <project>` | Reverse a build: delete the placed DATs + clear their file_id entries in every target it was built into, then remove the manifest (`--keep-json` keeps it) |
| `cexi dats json [manifest]` | Print the normalized manifest JSON |
| `cexi dats prepare <source> [manifest]` | Copy an exported JSON/change-set into `dats/resources` and add an action |
| `cexi dats changelog [manifest]` | Table of each action's recorded inline `result` (model_id → file_id → DAT) |

> Note: `new`/`build` write DATs + table patches straight into the chosen live target
> (`FFXI_DIR` or `FFXI_PIVOT_DIR`), while `zone` actions still build the
> `dats/catseyexi` + `dats/ffxi-hd` package trees described below.

## Current builders

Verbatim-placement types (written by `cexi dats new`, built into the live target):

- `gear`: places one prebuilt gear DAT per race at a windowed custom gear file_id
  (`gear.xi_inject.custom_fid`). Needs `cexi ftable expand gear`.
- `entity`: places a prebuilt entity DAT at `file_id = model_id + 98239`. The **NPC costume**
  wizard also emits an `entity` action — it first *bakes* the DAT it places
  (`entity.xi_bake_npc`, source `dats/custom/<project>.dat`).
- `mount`: places the model DAT at the chosen path, writes EN/JP name/help + optional
  key-item d_msg overrides, registers the file_id, and emits a server snippet.

GLB-rebuild / package types:

- `mesh`: rebuilds an existing model DAT's geometry from an edited GLB into the target.
- `zone`: applies one `zone-changes.json` to the `dats/catseyexi` standard tree and
  optionally the `dats/ffxi-hd` tree.

Other action schemas are present so package shape is stable, but their builders are
added incrementally.
