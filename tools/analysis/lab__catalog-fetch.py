# -*- coding: utf-8 -*-
"""Microsoft Update Catalog 抓取工具
   search <query> [page]                  -> 列出结果
   links  <updateID> [rawfile]            -> 取下载直链
   注意：必须先请求 Home.aspx 暖场，否则 Search.aspx 只返回需要脚本的壳页。
"""
import sys, json, urllib.request, urllib.parse, http.cookiejar, re

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BASE = "https://www.catalog.update.microsoft.com/"

_cj = http.cookiejar.CookieJar()
_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))
_op.addheaders = [("User-Agent", UA),
                  ("Accept", "text/html,application/xhtml+xml,*/*;q=0.8"),
                  ("Accept-Language", "en-US,en;q=0.9")]
_warm = [False]


def _warmup():
    if not _warm[0]:
        _op.open(BASE + "Home.aspx", timeout=60).read()
        _warm[0] = True


def get(url, data=None, headers=None):
    _warmup()
    h = {}
    if headers:
        h.update(headers)
    if data is not None:
        data = data.encode("utf-8")
        h["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=h)
    with _op.open(req, timeout=90) as r:
        return r.read()


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    return " ".join(s.split())


def search(q, page=1):
    url = BASE + "Search.aspx?q=" + urllib.parse.quote(q) + "&p=" + str(page)
    raw = get(url).decode("utf-8", "replace")
    # 结果行：<tr id="<GUID>_R0"> ... <td id="<GUID>_Cn_R0">
    out = []
    for m in re.finditer(r'<tr[^>]*id="([0-9a-fA-F\-]{36})_R(\d+)"[^>]*>', raw):
        uid = m.group(1)
        start = m.end()
        nxt = raw.find("</tr>", start)
        body = raw[start:nxt if nxt > 0 else start + 8000]
        tds = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S | re.I)
        cells = [strip_tags(t) for t in tds]
        out.append({"uid": uid, "cells": cells})
    return out, raw


def links(uid):
    payload = "updateIDs=" + json.dumps(
        [{"size": 0, "updateID": uid, "uidInfo": uid}], separators=(",", ":"))
    raw = get(BASE + "DownloadDialog.aspx", data=payload,
              headers={"Referer": BASE + "Search.aspx"}).decode("utf-8", "replace")
    return re.findall(r'https?://[^"\']+?\.(?:cab|msu|exe|msix|zip)', raw, re.I), raw


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "search"
    if cmd == "search":
        q = sys.argv[2]
        page = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        rows, raw = search(q, page)
        print("query=%r page=%d rows=%d" % (q, page, len(rows)))
        for r in rows:
            c = r["cells"]
            title = c[1] if len(c) > 1 else ""
            print("%s | %-26s | %-9s | %-9s | %-9s | %s" %
                  (r["uid"], (c[2] if len(c) > 2 else "")[:26],
                   (c[3] if len(c) > 3 else "")[:9],
                   (c[4] if len(c) > 4 else "")[:9],
                   (c[5] if len(c) > 5 else "")[:9], title[:78]))
    elif cmd == "links":
        uid = sys.argv[2]
        ls, raw = links(uid)
        if len(sys.argv) > 3:
            open(sys.argv[3], "w", encoding="utf-8").write(raw)
        print("uid=%s links=%d" % (uid, len(ls)))
        for l in ls:
            print("  ", l)
