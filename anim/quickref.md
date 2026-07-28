# anim — quick reference

Copy-paste commands for the common animation tasks. `<dat>` is a ROM-relative spec
(`ROM9/25/40`, trailing `.DAT` optional) or a file path. Full docs:
[export.md](export.md) · [import.md](import.md) · [emotes.md](emotes.md) ·
[format.md](format.md).

> The command group is **`cexi anim`** (top-level). The old `cexi entity anim` was
> removed — just use `cexi anim`.

## List / inspect

```bash
uv run cexi anim list  <dat>                 # every track: name, frames, joints, seconds
uv run cexi anim json  <dat> --anim idl      # one track's channels as JSON
```

## Export (to glTF for Blender / C4D)

```bash
uv run cexi anim export <dat> --anim idl              # → exports/anim/<rom>/<stem>_idl/  (+ textures)
uv run cexi anim export <dat> --anim idl --fbx        # also bake an animated .fbx
uv run cexi anim export <dat> --anim idl --no-tex     # geometry only, no PNGs
uv run cexi anim export <dat> --anim poi              # emote: merged full-body clip (see emotes.md)
uv run cexi anim export <dat> --anim idl --mesh       # dress the rig in its naked body for reference
```

- Race is **auto-detected** for PC motion files; monster/NPC DATs use their own
  skeleton and need nothing. Textures are included by default.
- Bulk (every race, every track): `uv run cexi anim export` with **no `<dat>`**
  (scope with `--race` / `--category`; texture-free).

## Import (glTF back into a DAT)

```bash
# Replace an existing track (auto-finds the exported clip)
uv run cexi anim import <dat> idl

# Create a NEW track from a full-body glTF
uv run cexi anim import <dat> tlk yap.gltf
uv run cexi anim import <dat> --add tlk yap.gltf          # same thing

# Partial clip (only the bones the glTF drives) — hold the rest still
uv run cexi anim import <dat> tlk yap.gltf --static-base

# Keep an imported mesh (don't restore .base first)
uv run cexi anim import <dat> idl --no-base

# Denser keyframes for smoother in-game interpolation
uv run cexi anim import <dat> idl --fps 30
```

A **bare glTF name** (`yap.gltf`) is looked up under the DAT's export folder, so it
doesn't need to be in your working directory.

## Layer one clip onto another (partial-bone overlay)

```bash
# "talk" = idle with yap driving bones 7 & 9 over frames 0-35, saved as new track tlk
uv run cexi anim import <dat> --anim idl --add tlk \
     --layer yap.gltf --frames 0-35 --bones bone0007,bone0009

uv run cexi anim import <dat> --anim idl --add tlk --layer yap.gltf   # all yap's bones, whole clip
```

- `--anim` = base (copied), `--add` = new track, `--layer` = overlay clip.
- Omit `--bones` → every bone the layer animates. Omit `--frames` → whole base clip.
- Keeps the base's live motion on un-selected bones; for a still body do a full import
  with `--static-base` instead.

## Make a clip playable in a cutscene (schedule)

A cutscene can only fire **`0x07` routine** tags via `SetAction`, never a raw clip — so
a freshly imported clip won't appear in the cutscene author's "Anim" dropdown until you
wrap it in a routine. ([schedule.md](schedule.md))

```bash
uv run cexi anim schedule list <dat>                       # routines the dropdown shows
uv run cexi anim schedule add  <dat> --clip tlk0           # wrap tlk0 in a looping routine
uv run cexi anim schedule add  <dat> --clip tlk0 --no-loop # play once, hold last frame

# Chain clips — transition once, then loop (sit-down → sitting idle):
uv run cexi anim schedule create <dat>                     # interactive wizard
uv run cexi anim schedule create <dat> --tag sit0 --clip sitd --clip siti

# Or in one step with the import:
uv run cexi anim import <dat> tlk yap.gltf --static-base --add-schedule
```

Then **hard-refresh the editor** (Ctrl+Shift+R) so it re-fetches the routine list.

## Full round-trip (mesh + anim)

```bash
uv run cexi mesh import <dat>                    # restores baseline, writes the mesh
uv run cexi anim import <dat> idl --no-base      # writes the animation, keeps the mesh
uv run cexi anim export <dat> --anim idl         # re-export to confirm
```

## Gotchas

- **Bouncy / extra motion on bones you didn't animate** → the base clip's translation
  (an idle bob) is leaking. Re-import with `--static-base`. ([import.md](import.md#only-some-bones-move---static-base))
- **Animate with bone ROTATIONS.** Translating/scaling bones in your DCC tool is
  ignored on import (translation/scale are taken from the template — rig structure).
- **Short custom names** (`tlk`) store as `tlk0` and are found by `--anim tlk`.
- **Monster/NPC DAT, wrong-looking result?** Make sure you didn't full-import a
  partial clip — see layer mode above.
