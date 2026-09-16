# -*- coding: utf-8 -*-
"""工学云自动打卡核心 API 封装（新版 v3 接口，AES + 本地 MD5 签名）"""

import json
import time
import hashlib
import random
import requests

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    _HAS_CRYPTO = True
except Exception:
    _HAS_CRYPTO = False

import urllib3
urllib3.disable_warnings()

BASE_URL = "https://api.moguding.net:9000/"

# 登录/加密密钥（工学云新版固定值）
AES_KEY = "23DbtQHR2UMbH6mJ"
# 签名盐（本地 MD5 签名用）
SIGN_SALT = "3478cbbc33f84bd00d75d7dfa69e0daa"

UA_LIST = [
    "Mozilla/5.0 (Linux; U; Android 9; zh-cn; Redmi Note 5 Build/PKQ1.180904.001) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/71.0.3578.141 Mobile Safari/537.36 XiaoMi/MiuiBrowser/11.10.8",
    "Mozilla/5.0 (Linux; Android 9; MI 6 Build/PKQ1.190118.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/76.0.3809.89 Mobile Safari/537.36 T7/11.20 SP-engine/2.16.0 baiduboxapp/11.20.2.3 (Baidu; P1 9)",
    "Mozilla/5.0 (Linux; Android 10; EVR-AL00 Build/HUAWEIEVR-AL00; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/74.0.3729.186 Mobile Safari/537.36 baiduboxapp/11.0.5.12 (Baidu; P1 10)",
    "Mozilla/5.0 (Linux; U; Android 9; zh-cn; SM-G977N Build/LMY48Z) AppleWebKit/533.1 (KHTML, like Gecko) Version/5.0 Mobile Safari/533.1",
]


class GxyError(Exception):
    pass


def _aes_encrypt(text):
    """AES-128-ECB + PKCS7 padding，输出 hex（工学云新版加密）"""
    if not _HAS_CRYPTO:
        raise GxyError("缺少 pycryptodome 依赖，无法加密")
    key = AES_KEY.encode("utf-8")
    cipher = AES.new(key, AES.MODE_ECB)
    return cipher.encrypt(pad(text.encode("utf-8"), 16)).hex()


def _sign(text):
    """新版本地 MD5 签名"""
    return hashlib.md5((text + SIGN_SALT).encode("utf-8")).hexdigest()


def _random_ua():
    return random.choice(UA_LIST)


def _base_headers():
    return {
        "Host": "api.moguding.net:9000",
        "accept-language": "zh-CN,zh;q=0.8",
        "user-agent": _random_ua(),
        "authorization": "",
        "rolekey": "student",
        "content-type": "application/json; charset=UTF-8",
        "accept-encoding": "gzip",
        "cache-control": "no-cache",
    }


class GxyClient(object):
    """工学云客户端（新版 v3 接口）"""

    def __init__(self, phone, password, address, latitude, longitude,
                 country="中国", province="", city="", device="Android",
                 token=""):
        self.phone = phone
        self.password = password
        self.token = token
        self.device = device
        self.country = country
        self.province = province
        self.city = city
        self.address = address
        self.latitude = str(latitude)
        self.longitude = str(longitude)

        self.user_id = ""
        self.nike_name = ""
        self.user_type = ""
        self.mogu_no = ""
        self.plan_id = ""
        self.plan_name = ""

    # ------------------------------------------------------------------
    def _post(self, url, body, need_sign=None):
        headers = _base_headers()
        headers["authorization"] = self.token
        if need_sign:
            headers["sign"] = _sign(need_sign)
        resp = requests.post(url=url, headers=headers,
                             data=json.dumps(body), verify=False, timeout=25)
        return resp.json()

    # ------------------------------------------------------------------
    def login(self):
        """登录（v3），返回 token"""
        if not _HAS_CRYPTO:
            raise GxyError("缺少 pycryptodome 依赖，无法登录")
        t = str(int(time.time() * 1000))
        body = {
            "password": _aes_encrypt(self.password),
            "phone": _aes_encrypt(self.phone),
            "t": _aes_encrypt(t),
            "loginType": "android",
            "uuid": "",
        }
        headers = _base_headers()
        url = BASE_URL + "session/user/v3/login"
        resp = requests.post(url=url, headers=headers,
                             data=json.dumps(body), verify=False, timeout=25)
        js = resp.json()
        if js.get("code") != 200:
            raise GxyError("登录失败: %s" % js.get("msg", "未知错误"))
        data = js["data"]
        self.token = data["token"]
        self.user_id = str(data["userId"])
        self.nike_name = data.get("nikeName", "")
        self.user_type = data.get("userType", "student")
        self.mogu_no = data.get("moguNo", "")
        return self.token

    # ------------------------------------------------------------------
    def get_plan(self):
        """获取实习计划，返回 (planId, planName)"""
        if not self.token:
            self.login()
        # sign = md5(userId + 'student' + salt)
        url = BASE_URL + "practice/plan/v3/getPlanByStu"
        js = self._post(url, {"state": ""}, need_sign=self.user_id + "student")
        if js.get("code") != 200:
            raise GxyError("获取实习计划失败: %s" % js.get("msg", ""))
        data_list = js.get("data") or []
        if not data_list:
            raise GxyError("没有可用的实习计划")
        data = data_list[0]
        self.plan_id = data.get("planId", "")
        self.plan_name = data.get("planName", "")
        return self.plan_id, self.plan_name

    # ------------------------------------------------------------------
    def clock_in(self, is_start=True):
        """打卡。is_start=True 上班，False 下班。返回 (title, message)"""
        if not self.plan_id:
            self.get_plan()
        if not self.token:
            self.login()

        type_str = "START" if is_start else "END"
        # sign = md5(device + type + planId + userId + address + salt)
        sign_text = self.device + type_str + self.plan_id + self.user_id + self.address

        body = {
            "device": self.device,
            "address": self.address,
            "t": _aes_encrypt(str(int(time.time() * 1000))),
            "description": "",
            "country": self.country,
            "longitude": self.longitude,
            "city": self.city,
            "latitude": self.latitude,
            "planId": self.plan_id,
            "province": self.province,
            "type": type_str,
        }
        url = BASE_URL + "attendence/clock/v2/save"
        js = self._post(url, body, need_sign=sign_text)
        if js.get("code") != 200:
            raise GxyError("打卡失败: %s" % js.get("msg", "未知错误"))
        create_time = (js.get("data") or {}).get("createTime", "")
        title = "%s，%s打卡成功!" % (
            self.nike_name, "上班" if is_start else "下班")
        message = "目标: %s\n打卡时间: %s\n打卡地点: %s" % (
            self.plan_name, create_time, self.address)
        return title, message
