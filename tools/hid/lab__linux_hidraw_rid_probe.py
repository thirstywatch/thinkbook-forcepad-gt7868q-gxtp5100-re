#!/usr/bin/env python3
"""N1 执行器 —— Linux `hidraw` 未声明 RID / OUTPUT 报告探针

背景（2026-10-14 §19.63）：
  · Windows 侧：Col02 `OutputReportByteLength = 0` ⇒ `HIDCLASS` 按描述符拦下，OUTPUT 报**发不出去**（实测 err=87）。
  · Linux 侧：`hidraw` 的 `write()` → `hid_hw_raw_request(..., HID_OUTPUT_REPORT, HID_REQ_SET_REPORT)`
    → `i2c_hid_raw_request()` → `i2c_hid_set_report()`，**不查描述符里有没有这个 RID**。
  ⇒ 所以「往这块板子发【描述符里未声明】的 OUTPUT 报告」这条注入面，**只能在 Linux 上试**。
  ⇒ 这就是本项目暴力路线里**唯一没试过**的一块（原 §20.11 第 34 项）。

安全设计（纪律 154 落地）：
  · **默认只读**：只做「已知良好的只读帧 + 存活位核对」，不写任何未声明 RID。
  · 写模式需显式 `--sweep`；且 **载荷恒为全 0x00**（不携带命令语义）。
  · **每发一条立刻复查存活位 `0x4000`**；一旦不是 `A7 E0 E5 B1` 或读失败 ⇒ **立即停**并提示急救。
  · **命令空间语义同构检查**：若待发 RID 命中已知危险区（`0x10`/`0x11`/`0x12`/`0x13`）⇒ **默认跳过**。
  · 绝不主动发 `0E 12`（写 flash）/`00 10`/`00 11`。

用法（需 root）：
    sudo python3 lab__linux_hidraw_rid_probe.py               # 只读：定位节点 + 存活位核对
    sudo python3 lab__linux_hidraw_rid_probe.py --sweep       # 追加 RID 扫描（有序、可急停）
    sudo python3 lab__linux_hidraw_rid_probe.py --sweep --include-risky   # 连危险 RID 也发（不推荐）
"""
import os, sys, glob, time, json, fcntl, struct, argparse

# Windows 控制台默认 GBK：打印 emoji / 生僻字会让 print 抛 UnicodeEncodeError（2026-10-14 实测）
try:  # 只把不可编码字符降级为 '?'，不改变可读内容
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

HIDIOCGRDESCSIZE = 0x80044801
HIDIOCGRDESC     = 0x90044802

VENDOR_RID = 0x0E          # Col04 的命令通道 RID
KNOWN_GOOD = bytes([0x0E, 0x20, 0x00, 0x00, 0x05, 0x01, 0x40, 0x00, 0x00, 0x08])  # 读 0x4000 +8B
ALIVE_EXPECT = bytes([0xA7, 0xE0, 0xE5, 0xB1])   # 0x4000 存活位（健康态）
DANGEROUS_RIDS = {0x10, 0x11, 0x12, 0x13}         # 已知语义：patch / update / 写 flash / reset
REPORT_LEN = 65

LOG = []


def log(m):
    print(m, flush=True)
    LOG.append(m)


def find_nodes():
    out = []
    for p in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        node = "/dev/" + os.path.basename(p)
        uevent = os.path.join(p, "device", "uevent")
        name = ""
        try:
            for line in open(uevent, errors="ignore"):
                if line.startswith("HID_NAME="):
                    name = line.strip().split("=", 1)[1]
        except Exception:
            pass
        if "GXTP5100" in name.upper() or "GXTP5100" in p.upper():
            out.append((node, name, uevent))
    return out


def read_rdesc(node):
    try:
        fd = os.open(node, os.O_RDONLY)
    except Exception as e:
        return None, "open失败:%s" % e
    try:
        sz = fcntl.ioctl(fd, HIDIOCGRDESCSIZE, b"\x00\x00\x00\x00")
        size = struct.unpack("<I", sz)[0]
        buf = bytearray(4 + size)
        struct.pack_into("<I", buf, 0, size)
        fcntl.ioctl(fd, HIDIOCGRDESC, buf)
        return bytes(buf[4:4 + size]), None
    except Exception as e:
        return None, str(e)
    finally:
        os.close(fd)


def has_usage(desc, page, usage):
    """粗略在描述符里找 usage page + usage 对（够用即可）"""
    if desc is None:
        return None
    return bytes([usage]) in desc and bytes([page]) in desc


def open_rw(node):
    try:
        return os.open(node, os.O_RDWR | os.O_NONBLOCK)
    except Exception:
        return None


def send(fd, payload):
    """payload[0] = RID，其余为数据；补齐到 65 字节"""
    b = bytes(payload) + bytes(REPORT_LEN - len(payload))
    try:
        n = os.write(fd, b)
        return True, n, 0
    except OSError as e:
        return False, 0, e.errno


def read_resp(fd, timeout=1.5):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            d = os.read(fd, REPORT_LEN)
            if d:
                return bytes(d)
        except BlockingIOError:
            time.sleep(0.05)
        except OSError:
            return None
    return None


