#!/usr/bin/env python3
"""
考试答题工具 - 原生窗口版
HTML 渲染界面，原生窗口显示（不跳转浏览器）
"""
import sys, os, json, threading, datetime, re, traceback, subprocess
from pathlib import Path

# ─── 自动引导 pip（处理 embed Python 无 pip 的情况） ───
def _ensure_pip(force=False):
    """确保 pip 可用：删除 ._pth + 安装 pip"""
    app_dir = Path(__file__).parent
    for pth in app_dir.glob("**/python*._pth"):
        try:
            pth.unlink()
        except:
            pass
    if not force:
        try:
            __import__("pip")
            return True
        except ImportError:
            pass
    # 下载 get-pip.py 并执行
    import urllib.request
    try:
        print("[pip] 下载 get-pip.py ...")
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py",
                                   app_dir / "get-pip.py")
        subprocess.check_call([sys.executable, str(app_dir / "get-pip.py"), "-q"])
        (app_dir / "get-pip.py").unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"[pip] 安装 pip 失败: {e}")
        return False

# ─── 启动时自动安装缺失依赖 ───
def _install_deps():
    _MISSING = []
    for _mod in ("webview",):
        try:
            __import__(_mod)
        except ImportError:
            _MISSING.append(_mod)
    if not _MISSING:
        return True
    print(f"[安装] 缺失依赖: {_MISSING}")
    _ensure_pip()
    # 先确保 setuptools 可用（pywebview 构建需要）
    for _pre in ("setuptools", "wheel"):
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--upgrade", _pre,
                 "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "-q"]
            )
        except:
            pass
    ok = True
    for dep in _MISSING:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", dep,
                 "-i", "https://pypi.tuna.tsinghua.edu.cn/simple", "-q"]
            )
            __import__(dep.replace("-", "_"))
            print(f"  ✅ {dep}")
        except Exception as e:
            print(f"  ❌ {dep} 安装失败: {e}")
            ok = False
    return ok

_install_deps()

# ─── 全局异常捕获 ───
def _global_excepthook(exc_type, exc_value, exc_traceback):
    try:
        log_path = Path(__file__).parent / "exam_tool.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] UNHANDLED ERROR:\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
            f.write("\n")
    except:
        traceback.print_exception(exc_type, exc_value, exc_traceback)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, str(exc_value), "程序错误", 0x10)
    except:
        pass

sys.excepthook = _global_excepthook

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules.fetcher import fetch_page, parse_html, check_cookie, parse_exam_params, fetch_and_parse, parse_headers_from_paste
from modules.submitter import submit_exam, parse_exam_result, random_exam, random_gradual_exam, get_job_status, start_gradual_submit
from modules.checker import check_pid

APP_DIR = Path(__file__).parent
LOG_FILE = APP_DIR / "exam_tool.log"
CONFIG_FILE = APP_DIR / "config.json"

cookie_str = ""
pid_val = ""
template_pageid = ""
course_id = ""
stored_answers = []  # [{num, type, answer}] from fetch
browser_headers = {}  # 解析后的浏览器完整标头（不含 cookie）
getanserurl = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid="
COOKIE_FILE = APP_DIR / "cookie.txt"
HEADERS_FILE = APP_DIR / "headers.txt"

def load_config():
    global cookie_str, pid_val, getanserurl, template_pageid, course_id, browser_headers
    try:
        if CONFIG_FILE.exists():
            d = json.load(open(CONFIG_FILE, encoding="utf-8"))
            pid_val = d.get("pid", "")
            getanserurl = d.get("getanserurl", "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=")
            template_pageid = d.get("template_pageid", "")
            course_id = d.get("course_id", "")
    except: pass
    try:
        if COOKIE_FILE.exists():
            cookie_str = open(COOKIE_FILE, encoding="utf-8").read().strip()
    except: pass
    # 启动时自动从 headers.txt 恢复标头
    try:
        if HEADERS_FILE.exists():
            raw = open(HEADERS_FILE, encoding="utf-8").read().strip()
            if raw:
                parsed = parse_headers_from_paste(raw)
                if parsed.get("cookie"):
                    cookie_str = parsed["cookie"]
                if parsed.get("headers"):
                    browser_headers = parsed["headers"]
    except: pass

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "pid": pid_val,
                "getanserurl": getanserurl,
                "template_pageid": template_pageid,
                "course_id": course_id,
            }, f, ensure_ascii=False, indent=2)
    except: pass
    try:
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(cookie_str)
    except: pass

