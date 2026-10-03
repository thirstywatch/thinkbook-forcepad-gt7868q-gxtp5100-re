import struct
PATH = r"C:/Windows/Firmware/TB14P_GT7868Q_14030522_20240202.BIN"
data = open(PATH, "rb").read()
N = len(data)
IMG_OFF = 0x19ABC          # 候选向量表位置
IMG_BASE = 0x08000000      # 加载地址
IMG_SIZE = N - IMG_OFF     # 到 EOF
print("FILE_SIZE", N, hex(N))
print("IMG_OFF", hex(IMG_OFF), "IMG_SIZE", IMG_SIZE, hex(IMG_SIZE))
print("=> 若镜像=最后56480字节, 与任务'约56480'一致:", IMG_SIZE==56480)

def u32(o): return struct.unpack_from("<I", data, o)[0]

# 向量表 (image 开头)
print("\n=== 向量表 @0x%X (加载基址0x%X) ===" % (IMG_OFF, IMG_BASE))
sp = u32(IMG_OFF)
rst = u32(IMG_OFF+4)
print("SP(initial) =", hex(sp), " Reset =", hex(rst))
# 统计前 N 个向量
entries = []
oob = 0
for i in range(0, 64):
    v = u32(IMG_OFF + i*4)
    addr = v & ~1
    thumb = v & 1
    if addr == 0:
        kind = "null"
    elif 0x08000000 <= addr < IMG_BASE + IMG_SIZE:
        kind = "in-flash"
    elif 0x20000000 <= addr < 0x20010000:
        kind = "in-sram"
    else:
        kind = "OUT-OF-BOUNDS"
        oob += 1
    entries.append((i, v, kind))
# 打印前 16 个
for i,(idx,v,kind) in enumerate(entries[:16]):
    print("  vec[%2d] = %08X  %s" % (idx, v, kind))
print("  越界向量(前64个中):", oob)

# 找第一个 null 向量，确定向量表实际长度
first_null = next((i for i,v,_ in entries if v==0), None)
print("  前64向量中首个null index:", first_null)

# 镜像头部 64 字节 (看有无长度字段/头)
print("\n=== 镜像头 64 字节 @0x%X ===" % IMG_OFF)
h = data[IMG_OFF:IMG_OFF+64]
print(' '.join('%02X'%b for b in h))

# 向量表前 64 字节 = 头本身
# 检查头部几个 32 位值是否像长度
print("  头部前8个u32:", [hex(u32(IMG_OFF+i*4)) for i in range(8)])

# 镜像前 128 字节上下文 (看 0x19ABC 之前是否有长度声明)
print("\n=== 0x19ABC 之前 64 字节 (是否有载荷头) ===")
pre = data[IMG_OFF-64:IMG_OFF]
print(' '.join('%02X'%b for b in pre))
