#!/usr/bin/env python3
"""isflash_lzma_dump.py —— 把 Insyde BIOS 镜像里所有 LZMA 压缩模块解压出来。

为什么需要它
------------
`isflash.bin` 里的 UEFI 模块（FV/FFS）是 **LZMA 压缩**的
（GUID `EE4E5898-3914-4259-9D6E-DC7BD79403CF`）。
⇒ 直接在镜像里搜字符串**必然搜不到**（上一轮搜 `AW86927`/`0x5A` 序列全 0 命中就是这个原因）。
⇒ 必须**先解压**，再在解压后的明文里搜。

输出
----
  out/sections/NNNN_<guid>.bin     每个 LZMA 段的解压结果
  out/index.json                   段清单（偏移/guid/压缩长/解压长/sha256）
  out/all.txt                      所有解压内容拼接（供 grep）

用法
----
  python isflash_lzma_dump.py isflash.bin --out lzma_out
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import struct
import sys
from pathlib import Path

# UEFI 常见压缩 GUID
GUID_LZMA = bytes.fromhex("9858ee4e14395942d69ede7bd79403cf")   # EE4E5898-3914-4259-9D6E-DC7BD79403CF
GUID_TIANO = bytes.fromhex("a312b0a798564c24b7ae7e47082b8e2a")   # A312B0A7-9856-4C24-B7AE-7E47082B8E2A (Tiano)
GUID_LZMAF86 = bytes.fromhex("d42ae6bd97414a3da21c4ac80d5b48de")  # D42AE6BD-9741-4A3D-A21C-4AC80D5B48DE
GUID_TIANOF86 = bytes.fromhex("c37f2b3c9a4f4d1a8d1b6e1ab0d0e1f2")

COMPRESS_GUIDS = {GUID_LZMA: "LZMA", GUID_LZMAF86: "LZMAF86",
                  GUID_TIANO: "TIANO", GUID_TIANOF86: "TIANOF86"}


def lzma_uefi_decompress(data: bytes) -> bytes | None:
    """UEFI LZMA 段：1 字节 props + 4 字节 dict_size(LE) + 裸 LZMA 流。"""
    if len(data) < 6:
        return None
    props = data[0]
    if props >= 9 * 5 * 5:
        return None
    dict_size = struct.unpack_from("<I", data, 1)[0]
    if dict_size == 0:
        dict_size = 1 << 16
    lc = props % 9
    rest = props // 9
    lp = rest % 5
    pb = rest // 5
    filt = [{"id": lzma.FILTER_LZMA1, "dict_size": dict_size,
             "lc": lc, "lp": lp, "pb": pb}]
    try:
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt)
        return dec.decompress(data[5:])
    except Exception:
        return None


def walk_ffs(d: bytes, off: int, end: int, out: list, depth: int = 0, limit_depth: int = 3):
    """遍历 FFS 文件与其中的 section，收集可解压段。"""
    guard = 0
    while off + 4 <= end and guard < 100000:
        guard += 1
        size = d[off] | (d[off + 1] << 8) | (d[off + 2] << 16)
        st = d[off + 3]
        if size == 0xFFFFFF:
            if off + 24 > end:
                return
            gd = d[off + 4:off + 20]
            realsize = struct.unpack_from("<I", d, off + 20)[0]
            doff = struct.unpack_from("<H", d, off + 20)[0]
            if realsize < 24 or off + realsize > end:
                return
            if st in (0x01, 0x02, 0x17):
                out.append(dict(kind="extsec", type=st, guid=gd.hex(),
                                off=off, size=realsize, doff=doff, depth=depth))
            if st == 0x17 and depth < limit_depth:            # 嵌套 FV
                walk_fv(d, off + doff, off + realsize, out, depth + 1, limit_depth)
            off += (realsize + 7) & ~7
            continue
        if size < 4 or off + size > end:
            return
        # 普通 section
        if st in (0x01, 0x02):                                 # COMPRESS / GUID_DEF
            out.append(dict(kind="sec", type=st, guid=d[off + 4:off + 20].hex(),
                            off=off, size=size, doff=0, depth=depth))
        elif st == 0x17 and depth < limit_depth:               # FV_IMAGE
            walk_fv(d, off + 4, off + size, out, depth + 1, limit_depth)
        off += (size + 3) & ~3


def walk_fv(d: bytes, start: int, endfv: int, out: list, depth: int, limit_depth: int):
    if start + 0x38 > len(d) or d[start + 0x28:start + 0x2C] != b"_FVH":
        return
    fvlen = struct.unpack_from("<Q", d, start + 0x20)[0]
    if not (0x40 < fvlen <= len(d) - start):
        return
    hlen = struct.unpack_from("<H", d, start + 0x30)[0]
    off = start + hlen
    end = start + fvlen
    guard = 0
    while off + 24 <= end and guard < 20000:
        guard += 1
        if d[off:off + 16] == b"\xff" * 16 and d[off + 16:off + 24] == b"\xff" * 8:
            break
        fsize = d[off + 20] | (d[off + 21] << 8) | (d[off + 22] << 16)
        if fsize < 24 or off + fsize > end:
            break
        walk_ffs(d, off + 24, off + fsize, out, depth + 1, limit_depth)
        off = (off + fsize + 7) & ~7


def extract(d: bytes, outdir: Path):
    secs: list = []
    for o in range(0, len(d) - 0x40):
        if d[o + 0x28:o + 0x2C] == b"_FVH" and d[o:o + 16] == b"\0" * 16:
            walk_fv(d, o, len(d), secs, 0, 3)
    (outdir / "sections").mkdir(parents=True, exist_ok=True)

    index, blob, ok, fail = [], [], 0, 0
    for i, s in enumerate(secs):
        raw_off = s["off"] + (24 if s["size"] == 0xFFFFFF else 4) + s.get("doff", 0)
        if s["size"] == 0xFFFFFF:
            raw_off = s["off"] + s["doff"]
            raw_len = s["size"] - s["doff"]
        else:
            raw_off = s["off"] + 4
            raw_len = s["size"] - 4
        if raw_off < 0 or raw_off + raw_len > len(d):
            continue
        raw = d[raw_off:raw_off + raw_len]
        res = lzma_uefi_decompress(raw)
        if res is None:
            # 试试 Tiano 风格：8 字节头(压缩长)+8字节头(解压长)
            if len(raw) > 16:
                res = _tiano(raw[16:])
            if res is None:
                fail += 1
                continue
        ok += 1
        name = f"{i:04d}_{s['guid'][:16]}.bin"
        (outdir / "sections" / name).write_bytes(res)
        index.append(dict(i=i, guid=s["guid"], type=s["type"], depth=s["depth"],
                          file_off=raw_off, raw_len=raw_len, out_len=len(res),
                          out_file=name, sha256=hashlib.sha256(res).hexdigest()[:16]))
        blob.append(f"\n===== [{i}] guid={s['guid']} off=0x{raw_off:X} out={len(res)} =====\n".encode()
                    + res)

    (outdir / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    (outdir / "all.bin").write_bytes(b"".join(blob))
    print(f"找到 {len(secs)} 个候选段：解压成功 {ok}，失败 {fail}")
    print(f"解压总字节 {sum(e['out_len'] for e in index):,}")
    print(f"-> {outdir}/sections/ · index.json · all.bin")


def _tiano(raw: bytes):
    try:
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_AUTO)
        return dec.decompress(raw)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("img")
    ap.add_argument("--out", default="lzma_out")
    a = ap.parse_args()
    d = Path(a.img).read_bytes()
    print(f"输入 {a.img}: {len(d):,} 字节")
    extract(d, Path(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
