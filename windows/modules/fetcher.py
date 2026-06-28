#!/usr/bin/env python3
"""
答案提取模块 — 独立模块，可被主程序调用或单独使用
"""
import re
import http.cookiejar
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor


# ─── 浏览器标头解析 ───

HEADER_TEMPLATE = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "DNT": "1",
    "Priority": "u=0, i",
    "sec-ch-ua": '"Microsoft Edge";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}


def parse_headers_from_paste(raw_text: str) -> dict:
    """
    解析从浏览器 F12 复制的请求标头文本
    支持三种格式:
      1. key: value (Chrome/Firefox DevTools)
      2. key\\nvalue (Edge DevTools, key/value 分行)
      3. 纯 cookie 文本

    返回: {header_key: header_value, ...}
    """
    headers = {}
    cookie = ""
    lines = raw_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith(":"):
            continue

        # 跳过中文行（Edge 复制的"请求URL""请求方法""状态代码"等）
        if re.search(r'[一-鿿]', line) and ":" not in line:
            continue

        # 格式1: key: value
        m = re.match(r'^([a-zA-Z][a-zA-Z0-9_-]*)\s*:\s*(.*)', line)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip()
        else:
            # 格式2: 当前行是 key，下一行是 value（Edge 格式）
            if i < len(lines):
                next_line = lines[i].strip()
                if re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', line) and \
                   next_line and not next_line.startswith(":") and \
                   ":" not in next_line:
                    key = line
                    value = next_line
                    i += 1
                else:
                    continue
            else:
                continue

        key_lower = key.lower()

        if key_lower == "cookie":
            cookie = value
        elif key_lower in (
            "user-agent", "accept", "accept-language", "accept-encoding",
            "referer", "origin", "content-type", "dnt", "priority",
            "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
            "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site",
            "sec-fetch-user", "upgrade-insecure-requests",
            "x-requested-with",
        ):
            headers[key] = value
        elif key_lower in ("content-length", "host"):
            pass  # 自动生成，不保存

    # 补全默认标头
    for k, v in HEADER_TEMPLATE.items():
        if k not in headers:
            headers[k] = v

    return {"cookie": cookie, "headers": headers}


def make_request_headers(custom_headers: dict = None) -> dict:
    """
    生成用于 fetch_page 的请求标头
    """
    base = {
        "User-Agent": custom_headers.get("User-Agent", HEADER_TEMPLATE["User-Agent"]) if custom_headers else HEADER_TEMPLATE["User-Agent"],
        "Accept-Language": custom_headers.get("Accept-Language", HEADER_TEMPLATE["Accept-Language"]) if custom_headers else HEADER_TEMPLATE["Accept-Language"],
    }
    if custom_headers:
        for k in ("Accept", "Referer", "Origin", "Content-Type"):
            if k in custom_headers:
                base[k] = custom_headers[k]
    return base


def fetch_page(pid: str, cookie: str, base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=",
               browser_headers: dict = None) -> str:
    cj = http.cookiejar.CookieJar()
    cookie = cookie.replace("\n", "").replace("\r", "")
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
    op = build_opener(HTTPCookieProcessor(cj))
    r = Request(f"{base_url}{pid}")
    # 浏览器完整标头
    if browser_headers:
        for k, v in browser_headers.items():
            if k.lower() not in ("cookie", "content-length", "host"):
                r.add_header(k, v)
    else:
        r.add_header("User-Agent", HEADER_TEMPLATE["User-Agent"])
        r.add_header("Accept-Language", HEADER_TEMPLATE["Accept-Language"])
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
        qt = "多选" if "data-type=2" in block[:300] or block.count("exam-yes.png") > 1 else "单选"

        # 提取所有选项 (value + 选项文本)
        opts = re.findall(r'value="(\d+)"[^>]*/?>\s*([^<]{1,80}?)\s*</', block)

        # 提取正确答案的 value
        correct_vals = []
        for yb in re.findall(r'<div class="s_answer optiondiv">.*?</div>', block, re.DOTALL):
            if "exam-yes.png" in yb:
                vm = re.search(r'value="(\d+)"', yb)
                if vm:
                    correct_vals.append(vm.group(1))

        # 匹配正确答案文本
        answer_parts = [t for v, t in opts if v in correct_vals]

        # 如果是 ABCD 选项(有字母前缀)，用字母显示
        letter_opts = [(v, l) for v, l in re.findall(r'value="(\d+)"[^>]*/?>\s*([A-E]+)\.', block)]
        if letter_opts:
            letters = [l for v, l in letter_opts if v in correct_vals]
            if letters:
                answer_parts = letters

        results.append({"num": num, "type": qt, "answer": " ".join(answer_parts) if answer_parts else ""})
    results.sort(key=lambda x: x["num"])
    return results


def parse_exam_params(html: str) -> dict:
    """从 examshow HTML 中提取 template_pageid 和 course_id

    查找格式: exambegin('994','251') 或 data:{"template_pageid":994,"course_id":251}
    返回: {"template_pageid": "994", "course_id": "251"} 或 None
    """
    # 优先从 exambegin('xxx','yyy') 提取
    m = re.search(r"exambegin\s*\(\s*['\"](\d+)['\"]\s*,\s*['\"](\d+)['\"]", html)
    if m:
        return {"template_pageid": m.group(1), "course_id": m.group(2)}
    # 备选: 从 data:{"template_pageid":994,"course_id":251} 提取
    m = re.search(r'template_pageid["\']?\s*[:=]\s*["\']?(\d+)["\']?[^}]*course_id["\']?\s*[:=]\s*["\']?(\d+)', html)
    if m:
        return {"template_pageid": m.group(1), "course_id": m.group(2)}
    return {"template_pageid": "", "course_id": ""}


def fetch_and_parse(pid: str, cookie: str,
                    base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=",
                    browser_headers: dict = None) -> dict:
    """
    一步完成: 请求 examshow + 提取答案 + 提取 exam 参数

    browser_headers: 可选，从 F12 粘贴解析的浏览器完整标头

    返回: {
      "pid": str,           # 入参的 pid
      "total": int,         # 总题数
      "found": int,         # 提取到答案的题数
      "questions": list,    # parse_html 的返回 [{num, type, answer}]
      "template_pageid": str,
      "course_id": str,
    }
    """
    html = fetch_page(pid, cookie, base_url, browser_headers=browser_headers)
    questions = parse_html(html)
    params = parse_exam_params(html)
    found = sum(1 for q in questions if q["answer"])
    return {
        "pid": pid,
        "total": len(questions),
        "found": found,
        "questions": questions,
        "template_pageid": params.get("template_pageid", ""),
        "course_id": params.get("course_id", ""),
    }


def check_cookie(pid: str, cookie: str, base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=") -> bool:
    try:
        h = fetch_page(pid, cookie, base_url)
        return "eptimu_name" in h
    except:
        return False


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
