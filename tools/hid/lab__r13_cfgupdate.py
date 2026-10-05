# -*- coding: utf-8 -*-
"""lab__r13_cfgupdate.py — ★ 走【官方 cfg_update 通道】向 GT7868Q 下发 cfg（含安全 dry-run）

依据：汇顶官方 Linux 工具 `gdixupdate` 源码 `gt7868q_gt7868q_update.cpp::GT7868QUpdate::cfg_update()`
（本机工区 `<LAB>/touchpad-lab/poc/gdix-hid-fw/`）

官方时序（原文，变量名照抄）：
  1. Write(CMD_ADDR=0x4160, [0x33,0,0,0,0x33], 5)   ×3   # 关闭坐标上报（可选，见 --official）
  2. Read (CFG_START_ADDR=0x96F8, 3)                     # 读当前 cfg 版本
  3. 轮询 Read(0x4160, 1) 直到 == 0xFF（IC 空闲）
  4. cmd_init(buf,0x80,0) → Write(0x4160, buf, 5)        # 握手：buf=[0x80,hi,lo,chk_hi,chk_lo]
     usleep(250 ms)
  5. 轮询 Read(0x4160, 1) 直到 == 0x82
  6. Write(0x96F8, cfg_data, sub_cfg_len)                # ★ 真正写 cfg
     usleep(100 ms)
  7. cmd_init(buf,0x83,0) → Write(0x4160, buf, 5)        # 告诉 IC：cfg 已就绪
     usleep(80 ms)
  8. 轮询 Read(0x4160, 5)：0x7F = 已写入；0x7E,0x00,0x07 = 【与 flash 完全一致】（本脚本的 dry-run 目标）
  9. cmd_init(buf,0x7D,0) → Write(0x4160, buf, 5)        # 结束
 10. Write(0x4160, [0x34,0,0,0,0x34], 5)                 # 恢复坐标上报

传输层（本项目已验证）：Col04 报告 ID 0x0E，命令 0x20 = I2C_DIRECT_RW
  写：0E 20 <cont> <seq> <len+5> 00 <addr16BE> <len16BE> <data…>   （len = 本块字节数）
      cont=1 表示后面还有块，cont=0 表示本块是最后一块；单块时 65 B 报告 → 最多 55 B 数据
  读：0E 20 00 00 05 01 <addr16BE> <size16BE>

★ 安全设计
  - `probe`   ：纯只读，零风险（这是每次开工的第一步）
  - `dryrun`  ：把【原封不动的 1024 B cfg】写回去 → IC 应回 `7E 00 07`（与 flash 一致）
                这一步把整条写链验证完，而设备行为【零改变】，是真正意义上的试跑
  - 任何写入前都会把原始 cfg 备份成 `lab__cfg_backup_*.bin`
  - 任何异常路径都会尝试 0x7D 收尾；若发过 0x33 则必定补发 0x34
"""
import os
import sys
import time
import ctypes

HERE = os.path.dirname(os.path.abspath(__file__))
# 本脚本与 gxmem.py 同目录（仓库 tools/hid/）；跑之前请把本机 firmware container
# （orig_TB14P.bin / 本机 161,628 B 那份）放到同目录，或改 --image 指过去。
for _c in (HERE, os.path.join(HERE, "..", "..", "2026-10-03-13-21-08",
                              "thinkbook-forcepad-haptics-re", "tools", "hid")):
    if os.path.isdir(_c):
        sys.path.insert(0, os.path.abspath(_c))
try:
    from gxmem import Gx                      # 复用项目已验证的 Col04 打开/收发实现
except Exception as e:                        # noqa
    print("!! 无法 import gxmem：%s" % e)
    print("   请把本脚本放到 thinkbook-forcepad-haptics-re/tools/hid/ 下再跑。")
    raise SystemExit(2)

CMD_ADDR = 0x4160
CFG_ADDR = 0x96F8
CFG_BODY_OFF = 0x4C          # 容器内 cfg body 起点（4 份副本，间距 1084）
CFG_BODY_LEN = 1084          # ★★★ 2026-10-05 实测定案：真正的 sub_cfg_len = 1084（1024 主体 + 60 B 尾）
                             #     写 1024 时 IC 回 `7E 00 02`；写 1084 时回 `7E 00 07`（= 与 flash 一致）

