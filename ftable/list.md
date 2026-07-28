# cexi ftable list

Dump every registered `file_id → DAT path` mapping from all FTABLE/VTABLE tables.

Reads all ROM tables (base + ROM2–ROM9), resolves each `file_id` to its DAT path,
and by default reads the first 4 bytes of each file to show the format magic.
Useful for finding where a DAT lives or auditing the table layout.

---

## Usage

```
uv run cexi ftable list [OPTIONS]
```

| Option | Description |
|---|---|
| `--magic AAAA` | Filter by 4-byte header magic (e.g. `--magic lobb`, `--magic menu`) |
| `--rom N` | Filter to a specific ROM index (1 = base, 2–9 = expansions) |
| `--range MIN-MAX` | Restrict to a file_id range, e.g. `--range 0-200` |
| `--json` | Write `exports/ftable/ftable_list.json` instead of printing |
| `--no-magic` | Skip reading DAT headers (faster for large ranges) |

---

## Examples

```bash
# find all lobb/menu UI DATs
uv run cexi ftable list --magic lobb
uv run cexi ftable list --magic menu

# dump first 200 entries from the base ROM
uv run cexi ftable list --rom 1 --range 0-200

# find all win0 window skin DATs
uv run cexi ftable list --magic win0

# export full list to JSON
uv run cexi ftable list --json
```

---

## Example output

```
 file_id   ROM  DAT path                         magic
------------------------------------------------------------------------
       1      1  ROM/0/1.DAT                      menu
       2      1  ROM/0/2.DAT                      lobb
      14      1  ROM/0/14.DAT                     win0
      15      1  ROM/0/15.DAT                     win0
      ...

47 entries.
```

---

## Notes

- Reading the file header requires the DAT to exist on disk — if `FFXI_DIR` doesn't
  match the installed game, magic values will be missing. Use `--no-magic` if that's
  the case.
- The base ROM (`rom=1`) uses `FTABLE.DAT` / `VTABLE.DAT` in `FFXI_DIR`;
  expansions use `ROMx/FTABLEx.DAT` / `VTABLEx.DAT`.
- Also see `cexi ui list` which uses the pre-scanned `ftable_full_scan.json` for
  faster UI-specific lookups without hitting the filesystem.

---

## Related commands

- **`cexi ftable lookup`** — look up a single file_id to get its DAT path and header
- **`cexi ftable range-scan`** — scan for occupied file_id blocks (retail layout analysis)
- **`cexi ui list`** — list only UI DATs (menu/lobb/win0/sel_) with magic-based filter
