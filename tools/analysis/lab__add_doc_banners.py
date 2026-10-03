# -*- coding: utf-8 -*-
# add_doc_banners.py — 给工区根目录文档批量插入统一的状态标注（只插在标题下，不改正文）
# 注意：banner 文本里的内层引号一律用「」，避免和 Python 字符串定界符冲突
import os

ROOT = r"<LAB>\touchpad-lab"

FROZEN = """\
> **【已冻结 · 2026-09-14 23:3x｜历史记录，不再更新】**
> **当前权威：`PREFLIGHT-STATE.md`**（把「实测 / 反推 / 未定」彻底分开）。
> 保留原因：本文的**原始实测数据与推导过程**仍有参考价值。
"""

BANNERS = {}

BANNERS["MASTER-CONSOLIDATION.md"] = FROZEN + \
    "> ⚠️ §6「逻辑漏洞审计」与 §7「机会空间」仍是好材料；但结论以 `PREFLIGHT-STATE.md` 为准。\n"

BANNERS["VIB-REOPENED.md"] = FROZEN + \
    "> ⚠️ **核心主张只对了一半**：它提出「扩展空间（`0x80`/`0xA0`/`0xA1`）从未被探测过」——\n" \
    "> **边界现已完整解出**（类 3 个 + `0xA0`×16 + `0xA1`×22，见 `COL04-BOUNDARY.md`）；\n" \
    "> 但**「主机能否到达 TF100A」至今未证实**（`PREFLIGHT-STATE.md` §7 的 H1，唯一的门）。\n" \
    "> ⚠️ 另：§6「找第二份容器」的理由「缺 5,141 字节」**已推翻**（准确量级 = 下界 **837 字节**）。\n"

BANNERS["VIBRATION-CONCLUSION.md"] = FROZEN

BANNERS["VIBRATION-FORENSICS-2.md"] = FROZEN + \
    "> ⚠️ §5.9「两个声明长度与在场字节精确相等」仍然有效且重要；\n" \
    "> 但文中涉及 **5,141 字节** 的段落**已推翻**（下界 **837 字节**）。\n"

BANNERS["SESSION-2026-09-14-PM.md"] = \
    "> **【已冻结 · 当日会话记录】**\n" \
    "> **结论已被取代**：状态以 `PREFLIGHT-STATE.md` 为准，Col04 相关以 `COL04-BOUNDARY.md` 为准。\n" \
    "> 尤其 §5「路径重排」与 §12「需要修正的既有文档」**已过时**（本轮已执行完）。\n" \
    "> 保留原因：**当天为什么那么判断**的推理轨迹。\n"

BANNERS["DESIGN.md"] = \
    "> **【参考 · 设计方案，未随本轮更新】** 项目当前权威状态：`PREFLIGHT-STATE.md`。\n" \
    "> 本文是 PC 侧手势方案的**设计稿**（对应 `PREFLIGHT-STATE.md` §5 的「后置工作」），仍可作实现参考。\n"

BANNERS["BIOS-TEST-RESULT.md"] = \
    "> **【参考 · 实测记录】** 项目当前权威状态：`PREFLIGHT-STATE.md`。\n" \
    "> 本记录与 `PREFLIGHT-STATE.md` §7 的 H1（主机能否到达 TF100A）**无直接关系**，两者不冲突。\n"

BANNERS["INCIDENT-2026-09-14-input-freeze.md"] = \
    "> **【参考 · 事故记录】** 红线汇总见 `PREFLIGHT-STATE.md` §8（**一条不动**）。\n"

BANNERS["OUTREACH.md"] = \
    "> **【现役 · 2026-09-14 23:3x 已修订】** 项目当前权威状态：`PREFLIGHT-STATE.md`。\n" \
    "> ⚠️ 已修正：原文「5,141 字节」**已推翻**（下界 **837 字节**）；\n" \
    "> **新增 §9 = 向原厂申请 EVK 的中英文话术**（建议优先做，比要固件现实得多）。\n"


def has_bom(b):
    return len(b) >= 3 and b[0] == 0xEF and b[1] == 0xBB and b[2] == 0xBF


report = []
for fn, banner in BANNERS.items():
    p = os.path.join(ROOT, fn)
    if not os.path.exists(p):
        report.append("!! 不存在: " + fn)
        continue
    raw = open(p, "rb").read()
    bom = has_bom(raw)
    s = raw.decode("utf-8-sig")
    lines = s.split("\n")
    if not lines or not lines[0].lstrip().startswith("# "):
        report.append("!! 首行不是标题，跳过: " + fn)
        continue
    head = s[:1500]
    if ("【已冻结" in head) or ("【现役" in head) or ("【参考" in head):
        report.append("-- 已有标注，跳过: " + fn)
        continue
    rest = lines[1:]
    while rest and rest[0].strip() == "":
        rest.pop(0)
    out = [lines[0], "", banner.rstrip("\n"), ""] + rest
    data = "\n".join(out).encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    open(p, "wb").write(data)
    report.append("OK 已插入标注: %-38s (BOM=%s, %d -> %d 字节)" % (fn, bom, len(raw), len(data)))

print("\n".join(report))
