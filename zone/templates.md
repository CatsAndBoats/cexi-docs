# Zone templates (`cexi zone new --template`)

Custom zones are stamped from a **pre-baked template DAT**. There are two kinds:

| Template | Source zone | Root | Sky in-game? |
|----------|-------------|------|--------------|
| `indoor` | Altar Room (ROM/0/64) | `d_oz` | no — enclosed room |
| `desert` | Eastern Altepa Desert (ROM2/0/1) | `f_ri` | yes |
| `snow`   | Xarcabard (ROM/0/57) | `f_xa` | yes |
| `jungle` | Yhoator Jungle (ROM2/0/5) | `f_yu` | yes |
| `fields` | La Theine Plateau (ROM/0/115) | `f_la` | yes |
| `city`   | Lower Jeuno (ROM/1/41) | `t_ju` | yes |

```
cexi zone new --template desert --name "My Desert"      # outdoor, sky renders in-game
cexi zone new --name "My Room"                          # indoor (default), no sky
```

The asset DATs live in `web/leveleditor/assets/` (`new.dat` for indoor, `template_<biome>.dat`
for the rest). The template→source-zone map is `TEMPLATES`/`TEMPLATE_DONOR` in
[`src/cexi/zone/xi_new.py`](../../src/cexi/zone/xi_new.py).

## Why an outdoor base is required for the sky

The retail client renders a zone's sky from data **inside the zone DAT** (the `0x2F` env +
sky meshes under the `weat/` directory subtree) **but only treats the zone as outdoor when it
was built from a real outdoor zone** — the indoor Altar husk (`d_oz`, no top-level `0x36`
ZoneInteractions) is treated as indoor and the sky is skipped, even though the env bytes are
identical to a working zone. Splicing a sky into the indoor template (`--sky`) makes it show
in the *editor* (which draws sky by mesh name) but **not in-game**. So outdoor zones must start
from an actual outdoor zone. See [format.md](format.md) and the memory note `sky-not-visible-ingame`.

## Building the templates — `research/build_biome_templates.py`

Each outdoor template is a real zone blanked to a flat floor while keeping its sky + outdoor
structure. The recipe (proven; do NOT reorder steps 4/5):

1. **copy** the source zone DAT
2. **strip sound** (`0x3D`) only — KEEP `0x05` effect generators (they **draw the sky meshes**;
   stripping them leaves the env gradient but no moon/clouds/sun)
3. **inject** the flat floor mesh (`new_floor.glb`)
4. **clear** the source's hilly walkable collision (`clear_zone_collision`) then **add** the
   flat floor collision. `clear_collision` now **PRESERVES the per-object cull transforms** —
   wiping them (the old behaviour) leaves the surviving placements pointing at a 0-length
   transform array → the engine culler reads a garbage cull volume → **instant crash** on large
   outdoor (v21+) zones. ([xi_collision.py](../../src/cexi/zone/xi_collision.py))
5. **blank** every original placement (objects invisible) + register the floor — done AFTER the
   collision rewrite, because `add_placements` appends the floor's quadtree leaf-index list at
   the section payload end and the collision rewrite (`sec[:coll_rel]+region`) would TRUNCATE
   anything after it → a dangling leaf `idx_ref` → instant crash in `InitializeQuadTreeNode`.
6. **purge** the terrain meshes/textures OUTSIDE `weat` — the base ground is drawn DIRECTLY from
   `0x2E` sections (not via placements), so blanking placements does NOT hide it; only removing
   the sections does. KEEP the `weat` sky + the `0x36` outdoor marker + the floor.

Every build is **offline-validated** before shipping: quadtree leaves in-bounds, collision
`idxCount == node_count`, cull transforms preserved (≈ node_count), and root/`weat`/sky/floor
present. A build that fails any check is reported FAIL and not used.

### Add a new biome

Add a row to `BIOMES` in `research/build_biome_templates.py` (`biome: (ROM-path, donor_zoneid)`),
re-run it, then add the same key to `TEMPLATES` + `TEMPLATE_DONOR` in `xi_new.py`. The source must
be a real outdoor/town zone with a `weat/` subtree (verify: `f_`/`t_` root, sky meshes under weat).

## Server side — the DB migration

`cexi zone new` writes `zone-migration.sql` to the workspace and (by default) **auto-applies it**
to the dev DB. It **clones the template's donor zone's** `zone_settings` + `zone_weather` rows
(overriding id/name/ip/port), so the custom zone inherits a known-good outdoor config + weather
rotation — which the server must send for the dynamic sky/weather to run. See
[import-json.md](import-json.md) and the DB creds in
[`xi_config.py`](../../src/cexi/xi_config.py) (`CEXI_DB_*`, `CEXI_DB_AUTOAPPLY`). **The map server
must be restarted** to load a newly-added zone's weather config.

## Known limitations

- **Collision** is a flat floor at origin; the source zone's terrain is invisible but removed, so
  walking off the floor edge has no ground. Add your own collision via the editor.
- **Water/sea** from the source zone is intentionally dropped (it references resources tied to that
  zone's layout) — add water as its own placeable feature, not baked into the base.
- **Spawn point** is server-side (not in the DAT); set it via the server (GM `!pos`, or a zone
  script's onZoneIn). `zone_settings` has no x/y/z column.
