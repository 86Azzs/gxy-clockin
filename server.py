# -*- coding: utf-8 -*-
"""工学云自动打卡 - 手机浏览器 Web 界面（零额外依赖，标准库 http.server）

运行：python3 server.py
手机浏览器访问：http://127.0.0.1:18088
"""

import json
import os
import threading
import datetime
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from gxy_api import GxyClient, GxyError

HOST = "127.0.0.1"
PORT = 18088
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "logs.txt")


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def log(msg):
    ts = datetime.datetime.now().strftime("%m-%d %H:%M:%S")
    line = "[%s] %s\n" % (ts, msg)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    # 保留最近 200 行
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > 200:
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines[-200:])
    except Exception:
        pass
    return line


def read_logs():
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


# 全局配置
CFG = load_config()
CFG_LOCK = threading.Lock()


def make_client(cfg):
    return GxyClient(
        phone=cfg.get("phone", ""),
        password=cfg.get("password", ""),
        token=cfg.get("token", ""),
        address=cfg.get("address", ""),
        latitude=cfg.get("latitude", ""),
        longitude=cfg.get("longitude", ""),
        province=cfg.get("province", ""),
        city=cfg.get("city", ""),
    )


# ---------------- 自动打卡后台线程 ----------------
def auto_loop():
    last_date = None
    done_start = False
    done_end = False
    while True:
        try:
            now = datetime.datetime.now()
            today = now.strftime("%Y-%m-%d")
            if today != last_date:
                last_date = today
                done_start = False
                done_end = False
            with CFG_LOCK:
                auto_enable = CFG.get("auto_enable", False)
                start_t = CFG.get("auto_start", "08:50")
                end_t = CFG.get("auto_end", "17:30")
            hhmm = now.strftime("%H:%M")
            if auto_enable:
                if hhmm == start_t and not done_start:
                    done_start = True
                    log("定时触发：上班打卡")
                    _do_clock_sync(True)
                elif hhmm == end_t and not done_end:
                    done_end = True
                    log("定时触发：下班打卡")
                    _do_clock_sync(False)
            time.sleep(20)
        except Exception as e:
            log("定时线程异常: %s" % e)
            time.sleep(30)


def _do_clock_sync(is_start):
    try:
        with CFG_LOCK:
            cfg = dict(CFG)
        c = make_client(cfg)
        title, msg = c.clock_in(is_start)
        log("%s\n%s" % (title, msg))
        return True, title + "\n" + msg
    except GxyError as e:
        log("打卡错误: %s" % e)
        return False, "打卡错误: %s" % e
    except Exception as e:
        log("打卡异常: %s" % e)
        return False, "打卡异常: %s" % e


