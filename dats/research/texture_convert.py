import argparse
import os
import shutil
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path


DDS_FOURCC_OFFSET = 84
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SUPPORTED_DDS_FORMATS = {"DXT1", "DXT3", "DXT5"}


@dataclass
class AlphaAnalysis:
    has_alpha: bool
    mode: str
    source: str
    detail: str


@dataclass
class DdsInfo:
    width: int
    height: int
    fourcc: str
    data_offset: int


def find_texconv(texconv_arg: str) -> str:
    if os.path.isfile(texconv_arg):
        return str(Path(texconv_arg).resolve())

    resolved = shutil.which(texconv_arg)
    if resolved:
        return resolved

    raise FileNotFoundError(
        f"texconv not found: {texconv_arg}. Install DirectXTex texconv or pass --texconv explicitly."
    )


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_dds_info(dds_path: Path) -> DdsInfo:
    with dds_path.open("rb") as handle:
        header = handle.read(128)

    if len(header) < 128 or header[:4] != b"DDS ":
        raise ValueError(f"Not a valid DDS file: {dds_path}")

    height = struct.unpack_from("<I", header, 12)[0]
    width = struct.unpack_from("<I", header, 16)[0]
    fourcc = header[DDS_FOURCC_OFFSET:DDS_FOURCC_OFFSET + 4].decode("ascii", errors="replace")
    data_offset = 128
    if fourcc == "DX10":
        data_offset += 20

    return DdsInfo(width=width, height=height, fourcc=fourcc, data_offset=data_offset)


def decode_rgb565(value: int) -> tuple[int, int, int]:
    r = ((value >> 11) & 0x1F) * 255 // 31
    g = ((value >> 5) & 0x3F) * 255 // 63
    b = (value & 0x1F) * 255 // 31
    return r, g, b


def interpolate(c0: tuple[int, int, int], c1: tuple[int, int, int], a: int, b: int, div: int) -> tuple[int, int, int]:
    return (
        (c0[0] * a + c1[0] * b) // div,
        (c0[1] * a + c1[1] * b) // div,
        (c0[2] * a + c1[2] * b) // div,
    )


def dxt_colors(color0: int, color1: int, allow_transparent: bool) -> list[tuple[int, int, int, int]]:
    c0 = decode_rgb565(color0)
    c1 = decode_rgb565(color1)
    palette = [
        (*c0, 255),
        (*c1, 255),
    ]

    if allow_transparent and color0 <= color1:
        palette.append((*interpolate(c0, c1, 1, 1, 2), 255))
        palette.append((0, 0, 0, 0))
        return palette

    palette.append((*interpolate(c0, c1, 2, 1, 3), 255))
    palette.append((*interpolate(c0, c1, 1, 2, 3), 255))
    return palette


def decode_dxt1_block(block: bytes) -> list[tuple[int, int, int, int]]:
    color0, color1, lookup = struct.unpack("<HHI", block)
    palette = dxt_colors(color0, color1, allow_transparent=True)
    pixels = []
    for index in range(16):
        pixels.append(palette[(lookup >> (2 * index)) & 0x03])
    return pixels


def decode_dxt3_block(block: bytes) -> list[tuple[int, int, int, int]]:
    alpha_bits = int.from_bytes(block[:8], "little")
    color0, color1, lookup = struct.unpack("<HHI", block[8:16])
    palette = dxt_colors(color0, color1, allow_transparent=False)
    pixels = []
    for index in range(16):
        rgba = list(palette[(lookup >> (2 * index)) & 0x03])
        rgba[3] = ((alpha_bits >> (4 * index)) & 0x0F) * 17
        pixels.append(tuple(rgba))
    return pixels


def dxt5_alpha_palette(alpha0: int, alpha1: int) -> list[int]:
    if alpha0 > alpha1:
        return [
            alpha0,
            alpha1,
            (6 * alpha0 + 1 * alpha1) // 7,
            (5 * alpha0 + 2 * alpha1) // 7,
            (4 * alpha0 + 3 * alpha1) // 7,
            (3 * alpha0 + 4 * alpha1) // 7,
            (2 * alpha0 + 5 * alpha1) // 7,
            (1 * alpha0 + 6 * alpha1) // 7,
        ]

    return [
        alpha0,
        alpha1,
        (4 * alpha0 + 1 * alpha1) // 5,
        (3 * alpha0 + 2 * alpha1) // 5,
        (2 * alpha0 + 3 * alpha1) // 5,
        (1 * alpha0 + 4 * alpha1) // 5,
        0,
        255,
    ]


