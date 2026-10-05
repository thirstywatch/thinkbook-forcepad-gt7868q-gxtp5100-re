# -*- coding: utf-8 -*-
"""R5-3: cfg 解析（帧序已更正）—— `tpcfgsid*.cfg` 头部身份 + TLV([LEN][TAG])

⚠️ 踩坑留档（本轮真实发生的错误）：
   第一版按 `[TAG][LEN]`、从偏移 0 起解析，报出 "98.4% 覆盖" —— **错的**。
   覆盖率被"解析失败就跳 1 字节"的兜底逻辑抬高了（37 条里只有约 20 条真有 LEN）。
   判帧序的正确方法（`method/10-semantics.md` §5.2）：
     ① 从 0x40 起；② 交换两种帧序做头对头覆盖率对比；
     ③ **看 `[0x3D]` 声明的条目数是否与实解帧数严格相等** —— 这条最硬。
   实测：sid0 55=55、sid3 53=53 ⇒ 帧序 = `[LEN:u8][TAG:u8][payload: LEN-2]`，起点 0x40。

用法:  python lab__r5_3_cfg_tlv.py <cfg文件> [...]
"""
import sys, os


def u16(b, o): return b[o] | (b[o + 1] << 8)


def parse_cfg(path):
    b = open(path, 'rb').read()
    print(f"\n{'=' * 84}\n{os.path.basename(path)}  ({len(b)} B)")
    vendor = b[0:8].split(b'\0')[0].decode('latin-1')
    ic_type = b[8:12].split(b'\0')[0].decode('latin-1')
    hw_pid = b[0x14:0x1C].split(b'\0')[0].decode('latin-1')
    date = b[0x23:0x2B].decode('latin-1', 'replace')
    tlvlen = u16(b, 0x3B)
    nentry = b[0x3D]
    ok = (0x40 + tlvlen == len(b))
    print(f"  头: vendor={vendor!r} ic_type={ic_type!r} hw_pid={hw_pid!r} date={date!r}")
    print(f"  [0x3B] TLV长度={tlvlen}  [0x3D] 条目数={nentry}  "
          f"0x40+len={0x40 + tlvlen} vs 文件 {len(b)}  {'✓闭合' if ok else '✗不是本格式'}")
    if not ok:
        print("  ⇒ 不是 [LEN][TAG] 格式（项目已记：sid2/7863 属此类），跳过 TLV 解析")
        return
    i, frames, cov = 0x40, [], 0
    while i < len(b) - 1:
        ln, tag = b[i], b[i + 1]
        if ln >= 2 and i + ln <= len(b):
            frames.append((i, tag, ln, b[i + 2:i + ln]))
            cov += ln
            i += ln
        else:
            i += 1
    inc = sum(1 for k in range(1, len(frames)) if frames[k][1] > frames[k - 1][1])
    print(f"  TLV: 帧 {len(frames)} 条 (声明 {nentry}) "
          f"{'✓相等' if len(frames) == nentry else '✗不等'}"
          f"  覆盖 {cov}/{tlvlen} = {100 * cov / tlvlen:.1f}%  "
          f"TAG 递增 {inc}/{max(1, len(frames) - 1)}")
    print(f"  TAG 序列: {[hex(t) for _, t, _, _ in frames]}")
    hap = [(hex(t), ln) for _, t, ln, _ in frames if 0x50 <= t <= 0x7A]
    print(f"  ★ 触觉区(0x50-0x7A) TAG: {hap}")
    for off, tag, ln, dat in frames:
        print(f"    @0x{off:04x}  LEN={ln:<3} TAG=0x{tag:02x}  {dat.hex(' ')[:60]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    for p in sys.argv[1:]:
        parse_cfg(p)
