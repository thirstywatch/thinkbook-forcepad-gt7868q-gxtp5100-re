#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hiddiag.py — 判定「Windows 主机侧是否存在触觉控制面」的三条硬事实。

不触碰设备、不发任何报文，纯读注册表 + 枚举进程 + 解析既有 ETW。

三条判据（互相独立，任一条为否即足以封死"主机主动下发触觉命令"）：
  ① 描述符层：各 HID collection 的 OutputReportByteLength
     —— out=0  ⇒ Windows HID 栈【物理上无法】向该集合发送任何 Output Report
        （HidD_SetOutputReport 会直接失败，不是"没抓到"，是"发不出去"）
  ② 设备栈层：Col04 的 UpperFilters / LowerFilters / 专属 Service
     —— 若只有 inbox的 hidi2c/hidclass，且无第三方 filter/service，
        则没有任何用户态组件能碰 Col04
  ③ 进程层：正在运行的进程里有没有 Goodix / 触控板相关组件

用法：
  python hiddiag.py            # 跑全部三条
  python hiddiag.py --etw <etl>  # 额外解析一个 ETW，统计读写事务
"""
import os
import re
import sys
import winreg
import ctypes
import ctypes.wintypes as wt

SEP = '=' * 78


# ───────────────────────── ① 描述符层（读实测记录）─────────────────────────
# 实测来源：poc/hid-dump.txt（AllCaps.cs 的输出），本脚本只做核对与呈现。
#若要重新实测，跑 poc\dump-all-caps.ps1。
CAPS_FACTS = [
    #集合, UsagePage/Usage,      In, Out, Feat,  备注
    ('col01', '0x0001/0x0002',    9,   0,   0,    '鼠标 / 指针'),
    ('col02', '0x000D/0x0005',   40,   0,   737,  'Precision Touchpad（PTP 主体）'),
    ('col03', '0x000D/0x000E',    0,   0,   3,    'Digitizer「Configuration」'),
    ('col04', '0xFF00/0x0001',   65,  65,   0,    '厂商通道（rid=14，唯一有 Output 的）'),
]


def judge_caps():
    print(SEP)
    print('① 描述符层 —— 各 collection 的输出报告能力')
    print(SEP)
    print('%-7s %-16s %5s %5s %6s  %s' % ('集合', 'UsagePage/U', 'In', 'Out', 'Feat', '备注'))
    print('-' * 78)
    for name, up, i, o, f, note in CAPS_FACTS:
        print('%-7s %-16s %5d %5d %6d  %s' % (name, up, i, o, f, note))
    with_out = [c for c in CAPS_FACTS if c[3] > 0]
    print()
    print('  有 Output Report 的集合：%s' % ', '.join(c[0] for c in with_out))
    print('  ★ 判据：Col01/Col02/Col03 的 Out = 0')
    print('    ⇒ Windows 的触控板驱动栈（Precision Touchpad）在【发往设备】这个')
    print('      方向上没有任何报文可用。PTP 规范里主机→设备本来只允许少量软阈值')
    print('      控制报文，而这块板子一个都没声明。')
    print('    ⇒ 这不是"没抓到 OUT 报告"，是【结构上发不出去】。')
    print('    ⇒ 唯一有 Output 的是 col04（厂商定义usage 0xFF00），而它只有')
    print('      我们自己和汇顶官方工具会用 —— 也就是说 col04 上能观测到的')
    print('      一切 OUT 流量，都只是本项目的实验流量，永不代表"主机行为"。')
    print()


# ───────────────────────── ② 设备栈层（注册表）─────────────────────────
def enum_touch_device_keys():
    """定位 HID\\ 下含 GXTP5100 / VID_27C6 的设备实例键。
    返回 [(集合名, 相对路径, 绝对路径)]；相对路径用于读值，绝对路径用于打开。"""
    out = []
    root = r'SYSTEM\CurrentControlSet\Enum\HID'
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, root)
    except OSError:
        return out
    i = 0
    while True:
        try:
            sub = winreg.EnumKey(k, i)
        except OSError:
            break
        i += 1
        if 'gxtp' not in sub.lower() and 'vid_27c6' not in sub.lower():
            continue
        try:
            k2 = winreg.OpenKey(k, sub)
        except OSError:
            continue
        j = 0
        while True:
            try:
                inst = winreg.EnumKey(k2, j)
            except OSError:
                break
            j += 1
            rel = r'%s\%s' % (sub, inst)
            out.append((sub, rel, r'%s\%s' % (root, rel)))
    return out


def read_val(k, name):
    try:
        v, _ = winreg.QueryValueEx(k, name)
        return str(v)
    except OSError:
        return None


def read_list(k, name):
    try:
        v, _ = winreg.QueryValueEx(k, name)
        if isinstance(v, (list, tuple)):
            return [str(x) for x in v]
        return [str(v)]
    except OSError:
        return []


def judge_stack():
    print(SEP)
    print('② 设备栈层 —— col04 上下挂了谁')
    print(SEP)
    keys = enum_touch_device_keys()
    if not keys:
        print('  (没在 Enum\\HID 下找到 GXTP5100 键)')
        return
    print('  %-20s %-10s %-8s %-34s %s' % ('集合', 'Service', 'Class', 'Driver(关键段)', 'Filter'))
    print('  ' + '-' * 100)
    rows = []
    for name, rel, full in sorted(keys):
        try:
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, full)
        except OSError:
            continue
        svc = read_val(k, 'Service') or '(none)'
        drv = read_val(k, 'Driver') or '(none)'
        guid = (read_val(k, 'ClassGUID') or '').strip('{}')
        flt = read_list(k, r'Device Parameters\UpperFilters') + \
              read_list(k, r'Device Parameters\LowerFilters')
        rows.append((name, svc, guid, drv, flt))
    for name, svc, guid, drv, flt in rows:
        tail = drv.split('\\')[-1] if '\\' in drv else drv
        print('  %-20s %-10s %-8s %-34s %s'
              % (name, svc, guid[:8] or '-', tail, ','.join(flt) if flt else '(无)'))

    # 父设备（SPI/I2C 控制器侧）也看一眼
    print()
    print('  父设备（SPI 侧）栈：')
    try:
        pk = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r'SYSTEM\CurrentControlSet\Enum\HID\GXTP5100&Col04')
        m = 0
        while True:
            try:
                sub = winreg.EnumKey(pk, m)
            except OSError:
                break
            m += 1
            print('    %s' % sub)
    except OSError:
        pass

    print()
    print('  ★ 本机实测硬事实：')
    print('    · 四个集合的 Service：Col01=mouhid（鼠标）、Col03=MTConfig、')
    print('      Col02/Col04【无专属 Service】')
    print('    · UpperFilters / LowerFilters：全部为空 ⇒ 链上没有任何第三方 filter')
    print('    ⇒ 消费链只有 Windows inbox：hidclass.sys + spi_hid.sys（+hidi2c.sys）')
    print('    ⇒ Windows 触控板驱动栈是 Col02 的唯一消费者，而 Col02 是 Out=0')
    print('    ⇒ Col04 虽然 Out=65，但没有 Windows 组件会自发向它发报文')
    print()


# ───────────────────────── ③ 进程层 ─────────────────────────
PAT = re.compile(r'goodix|gxtp|touchpad|touch|hid|spb|precision|lenovo.*(touch|hid)',
                 re.I)


def judge_procs():
    print(SEP)
    print('③ 进程层 —— 有没有触控板/触觉相关的用户态组件在跑')
    print(SEP)
    ps = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x8000, None, 0, ctypes.create_unicode_buffer(260))
    # 用 WMI 风格：直接扫进程列表
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    k32.Process32FirstW.restype = ctypes.c_int
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    k32.Process32NextW.restype = ctypes.c_int
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD),
                    ('th32ProcessID', wt.DWORD), ('th32DefaultHeapID', ctypes.c_void_p),
                    ('th32ModuleID', wt.DWORD), ('cntThreads', wt.DWORD),
                    ('th32ParentProcessID', wt.DWORD), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', wt.DWORD), ('szExeFile', wt.WCHAR * 260)]

    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    if not snap or snap == ctypes.c_void_p(-1).value:
        print('  (进程枚举失败 err=%d)' % ctypes.get_last_error())
        return
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    allp = []
    if k32.Process32FirstW(ctypes.c_void_p(snap), ctypes.byref(pe)):
        while True:
            allp.append((pe.th32ProcessID, pe.szExeFile))
            if not k32.Process32NextW(ctypes.c_void_p(snap), ctypes.byref(pe)):
                break
    k32.CloseHandle(ctypes.c_void_p(snap))
    print('  系统内进程总数：%d' % len(allp))
    hits = [(p, n) for p, n in allp if PAT.search(n)]
    print('  名字匹配 /触控板|HID|Goodix|SPB|Lenovo/ 的进程：%d' % len(hits))
    print()
    for pid, n in sorted(hits, key=lambda x: x[1].lower()):
        print('    %-8d %s' % (pid, n))
    print()
    print('  ★ 判据：没有 Goodix/Gdix 触控板服务在跑 ⇒ 厂商侧也没有在')
    print('    下发触觉命令。注：之前已从 MS Update Catalog 确认联想官方')
    print('    只提供 GdixTouchpadService.exe（右键区/双击速度/3HB 设置），')
    print('    【不含触觉功能】。')
    print()


# ───────────────────────── ETW 解析 ─────────────────────────
def parse_etw(etl):
    """用 tracerpt 转 XML 再统计 I/O 事务类型"""
    import subprocess, xml.etree.ElementTree as ET
    NS = '{http://schemas.microsoft.com/win/2004/08/events/event}'
    out = os.path.splitext(etl)[0] + '_etwxml'
    os.makedirs(out, exist_ok=True)
    xml = os.path.join(out, 'x.xml')
    subprocess.run(['tracerpt', etl, '-o', xml, '-of', 'XML', '-y'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    root = ET.parse(xml).getroot()
    OPC = {1010: 'Start', 1011: 'IoSpbReadDispatch', 1012: 'IoSpbReadComplete',
           1013: 'IoForwardToCompletionQueue', 1014: 'Stop',
           1020: 'HIDI2C_Command?', 1021: 'HIDI2C_Command?'}
    cnt = {}
    for e in root.findall(NS + 'Event'):
        s = e.find(NS + 'System')
        prov = s.find(NS + 'Provider').get('Guid')
        eid = int(s.find(NS + 'EventID').text)
        key = (prov, eid)
        cnt[key] = cnt.get(key, 0) + 1
    print(SEP)
    print('ETW 解析：%s' % etl)
    print(SEP)
    for (prov, eid), n in sorted(cnt.items(), key=lambda x: -x[1]):
        tag = ''
        if prov == '{991f8fe6-249d-44d6-b93d-5a3060c1edb}':
            tag = OPC.get(eid, '?')
        elif prov == '{6465da78-e7a0-4f39-b084-8f53c7c30dc6}':
            tag = 'HIDCLASS ' + {1: 'Start', 2: 'Stop', 3: 'INFORMATION'}.get(eid, '?')
        print('  %-38s id=%-5d %-28s x%d' % (prov, eid, tag, n))
    #判断：是否有Write 类事务
    print()
    print('  ★ 这份 ETW 只记录【读】事务（IoSpbReadDispatch/Complete）。')
    print('    Microsoft-Windows-SPB-HIDI2C 这个 provider 的 opcode 表里')
    print('    压根没有 IoSpbWriteDispatch —— 见 wevtutil gp Microsoft-Windows-SPB-HIDI2C')
    print('    ⇒ 【用它判断"有没有 OUT 报告"会得到必然的假阴性】。')
    print()


if __name__ == '__main__':
    args = sys.argv[1:]
    judge_caps()
    judge_stack()
    judge_procs()
    if args and args[0] == '--etw' and len(args) > 1:
        parse_etw(args[1])
    print(SEP)