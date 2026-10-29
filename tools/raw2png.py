#!/usr/bin/env python3
"""Turn captures of the badge's screen into PNGs.

    python3 tools/raw2png.py shot.raw [more.raw ...]    # writes shot.png, ...

A capture is the bytes of `screen.raw`, saved on the badge and copied off
(see "Capturing the screen" in docs/workflow.md): RGB565, little-endian, row
by row. Its size gives the mode: 320 x 240 in HIRES, 160 x 120 otherwise.
Only the standard library is used.
"""

import struct
import sys
import zlib

SIZES = {320 * 240 * 2: (320, 240), 160 * 120 * 2: (160, 120)}


def png(width, height, rgb_rows):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + row for row in rgb_rows)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def convert(path):
    data = open(path, "rb").read()
    if len(data) not in SIZES:
        sys.exit("%s: %d bytes isn't a 320 x 240 or 160 x 120 capture" % (path, len(data)))
    width, height = SIZES[len(data)]
    rows = []
    for y in range(height):
        row = bytearray()
        for (v,) in struct.iter_unpack("<H", data[y * width * 2:(y + 1) * width * 2]):
            # Scale 5 and 6 bit channels to 8 bits, filling the low bits.
            r, g, b = v >> 11, (v >> 5) & 63, v & 31
            row += bytes(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))
        rows.append(bytes(row))
    out = path[:-4] + ".png" if path.endswith(".raw") else path + ".png"
    with open(out, "wb") as f:
        f.write(png(width, height, rows))
    print(out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        convert(path)
