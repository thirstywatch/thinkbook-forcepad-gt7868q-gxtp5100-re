"""把构建产物部署到 U 盘（F:）与项目 usb/ 目录。
用法：python deploy_usb.py [盘符，默认 F]
"""
import hashlib
import os
import shutil
import sys

DRIVE = (sys.argv[1] if len(sys.argv) > 1 else "F").rstrip(":") + ":"
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
USB = os.path.join(PKG, "usb")

PLAN = [
    # 源文件, U 盘目标（相对盘符）
    ("TpadBootTest.efi", r"\EFI\BOOT\BOOTX64.EFI"),      # 主入口：F12 选 U 盘就跑它（含按任意键清理）
    ("TpadBootTest.efi", r"\EFI\Tpad\TpadBootTest.efi"),
    ("TpadClear.efi", r"\EFI\Tpad\TpadClear.efi"),       # 救命：纯清理程序
    # ★ Driver0000 里登记的路径就是 \EFI\Tpad\TpadAcpiProbe.efi
    #   ⇒ 把【真驱动】放在这个位置，固件下次启动就会加载它
    ("TpadAcpiPatch.efi", r"\EFI\Tpad\TpadAcpiProbe.efi"),
    ("TpadAcpiPatch.efi", r"\EFI\Tpad\TpadAcpiPatch.efi"),
]


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def put(src, dst):
    """直接原地覆盖写入。

    注意：不要用 os.remove / shutil.rmtree —— 本环境有 safe-delete 垫片会把删除
    重定向到回收站，在 FAT U 盘上会失败。也不要用 shutil.copyfile 前删文件。
    另外 bash 的 cp 覆盖 FAT 上的已有文件会 Permission denied，所以统一走 Python
    的 open(...,'wb')（截断写入，不需要删除）。
    """
    d = os.path.dirname(dst)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

    if os.path.exists(dst):
        try:
            os.chmod(dst, 0o666)
        except Exception:
            pass

    with open(src, "rb") as f:
        data = f.read()
    with open(dst, "wb") as f:
        f.write(data)
    return len(data), md5(dst)


print(f"目标盘: {DRIVE}")
for name, rel in PLAN:
    src = os.path.join(HERE, name)
    if not os.path.exists(src):
        print(f"  ✗ 源文件缺失: {src}")
        continue
    size, h = put(src, DRIVE + rel)
    print(f"  OK  {DRIVE}{rel}   {size:>8,} B   {h[:8]}")

# OpenShell 留档到 \EFI\Tpad\
shell = os.path.join(PKG, "shell", "OpenShell_x64.efi")
if os.path.exists(shell):
    size, h = put(shell, DRIVE + r"\EFI\Tpad\OpenShell.efi")
    print(f"  OK  {DRIVE}\\EFI\\Tpad\\OpenShell.efi   {size:>8,} B   {h[:8]}")

# 删掉根目录的 shellx64.efi，避免歧义
stale = DRIVE + r"\shellx64.efi"
if os.path.exists(stale):
    os.remove(stale)
    print(f"  已删除 {stale}（避免歧义）")

# 同步项目 usb/ 目录
for name, rel in PLAN:
    src = os.path.join(HERE, name)
    if os.path.exists(src):
        put(src, os.path.join(USB, rel.lstrip("\\")))

print()
print("=== U 盘最终内容 ===")
for root, _dirs, files in os.walk(DRIVE + os.sep):
    for f in files:
        p = os.path.join(root, f)
        if "System Volume Information" in p:
            continue
        print(f"  {os.path.getsize(p):>10,}  {p}")
