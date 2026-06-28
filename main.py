#!/usr/bin/env python3
"""
考试答题工具 - 原生窗口版
HTML 渲染界面，原生窗口显示（不跳转浏览器）
"""
import sys, os, json, threading, datetime, re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules.fetcher import fetch_page, parse_html, check_cookie

APP_DIR = Path(__file__).parent
LOG_FILE = APP_DIR / "exam_tool.log"
CONFIG_FILE = APP_DIR / "config.json"

cookie_str = ""
pid_val = ""
getanserurl = "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid="

def load_config():
    global cookie_str, pid_val, getanserurl
    try:
        if CONFIG_FILE.exists():
            d = json.load(open(CONFIG_FILE, encoding="utf-8"))
            cookie_str = d.get("cookie", "")
            pid_val = d.get("pid", "")
            getanserurl = d.get("getanserurl", "https://sxvtc.cjnep.net/lms/web/exam/examshow?pid=")
    except: pass

def save_config():
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"cookie": cookie_str, "pid": pid_val, "getanserurl": getanserurl}, f, ensure_ascii=False, indent=2)
    except: pass

# ─── HTTP API ───
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

api_server = None

class ApiHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global cookie_str, pid_val, getanserurl
        u = urlparse(self.path)
        if u.path == '/api/check':
            q = parse_qs(u.query)
            pid = q.get('pid', [''])[0]
            ck = q.get('cookie', [''])[0]
            urlbase = q.get('url', [getanserurl])[0]
            try:
                ok = check_cookie(pid, ck, urlbase)
                self._text("Cookie 有效" if ok else "Cookie 无效")
            except Exception as e:
                self._text(f"错误: {str(e)[:50]}")
        elif u.path == '/api/fetch':
            q = parse_qs(u.query)
            pid = q.get('pid', [''])[0]
            ck = q.get('cookie', [''])[0]
            urlbase = q.get('url', [getanserurl])[0]
            try:
                h = fetch_page(pid, ck, urlbase)
                rs = parse_html(h)
                found = sum(1 for r in rs if r["answer"])
                txt = ""
                for r in rs:
                    a = r["answer"] if r["answer"] else "?"
                    txt += f"第{r['num']:>2}题 [{r['type']}] {a}\n"
                cookie_str = ck; pid_val = pid; getanserurl = urlbase; save_config()
                self._json({"found": found, "total": len(rs), "text": txt})
            except Exception as e:
                self._json({"error": str(e)[:60]})
        elif u.path == '/api/config':
            self._json({"cookie": cookie_str, "pid": pid_val, "getanserurl": getanserurl})
        elif u.path == '/api/save':
            q = parse_qs(u.query)
            cookie_str = q.get('cookie', [''])[0]
            pid_val = q.get('pid', [''])[0]
            save_config()
            self._text("saved")
        else:
            self._text("ok")
    def _text(self, t):
        self.send_response(200)
        self.send_header("Content-type", "text/plain;charset=utf-8")
        self.end_headers()
        self.wfile.write(t.encode("utf-8"))
    def _json(self, d):
        self.send_response(200)
        self.send_header("Content-type", "application/json;charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(d, ensure_ascii=False).encode("utf-8"))
    def log_message(self, *a): pass

def start_api():
    global api_server
    api_server = HTTPServer(("127.0.0.1", 0), ApiHandler)
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
  <h3>Cookie 输入</h3>
  <div class="cookie-area"><textarea id="cookie" placeholder="F12 → Application → Cookies 粘贴"></textarea></div>
  <div class="row">
    <label>PID 输入</label>
    <input type="text" id="pid" placeholder="数字" value="" style="width:100px">
    <span class="tip">(数字)</span>
    <button class="btn" onclick="checkPid()">PID 检测</button>
  </div>
  <div class="row">
    <label>虚拟答题</label><button class="btn" id="vbtn" disabled onclick="alert('待实现')">开始答题（虚拟）</button>
    <label style="margin-left:10px">答案提取</label>
    <button class="btn btn-primary" onclick="fetchAnswers()">获取答案</button>
  </div>
  <div class="row">
    <button class="btn btn-danger" id="execBtn" disabled onclick="alert('待实现')">开始答题</button>
    <label style="margin-left:8px">答案预览</label>
  </div>
  <div class="preview-area"><textarea id="preview" readonly></textarea></div>
</div>
<div class="right">
  <h3>日志栏</h3>
  <div class="log-area"><textarea id="log" readonly></textarea></div>
</div>
<script>
let API='http://127.0.0.1:APIPORT';
let logs=[];
function log(m){let t=new Date().toLocaleTimeString();let l="["+t+"] "+m;logs.push(l);let ta=document.getElementById('log');ta.value=logs.join('\n');ta.scrollTop=ta.scrollHeight}
function checkPid(){let p=document.getElementById('pid').value.trim();let c=document.getElementById('cookie').value.trim();if(!p||!/^\d+$/.test(p)){alert('输入 PID 数字');return}log('PID 检测: '+p);fetch(API+'/api/check?pid='+p+'&cookie='+encodeURIComponent(c)).then(r=>r.text()).then(t=>log(t)).catch(e=>log('错误: '+e))}
function fetchAnswers(){let p=document.getElementById('pid').value.trim();let c=document.getElementById('cookie').value.trim();if(!p||!/^\d+$/.test(p)){alert('输入 PID');return}log('提取答案: '+p);fetch(API+'/api/fetch?pid='+p+'&cookie='+encodeURIComponent(c)).then(r=>r.json()).then(d=>{if(d.error){log('错误: '+d.error);return};log('完成: '+d.found+'/'+d.total);document.getElementById('preview').value=d.text;document.getElementById('execBtn').disabled=false;document.getElementById('vbtn').disabled=false}).catch(e=>log('错误: '+e))}
window.onload=function(){let p=document.getElementById('pid');let ck=document.getElementById('cookie');fetch(API+'/api/config').then(r=>r.json()).then(d=>{if(d.cookie)ck.value=d.cookie;if(d.pid)p.value=d.pid});log('程序启动')};
setInterval(function(){let p=document.getElementById('pid').value.trim();let c=document.getElementById('cookie').value.trim();if(p||c){fetch(API+'/api/save?pid='+encodeURIComponent(p)+'&cookie='+encodeURIComponent(c))}},3000);
</script></body></html>"""

def main():
    load_config()
    port = start_api()

    html = HTML.replace("APIPORT", str(port))

    import webview
    webview.create_window(
        "考试答题工具",
        html=html,
        width=1050,
        height=730,
        resizable=False,
    )
    webview.start(private_mode=False)

if __name__ == "__main__":
    main()
