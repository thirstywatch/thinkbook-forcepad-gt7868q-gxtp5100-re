"""TF100A 精确调用图：统计每个函数的调/被调次数。

用法:
  callgraph.py --indeg <addr> [<addr> ...]      查这些地址的调用者
  callgraph.py --funcs                           列出所有函数入口（push {...,lr}）
  callgraph.py --reach <addr>                    从该地址做可达性分析
  callgraph.py --callees <addr>                  列出某函数的直接调用（带调用点）
  callgraph.py --zero                            列出零调用者的函数入口
  callgraph.py --top                             按被调用次数排序

⚠️ 已知局限（重要）：
  本脚本只扫**直接** `bl`/`b` 控制流。固件里存在**间接调用**（函数指针，
  如 `str r1,[r0,#0x14]` 之后再 `blx`），静态图会把这类目标误判为"不可达"。
  实例：`0x080105AC`（CCER 配置）经 `0x0800D704` 的函数指针槽调用，
  直接图判为不可达 —— **是假阴性**。
  ⇒ 判"死代码"时必须同时满足：① 直接图零入度；② 无函数指针写入；
    ③ 不在向量表位置。单靠本脚本不足以定死代码。
"""
import re, os, sys, collections

# ★ 以脚本自身所在目录为基准找反汇编文件，避免依赖 CWD
ASM = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "touchpad_TF100A_thumb.asm.txt")
if not os.path.exists(ASM):
    sys.exit("找不到反汇编文件：%s\n（请与 callgraph.py 放在同一目录）" % ASM)

L = [l for l in open(ASM, encoding="utf-8").read().splitlines() if l.strip()]

# 解析：每行 = "PC  mnemonic  operands"
rows = []
for l in L:
    p = l.split(None, 2)
    if len(p) < 2:
        continue
    pc = int(p[0], 16)
    mn = p[1]
    ops = p[2] if len(p) > 2 else ""
    rows.append((pc, mn, ops))

pcset = {pc for pc, _, _ in rows}

# 所有控制流目标：#0xXXXXXXX
def targets(ops):
    out = []
    for m in re.finditer(r"#?(0x[0-9a-fA-F]{6,8})", ops):
        try:
            out.append(int(m.group(1), 16))
        except ValueError:
            pass
    return out

# 函数入口判定：push {...lr...}
is_entry = {}
for pc, mn, ops in rows:
    if mn == "push" and "lr" in ops:
        is_entry[pc] = True

# 收集 bl / b / blx / bx 目标
calls = collections.defaultdict(list)   # target -> [from...]
for pc, mn, ops in rows:
    if mn in ("bl", "blx", "b", "b.w", "bl.w"):
        for t in targets(ops):
            calls[t].append(pc)

# 对每个函数入口，统计被引用次数（只看落在已知 pc 的）
entries = sorted(is_entry)
def nearest_entry(pc):
    """返回 <= pc 的最近函数入口"""
    lo, hi = 0, len(entries) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if entries[mid] <= pc:
            best = entries[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return best

def indeg(addr):
    """addr 作为函数入口，被调用的来源点（去重）"""
    srcs = calls.get(addr, [])
    return srcs

# callees: 调用点所在函数入口 -> 被调目标集合
callees = collections.defaultdict(set)
for pc, mn, ops in rows:
    if mn in ("bl", "blx", "b.w", "bl.w", "b"):
        ent = nearest_entry(pc)
        for t in targets(ops):
            callees[ent].add(t)

def reachable(start):
    """从 start 出发，沿调用边做可达闭包（函数入口粒度）"""
    seen = set()
    stack = [start]
    while stack:
        a = stack.pop()
        if a in seen:
            continue
        seen.add(a)
        for t in callees.get(a, ()):
            if t in is_entry and t not in seen:
                stack.append(t)
    return seen

mode = sys.argv[1] if len(sys.argv) > 1 else "--help"

if mode == "--indeg":
    for arg in sys.argv[2:]:
        a = int(arg, 16)
        srcs = indeg(a)
        print("=== 0x%08X 被调用 %d 次 ===" % (a, len(srcs)))
        for s in srcs:
            ent = nearest_entry(s)
            print("   from 0x%08X   (所在函数入口 0x%08X)" % (s, ent))
        if not srcs:
            print("   ⚠ 零调用者")

elif mode == "--funcs":
    print("函数入口共 %d 个" % len(entries))
    for e in entries:
        n = len(calls.get(e, []))
        print("   0x%08X  被调 %d 次" % (e, n))

elif mode == "--reach":
    a = int(sys.argv[2], 16)
    ent = nearest_entry(a)
    print("起点 0x%08X 归一化到所在函数入口 0x%08X" % (a, ent))
    seen = reachable(ent)
    print("从 0x%08X 可达 %d 个函数" % (ent, len(seen)))
    for s in sorted(seen):
        print("   0x%08X" % s)

elif mode == "--callees":
    # 列出某函数直接调用的目标（带调用点）
    a = int(sys.argv[2], 16)
    ent = nearest_entry(a)
    print("=== 函数 0x%08X 的直接调用 ===" % ent)
    seen_pc = set()
    for pc, mn, ops in rows:
        if mn in ("bl", "blx", "b.w", "bl.w") and nearest_entry(pc) == ent:
            for t in targets(ops):
                print("   %08X -> 0x%08X" % (pc, t))
                seen_pc.add(pc)

elif mode == "--top":
    c = collections.Counter()
    for pc, mn, ops in rows:
        if mn in ("bl", "blx"):
            for t in targets(ops):
                c[t] += 1
    print("=== 被调用最多的 30 个目标 ===")
    for t, n in c.most_common(30):
        tag = "函数" if t in is_entry else "???"
        print("   0x%08X  ×%-4d %s" % (t, n, tag))

elif mode == "--zero":
    # 找所有"是函数入口但零调用者"的
    print("=== 零调用者的函数入口（候选：ISR 向量 / 模块入口 / 死代码）===")
    z = [e for e in entries if not calls.get(e)]
    print("共 %d 个" % len(z))
    for e in z:
        print("   0x%08X" % e)

else:
    print(__doc__)
