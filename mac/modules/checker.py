#!/usr/bin/env python3
"""
PID 检测模块 — 验证试卷是否可访问、获取基本信息
独立模块，可被主程序调用或单独使用
"""
import re
from urllib.request import Request, urlopen, build_opener, HTTPCookieProcessor
import http.cookiejar


def check_pid(pid: str, cookie: str, base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=",
              browser_headers: dict = None) -> dict:
    """
    检测 PID 是否有效，返回试卷信息
    返回: {"ok": bool, "title": str, "total": int, "type": str, "msg": str}
    """
    cookie = cookie.replace("\n", "").replace("\r", "")
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
    op = build_opener(HTTPCookieProcessor(cj))
    r = Request(f"{base_url}{pid}")
    if browser_headers:
        for k, v in browser_headers.items():
            if k.lower() not in ("cookie", "content-length", "host"):
                r.add_header(k, v)
    else:
        r.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
        r.add_header("Accept-Language", "zh-CN,zh;q=0.9")

    try:
        resp = op.open(r, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "title": "", "total": 0, "type": "", "msg": f"请求失败: {str(e)[:50]}"}

    if len(html) < 200:
        return {"ok": False, "title": "", "total": 0, "type": "", "msg": "页面内容过短，Cookie 可能过期"}

    # 提取试卷标题（从面包屑导航）
    title = ""
    tm = re.search(r'ep_sign[^>]*>.*?练习[：:]\s*([^<]{4,80})', html)
    if tm:
        title = tm.group(1).strip()
    if not title:
        tm = re.search(r'<title>([^<]+)</title>', html)
        if tm:
            title = tm.group(1).strip()

    # 统计题目数
    qids = re.findall(r'data-qid=(\d+)', html)
    total = len(set(qids))

    # 检测题目类型分布
    single = 0
    multi = 0
    for qid in set(qids):
        idx = html.find(f"data-qid={qid}")
        block = html[idx:idx+500] if idx >= 0 else ""
        if "data-type=2" in block[:200]:
            multi += 1
        else:
            single += 1

    # 检测 exam-yes.png 数量（已答对题数）
    yes_count = html.count("exam-yes.png")

    # 检测题型（单选/多选/判断）
    types_found = set()
    for qid in list(set(qids))[:10]:  # 抽检前10题判断题型
        idx = html.find(f"data-qid={qid}")
        block = html[idx:idx+500] if idx >= 0 else ""

        if "data-type=2" in block[:200]:
            types_found.add("多选")
            continue

        # 判断是否有 A. B. 等字母选项
        if re.search(r'/>([A-E])\.', block):
            types_found.add("单选")
            continue

        # 否则可能是判断题
        if re.search(r'value="\d+"[^>]*/?>\s*(对|错|正确|错误|√|×)', block):
            types_found.add("判断")
            continue

    types_str = " + ".join(sorted(types_found)) if types_found else "未知"

    msg = f"共 {total} 题"
    if single:
        msg += f"，单选 {single} 题"
    if multi:
        msg += f"，多选 {multi} 题"

    if yes_count > 0:
        msg += f"，已答 {yes_count} 题"

    return {
        "ok": True,
        "title": title or f"PID-{pid}",
        "total": total,
        "type": types_str,
        "single": single,
        "multi": multi,
        "answered": yes_count,
        "msg": msg,
        "pid": pid,
    }


if __name__ == "__main__":
    import sys
    print("PID 检测模块 - 独立测试")
    print("用法: python3 checker.py <PID> <COOKIE>")
    if len(sys.argv) >= 3:
        result = check_pid(sys.argv[1], sys.argv[2])
        print(f"\n检测结果:")
        for k, v in result.items():
            print(f"  {k}: {v}")
