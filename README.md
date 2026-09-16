# 工学云自动打卡 (Gxy Auto Clock-In)

基于 Kivy 的工学云（MoGuDing）自动打卡 Android App。

## 功能
- 账号登录 / Token 免密
- 手动上班 / 下班打卡
- 定时自动打卡（可设上班、下班时间）
- 打卡地点（地址 / 省市 / 经纬度）配置
- 本地日志 + 配置持久化

## 文件
- `main.py` — Kivy GUI
- `gxy_api.py` — 工学云打卡 API 封装（登录 / 计划 / 打卡）
- `buildozer.spec` — 编译配置

## 云编译（GitHub Actions）
推送代码到本仓库后，`Build Android APK` workflow 会自动用 buildozer 编译，
APK 作为 artifact (`gxy-apk`) 上传，可到 Actions 页面下载。

## 本地编译（x86 电脑）
```bash
pip install buildozer cython
buildozer android debug
```
