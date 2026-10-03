import io
p = r"C:\Windows\System32\DriverStore\FileRepository\goodixtouchpad.inf_amd64_dd57a59bc9759d61\goodixtouchpad.inf"
b = open(p,"rb").read()
print("size", len(b), "first4", b[:4].hex())
for enc in ("utf-16","utf-8-sig","utf-16-be"):
    try:
        t = b.decode(enc)
        print("=== decoded as", enc, "===")
        print(t)
        break
    except Exception as e:
        print(enc, "failed:", e)
