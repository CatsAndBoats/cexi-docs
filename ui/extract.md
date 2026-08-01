# cexi ui extract → removed

There is **no** `cexi ui extract` command. Texture export is:

```
uv run cexi ui tex export <DAT_FILE> [OPTIONS]
```

Shortcuts (registered names only):

```
uv run cexi ui tex sx <DAT_FILE>   # export DDS + convert to PNG
uv run cexi ui tex si <DAT_FILE>   # PNG → DDS + import
```

See **[export.md](export.md)** for full usage, inventories, and format notes.