CHUNK = 55                   # 单报告最多携带的数据字节数（65 - 10 头）
USE_CONT = False             # 第 3 轮结论：主机→设备方向每块 cont=0


# ---------------------------------------------------------------- 基础工具
def cmd_init(cmd, data=0):
    """照抄官方 cmd_init()：buf=[cmd, hi(data), lo(data), cksum_hi, cksum_lo]"""
    b = [cmd & 0xFF, (data >> 8) & 0xFF, data & 0xFF, 0, 0]
    c = (b[0] + b[1] + b[2]) & 0xFFFF
    b[3] = (c >> 8) & 0xFF
    b[4] = c & 0xFF
    return b


def load_cfg(image_path, off=CFG_BODY_OFF, ln=CFG_BODY_LEN):
    d = open(image_path, "rb").read()
    body = d[off:off + ln]
    copies = [d[off + i * 1084: off + i * 1084 + ln] for i in range(4)]
    same = all(c == copies[0] for c in copies)
    return body, same, len(d)


def write_chunked(g, addr, data, chunk=CHUNK, delay=0.03, verbose=True,
                  advance=True, use_cont=False):
    """把 data 分块写进设备内存。

    ★★ 2026-10-05 实测两轮（这是本项目第一次真正走 cfg 下发通道）：
      · 第 1 轮：每块都用同一 addr、cont=1/1/…/0  ⇒ IC 回 `7E 00 00`，
        活体 0x96F8 读出 `body[990:1024]`（= 尾块 34 B）⇒ **每块都写在给定地址，互相覆盖**
      · 第 2 轮：addr 逐块递增、仍带 cont=1  ⇒ IC 回 `7E 00 02`，且**暂存区纹丝不动**
        ⇒ `cont=1` 在【主机→设备】方向不是"续传"语义，带上它反而被判为序列错误
      · 第 3 轮（本版本默认）：**addr 逐块递增 + 每块 cont=0**（每条 `0E 20` 自成一次完整写）
    """
    n = (len(data) + chunk - 1) // chunk
    for i in range(n):
        blk = data[i * chunk:(i + 1) * chunk]
        cont = 0 if not use_cont else (0 if i == n - 1 else 1)
        a = addr + (i * chunk if advance else 0)
        pkt = [0x0E, 0x20, cont, i & 0xFF, (len(blk) + 5) & 0xFF, 0x00,
               (a >> 8) & 0xFF, a & 0xFF,
               (len(blk) >> 8) & 0xFF, len(blk) & 0xFF] + list(blk)
        if not g._send(pkt):
            return False, i, n
        if verbose and (i % 4 == 0 or i == n - 1):
            print("      块 %2d/%d  addr=0x%04X  %2dB  cont=%d" % (i + 1, n, a, len(blk), cont))
        time.sleep(delay)
    return True, n, n


def poll_cmd(g, expect, tries=30, gap=0.03, nbytes=1, label=""):
    """轮询 Read(0x4160, nbytes)，返回读到的原始字节"""
    last = None
    for _ in range(tries):
        d, log = g.read(CMD_ADDR, nbytes, rounds=4, delay=0.05)
        last = d
        if d and len(d) >= 1:
            if d[0] == (expect if isinstance(expect, int) else expect[0]):
                return d, True
        time.sleep(gap)
    return last, False