# ─── HTTP API ───
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

api_server = None

class ApiHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global cookie_str, pid_val, getanserurl, template_pageid, course_id, browser_headers
        u = urlparse(self.path)
        if u.path == '/api/check':
            q = parse_qs(u.query)
            pid = q.get('pid', [''])[0]
            ck = q.get('cookie', [''])[0]
            try:
                result = check_pid(pid, ck, getanserurl,
                                    browser_headers=browser_headers if browser_headers else None)
                # PID 检测通过后更新全局参数并保存 config
                if result.get("ok", False):
                    pid_val = pid
                    # 顺便提取 template_pageid/course_id
                    try:
                        h = fetch_page(pid, ck, getanserurl,
                                       browser_headers=browser_headers if browser_headers else None)
                        params = parse_exam_params(h)
                        if params.get("template_pageid"):
                            template_pageid = params["template_pageid"]
                            course_id = params["course_id"]
                    except: pass
                    try:
                        with open(CONFIG_FILE, encoding="utf-8") as f:
                            d = json.load(f)
                        d["pid"] = pid
                        if template_pageid:
                            d["template_pageid"] = template_pageid
                            d["course_id"] = course_id
                        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                            json.dump(d, f, ensure_ascii=False, indent=2)
                    except: pass
                self._json(result)
            except Exception as e:
                self._json({"ok": False, "msg": str(e)[:50]})
        elif u.path == '/api/fetch':
            q = parse_qs(u.query)
            request_pid = q.get('pid', [''])[0]
            ck = q.get('cookie', [''])[0]
            try:
                data = fetch_and_parse(request_pid, ck, getanserurl,
                                       browser_headers=browser_headers if browser_headers else None)
                txt = ""
                for r in data["questions"]:
                    a = r["answer"] if r["answer"] else "?"
                    txt += f"第{r['num']:>2}题 [{r['type']}] {a}\n"
                # 提取 template_pageid + course_id 并写入 config
                template_pageid_saved = data.get("template_pageid", "")
                course_id_saved = data.get("course_id", "")
                if template_pageid_saved and course_id_saved:
                    template_pageid = template_pageid_saved
                    course_id = course_id_saved
                    global stored_answers
                    stored_answers = data["questions"]
                cookie_str = ck; pid_val = request_pid; save_config()
                self._json({
                    "found": data["found"], "total": data["total"], "text": txt,
                    "template_pageid": template_pageid,
                    "course_id": course_id,
                })
            except Exception as e:
                self._json({"error": str(e)[:60]})
        elif u.path == '/api/config':
            # 检查 headers.txt 是否存在，返回原始文本供输入框回填
            headers_raw = ""
            try:
                if HEADERS_FILE.exists():
                    headers_raw = open(HEADERS_FILE, encoding="utf-8").read().strip()
            except: pass
            self._json({"cookie": cookie_str, "pid": pid_val, "getanserurl": getanserurl,
                        "template_pageid": template_pageid, "course_id": course_id,
                        "headers_raw": headers_raw, "has_headers": len(browser_headers) > 0})
        elif u.path == '/api/save':
            length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(length).decode('utf-8') if length else ''
            if body:
                try: d = json.loads(body); cookie_str = d.get('cookie',''); pid_val = d.get('pid','')
                except: pass
            else:
                q = parse_qs(u.query)
                cookie_str = q.get('cookie', [''])[0]
                pid_val = q.get('pid', [''])[0]
            save_config()
            self._text("saved")
        else:
            self._text("ok")
    def do_POST(self):
        global cookie_str, pid_val, getanserurl, template_pageid, course_id, stored_answers, browser_headers
        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else '{}'
        u = urlparse(self.path)

        if u.path == '/api/parse_headers':
            try:
                d = json.loads(body)
                raw = d.get("text", "")
                if not raw:
                    self._json({"success": False, "msg": "未提供标头文本"})
                    return
                parsed = parse_headers_from_paste(raw)
                cookie = parsed.get("cookie", "")
                hdrs = parsed.get("headers", {})
                global browser_headers
                browser_headers = hdrs
                if cookie:
                    cookie_str = cookie
                # 1. 原始完整标头写入 headers.txt
                try:
                    with open(HEADERS_FILE, "w", encoding="utf-8") as f:
                        f.write(raw.strip())
                except: pass
                # 2. cookie 写入 cookie.txt
                save_config()
                self._json({
                    "success": True,
                    "has_cookie": bool(cookie),
                    "has_headers": len(hdrs),
                    "cookie_preview": cookie[:60] + "..." if len(cookie) > 60 else cookie,
                    "headers_keys": list(hdrs.keys()),
                    "saved_to": "headers.txt + cookie.txt",
                })
            except Exception as e:
                self._json({"success": False, "msg": f"解析失败: {str(e)[:60]}"})
        elif u.path == '/api/submit':
            try:
                d = json.loads(body)
                tpid = d.get("template_pageid", template_pageid)
                cid = d.get("course_id", course_id)
                ck = d.get("cookie", cookie_str)
                # 从请求体或 stored_answers 获取答案
                raw_answers = d.get("answers", None)
                if raw_answers:
                    answers = {int(k): v for k, v in raw_answers.items()}
                elif stored_answers:
                    answers = {q["num"]: q["answer"] for q in stored_answers if q["answer"]}
                else:
                    self._json({"success": False, "msg": "没有答案数据，请先提取答案"})
                    return

                if not tpid or not cid:
                    self._json({"success": False, "msg": "缺少 template_pageid/course_id，请先提取答案"})
                    return

                # 开始答题并提交（如有浏览器标头则传入）
                result = submit_exam(ck, tpid, cid, answers,
                                     expected_pid=pid_val, base_url=getanserurl,
                                     browser_headers=browser_headers if browser_headers else None)
                # 如果成功，顺便获取批改结果
                if result.get("success") and result.get("new_pid"):
                    try:
                        show_html = fetch_page(result["new_pid"], ck, getanserurl,
                                               browser_headers=browser_headers if browser_headers else None)
                        grade = parse_exam_result(show_html)
                        result["result"] = grade
                    except:
                        pass
                self._json(result)
            except Exception as e:
                self._json({"success": False, "msg": f"提交失败: {str(e)[:100]}"})
        elif u.path == '/api/random_exam':
            try:
                d = json.loads(body)
                tpid = d.get("template_pageid", template_pageid)
                cid = d.get("course_id", course_id)
                ck = d.get("cookie", cookie_str)
                if not tpid or not cid:
                    self._json({"success": False, "msg": "缺少 template_pageid/course_id，请先提取答案"})
                    return
                result = random_exam(ck, tpid, cid,
                                     base_url=getanserurl,
                                     browser_headers=browser_headers if browser_headers else None)
                if result.get("success") and result.get("new_pid"):
                    try:
                        show_html = fetch_page(result["new_pid"], ck, getanserurl,
                                               browser_headers=browser_headers if browser_headers else None)
                        grade = parse_exam_result(show_html)
                        result["result"] = grade
                    except:
                        pass
                self._json(result)
            except Exception as e:
                self._json({"success": False, "msg": f"随机答题失败: {str(e)[:100]}"})
        elif u.path == '/api/gradual_submit':
            try:
                d = json.loads(body)
                tpid = d.get("template_pageid", template_pageid)
                cid = d.get("course_id", course_id)
                ck = d.get("cookie", cookie_str)
                if not tpid or not cid:
                    self._json({"success": False, "msg": "缺少 template_pageid/course_id"})
                    return

                # 从 stored_answers 取答案
                if not stored_answers:
                    self._json({"success": False, "msg": "请先提取答案"})
                    return
                answers = {q["num"]: q["answer"] for q in stored_answers if q["answer"]}

                start = __import__('modules.submitter', fromlist=['start_exam']).start_exam(
                    ck, tpid, cid, getanserurl, browser_headers=browser_headers if browser_headers else None)
                if not start["success"]:
                    self._json(start)
                    return

                exam_referer = f"https://sxvtc.cjnep.net/lms/web/onlineexam/exambegin" \
                               f"?course_id={cid}&page_id={start['page_id']}&template_pageid={tpid}"

                job_id = start_gradual_submit(ck, tpid, cid,
                                               start["questions"], answers,
                                               start["page_id"], exam_referer,
                                               getanserurl,
                                               browser_headers if browser_headers else None)
                self._json({
                    "success": True,
                    "job_id": job_id,
                    "total": len(start["questions"]),
                    "msg": f"逐题答题已启动, job_id={job_id}",
                })
            except Exception as e:
                self._json({"success": False, "msg": f"启动失败: {str(e)[:100]}"})
        elif u.path == '/api/job_status':
            try:
                d = json.loads(body)
                jid = d.get("job_id", "")
                status = get_job_status(jid)
                self._json(status)
            except Exception as e:
                self._json({"status": "error", "msg": str(e)[:60]})
        elif u.path == '/api/random_gradual':
            try:
                d = json.loads(body)
                tpid = d.get("template_pageid", template_pageid)
                cid = d.get("course_id", course_id)
                ck = d.get("cookie", cookie_str)
                if not tpid or not cid:
                    self._json({"success": False, "msg": "缺少 template_pageid/course_id"})
                    return
                result = random_gradual_exam(ck, tpid, cid,
                                              base_url=getanserurl,
                                              browser_headers=browser_headers if browser_headers else None)
                self._json(result)
            except Exception as e:
                self._json({"success": False, "msg": f"随机逐题启动失败: {str(e)[:100]}"})
        elif u.path == '/api/exit':
            self._text("bye")
            import threading
            threading.Timer(0.3, lambda: os._exit(0)).start()
        else:
            self._text("ok")
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()
    def _text(self, t):
        self.send_response(200)
        self._cors()
        self.send_header("Content-type", "text/plain;charset=utf-8")
        self.end_headers()
        self.wfile.write(t.encode("utf-8"))
    def _json(self, d):
        self.send_response(200)
        self._cors()
        self.send_header("Content-type", "application/json;charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(d, ensure_ascii=False).encode("utf-8"))
    def log_message(self, *a): pass

def start_api():
    global api_server
    api_server = HTTPServer(("", 0), ApiHandler)
    port = api_server.server_address[1]
    t = threading.Thread(target=api_server.serve_forever, daemon=True)
    t.start()
    return port

HTML = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>考试答题工具</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,"Microsoft YaHei",sans-serif;user-select:none}
body{background:#f5f5f5;height:100vh;display:flex}
.left{flex:2;padding:12px;display:flex;flex-direction:column;overflow:hidden}
.right{flex:1;max-width:320px;background:#f0f0f0;padding:12px;border-left:2px solid #ddd;display:flex;flex-direction:column;overflow:hidden}
h3{margin:4px 0;color:#333}
textarea,input,button{font-size:14px}
textarea{resize:none}
.cookie-area{height:90px;margin:4px 0}
.cookie-area textarea{width:100%;height:100%;padding:6px;border:1px solid #ccc;border-radius:4px;font-family:Courier}
.row{display:flex;align-items:center;gap:6px;margin:3px 0;flex-wrap:wrap}
.row label{font-size:14px;font-weight:500;color:#333}
input[type=text]{padding:4px 8px;border:1px solid #ccc;border-radius:4px;font-size:14px}
.btn{padding:5px 12px;border:1px solid #aaa;border-radius:4px;cursor:pointer;background:#f0f0f0;font-size:13px;outline:none}
.btn:hover{background:#e0e0e0}
.btn-primary{background:#4472C4;color:white;border-color:#4472C4}
.btn-primary:hover{background:#3563b0}
.btn-danger{background:#C00000;color:white;border-color:#C00000}
.btn-danger:hover{background:#a00000}
.btn:disabled{opacity:0.5;cursor:default}
.preview-area{flex:1;margin:4px 0}
.preview-area textarea{width:100%;height:100%;padding:6px;border:1px solid #ccc;border-radius:4px;font-family:Courier;background:#fafafa}
.log-area{flex:1;margin:4px 0}
.log-area textarea{width:100%;height:100%;padding:6px;border:1px solid #ccc;border-radius:4px;font-family:Courier;background:white}
.tip{font-size:11px;color:#999}
</style></head><body>
<div class="left">
  <h3>标头信息输入</h3>
  <div class="cookie-area"><textarea id="cookie" placeholder="F12 → 网络 → 请求标头 → 右键Copy → 粘贴在此"></textarea></div>
  <div class="row">
    <button class="btn" onclick="importHeaders()">导入标头</button>
  </div>
  <div class="row">
    <label>PID 输入</label>
    <input type="text" id="pid" placeholder="数字" value="PIDVAL" style="width:100px">
    <span class="tip">(数字)</span>
    <button class="btn" onclick="checkPid()">PID 检测</button>
  </div>
  <div class="row">
    <label>答案提取</label>
    <button class="btn btn-primary" onclick="fetchAnswers()">获取答案</button>
  </div>
  <div class="row">
    <label>随机测试</label><button class="btn" id="vbtn_fast" onclick="randomFast()">随机(快速)</button>
    <button class="btn" id="vbtn" onclick="randomGradual()">随机(逐题)</button>
    <label style="margin-left:10px">提交答案</label>
    <button class="btn btn-danger" id="execBtn" disabled onclick="submitFast()">提交(快速)</button>
    <button class="btn" id="gradualBtn" disabled onclick="submitGradual()">提交(逐题)</button>
  </div>
  <div class="preview-area"><textarea id="preview" readonly></textarea></div>
</div>
<div class="right">
  <h3>日志栏</h3>
  <div class="log-area"><textarea id="log" readonly></textarea></div>
  <div style="margin-top:6px;text-align:center">
    <button class="btn" onclick="exitApp()" style="color:#C00000">关闭退出</button>
  </div>
</div>
<script>
let API='';
let logs=[];
function log(m){let t=new Date().toLocaleTimeString();let l="["+t+"] "+m;logs.push(l);let ta=document.getElementById('log');ta.value=logs.join('\n');ta.scrollTop=ta.scrollHeight}
function importHeaders(){let t=document.getElementById('cookie').value.trim();if(!t){alert('请先在输入框粘贴浏览器F12复制的完整请求标头');return}log('解析标头...');fetch(API+'/api/parse_headers',{method:'POST',body:JSON.stringify({text:t}),headers:{'Content-Type':'application/json'}}).then(r=>r.json()).then(d=>{if(d.success){log('✅ 标头解析成功');if(d.has_cookie)log('  Cookie: '+d.cookie_preview);log('  标头字段: ('+d.headers_keys.length+'个): '+d.headers_keys.join(', '));log('  原始→headers.txt  Cookie→cookie.txt  标头参数→内存')}else{log('❌ '+d.msg)}}).catch(e=>log('错误: '+e))}
function getStoredCookie(){return fetch(API+'/api/config').then(r=>r.json()).then(d=>d.cookie||'')}
function checkPid(){let p=document.getElementById('pid').value.trim();if(!p||!/^\d+$/.test(p)){alert('输入 PID 数字');return}log('PID 检测: '+p);getStoredCookie().then(c=>{let ck=encodeURIComponent(c);fetch(API+'/api/check?pid='+p+'&cookie='+ck).then(r=>r.json()).then(d=>{log('📋 '+(d.title||'试卷'));log(d.ok?'✅ '+d.msg:'❌ '+d.msg);log('  题数: '+d.total+' | 类型: '+d.type);let a=Math.min(d.answered,d.total);if(a>0)log('  已答: '+a+' 题')}).catch(e=>log('错误: '+e))})}
function fetchAnswers(){let p=document.getElementById('pid').value.trim();if(!p||!/^\d+$/.test(p)){alert('输入 PID');return}log('提取答案: '+p);getStoredCookie().then(c=>{let ck=encodeURIComponent(c);fetch(API+'/api/fetch?pid='+p+'&cookie='+ck).then(r=>r.json()).then(d=>{if(d.error){log('错误: '+d.error);return};log('完成: '+d.found+'/'+d.total);if(d.template_pageid)log('📋 template_pageid='+d.template_pageid+' course_id='+d.course_id);document.getElementById('preview').value=d.text;document.getElementById('execBtn').disabled=false;document.getElementById('gradualBtn').disabled=false}).catch(e=>log('错误: '+e))})}
function submitFast(){let btn=document.getElementById('execBtn');btn.disabled=true;btn.textContent='答题中...';log('🚀 快速提交...');fetch(API+'/api/submit',{method:'POST',body:JSON.stringify({}),headers:{'Content-Type':'application/json'}}).then(r=>r.json()).then(d=>{if(d.success){log('✅ 交卷成功! PID='+d.new_pid);log('📊 提交 '+d.answered+' 题');if(d.result){log('  正确:'+d.result.correct+' 错误:'+d.result.wrong+' 未做:'+d.result.unanswered)}else{log('  共 '+d.total+' 题')}}else{log('❌ '+d.msg)}btn.disabled=false;btn.textContent='提交(快速)'}).catch(e=>{log('错误: '+e);btn.disabled=false;btn.textContent='提交(快速)'})}
function randomFast(){let btn=document.getElementById('vbtn_fast');btn.disabled=true;btn.textContent='随机中...';log('🎲 随机(快速)...');fetch(API+'/api/random_exam',{method:'POST',body:JSON.stringify({}),headers:{'Content-Type':'application/json'}}).then(r=>r.json()).then(d=>{if(d.success){log('✅ 随机完成! PID='+d.new_pid);log('📊 提交 '+d.answered+' 题');if(d.result){log('  正确:'+d.result.correct+' 错误:'+d.result.wrong+' 未做:'+d.result.unanswered)}else{log('  共 '+d.total+' 题')}}else{log('❌ '+d.msg)}btn.disabled=false;btn.textContent='随机(快速)'}).catch(e=>{log('错误: '+e);btn.disabled=false;btn.textContent='随机(快速)'})}
function exitApp(){if(confirm('确认退出程序？')){fetch(API+'/api/exit',{method:'POST',body:'{}'}).then(()=>{}).catch(()=>{})}}
function randomGradual(){let btn=document.getElementById('vbtn');if(g_job_id){log('🛑 取消随机...');g_job_id=null;if(g_poll_timer){clearInterval(g_poll_timer);g_poll_timer=null}btn.disabled=false;btn.textContent='随机(逐题)';return}
btn.disabled=true;btn.textContent='启动中...';log('🎲 随机逐题(每题间隔10-20秒)...');fetch(API+'/api/random_gradual',{method:'POST',body:JSON.stringify({}),headers:{'Content-Type':'application/json'}}).then(r=>r.json()).then(d=>{if(d.success){g_job_id=d.job_id;log('📋 随机任务启动, 共'+d.total+'题');btn.textContent='点击取消';g_poll_timer=setInterval(function(){fetch(API+'/api/job_status',{method:'POST',body:JSON.stringify({job_id:g_job_id}),headers:{'Content-Type':'application/json'}}).then(r=>r.json()).then(s=>{if(s.status=='answering'){log('⏳ 第'+s.current_num+'题 随机('+s.answer+'), '+s.completed+'/'+s.total);}else if(s.status=='done'){log('✅ 随机完成! '+s.msg);if(s.result){log('📊 正确:'+s.result.correct+' 错误:'+s.result.wrong+' 未做:'+s.result.unanswered)}clearInterval(g_poll_timer);g_poll_timer=null;g_job_id=null;btn.textContent='随机(逐题)';btn.disabled=false}else if(s.status=='error'){log('❌ '+s.msg);clearInterval(g_poll_timer);g_poll_timer=null;g_job_id=null;btn.disabled=false;btn.textContent='随机(逐题)'}})},15000)}else{log('❌ '+d.msg);btn.disabled=false;btn.textContent='随机(逐题)'}}).catch(e=>{log('错误: '+e);btn.disabled=false;btn.textContent='随机(逐题)'})}
var g_job_id=null;var g_poll_timer=null;
function submitGradual(){let btn=document.getElementById('gradualBtn');if(g_job_id){log('🛑 取消提交...');g_job_id=null;if(g_poll_timer){clearInterval(g_poll_timer);g_poll_timer=null}btn.disabled=false;btn.textContent='提交(逐题)';return}
btn.disabled=true;btn.textContent='启动中...';log('🚀 逐题答题启动(每题间隔10-20秒)...');fetch(API+'/api/gradual_submit',{method:'POST',body:JSON.stringify({}),headers:{'Content-Type':'application/json'}}).then(r=>r.json()).then(d=>{if(d.success){g_job_id=d.job_id;log('📋 任务已启动, 共'+d.total+'题, job_id='+g_job_id);btn.textContent='取消答题';g_poll_timer=setInterval(function(){fetch(API+'/api/job_status',{method:'POST',body:JSON.stringify({job_id:g_job_id}),headers:{'Content-Type':'application/json'}}).then(r=>r.json()).then(s=>{if(s.status=='answering'){log('⏳ 第'+s.current_num+'题 ('+s.answer+'), '+s.completed+'/'+s.total+' 完成');if(s.setanswer_ok===false)log('  ⚠️ 部分setanswer失败')}else if(s.status=='done'){log('✅ '+s.msg);if(s.result){log('📊 正确:'+s.result.correct+' 错误:'+s.result.wrong+' 未做:'+s.result.unanswered)}clearInterval(g_poll_timer);g_poll_timer=null;g_job_id=null;btn.disabled=true;btn.textContent='已完成';if(s.new_pid)document.getElementById('pid').value=s.new_pid}else if(s.status=='error'){log('❌ '+s.msg);clearInterval(g_poll_timer);g_poll_timer=null;g_job_id=null;btn.disabled=false;btn.textContent='提交(逐题)'}})},15000)}else{log('❌ '+d.msg);btn.disabled=false;btn.textContent='提交(逐题)'}}).catch(e=>{log('错误: '+e);btn.disabled=false;btn.textContent='提交(逐题)'})}
window.onload=function(){log('程序启动');fetch(API+'/api/config').then(r=>r.json()).then(d=>{if(d.pid)document.getElementById('pid').value=d.pid;if(d.headers_raw)document.getElementById('cookie').value=d.headers_raw;if(d.headers_raw&&d.cookie)log('📋 已导入上次的标头 + Cookie')}).catch(()=>{})};
</script></body></html>"""

def main():
    load_config()

    # 直接在同端口提供 HTML
    html_out = HTML.replace(
        'PIDVAL', pid_val if pid_val else ''
    )

    # 写入临时变量给 handler 使用
    serve_html = html_out

    original_do_GET = ApiHandler.do_GET
    def new_do_GET(self):
        if self.path == '/' or not self.path.startswith('/api/'):
            self.send_response(200)
            self.send_header("Content-type", "text/html;charset=utf-8")
            self.end_headers()
            self.wfile.write(serve_html.encode("utf-8"))
        else:
            original_do_GET(self)
    ApiHandler.do_GET = new_do_GET

    port = start_api()
    url = f"http://127.0.0.1:{port}"

    # --server 模式：跳过 pywebview，直接开浏览器
    if "--server" in sys.argv:
        print(f"\n=== 服务运行模式 ===")
        print(f"地址: {url}")
        print(f"状态: 按 Ctrl+C 停止服务")
        print()
        import webbrowser
        webbrowser.open(url)
        try:
            while True:
                import time; time.sleep(1)
        except KeyboardInterrupt:
            print("\n服务已停止")
        return

    try:
        import webview
        webview.create_window(
            "考试答题工具",
            url=url,
            width=1050,
            height=730,
            resizable=False,
        )
        webview.start(private_mode=False)
    except Exception as e:
        print(f"[回退] pywebview 不可用 ({e})，已在浏览器打开")
        import webbrowser
        webbrowser.open(url)
        try:
            while True:
                import time; time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        if api_server:
            api_server.shutdown()
        print("程序已退出")
