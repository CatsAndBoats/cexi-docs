# pol_decompress.py

Standalone script that decompresses the POL1-packed `.text` section of
`FFXiMain.dll` and writes a valid PE/DLL with `.text` restored on disk —
suitable for loading in Ghidra or IDA Pro.

**Research only.** The game loads the original packed DLL; the output is
for static analysis only.

## Background

FFXiMain.dll ships with its `.text` section zeroed on disk. The real
`.text` is stored compressed in a custom PE section named **POL1**. The
DLL's OEP points into POL1's unpacker stub, which decompresses POL1 into
the `.text` VMA at load time using a simple LZSS variant:

- Control byte processed **MSB-first**
- Bit `1` → literal byte follows
- Bit `0` → back-reference: two bytes encoding `(length, offset)` where offset `0` is the end-of-stream sentinel
- Compressed size: `0x1E57B0` bytes; decompressed: `0x32716E` bytes

`pol1_inspect.py` and `pol1_unpack.py` in this folder document the
exploratory work that reverse-engineered the stub before the algorithm was
confirmed.

## Dependencies

```
pip install pefile
pip install capstone   # optional — prints first 10 instructions as a sanity check
```

## Usage

```bash
python pol_decompress.py FFXiMain.dll
python pol_decompress.py FFXiMain.dll --output FFXiMain_unpacked.dll
```

Output defaults to `FFXiMain_unpacked.dll` next to the input file.

## Loading in Ghidra

1. File → Import File → `FFXiMain_unpacked.dll`
2. Set image base to `0x10000000`
3. Run auto-analysis — the restored `.text` gives full decompiler output

## See also

- [`reference/ffximain.md`](../../reference/ffximain.md) — full background on the POL1 packer format
- [`pol_gear_formula.md`](pol_gear_formula.md) — example: searching the decompressed binary for gear model ID constants
- [`search_gear_formula.py`](search_gear_formula.py) / [`search_model_formula.py`](search_model_formula.py) — scripts that search the decompressed binary
