"""部署到 U 盘 —— 带"被锁文件"绕过。

背景：本机环境下，之前用 Python 部署过的 .efi 文件会被 Windows 拒绝覆盖/改名/删除
      （ACCESS_DENIED，同目录新建新文件却完全正常）。
解决办法：把整个目录改名挪走（BACKUP_*），再新建一个同名新目录，把文件写进去。
         固件只认路径 F:\\EFI\\BOOT\\BOOTX64.EFI，所以新目录里的新文件同样有效。

用法：python deploy_usb_fix.py [盘符 默认F]
"""
import hashlib
import os
import shutil
import sys
import time

DRIVE = (sys.argv[1] if len(sys.argv) > 1 else "F").rstrip(":") + ":"
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)

# 需要写到 U 盘的（源文件 -> 相对路径）
FILES = [
    ("TpadInstall.efi", r"\EFI\BOOT\BOOTX64.EFI"),        # 主入口：装驱动到 ESP
    ("TpadInstall.efi", r"\EFI\Tpad\TpadInstall.efi"),
    ("TpadBootTest.efi", r"\EFI\Tpad\TpadBootTest.efi"),  # 纯诊断（备用）
    ("TpadClear.efi", r"\EFI\Tpad\TpadClear.efi"),        # 救命
    ("TpadAcpiPatch.efi", r"\EFI\Tpad\TpadAcpiProbe.efi"),  # ★ 要装到 ESP 的驱动本体
    ("TpadAcpiPatch.efi", r"\EFI\Tpad\TpadAcpiPatch.efi"),
]

# 可选：把 Shell 也带上（若项目里有）
OPTIONAL = [("OpenShell_x64.efi", r"\EFI\Tpad\OpenShell.efi")]


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def write_new(dst, data):
    """写新文件（不覆盖）。返回 True/False。"""
    d = os.path.dirname(dst)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    try:
        with open(dst, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"    write failed: {dst} -> {e}")
        return False


def is_locked(dst):
    if not os.path.exists(dst):
        return False
    try:
        with open(dst, "ab"):
            pass
        return False
    except Exception:
        return True


def make_dir_writable(rel_dir):
    """确保 DRIVE+rel_dir 是一个"新目录"（里面没有残留的锁定文件）。"""
    full = DRIVE + rel_dir
    if not os.path.isdir(full):
        os.makedirs(full, exist_ok=True)
        return

    # 目录里若有锁定文件，就把整个目录改名挪走
    locked = [f for f in os.listdir(full)
              if os.path.isfile(os.path.join(full, f)) and is_locked(os.path.join(full, f))]
    if not locked:
        return

    stamp = time.strftime("%H%M%S")
    backup = f"{full}_BACKUP_{stamp}"
    try:
        os.rename(full, backup)
        print(f"  [绕过] 旧目录被锁定，已改名挪走: {backup}")
    except Exception as e:
        print(f"  [绕过失败] 连目录改名都不行: {e}")
        return

    os.makedirs(full, exist_ok=True)


def main():
    print(f"目标盘: {DRIVE}")
    for rel in (r"\EFI\BOOT", r"\EFI\Tpad"):
        make_dir_writable(rel)
        # 目录里若有锁定文件而改名失败，则退化为"只写没被锁的"
    print()

    ok = 0
    for name, rel in FILES:
        src = os.path.join(HERE, name)
        if not os.path.exists(src):
            print(f"  SKIP 源缺失 {name}")
            continue
        dst = DRIVE + rel
        if is_locked(dst):
            print(f"  LOCKED {dst}（目录级绕过未生效）")
            continue
        if write_new(dst, open(src, "rb").read()):
            print(f"  OK  {dst}  {os.path.getsize(dst):>8,} B  {md5(dst)[:8]}")
            ok += 1

    for name, rel in OPTIONAL:
        src = os.path.join(PKG, "shell", name)
        dst = DRIVE + rel
        if os.path.exists(src) and (not is_locked(dst)):
            if write_new(dst, open(src, "rb").read()):
                print(f"  OK  {dst}  {os.path.getsize(dst):>8,} B  (shell)")

    print()
    print(f"=== 成功 {ok}/{len(FILES)} ===")
    print("=== U 盘内容 ===")
    for root, _d, files in os.walk(DRIVE + os.sep):
        for f in files:
            p = os.path.join(root, f)
            if "System Volume Information" in p:
                continue
            flag = "  [LOCKED]" if is_locked(p) else ""
            print(f"  {os.path.getsize(p):>10,}  {p}{flag}")


if __name__ == "__main__":
    main()
