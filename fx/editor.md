# cexi gui weapon

Serve the browser-based **particle-effect editor** — a local web UI for inspecting
and tweaking `0x05` effects against your game install.

The command locates the bundled `web/particleeditor` files, creates a `game/` symlink
pointing at `FFXI_DIR` (so the editor can fetch DATs as `game/ROM/…` URLs), starts a
local HTTP server, and opens it in your browser.

---

## Usage

```
uv run cexi gui weapon [OPTIONS]
```

| Option | Default | Description |
|---|---|---|
| `--port`, `-p` | `8776` | Port to serve the editor on |
| `--host` | `0.0.0.0` | Host / interface to bind |
| `--open / --no-open` | `--open` | Open the editor in the default browser |
| `--directory PATH` | bundled | Directory with the editor web files (overrides `$CEXI_PARTICLE_EDITOR_DIR` and the bundled `web/particleeditor`) |

---

## Examples

```bash
# serve on the default port and open the browser
uv run cexi gui weapon

# pick a port and don't auto-open
uv run cexi gui weapon --port 9000 --no-open

# point at a custom web build
uv run cexi gui weapon --directory ./web/particleeditor
```

---

## Notes

- The editor reads DATs from your **game install** via the `game/` symlink it creates
  next to the web files, resolved from `FFXI_DIR`. If `FFXI_DIR` is unset, no symlink
  is created and DAT fetches won't resolve.
- **On Windows**, creating the symlink requires Administrator rights or Developer Mode.
  If it fails, the command prints a `mklink /D` line you can run manually.
- The editor web files are found via, in order: `$CEXI_PARTICLE_EDITOR_DIR`, then the
  first `web/particleeditor` directory walking up from the module (works from a source
  tree or a packaged install).
- This mirrors [`cexi gui zone`](../zone/README.md) (the level editor); the two are
  separate web apps on separate default ports.

---

## Related commands

- **[`cexi fx json`](json.md)** / **[`cexi fx set`](set.md)** — the CLI equivalents for
  reading and editing effect params without the browser UI
- **[`cexi fx export`](export.md)** — pull an effect's mesh + texture out to disk
