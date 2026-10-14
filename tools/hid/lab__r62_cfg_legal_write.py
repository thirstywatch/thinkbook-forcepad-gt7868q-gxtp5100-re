# -*- coding: utf-8 -*-
"""lab__r62_cfg_legal_write.py —— ★★★★★ 三例对照：官方 cfg 会话写入 × 袋校验和

★ 要回答的问题（本项目史上从未有过的干净对照）
------------------------------------------------
  用 `tools/hid/gdix_cfg_tool.py` 生成**重算过袋校验尾**的改写 cfg，走官方 cfg 会话流程写 `0x96F8`：
      A 原样（与 flash 逐字节相同）        → 预期 `7E 00 07` (DATA_EQU)
      B 合法改写（改数据 + **重算袋尾**）  → ？？？  ← 若得 `7F` 则**项目史上首次成功**
      C 非法改写（**同一处数据**、袋尾不动）→ 预期 `7E 00 02` (CHKSUM_ERR)
  **B 与 C 只差 2 字节（袋校验尾）** ⇒ 若 B/C 结果码不同，`0x02 = 校验和错误` 即被**单变量**证实。

★ 依据
------
  · 官方 `gtx8drv_goodix_ts_i2c.c:83-88`  enum TS_SEND_CFG_REPLY
        PKGS_ERR=0x01 · **CHKSUM_ERR=0x02** · DATA_ERR=0x03 · DATA_EQU=0x07
  · 官方 `:930-937`  `buf[0]==0x7E` ⇒ **一律 `-EINVAL`（失败）**；子码在 `buf[2]`
  · 官方 `:847-935`  7 步：轮询 0xFF → 0x80 → 轮询 0x82 → 写 cfg → 0x83 → 读 3B → 0x7D
  · 官方 `gtx8drv_goodix_ts_core.h:579-587`  YS 袋校验 `sum(data[:-2]) == BE16(data[-2:])`
  · 本项目 `lab__r13_cfgupdate.py::write_chunked` 已验证的传输层：
        写 `0E 20 <cont=0> <seq> <len+5> 00 <addr16BE> <len16BE> <data…>`
        **addr 逐块 +55、每块 cont=0**（带 cont=1 会被判序列错误 ⇒ `7E 00 02`）
  · 本项目 §19.42b.3：**T2 会话态下 `0x96F8` 全 1084 B 可读且与所发内容逐字节相同**（IC 纯透传）

★ 安全性
--------
  · **只写 `0x96F8`（会话 RAM 暂存区）** —— §19.42b.4：`0x7D` 后暂存区被丢弃、IC 从 flash 重载
  · **绝不碰** `0x1E000` / `0xC000` / `0E 10 / 0E 11 / 0E 12`（那条是 flash 持久化路径）
  · 默认 **dry**；不加 `--commit` 不打开设备
  · `finally` 必发 `0x7D` 收尾 + 发 `0E 13` 复位 IC（保证从 flash 重载）+ 读回基线比对
"""
import sys, os, time, argparse, hashlib

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级为 '?'，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import gxmem
except Exception as e:
    print("[FATAL] 需同目录 gxmem.py: %r" % e)
    raise SystemExit(2)

CMD_ADDR = 0x4160
CFG_ADDR = 0x96F8
CHUNK    = 55          # 65 B 报告 − 10 B 头
CFG_LEN  = 1084

C_START_SEND_CFG  = 0x80
C_END_SEND_CFG    = 0x83
C_END_SEND_CFG_YS = 0x7D
REPLY_OK  = 0x7F       # TS_CMD_CFG_OK
REPLY_ERR = 0x7E       # TS_CMD_CFG_ERR
SUB = {0x01: "PKGS_ERR(袋/包错误)", 0x02: "CHKSUM_ERR(校验和错误)",
       0x03: "DATA_ERR(数据错误)",  0x07: "DATA_EQU(与 flash 完全一致)"}

BASE_CFG = os.path.join(HERE, "lab__cfg_backup_1791782094.bin")


def log(m=""):
    print(m, flush=True)


def hx(b):
    return b.hex(' ').upper() if b else '<FAIL>'


def mk_cmd(cmd, data=0):
    """官方 YS 5 字节命令帧 {cmd, dataHi, dataLo, sumHi, sumLo}（校验 = 前三字节和）"""
    hi, lo = (data >> 8) & 0xFF, data & 0xFF
    s = (cmd + hi + lo) & 0xFFFF
    return bytes([cmd, hi, lo, (s >> 8) & 0xFF, s & 0xFF])


