#!/usr/bin/env python3
"""
提交答案模块 — 自动答题/交卷流程
独立模块，可被主程序调用或单独使用
"""
import re, json, uuid, time, random, threading
import http.cookiejar
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler
from urllib.error import HTTPError

# 全局后台任务进度表
_jobs: dict = {}
_jobs_lock = threading.Lock()

def _job_id() -> str:
    return "gj_" + uuid.uuid4().hex[:12]

# ─── 完整浏览器标头（根据抓包还原） ───
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 Edg/149.0.0.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
              "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "sec-ch-ua": '"Microsoft Edge";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "DNT": "1",
    "Priority": "u=0, i",
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
}

# AJAX 请求额外标头
AJAX_EXTRA = {
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


def _merge_headers(base: dict, extra: dict = None) -> dict:
    """合并标头，extra 覆盖 base"""
    h = dict(base)
    if extra:
        h.update(extra)
    return h


def _make_opener(cookie_str: str):
    """构建带 cookie 的 opener"""
    cj = http.cookiejar.CookieJar()
    for item in cookie_str.replace("\n", "").replace("\r", "").split(";"):
        item = item.strip()
        if "=" not in item:
            continue
        n, v = item.split("=", 1)
        cj.set_cookie(http.cookiejar.Cookie(
            version=0, name=n.strip(), value=v.strip(),
            port=None, port_specified=False, domain="sxvtc.cjnep.net",
            domain_specified=True, domain_initial_dot=False,
            path="/", path_specified=True, secure=False,
            expires=None, discard=False, comment=None, comment_url=None,
            rest={"HttpOnly": None}, rfc2109=False))
    return build_opener(HTTPCookieProcessor(cj))
    cj = http.cookiejar.CookieJar()
    for item in cookie_str.replace("\n", "").replace("\r", "").split(";"):
        item = item.strip()
        if "=" not in item:
            continue
        n, v = item.split("=", 1)
        cj.set_cookie(http.cookiejar.Cookie(
            version=0, name=n.strip(), value=v.strip(),
            port=None, port_specified=False, domain="sxvtc.cjnep.net",
            domain_specified=True, domain_initial_dot=False,
            path="/", path_specified=True, secure=False,
            expires=None, discard=False, comment=None, comment_url=None,
            rest={"HttpOnly": None}, rfc2109=False))
    return build_opener(HTTPCookieProcessor(cj))


def parse_exam_questions(html: str) -> dict:
    """
    从 exambegin HTML 解析每题详细信息

    返回: {题号: {qid, type, opts: {字母: 值}}, ...}
      opts: {"A": "1", "B": "2", "C": "3", "D": "4"}
    """
    parts = re.split(r'data-qid=(\d+)', html)[1:]
    questions = {}
    for i in range(0, len(parts), 2):
        qid, block = parts[i], parts[i+1]
        nm = re.search(r"eptimu_name[^>]*>\s*(\d+)", block)
        num = int(nm.group(1)) if nm else 0
        qtype = "单选"
        # 多选题: type="checkbox" 或 data-type=2
        if 'type="checkbox"' in block[:500] or "data-type=2" in block[:300]:
            qtype = "多选"

        # 提取选项映射: 字母→value
        opts = {}
        for m in re.finditer(r'value="(\d+)"[^>]*/?>\s*([^<]{1,80}?)\s*</', block):
            val = m.group(1)
            text = m.group(2).strip()
            lm = re.match(r'^([A-E]+)\.', text)
            if lm:
                opts[lm.group(1)] = val
            else:
                opts[text] = val

        questions[num] = {"qid": qid, "type": qtype, "opts": opts}
    return questions


def parse_exam_result(html: str) -> dict:
    """
    解析 examshow 阅卷页，返回批改统计

    返回: {correct, wrong, correct_partial, unanswered, total, score_str}
    """
    result = {}
    # 正确：<font color="#59C75C">6</font>题
    m = re.search(r'正确[：:].*?<font[^>]*>(\d+)</font>', html)
    result["correct"] = int(m.group(1)) if m else 0
    # 部分正确
    m = re.search(r'部分正确[：:].*?<font[^>]*>(\d+)</font>', html)
    result["correct_partial"] = int(m.group(1)) if m else 0
    # 错误
    m = re.search(r'错误[：:].*?<font[^>]*>(\d+)</font>', html)
    result["wrong"] = int(m.group(1)) if m else 0
    # 未做
    m = re.search(r'未做[：:].*?<font[^>]*>(\d+)</font>', html)
    result["unanswered"] = int(m.group(1)) if m else 0
    result["total"] = result.get("correct", 0) + result.get("correct_partial", 0) + \
                      result.get("wrong", 0) + result.get("unanswered", 0)

    # 已答（考试记录表用了 answered-check.png）
    answered = re.findall(r'answered-check\.png', html)
    result["answered_display"] = len(answered)

    return result


def start_exam(cookie: str, template_pageid: str, course_id: str,
               base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=",
               browser_headers: dict = None) -> dict:
    """
    开始一次新的答题，执行 chk-hw-cando → gettemplatepage → exambegin

    browser_headers: 可选，从 F12 粘贴解析的完整浏览器标头

    返回: {success, page_id, exam_html, questions, total, msg, _opener}
      questions: parse_exam_questions() 的返回格式
      _opener: 内部使用，供 submit_answers 传入
    """
    h = browser_headers if browser_headers else {}
    opener = _make_opener(cookie)
    headers = _merge_headers(BROWSER_HEADERS, {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": "https://sxvtc.cjnep.net",
        "Referer": "https://sxvtc.cjnep.net/lms/web/exam/index",
    })
    # 传入的 browser_headers 覆盖
    if h:
        for k in ("User-Agent", "Accept-Language", "sec-ch-ua", "sec-ch-ua-mobile",
                   "sec-ch-ua-platform", "DNT", "Priority"):
            if k in h:
                headers[k] = h[k]

    try:
        # 步骤 1: chk-hw-cando
        req = Request("https://sxvtc.cjnep.net/lms/web/onlineexam/chk-hw-cando",
                      data=f"template_pageid={template_pageid}".encode(),
                      headers=headers)
        resp = opener.open(req, timeout=15)
        j1 = json.loads(resp.read().decode())

        # 步骤 2: gettemplatepage → 获取 page_id
        req2 = Request("https://sxvtc.cjnep.net/lms/web/onlineexam/gettemplatepage",
                       data=f"template_pageid={template_pageid}&course_id={course_id}".encode(),
                       headers=headers)
        resp2 = opener.open(req2, timeout=15)
        j2 = json.loads(resp2.read().decode())

        page_id = str(j2.get("page_id", ""))
        if not page_id:
            return {"success": False, "msg": "gettemplatepage 未返回 page_id", "detail": j2}

        # 步骤 3: exambegin
        exam_url = f"https://sxvtc.cjnep.net/lms/web/onlineexam/exambegin" \
                   f"?course_id={course_id}&page_id={page_id}&template_pageid={template_pageid}"
        req3 = Request(exam_url, headers=_merge_headers(BROWSER_HEADERS, {
            "Referer": "https://sxvtc.cjnep.net/lms/web/exam/index",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }))
        resp3 = opener.open(req3, timeout=15)
        exam_html = resp3.read().decode("utf-8", errors="replace")

        if "eptimu_name" not in exam_html:
            return {"success": False, "msg": "exam 页面无题目内容", "exam_html": exam_html[:500]}

        questions = parse_exam_questions(exam_html)
        return {"success": True, "page_id": page_id, "exam_html": exam_html,
                "questions": questions, "total": len(questions),
                "_opener": opener,
                "msg": f"成功获取试卷，共 {len(questions)} 题"}

    except Exception as e:
        return {"success": False, "msg": f"启动考试失败: {str(e)[:100]}"}


def submit_answers(cookie: str, page_id: str, course_id: str, template_pageid: str,
                   questions: dict, answers: dict,
                   exam_referer: str = None,
                   _opener=None) -> dict:
    """
    提交答案（subexamnew 交卷）

    参数:
      questions: parse_exam_questions() 返回的题目信息
      answers:  {题号: "A"} 或 {题号: "A C"}（多选用空格分隔字母）
      _opener:  内部使用，传入已有的 opener 避免重建

    返回: {success, new_pid, msg}
    """
    opener = _opener if _opener else _make_opener(cookie)

    # 构建 exam_referer
    if not exam_referer:
        exam_referer = f"https://sxvtc.cjnep.net/lms/web/onlineexam/exambegin" \
                       f"?course_id={course_id}&page_id={page_id}&template_pageid={template_pageid}"

    # 构建 multipart body
    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex[:24]
    parts_body = []

    # page_id
    parts_body.append(f'--{boundary}\r\n'
                      f'Content-Disposition: form-data; name="page_id"\r\n\r\n'
                      f'{page_id}')

    # act
    parts_body.append(f'--{boundary}\r\n'
                      f'Content-Disposition: form-data; name="act"\r\n\r\n'
                      f'subexam')

    # 已答题
    answered_count = 0
    for num in sorted(answers.keys(), key=int):
        qinfo = questions.get(int(num))
        if not qinfo:
            continue
        qid = qinfo["qid"]
        qtype = qinfo["type"]
        opts_rev = {v: k for k, v in qinfo["opts"].items()}  # value→letter

        raw_answer = answers[num]
        # 解析回答中的字母
        selected_letters = raw_answer.strip().split()
        for letter in selected_letters:
            val = qinfo["opts"].get(letter)
            if not val:
                continue
            if qtype == "多选":
                parts_body.append(f'--{boundary}\r\n'
                                  f'Content-Disposition: form-data; name="question{qid}[]"\r\n\r\n'
                                  f'{val}')
            else:
                parts_body.append(f'--{boundary}\r\n'
                                  f'Content-Disposition: form-data; name="question{qid}"\r\n\r\n'
                                  f'{val}')
        if selected_letters:
            answered_count += 1

    # 未答题列表（题号）
    empty_nums = [str(n) for n in sorted(questions.keys(), key=int)
                  if n not in answers or not answers[n].strip()]
    if empty_nums:
        parts_body.append(f'--{boundary}\r\n'
                          f'Content-Disposition: form-data; name="empty_que"\r\n\r\n'
                          f'{",".join(empty_nums)}')

    parts_body.append(f'--{boundary}--')
    body_data = "\r\n".join(parts_body).encode("utf-8")

    # 发送 subexamnew
    sub_headers = _merge_headers(BROWSER_HEADERS, {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Referer": exam_referer,
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
    })

    # 用同一个 opener 提交，让 urllib 自动处理 302 跳转
    try:
        req = Request("https://sxvtc.cjnep.net/lms/web/onlineexam/subexamnew",
                      data=body_data, headers=sub_headers)
        resp = opener.open(req, timeout=30)
        final_url = resp.geturl()
        if "examshow" in final_url:
            new_pid = final_url.split("pid=")[-1].split("&")[0]
            return {"success": True, "new_pid": new_pid,
                    "answered": answered_count, "total": len(questions),
                    "msg": f"交卷成功！PID={new_pid}"}
        # 没有跳转到 examshow（比如跳到了首页）
        body = resp.read().decode("utf-8", errors="replace")[:300]
        return {"success": False, "msg": f"交卷后跳转至 {final_url}", "body": body}

    except HTTPError as e:
        location = e.headers.get("Location", "")
        if e.code in (301, 302) and "examshow" in location:
            new_pid = location.split("pid=")[-1].split("&")[0]
            return {"success": True, "new_pid": new_pid,
                    "answered": answered_count, "total": len(questions),
                    "msg": f"交卷成功！PID={new_pid}"}
        body = e.read().decode("utf-8", errors="replace")[:200]
        return {"success": False, "msg": f"HTTP {e.code}: {body}"}

    except Exception as e:
        return {"success": False, "msg": f"交卷失败: {str(e)[:100]}"}


def check_pid_match(expected_pid: str, template_pageid: str, course_id: str,
                    cookie: str, base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=",
                    browser_headers: dict = None) -> dict:
    """
    校验答案来源 PID 的 template_pageid/course_id 是否与提交配置一致

    返回: {"ok": bool, "msg": str}
    """
    from .fetcher import fetch_and_parse
    try:
        result = fetch_and_parse(expected_pid, cookie, base_url, browser_headers=browser_headers)
        actual_tpid = result.get("template_pageid", "")
        actual_cid = result.get("course_id", "")
        if not actual_tpid or not actual_cid:
            return {"ok": False, "msg": f"PID={expected_pid} 页面未找到 template_pageid/course_id"}
        if actual_tpid != template_pageid or actual_cid != course_id:
            return {
                "ok": False,
                "msg": f"PID={expected_pid} 的参数不匹配: "
                       f"答案页 template_pageid={actual_tpid}, course_id={actual_cid}；"
                       f"提交模板 template_pageid={template_pageid}, course_id={course_id}",
            }
        return {"ok": True, "msg": f"PID={expected_pid} 校验通过"}
    except Exception as e:
        return {"ok": False, "msg": f"校验失败: {str(e)[:60]}"}


def submit_exam(cookie: str, template_pageid: str, course_id: str,
                answers: dict, expected_pid: str = None,
                base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=",
                browser_headers: dict = None) -> dict:
    """
    一键开始答题 + 提交答案 + 交卷

    answers: {题号: "A"} 或 {题号: "A C"}（多选用空格分隔字母）
    expected_pid: 可选，答案来源 PID，传入后会校验其 template_pageid/course_id 是否匹配
    browser_headers: 可选，从 F12 粘贴解析的浏览器完整标头，传入后覆盖默认标头

    返回: {success, new_pid, page_id, total, answered, result, msg}
    """
    # 如有 expected_pid，校验参数一致性
    if expected_pid:
        check = check_pid_match(expected_pid, template_pageid, course_id, cookie, base_url,
                                     browser_headers=browser_headers)
        if not check["ok"]:
            return {**check, "success": False, "expected_pid": expected_pid}

    # 开始考试
    start = start_exam(cookie, template_pageid, course_id, base_url, browser_headers=browser_headers)
    if not start["success"]:
        return start

    # 提交答案（传入 _opener 复用连接和 cookie）
    submit = submit_answers(cookie, start["page_id"], course_id, template_pageid,
                            start["questions"], answers,
                            _opener=start.get("_opener"))
    if not submit["success"]:
        return submit

    submit["questions"] = start["questions"]
    submit["page_id"] = start["page_id"]
    return submit


# ─── 随机答题 ───

def generate_random_answers(questions: dict) -> dict:
    """
    根据题目类型生成随机答案

    questions: parse_exam_questions() 的返回
    返回: {题号: "A"} 或 {题号: "A C"}（多选用空格分隔字母）
    """
    import random
    answers = {}
    for num, q in questions.items():
        opts_keys = list(q["opts"].keys())
        if not opts_keys:
            continue
        if q["type"] == "多选":
            # 多选题随机选 1～全部选项
            count = random.randint(1, len(opts_keys))
            chosen = random.sample(opts_keys, count)
            answers[num] = " ".join(sorted(chosen))
        else:
            # 单选/判断: 随机选一个
            answers[num] = random.choice(opts_keys)
    return answers


def random_exam(cookie: str, template_pageid: str, course_id: str,
                base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=",
                browser_headers: dict = None) -> dict:
    """
    随机答题测试:
      1. 开始考试 (start_exam)
      2. 生成随机答案 (generate_random_answers)
      3. 提交交卷 (submit_answers)

    返回: submit_exam 的返回格式
    """
    start = start_exam(cookie, template_pageid, course_id, base_url, browser_headers=browser_headers)
    if not start["success"]:
        return start

    answers = generate_random_answers(start["questions"])
    submit = submit_answers(cookie, start["page_id"], course_id, template_pageid,
                            start["questions"], answers,
                            _opener=start.get("_opener"))
    if not submit["success"]:
        return submit

    submit["questions"] = start["questions"]
    submit["page_id"] = start["page_id"]
    return submit


def random_gradual_exam(cookie: str, template_pageid: str, course_id: str,
                         base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=",
                         browser_headers: dict = None) -> dict:
    """
    随机答题测试(逐题间隔版):
      1. start_exam → 2. generate_random_answers → 3. 逐题 setanswer → subexamnew

    返回: {success, job_id, page_id, total, msg}
    """
    start = start_exam(cookie, template_pageid, course_id, base_url, browser_headers=browser_headers)
    if not start["success"]:
        return start

    answers = generate_random_answers(start["questions"])
    exam_referer = f"https://sxvtc.cjnep.net/lms/web/onlineexam/exambegin" \
                   f"?course_id={course_id}&page_id={start['page_id']}&template_pageid={template_pageid}"

    job_id = start_gradual_submit(cookie, template_pageid, course_id,
                                   start["questions"], answers,
                                   start["page_id"], exam_referer,
                                   base_url, browser_headers)

    return {
        "success": True,
        "job_id": job_id,
        "page_id": start["page_id"],
        "total": len(start["questions"]),
        "answered": len(answers),
        "msg": f"随机逐题答题已启动 (job_id={job_id})",
    }


# ─── 逐题间隔答题 ───

def get_job_status(job_id: str) -> dict:
    """查询后台任务进度"""
    with _jobs_lock:
        return _jobs.get(job_id, {"status": "unknown", "msg": "任务不存在"})


def cancel_job(job_id: str) -> bool:
    """取消任务"""
    with _jobs_lock:
        if job_id in _jobs and _jobs[job_id]["status"] in ("starting", "answering"):
            _jobs[job_id]["status"] = "cancelled"
            return True
    return False


def _run_gradual(job_id: str, cookie: str, tpid: str, cid: str,
                 questions: dict, answers: dict,
                 page_id: str, exam_referer: str,
                 base_url: str, bh: dict):
    """后台线程：逐题 setanswer → 全部完成后 subexamnew"""
    opener = _make_opener(cookie)
    ajax_h = _merge_headers(BROWSER_HEADERS, {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": "https://sxvtc.cjnep.net",
        "Referer": exam_referer,
    })
    if bh:
        for k in ("User-Agent", "Accept-Language", "sec-ch-ua", "sec-ch-ua-platform", "DNT", "Priority"):
            if k in bh: ajax_h[k] = bh[k]

    total = len(questions)
    completed = 0
    setanswer_ok = True
    answered_keys = sorted(answers.keys(), key=int)
    empty_nums = [str(n) for n in sorted(questions.keys(), key=int)
                  if n not in answers or not answers[n].strip()]

    for idx, num in enumerate(answered_keys):
        with _jobs_lock:
            if _jobs.get(job_id, {}).get("status") == "cancelled":
                return
        q = questions.get(int(num))
        if not q: continue
        raw_answer = answers[num]
        vals = [q["opts"].get(l) for l in raw_answer.strip().split() if q["opts"].get(l)]
        if not vals: continue

        try:
            opener.open(Request(
                "https://sxvtc.cjnep.net/lms/web/exam/setanswer",
                data=f"i={q['qid']}&answer={vals[0]}&page_id={page_id}&sqtnum={total}".encode(),
                headers=ajax_h), timeout=15)
        except Exception as e:
            setanswer_ok = False

        completed += 1
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "answering",
                "total": total, "completed": completed,
                "current_num": num, "answer": raw_answer,
                "setanswer_ok": setanswer_ok,
            }

        # 非最后一题则等待 10-20 秒
        if idx < len(answered_keys) - 1:
            delay = random.randint(10, 20)
            for _ in range(delay):
                time.sleep(1)
                with _jobs_lock:
                    if _jobs.get(job_id, {}).get("status") == "cancelled":
                        return

    # subexamnew 交卷
    boundary = "----" + uuid.uuid4().hex[:24]
    parts = []
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"page_id\"\r\n\r\n{page_id}")
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"act\"\r\n\r\nsubexam")

    for num in sorted(questions.keys(), key=int):
        qinfo = questions.get(int(num))
        raw_answer = answers.get(num, "")
        if not raw_answer.strip(): continue
        for letter in raw_answer.strip().split():
            val = qinfo["opts"].get(letter)
            if val is None: continue
            nm = f"question{qinfo['qid']}[]" if qinfo["type"] == "多选" else f"question{qinfo['qid']}"
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{nm}\"\r\n\r\n{val}")

    if empty_nums:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"empty_que\"\r\n\r\n{','.join(empty_nums)}")
    parts.append(f"--{boundary}--")
    body_data = "\r\n".join(parts).encode("utf-8")

    sub_h = _merge_headers(BROWSER_HEADERS, {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Referer": exam_referer,
    })

    try:
        resp = opener.open(Request(
            "https://sxvtc.cjnep.net/lms/web/onlineexam/subexamnew",
            data=body_data, headers=sub_h), timeout=30)
        fu = resp.geturl()
        if "examshow" in fu:
            new_pid = fu.split("pid=")[-1].split("&")[0]
            from .fetcher import fetch_page
            show_html = fetch_page(new_pid, cookie, base_url, browser_headers=bh)
            grade = parse_exam_result(show_html)
            with _jobs_lock:
                _jobs[job_id] = {
                    "status": "done", "total": total, "completed": completed,
                    "new_pid": new_pid, "result": grade,
                    "msg": f"交卷成功! PID={new_pid}",
                }
        else:
            with _jobs_lock:
                _jobs[job_id] = {"status": "error", "msg": f"跳转至 {fu}"}
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id] = {"status": "error", "msg": f"交卷失败: {str(e)[:80]}"}


