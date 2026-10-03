"""把组装好的 OpenCore 内容部署到 U 盘。

要点：
  * \EFI\BOOT\BOOTX64.EFI 会被系统的 safe-delete/锁定问题卡住 ⇒ 沿用"目录改名绕过"
  * \EFI\OC\ 是全新目录，直接写即可
  * \EFI\Tpad\ 里我们自己的程序保持不动（备用）

用法：python deploy_oc.py [盘符 默认F]
"""
import base64
import hashlib
import os
import plistlib
import shutil
import sys
import time

DRIVE = (sys.argv[1] if len(sys.argv) > 1 else "F").rstrip(":") + ":"
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
SRC = os.path.join(PKG, "open-core-usb")

FIND = bytes.fromhex("0A040A2C0A200D475854503531303000")
REPLACE = bytes.fromhex("0AFE0A2C0A200D4D5346543030303100")


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def is_locked(p):
    if not os.path.exists(p):
        return False
    try:
        with open(p, "ab"):
            pass
        return False
    except Exception:
        return True


def put(src, dst):
    d = os.path.dirname(dst)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    if os.path.exists(dst):
        try:
            os.chmod(dst, 0o666)
        except Exception:
            pass
    data = open(src, "rb").read()
    with open(dst, "wb") as f:
        f.write(data)
    return len(data)


def ensure_writable_dir(rel):
    full = DRIVE + rel
    if not os.path.isdir(full):
        os.makedirs(full, exist_ok=True)
        return
    locked = [f for f in os.listdir(full)
              if os.path.isfile(os.path.join(full, f)) and is_locked(os.path.join(full, f))]
    if not locked:
        return
    stamp = time.strftime("%H%M%S")
    backup = f"{full}_BACKUP_{stamp}"
    try:
        os.rename(full, backup)
        print(f"  [绕过] 目录被锁，已改名挪走: {backup}")
        os.makedirs(full, exist_ok=True)
    except Exception as e:
        print(f"  [绕过失败] {e}")


def verify_config():
    cfg = os.path.join(SRC, "EFI", "OC", "config.plist")
    d = plistlib.load(open(cfg, "rb"))
    print("=== config.plist 自检 ===")
    patch = d["ACPI"]["Patch"]
    ok = False
    if patch:
        p = patch[0]
        ok = (p["Find"] == FIND and p["Replace"] == REPLACE and p["Enabled"] is True
              and p["TableSignature"] == b"DSDT")
        print(f"  ACPI->Patch 条目数 : {len(patch)}")
        print(f"  Find    : {p['Find'].hex(' ')}")
        print(f"  Replace : {p['Replace'].hex(' ')}")
        print(f"  长度相等: {len(p['Find']) == len(p['Replace'])}   Enabled: {p['Enabled']}   Sig: {p['TableSignature']}")
        print(f"  base64 Find    : {base64.b64encode(p['Find']).decode()}")
        print(f"  base64 Replace : {base64.b64encode(p['Replace']).decode()}")
    print(f"  PlatformInfo.Automatic : {d['PlatformInfo']['Automatic']}  (应为 False)")
    print(f"  UEFI.Drivers           : {d['UEFI']['Drivers']}  (应只列 OpenRuntime.efi)")
    print(f"  Misc.Security.ScanPolicy: {d['Misc']['Security']['ScanPolicy']}")
    print(f"  Misc.Boot.ShowPicker   : {d['Misc']['Boot']['ShowPicker']}")
    print(f"  ACPI->Add / Delete     : {len(d['ACPI']['Add'])} / {len(d['ACPI']['Delete'])}")
    print(f"  >> 自检: {'通过 ✅' if ok else '★不通过★'}")
    print()
    return ok


def main():
    print(f"目标盘: {DRIVE}")
    print(f"源目录: {SRC}")
    print()
    if not verify_config():
        print("配置有问题，中止。")
        return

    print("=== 部署 ===")
    ensure_writable_dir(r"\EFI\BOOT")

    plan = []
    for root, _d, files in os.walk(SRC):
        for f in files:
            s = os.path.join(root, f)
            rel = os.path.relpath(s, SRC)
            plan.append((s, DRIVE + "\\" + rel.replace("/", "\\")))

    plan.sort(key=lambda t: (t[1].count("\\"), t[1]))
    for s, dst in plan:
        if is_locked(dst):
            print(f"  LOCKED {dst}")
            continue
        n = put(s, dst)
        print(f"  OK  {dst}   {n:>9,} B")

    # 空目录
    for rel in (r"\EFI\OC\ACPI", r"\EFI\OC\Kexts"):
        p = DRIVE + rel
        if not os.path.isdir(p):
            os.makedirs(p, exist_ok=True)
            print(f"  新建空目录 {p}")

    print()
    print("=== U 盘 EFI 目录 ===")
    root = DRIVE + r"\EFI"
    for r, dirs, files in os.walk(root):
        if "BACKUP" in r:
            continue
        for f in sorted(files):
            p = os.path.join(r, f)
            print(f"  {os.path.getsize(p):>10,}  {p}")
        for d in sorted(dirs):
            if "BACKUP" not in d and not os.listdir(os.path.join(r, d)):
                print(f"  {'(empty)':>10}  {os.path.join(r, d)}")


if __name__ == "__main__":
    main()
