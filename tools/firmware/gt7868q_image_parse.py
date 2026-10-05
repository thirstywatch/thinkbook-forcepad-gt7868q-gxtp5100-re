"""GT7868Q 固件镜像 —— 官方格式权威解析器（依据汇顶官方 gdixupdate 源码）

官方依据（poc/gdix-hid-fw/，Apache-2.0，Goodix 官方工具 gdixupdate v1.8.0）：
  firmware_image.cpp          : size = BE u32 @0 ; chksum = BE u16 @4 ; Σ byte[6 : size+6] == chksum
  gt7868q_gt7868q_firmware_image.cpp:
      FW_IMAGE_PID_OFFSET 15 / CID 23 / VID 24 / SUB_FWNUM 27 / SUB_FW_INFO_OFFSET 32 / SUB_FW_DATA_OFFSET 256
  gtx3_gtx3_update.cpp::fw_update :
      sub_fw_type = d[p] ; sub_fw_len = BE u32 d[p+1..p+5) ; sub_fw_addr = ((d[p+5]<<8)|d[p+6])<<8 ; p += 8
      if (!(firmware_flag & (0x01 << sub_fw_type))) -> 跳过该子固件
  main.cpp : TYPE_YELLOWSTONE (GT7868Q) firmware_flag = 0x0C  --> 只写 type 0x02 / 0x03
  gt7868q_gt7868q_update.cpp / gt7868q.cpp :
      CFG_FLASH_ADDR 0x19000 ; CFG_START_ADDR 0x96F8 ; CMD_ADDR 0x4160
"""
import collections, math, sys

FW_INFO_OFFSET = 32
FW_DATA_OFFSET = 256
PID_OFF = 15
CID_OFF = 23
VID_OFF = 24
SUB_FWNUM_OFF = 27
YELLOWSTONE_FW_FLAG = 0x0C          # 只写 type 0x02 / 0x03


def parse(img: bytes):
    """img = 一个「Goodix 固件镜像」（首字节起就是 256B 镜像头）。返回 dict。"""
    size = int.from_bytes(img[0:4], "big")
    chk = int.from_bytes(img[4:6], "big")
    real = sum(img[6:size + 6]) & 0xFFFF
    pid = bytes(c for c in img[PID_OFF:PID_OFF + 8] if c).decode("latin-1")
    n = img[SUB_FWNUM_OFF]
    subs, p, off = [], FW_INFO_OFFSET, FW_DATA_OFFSET
    for _ in range(n):
        t = img[p]
        ln = (img[p + 1] << 24) | (img[p + 2] << 16) | (img[p + 3] << 8) | img[p + 4]
        ad = ((img[p + 5] << 8) | img[p + 6]) << 8
        subs.append(dict(type=t, size=ln, addr=ad,
                         data=img[off:off + ln],
                         written_by_official_tool=bool(YELLOWSTONE_FW_FLAG & (1 << t))))
        off += ln
        p += 8
    return dict(size=size, checksum=chk, checksum_ok=(chk == real),
                checksum_over="stored bytes", family=img[6:12].decode("latin-1"),
                hw_vid=img[12:15].hex(" "), pid=pid, cid=img[CID_OFF],
                vid=(img[VID_OFF], img[VID_OFF + 1], img[VID_OFF + 2]),
                subsys_num=n, subs=subs, header=img[:FW_DATA_OFFSET],
                tail_unaccounted=(size + 6) - FW_DATA_OFFSET - sum(s["size"] for s in subs))


def load(path):
    with open(path, "rb") as f:
        return f.read()


def report(r):
    print(f"  家族 hw_pid = {r['family']!r}   hw_vid = {r['hw_vid']}")
    print(f"  PID = {r['pid']!r}   CID = {r['cid']:#04x}   VID = {r['vid'][0]}.{r['vid'][1]}.{r['vid'][2]}")
    print(f"  size = {r['size']}  (size+6 = {r['size']+6})   校验和 = 0x{r['checksum']:04x}  "
          f"({r['checksum_ok'] and 'OK' or 'MISMATCH'}，覆盖 {r['checksum_over']})")
    print(f"  子固件数 = {r['subsys_num']}   头 256B 之后多余字节 = {r['tail_unaccounted']}")
    print(f"  {'idx':>3} {'type':>5} {'flash':>9} {'size':>7} {'官方会写?':>10} {'零%':>6} {'熵':>6}")
    for i, s in enumerate(r["subs"]):
        d = s["data"]
        c = collections.Counter(d)
        h = -sum((v / len(d)) * math.log2(v / len(d)) for v in c.values())
        print(f"  {i:>3} {s['type']:#05x} {s['addr']:#09x} {s['size']:>7} "
              f"{'YES' if s['written_by_official_tool'] else 'skip':>10} "
              f"{100*(d.count(0)/len(d)):>6.2f} {h:>6.3f}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "orig_TB14P.bin"
    base = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x113C
    raw = load(path)
    print(f"== {path} @ 0x{base:x} ==")
    report(parse(raw[base:]))
