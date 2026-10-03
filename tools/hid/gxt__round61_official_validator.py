#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROUND61 - 官方格式校验器
逐字节复刻 gdix_hid_firmware_update/firmware_image.cpp 的 GetDataFromFile(),
判定每个候选 BIN 能不能被官方工具接受; 若能, 再打印官方语义下的全部字段。
"""
import os
import struct

ROOT = r"<WORKSPACE>"


def u16be(d, o):
    return (d[o] << 8) | d[o + 1]


def u32be(d, o):
    return (d[o] << 24) | (d[o + 1] << 16) | (d[o + 2] << 8) | d[o + 3]


def official_load(path):
    """完全按 firmware_image.cpp 逻辑走一遍, 返回 (verdict, dict)"""
    with open(path, "rb") as f:
        d = f.read()
    total = len(d)
    out = {"file": os.path.basename(path), "total": total}

    if total < 8:
        return "TOO_SMALL", out

    fw_size = u32be(d, 0)
    out["m_firmwareSize"] = fw_size
    out["step1_len_check"] = f"fw_size+6 = {fw_size + 6} vs total = {total}"

    if fw_size + 6 != total:
        out["hasConfig"] = True
        out["msg"] = "长度不等 -> 官方认定『可能含 config bin』"
    else:
        out["hasConfig"] = False
        out["msg"] = "长度相等 -> 纯固件"

    # 固件体校验和
    if fw_size + 6 > total:
        return "FAIL_LEN_OVERFLOW", out
    cs = sum(d[6:6 + fw_size]) & 0xFFFFFFFF
    stored = u16be(d, 4)
    out["checksum_calc"] = hex(cs & 0xFFFF)
    out["checksum_stored"] = hex(stored)
    out["checksum_low16"] = hex(cs & 0xFFFF)
    if (cs & 0xFFFF) != stored:
        out["checksum_ok"] = False
        return "FAIL_FW_CHECKSUM", out
    out["checksum_ok"] = True

    # config pack
    if out["hasConfig"]:
        base = fw_size + 6
        if base + 8 > total:
            return "FAIL_CFG_TRUNC", out
        cfgpack_len = u16be(d, base)
        out["cfgpack_len"] = cfgpack_len
        out["cfg_actual_len"] = total - base
        if total - base != cfgpack_len + 6:
            out["cfg_len_ok"] = False
            return "FAIL_CFG_LEN", out
        out["cfg_len_ok"] = True
        ccs = sum(d[base + 6:total]) & 0xFFFFFFFF
        cstored = u16be(d, base + 4)
        out["cfg_checksum_calc"] = hex(ccs & 0xFFFF)
        out["cfg_checksum_stored"] = hex(cstored)
        if (ccs & 0xFFFF) != cstored:
            out["cfg_checksum_ok"] = False
            return "FAIL_CFG_CHECKSUM", out
        out["cfg_checksum_ok"] = True
        out["cfg_update_flag"] = hex(d[base + 2])
        out["cfg_sub_cfg_num"] = d[base + 3]
        # 子 cfg 表
        subs = []
        for i in range(d[base + 3]):
            o = base + 6 + i * 3
            subs.append((d[o], (d[o + 1] << 8) | d[o + 2]))
        out["cfg_sub_table"] = subs
        out["cfg_sub_data_off"] = base + 64 - 6

    # GT7868Q 专有字段
    pid = bytes(x for x in d[15:15 + 8] if x != 0).decode("latin1")
    out["pid@15"] = pid
    out["cid@23"] = hex(d[23])
    out["vid@24"] = [hex(d[24]), hex(d[25]), hex(d[26])]
    out["sub_fw_num@27"] = d[27]
    out["sub_fw_info@32"] = []
    info_pos = 32
    data_off = 256
    for i in range(d[27]):
        if info_pos + 8 > total:
            break
        t = d[info_pos]
        ln = u32be(d, info_pos + 1)
        addr = ((d[info_pos + 5] << 8) | d[info_pos + 6]) << 8
        out["sub_fw_info@32"].append((hex(t), ln, hex(addr)))
        info_pos += 8
        data_off += ln
    return "PASS_OFFICIAL", out


def main():
    cands = []
    for base, _, files in os.walk(ROOT):
        for fn in files:
            if fn.lower().endswith((".bin", ".fw", ".img")):
                cands.append(os.path.join(base, fn))

    print("=" * 78)
    print("ROUND61 官方格式校验 (复刻 firmware_image.cpp: GetDataFromFile)")
    print("=" * 78)
    print(f"候选文件 {len(cands)} 个\n")

    for p in sorted(cands):
        try:
            v, info = official_load(p)
        except Exception as e:
            print(f"[{os.path.basename(p)}] EXCEPTION {e}\n")
            continue
        print(f"--- {info['file']} ({info['total']} B) ---")
        for k in ("m_firmwareSize", "hasConfig", "checksum_calc", "checksum_stored",
                  "checksum_ok", "cfgpack_len", "cfg_len_ok", "cfg_checksum_ok",
                  "cfg_update_flag", "cfg_sub_cfg_num", "cfg_sub_table",
                  "pid@15", "cid@23", "vid@24", "sub_fw_num@27", "sub_fw_info@32"):
            if k in info:
                print(f"    {k:20s} = {info[k]}")
        print(f"    >>> 判定: {v}\n")


if __name__ == "__main__":
    main()