def start_gradual_submit(cookie: str, tpid: str, cid: str,
                          questions: dict, answers: dict,
                          page_id: str, exam_referer: str,
                          base_url: str = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=",
                          bh: dict = None) -> str:
    job_id = _job_id()
    with _jobs_lock:
        _jobs[job_id] = {"status": "starting", "total": len(questions), "completed": 0}
    t = threading.Thread(target=_run_gradual,
                         args=(job_id, cookie, tpid, cid, questions, answers,
                               page_id, exam_referer, base_url, bh),
                         daemon=True)
    t.start()
    return job_id


if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("提交答案模块 - 独立测试")
    print("用法: python3 submitter.py <template_pageid> <course_id> [answers...]")
    print("示例: python3 submitter.py 986 272 1=A 2=B 3=C")
    print()

    config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    cookie_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookie.txt")

    config = json.load(open(config_file))
    cookie = open(cookie_file).read().strip().split("\n")[0]

    tpid = config.get("template_pageid", "")
    cid = config.get("course_id", "")

    if len(sys.argv) >= 3:
        tpid = sys.argv[1]
        cid = sys.argv[2]

    if not tpid or not cid:
        print("❌ 请在 config.json 中配置 template_pageid 和 course_id")
        sys.exit(1)

    # 从命令行解析答案
    answers = {}
    for arg in sys.argv[3:]:
        parts = arg.split("=", 1)
        if len(parts) == 2:
            answers[int(parts[0])] = parts[1].strip()

    if not answers:
        print("⚠️  未指定答案，将交空卷")
    else:
        print(f"📋 准备提交答案: {answers}")
        print(f"   共 {len(answers)} 题")
        for n, a in sorted(answers.items()):
            print(f"     第{n:>2}题 → {a}")

    print(f"\n🚀 template_pageid={tpid}, course_id={cid}")
    print("---")

    result = submit_exam(cookie, tpid, cid, answers)
    print(f"\n结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
