# cexi ui import

Imports edited `.dds` textures from an extracted UI folder back into an FFXI UI
container DAT (`lobb` / `menu` format).

---

## Usage

```
uv run cexi ui import <DAT_FILE> <TEXTURE_DIR> [OPTIONS]
```

Shortcut wrapper:

```
uv run cexi ui simple-import <DAT_FILE> [OPTIONS]
uv run cexi ui si <DAT_FILE> [OPTIONS]
```

`simple-import` / `si` derive the working folder automatically from the DAT path,
rebuild any edited `.png` files in that folder back into `.dds`, and then import
the resulting DDS files into the DAT.

Example:

- `ROM/0/1.DAT -> exports/ui/0/1`
- `ROM/119/50.DAT -> exports/ui/119/50`

| Option | Description |
|---|---|
| `--output-dat PATH` | Write to a new DAT instead of overwriting `DAT_FILE` |
| `--format auto\|dxt1\|dxt3\|dxt5` | DDS compression; `auto` preserves the extracted DDS format |
| `--all-themes` | Window skins only (`ROM/0/14..21`): apply this DAT's edited PNGs to every skin and import each (see below) |

---

## Examples

```bash
# overwrite the original DAT using edited DDS files from the extract folder
uv run cexi ui import ROM/119/50.DAT exports/ui/50

# write to a different DAT path
uv run cexi ui import ROM/119/51.DAT exports/ui/51 --output-dat ROM/119/51_mod.DAT

# simplified PNG->DDS + import flow
uv run cexi ui simple-import ROM/0/1.DAT
uv run cexi ui si ROM/119/50.DAT --output-dat ROM/119/50_mod.DAT
```

If you used `ui sx` / `ui simple-extract`, the matching import step is usually just:

```bash
uv run cexi ui si ROM/0/1.DAT
```

That rebuilds edited PNG files in `exports/ui/0/1` back into DDS and imports them
into `ROM/0/1.DAT`.

## Window skins — `--all-themes`

The 8 window-skin DATs `ROM/0/14`–`ROM/0/21` share the same four texture names
(`newtex`, `hfr1`, `corner`, `vfr1`) — only the colours differ. Edit one skin and
push it to all of them in a single command:

```bash
uv run cexi ui sx "ROM\0\21.DAT"          # extract one skin
# edit exports/ui/0/21/*.png
uv run cexi ui si "ROM\0\21.DAT" --all-themes
```

For each skin `14..21`, it extracts that DAT's current DDS (so `auto` format
matching has a reference), copies your edited PNGs in **by name** (correct despite
each DAT storing the textures in a different order), then converts and imports —
overwriting all 8 DATs. The source skin imports from its own folder.

`--all-themes` only works on the `ROM/0/14..21` set; using it elsewhere errors out.

---

## How matching works

`ui import` looks for `.dds` files using the same filenames produced by
`ui extract`.

- matching files are imported
- missing files are skipped and their DAT entries are left unchanged
- if no matching `.dds` files are found, the command errors

---

## Validation

Each replacement `.dds` must:

- be a classic DDS file with `DXT1`, `DXT3`, or `DXT5` FourCC
- match the original texture dimensions exactly
- have a compressed payload size consistent with its format and dimensions

If a file fails validation, the import stops with an error.