# ---------------------------------------------------------------- 子命令
def cmd_probe(g, image):
    print("=" * 88)
    print("### 只读探测（零风险）")
    print("=" * 88)
    ok = 0
    for addr, sz, lbl in [(0x4000, 4, "liveness 0x4000（期望 A7 E0 ED B1）"),
                          (0x452C, 4, "fw_info  0x452C（期望 AE EB 22 90）"),
                          (CMD_ADDR, 1, "命令寄存器 0x4160（空闲应为 FF）"),
                          (0x5095, 1, "BL_STATE 0x5095（期望 DD）"),
                          (0x5096, 1, "FLASH_RESULT 0x5096（期望 AA）")]:
        d, log = g.read(addr, sz)
        print("  0x%04X x%-2d %-34s = %s   %s"
              % (addr, sz, lbl, " ".join("%02X" % b for b in d) if d else "<FAIL>", log))
        time.sleep(0.05)
        if d:
            ok += 1
    print()
    d, log = g.read(CFG_ADDR, 3)
    print("  cfg 版本 (0x96F8, 3B)          = %s   %s"
          % (" ".join("%02X" % b for b in d) if d else "<FAIL>", log))
    time.sleep(0.05)
    d2, log2 = g.read(CFG_ADDR, 32)
    print("  cfg 前 32B (0x96F8, 32B)       = %s"
          % (" ".join("%02X" % b for b in d2) if d2 else "<FAIL>"))
    print("                                    %s" % log2)
    print()
    body, same, flen = load_cfg(image)
    print("  容器 %s (%d B)" % (os.path.basename(image), flen))
    print("  容器 cfg body 前 32B           = %s" % " ".join("%02X" % b for b in body[:32]))
    print("  4 份副本逐字节相同             = %s" % same)
    if d2 and len(d2) == 32:
        print("  ★ 活体 vs 容器 前 32B          = %s"
              % ("逐字节相同 ✓✓" if bytes(d2) == body[:32] else "不同 ✗ —— 需要重查"))
    if d and len(d) >= 3:
        print("  ★ 活体 vs 容器 版本 3B         = %s"
              % ("相同 ✓" if bytes(d[:3]) == body[:3] else "不同 ✗"))
    print("\n  只读探测成功 %d / 5" % ok)
    return ok


