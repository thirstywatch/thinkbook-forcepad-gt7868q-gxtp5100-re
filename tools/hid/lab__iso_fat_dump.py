"""从 Lenovo BIOS 更新 ISO 里解析 FAT32 分区，列出并提取文件。

ISO 结构（项目此前已解出）：
  El Torito 硬盘仿真镜像 LBA 27 (0xD800) -> MBR 分区 type 0x0B -> FAT32 @ 0x11800

用法：
  python iso_fat_dump.py <iso> list
  python iso_fat_dump.py <iso> extract <FAT路径> <输出文件>
"""
import struct
import sys


class Fat32:
    def __init__(self, data, part_off):
        self.d = data
        self.base = part_off
        b = data
        o = part_off
        self.bytes_per_sec = struct.unpack_from("<H", b, o + 11)[0]
        self.sec_per_clus = b[o + 13]
        self.reserved = struct.unpack_from("<H", b, o + 14)[0]
        self.num_fats = b[o + 16]
        self.fat_size = struct.unpack_from("<I", b, o + 36)[0]
        self.root_clus = struct.unpack_from("<I", b, o + 44)[0]
        self.data_start = o + (self.reserved + self.num_fats * self.fat_size) * self.bytes_per_sec

    def clus_off(self, clus):
        return self.data_start + (clus - 2) * self.sec_per_clus * self.bytes_per_sec

    def next_clus(self, clus):
        fat = self.base + self.reserved * self.bytes_per_sec
        return struct.unpack_from("<I", self.d, fat + clus * 4)[0] & 0x0FFFFFFF

    def chain(self, clus):
        out = []
        while 2 <= clus < 0x0FFFFFF8 and len(out) < 200000:
            out.append(clus)
            clus = self.next_clus(clus)
        return out

    def read_clus(self, clus):
        off = self.clus_off(clus)
        return self.d[off:off + self.sec_per_clus * self.bytes_per_sec]

    def entry_bytes(self, clus):
        return b"".join(self.read_clus(c) for c in self.chain(clus))

    def walk(self, clus, path=""):
        """返回 [(完整路径, 首簇, 大小)]"""
        out = []
        for e in self.entry_bytes(clus):
            if len(out) * 32 >= len(self.entry_bytes(clus)):
                break
        buf = self.entry_bytes(clus)
        for i in range(0, len(buf), 32):
            e = buf[i:i + 32]
            if len(e) < 32 or e[0] == 0x00:
                break
            if e[0] == 0xE5:
                continue
            attr = e[11]
            if attr & 0x0F == 0x0F:  # LFN
                continue
            name = bytes(e[0:8]).decode("ascii", "replace").strip()
            ext = bytes(e[8:11]).decode("ascii", "replace").strip()
            if name in (".", ".."):
                continue
            full = f"{path}/{name}" + (f".{ext}" if ext else "")
            first = (struct.unpack_from("<H", e, 20)[0] << 16) | struct.unpack_from("<H", e, 26)[0]
            size = struct.unpack_from("<I", e, 28)[0]
            if attr & 0x10:
                out += self.walk(first, full)
            else:
                out.append((full, first, size))
        return out

    def read_file(self, first, size):
        buf = b"".join(self.read_clus(c) for c in self.chain(first))
        return buf[:size]


def main():
    iso = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else "list"
    d = open(iso, "rb").read()
    fs = Fat32(d, 0x11800)

    if cmd == "list":
        files = fs.walk(fs.root_clus)
        print(f"共 {len(files)} 个文件/目录")
        for p, c, s in files:
            print(f"  {s:>12,}  {p}")
    elif cmd == "extract":
        need = sys.argv[3].upper().lstrip("/")
        out = sys.argv[4]
        for p, c, s in fs.walk(fs.root_clus):
            if p.upper().lstrip("/") == need:
                blob = fs.read_file(c, s)
                open(out, "wb").write(blob)
                print(f"已提取 {p} -> {out}  ({len(blob):,} 字节)")
                return
        print(f"未找到 {need}")
        sys.exit(1)


if __name__ == "__main__":
    main()
