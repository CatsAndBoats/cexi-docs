# `cexi tex` — DAT textures (extract / repaint / reimport)

Decode `0x20` texture sections to PNG, edit them, and re-encode back into the DAT.
Works on **any** DAT (zone, entity, …). Three commands:

```
cexi tex list   <dat>                 # list textures: fourcc, name, WxH, size
cexi tex export <dat> [name...]       # decode -> PNG (exports/tex/<rom>/)
cexi tex import <dat> [png...]        # re-encode edited PNG(s) back in (matched by name)
```

`<dat>` is a path or ROM spec like `ROM/1/41`. Implemented in the `src/cexi/tex/` package (`core.py` shared; `xi_list.py` / `xi_export.py` / `xi_import.py` per command).

## Workflow (e.g. repaint the fountain splash)

```sh
uv run cexi tex export ROM/1/41 funsui      # -> exports/tex/rom/1/41/funsui_sib1.png  (+ abuk/umi02/tare)
# …edit funsui_sib1.png in any image editor (keep its size/name)…
uv run cexi tex import ROM/1/41              # re-imports every PNG in that folder, by name
```

## How it works

- Textures are `0x20` sections. `tex list`/`export` decode them (DXT or palettized)
  to RGBA PNG via the same decoder used by zone/entity export.
- The export path is **auto-derived from the DAT's ROM path** (`exports/tex/rom/1/41/`),
  so it's the same regardless of DAT type — no zone-vs-entity confusion.
- PNGs are named after the texture's stored name (whitespace → `_`, e.g.
  `funsui  sib1` → `funsui_sib1.png`). `tex import` matches each PNG back to its
  section **by that name** — just edit the PNGs and run import, no manual mapping.
- With no PNG args, `tex import` imports every `*.png` in `exports/tex/<rom>/`
  (or `--dir`). Specific files: `tex import <dat> a.png b.png`.
- A `<dat>.base` backup is kept (shared with `zone import` / `fx`).

## Caveats

- **Re-encoded as DXT** (`0xA1`): DXT3 if the PNG has an alpha channel, else DXT1.
  Originals that were palettized are replaced by DXT — visually equivalent, but the
  section size changes (the DAT is spliced/rebuilt, all sections preserved).
- Requires **texconv** for the PNG→DDS step (same dependency as `entity mesh import`).
- Keep the PNG's dimensions sensible (power-of-two; same size as the original is
  safest). The texture name is preserved from the original section so mesh/effect
  references still resolve.

## Related

- [fx.md](fx.md) — effects reference the textures shown here (e.g. the fountain
  spray `tki` uses `funsui_sib1` via the `sibj` mesh).
- `cexi utils dds2png` / `png2dds` — lower-level single-file conversion.