def decode_dxt5_block(block: bytes) -> list[tuple[int, int, int, int]]:
    alpha0 = block[0]
    alpha1 = block[1]
    alpha_lookup = int.from_bytes(block[2:8], "little")
    color0, color1, color_lookup = struct.unpack("<HHI", block[8:16])
    alpha_palette = dxt5_alpha_palette(alpha0, alpha1)
    color_palette = dxt_colors(color0, color1, allow_transparent=False)

    pixels = []
    for index in range(16):
        rgba = list(color_palette[(color_lookup >> (2 * index)) & 0x03])
        rgba[3] = alpha_palette[(alpha_lookup >> (3 * index)) & 0x07]
        pixels.append(tuple(rgba))
    return pixels


def decode_dds_to_rgba(dds_path: Path) -> tuple[DdsInfo, bytes]:
    info = parse_dds_info(dds_path)
    if info.fourcc == "DX10":
        raise ValueError("DX10 DDS files are not supported by this script")
    if info.fourcc not in SUPPORTED_DDS_FORMATS:
        raise ValueError(f"Unsupported DDS format: {info.fourcc}")

    data = dds_path.read_bytes()
    block_size = 8 if info.fourcc == "DXT1" else 16
    blocks_wide = max(1, (info.width + 3) // 4)
    blocks_high = max(1, (info.height + 3) // 4)
    rgba = bytearray(info.width * info.height * 4)

    offset = info.data_offset
    for block_y in range(blocks_high):
        for block_x in range(blocks_wide):
            block = data[offset:offset + block_size]
            if len(block) != block_size:
                raise ValueError(f"DDS pixel data is truncated: {dds_path}")
            offset += block_size

            if info.fourcc == "DXT1":
                block_pixels = decode_dxt1_block(block)
            elif info.fourcc == "DXT3":
                block_pixels = decode_dxt3_block(block)
            else:
                block_pixels = decode_dxt5_block(block)

            for pixel_index, pixel in enumerate(block_pixels):
                local_x = pixel_index % 4
                local_y = pixel_index // 4
                x = block_x * 4 + local_x
                y = block_y * 4 + local_y
                if x >= info.width or y >= info.height:
                    continue

                dest = (y * info.width + x) * 4
                rgba[dest:dest + 4] = bytes(pixel)

    return info, bytes(rgba)


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + chunk_type
        + data
        + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def write_png_rgba(path: Path, width: int, height: int, rgba: bytes) -> None:
    ensure_parent_dir(path)
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        start = y * stride
        raw.extend(rgba[start:start + stride])

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw))
    png = PNG_SIGNATURE + png_chunk(b"IHDR", ihdr) + png_chunk(b"IDAT", idat) + png_chunk(b"IEND", b"")
    path.write_bytes(png)


def inspect_png_alpha(path: Path) -> AlphaAnalysis:
    try:
        from PIL import Image
    except ImportError:
        return inspect_png_alpha_basic(path)

    with Image.open(path) as image:
        if image.mode in {"RGBA", "LA"}:
            alpha = image.getchannel("A")
            extrema = alpha.getextrema()
            if extrema == (255, 255):
                return AlphaAnalysis(False, "opaque", "pillow", "alpha channel exists but all pixels are fully opaque")

            values = set(alpha.getdata())
            if values.issubset({0, 255}):
                return AlphaAnalysis(True, "binary", "pillow", "alpha uses only 0/255 values")

            if all(value % 17 == 0 for value in values) and len(values) <= 16:
                return AlphaAnalysis(True, "sharp", "pillow", "alpha fits 4-bit style steps")

            return AlphaAnalysis(True, "smooth", "pillow", "alpha uses mixed gradient values")

        if "transparency" in image.info:
            return AlphaAnalysis(True, "binary", "pillow", "PNG transparency metadata is present")

        return AlphaAnalysis(False, "opaque", "pillow", "image has no alpha channel")