def read_all(g, addr, n, rounds=6, delay=0.05):
    d, _ = g.read(addr, n, rounds=rounds, delay=delay)
    return bytes(d) if d else None


def write_chunked(g, cfg, addr0=CFG_ADDR, chunk=CHUNK, delay=0.03):
    """addr 逐块 +chunk、每块 cont=0（= lab__r13_cfgupdate.py 第 3 轮验证过的写法）"""
    n = (len(cfg) + chunk - 1) // chunk
    for i in range(n):
        blk = cfg[i * chunk:(i + 1) * chunk]
        a = addr0 + i * chunk
        pkt = [0x0E, 0x20, 0x00, i & 0xFF, (len(blk) + 5) & 0xFF, 0x00,
               (a >> 8) & 0xFF, a & 0xFF,
               (len(blk) >> 8) & 0xFF, len(blk) & 0xFF] + list(blk)
        if not g._send(pkt):
            return False, i, n
        time.sleep(delay)
    return True, n, n


def read_full_cfg(g, total=CFG_LEN):
    """T2 会话态全量读回（§19.42b.3：1084 B 可读且与所发逐字节相同）"""
    buf = bytearray()
    off = 0
    while off < total:
        n = min(64, total - off)
        d = read_all(g, CFG_ADDR + off, n)
        if not d or len(d) < 2:
            break
        buf += d
        off += len(d)
        if len(d) < n:
            break
    return bytes(buf)


def official_cycle(g, cfg, label, expect):
    log("\n" + "=" * 84)
    log("### %s" % label)
    log("    cfg sha256[:12] = %s   期望 = %s"
        % (hashlib.sha256(cfg).hexdigest()[:12], expect))
    log("=" * 84)

    # 官方 1) 轮询命令寄存器直到空闲 0xFF
    v, ok = None, False
    for _ in range(20):
        v = read_all(g, CMD_ADDR, 1)
        if v and v[0] == 0xFF:
            ok = True
            break
        time.sleep(0.03)
    log("  ① 0x4160 == 0xFF ？ %s   (值 %s)" % (ok, hx(v)))
    if not ok:
        log("  ❌ 命令寄存器不空闲 ⇒ 放弃本轮")
        return None

    # 官方 2) 读当前 cfg 版本（前 3 B）
    log("  ② 当前 cfg 头 3 B = %s" % hx(read_all(g, CFG_ADDR, 3)))

    # 官方 4) 发 0x80
    g.write(CMD_ADDR, mk_cmd(C_START_SEND_CFG))
    log("  ③ 已发 0x80 %s" % hx(mk_cmd(C_START_SEND_CFG)))
    time.sleep(0.25)

    # 官方 5) 轮询 == 0x82（SEND_CFG_PREPARE_OK）
    ok82 = False
    for _ in range(20):
        d = read_all(g, CMD_ADDR, 1)
        if d and d[0] == 0x82:
            ok82 = True
            break
        time.sleep(0.03)
    log("  ④ 0x4160 == 0x82 ？ %s" % ok82)
    if not ok82:
        log("  ❌ 握手失败 ⇒ 放弃本轮")
        return None

    # 官方 6) 写 cfg（1084 B，20 块 × 55 B，地址逐块 +55）
    okw, done, tot = write_chunked(g, cfg)
    log("  ⑤ 写入 %d/%d 块 -> %s" % (done, tot, okw))
    time.sleep(0.12)

    # ★ 会话态全量读回比对（§19.42b.3）
    rb = read_full_cfg(g)
    if rb:
        same = hashlib.sha256(rb).hexdigest() == hashlib.sha256(cfg).hexdigest()
        log("     读回 %d B  sha256[:12]=%s   与所发%s"
            % (len(rb), hashlib.sha256(rb).hexdigest()[:12],
               "逐字节相同 ✔" if same else "不同（前 32 B: %s）" % hx(rb[:32])))
    else:
        log("     读回 <FAIL>")

    # 官方 7) 发 0x83
    g.write(CMD_ADDR, mk_cmd(C_END_SEND_CFG))
    log("  ⑥ 已发 0x83 %s" % hx(mk_cmd(C_END_SEND_CFG)))
    time.sleep(0.10)

    # 官方 8) 读命令寄存器，等 buf[0] ∈ {0x7E, 0x7F}
    res = None
    for _ in range(30):
        d, _ = g.read(CMD_ADDR, 5, rounds=4, delay=0.05)
        if d and d[0] in (REPLY_OK, REPLY_ERR):
            res = bytes(d)
            break
        time.sleep(0.03)
    if res is None:
        log("  ⑦ 结果 = <FAIL>（超时未拿到 0x7E/0x7F）")
    elif res[0] == REPLY_OK:
        log("  ⑦ ★★★★ 结果 = %s ⇒ buf[0]=0x7F = TS_CMD_CFG_OK ⇒ **IC 接受并应用！**" % hx(res))
    else:
        sub = res[2] if len(res) > 2 else -1
        log("  ⑦ 结果 = %s ⇒ 0x7E + 子码 0x%02X = %s"
            % (hx(res), sub, SUB.get(sub, "未知")))

    # 官方 9) 发 0x7D 收尾
    g.write(CMD_ADDR, mk_cmd(C_END_SEND_CFG_YS))
    log("  ⑧ 已发 0x7D %s（会话结束，暂存区将被丢弃）" % hx(mk_cmd(C_END_SEND_CFG_YS)))
    time.sleep(0.12)
    return res


