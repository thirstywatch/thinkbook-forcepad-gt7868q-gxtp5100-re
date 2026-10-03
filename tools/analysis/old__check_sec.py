import winreg
def rd(root, path, name):
    try:
        with winreg.OpenKey(root, path) as k:
            v, t = winreg.QueryValueEx(k, name)
            return v
    except FileNotFoundError:
        return "KEY_NOT_FOUND"
    except OSError as e:
        return "NO_VALUE(%s)" % e.errno

print("=== VBS / HVCI ===")
print("EnableVirtualizationBasedSecurity :", rd(winreg.HKEY_LOCAL_MACHINE,
    r"SYSTEM\CurrentControlSet\Control\DeviceGuard", "EnableVirtualizationBasedSecurity"))
print("HVCI Enabled                       :", rd(winreg.HKEY_LOCAL_MACHINE,
    r"SYSTEM\CurrentControlSet\Control\DeviceGuard\Scenarios\HypervisorEnforcedCodeIntegrity", "Enabled"))
print("VulnerableDriverBlocklistEnable    :", rd(winreg.HKEY_LOCAL_MACHINE,
    r"SYSTEM\CurrentControlSet\Control\CI\Config", "VulnerableDriverBlocklistEnable"))
print("=== DeviceGuard Running ===")
try:
    dg = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\DeviceGuard")
    i=0
    while True:
        try:
            n,_,_ = winreg.EnumKey(dg, i); print("  subkey:", n); i+=1
        except OSError: break
    winreg.CloseKey(dg)
except OSError as e:
    print("  err", e)
for n in ("SecurityServicesRunning","SecurityServicesConfigured","VirtualizationBasedSecurityStatus"):
    print(n, ":", rd(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\DeviceGuard", n))
