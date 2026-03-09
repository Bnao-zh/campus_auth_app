#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, sys, json, threading, subprocess, urllib.request, webbrowser
os.environ.setdefault('PYSTRAY_BACKEND', 'appindicator')
import tkinter as tk
from tkinter import ttk, messagebox

import pystray
from pystray import MenuItem as item
from PIL import Image

APP_NAME = "Campus Auth GUI"
CFG_DIR = os.path.join(os.path.expanduser("~"), ".config", "campus_auth_gui")
CFG_FILE = os.path.join(CFG_DIR, "config.json")
DETECT_URL = "http://connect.rom.miui.com/generate_204"
PORTAL_KEY = "enet.10000.gd.cn"
JAVA_URL = "https://www.oracle.com/java/technologies/downloads/"

def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)

def java_major():
    try:
        p = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=8)
        txt = (p.stdout or "") + "\n" + (p.stderr or "")
        m = re.search(r'version\s+"([^"]+)"', txt)
        if not m: return None
        v = m.group(1)
        if v.startswith("1."): return int(v.split(".")[1])
        return int(v.split(".")[0])
    except:
        return None

def ensure_java_24():
    m = java_major()
    if m is None or m < 24:
        msg = (
            "当前未检测到可用的 Java 24 及以上环境。"
            f"检测结果: Java {m}"
            "点击【确定】将打开 Java 官方下载页面"
            "点击【取消】将直接退出程序。"
        )
        ok = messagebox.askokcancel("Java 环境不满足（需要 >= 24）", msg)
        if ok:
            webbrowser.open_new(JAVA_URL)
        return False
    return True

def make_icon():
    return Image.open(resource_path("tray.png")).convert("RGBA")

