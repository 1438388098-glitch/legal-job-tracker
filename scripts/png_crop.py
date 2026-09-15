"""裁剪 PNG 的一小块并重新编码，用于核对配色（顺手也能统计整体明暗）。

只依赖 zlib/struct，避免为一两次核对去装 Pillow。
用法：python scripts/png_crop.py <输入.png> <输出.png> <x> <y> <w> <h>
"""
import struct
import sys
import zlib
from pathlib import Path


def load_png(path):
    data = Path(path).read_bytes()
    pos, idat = 8, bytearray()
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and interlace == 0
            ch = {0: 1, 2: 3, 4: 2, 6: 4}[color]
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln
    raw = zlib.decompress(bytes(idat))
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    i = 0
    for y in range(h):
        f, i = raw[i], i + 1
        line = bytearray(raw[i:i + stride])
        i += stride
        for x in range(stride):
            a = line[x - ch] if x >= ch else 0
            b = prev[x]
            c = prev[x - ch] if x >= ch else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return w, h, ch, out


def encode_png(w, h, ch, buf):
    color = {1: 0, 3: 2, 4: 6}[ch]
    raw = bytearray()
    stride = w * ch
    for y in range(h):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]

    def chunk(typ, body):
        return (struct.pack(">I", len(body)) + typ + body
                + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, color, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
            + chunk(b"IEND", b""))


def main(src, dst, x, y, w, h):
    sw, sh, ch, buf = load_png(src)
    x, y, w, h = int(x), int(y), int(w), int(h)
    w = min(w, sw - x)
    h = min(h, sh - y)
    out = bytearray()
    for yy in range(h):
        o = ((y + yy) * sw + x) * ch
        out += buf[o:o + w * ch]
    Path(dst).write_bytes(encode_png(w, h, ch, out))
    print(f"  {src} → {dst}  裁剪 {w}x{h} @({x},{y})")


if __name__ == "__main__":
    main(*sys.argv[1:7])
