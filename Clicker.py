"""
连点器主程序 - Interception 版本
使用标准库实现全局按键轮询和日志记录。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import queue
import logging
import sys
import time
from pathlib import Path
import threading
import argparse

from InterceptionCore import InterceptionCore
from ConfigManager import ConfigManager
from ActionScript import (
    ActionScriptManager,
    ActionExecutor,
    ClickAction,
    MoveAction,
    KeyAction,
    WaitAction,
)


VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_DELETE = 0x2E
VK_0 = 0x30
VK_1 = 0x31
VK_2 = 0x32
VK_3 = 0x33
VK_4 = 0x34
VK_5 = 0x35
VK_6 = 0x36
VK_7 = 0x37
VK_8 = 0x38
VK_9 = 0x39



WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
HC_ACTION = 0


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_uint32),
        ("scanCode", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("time", ctypes.c_uint32),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def setup_logger():
    """配置日志。"""
    data_dir = get_app_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(data_dir / "clicker.log", encoding="utf-8"),
        ],
    )


def key_pressed(vk_code: int) -> bool:
    """检测虚拟按键是否被按下。"""
    return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)


class GlobalHotkeyListener:
    """全局热键监听器。

    仅记录键盘事件，不会拦截按键，所以游戏原本热键功能仍然保留。
    """

    def __init__(self):
        self._queue: queue.Queue[tuple[str, int]] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._hook = None
        self._proc = None
        self._pressed_keys: set[int] = set()
        self._logger = logging.getLogger("hotkey_listener")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread_id is not None:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        self._thread_id = None

    def clear(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def get_event(self, timeout: float = 0.05):
        try:
            ev = self._queue.get(timeout=timeout)
            try:
                self._logger.debug("hotkey consumer: get_event %s", ev)
            except Exception:
                pass
            return ev
        except queue.Empty:
            return None

    def _create_proc(self):
        user32 = ctypes.windll.user32

        @ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p)
        def keyboard_proc(n_code, w_param, l_param):
            if n_code == HC_ACTION:
                data = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk_code = int(data.vkCode)
                if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    if vk_code not in self._pressed_keys:
                        self._pressed_keys.add(vk_code)
                        try:
                            self._logger.debug("hotkey producer: put down %s", vk_code)
                        except Exception:
                            pass
                        self._queue.put(("down", vk_code))
                elif w_param in (WM_KEYUP, WM_SYSKEYUP):
                    if vk_code in self._pressed_keys:
                        self._pressed_keys.discard(vk_code)
                        try:
                            self._logger.debug("hotkey producer: put up %s", vk_code)
                        except Exception:
                            pass
                        self._queue.put(("up", vk_code))

            return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

        return keyboard_proc

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentThreadId.restype = ctypes.c_ulong
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
        user32.UnhookWindowsHookEx.restype = ctypes.c_bool
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p]
        self._thread_id = kernel32.GetCurrentThreadId()
        self._proc = self._create_proc()
        module_handle = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._proc,
            module_handle,
            0,
        )

        if not self._hook:
            error_code = ctypes.windll.kernel32.GetLastError()
            self._logger.error("全局热键监听器启动失败，错误码=%s", error_code)
            self._thread_id = None
            return

        msg = wintypes.MSG()
        try:
            while not self._stop_event.is_set():
                result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            if self._hook:
                user32.UnhookWindowsHookEx(self._hook)
                self._hook = None
            self._pressed_keys.clear()
            self._thread_id = None


class ClickerManager:
    """连点器管理类 - 处理热键和用户交互（Interception 版）。"""

    def __init__(self):
        self.logger = logging.getLogger("clicker")
        self.clicker = InterceptionCore()
        self.action_executor = ActionExecutor()
        # 注入 clicker 引用到 action_executor，以便执行器能读取运行时配置（例如 move_mouse）
        try:
            self.action_executor.clicker = self.clicker
        except Exception:
            pass
        self.action_manager = ActionScriptManager(get_app_dir() / "data")
        self.hotkey_listener = GlobalHotkeyListener()
        self.running = True
        self.listening = False  # 标记是否在监听热键
        # 倒计时状态：当程序/脚本在短暂倒计时后启动时，设置为结束时间戳
        self.countdown_end: float | None = None
        self.countdown_label: str | None = None
        # 当前脚本会话信息（供 GUI 查询）
        self.current_script_name: str | None = None
        self.script_running: bool = False
        self.script_paused: bool = False
        self._script_session_lock = threading.Lock()
        self._script_session_thread: threading.Thread | None = None
        self._script_session_stop_event: threading.Event | None = None
        self._script_session_pause_event: threading.Event | None = None

        self.logger.info("连点器管理器已初始化")

    def _on_start(self):
        if not self.clicker.running:
            self.logger.info("连点器将在 3 秒后启动，请切换到游戏窗口...")
            print("\n⏳ 连点器将在 3 秒后启动...")
            # 设置倒计时信息供 GUI 查询
            try:
                self.countdown_end = time.time() + 3
                self.countdown_label = "连点器即将启动"
            except Exception:
                self.countdown_end = None
                self.countdown_label = None
            for countdown in range(3, 0, -1):
                print(f"   倒计时: {countdown}...")
                time.sleep(1)

            # 清除倒计时并启动
            self.countdown_end = None
            self.countdown_label = None
            self.clicker.start()
            self.logger.info("连点器已启动")
            print("✓ 连点器已启动！")
        elif self.clicker.is_paused():
            # 旧的全局定时逻辑已移除，脚本层面的定时请使用 timed 动作

            self.logger.info("连点器将在 3 秒后恢复，请切换到游戏窗口...")
            print("\n⏳ 连点器将在 3 秒后恢复...")
            try:
                self.countdown_end = time.time() + 3
                self.countdown_label = "连点器将恢复运行"
            except Exception:
                self.countdown_end = None
                self.countdown_label = None
            for countdown in range(3, 0, -1):
                print(f"   倒计时: {countdown}...")
                time.sleep(1)

            self.countdown_end = None
            self.countdown_label = None
            if self.clicker.resume():
                print("▶ 连点器已恢复！")

    

    def _on_stop(self):
        if self.clicker.running:
            self.clicker.stop()
            self.logger.info("连点器已停止")

    def _on_exit(self):
        if self.clicker.running:
            self.clicker.stop()
        self.listening = False
        self.logger.info("已退出热键监听，返回主菜单")

    def _on_stats(self):
        stats = self.clicker.get_stats()
        self.logger.info("========== 连点器统计信息 ==========")
        self.logger.info("状态: %s", "运行中" if stats["running"] else "已停止")
        self.logger.info("总点击次数: %s", stats["click_count"])
        self.logger.info("点击中心: (%s, %s)", stats["center_x"], stats["center_y"])
        self.logger.info("随机移动半径: %spx", stats["radius"])
        self.logger.info("点击间隔: %sms", stats["click_interval"])
        self.logger.info("按压持续时间: %sms", stats["hold_duration"])
        self.logger.info("时间抖动范围: %sms", stats["jitter_range"])
        # 旧的全局定时模式已废弃，使用脚本层面的 timed 动作
        self.logger.info("暂停状态: %s", "是" if stats.get("paused") else "否")
        if "duration" in stats:
            self.logger.info("运行时长: %.2f秒", stats["duration"])
            self.logger.info("平均频率: %.2f次/秒", stats["clicks_per_second"])
        self.logger.info("====================================")

    def _stop_active_script_session(self, wait_timeout: float = 5.0) -> bool:
        """停止当前正在运行的脚本会话，并尽量等待其退出。"""
        with self._script_session_lock:
            active_thread = self._script_session_thread
            stop_event = self._script_session_stop_event
            pause_event = self._script_session_pause_event

        if active_thread is None:
            return True

        if stop_event is not None:
            stop_event.set()
        if pause_event is not None:
            pause_event.set()

        if active_thread.is_alive() and active_thread is not threading.current_thread():
            active_thread.join(timeout=wait_timeout)

        alive = active_thread.is_alive()
        if alive:
            self.logger.warning("旧脚本会话未能在 %.1f 秒内退出", wait_timeout)
            return False

        with self._script_session_lock:
            if self._script_session_thread is active_thread:
                self._script_session_thread = None
                self._script_session_stop_event = None
                self._script_session_pause_event = None

        return True

    def _run_script_session(self, script_name: str, actions) -> None:
        """以和连点器类似的方式运行动作脚本。"""
        if not self._stop_active_script_session():
            print(f"❌ 旧脚本会话未能及时退出，已取消启动新脚本: {script_name}")
            return

        stop_event = threading.Event()
        pause_event = threading.Event()
        pause_event.set()

        worker = threading.Thread(
            target=self.action_executor.execute_sequence,
            args=(actions, stop_event, pause_event),
            daemon=True,
        )

        with self._script_session_lock:
            self._script_session_thread = worker
            self._script_session_stop_event = stop_event
            self._script_session_pause_event = pause_event

        self.logger.info("脚本将在 3 秒后启动: %s", script_name)
        print(f"\n⏳ 脚本 {script_name} 将在 3 秒后启动...")
        # 设置倒计时信息供 GUI 查询
        try:
            self.countdown_end = time.time() + 3
            self.countdown_label = f"脚本 {script_name} 即将启动"
        except Exception:
            self.countdown_end = None
            self.countdown_label = None
        for countdown in range(3, 0, -1):
            print(f"   倒计时: {countdown}...")
            time.sleep(1)
        # 清除倒计时并启动
        self.countdown_end = None
        self.countdown_label = None
        print(f"✓ 脚本已启动: {script_name}")
        # 标记脚本会话状态
        self.current_script_name = script_name
        self.script_running = True
        self.script_paused = False
        worker.start()

        print("\n【脚本热键】")
        print("  F1  - 继续脚本（暂停后使用，继续前再次等待 3 秒）")
        print("  F2  - 暂停脚本")

        paused = False
        self.hotkey_listener.start()
        self.hotkey_listener.clear()
        try:
            while worker.is_alive():
                try:
                    event = self.hotkey_listener.get_event(timeout=0.05)
                    if not event:
                        continue

                    event_type, vk_code = event
                    if event_type != "down":
                        continue

                    if vk_code == VK_F2 and not paused:
                        pause_event.clear()
                        paused = True
                        # 标记为暂停，供 GUI 查询
                        self.script_paused = True
                        self.logger.info("脚本已暂停: %s", script_name)
                        print("⏸ 脚本已暂停")

                    elif vk_code == VK_F1 and paused:
                        self.logger.info("脚本将在 3 秒后继续: %s", script_name)
                        print("\n⏳ 脚本将在 3 秒后继续执行，请切换到游戏窗口...")
                        for countdown in range(3, 0, -1):
                            if stop_event.is_set():
                                break
                            print(f"   倒计时: {countdown}...")
                            time.sleep(1)
                        if not stop_event.is_set():
                            pause_event.set()
                            paused = False
                            # 清除暂停标记
                            self.script_paused = False
                            print("▶ 脚本已继续")

                    # F4 已移除：不再通过 F4 退出脚本会话，使用 GUI 按钮或程序逻辑退出
                except Exception as e:
                    self.logger.error("脚本会话异常: %s", e)
                    stop_event.set()
                    pause_event.set()
                    break
        finally:
            self.hotkey_listener.stop()
            # 清理脚本会话状态
            with self._script_session_lock:
                if self._script_session_thread is worker:
                    self._script_session_thread = None
                    self._script_session_stop_event = None
                    self._script_session_pause_event = None
                    self.script_running = False
                    self.script_paused = False
                    self.current_script_name = None

        if stop_event.is_set():
            return

        print("✓ 脚本已执行完成")

    def show_menu(self):
        """显示主菜单。"""
        print("\n")
        print("╔════════════════════════════════════════╗")
        print("║           ROCOKINGDOM 连点器            ║")
        print("║   基于 Interception 驱动的高效点击工具   ║")
        print("╚════════════════════════════════════════╝")
        print("\n【热键控制】")
        print("  F1  - 启动连点器")
        print("  F2  - 停止连点器")
        print("  F3  - 显示统计信息")
        print("\n【默认参数】")
        print(f"  点击中心位置: ({self.clicker.config.center_x}, {self.clicker.config.center_y})")
        print(f"  随机移动半径: {self.clicker.config.radius}px")
        print(f"  点击间隔: {self.clicker.config.click_interval}ms")
        print(f"  按压持续时间: {self.clicker.config.hold_duration}ms")
        print(f"  时间抖动范围: {self.clicker.config.jitter_range}ms")
        print(f"  启动时移动鼠标到目标: {getattr(self.clicker.config, 'move_mouse', True)}")
        # 全局定时模式已移除，建议使用脚本中的 timed 动作
        print("\n")

    def interactive_config(self):
        """交互式配置。"""
        while True:
            print("\n【参数调整】(输入数字选择)")
            print("  6 - 加载配置预设")
            print("  7 - 管理已保存的配置")
            print("  8 - 动作脚本管理（创建/执行/删除脚本）")
            
            print("  0 - 开始监听热键")
            print("  m - 切换是否在每次点击前移动鼠标")
            print("  直接回车 - 进入热键监听")

            choice = input("请选择操作: ").strip()
            if not choice or choice == "0":
                return

            if choice == "6":
                self.load_config_menu()
            elif choice.lower() == 'm':
                cur = getattr(self.clicker.config, 'move_mouse', True)
                self.clicker.config.move_mouse = not cur
                ConfigManager.save_config(self.clicker.config, "default")
                print(f"✓ move_mouse 已设置为 {self.clicker.config.move_mouse}")
            elif choice == "7":
                self.manage_configs_menu()
            elif choice == "8":
                self.action_script_menu()
            # 已移除绑定目标窗口的交互菜单，改用脚本或手动绑定
            else:
                self.logger.warning("选择无效，请重新输入")

    def load_config_menu(self):
        """加载预设配置菜单"""
        presets = ConfigManager.list_presets()
        print("\n可用预设:")
        for i, (key, name) in enumerate(presets, 1):
            print(f"  {i}. {name} ({key})")
        choice = input("选择预设编号 (按 Enter 返回): ").strip()
        if not choice:
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(presets):
                key = presets[idx][0]
                cfg = ConfigManager.load_preset(key)
                self.clicker.config = cfg
                ConfigManager.save_config(self.clicker.config, "default")
                print(f"✓ 预设 '{presets[idx][1]}' 已加载并设置为当前配置")
            else:
                print("❌ 编号无效")
        except ValueError:
            print("❌ 输入错误")

    def manage_configs_menu(self):
        """管理已保存的配置（加载/删除）"""
        while True:
            configs = ConfigManager.list_configs()
            print("\n已保存的配置:")
            for i, name in enumerate(configs, 1):
                print(f"  {i}. {name}")
            print("  d<number> - 删除配置，例如 d2")
            print("  b - 返回")
            choice = input("选择操作或编号: ").strip()
            if not choice or choice.lower() == 'b':
                return
            if choice.startswith('d'):
                try:
                    idx = int(choice[1:]) - 1
                    if 0 <= idx < len(configs):
                        name = configs[idx]
                        if ConfigManager.delete_config(name):
                            print(f"✓ 已删除配置: {name}")
                        else:
                            print("❌ 删除失败")
                    else:
                        print("❌ 编号无效")
                except ValueError:
                    print("❌ 输入错误")
                continue
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(configs):
                    name = configs[idx]
                    cfg = ConfigManager.load_config(name)
                    self.clicker.config = cfg
                    ConfigManager.save_config(self.clicker.config, "default")
                    print(f"✓ 已加载配置: {name}")
                    return
                else:
                    print("❌ 编号无效")
            except ValueError:
                print("❌ 输入错误")

    def action_script_menu(self):
        """动作脚本管理（列出/执行/创建/删除）"""
        while True:
            scripts = self.action_manager.list_scripts()
            print("\n动作脚本:")
            if scripts:
                for i, s in enumerate(scripts, 1):
                    print(f"  {i}. {s}")
            else:
                print("  (无脚本)")

            print("  e<number> - 执行脚本，例如 e1")
            print("  c - 创建简单点击脚本")
            print("  d<number> - 删除脚本，例如 d1")
            print("  b - 返回")
            choice = input("选择操作: ").strip()
            if not choice or choice.lower() == 'b':
                return
            if choice.lower().startswith('e'):
                try:
                    idx = int(choice[1:]) - 1
                    if 0 <= idx < len(scripts):
                        name = scripts[idx]
                        actions = self.action_manager.load_script(name)
                        if actions:
                            self._run_script_session(name, actions)
                        else:
                            print("❌ 加载脚本失败")
                    else:
                        print("❌ 编号无效")
                except ValueError:
                    print("❌ 输入错误")
                continue
            if choice.lower().startswith('d'):
                try:
                    idx = int(choice[1:]) - 1
                    if 0 <= idx < len(scripts):
                        name = scripts[idx]
                        path = self.action_manager.scripts_dir / f"{name}.json"
                        try:
                            path.unlink()
                            print(f"✓ 已删除脚本: {name}")
                        except Exception as e:
                            print("❌ 删除失败:", e)
                    else:
                        print("❌ 编号无效")
                except ValueError:
                    print("❌ 输入错误")
                continue
            if choice.lower() == 'c':
                try:
                    name = input("脚本名 (不含扩展名): ").strip()
                    if not name:
                        print("❌ 名称不能为空")
                        continue
                    x = int(input("点击 X 坐标: "))
                    y = int(input("点击 Y 坐标: "))
                    hold = int(input("按住时长 ms (默认100): ") or 100)
                    action = ClickAction(x=x, y=y, hold_ms=hold)
                    self.action_manager.save_script(name, [action])
                    print(f"✓ 已创建脚本: {name}")
                except ValueError:
                    print("❌ 输入错误")
                continue

    # 目标窗口绑定交互已移除（使用脚本或手动绑定目标窗口）

    # Delete + 0..9 快捷键处理已移除（GUI 操作替代）

    def listen_hotkeys(self):
        """监听热键。"""
        self.listening = True
        self.logger.info("开始监听热键...")

        self.hotkey_listener.start()
        self.hotkey_listener.clear()
        try:
            while self.listening:
                try:
                    event = self.hotkey_listener.get_event(timeout=0.05)
                    if not event:
                        continue

                    event_type, vk_code = event

                    if event_type != "down":
                        continue

                    if vk_code == VK_F1:
                        self._on_start()
                        continue

                    if vk_code == VK_F2:
                        self._on_stop()
                        continue

                    if vk_code == VK_F3:
                        self._on_stats()
                        continue

                    # F4 与 Delete+数字 快捷键已移除；所有脚本管理请使用 GUI 控件或命令行接口。

                except Exception as e:
                    self.logger.error("热键监听异常: %s", e)
                    time.sleep(0.1)
        finally:
            self.hotkey_listener.stop()

    def run_menu_loop(self):
        """主菜单循环。"""
        self.show_menu()
        self.interactive_config()
        self.logger.info("连点器已准备就绪，监听热键中...")

        try:
            self.listen_hotkeys()
        except KeyboardInterrupt:
            self.logger.info("收到中断信号")

        print("\n")
        print("╔════════════════════════════════════════╗")
        print("║           已返回主菜单                  ║")
        print("╚════════════════════════════════════════╝")
        choice = input("是否继续? [y/n]: ").strip().lower()
        if choice != 'y':
            self.running = False

        ConfigManager.save_config(self.clicker.config, "default")

    def run(self):
        """启动程序。"""
        setup_logger()
        self.clicker.config = ConfigManager.load_config("default")
        self.logger.info("=" * 50)
        self.logger.info("连点器启动（Interception 版）")
        self.logger.info("=" * 50)
        
        try:
            while self.running:
                self.run_menu_loop()
        
        except Exception as e:
            self.logger.error("程序异常: %s", e)
        finally:
            # 清理
            if self.clicker.running:
                self.clicker.stop()
            self.logger.info("连点器已关闭")


def main():
    """主入口"""
    try:
        parser = argparse.ArgumentParser(description="RocoKingdom Clicker")
        parser.add_argument('--gui', action='store_true', help='启动图形界面')
        args = parser.parse_args()
        # 如果是打包后的可执行文件（frozen），默认打开 GUI 窗口以匹配发布版行为
        if getattr(sys, 'frozen', False) and not args.gui:
            args.gui = True

        if args.gui:
            # 延迟导入 GUI，以避免在非 GUI 模式下引入额外依赖
            try:
                import gui
                gui.start_gui()
                return
            except Exception as e:
                logging.error("启动 GUI 失败: %s", e)
                # 回退到 CLI 模式

        manager = ClickerManager()
        manager.run()
    except Exception as e:
        logging.error("致命错误: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
