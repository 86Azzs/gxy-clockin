# -*- coding: utf-8 -*-
"""工学云自动打卡核心 API 封装（移植自 MoGuDing-Auto）"""

import json
import requests
import urllib3

urllib3.disable_warnings()

BASE_URL = "https://api.moguding.net:9000/"
SIGN_URL = "http://mgd.lftools.ltd:2658/api/"

HEADERS = {
    "Host": "api.moguding.net:9000",
    "accept-language": "zh-CN,zh;q=0.8",
    "user-agent": "Mozilla/5.0 (Linux; Android 7.0; HTC M9e Build/EZG0TF) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                  "Chrome/55.0.1566.54 Mobile Safari/537.36",
    "sign": "",
    "authorization": "",
    "rolekey": "student",
    "content-type": "application/json; charset=UTF-8",
    "accept-encoding": "gzip",
    "cache-control": "no-cache",
}


class GxyError(Exception):
    pass


class GxyClient(object):
    """工学云客户端"""

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
    def _post(self, url, body, need_sign_url=None, sign_param=None):
        headers = dict(HEADERS)
        headers["authorization"] = self.token
        headers["rolekey"] = "student"
        if need_sign_url and sign_param is not None:
            sign = self._get_sign(need_sign_url, sign_param)
            headers["sign"] = sign or ""
        resp = requests.post(url=url, headers=headers,
                             data=json.dumps(body), verify=False, timeout=20)
        return resp.json()

    # ------------------------------------------------------------------
    def login(self):
        """登录，返回 token"""
        body = {
            "phone": self.phone,
            "password": self.password,
            "loginType": "android",
            "uuid": "",
        }
        url = BASE_URL + "session/user/v1/login"
        resp = requests.post(url=url, headers=dict(HEADERS),
                             data=json.dumps(body), verify=False, timeout=20)
        js = resp.json()
        if js.get("code") != 200:
            raise GxyError("登录失败: %s" % js.get("msg", "未知错误"))
        data = js["data"]
        self.token = data["token"]
        self.user_id = data["userId"]
        self.nike_name = data.get("nikeName", "")
        self.user_type = data.get("userType", "")
        self.mogu_no = data.get("moguNo", "")
        return self.token

    # ------------------------------------------------------------------
    def get_user_info(self):
        url = BASE_URL + "usercenter/user/v1/info"
        js = self._post(url, {})
        if js.get("code") != 200:
            raise GxyError("获取用户信息失败: %s" % js.get("msg", ""))
        data = js["data"]
        self.user_id = data.get("userId", self.user_id)
        self.nike_name = data.get("nikeName", self.nike_name)
        self.user_type = data.get("userType", self.user_type)
        self.mogu_no = data.get("moguNo", self.mogu_no)
        return data

    # ------------------------------------------------------------------
    def _get_sign(self, sign_url, parameter):
        url = SIGN_URL + sign_url
        try:
            resp = requests.post(url=url, headers=dict(HEADERS),
                                 data=json.dumps(parameter), timeout=15)
            js = resp.json()
            if js.get("code") == 200:
                return js.get("sign")
            return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    def get_plan(self):
        """获取实习计划，返回 planId / planName"""
        if not self.token:
            self.login()
        if not self.user_id:
            self.get_user_info()

        sign = self._get_sign("getPlanByStuSign", {
            "userId": self.user_id,
            "paramString": "",
            "moguNo": self.mogu_no,
            "userType": self.user_type,
        })
        headers = dict(HEADERS)
        headers["authorization"] = self.token
        headers["rolekey"] = "student"
        headers["sign"] = sign or ""
        url = BASE_URL + "practice/plan/v3/getPlanByStu"
        resp = requests.post(url=url, headers=headers,
                             data=json.dumps({"state": ""}),
                             verify=False, timeout=20)
        js = resp.json()
        if js.get("code") != 200:
            raise GxyError("获取实习计划失败: %s" % js.get("msg", ""))
        data_list = js.get("data") or []
        if not data_list:
            raise GxyError("没有可用的实习计划")
        data = data_list[-1]
        self.plan_id = data.get("planId", "")
        self.plan_name = data.get("planName", "")
        return self.plan_id, self.plan_name

    # ------------------------------------------------------------------
    def clock_in(self, is_start=True):
        """打卡。is_start=True 上班，False 下班。返回 (title, message)"""
        if not self.plan_id:
            self.get_plan()

        type_str = "START" if is_start else "END"
        sign = self._get_sign("getClockInSign", {
            "userId": self.user_id,
            "moguNo": self.mogu_no,
            "address": self.address,
            "device": self.device,
            "planId": self.plan_id,
            "type": type_str,
            "latitude": self.latitude,
            "longitude": self.longitude,
        })
        headers = dict(HEADERS)
        headers["authorization"] = self.token
        headers["rolekey"] = "student"
        headers["sign"] = sign or ""

        body = {
            "country": self.country,
            "address": self.address,
            "province": self.province,
            "city": self.city,
            "latitude": self.latitude,
            "description": "",
            "planId": self.plan_id,
            "type": type_str,
            "device": self.device,
            "longitude": self.longitude,
        }
        url = BASE_URL + "attendence/clock/v2/save"
        resp = requests.post(url=url, headers=headers,
                             data=json.dumps(body), verify=False, timeout=20)
        js = resp.json()
        if js.get("code") != 200:
            raise GxyError("打卡失败: %s" % js.get("msg", "未知错误"))
        create_time = (js.get("data") or {}).get("createTime", "")
        title = "%s，%s打卡成功!" % (
            self.nike_name, "上班" if is_start else "下班")
        message = "目标: %s\n打卡时间: %s\n打卡地点: %s" % (
            self.plan_name, create_time, self.address)
        return title, message
