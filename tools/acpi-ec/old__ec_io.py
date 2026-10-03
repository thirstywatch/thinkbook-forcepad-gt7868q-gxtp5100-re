import sys, re, struct
from pe_dis import disasm_pe

IN_OUT = {"in","out","insb","insw","insd","outsb","outsw","outsd"}

def analyze(path):
    r=disasm_pe(path)
    if not r: print("非 PE"); return
    print("="*74)
    print("### %s   entry=0x%X"%(path, r["info"]["ep"]))
    events=[]
    for name,base,code,insns,bad in r["insn_groups"]:
        # 建地址->索引 便于回溯
        idx={ins.address:i for i,ins in enumerate(insns)}
        for i,ins in enumerate(insns):
            m=ins.mnemonic
            if m not in IN_OUT: continue
            port=None; how=""
            # 立即数端口: E4/E5/E6/E7 -> op_str 形如 "al, 0x66"
            if ins.operands:
                for op in ins.operands:
                    if op.type==2:  # IMM
                        port=op.imm & 0xFFFF; how="imm"
            if port is None:
                # DX 形式: 回溯最近 5 条找 mov dx/edx, imm
                for j in range(i-1,max(-1,i-6),-1):
                    p=insns[j]
                    if p.mnemonic=="mov" and p.operands and p.operands[0].type==1:
                        reg=p.reg_name(p.operands[0].reg) if p.operands[0].reg else ""
                        if reg in ("dx","edx","rdx"):
                            for op in p.operands[1:]:
                                if op.type==2:
                                    port=op.imm & 0xFFFF; how="dx<-%s"%("%02X"%(op.imm&0xFFFFFFFF))
                            break
                    if p.mnemonic in ("out","in"): break
            if port is not None or m in ("insb","insw","insd","outsb","outsw","outsd"):
                events.append((ins.address,m,port,how,ins.op_str))
    print("\n-- I/O 指令 (%d 条) --"%len(events))
    from collections import Counter
    c=Counter()
    for a,m,p,h,o in events:
        c[(m,p)]+=1
    for (m,p),n in c.most_common(40):
        print("   %-6s port=%s  ×%d"%(m, ("0x%X"%p) if p is not None else "?", n))
    print("\n-- 明细（前 60 条，含上下文）--")
    for a,m,p,h,o in events[:60]:
        print("   0x%06X  %-5s %-24s  [%s]"%(a,m,o,h))

    # 立即数常量扫描：找像 EC 命令码/MMIO 的
    print("\n-- 可疑常量（0x62/0x66/0x80/0xFE0Bxxxx/0x6xxxx 风格）--")
    consts=Counter()
    for name,base,code,insns,bad in r["insn_groups"]:
        for ins in insns:
            for op in ins.operands:
                if op.type==2:
                    v=op.imm
                    if 0x60<=v<=0x68 or v in (0x80,0x84,0x81,0x2000,0xFE0B0400,0xFE0B0401):
                        consts[(v,ins.mnemonic)]+=1
    for (v,m),n in sorted(consts.items(), key=lambda x:-x[1])[:30]:
        print("   0x%X  in %-8s ×%d"%(v,m,n))
    return r

if __name__=="__main__":
    for p in sys.argv[1:]: analyze(p)
