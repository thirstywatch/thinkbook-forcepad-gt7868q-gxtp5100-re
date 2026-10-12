#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
lab__r32_official_seq.py — 复刻官方更新序列（分步可停 + 强制恢复路径）

★ 依据
------
`goodix/gdix_hid_firmware_update`（官方，master）：
  · `gt7868q/gt7868q_update.cpp:122-311`  GT7868QUpdate::fw_update
  · `gtx2/gtx2_update.cpp:139-213`        GTx2Update::load_sub_firmware
  · `gtx5/gtx5.cpp:227-309`               两条传输原语
  · `gt7868q/gt7868q.h:23` / `gtx2/gtx2_update.h:24-26` / `gt_update.h:9`  常量

★ 官方序列（本脚本按此逐步实现）
------------------------------
  ① 0E 10 00 00 01 01                 切到 patch / bootloader      → usleep 250ms
  ② 写 0x4160 ← {33,00,00,00,33}      关坐标上报（重发 3 次）
  ③ 读 0x5095 轮询 == 0xDD            等 bootloader（6 × 30ms）
  ④ 0E 11 00 00 01 01                 启动更新                    → usleep 100ms
  ⑤ 逐块：写 0xC000 → 0E 12 → 轮询 0x5096 == 0xAA
  ⑥ 写 0x4160 ← {34,00,00,00,34}      开坐标上报
  ⑦ 0E 13 00 00 01 01                 复位 IC（使新配置生效）     → usleep 300ms
  ⑧ 写 0x4160 ← {32,00,00,00,32}      切 PTP 模式

★ 分步执行（--stage），每步独立，可随时停
------------------------------------
  base      只读：基线快照 + **多次读 0x5095 查稳定性**
  rehearse  ★ 演练恢复路径：只发复位 0E 13，确认设备能恢复（低风险）
  enter     ①②③④：进 patch 并启动更新
  persist   ⑤：幂等 0E 12（写回从目标读出的【原样内容】）
  exit      ⑥⑦⑧：开坐标 + 复位 + 切 PTP
  all       rehearse → base → enter → persist → exit（任一步失败则立即跳到 exit）

★ 安全
------
  · 默认 **dry**（不加 --commit 不打开设备）
  · **写入目标受白名单限制**；**必须先读回原内容**，否则拒绝
  · **每一步的 finally 都会尽力把设备带回正常态**（发 0E 13 + 恢复坐标上报）
  · 全程打日志到 `_r32_log.txt`
