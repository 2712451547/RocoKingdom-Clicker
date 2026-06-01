from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox


_window_config = None


class _DesktopWindow:
    def __init__(self, title: str, js_api, width: int, height: int):
        self.title = title
        self.js_api = js_api
        self.width = width
        self.height = height
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(1400, 860)
        self.root.configure(bg="#f3f6fb")

        self.status_var = tk.StringVar(value="准备就绪")
        self.move_mouse_var = tk.BooleanVar(value=False)

        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#10233b", background="#f3f6fb")
        style.configure("Sub.TLabel", font=("Segoe UI", 10), foreground="#4b5b74", background="#f3f6fb")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=8)

        header = ttk.Frame(self.root, padding=(18, 16, 18, 8))
        header.pack(fill="x")
        ttk.Label(header, text="RocoKingdom Clicker", style="Header.TLabel").pack(anchor="w")

        body = ttk.Frame(self.root, padding=(18, 8, 18, 18))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=4)
        body.columnconfigure(1, weight=2)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(body, text="控制", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.configure(width=430)
        left.grid_propagate(False)

        center = ttk.LabelFrame(body, text="动作脚本", padding=12)
        center.grid(row=0, column=1, sticky="nsew", padx=(0, 12))
        center.configure(width=560)
        center.grid_propagate(False)
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        right = ttk.LabelFrame(body, text="当前配置", padding=12)
        right.grid(row=0, column=2, sticky="nsew")
        right.configure(width=260)
        right.grid_propagate(False)
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.start_stop_btn = ttk.Button(left, text="启动 / 停止", style="Primary.TButton", command=self.on_start_stop)
        self.start_stop_btn.pack(fill="x", pady=(0, 10))

        move_row = ttk.Frame(left)
        move_row.pack(fill="x", pady=(0, 10))
        self.move_mouse_check = ttk.Checkbutton(
            move_row,
            text="控制鼠标移动（启用时执行脚本中的移动/位置指令）",
            variable=self.move_mouse_var,
            command=self.on_toggle_move_mouse,
        )
        self.move_mouse_check.pack(anchor="w")

        ttk.Label(left, text="当前选择脚本").pack(anchor="w", pady=(8, 2))
        self.selected_script_var = tk.StringVar(value="(未选择)")
        ttk.Label(left, textvariable=self.selected_script_var, foreground="#10233b").pack(anchor="w")

        ttk.Label(left, text="状态").pack(anchor="w", pady=(8, 2))
        ttk.Label(left, textvariable=self.status_var, foreground="#125c2b").pack(anchor="w")

        ttk.Label(left, text="快捷键").pack(anchor="w", pady=(12, 2))
        ttk.Label(
            left,
            text="F1 继续脚本\nF2 暂停脚本\n（脚本启动/停止请使用左侧按钮或脚本列表）",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", fill="x")

        ttk.Button(left, text="刷新", command=self.refresh_all).pack(fill="x", pady=(16, 0))

        self.script_list = tk.Listbox(center, activestyle="dotbox", height=18)
        self.script_list.grid(row=0, column=0, sticky="nsew")
        # 立即响应选择，避免依赖轮询刷新延迟
        self.script_list.bind('<<ListboxSelect>>', self._on_list_select)
        script_scroll = ttk.Scrollbar(center, orient="vertical", command=self.script_list.yview)
        script_scroll.grid(row=0, column=1, sticky="ns")
        self.script_list.configure(yscrollcommand=script_scroll.set)

        script_btns = ttk.Frame(center)
        script_btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        script_btns.columnconfigure(0, weight=1)
        script_btns.columnconfigure(1, weight=1)
        script_btns.columnconfigure(2, weight=1)
        ttk.Button(script_btns, text="执行", command=self.on_run_script).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(script_btns, text="删除", command=self.on_delete_script).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(script_btns, text="刷新", command=self.refresh_scripts).grid(row=0, column=2, sticky="ew", padx=(6, 0))

        self.config_text_widget = tk.Text(right, height=24, width=26, wrap="word", relief="flat", bg="#f7f9fc", fg="#10233b")
        self.config_text_widget.grid(row=0, column=0, sticky="nsew")
        self.config_text_widget.configure(state="disabled")

        footer = ttk.Frame(self.root, padding=(18, 0, 18, 14))
        footer.pack(fill="x")
        ttk.Label(footer, text="F1/F2 仍由程序后台热键处理", style="Sub.TLabel").pack(anchor="w")

        self.root.after(500, self._refresh_loop)

    def _selected_script(self) -> str | None:
        selection = self.script_list.curselection()
        if not selection:
            return None
        return self.script_list.get(selection[0])

    def on_start_stop(self):
        try:
            self.js_api.toggle_start_stop()
            self.root.after(300, self.refresh_status)
        except Exception as exc:
            messagebox.showerror("操作失败", str(exc))

    def on_toggle_move_mouse(self):
        try:
            new_value = self.js_api.toggle_move_mouse()
            self.move_mouse_var.set(bool(new_value))
            self.refresh_status()
        except Exception as exc:
            messagebox.showerror("操作失败", str(exc))

    def on_run_script(self):
        name = self._selected_script()
        if not name:
            messagebox.showinfo("提示", "先选择一个脚本")
            return
        try:
            self.js_api.run_script(name)
            self.root.after(500, self.refresh_status)
        except Exception as exc:
            messagebox.showerror("执行失败", str(exc))

    def on_delete_script(self):
        name = self._selected_script()
        if not name:
            messagebox.showinfo("提示", "先选择一个脚本")
            return
        if not messagebox.askyesno("确认删除", f"确定删除脚本 {name} 吗？"):
            return
        try:
            if self.js_api.delete_script(name):
                self.refresh_scripts()
            else:
                messagebox.showwarning("删除失败", "脚本删除失败或文件不存在")
        except Exception as exc:
            messagebox.showerror("删除失败", str(exc))

    def refresh_scripts(self):
        try:
            scripts = self.js_api.list_scripts() or []
        except Exception:
            scripts = []

        current = self._selected_script()
        self.script_list.delete(0, tk.END)
        for name in scripts:
            self.script_list.insert(tk.END, name)

        if current and current in scripts:
            idx = scripts.index(current)
            self.script_list.selection_set(idx)
            self.script_list.see(idx)

    def _on_list_select(self, event=None):
        """Listbox selection handler — update selected label immediately."""
        try:
            sel = self._selected_script()
            self.selected_script_var.set(sel if sel else "(未选择)")
            # 轻刷新状态以同步配置面板（但不强制完整刷新脚本列表）
            self.root.after(150, self.refresh_status)
        except Exception:
            pass

    def refresh_status(self):
        try:
            status = self.js_api.get_status() or {}
        except Exception:
            status = {}

        running = bool(status.get("running"))

        # 当前选择脚本栏仅显示脚本名，不混入运行状态。
        sel = self._selected_script()
        self.selected_script_var.set(sel if sel else "(未选择)")

        script_running = bool(status.get('script_running'))
        script_paused = bool(status.get('script_paused'))

        # 状态栏统一承载运行/暂停/倒计时信息。
        countdown = status.get('countdown')
        countdown_label = status.get('countdown_label')
        if countdown is not None and countdown > 0:
            label = countdown_label or "即将启动"
            status_text = f"{label} ({countdown}s)"
        elif script_running and script_paused:
            status_text = "脚本已暂停"
        elif script_running:
            status_text = "脚本运行中"
        elif running:
            status_text = "连点器运行中"
        else:
            status_text = "已停止"

        self.status_var.set(status_text)
        self.start_stop_btn.configure(text="停止" if running else "启动")
        self.move_mouse_var.set(bool(status.get("move_mouse", False)))

        # 格式化并展示精简字段（更适合人类阅读）
        lines = []
        lines.append(f"运行状态: {status_text}")
        ci = status.get('click_interval')
        if ci is not None:
            lines.append(f"点击间隔: {ci} ms")
        hd = status.get('hold_duration')
        if hd is not None:
            lines.append(f"按压时长: {hd} ms")
        mm = status.get('move_mouse')
        lines.append(f"控制鼠标移动: {'已启用' if mm else '已禁用'}")

        if mm:
            cx = status.get('center_x')
            cy = status.get('center_y')
            if cx is not None and cy is not None:
                lines.append(f"点击中心: ({cx}, {cy})")
            r = status.get('radius')
            if r is not None:
                lines.append(f"随机半径: {r} px")

        ignored = status.get('ignored_moves', 0)
        if ignored:
            lines.append(f"已忽略的移动指令: {ignored}")

        config_text = "\n".join(lines)
        self.config_text_widget.configure(state="normal")
        self.config_text_widget.delete("1.0", tk.END)
        self.config_text_widget.insert("1.0", config_text)
        self.config_text_widget.configure(state="disabled")

    def refresh_all(self):
        self.refresh_scripts()
        self.refresh_status()

    def _refresh_loop(self):
        self.refresh_status()
        self.root.after(2000, self._refresh_loop)

    def run(self):
        self.root.mainloop()


def create_window(title, url=None, js_api=None, width=1480, height=900):
    global _window_config
    _window_config = {
        "title": title,
        "js_api": js_api,
        "width": width,
        "height": height,
    }
    return _window_config


def start():
    if not _window_config:
        raise RuntimeError("No window has been created")
    if _window_config["js_api"] is None:
        raise RuntimeError("js_api is required")

    app = _DesktopWindow(
        title=_window_config["title"],
        js_api=_window_config["js_api"],
        width=_window_config["width"],
        height=_window_config["height"],
    )
    app.run()
