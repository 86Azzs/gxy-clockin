# -*- coding: utf-8 -*-
"""工学云自动打卡 - Kivy 图形界面 App"""

import json
import os
import threading
import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.core.text import LabelBase
from kivy.core.window import Window

_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "NotoSansSC-Regular.otf")
if os.path.exists(_FONT_PATH):
    LabelBase.register(name="Roboto", fn_regular=_FONT_PATH)
    LabelBase.register(name="RobotoMedium", fn_regular=_FONT_PATH)
    LabelBase.register(name="RobotoBold", fn_regular=_FONT_PATH)
    LabelBase.register(name="RobotoItalic", fn_regular=_FONT_PATH)
    LabelBase.register(name="RobotoMediumItalic", fn_regular=_FONT_PATH)

from gxy_api import GxyClient, GxyError

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "config.json")


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


class GxyApp(App):
    title = "工学云自动打卡"

    def build(self):
        Window.clearcolor = (0.95, 0.96, 0.98, 1)
        self.cfg = load_config()
        self._worker = None
        self._auto_job = None
        self.auto_enabled = False
        root = self._build_ui()
        # 恢复自动打卡状态
        if self.cfg.get("auto_enable"):
            self._toggle_auto(self.cfg.get("auto_enable"),
                              self.cfg.get("auto_start"),
                              self.cfg.get("auto_end"))
        return root

    # --------------------------------------------------------------
    def _build_ui(self):
        outer = ScrollView()
        box = BoxLayout(orientation="vertical", padding=20, spacing=12,
                        size_hint_y=None)
        box.bind(minimum_height=box.setter("height"))
        outer.add_widget(box)

        box.add_widget(Label(text="[b]工学云自动打卡[/b]", markup=True,
                             size_hint_y=None, height=40, font_size=22,
                             color=(0.1, 0.2, 0.4, 1)))

        # ---- 账号区 ----
        box.add_widget(Label(text="账号设置", size_hint_y=None, height=28,
                             bold=True, color=(0.2, 0.3, 0.5, 1)))
        self.in_phone = self._field(box, "手机号")
        self.in_phone.text = self.cfg.get("phone", "")
        self.in_pwd = self._field(box, "密码", password=True)
        self.in_pwd.text = self.cfg.get("password", "")
        self.in_token = self._field(box, "Token（可选，留空自动登录）")
        self.in_token.text = self.cfg.get("token", "")

        # ---- 打卡地点区 ----
        box.add_widget(Label(text="打卡地点", size_hint_y=None, height=28,
                             bold=True, color=(0.2, 0.3, 0.5, 1)))
        self.in_addr = self._field(box, "详细地址", text=self.cfg.get("address", ""))
        self.in_province = self._field(box, "省份", text=self.cfg.get("province", ""))
        self.in_city = self._field(box, "城市", text=self.cfg.get("city", ""))
        self.in_lat = self._field(box, "纬度 latitude", text=self.cfg.get("latitude", ""))
        self.in_lng = self._field(box, "经度 longitude", text=self.cfg.get("longitude", ""))

        # ---- 手动打卡按钮 ----
        btnrow = BoxLayout(size_hint_y=None, height=56, spacing=12)
        btn_start = Button(text="上班打卡", size_hint_x=1,
                           background_normal="",
                           background_color=(0.2, 0.6, 0.3, 1))
        btn_start.bind(on_release=lambda x: self._do_clock(True))
        btn_end = Button(text="下班打卡", size_hint_x=1,
                         background_normal="",
                         background_color=(0.8, 0.4, 0.2, 1))
        btn_end.bind(on_release=lambda x: self._do_clock(False))
        btnrow.add_widget(btn_start)
        btnrow.add_widget(btn_end)
        box.add_widget(btnrow)

        # ---- 定时打卡 ----
        box.add_widget(Label(text="定时自动打卡", size_hint_y=None, height=28,
                             bold=True, color=(0.2, 0.3, 0.5, 1)))
        self.in_auto_start = self._field(box, "上班打卡时间 (HH:MM)",
                                         text=self.cfg.get("auto_start", "08:50"))
        self.in_auto_end = self._field(box, "下班打卡时间 (HH:MM)",
                                       text=self.cfg.get("auto_end", "17:30"))
        self.btn_auto = ToggleButton(text="启用自动打卡", size_hint_y=None,
                                     height=50,
                                     background_normal="",
                                     background_color=(0.3, 0.5, 0.8, 1))
        self.btn_auto.bind(on_release=self._on_toggle_auto)
        box.add_widget(self.btn_auto)

        # ---- 保存与测试 ----
        row2 = BoxLayout(size_hint_y=None, height=56, spacing=12)
        btn_save = Button(text="保存配置", size_hint_x=1,
                          background_normal="",
                          background_color=(0.5, 0.5, 0.55, 1))
        btn_save.bind(on_release=lambda x: self._save())
        btn_test = Button(text="测试登录", size_hint_x=1,
                          background_normal="",
                          background_color=(0.5, 0.4, 0.6, 1))
        btn_test.bind(on_release=lambda x: self._test_login())
        row2.add_widget(btn_save)
        row2.add_widget(btn_test)
        box.add_widget(row2)

        # ---- 日志区 ----
        box.add_widget(Label(text="运行日志", size_hint_y=None, height=28,
                             bold=True, color=(0.2, 0.3, 0.5, 1)))
        self.log = TextInput(text="", readonly=True, size_hint_y=None,
                             height=200, multiline=True,
                             background_color=(1, 1, 1, 1),
                             foreground_color=(0.1, 0.1, 0.1, 1))
        box.add_widget(self.log)

        return outer

    def _field(self, parent, hint, text="", password=False):
        ti = TextInput(hint_text=hint, text=text, password=password,
                       multiline=False, size_hint_y=None, height=48,
                       background_color=(1, 1, 1, 1),
                       foreground_color=(0.1, 0.1, 0.1, 1))
        parent.add_widget(ti)
        return ti

    # --------------------------------------------------------------
    def _log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.text = "[%s] %s\n%s" % (ts, msg, self.log.text)

    def _save(self):
        self.cfg.update({
            "phone": self.in_phone.text.strip(),
            "password": self.in_pwd.text.strip(),
            "token": self.in_token.text.strip(),
            "address": self.in_addr.text.strip(),
            "province": self.in_province.text.strip(),
            "city": self.in_city.text.strip(),
            "latitude": self.in_lat.text.strip(),
            "longitude": self.in_lng.text.strip(),
            "auto_start": self.in_auto_start.text.strip(),
            "auto_end": self.in_auto_end.text.strip(),
        })
        save_config(self.cfg)
        self._log("配置已保存")

    def _make_client(self):
        self._save()
        return GxyClient(
            phone=self.cfg["phone"],
            password=self.cfg["password"],
            token=self.cfg.get("token", ""),
            address=self.cfg["address"],
            latitude=self.cfg["latitude"],
            longitude=self.cfg["longitude"],
            province=self.cfg["province"],
            city=self.cfg["city"],
        )

    def _run_async(self, fn, done=None):
        if self._worker and self._worker.is_alive():
            self._log("已有任务在运行中，请稍候")
            return
        def _wrap():
            try:
                fn()
            finally:
                if done:
                    Clock.schedule_once(lambda dt: done(), 0)
        self._worker = threading.Thread(target=_wrap, daemon=True)
        self._worker.start()

    def _do_clock(self, is_start):
        def task():
            try:
                c = self._make_client()
                title, msg = c.clock_in(is_start)
                self._log("%s\n%s" % (title, msg))
            except GxyError as e:
                self._log("错误: %s" % e)
            except Exception as e:
                self._log("异常: %s" % e)
        self._run_async(task)

    def _test_login(self):
        def task():
            try:
                c = self._make_client()
                c.login()
                c.get_plan()
                self._log("登录成功！昵称: %s，计划: %s" %
                          (c.nike_name, c.plan_name))
            except GxyError as e:
                self._log("登录失败: %s" % e)
            except Exception as e:
                self._log("异常: %s" % e)
        self._run_async(task)

    # --------------------------------------------------------------
    def _on_toggle_auto(self, *args):
        self._toggle_auto(self.btn_auto.state == "down",
                          self.in_auto_start.text.strip(),
                          self.in_auto_end.text.strip())

    def _toggle_auto(self, enable, start_hhmm, end_hhmm):
        self._save()
        if self._auto_job:
            self._auto_job.cancel()
            self._auto_job = None
        self.auto_enabled = False
        self.btn_auto.state = "normal"
        self.cfg["auto_enable"] = False
        save_config(self.cfg)

        if not enable:
            self._log("自动打卡已关闭")
            return

        self.btn_auto.state = "down"
        self.auto_enabled = True
        self.cfg["auto_enable"] = True
        save_config(self.cfg)

        self._auto_job = Clock.schedule_interval(self._auto_check, 60)
        self._log("自动打卡已启用（上班 %s / 下班 %s）" % (start_hhmm, end_hhmm))

    def _auto_check(self, dt):
        now = datetime.datetime.now()
        hhmm = now.strftime("%H:%M")
        start = self.cfg.get("auto_start", "08:50")
        end = self.cfg.get("auto_end", "17:30")
        if hhmm == start:
            self._log("触发定时上班打卡")
            self._do_clock(True)
        elif hhmm == end:
            self._log("触发定时下班打卡")
            self._do_clock(False)


if __name__ == "__main__":
    GxyApp().run()