# ---------------- HTML 页面 ----------------
PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>工学云自动打卡</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#f0f2f5;color:#222;padding:16px;padding-bottom:40px}
h1{font-size:20px;color:#1a3c6e;margin:4px 0 16px;text-align:center}
.card{background:#fff;border-radius:14px;padding:16px;margin-bottom:14px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.card h2{font-size:14px;color:#4a6fa5;margin-bottom:12px;font-weight:600}
label{display:block;font-size:13px;color:#666;margin:8px 0 4px}
input{width:100%;height:44px;border:1px solid #ddd;border-radius:8px;padding:0 12px;font-size:15px;background:#fafafa}
input:focus{outline:none;border-color:#4a90d9;background:#fff}
.row{display:flex;gap:10px;margin-top:14px}
.btn{flex:1;height:48px;border:none;border-radius:10px;font-size:16px;color:#fff;font-weight:600;cursor:pointer}
.btn:active{opacity:.8}
.btn-start{background:#2e7d32}
.btn-end{background:#e65100}
.btn-save{background:#607d8b}
.btn-test{background:#7b5ea7}
.btn-auto{background:#1565c0}
.btn-auto.on{background:#c62828}
#log{width:100%;height:180px;border:1px solid #ddd;border-radius:10px;padding:10px;font-size:12px;background:#fafafa;color:#333;resize:none;font-family:monospace;line-height:1.5}
#msg{position:fixed;top:12px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.8);color:#fff;padding:10px 18px;border-radius:8px;font-size:14px;display:none;z-index:99;max-width:90%}
</style>
</head>
<body>
<h1>工学云自动打卡</h1>
<div id="msg"></div>

<div class="card">
<h2>账号设置</h2>
<label>手机号</label><input id="phone" placeholder="手机号">
<label>密码</label><input id="password" type="password" placeholder="密码">
<label>Token（可选，留空自动登录）</label><input id="token" placeholder="Token">
</div>

<div class="card">
<h2>打卡地点</h2>
<label>详细地址</label><input id="address" placeholder="详细地址">
<label>省份</label><input id="province" placeholder="省份">
<label>城市</label><input id="city" placeholder="城市">
<label>纬度 latitude</label><input id="latitude" placeholder="如 30.123456">
<label>经度 longitude</label><input id="longitude" placeholder="如 120.123456">
</div>

<div class="card">
<h2>打卡操作</h2>
<div class="row">
<button class="btn btn-start" onclick="clock(true)">上班打卡</button>
<button class="btn btn-end" onclick="clock(false)">下班打卡</button>
</div>
<div class="row">
<button class="btn btn-save" onclick="save()">保存配置</button>
<button class="btn btn-test" onclick="testLogin()">测试登录</button>
</div>
</div>

<div class="card">
<h2>定时自动打卡</h2>
<label>上班打卡时间 (HH:MM)</label><input id="auto_start" value="08:50">
<label>下班打卡时间 (HH:MM)</label><input id="auto_end" value="17:30">
<div class="row"><button class="btn btn-auto" id="autoBtn" onclick="toggleAuto()">启用自动打卡</button></div>
</div>

<div class="card">
<h2>运行日志</h2>
<textarea id="log" readonly></textarea>
</div>

<script>
function toast(s){var m=document.getElementById('msg');m.textContent=s;m.style.display='block';clearTimeout(m._t);m._t=setTimeout(function(){m.style.display='none'},2500);}
function val(id){return document.getElementById(id).value.trim();}
function getCfg(){return {phone:val('phone'),password:val('password'),token:val('token'),address:val('address'),province:val('province'),city:val('city'),latitude:val('latitude'),longitude:val('longitude'),auto_start:val('auto_start'),auto_end:val('auto_end')};}
function post(url,data,cb){fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}).then(r=>r.json()).then(cb).catch(e=>toast('请求失败: '+e));}
function save(){post('/api/save',getCfg(),function(r){toast(r.ok?'配置已保存':('保存失败: '+r.msg));});}
function clock(isStart){save();post('/api/clock',{is_start:isStart},function(r){toast(r.title||r.msg||'完成');refreshLog();});}
function testLogin(){save();post('/api/test',{},function(r){toast(r.msg||'完成');});}
function toggleAuto(){var btn=document.getElementById('autoBtn');var nowOn=btn.classList.contains('on');post('/api/auto',{enable:!nowOn,start:val('auto_start'),end:val('auto_end')},function(r){if(r.ok){refreshStatus();}toast(r.msg||'完成');});}
function refreshStatus(){fetch('/api/status').then(r=>r.json()).then(function(s){if(s.auto_enable){autoBtn.classList.add('on');autoBtn.textContent='关闭自动打卡';}else{autoBtn.classList.remove('on');autoBtn.textContent='启用自动打卡';}});}
function refreshLog(){fetch('/api/logs').then(r=>r.json()).then(function(d){document.getElementById('log').value=d.logs;});}
function loadCfg(){fetch('/api/status').then(r=>r.json()).then(function(s){var c=s.config||{};['phone','password','token','address','province','city','latitude','longitude','auto_start','auto_end'].forEach(function(k){if(c[k]!=null)document.getElementById(k).value=c[k];});refreshStatus();refreshLog();});}
loadCfg();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
            ctype = "application/json; charset=utf-8"
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        ln = int(self.headers.get("Content-Length", 0) or 0)
        if ln <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(ln).decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if path == "/api/status":
            with CFG_LOCK:
                cfg = dict(CFG)
            return self._send(200, {"auto_enable": cfg.get("auto_enable", False),
                                    "config": cfg})
        if path == "/api/logs":
            return self._send(200, {"logs": read_logs()})
        return self._send(404, {"msg": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._json_body()

        if path == "/api/save":
            with CFG_LOCK:
                for k in ("phone", "password", "token", "address", "province",
                          "city", "latitude", "longitude", "auto_start", "auto_end"):
                    if k in body:
                        CFG[k] = body[k]
                cfg = dict(CFG)
            save_config(cfg)
            return self._send(200, {"ok": True})

        if path == "/api/test":
            def task():
                with CFG_LOCK:
                    cfg = dict(CFG)
                try:
                    c = make_client(cfg)
                    c.login()
                    c.get_plan()
                    return {"ok": True, "msg": "登录成功！昵称: %s，计划: %s" % (c.nike_name, c.plan_name)}
                except GxyError as e:
                    return {"ok": False, "msg": "登录失败: %s" % e}
                except Exception as e:
                    return {"ok": False, "msg": "异常: %s" % e}
            r = task()
            log("测试登录: %s" % r["msg"])
            return self._send(200, r)

        if path == "/api/clock":
            is_start = body.get("is_start", True)
            ok, msg = _do_clock_sync(is_start)
            return self._send(200, {"ok": ok, "title": msg})

        if path == "/api/auto":
            enable = body.get("enable", False)
            start = body.get("start", "08:50")
            end = body.get("end", "17:30")
            with CFG_LOCK:
                CFG["auto_enable"] = enable
                CFG["auto_start"] = start
                CFG["auto_end"] = end
                cfg = dict(CFG)
            save_config(cfg)
            log("自动打卡已%s（上班 %s / 下班 %s）" % ("启用" if enable else "关闭", start, end))
            return self._send(200, {"ok": True, "msg": "自动打卡已" + ("启用" if enable else "关闭")})

        return self._send(404, {"msg": "not found"})

    def log_message(self, *args):
        pass


def main():
    threading.Thread(target=auto_loop, daemon=True).start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    log("服务已启动：http://%s:%d" % (HOST, PORT))
    print("工学云自动打卡服务已启动：http://%s:%d" % (HOST, PORT))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
