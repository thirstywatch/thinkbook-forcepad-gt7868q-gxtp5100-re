r"""ecram_live.py -- read the EC RAM window (physical 0xFE0B0400, 4096 bytes) straight from
RWEverything's kernel driver, sample it continuously, and tell you which bytes react to the lid.

Requires: RWEverything installed AND Rw.exe having been run once as admin (that loads \\.\RwDrv).

Usage:
    python ecram_live.py --probe          # just check whether the driver is loaded
    python ecram_live.py --once out.bin   # take one snapshot
    python ecram_live.py --run            # the full A/B/C experiment (about 90 s, follow prompts)

Driver interface (RwDrv):
    device : \\\\.\\RwDrv
    struct : { u64 physicalAddress; u32 size; u32 access; u64 buffer; }   access 0=U8 1=U16 2=U32
    IOCTL  : 0x222808 = read physical memory   (0x22280C would be WRITE -- never used here)
"""
import ctypes, ctypes.wintypes as wt, struct, sys, time, os

ADDR = 0xFE0B0400
SIZE = 0x1000
IOCTL_READ_PHYS = 0x222808

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
INVALID_HANDLE = ctypes.c_void_p(-1).value

k32 = ctypes.WinDLL("kernel32", use_last_error=True)


class PhysRw(ctypes.Structure):
    _fields_ = [("physicalAddress", ctypes.c_ulonglong),
                ("size", ctypes.c_uint32),
                ("access", ctypes.c_uint32),
                ("buffer", ctypes.c_ulonglong)]


assert ctypes.sizeof(PhysRw) == 24, ctypes.sizeof(PhysRw)

k32.CreateFileW.restype = ctypes.c_void_p
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
                            wt.DWORD, wt.DWORD, ctypes.c_void_p]
k32.DeviceIoControl.restype = wt.BOOL
k32.DeviceIoControl.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.c_void_p, wt.DWORD,
                                ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD),
                                ctypes.c_void_p]
k32.CloseHandle.argtypes = [ctypes.c_void_p]


def open_drv():
    h = k32.CreateFileW("\\\\.\\RwDrv", GENERIC_READ | GENERIC_WRITE, 0, None,
                        OPEN_EXISTING, 0, None)
    if h == INVALID_HANDLE or h is None:
        e = ctypes.get_last_error()
        return None, e
    return h, 0


def read_phys(h, addr, size):
    """Read `size` bytes; chunked so a long read cannot fail as a whole."""
    out = bytearray()
    step = 0x100
    while len(out) < size:
        n = min(step, size - len(out))
        buf = ctypes.create_string_buffer(n)
        req = PhysRw(addr + len(out), n, 0, ctypes.cast(buf, ctypes.c_void_p).value)
        ret = wt.DWORD(0)
        ok = k32.DeviceIoControl(h, IOCTL_READ_PHYS, ctypes.byref(req), ctypes.sizeof(req),
                                 None, 0, ctypes.byref(ret), None)
        if not ok:
            # second attempt: some builds expect the data in the output buffer instead
            buf2 = ctypes.create_string_buffer(n)
            req2 = PhysRw(addr + len(out), n, 0, 0)
            ok2 = k32.DeviceIoControl(h, IOCTL_READ_PHYS, ctypes.byref(req2), ctypes.sizeof(req2),
                                      buf2, n, ctypes.byref(ret), None)
            if not ok2:
                raise OSError("DeviceIoControl failed (err=%d) at 0x%X"
                              % (ctypes.get_last_error(), addr + len(out)))
            out += buf2.raw[:n]
        else:
            out += buf.raw[:n]
    return bytes(out)


# ---------------- field table (from Field(ECMM)) ----------------
FIELDS = [
    (0x002, "LESR"), (0x0E4, "EST4"), (0x0E5, "EST3"), (0x0E6, "EST5"), (0x0E7, "EST1"),
    (0x0E8, "EST6"), (0x0E9, "EST2"), (0x0EA, "WLIS/APSB/TCAD"), (0x52B, "ERIB"),
    (0x52F, "SMST"), (0x530, "SMAD"), (0x531, "SMCM"), (0x532, "SMD0(512B)"),
    (0x732, "BCNT"), (0x733, "SMAA"), (0x736, "SMBN"), (0x73B, "SUPL"), (0x73C, "SPPT"),
    (0x73D, "FPPT"), (0x83E, "EECF"), (0x83F, "SGMT/VIDO/TOUP/SPMT/MCMT"), (0x840, "ODTS"),
    (0x841, "OSTY/PBOV/ECRD/ADPT"), (0x842, "PWAK..TWAK"), (0x843, "CCAC..ACAC"),
    (0x844, "S3ST..CSRM"), (0x845, "CATT"), (0x846, "VATT"), (0x847, "THLT"), (0x848, "TCNL"),
    (0x849, "MODE/INIT/FAEN"), (0x84A, "SDTM"), (0x84B, "FSSN/FANU"), (0x84C, "PCVL/SWTO/TTHR"),
    (0x84D, "TTHM/THTL/TFCT/NPST"), (0x84E, "CTMP"), (0x84F, "CTML"), (0x851, "SKTB"),
    (0x852, "SKTC"), (0x853, "DPOT"), (0x856, "*** LIDF ***"), (0x857, "BRTS"),
    (0x858, "S35M/S35S/MSFG/FFEN/FFST"), (0x859, "WLAT..EX3G"), (0x85A, "PJID"),
    (0x85B, "CPUJ/CPNM/GATY"), (0x85E, "BTY0/BAM0"), (0x85F, "BST0"), (0x860, "BRC0"),
    (0x864, "BPV0"), (0x866, "BDV0"), (0x868, "BDC0"), (0x86A, "BFC0"), (0x86C, "GAU0"),
    (0x86D, "BAT0"), (0x86E, "BPC0"), (0x870, "BAC0"), (0x872, "BCG0"), (0x874, "BFCB"),
    (0x876, "BTPB"), (0x878, "BOL0/BFS0"), (0x879, "ORRF"),
]


