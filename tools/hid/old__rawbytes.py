import struct, sys
d = open("touchpad_GT7868Q_fw.bin", "rb").read()
def off(a): return a - 0x08005000 + 0x19ABC
addrs = [int(x, 16) for x in sys.argv[1:]]
if not addrs:
    addrs = [0x0800FBE0, 0x0800FBE6, 0x0800FBE8, 0x0800FBEA, 0x0800FA4C, 0x0800FAAE, 0x0800FB96]
for a in addrs:
    b = d[off(a):off(a) + 8]
    print("%08X  %s  word=%08X" % (a, " ".join("%02X" % x for x in b), struct.unpack_from("<I", b)[0]))
try:
    import capstone
    print("capstone OK", capstone.__version__)
except Exception as e:
    print("capstone unavailable:", e)
