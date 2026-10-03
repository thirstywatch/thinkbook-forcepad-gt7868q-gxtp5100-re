"""Minimal PDF text extractor: flate-decompress streams, pull Tj/TJ strings.

Handles WinAnsi/Standard single-byte encodings. For CID/Identity-H fonts
(2-byte codes) it falls back to a heuristic that maps the ToUnicode CMap if
present. Output is intentionally rough: we only need to grep usage names.
"""
import re, sys, zlib


def streams(data: bytes):
    out = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        raw = data[start:end]
        try:
            out.append(zlib.decompress(raw))
        except Exception:
            try:
                out.append(zlib.decompressobj().decompress(raw))
            except Exception:
                pass
    return out


def unescape(s: bytes) -> bytes:
    res = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == 0x5C and i + 1 < len(s):
            n = s[i + 1]
            mp = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12,
                  0x28: 0x28, 0x29: 0x29, 0x5C: 0x5C}
            if n in mp:
                res.append(mp[n]); i += 2; continue
            if 0x30 <= n <= 0x37:
                j = i + 1; oct_digits = b""
                while j < len(s) and len(oct_digits) < 3 and 0x30 <= s[j] <= 0x37:
                    oct_digits += bytes([s[j]]); j += 1
                res.append(int(oct_digits, 8) & 0xFF); i = j; continue
            res.append(n); i += 2; continue
        res.append(c); i += 1
    return bytes(res)


TOK = re.compile(rb"\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]*>|\bTJ\b|\bTj\b|\bTD\b|\bTd\b|\bT\*\b|\bET\b")


def text_from(content: bytes) -> str:
    parts = []
    for m in TOK.finditer(content):
        t = m.group(0)
        if t in (b"TD", b"Td", b"T*", b"ET"):
            parts.append("\n")
        elif t.startswith(b"("):
            parts.append(unescape(t[1:-1]).decode("latin-1"))
        elif t.startswith(b"<"):
            hx = re.sub(rb"\s", b"", t[1:-1])
            if len(hx) % 2:
                hx += b"0"
            try:
                b = bytes.fromhex(hx.decode())
            except Exception:
                continue
            # heuristic: 2-byte big-endian CID -> ascii if it lands in range
            if len(b) >= 2 and b[0::2].count(0) == len(b[0::2]):
                parts.append(b[1::2].decode("latin-1"))
            else:
                parts.append(b.decode("latin-1"))
    return "".join(parts)


def main():
    path = sys.argv[1]
    data = open(path, "rb").read()
    chunks = []
    for i, s in enumerate(streams(data)):
        txt = text_from(s)
        if txt.strip():
            chunks.append(f"\n===== stream {i} =====\n{txt}")
    out = "\n".join(chunks)
    out = re.sub(r"\n{3,}", "\n\n", out)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 2:
        open(sys.argv[2], "w", encoding="utf-8").write(out)
        print(f"wrote {sys.argv[2]} chars={len(out)} streams={len(chunks)}")
    else:
        print(out)


main()
