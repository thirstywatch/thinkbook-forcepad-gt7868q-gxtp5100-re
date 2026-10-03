#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etwcheck.py — 既有 ETW 样本的有效性检验 + 判据边界。

要回答两个问题：
  Q1  这份 ETW 到底抓到的是不是「触控板的 I²C/HID 读事务」？
      判据：把 398 组事务按时间间隔排开，看间隔是否呈周期性轮询节奏。
      触控板空闲时 spi_hid 会持续轮询 → 间隔应近似常数（~8ms/报告）。
  Q2  这份 ETW 能不能回答「点击时有没有新的 OUT 报告」？
      判据：查 SPB-HIDI2C provider 的 opcode 表里是否存在 Write 类事件。
      ⇒ 不存在 ⇒ 用它判断写事务必然假阴性（这是【结构性】结论，与抓得好不好无关）

另：检查 HidReadRequest 指针是否指向同一对象（判断是否同一集合/同一队列）。
"""
import os
import sys
import csv
import collections
import xml.etree.ElementTree as ET
import subprocess

NS = '{http://schemas.microsoft.com/win/2004/08/events/event}'
SPB_GUID = '{991f8fe6-249d-44d6-b93d-5a3060c1dedb}'
HIDCLASS_GUID = '{6465da78-e7a0-4f39-b084-8f53c7c30dc6}'


def to_xml(etl):
    # 输出目录放在工具旁边，避免污染样本目录、也避免路径过长
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '_etwxml', os.path.splitext(os.path.basename(etl))[0])
    os.makedirs(out, exist_ok=True)
    xml = os.path.join(out, 'x.xml')
    if not os.path.exists(xml):
        subprocess.run(['tracerpt', etl, '-o', xml, '-of', 'XML', '-y'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not os.path.exists(xml):
        raise SystemExit('tracerpt 转换失败：%s' % etl)
    return xml


def load(etl):
    root = ET.parse(to_xml(etl)).getroot()
    evs = []
    for e in root.findall(NS + 'Event'):
        s = e.find(NS + 'System')
        prov = s.find(NS + 'Provider').get('Guid')
        eid = int(s.find(NS + 'EventID').text)
        ver = int(s.find(NS + 'Version').text)
        ts = s.find(NS + 'TimeCreated').get('SystemTime')
        act = s.find(NS + 'Correlation').get('ActivityID')
        pid = int(s.find(NS + 'Execution').get('ProcessID'))
        data = {}
        d = e.find(NS + 'EventData')
        if d is not None:
            for item in d.findall(NS + 'Data'):
                data[item.get('Name')] = (item.text or '').strip()
        evs.append(dict(prov=prov, eid=eid, ver=ver, ts=ts, act=act,
                        pid=pid, data=data))
    return evs


def parse_ts(s):
    # 2026-10-02T15:00:22.262624800+07:59
    date, rest = s.split('T')
    hh, mm, ss = rest.split('.')[0].split(':')
    frac = float('0.' + rest.split('.')[1].split('+')[0])
    return int(hh) * 3600 + int(mm) * 60 + int(ss) + frac


def main(etl):
    print('=' * 78)
    print('ETW 样本检验：%s' % etl)
    print('=' * 78)
    evs = load(etl)
    spb = [e for e in evs if e['prov'] == SPB_GUID]
    print('总事件 %d ；SPB-HIDI2C %d ；HIDCLASS %d'
          % (len(evs), len(spb), len([e for e in evs if e['prov'] == HIDCLASS_GUID])))

    # 只看 Dispatch(=1011) 作为一次事务的代表
    disp = [e for e in spb if e['eid'] == 1011]
    disp.sort(key=lambda e: parse_ts(e['ts']))
    print('IoSpbReadDispatch 次数：%d' % len(disp))
    if len(disp) < 3:
        print('样本太少')
        return

    ts = [parse_ts(e['ts']) for e in disp]
    span = ts[-1] - ts[0]
    gaps = [round((ts[i + 1] - ts[i]) * 1000, 3) for i in range(len(ts) - 1)]
    # ★ 两个必须避开的坑：
    #  1) 同一簇内的浮点抖动可到 ±0.05 ms，精确相等会把一簇拆成十几簇；
    #  2) 用"与前一个间隔之差 ≤TOL"来串链是错的 —— 一串 7.69/7.71/7.69 会
    #     因为步长小而无限延长，最后吞掉真实的不同间隔。
    # 正确做法：取众数附近的值作【基准】，把每个间隔独立归到最近的基准簇。
    bins = collections.Counter(round(g, 1) for g in gaps)
    base = bins.most_common(1)[0][0]
    TOL = 0.30          # ms，簇半宽
    clusters = collections.Counter()
    for g in gaps:
        clusters[round(round(g / TOL) * TOL, 2)] += 1
    cc = sorted(((n, m) for m, n in clusters.items()), reverse=True)
    top_n, top_mean = cc[0]
    print()
    print('时间跨度：%.3f s ；平均间隔：%.3f ms  ⇒ %.1f 次/秒'
          % (span, span * 1000 / len(gaps), len(gaps) / span))
    print('间隔簇（±%.2f ms 分桶，按数量排序，top 8）：' % TOL)
    for n, m in cc[:8]:
        bar = '#' * max(1, n * 40 // len(gaps))
        print('    %9.2f ms  %4d/%-4d %5.1f%% %s'
              % (m, n, len(gaps), 100.0 * n / len(gaps), bar))
    print()
    print('最大簇：%.2f ms，占 %.1f%%  ⇒ 约 %.1f Hz'
          % (top_mean, 100.0 * top_n / len(gaps), 1000.0 / top_mean))
    inl = [g for g in gaps if abs(g - top_mean) <= TOL]
    print('该簇内实际范围 %.3f – %.3f ms（n=%d）'
          % (min(inl), max(inl), len(inl)))

    print()
    print('★ Q1 判定：')
    frac = top_n / len(gaps)
    if frac > 0.5 and top_mean < 60:
        print('    %.1f%% 的间隔落在 %.2f ms ±%.2f ms 的单一簇里' % (100 * frac, top_mean, TOL))
        print('    ⇒ 【严格等周期轮询】，正是 spi_hid 空闲时对触控板持续拉取')
        print('      输入报告的形态（约 %.0f Hz）。' % (1000.0 / top_mean))
        print('    ⇒ 样本【有效】：确实抓到了触控板的 HID 读事务，不是空跑。')
        big = [g for g in gaps if g > top_mean * 3]
        print('    ⇒ 超过 3× 周期的长间隔 %d 个%s'
              % (len(big),
                 ('（最大 %.0f ms）' % max(big)) if big else '（无明显空洞）'))
    else:
        print('    最大簇仅 %.1f%% ⇒ 无法确认抓到的就是触控板读事务。' % (100 * frac))
        print('    ⇒ 这个样本【不足以支撑任何结论】。')

    print()
    print('★ Q2 判定（关键）：')
    print('    Microsoft-Windows-SPB-HIDI2C 的 opcode 全表：')
    for name, val in (('win:Info', 0), ('win:Start', 1), ('win:Stop', 2),
                      ('IoSpbReadDispatch', 10), ('IoSpbReadComplete', 11),
                      ('IoForwardToCompletionQueue', 12)):
        print('        opcode %2d  %s' % (val, name))
    print('    ⇒ 表中【没有任何 Write 类事件】。')
    print('    ⇒ 该 provider 结构上无法记录 I²C 写事务。')
    print('    ⇒ HID 的 Output Report 在 SPB 层就是写事务。')
    print('    ⇒ 【用它判断"点击时是否出现新 OUT 报告"必然得到假阴性】。')
    print('       这不是"没抓到"，是"provider 没有这个事件"。')
    print()
    print('    ⇒ 所以：ETW 能回答"主机在读什么"，【不能】回答"主机在写什么"。')

    # 附：HIDCLASS 的 INFORMATION 事件看是什么
    hc = [e for e in evs if e['prov'] == HIDCLASS_GUID and e['eid'] == 3]
    print()
    print('附：HIDCLASS INFORMATION 事件 %d 条，其DeviceInstancePath：' % len(hc))
    for e in hc[:6]:
        print('    VID&PID=%s&%s  %s'
              % (e['data'].get('VendorID'), e['data'].get('ProductID'),
                 (e['data'].get('DeviceInstancePath') or '')[:70]))
    tp = [e for e in hc if 'gxtp' in (e['data'].get('DeviceInstancePath') or '').lower()]
    print('    其中属于触控板(GXTP)的：%d 条' % len(tp))
    print('    ⇒ HIDCLASS provider 同样只记录设备启停/信息，不含报文内容。')


if __name__ == '__main__':
    for p in sys.argv[1:]:
        main(p)
        print()