class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("760x520")

        self.proc = None
        self.auto_job = None
        self.tray_icon = None
        self.quitting = False

        self.user = tk.StringVar()
        self.pwd = tk.StringVar()
        self.save_pwd = tk.BooleanVar(value=True)
        self.auto = tk.BooleanVar(value=False)
        self.interval = tk.StringVar(value="60")

        self.ui()
        self.load_cfg()
        if not ensure_java_24():
            self.root.after(100, self.root.destroy)
            return
        self.init_tray()

    def ui(self):
        f = ttk.Frame(self.root, padding=12); f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1); f.rowconfigure(7, weight=1)

        ttk.Label(f, text="账号").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.user).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(f, text="密码").grid(row=1, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.pwd, show="*").grid(row=1, column=1, sticky="ew", pady=4)


        ttk.Checkbutton(f, text="保存账号密码", variable=self.save_pwd).grid(row=3, column=0, sticky="w")
        ttk.Checkbutton(f, text="自动检测并认证", variable=self.auto, command=self.toggle_auto).grid(row=3, column=1, sticky="w")

        ttk.Label(f, text="检测间隔(秒)").grid(row=4, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.interval, width=10).grid(row=4, column=1, sticky="w", pady=4)

        b = ttk.Frame(f); b.grid(row=5, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(b, text="检测校园网", command=self.detect_now).pack(side="left", padx=4)
        ttk.Button(b, text="启动认证", command=self.start_auth).pack(side="left", padx=4)
        ttk.Button(b, text="停止认证", command=self.stop_auth).pack(side="left", padx=4)
        ttk.Button(b, text="保存配置", command=self.save_cfg).pack(side="left", padx=4)
        ttk.Button(b, text="退出程序", command=self.quit_app).pack(side="left", padx=4)

        self.status = ttk.Label(f, text="状态：待机"); self.status.grid(row=6, column=0, columnspan=2, sticky="w")
        self.logbox = tk.Text(f, height=18); self.logbox.grid(row=7, column=0, columnspan=2, sticky="nsew")

        self.root.protocol("WM_DELETE_WINDOW", self.on_click_close)

    def init_tray(self):
        try:
            # Linux(AppIndicator) 一般通过右键菜单操作最稳定
            menu = pystray.Menu(
                item("显示窗口", self._tray_show, default=True),
                item("退出程序", self._tray_quit)
            )
            self.tray_icon = pystray.Icon("campus-auth", make_icon(), "", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
            self.log("托盘已启动：右键图标可显示窗口或退出")
        except Exception as e:
            self.log(f"托盘启动失败：{e}")

    def _tray_show(self, icon, menu_item):
        self.root.after(0, self.show_window)

    def _tray_quit(self, icon, menu_item):
        self.root.after(0, self.quit_app)

    def on_click_close(self):
        # 点X时隐藏，不退出
        self.hide_window()

    def hide_window(self):
        self.root.withdraw()
        self.set_status("后台运行中（托盘）")

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.attributes("-topmost", True)
            self.root.after(80, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass
        self.root.focus_force()

    def log(self, s): self.logbox.insert("end", s + "\n"); self.logbox.see("end")
    def set_status(self, s): self.status.config(text="状态：" + s)

    def detect(self):
        try:
            req = urllib.request.Request(DETECT_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                u, c = r.geturl(), r.getcode()
            if PORTAL_KEY in u: return True, f"检测到门户: {u}"
            if c == 204: return False, "网络直连(204)，通常无需认证"
            return False, f"未检测到门户 code={c}, url={u}"
        except Exception as e:
            return False, f"检测失败: {e}"

    def detect_now(self):
        ok, msg = self.detect()
        self.log(msg)
        self.set_status("可认证" if ok else "非校园网/无需认证")

    def start_auth(self):
        if not ensure_java_24(): return
        u, p = self.user.get().strip(), self.pwd.get().strip()
        jar = resource_path("network.jar")
        if not u or not p:
            messagebox.showwarning("提示", "请输入账号密码"); return
        if not os.path.isfile(jar):
            messagebox.showerror("错误", "找不到 network.jar"); return
        if self.proc and self.proc.poll() is None:
            self.log("认证程序已在运行"); return

        ok, msg = self.detect(); self.log(msg)
        if not ok:
            self.set_status("未启动（非认证环境）"); return

        self.proc = subprocess.Popen(["java", "-jar", jar, "-u", u, "-p", p],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1)
        self.set_status("运行中")
        threading.Thread(target=self.read_output, daemon=True).start()

    def read_output(self):
        if not self.proc or not self.proc.stdout: return
        for line in self.proc.stdout:
            self.root.after(0, self.log, line.rstrip("\n"))
        self.root.after(0, self.set_status, f"已退出 code={self.proc.poll()}")

    def stop_auth(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.log("已停止认证程序")
        self.set_status("待机")

    def auto_loop(self):
        if not self.auto.get(): return
        try: sec = max(10, int(self.interval.get().strip()))
        except: sec = 60
        running = self.proc and self.proc.poll() is None
        if not running:
            ok, _ = self.detect()
            if ok: self.start_auth()
        self.auto_job = self.root.after(sec * 1000, self.auto_loop)

    def toggle_auto(self):
        if self.auto.get():
            if self.auto_job is None: self.auto_loop()
        else:
            if self.auto_job: self.root.after_cancel(self.auto_job); self.auto_job = None

    def save_cfg(self):
        os.makedirs(CFG_DIR, exist_ok=True)
        data = {
            "username": self.user.get().strip(),
            "password": self.pwd.get().strip() if self.save_pwd.get() else "",
            "save_pwd": self.save_pwd.get(),
            "auto": self.auto.get(),
            "interval": self.interval.get().strip(),
        }
        with open(CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.chmod(CFG_FILE, 0o600)
        self.log("配置已保存")

    def load_cfg(self):
        if not os.path.isfile(CFG_FILE): return
        try:
            d = json.load(open(CFG_FILE, "r", encoding="utf-8"))
            self.user.set(d.get("username", ""))
            self.pwd.set(d.get("password", ""))
            self.save_pwd.set(bool(d.get("save_pwd", True)))
            self.auto.set(bool(d.get("auto", False)))
            self.interval.set(str(d.get("interval", "60")))
        except Exception as e:
            self.log(f"加载配置失败: {e}")

    def quit_app(self):
        self.quitting = True
        self.save_cfg()
        self.stop_auth()
        if self.tray_icon:
            try: self.tray_icon.stop()
            except: pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