def read_alive(fd):
    """发已知良好的只读帧，取回 0x4000 的 8 字节"""
    ok, n, err = send(fd, KNOWN_GOOD)
    if not ok:
        return None, "写失败 errno=%s" % err
    r = read_resp(fd)
    if r is None:
        return None, "无响应"
    return r, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true", help="启用 RID 扫描（写 OUTPUT 报告）")
    ap.add_argument("--include-risky", action="store_true", help="连 0x10-0x13 也发（不推荐）")
    ap.add_argument("--start", type=lambda x: int(x, 0), default=0x00)
    ap.add_argument("--end", type=lambda x: int(x, 0), default=0xFF)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    outdir = os.path.join(here, "linux-rid-probe")
    os.makedirs(outdir, exist_ok=True)

    if os.geteuid() != 0:
        log("⚠ 建议以 root 运行（读写 hidraw 需要）。")

    nodes = find_nodes()
    if not nodes:
        log("未找到 GXTP5100 的 hidraw 节点。可用 `ls /sys/class/hidraw/*/device/uevent` 手工核对。")
        return

    log("=" * 78)
    log("Linux hidraw RID 探针 —— %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("=" * 78)

    # ---- 定位：哪个节点是厂商集合（能应答只读帧的那个）----
    vendor_fd, vendor_node, findings = None, None, {}
    for node, name, ue in nodes:
        desc, err = read_rdesc(node)
        log("\n节点 %s   HID_NAME=%s" % (node, name))
        log("  描述符: %s" % (("%d 字节" % len(desc)) if desc else ("读取失败: %s" % err)))
        findings[node] = {"name": name, "rdesc_len": len(desc) if desc else None}
        fd = open_rw(node)
        if fd is None:
            log("  打开 RW 失败，跳过")
            continue
        r, e = read_alive(fd)
        if r is not None:
            log("  只读帧应答: %s" % " ".join("%02X" % c for c in r[:12]))
            if r[1:5] == ALIVE_EXPECT or ALIVE_EXPECT in r:
                log("  ★ 判定：这就是**厂商命令集合**（存活位 %s 命中）" %
                    " ".join("%02X" % c for c in ALIVE_EXPECT))
                vendor_fd, vendor_node = fd, node
                findings[node]["is_vendor"] = True
                break
            else:
                log("  应答内容与预期不符（不是厂商集合，或 IC 当前非健康态）")
        else:
            log("  无应答（%s）" % e)
        os.close(fd)

    if vendor_fd is None:
        log("\n❌ 没有定位到厂商命令集合。安全检查未通过 ⇒ **不进入扫描**。")
        json.dump(findings, open(os.path.join(outdir, "nodes.json"), "w"), indent=1)
        return

    # ---- 基线存活位复核 ----
    log("\n" + "-" * 78)
    log("扫描前基线复核")
    r, e = read_alive(vendor_fd)
    if r is None or ALIVE_EXPECT not in r:
        log("  基线不符（%s）⇒ 不进入扫描。" % e)
        os.close(vendor_fd); return
    log("  基线 OK：%s" % " ".join("%02X" % c for c in r[:12]))

    if not args.sweep:
        log("\n（只读模式结束。要发未声明 RID 的 OUTPUT 报告，请加 --sweep。）")
        log("  扫描时：一次一个 RID、载荷全 0x00、每发一条立刻复查存活位、异常即停。")
        os.close(vendor_fd)
        open(os.path.join(outdir, "probe_log.txt"), "w").write("\n".join(LOG))
        return

    # ---- 扫描 ----
    log("\n" + "-" * 78)
    log("★ RID 扫描（OUTPUT 报告，载荷全 0x00）—— 每步复查存活位")
    order = ([0x0E] + [0x02, 0x06, 0x09, 0x0B, 0x0C, 0x0D] +
             [r for r in range(0x00, 0x10)] + [r for r in range(0x10, args.end + 1)])
    seen, results = set(), {}
    for rid in order:
        if rid in seen or rid < args.start:
            continue
        seen.add(rid)
        if rid in DANGEROUS_RIDS and not args.include_risky:
            log("  RID=0x%02X  跳过（纪律 154：命中已知危险语义 patch/update/flash/reset）" % rid)
            results["0x%02X" % rid] = {"skipped": "dangerous"}
            continue
        ok, n, err = send(vendor_fd, bytes([rid]))
        resp = read_resp(vendor_fd)
        alive, ae = read_alive(vendor_fd)
        live_ok = (alive is not None and ALIVE_EXPECT in alive)
        results["0x%02X" % rid] = {
            "write_ok": ok, "errno": err,
            "resp": (" ".join("%02X" % c for c in resp[:12]) if resp else None),
            "alive_ok": live_ok,
        }
        log("  RID=0x%02X  write=%-5s errno=%-3s  应答=%-30s 存活=%s" % (
            rid, ok, err, ((" ".join("%02X" % c for c in resp[:8])) if resp else "-"),
            "OK" if live_ok else "★异常"))
        if not live_ok:
            log("\n🛑 **存活位异常 ⇒ 立即停止扫描。** 请跑 tools/hid/lab__touchpad_rescue.py（或长按重启）。")
            break
        time.sleep(0.15)

    os.close(vendor_fd)
    json.dump(results, open(os.path.join(outdir, "sweep_result.json"), "w"), indent=1)
    open(os.path.join(outdir, "probe_log.txt"), "w").write("\n".join(LOG))
    log("\n完成。结果目录: %s" % outdir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n中断。")