"""
import sys, os, time, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import gxmem
except Exception as e:
    print("[FATAL] 需同目录 gxmem.py: %r" % e)
    raise SystemExit(2)

# ── 官方常量 ──
CMD_ADDR          = 0x4160
BL_STATE_ADDR     = 0x5095
FLASH_RESULT_ADDR = 0x5096
FLASH_BUFFER_ADDR = 0xC000
RAM_BUFFER_SIZE   = 4096
CFG_FLASH_ADDR    = 0x19000

BL_STATE_READY    = 0xDD
FLASH_RESULT_OK   = 0xAA

CMD_SWITCH_PATCH  = 0x10
CMD_START_UPDATE  = 0x11
CMD_LOAD_FLASH    = 0x12
CMD_RESET         = 0x13
CMD_PTP_MODE      = 0x32
CMD_COOR_OFF      = 0x33
CMD_COOR_ON       = 0x34

# ★ 写入白名单（实机目标）：addr -> 整块长度（来自镜像表，勿凭猜）
ALLOWED = {
    0x012000: 4096,    # ★ idx12, type 0x02 —— 2026-10-12 起的新默认首选靶（单块 4096、非 CONFIG 类）
    0x013000: 12288,   # idx11, type 0x02
    0x001000: 12288,   # idx8,  type 0x02
    0x0A000: 8192,     # idx4,  type 0x03 —— ⚠️ 2026-10-12 实测【造成退化】，勿再作首个靶
    0x19000: 1084,     # ★ CFG_FLASH_ADDR —— 官方 flash_cfg_with_isp() 的 cfg 落盘目标（1084 B）
}
# ★★ 2026-10-12 新增硬闸门：首次实机靶【只允许】type 0x02（非 CONFIG 类）。
#    代价：2026-10-10 写 type 0x03 的 idx1 → 退化；2026-10-12 写 type 0x03 的 idx4 → 再次退化。
#    （见 docs/08-findings/2026-10-12-首次0E12成功0xAA-与同型退化.md）
CONFIG_CLASS_TYPE = 0x03
GDIX_RETRY_TIMES = 6       # 官方 gtx5.h:41 —— 官方在 0x5096 != 0xAA 时会【重发同一块】

LOG = []
STATE = {"in_bootloader": False}   # ★ 只有真的进过 bootloader 才允许触发 recover()


def log(s):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%H:%M:%S"), s)
    print(line)
    LOG.append(line)


def flush_log():
    try:
        with open(os.path.join(HERE, "_r32_log.txt"), "a", encoding="utf-8") as f:
            f.write("\n".join(LOG) + "\n")
    except Exception:
        pass


# ── 帧构造 ──
def framed_cmd(code):
    return bytes([0x0E, code, 0x00, 0x00, 0x01, 0x01])


def cmd_init(cmd, d_hi=0, d_lo=0):
    ck = (cmd + d_hi + d_lo) & 0xFFFF
    return bytes([cmd, d_hi, d_lo, (ck >> 8) & 0xFF, ck & 0xFF])


def framed_load_flash(addr, length, checksum):
    return bytes([0x0E, 0x12, 0x00, 0x00, 0x06,
                  (length >> 8) & 0xFF, length & 0xFF,
                  (addr >> 16) & 0xFF, (addr >> 8) & 0xFF,
                  (checksum >> 8) & 0xFF, checksum & 0xFF])


def ck16be_word_sum(data):
    s = 0
    for i in range(0, len(data) - 1, 2):
        s = (s + ((data[i] << 8) + data[i + 1])) & 0xFFFF
    return s


def hx(b, n=32):
    if not b:
        return "<null>"
    return " ".join("%02X" % x for x in b[:n]) + ("…" if len(b) > n else "")


# ── 原子操作 ──
def send_cmd(g, code, wait_ms=0, retries=3):
    """发直发命令帧（原语 B）。返回 True/False。"""
    for i in range(retries):
        if g._send(list(framed_cmd(code))):
            log("    0E %02X 已发出（第 %d 次）" % (code, i + 1))
            if wait_ms:
                time.sleep(wait_ms / 1000.0)
            return True
        time.sleep(0.02)
    log("    ⚠️ 0E %02X 发送失败（%d 次）" % (code, retries))
    return False


def write_cmd_reg(g, cmd, d_hi=0, d_lo=0, retries=3):
    """写 0x4160 的 5 字节命令（原语 A）：{cmd, dHi, dLo, ckHi, ckLo}"""
    payload = cmd_init(cmd, d_hi, d_lo)
    for i in range(retries):
        if g.write(CMD_ADDR, payload):
            return True
        time.sleep(0.01)
    log("    ⚠️ 写 0x4160 ← %s 失败" % hx(payload, 5))
    return False


def read_byte(g, addr):
    d, _ = g.read(addr, 1)
    return d[0] if d else None


def read_bl_state_stable(g, need=5, gap_ms=30, max_tries=30):
    """★ 纪律 126：多次读确认稳定后再返回。返回 (value, stable?)"""
    seq = []
    for _ in range(max_tries):
        v = read_byte(g, BL_STATE_ADDR)
        seq.append(v)
        if len(seq) >= need and all(x == seq[-1] for x in seq[-need:]):
            return seq[-1], True
        time.sleep(gap_ms / 1000.0)
    return (seq[-1] if seq else None), False


def poll_flash_result(g, ok_val=FLASH_RESULT_OK, tries=100, gap_ms=2):
    for i in range(tries):
        time.sleep(gap_ms / 1000.0)
        v = read_byte(g, FLASH_RESULT_ADDR)
        if v == ok_val:
            log("      轮询 0x5096 第 %d 次 = 0x%02X ⇒ ✅" % (i + 1, v))
            return True
    log("      轮询 0x5096 %d 次未见 0x%02X（末值 %s）" % (tries, ok_val, hx(bytes([v]) if v is not None else b'')))
    return False


# ── 健康检查 ──
def health(g, tag=""):
    log("  [健康检查 %s]" % tag)
    h = {}
    h["0x4160"] = read_byte(g, CMD_ADDR)
    h["0x5095"] = read_byte(g, BL_STATE_ADDR)
    h["0x5096"] = read_byte(g, FLASH_RESULT_ADDR)
    d, lgd = g.read(0x96F8, 8)
    h["0x96F8"] = hx(d, 8)
    for k, v in h.items():
        log("    %-8s = %s" % (k, ("0x%02X" % v) if isinstance(v, int) and v is not None else v))
    return h


# ── 恢复路径（finally 里必跑）──
def recover(g, reason):
    log("")
    log("★ [恢复路径] 触发原因：%s" % reason)
    try:
        send_cmd(g, CMD_RESET, wait_ms=300, retries=3)
        log("    → 已发复位 0E 13")
    except Exception as e:
        log("    ⚠️ 复位发送异常：%r" % e)
    try:
        write_cmd_reg(g, CMD_COOR_ON)
        log("    → 已发 {34} 开坐标上报")
    except Exception as e:
        log("    ⚠️ 开坐标异常：%r" % e)
    try:
        write_cmd_reg(g, CMD_PTP_MODE)
        log("    → 已发 {32} 切 PTP")
    except Exception as e:
        log("    ⚠️ 切 PTP 异常：%r" % e)
    health(g, "恢复后")


# ── 各阶段 ──
def stage_base(g):
    log("【base】只读基线")
    log("-" * 66)
    for a, n, note in [(0x96F8, 32, "CFG_START_ADDR(RAM)"),
                       (CFG_FLASH_ADDR, 32, "CFG_FLASH_ADDR(flash)")]:
        d, _ = g.read(a, n)
        log("  0x%05X  %-24s %s" % (a, note, hx(d, 32)))
    v, stable = read_bl_state_stable(g)
    log("  0x5095 多次读：末值 0x%02X，稳定=%s" % ((-1 if v is None else v), stable))
    health(g, "base")
    return True


def stage_rehearse(g):
    """★ 演练恢复路径：只发复位，确认设备能恢复健康。"""
    log("【rehearse】演练恢复路径（只发 0E 13 复位）")
    log("-" * 66)
    before = health(g, "复位前")
    if not send_cmd(g, CMD_RESET, wait_ms=300, retries=3):
        log("  ❌ 复位命令发送失败 ⇒ 准备终止")
        return False
    after = health(g, "复位后")
    ok = after.get("0x4160") is not None and after.get("0x96F8") == before.get("0x96F8")
    log("  %s 演练结论：复位后 0x96F8 与复位前%s" %
        ("✅" if ok else "⚠️", "一致" if ok else "不一致（需人工复查）"))
    return ok


def stage_enter(g):
    log("【enter】进 patch + 启动更新（① ② ③ ④）")
    log("-" * 66)
    log("  ① 0E 10 切 patch …")
    if not send_cmd(g, CMD_SWITCH_PATCH, wait_ms=250):
        return False
    log("  ② 写 0x4160 ← {33} 关坐标上报（官方重发 3 次）…")
    write_cmd_reg(g, CMD_COOR_OFF)
    log("  ③ 读 0x5095 等 0xDD …")
    v, stable = read_bl_state_stable(g, need=5)
    log("     末值 0x%02X（需连续 5 次相同；稳定=%s）" % ((-1 if v is None else v), stable))
    if v != BL_STATE_READY:
        log("  ❌ 0x5095 未变成 0xDD ⇒ **未进入 bootloader**，不继续发 0E 11")
        return False
    log("  ✅ 已进入 bootloader 态")
    log("  ④ 0E 11 启动更新 …")
    if not send_cmd(g, CMD_START_UPDATE, wait_ms=100):
        return False
    log("  ✅ enter 阶段完成")
    STATE["in_bootloader"] = True
    return True


def stage_persist(g, flash_addr, image_path=None, payload_off=0x0113C, payload_size=100608,
                  allow_cfg_class=False):
    """幂等 0E 12。

    ★★ 数据来源已更正（2026-10-10）：
      实验证明设备读通道在 flash 地址上读到的是【RAM/采样窗口】而非静态内容
      （`0x0A3C0` 连读 5 次完全不同）⇒ **不能用"读设备"来做幂等**。
      改用 **官方 .bin 里解出的【原样内容】**：
        设备当前跑的就是这份官方固件（`0x96F8` 前 32 B 与容器一致已证）
        ⇒ 把官方内容写回官方地址 = 官方流程本身 = 幂等 ⇒ **无需读设备**。
    """
    log("【persist】幂等 0E 12（目标 0x%06X，数据源=官方镜像）" % flash_addr)
    log("-" * 66)

    if image_path is None:
        log("  [ABORT] 未提供 --image（官方固件容器）。")
        log("          ★ 不能用读设备的方式取数据 —— 该通道读不到静态 flash 内容（纪律 127）。")
        return False
    block = ALLOWED.get(flash_addr)
    if block is None:
        log("  [REFUSE] 地址 0x%06X 不在白名单 %s" % (flash_addr, [hex(x) for x in ALLOWED]))
        return False

    # 前置：必须在 bootloader
    v, stable = read_bl_state_stable(g)
    if v != BL_STATE_READY:
        log("  [ABORT] 0x5095=0x%02X ≠ 0xDD ⇒ 不在 bootloader，拒绝发 0E 12" % (-1 if v is None else v))
        return False

    STATE["in_bootloader"] = True   # ★ 已确认在 bootloader 态

    # 从官方镜像里取内容 + 地址
    d = open(image_path, 'rb').read()
    A = d[payload_off:payload_off + payload_size]
    if len(A) < payload_size or (int.from_bytes(A[0:4], 'big') + 6) != payload_size:
        log("  [ABORT] 官方镜像校验失败（长度字段不符）⇒ 拒绝")
        return False
    # 找匹配 flash_addr 的表项
    ent = None
    cur = 0x100
    for i in range(A[0x1B]):
        p = 0x20 + i * 8
        ln = int.from_bytes(A[p + 1:p + 5], 'big')
        fa = int.from_bytes(A[p + 5:p + 7], 'big') << 8
        if fa == flash_addr:
            ent = {'i': i, 'type': A[p], 'len': ln, 'fa': fa, 'off': cur}
            break
        cur += ln
    if ent is None:
        log("  [ABORT] 官方镜像里没有 flash_addr=0x%06X 的块" % flash_addr)
        return False
    if ent['len'] != block:
        log("  [ABORT] 块长不符（镜像 %d vs 白名单 %d）" % (ent['len'], block))
        return False
    if ent['type'] == CONFIG_CLASS_TYPE and not allow_cfg_class:
        log("  [REFUSE] ★ 目标块 type=0x%02X = 官方 `FLASH_SUBSYS_TYPE_CONFIG`（CONFIG 类）。" % ent['type'])
        log("           2026-10-10（idx1）与 2026-10-12（idx4）两次退化都出在 type 0x03 块上。")
        log("           本机实测：写 type 0x03 块会破坏【点按震动 / 压力点击】。")
        log("           ⇒ 首次实机靶请改用 type 0x02：0x012000(idx12) / 0x013000(idx11) / 0x001000(idx8)。")
        log("           确实要用 CONFIG 类，请显式加 --allow-cfg-class。")
        return False
    if not (ent['type'] == 0x02 or ent['type'] == 0x03):
        log("  [ABORT] type=0x%02X 不在官方本机下发集合 flag=0x0C 内" % ent['type'])
        return False
    orig = A[ent['off']:ent['off'] + block]
    log("  ★ 数据源 = 官方镜像 idx%d（type 0x%02X, len %d, file 0x%05X）"
        % (ent['i'], ent['type'], ent['len'], ent['off']))
    log("     前 32 B: %s" % hx(orig))
    log("     ★ 幂等依据：设备当前持有该版本（cfg 前 32 B 与容器一致已证）⇒ 写回=不改动")

    for off in range(0, block, RAM_BUFFER_SIZE):
        ch = orig[off:off + RAM_BUFFER_SIZE]
        addr = flash_addr + off
        ok_chunk = False
        # ★ 2026-10-12：对齐官方 gtx2_update.cpp::load_sub_firmware ——
        #   官方在 0x5096 != 0xAA 时 **重发同一块**（retry_load++，最多 GDIX_RETRY_TIMES 次），
        #   而不是像本脚本原来那样直接中止。重发同一块 = 官方行为，且天然幂等。
        for attempt in range(1, GDIX_RETRY_TIMES + 1):
            log("  chunk @0x%06X (%d B) · 第 %d/%d 次…" % (addr, len(ch), attempt, GDIX_RETRY_TIMES))
            if send_flash_unit(g, addr, ch):
                ok_chunk = True
                break
            log("      ⚠️ 本块未报 0xAA —— 官方此时【重发同一块】；本脚本照做")
            time.sleep(0.02)
        if not ok_chunk:
            log("      ❌ 本块重试 %d 次仍失败 ⇒ 停止" % GDIX_RETRY_TIMES)
            return False

    log("  ✅ 全部 %d 块均报 0xAA" % (block // RAM_BUFFER_SIZE))
    log("  ★ 注意：本通道【读不到 flash】⇒ 无法读回比对；验证只能靠 `0x5096==0xAA` + 后续功能表现。")
    return True


CFG_RECORD_LEN = 1084
DEFAULT_CFG = os.path.join(HERE, "..", "..", "data", "reference", "lab__cfg_record_orig_1084.bin")


def pad_to_unit(data, unit=RAM_BUFFER_SIZE):
    """★★ 2026-10-12 修正：官方 fwupd 实现把每个写入单元【零填充】到 RAM_BUFFER_SIZE(4096)。

    依据 `fwupd/plugins/goodix-tp/fu-goodixtp-gtx8-device.c`
    （作者 `xulinkun@goodix.com`，即官方）：
        guint8 buf_align4k[RAM_BUFFER_SIZE] = {0};
        fu_memcpy_safe(buf_align4k, sizeof(buf_align4k), 0, data, len, 0, len, error);
        hid_write(FLASH_BUFFER_ADDR, buf_align4k, sizeof(buf_align4k));     // 恒写 4096
        check_sum = fu_sum16w(buf_align4k, sizeof(buf_align4k), BIG_ENDIAN); // 按 4096 算
        fu_memwrite_uint16(buf_load_flash + 5, sizeof(buf_align4k), BIG_ENDIAN); // unitlen 恒 4096

    ⇒ 传非 4096 的 unitlen（如 1084）会得到 `0xBB`（IC 按 4096 缓冲算校验和）。
    """
    data = bytes(data)
    if len(data) > unit:
        raise ValueError("数据 %d > 单元 %d" % (len(data), unit))
    return data + b"\x00" * (unit - len(data))


def send_flash_unit(g, flash_addr, data, tag=""):
    """★ 以一个完整 4096 B 单元执行 `0x12`（零填充 + unitlen=4096 + u16BE 字和）。

    返回 True 表示 0x5096 报了 0xAA。**不做重试**（重试由调用方按官方语义处理）。
    """
    unit = pad_to_unit(data)
    if not g.write(FLASH_BUFFER_ADDR, unit):
        log("      ❌ 写 0xC000（%d B）失败" % len(unit))
        return False
    ck = ck16be_word_sum(unit)
    fr = framed_load_flash(flash_addr, len(unit), ck)
    log("      → %s   (ck=0x%04X, 实发 %d B, 补零 %d B)%s"
        % (hx(fr, 11), ck, len(unit), len(unit) - len(data), tag))
    if not g._send(list(fr)):
        log("      ❌ 0E 12 发送失败")
        return False
    time.sleep(0.08)          # 官方 usleep(80000)
    if poll_flash_result(g):
        g.write(FLASH_RESULT_ADDR, b"\x00")
        return True
    return False


def stage_persist_cfg(g, cfg_path=None):
    """★★ 官方 `flash_cfg_with_isp()` 的等价实现：把【cfg 记录（1084 B）】经 `0E 12` 写到 `0x19000`。

    ★ 这是 B12 的真正目标 —— **cfg 持久化的【官方机制】**：
      官方源码 `gt7868q_update.cpp::flash_cfg_with_isp()` 做的就是
      `load_sub_firmware(CFG_FLASH_ADDR /*0x19000*/, cfg, sub_cfg_len)`。
      ⚠️ 官方仅在 update flag 含 `NEED_UPDATE_CONFIG_WITH_ISP` 时才走这条路；
         **本机 `firmware_flag = 0x0C` 不含它** ⇒ 官方从不走 ⇒ 项目此前从未见过这一步，
         这也是"cfg 写入不落盘"（B12）长期无解的原因。
    """
    log("【persist-cfg】★ cfg → flash（官方 flash_cfg_with_isp 等价）· 目标 0x%06X · %d B"
        % (CFG_FLASH_ADDR, CFG_RECORD_LEN))
    log("-" * 66)
    path = cfg_path or DEFAULT_CFG
    if not os.path.isfile(path):
        log("  [ABORT] 找不到 cfg 记录文件：%s" % path)
        return False
    cfg = open(path, "rb").read()
    if len(cfg) != CFG_RECORD_LEN:
        log("  [ABORT] cfg 记录长度 %d ≠ %d" % (len(cfg), CFG_RECORD_LEN))
        return False
    log("  cfg 记录 %d B · 前 32 B: %s" % (len(cfg), hx(cfg, 32)))
    log("  ★ 幂等依据：设备当前 live cfg 前 32 B 与容器 cfg 逐字节相同（本回合 probe 已证）")

    v, stable = read_bl_state_stable(g)
    if v != BL_STATE_READY:
        log("  [ABORT] 0x5095=0x%02X ≠ 0xDD ⇒ 不在 bootloader，拒绝发 0E 12" % (-1 if v is None else v))
        return False
    STATE["in_bootloader"] = True

    for attempt in range(1, GDIX_RETRY_TIMES + 1):
        log("  第 %d/%d 次…" % (attempt, GDIX_RETRY_TIMES))
        if send_flash_unit(g, CFG_FLASH_ADDR, cfg):
            log("  ✅ cfg 已落盘：0x5096 == 0xAA")
            return True
        log("      ⚠️ 未报 0xAA —— 重发同一块（官方行为）")
        time.sleep(0.02)
    log("  ❌ 重试 %d 次仍未报 0xAA" % GDIX_RETRY_TIMES)
    return False


def stage_exit(g):
    log("【exit】开坐标 + 复位 + 切 PTP（⑥ ⑦ ⑧）")
    log("-" * 66)
    write_cmd_reg(g, CMD_COOR_ON)
    send_cmd(g, CMD_RESET, wait_ms=300)
    write_cmd_reg(g, CMD_PTP_MODE)
    health(g, "exit")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=["base", "rehearse", "enter", "persist", "cfg-persist", "exit", "all"])
    ap.add_argument("--flash-addr", type=lambda x: int(x, 0), default=0x012000,
                    help="★ 默认 0x012000（idx12, type 0x02, 4096 B）—— 单块、非 CONFIG 类，最小风险首靶")
    ap.add_argument("--allow-cfg-class", action="store_true",
                    help="★ 显式允许写 type 0x03（CONFIG 类）块 —— 已知会破坏点按震动/点击，慎用")
    ap.add_argument("--commit", action="store_true", help="★ 真正执行（不加则 dry）")
    ap.add_argument("--image", default=None, help="官方固件容器路径（persist 阶段的数据源，★ 不用读设备）")
    ap.add_argument("--cfg", default=None, help="cfg 记录文件（cfg-persist 阶段的数据源，默认 data/reference/lab__cfg_record_orig_1084.bin）")
    ap.add_argument("--with-cfg", action="store_true", help="★ 在 all 流程的 persist 之后，追加 cfg-persist（官方 flash_cfg_with_isp 等价）")
    ap.add_argument("--skip-persist", action="store_true", help="★ 跳过 persist（固件块）阶段；配合 --with-cfg 即只做 cfg 落盘")
    a = ap.parse_args()

    log("=" * 74)
    log("r32 · 复刻官方更新序列 · stage=%s · %s" % (a.stage, "COMMIT" if a.commit else "DRY"))
    log("=" * 74)

    if not a.commit:
        log("[DRY] 未加 --commit ⇒ 不打开设备。将执行的阶段：")
        plan = {"base": "只读基线 + 多次读 0x5095 查稳定性",
                "rehearse": "★ 只发复位 0E 13（演练恢复路径，低风险）",
                "enter": "0E 10 → {33} → 等 0x5095==0xDD → 0E 11",
                "persist": "★ 从【官方镜像】取原样内容（不读设备）→ 逐 4096 写 0xC000 → 0E 12 → 轮询 0x5096==0xAA",
                "cfg-persist": "★ 从 data/reference 取 1084 B cfg 记录 → 写 0xC000 → 0E 12 @0x19000 → 轮询 0x5096==0xAA（官方 flash_cfg_with_isp 等价）",
                "exit": "{34} → 0E 13 → {32}",
                "all": "rehearse → base → enter → persist → [--with-cfg: cfg-persist] → exit"}
        log("  " + plan[a.stage])
        return 0

    g = gxmem.Gx()
    if not g.open():
        log("[FATAL] 打开 Col04 失败")
        return 3
    failed = False
    try:
        if a.stage == "base":
            stage_base(g)
        elif a.stage == "rehearse":
            failed = not stage_rehearse(g)
        elif a.stage == "enter":
            failed = not stage_enter(g)
        elif a.stage == "persist":
            failed = not stage_persist(g, a.flash_addr, a.image, allow_cfg_class=a.allow_cfg_class)
        elif a.stage == "cfg-persist":
            failed = not stage_persist_cfg(g, a.cfg)
        elif a.stage == "exit":
            stage_exit(g)
        elif a.stage == "all":
            if not stage_rehearse(g):
                log("⚠️ 恢复路径演练未通过 ⇒ **终止，不进 bootloader**")
                flush_log()
                return 9
            stage_base(g)
            ok = stage_enter(g)
            if not ok:
                log("❌ enter 失败")
            elif not a.skip_persist:
                ok = stage_persist(g, a.flash_addr, a.image, allow_cfg_class=a.allow_cfg_class)
                if not ok:
                    log("❌ persist 失败")
            if ok and a.with_cfg:
                ok = stage_persist_cfg(g, a.cfg)
                if not ok:
                    log("❌ cfg-persist 失败（cfg 未落盘）")
            if ok:
                log("★ 全部写入阶段成功 ⇒ 进入 exit")
            failed = not ok
            stage_exit(g)
    finally:
        # ★ 修正（2026-10-10）：只有【真的进过 bootloader】才触发恢复路径。
        # 前置检查 ABORT 时什么都没改动，不应发 0E13 / 写 0x4160（此前会误发）。
        if a.stage in ("enter", "persist", "all") and failed and STATE["in_bootloader"]:
            recover(g, "阶段失败（已进 bootloader）")
        elif failed:
            log("(未进 bootloader ⇒ 未改动任何状态 ⇒ **不触发恢复路径**，不发送任何命令)")
        g.close()
        flush_log()
        log("日志已写入 _r32_log.txt")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