def mk_variants(base):
    """造 B / C 两份改写：只差【袋校验尾】2 字节"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gdixcfg", os.path.join(HERE, "gdix_cfg_tool.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _, _, bags = m.parse(base)
    tgt = next(x for x in bags if x[0] == 6)     # 本项目历史上 +0x10F / +0x115 都在 bag_id=6
    bid, o, ln, ck, end, st = tgt
    legal = bytearray(base)
    legal[0x116] = 0xF0                          # u16BE 120 -> 240
    s = sum(bytes(legal[o:end - 2])) & 0xFFFF
    legal[end - 2] = (s >> 8) & 0xFF
    legal[end - 1] = s & 0xFF
    illegal = bytearray(base)
    illegal[0x116] = 0xF0                        # 同一处改动，袋尾保持原值（= 非法）
    info = dict(bag_id=bid, off=o, end=end,
                tail_orig=bytes(base[end - 2:end]), tail_legal=bytes(legal[end - 2:end]))
    return bytes(legal), bytes(illegal), info


def mk_bag_variant(base, bag_id, fill):
    """【G2 逐袋扫描用】把指定袋的数据区整体填成 fill，并重算该袋校验尾（合法）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gdixcfg", os.path.join(HERE, "gdix_cfg_tool.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _, _, bags = m.parse(base)
    tgt = next((x for x in bags if x[0] == bag_id), None)
    if tgt is None:
        ids = ",".join(str(x[0]) for x in bags)
        raise SystemExit("袋 %d 不存在；本机袋号: %s" % (bag_id, ids))
    bid, o, ln, ck, end, st = tgt
    v = bytearray(base)
    # ★ 只填【袋数据区】：o 是袋起点（含 id/len），数据区 = o+2 .. o+2+ln
    #   （2026-10-14 预演抓到：先前从 o 开始填会覆盖 id/len ⇒ 解析器失同步，27 袋只剩 19 袋）
    for i in range(o + 2, min(o + 2 + ln, end - 2)):
        v[i] = fill & 0xFF
    s = sum(bytes(v[o:end - 2])) & 0xFFFF
    v[end - 2] = (s >> 8) & 0xFF
    v[end - 1] = s & 0xFF
    # 头校验（head[3:5] = sum(head[0:3])）也要跟着重算，否则整包会被拒
    h = sum(bytes(v[0:3])) & 0xFFFF
    v[3] = (h >> 8) & 0xFF
    v[4] = h & 0xFF
    return bytes(v), dict(bag_id=bid, off=o, end=end, fill=fill)