def inspect_png_alpha_basic(path: Path) -> AlphaAnalysis:
    with path.open("rb") as handle:
        data = handle.read()

    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"Not a valid PNG file: {path}")

    offset = len(PNG_SIGNATURE)
    color_type = None
    has_trns = False

    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        chunk_type = data[offset + 4:offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + length
        if chunk_data_end + 4 > len(data):
            break

        if chunk_type == b"IHDR":
            color_type = data[chunk_data_start + 9]
        elif chunk_type == b"tRNS":
            has_trns = True
        elif chunk_type == b"IEND":
            break

        offset = chunk_data_end + 4

    if color_type in {4, 6}:
        return AlphaAnalysis(True, "smooth", "basic", "PNG has an alpha channel; install Pillow for sharper auto-detection")
    if has_trns:
        return AlphaAnalysis(True, "binary", "basic", "PNG has a transparency chunk")
    return AlphaAnalysis(False, "opaque", "basic", "PNG has no alpha channel or transparency chunk")


def choose_dds_format(requested_format: str, alpha_mode: str, analysis: AlphaAnalysis) -> str:
    if requested_format != "auto":
        return requested_format.upper()

    if alpha_mode == "opaque":
        return "DXT1"
    if alpha_mode == "cutout":
        return "DXT1"
    if alpha_mode == "sharp":
        return "DXT3"
    if alpha_mode == "smooth":
        return "DXT5"

    if not analysis.has_alpha:
        return "DXT1"
    if analysis.mode == "binary":
        return "DXT1"
    if analysis.mode == "sharp":
        return "DXT3"
    return "DXT5"


def choose_dds_format_with_source(
    requested_format: str,
    alpha_mode: str,
    analysis: AlphaAnalysis,
    match_source: str | None,
) -> tuple[str, str]:
    if match_source:
        source_info = parse_dds_info(Path(match_source).resolve())
        if source_info.fourcc not in SUPPORTED_DDS_FORMATS:
            raise ValueError(
                f"Unsupported source DDS format for --match-source: {source_info.fourcc}"
            )
        return source_info.fourcc, f"matched source DDS format from {match_source}"

    return choose_dds_format(requested_format, alpha_mode, analysis), "chosen from args/alpha analysis"


def run_texconv(texconv: str, args: list[str]) -> None:
    completed = subprocess.run([texconv, *args], capture_output=True, text=True)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout or "texconv failed without output"
        raise RuntimeError(detail)


def convert_with_temp_output(texconv: str, texconv_args: list[str], desired_output: Path, produced_suffix: str) -> None:
    ensure_parent_dir(desired_output)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        run_texconv(texconv, [*texconv_args, "-o", str(tmp_path)])

        produced_files = list(tmp_path.glob(f"*{produced_suffix}"))
        if len(produced_files) != 1:
            raise RuntimeError(
                f"Expected exactly one {produced_suffix} file from texconv, found {len(produced_files)}"
            )

        shutil.move(str(produced_files[0]), str(desired_output))


def cmd_dds_to_png(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    info, rgba = decode_dds_to_rgba(input_path)
    format_notes = {
        "DXT1": "opaque or cutout alpha",
        "DXT3": "explicit sharp alpha",
        "DXT5": "interpolated smooth alpha",
    }
    print(f"Detected DDS format: {info.fourcc}")
    if info.fourcc in format_notes:
        print(f"Format note: {format_notes[info.fourcc]}")
    print(f"Dimensions: {info.width}x{info.height}")

    write_png_rgba(output_path, info.width, info.height, rgba)
    print(f"Wrote PNG: {output_path}")


def cmd_png_to_dds(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    texconv = find_texconv(args.texconv)

    analysis = inspect_png_alpha(input_path)
    dds_format, format_reason = choose_dds_format_with_source(
        args.format,
        args.alpha_mode,
        analysis,
        args.match_source,
    )

    print(f"Alpha analysis: has_alpha={analysis.has_alpha} mode={analysis.mode} source={analysis.source}")
    print(f"Alpha detail: {analysis.detail}")
    print(f"Format source: {format_reason}")
    print(f"Chosen DDS format: {dds_format}")

    texconv_args = ["-y", "-ft", "dds", "-f", dds_format, "-m", str(args.mipmaps)]
    if args.srgb:
        texconv_args.append("-srgb")
    texconv_args.append(str(input_path))

    convert_with_temp_output(texconv, texconv_args, output_path, ".DDS")
    print(f"Wrote DDS: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert DDS<->PNG using DirectXTex texconv with DXT1/DXT3/DXT5-aware options."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dds_to_png = subparsers.add_parser("dds-to-png", help="Convert a DDS file to PNG")
    dds_to_png.add_argument("input", help="Input .dds file")
    dds_to_png.add_argument("output", help="Output .png file")
    dds_to_png.set_defaults(func=cmd_dds_to_png)

    png_to_dds = subparsers.add_parser("png-to-dds", help="Convert a PNG file to DDS")
    png_to_dds.add_argument("input", help="Input .png file")
    png_to_dds.add_argument("output", help="Output .dds file")
    png_to_dds.add_argument(
        "--format",
        choices=["auto", "dxt1", "dxt3", "dxt5"],
        default="auto",
        help="DDS compression format. auto picks a format from the PNG alpha usage.",
    )
    png_to_dds.add_argument(
        "--alpha-mode",
        choices=["auto", "opaque", "cutout", "sharp", "smooth"],
        default="auto",
        help="Override the auto format choice: cutout->DXT1, sharp->DXT3, smooth->DXT5.",
    )
    png_to_dds.add_argument(
        "--mipmaps",
        type=int,
        default=1,
        help="Mip level count passed to texconv. Use 1 to keep a single top-level image.",
    )
    png_to_dds.add_argument(
        "--match-source",
        help="Original DDS file to read and reuse its DXT1/DXT3/DXT5 format.",
    )
    png_to_dds.add_argument(
        "--srgb",
        action="store_true",
        help="Pass -srgb to texconv for sRGB output.",
    )
    png_to_dds.add_argument("--texconv", default="texconv", help="Path to texconv.exe or command name in PATH")
    png_to_dds.set_defaults(func=cmd_png_to_dds)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