def who(off):
    prev = None
    for base, name in FIELDS:
        if base <= off:
            prev = (base, name)
        else:
            break
    return prev[1] if prev else "(before first field)"


def probe():
    h, err = open_drv()
    if h is None:
        print("[X] \\\\.\\RwDrv NOT available (CreateFile err=%d)." % err)
        print("    -> Run Rw.exe once as Administrator (that loads the driver), then retry.")
        print("    -> err 2 = file not found (driver not loaded); 5 = access denied (run as admin)")
        return 1
    print("[OK] \\\\.\\RwDrv opened.")
    try:
        b = read_phys(h, ADDR, 64)
        print("[OK] sample @0x%X: %s" % (ADDR, b.hex(" ")))
    finally:
        k32.CloseHandle(h)
    return 0


def once(path):
    h, err = open_drv()
    if h is None:
        print("[X] driver not available (err=%d)" % err); return 1
    try:
        data = read_phys(h, ADDR, SIZE)
    finally:
        k32.CloseHandle(h)
    open(path, "wb").write(data)
    print("wrote %d bytes -> %s" % (len(data), path))
    print("LIDF byte (0x856) = 0x%02X   bit1 = %d" % (data[0x856], (data[0x856] >> 1) & 1))
    return 0


def run():
    h, err = open_drv()
    if h is None:
        print("[X] driver not available (err=%d)" % err); return 1

    print("=" * 68)
    print(" EC RAM live sampler -- target 0x%X, %d bytes" % (ADDR, SIZE))
    print("=" * 68)
    print(" Total ~80 s.  Follow the prompts.  NEVER bring the lid near closed.")
    print()
    phases = [("A", 20, "DO NOT TOUCH the laptop. Sit still."),
              ("B", 45, "Now SLOWLY swing the screen 90deg +/- 10deg, back and forth."),
              ("C", 15, "Stop. Hold the screen at 90deg and sit still.")]
    samples = []          # (phase, t, bytes)
    for tag, dur, msg in phases:
        print("[phase %s] %d s : %s" % (tag, dur, msg))
        t0 = time.time()
        while time.time() - t0 < dur:
            try:
                samples.append((tag, time.time() - t0, read_phys(h, ADDR, SIZE)))
            except OSError as e:
                print("   read error:", e)
            time.sleep(0.20)
        print("   -> %d samples" % sum(1 for s in samples if s[0] == tag))
    k32.CloseHandle(h)

    print()
    print("=" * 68)
    print(" analysis  (%d samples)" % len(samples))
    print("=" * 68)
    base = samples[0][2]
    varying = {}
    for off in range(SIZE):
        vals = {}
        for ph, t, d in samples:
            vals.setdefault(ph, set()).add(d[off])
        if len(set().union(*vals.values())) > 1:
            varying[off] = {ph: sorted(v) for ph, v in vals.items()}

    if not varying:
        print(" NOTHING changed at all -- check that the driver really read memory")
        print(" (sample:", base[:32].hex(" "), ")"); return 0

    print(" %-7s %-28s %-22s %s" % ("off", "field", "values by phase A/B/C", "verdict"))
    print("-" * 96)
    for off, vals in sorted(varying.items()):
        a = vals.get("A", [])
        b = vals.get("B", [])
        c = vals.get("C", [])
        def s(v):
            return "{" + ",".join("%02X" % x for x in v[:4]) + (".." if len(v) > 4 else "") + "}"
        verdict = ""
        if len(a) == 1 and len(c) == 1 and len(b) > 1:
            verdict = "<== reacts ONLY to screen movement"
        elif len(a) > 1:
            verdict = "(noisy even while still)"
        print(" 0x%03X   %-28s %-22s %s" % (off, who(off), "%s %s %s" % (s(a), s(b), s(c)), verdict))
    print()
    print(" LIDF byte 0x856 -> phase A %s | B %s | C %s"
          % ([hex(x) for x in sorted({d[0x856] for ph, t, d in samples if ph == "A"})],
             [hex(x) for x in sorted({d[0x856] for ph, t, d in samples if ph == "B"})],
             [hex(x) for x in sorted({d[0x856] for ph, t, d in samples if ph == "C"})]))
    open("ecram_live_samples.bin", "wb").write(b"".join(d for _, _, d in samples))
    print(" raw samples -> ecram_live_samples.bin")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        print(__doc__); sys.exit(0)
    if a[0] == "--probe":
        sys.exit(probe())
    if a[0] == "--once":
        sys.exit(once(a[1] if len(a) > 1 else "ecram-once.bin"))
    if a[0] == "--run":
        sys.exit(run())
    print(__doc__)
