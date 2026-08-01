# cexi ftable list

Dump every registered `file_id → DAT path` mapping from all FTABLE/VTABLE tables.

> **Hidden command.** `cexi ftable list` is registered but **hidden** from `--help`.
> The public JSON surface is **`cexi ftable json`** (same filters; use that in scripts).

Reads all ROM tables (base + ROM2–ROM9) and resolves each `file_id` to its DAT path.
**Headers are off by default** — path listing only; the command does **not** open DAT
files unless you pass `--header-read` or `--header`. Flags are `--header` /
`--header-read` (not `--magic` / `--no-magic` — those belong to `cexi ui tex list`).

---

## Usage

```
uv run cexi ftable list [OPTIONS]
```

| Option | Description |
|---|---|
| `--header AAAA` | Filter by the DAT's 4-byte file header (e.g. `--header lobb`, `--header menu`). Forces a header read per file. |
| `--header-read` | Also read each DAT's file header (slower: opens every matching DAT on disk). Implied by `--header`. |
| `--rom N` | Filter to a specific ROM index (1 = base, 2–9 = expansions) |
| `--range MIN-MAX` | Restrict to a file_id range, e.g. `--range 0-200` |
| `--json` | Write `exports/ftable/ftable_list.json` instead of printing |
| `--progress` | Print scan progress to stderr (useful for unfiltered scans) |

---

## Examples

```bash
# find all lobb/menu UI DATs (opens each DAT for the 4-byte header)
uv run cexi ftable list --header lobb
uv run cexi ftable list --header menu

# dump first 200 entries from the base ROM (paths only — no DAT open)
uv run cexi ftable list --rom 1 --range 0-200

# find all win0 window skin DATs
uv run cexi ftable list --header win0

# paths + headers for a range without filtering by a specific header
uv run cexi ftable list --range 0-200 --header-read

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

(Header column only appears with `--header` / `--header-read`.)

---

## Notes

- Default listing never opens DATs — only FTABLE/VTABLE. Header reads require the
  DAT to exist on disk; if `FFXI_DIR` doesn't match the installed game, header
  values will be missing.
- The base ROM (`rom=1`) uses `FTABLE.DAT` / `VTABLE.DAT` in `FFXI_DIR`;
  expansions use `ROMx/FTABLEx.DAT` / `VTABLEx.DAT`.
- Also see `cexi ui tex list` which uses the pre-scanned `ftable_full_scan.json` for
  faster UI-specific lookups without hitting the filesystem.

---

## Related commands

- **`cexi ftable json`** — public JSON listing (preferred over hidden `list`)
- **`cexi ftable lookup`** — look up a single file_id to get its DAT path and header
- **`cexi ftable range-scan`** — scan for occupied file_id blocks (retail layout analysis)
- **`cexi ftable compare`** — diff registered file_ids between two FTABLE roots
- **`cexi ui tex list`** — list only UI DATs (menu/lobb/win0/sel_) with `--magic` filter
