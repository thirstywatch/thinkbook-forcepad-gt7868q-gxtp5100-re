#!/usr/bin/env python3
# update-idx-26.py —— 给总表里 追加二十六 那一行补上 §十一 的终局定案
import os

p = r"<WORKSPACE>"
txt = open(p, encoding="utf-8").read()

anchor = "ACPI 表存储 GUID `7E374E25-8E01-4FEE-87F2-390C23C606CD` | \u2705 有效（权威） |"
if anchor not in txt:
    print("未找到锚点，可能已更新过")
    raise SystemExit

addition = (
    "\uff08\u2605 2026-09-29 \u518d\u8865\uff1a**\u00a7\u5341\u4e00 \u7ec8\u5c40\u5b9a\u6848** \u2014\u2014 "
    "**Code 10 \u7684\u7cbe\u786e\u539f\u56e0\u5728\u672c\u673a BIOS \u7684\u767d\u540d\u5355\u91cc**\uff1a"
    "`GoodixTpDxe` \u7684\u5b9e\u9645\u751f\u6548\u68c0\u67e5\u4e3a "
    "`cmp eax,0x27c6`\uff08VID\uff09+ `cmp eax,0x1e8` / `cmp eax,0x1e9`\uff08PID\uff09"
    "\u21d2 **\u767d\u540d\u5355 = VID `0x27C6` \u4e14 PID \u2208 {`0x01E8`,`0x01E9`}**\uff1b"
    "\u800c X9-15 \u6a21\u7ec4\u62a5 **`0x01EA`** \u21d2 \u4e0d\u5728\u767d\u540d\u5355 \u21d2 \u88ab\u62d2 \u21d2 **\u4ee3\u7801 10**"
    "\uff08\u4e0e B\u7ad9\u8bc4\u8bba\u533a\u5b9e\u6d4b\u5b8c\u5168\u543b\u5408\uff09\uff1b"
    "\u2605 \u540c\u65f6\u66f4\u6b63\u672c\u8f6e\u81ea\u8eab\u4e00\u5904**\u8bef\u62a5**\uff1a"
    "`I2cTouchPanelDxe.bin` \u91cc\u7684 `01E9`/`01EA` \u5168\u662f\u6307\u4ee4\u5b57\u8282\uff08`E9`=jmp\u3001`0F 84 xx`=jz\uff09"
    "\u5047\u9633\u6027\uff0c\u8be5\u6a21\u5757**\u4e0d\u542b\u4efb\u4f55 VID/PID \u5e38\u91cf**\uff1b"
    "\u65b9\u6cd5\u5b66\u65b0\u589e\u7b2c 6/7 \u6761\uff08x86 \u4e8c\u5b57\u8282\u6a21\u5f0f\u5339\u914d\u4f1a\u5927\u91cf\u5047\u9633\u6027\uff1b"
    "\u770b\u5230\u5e38\u91cf\u4e0d\u7b49\u4e8e\u5b83\u5728\u6bd4\u8f83\uff09\uff09 | \u2705 \u6709\u6548\uff08\u6743\u5a01\uff09 |"
)

txt = txt.replace(anchor, anchor + "\n" + addition, 1)
txt = txt.rstrip("\n") + "\n"
open(p, "w", encoding="utf-8", newline="").write(txt)
print("已更新 追加二十六 索引行")
print("文件大小:", os.path.getsize(p), "B")
print("行数:", txt.count("\n"))
