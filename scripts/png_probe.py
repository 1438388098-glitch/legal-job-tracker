"""从 PNG 里取几个像素点，用来客观判断截图到底是深色还是浅色。

为什么不用 Pillow：这台机器上装它要走网络、还很慢；PNG 解码本身只要 zlib。
只支持 Chrome 截图输出的 8bit 真彩（含 alpha），够用。
"""
import struct
import sys
import zlib
from pathlib import Path


def load_png(path):
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "不是 PNG"
    pos, idat, w = 8, bytearray(), None
    while pos < len(data):
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and interlace == 0, "只支持 8bit 非隔行"
            channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln

    raw = zlib.decompress(bytes(idat))
    stride = w * channels
    out = bytearray(h * stride)
    prev = bytearray(stride)
    i = 0
    for y in range(h):
        f = raw[i]
        i += 1
        line = bytearray(raw[i:i + stride])
        i += stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
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
    return w, h, channels, out


def px(img, x, y):
    w, h, ch, buf = img
    o = (y * w + x) * ch
    return tuple(buf[o:o + 3])


def main(paths):
    for p in paths:
        try:
            img = load_png(p)
        except Exception as e:  # noqa: BLE001
            print(f"  {p}: 读取失败 {e}")
            continue
        w, h = img[0], img[1]
        pts = {"页面底": (w - 12, h - 12), "顶栏": (w // 2, 22), "表头": (w // 2, 180)}
        vals = {k: px(img, *v) for k, v in pts.items()}
        avg = sum(sum(v) for v in vals.values()) / (3 * len(vals))
        tone = "深色" if avg < 110 else ("浅色" if avg > 200 else "中间调")
        print(f"  {Path(p).name:<18} {w}x{h}  判定={tone}")
        for k, v in vals.items():
            print(f"      {k}: rgb{v}")


if __name__ == "__main__":
    main(sys.argv[1:])
