#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_bat.py -- 生成分批次的全地址扫描 .bat（供用户双击；ASCII only）

背景：RWE 的 /Command 内联脚本一旦太长（>~6 KB）就会被 WorkBuddy 的
PowerShell 工具安全策略拦下，所以拆成多个批次写进一个 .bat，
用户双击（以管理员）一次即可跑完全表。
"""
import os

OUT = r"<WORKSPACE>"
PORT = r"<LAB>\touchpad-lab\rwe\Win64\Portable"
RWE = os.path.join(PORT, "Rw.exe")

HDR = [
    "LocalA=Rpci32(0,0x15,0,0x10)",
    "LocalB=Rpci32(0,0x15,0,0x14)",
    "LocalA=And(LocalA,0xFFFFFFF0)",
    "LocalB=Shl(LocalB,32)",
    "LocalA=Or(LocalA,LocalB)",
    "Cout BAR=%Lah",
    "LocalC=Add(LocalA,0x6C)",
    "LocalD=Add(LocalA,0x70)",
    "LocalE=Add(LocalA,0x10)",
    "LocalF=Add(LocalA,0x04)",
    "Local1=Add(LocalA,0x80)",
    "Local2=Add(LocalA,0x54)",
    "w32(LocalC,1)",
    "Delay 30",
]

BATCH = 20
FIRST, LAST = 0x08, 0x77

batches = []
a = FIRST
while a <= LAST:
    b = min(a + BATCH - 1, LAST)
    batches.append((a, b))
    a = b + 1

lines = [
    "@echo off",
    "REM Full I2C0 address sweep in batches. ASCII only.",
    "REM Right-click this file -> Run as administrator.",
    "setlocal",
    'cd /d "%s"' % PORT,
    "",
]

n = 1
for (a, b) in batches:
    p = list(HDR)
    for x in range(a, b + 1):
        h = "%02X" % x
        p += [
            "w32(LocalC,1)",
            "Delay 3",
            "r32(Local2)",
            "w32(LocalF,0x" + h + ")",
            "w32(LocalE,0x300)",
            "Delay 4",
            "Local3=r32(Local1)",
            "Cout S" + h + "=%%L3h",
        ]
    p.append("Cout B%d_DONE" % n)
    p.append("RwExit")
    body = ";".join(p)
    arg = '/Min /Nologo /LogFile=L%d.txt /Command="%s"' % (n, body)
    lines.append('echo batch %d : %02X-%02X : %d chars' % (n, a, b, len(arg)))
    lines.append('"%s" %s' % (RWE, arg))
    lines.append("")
    n += 1

lines.append("echo ALL DONE")
lines.append("pause")

with open(OUT, "w", encoding="ascii", newline="\r\n") as f:
    f.write("\n".join(lines) + "\n")

d = open(OUT, "rb").read()
maxline = max(len(l) for l in open(OUT, encoding="ascii"))
print("batches    :", len(batches), [(("%02X-%02X") % (a, b)) for a, b in batches])
print("bat bytes  :", len(d))
print("non-ascii  :", sum(1 for c in d if c > 0x7F))
print("max cmdline:", maxline, "(cmd.exe limit 8191)")
print("out        :", OUT)