def rehearse(base, out_txt=None, out_json=None):
    """【G2 离线预演】不开设备：27 袋 × {0x00,0xFF} 各造一份合法变体，逐份用 ys_ck 验合法。

    目的：把"协议能不能执行"这件事在**零风险**下先证明一遍，并产出可直接抄的执行表。
    """
    import importlib.util, json
    spec = importlib.util.spec_from_file_location("gdixcfg", os.path.join(HERE, "gdix_cfg_tool.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _, _, bags = m.parse(base)
    base_illegal = [x[0] for x in bags if m.ys_ck(bytes(base[x[1]:x[4]])) != 0]
    rows = []
    print("基线 %d B · %d 袋 · 基线自身不合法袋: %s"
          % (len(base), len(bags), base_illegal if base_illegal else "无（全部 ck=0）"))
    for bid, o, ln, ck, end, st in bags:
        for fill in (0x00, 0xFF):
            v, _info = mk_bag_variant(base, bid, fill)
            _, _, vb = m.parse(v)
            legal = (len(vb) == len(bags)) and all(m.ys_ck(bytes(v[x[1]:x[4]])) == 0 for x in vb)
            h = (sum(v[0:3]) & 0xFFFF)
            head_ok = (v[3] == ((h >> 8) & 0xFF)) and (v[4] == (h & 0xFF))
            delta = sum(1 for i in range(len(base)) if base[i] != v[i])
            rows.append(dict(bag=bid, off=o, end=end, len=end - o, fill=fill,
                             delta=delta, legal=bool(legal), head_ok=bool(head_ok),
                             sha12=hashlib.sha256(v).hexdigest()[:12]))
    print("")
    print("袋号 | 偏移    | 长度 | 填充 | 改动字节 | 变体合法 | 头校验 | sha256[:12]")
    print("-----|---------|------|------|----------|----------|--------|------------")
    for r in rows:
        print("%4d | 0x%05X | %4d | 0x%02X | %8d | %-8s | %-6s | %s"
              % (r["bag"], r["off"], r["len"], r["fill"], r["delta"],
                 "✅" if r["legal"] else "❌", "✅" if r["head_ok"] else "❌", r["sha12"]))
    bad = [r for r in rows if not r["legal"] or not r["head_ok"]]
    print("")
    print("预演结果：%d 个变体，%d 个不合法 %s"
          % (len(rows), len(bad), "⇒ ✅ 全部可直接执行（协议 §3 步骤 2/3 就绪）" if not bad else "⇒ ❌ 需先修工具"))
    txt = []
    txt.append("G2 E 面逐袋扫描 · 离线预演表（2026-10-14，lab__r62_cfg_legal_write.py --rehearse）")
    txt.append("基线 cfg: %s  %d B  sha256[:12]=%s" % (os.path.basename(BASE_CFG), len(base), hashlib.sha256(base).hexdigest()[:12]))
    txt.append("基线不合法袋: %s" % (base_illegal if base_illegal else "无"))
    txt.append("")
    txt.append("袋号	偏移	长度	填充	改动字节	变体合法	头校验	sha256_12")
    for r in rows:
        txt.append("%d	0x%05X	%d	0x%02X	%d	%s	%s	%s"
                   % (r["bag"], r["off"], r["len"], r["fill"], r["delta"],
                      "OK" if r["legal"] else "BAD", "OK" if r["head_ok"] else "BAD", r["sha12"]))
    if out_txt:
        open(out_txt, "w", encoding="utf-8", newline="\n").write("\n".join(txt) + "\n")
        print("已写 " + out_txt)
    if out_json:
        open(out_json, "w", encoding="utf-8", newline="\n").write(json.dumps(dict(base_sha12=hashlib.sha256(base).hexdigest()[:12], rows=rows), ensure_ascii=False, indent=1))
        print("已写 " + out_json)
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true", help="真正打开设备（默认 dry）")
    ap.add_argument("--no-reset", action="store_true", help="收尾不发 0E 13 复位")
    ap.add_argument("--cases", default=None, help="要跑的例：A,B,C 或 D（默认 A,B,C；给 --bag 时默认 D）")
    ap.add_argument("--bag", type=int, default=None, help="【G2】只改这一个袋（配 --fill）")
    ap.add_argument("--fill", default="0x00", help="【G2】袋数据填充值，如 0x00 / 0xFF")
    ap.add_argument("--rehearse", action="store_true", help="【G2】离线预演：全部袋 × {0x00,0xFF} 造变体并验合法（不开设备）")
    ap.add_argument("--rehearse-txt", default=None, help="预演表输出路径")
    ap.add_argument("--rehearse-json", default=None, help="预演 JSON 输出路径")
    a = ap.parse_args()

    base = open(BASE_CFG, 'rb').read()
    if a.rehearse:
        return rehearse(base, a.rehearse_txt, a.rehearse_json)
    legal, illegal, info = mk_variants(base)
    log("基线 cfg   = %s  %d B  sha256[:12]=%s"
        % (os.path.basename(BASE_CFG), len(base), hashlib.sha256(base).hexdigest()[:12]))
    log("目标袋     = bag_id=%d  范围 %#x..%#x   原袋尾=%s  合法袋尾=%s"
        % (info['bag_id'], info['off'], info['end'], hx(info['tail_orig']), hx(info['tail_legal'])))
    log("B 合法改写 sha256[:12]=%s  与基线差 %d 字节"
        % (hashlib.sha256(legal).hexdigest()[:12],
           sum(1 for i in range(len(base)) if base[i] != legal[i])))
    log("C 非法改写 sha256[:12]=%s  与基线差 %d 字节（只改数据、袋尾不动）"
        % (hashlib.sha256(illegal).hexdigest()[:12],
           sum(1 for i in range(len(base)) if base[i] != illegal[i])))
    log("★ B 与 C 只差 2 字节（袋校验尾）⇒ 结果码若不同，即单变量证明 `0x02` = 校验和错误")

    cases = []
    if a.bag is not None:
        fill = int(a.fill, 16) if a.fill.lower().startswith("0x") else int(a.fill)
        bagv, binfo = mk_bag_variant(base, a.bag, fill)
        log("★ G2 逐袋模式：bag_id=%d 数据区整体填 0x%02X ⇒ 与基线差 %d 字节（袋尾/头校验已重算）"
            % (binfo["bag_id"], fill, sum(1 for i in range(len(base)) if base[i] != bagv[i])))
        cases.append(("D G2 逐袋改写 bag=%d fill=0x%02X" % (a.bag, fill), bagv, "★ 0x7F (TS_CMD_CFG_OK)"))
    for c in (a.cases or ("A,B,C" if a.bag is None else "")).split(','):
        c = c.strip().upper()
        if not c:
            continue
        if c == 'A':
            cases.append(('A 原样（与 flash 相同）', base, '7E 00 07 (DATA_EQU)'))
        elif c == 'B':
            cases.append(('B 合法改写（袋尾已重算）', legal, '★ 0x7F (TS_CMD_CFG_OK)'))
        elif c == 'C':
            cases.append(('C 非法改写（袋尾未动）', illegal, '7E 00 02 (CHKSUM_ERR)'))

    if not a.commit:
        log("\n[DRY] 未打开设备。将依次执行：")
        for lab, _, exp in cases:
            log("   · %-28s 期望 %s" % (lab, exp))
        log("  只写 0x96F8（会话 RAM），不碰 flash；加 --commit 执行。")
        return

    g = gxmem.Gx()
    log("\nopen(Col04) = %s" % g.open())
    log("【写前】0x4000=%s  0x4160=%s  0x96F8[0:16]=%s"
        % (hx(read_all(g, 0x4000, 4)), hx(read_all(g, CMD_ADDR, 1)),
           hx(read_all(g, CFG_ADDR, 16))))
    results = []
    try:
        for lab, cfg, exp in cases:
            r = official_cycle(g, cfg, lab, exp)
            results.append((lab, r, exp))
    finally:
        try:
            g.write(CMD_ADDR, mk_cmd(C_END_SEND_CFG_YS))
            time.sleep(0.05)
            if not a.no_reset:
                g._send([0x0E, 0x13, 0x00, 0x00, 0x01, 0x01])   # 复位 IC（从 flash 重载）
                log("\n[restore] 已发 0E 13 复位 IC")
                time.sleep(0.60)
            d = read_all(g, CFG_ADDR, 32)
            log("[restore] 0x96F8[0:32] = %s" % hx(d))
            log("[restore] 与基线一致 = %s"
                % ("✔" if d == base[:32] else "✗（如不一致请再跑一次或拔插）"))
            log("[restore] 0x4000=%s  0x4160=%s"
                % (hx(read_all(g, 0x4000, 4)), hx(read_all(g, CMD_ADDR, 1))))
        except Exception as e:
            log("[restore] 例外 %r" % e)
        g.close()

    log("\n" + "=" * 84)
    log("### 汇总")
    log("=" * 84)
    for lab, r, exp in results:
        log("  %-28s 实测 %-14s 期望 %s" % (lab, hx(r) if r else '<FAIL>', exp))


if __name__ == "__main__":
    main()