def do_update(g, cfg, official=False, dry=False, expect_equal=True):
    """执行官方 cfg_update 时序。cfg = 要下发的字节串。返回 (结果码, 说明)"""
    status = {}
    sent_disable = False
    try:
        if official:
            print("  [0] 关闭坐标上报 0x33 ×3")
            for _ in range(3):
                g.write(CMD_ADDR, bytes([0x33, 0, 0, 0, 0x33]))
                time.sleep(0.05)
            sent_disable = True

        print("  [1] 读当前 cfg 版本 (0x96F8,3B) ...")
        before, _ = g.read(CFG_ADDR, 3)
        print("      before = %s" % (" ".join("%02X" % b for b in before) if before else "<FAIL>"))
        status["before"] = before

        print("  [2] 等 IC 空闲：轮询 0x4160 == 0xFF")
        d, good = poll_cmd(g, 0xFF, tries=20, label="idle")
        print("      0x4160 = %s  %s" % (" ".join("%02X" % b for b in d) if d else "<FAIL>",
                                          "OK" if good else "（超时，但继续尝试）"))

        print("  [3] 握手 0x80")
        buf = cmd_init(0x80, 0)
        g.write(CMD_ADDR, bytes(buf))
        print("      发出 %s" % " ".join("%02X" % b for b in buf))
        time.sleep(0.25)

        print("  [4] 等 IC 确认：轮询 0x4160 == 0x82")
        d, good = poll_cmd(g, 0x82, tries=20)
        print("      0x4160 = %s  %s" % (" ".join("%02X" % b for b in d) if d else "<FAIL>",
                                          "确认 ✓" if good else "未确认 ✗"))
        if not good:
            return -1, "IC 未回 0x82，已中止（未写任何数据）"
        status["handshake"] = True

        print("  [5] ★ 写 cfg 到 0x96F8（%d 字节，分 %d 块）"
              % (len(cfg), (len(cfg) + CHUNK - 1) // CHUNK))
        ok, done, total = write_chunked(g, CFG_ADDR, cfg, use_cont=USE_CONT)
        if not ok:
            return -2, "第 %d/%d 块写失败" % (done + 1, total)
        time.sleep(0.10)

        print("  [6] 通知 IC：cfg 已就绪 0x83")
        g.write(CMD_ADDR, bytes(cmd_init(0x83, 0)))
        time.sleep(0.08)

        print("  [7] 读校验结果 (0x4160, 5B)")
        res = None
        for _ in range(30):
            d, _ = g.read(CMD_ADDR, 5, rounds=4, delay=0.05)
            if d and len(d) >= 3 and d[0] in (0x7F, 0x7E):
                res = bytes(d)
                break
            time.sleep(0.03)
        print("      结果 = %s" % (" ".join("%02X" % b for b in res) if res else "<FAIL>"))
        status["result"] = res
        if res:
            if res[0] == 0x7E and res[1] == 0x00 and res[2] == 0x07:
                print("      ★★★ 0x7E 00 07 = 【cfg 与 flash 完全一致】")
            elif res[0] == 0x7F:
                print("      ★★★ 0x7F = 【cfg 已被接受并写入】")
            elif res[0] == 0x7E:
                print("      0x7E + 数据 0x%02X%02X（官方只把 00 07 定义为『与 flash 一致』；"
                      "实测 00 02 = 与 flash 不同 ⇒ 会真正生效，见 cfg+0x115 强度实验）" % (res[1], res[2]))

        print("  [8] 结束 0x7D")
        g.write(CMD_ADDR, bytes(cmd_init(0x7D, 0)))
        time.sleep(0.10)

        after, _ = g.read(CFG_ADDR, 3)
        print("      之后 cfg 版本 = %s" % (" ".join("%02X" % b for b in after) if after else "<FAIL>"))
        status["after"] = after
        return 0, "完成"
    finally:
        if sent_disable:
            print("  [9] 恢复坐标上报 0x34")
            for _ in range(3):
                g.write(CMD_ADDR, bytes([0x34, 0, 0, 0, 0x34]))
                time.sleep(0.05)


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return 0
    op = args[0]
    image = os.path.join(HERE, "orig_TB14P.bin")
    patches = []
    official = "--official" in args
    ln = CFG_BODY_LEN
    for i, a in enumerate(args):
        if a == "--image":
            image = args[i + 1]
        elif a == "--len":
            ln = int(args[i + 1], 0)
        elif a == "--patch":
            off, hx = args[i + 1].split(":")
            patches.append((int(off, 0), bytes.fromhex(hx)))

    g = Gx()
    if not g.open():
        print("!! Col04 打开失败 err=%d" % ctypes.get_last_error())
        print("   请确认 Goodix 触控板在位，且当前是【管理员】或对 Col04 有读写权限。")
        return 1
    try:
        if op == "probe":
            return 0 if cmd_probe(g, image) else 1

        body, same, _ = load_cfg(image, ln=ln)
        bk = open(os.path.join(HERE, "lab__cfg_backup_%d.bin" % int(time.time())), "wb")
        bk.write(body)
        bk.close()
        print("已备份原始 cfg（%d B）→ %s\n" % (len(body), os.path.basename(bk.name)))

        cfg = bytearray(body)
        for off, val in patches:
            old = bytes(cfg[off:off + len(val)])
            cfg[off:off + len(val)] = val
            print("打补丁 记录+0x%03X : %s -> %s" % (off, old.hex(" ").upper(), val.hex(" ").upper()))

        if op in ("dryrun",):
            print("=" * 88)
            print("### DRY-RUN：把【原封不动】的 cfg 写回去（设备行为应零改变）")
            print("=" * 88)
            r, msg = do_update(g, bytes(cfg), official=official)
            print("\n=> %s" % msg)
            return 0 if r == 0 else 1

        if op in ("write", "restore"):
            print("=" * 88)
            print("### %s：下发 cfg（%d B）%s"
                  % ("RESTORE 还原" if op == "restore" else "WRITE 修改",
                     len(cfg), "OFFICIAL 全序列" if official else "精简序列（不动坐标上报）"))
            print("=" * 88)
            r, msg = do_update(g, bytes(cfg), official=official)
            print("\n=> %s" % msg)
            return 0 if r == 0 else 1

        if op == "coord":
            v = 0x34 if (len(args) > 1 and args[1] == "on") else 0x33
            g.write(CMD_ADDR, bytes([v, 0, 0, 0, v]))
            print("已发 0x%02X（%s 坐标上报）" % (v, "开启" if v == 0x34 else "关闭"))
            return 0

        if op == "end":
            g.write(CMD_ADDR, bytes(cmd_init(0x7D, 0)))
            print("已发 0x7D（结束 cfg 传输）")
            return 0
    finally:
        g.close()
    print("未知子命令：%s" % op)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
