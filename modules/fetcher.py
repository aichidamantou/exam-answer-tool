#!/usr/bin/env python3
"""
答案提取模块 — 独立模块，可被主程序调用或单独使用
"""
import re
from urllib.request import Request, urlopen, build_opener
import http.cookiejar


def fetch_page(pid: str, cookie: str) -> str:
    """请求 examshow 页面，返回 HTML"""
    cj = http.cookiejar.CookieJar()
    for item in cookie.split(";"):
        item = item.strip()
        if "=" in item:
            n, v = item.split("=", 1)
            cj.set_cookie(http.cookiejar.Cookie(
                version=0, name=n.strip(), value=v.strip(),
                port=None, port_specified=False, domain="sxvtc.cjnep.net",
                domain_specified=True, domain_initial_dot=False,
                path="/", path_specified=True, secure=False,
                expires=None, discard=False, comment=None, comment_url=None,
                rest={"HttpOnly": None}, rfc2109=False))
    op = build_opener(http.cookiejar.HTTPCookieProcessor(cj))
    r = Request(f"https://sxvtc.cjnep.net/lms/web/exam/examshow?pid={pid}")
    r.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                 "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
    r.add_header("Accept-Language", "zh-CN,zh;q=0.9")
    resp = op.open(r, timeout=30)
    return resp.read().decode("utf-8", errors="replace")


def parse_html(html: str) -> list:
    """解析 examshow HTML，返回答案列表 [{num, type, answer}]"""
    parts = re.split(r'data-qid=(\d+)', html)[1:]
    results = []
    for i in range(0, len(parts), 2):
        _, block = parts[i], parts[i+1]
        nm = re.search(r"eptimu_name[^>]*>\s*(\d+)", block)
        num = int(nm.group(1)) if nm else 0
        qt = "多选" if "data-type=2" in block[:300] else "单选"
        opts = re.findall(r'value="(\d+)"[^>]*/>([A-E]+)\.', block)
        vals = []
        for yb in re.findall(r'<div class="s_answer optiondiv">.*?</div>', block, re.DOTALL):
            if "exam-yes.png" in yb:
                vm = re.search(r'value="(\d+)"', yb)
                if vm:
                    vals.append(vm.group(1))
        letters = [o[1] for o in opts if o[0] in vals]
        results.append({"num": num, "type": qt, "answer": " ".join(letters)})
    results.sort(key=lambda x: x["num"])
    return results


def check_cookie(pid: str, cookie: str) -> bool:
    """验证 Cookie 是否有效"""
    try:
        h = fetch_page(pid, cookie)
        return "eptimu_name" in h
    except:
        return False


# 单独运行时测试
if __name__ == "__main__":
    import sys
    print("答案提取模块 - 独立测试")
    print("用法: python3 fetcher.py <PID> <COOKIE>")
    if len(sys.argv) >= 3:
        pid = sys.argv[1]
        ck = sys.argv[2]
        print(f"正在请求 PID={pid}...")
        html = fetch_page(pid, ck)
        results = parse_html(html)
        found = sum(1 for r in results if r["answer"])
        print(f"共 {len(results)} 题，提取 {found} 题")
        for r in results:
            a = r["answer"] if r["answer"] else "?"
            print(f"  第{r['num']:>2}题 [{r['type']}] {a}")
