"""
动作脚本模块 - 支持自定义动作序列，基于 Interception 驱动
支持动作：Click（点击）、Move（移动）、Key（按键）、Wait（等待）
"""

from __future__ import annotations

import ctypes
import json
import logging
import math
import random
import threading
import time
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional
from ctypes import wintypes


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

MAX_PATH = 260
TH32CS_SNAPPROCESS = 0x00000002
SW_RESTORE = 9
SW_SHOW = 5
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
INTERCEPTION_MAX_DEVICE = 20
INTERCEPTION_KEY_DOWN = 0x00
INTERCEPTION_KEY_UP = 0x01
INTERCEPTION_KEY_E0 = 0x02

VK_TO_SCANCODE = {
    0x08: (0x0E, False),
    0x09: (0x0F, False),
    0x0D: (0x1C, False),
    0x10: (0x2A, False),
    0x11: (0x1D, False),
    0x12: (0x38, False),
    0x13: (0x45, False),
    0x14: (0x3A, False),
    0x1B: (0x01, False),
    0x20: (0x39, False),
    0x21: (0x49, True),
    0x22: (0x51, True),
    0x23: (0x4F, True),
    0x24: (0x47, True),
    0x25: (0x4B, True),
    0x26: (0x48, True),
    0x27: (0x4D, True),
    0x28: (0x50, True),
    0x2D: (0x53, True),
    0x2E: (0x53, True),
    0x30: (0x0B, False),
    0x31: (0x02, False),
    0x32: (0x03, False),
    0x33: (0x04, False),
    0x34: (0x05, False),
    0x35: (0x06, False),
    0x36: (0x07, False),
    0x37: (0x08, False),
    0x38: (0x09, False),
    0x39: (0x0A, False),
    0x41: (0x1E, False),
    0x42: (0x30, False),
    0x43: (0x2E, False),
    0x44: (0x20, False),
    0x45: (0x12, False),
    0x46: (0x21, False),
    0x47: (0x22, False),
    0x48: (0x23, False),
    0x49: (0x17, False),
    0x4A: (0x24, False),
    0x4B: (0x25, False),
    0x4C: (0x26, False),
    0x4D: (0x32, False),
    0x4E: (0x31, False),
    0x4F: (0x18, False),
    0x50: (0x19, False),
    0x51: (0x10, False),
    0x52: (0x13, False),
    0x53: (0x1F, False),
    0x54: (0x14, False),
    0x55: (0x16, False),
    0x56: (0x2F, False),
    0x57: (0x11, False),
    0x58: (0x2D, False),
    0x59: (0x15, False),
    0x5A: (0x2C, False),
    0x60: (0x52, False),
    0x61: (0x4F, False),
    0x62: (0x50, False),
    0x63: (0x51, False),
    0x64: (0x4B, False),
    0x65: (0x4C, False),
    0x66: (0x4D, False),
    0x67: (0x47, False),
    0x68: (0x48, False),
    0x69: (0x49, False),
    0x6F: (0x35, True),
    0x70: (0x3B, False),
    0x71: (0x3C, False),
    0x72: (0x3D, False),
    0x73: (0x3E, False),
    0x74: (0x3F, False),
    0x75: (0x40, False),
    0x76: (0x41, False),
    0x77: (0x42, False),
    0x78: (0x43, False),
    0x79: (0x44, False),
    0x7A: (0x57, False),
    0x7B: (0x58, False),
    0xA0: (0x2A, False),
    0xA1: (0x36, False),
    0xA2: (0x1D, False),
    0xA3: (0x1D, True),
    0xA4: (0x38, False),
    0xA5: (0x38, True),
}


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


# Interception 结构体定义
class InterceptionMouseStroke(ctypes.Structure):
    _fields_ = [
        ("state", ctypes.c_ushort),
        ("flags", ctypes.c_ushort),
        ("rolling", ctypes.c_short),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("information", ctypes.c_uint),
    ]


class InterceptionKeyStroke(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_ushort),
        ("state", ctypes.c_ushort),
        ("information", ctypes.c_uint),
    ]


class ActionType(Enum):
    """动作类型"""
    CLICK = "click"
    MOVE = "move"
    KEY = "key"
    COMBO = "combo"
    WAIT = "wait"


@dataclass
class ClickAction:
    """点击动作"""
    x: int
    y: int
    hold_ms: int = 100  # 默认按住 100ms
    x_jitter_px: int = 0
    y_jitter_px: int = 0
    hold_jitter_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MoveAction:
    """移动动作"""
    x: int
    y: int
    duration_ms: int = 100  # 移动耗时
    x_jitter_px: int = 0
    y_jitter_px: int = 0
    duration_jitter_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class KeyAction:
    """按键动作"""
    vk_code: int
    hold_ms: int = 50
    hold_jitter_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WaitAction:
    """等待动作"""
    duration_ms: int
    duration_jitter_ms: int = 0


@dataclass
class ComboAction:
    """组合按键动作"""
    vk_codes: List[int]
    hold_ms: int = 50
    hold_jitter_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LoopAction:
    """循环动作"""
    actions: List[Any] = field(default_factory=list)
    count: int = 1
    forever: bool = False
    pause_ms: int = 0
    pause_jitter_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def find_process_by_name(process_name: str) -> int:
    """按进程名查找 PID"""
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        
        if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                if process_name.lower() in entry.szExeFile.lower():
                    return entry.th32ProcessID
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)
    
    return None


def list_windows_for_process(process_name: str) -> List[tuple]:
    """列出进程所有窗口 (hwnd, window_title)"""
    pid = find_process_by_name(process_name)
    if not pid:
        return []
    
    windows = []
    
    def enum_callback(hwnd, _):
        try:
            tid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(tid))
            if tid.value == pid:
                title_buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, title_buf, 256)
                windows.append((hwnd, title_buf.value))
        except Exception:
            pass
        return True
    
    EnumWindowsProc = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindowsW(EnumWindowsProc(enum_callback), None)
    
    return windows


class TargetWindowBinding:
    """目标窗口绑定管理"""
    
    def __init__(self, process_name: str):
        self.process_name = process_name
        self.hwnd: Optional[int] = None
        self.logger = logging.getLogger("target_window")
    
    def bind(self, hwnd: int) -> bool:
        """绑定窗口"""
        self.hwnd = hwnd
        self.logger.info("已绑定窗口: %s (hwnd=%d)", self._get_title(), hwnd)
        return True
    
    def is_bound(self) -> bool:
        """检查是否已绑定"""
        return self.hwnd is not None
    
    def activate(self) -> bool:
        """激活目标窗口（多步激活流程）"""
        if not self.is_bound():
            return False
        
        try:
            # 1. 获取目标线程和前台线程
            target_tid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(self.hwnd, ctypes.byref(target_tid))
            foreground_hwnd = user32.GetForegroundWindow()
            foreground_tid = user32.GetWindowThreadProcessId(foreground_hwnd, None)
            
            # 2. 如果不同线程，尝试 AttachThreadInput
            if foreground_tid != target_tid.value:
                user32.AttachThreadInput(foreground_tid, target_tid.value, True)
                time.sleep(0.05)
            
            # 3. 将窗口置顶并激活
            user32.BringWindowToTop(self.hwnd)
            user32.SetForegroundWindow(self.hwnd)
            user32.SetActiveWindow(self.hwnd)
            time.sleep(0.05)
            
            # 4. 分离线程
            if foreground_tid != target_tid.value:
                user32.AttachThreadInput(foreground_tid, target_tid.value, False)
            
            self.logger.debug("目标窗口激活成功")
            return True
        
        except Exception as e:
            self.logger.error("激活目标窗口失败: %s", e)
            return False
    
    def _get_title(self) -> str:
        """获取窗口标题"""
        if not self.is_bound():
            return "(未绑定)"
        try:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(self.hwnd, buf, 256)
            return buf.value
        except Exception:
            return "(获取标题失败)"
    
    def describe(self) -> str:
        """描述窗口信息"""
        return f"{self.process_name}:{self._get_title()}"


class ActionExecutor:
    """动作执行器 - 基于 Interception 驱动"""
    
    def __init__(self, target_window: TargetWindowBinding):
        self.target_window = target_window
        self.logger = logging.getLogger("action_executor")
        
        # 加载 Interception 库
        self._lib = None
        self._ctx = None
        self._device = None
        self._initialize_interception()
    
    def _initialize_interception(self):
        """初始化 Interception"""
        try:
            import os
            dll_paths = [
                os.path.join(os.path.dirname(__file__), "interception.dll"),
                "interception.dll",
            ]
            
            lib = None
            for path in dll_paths:
                try:
                    lib = ctypes.CDLL(path)
                    self.logger.info(f"加载 Interception: {path}")
                    break
                except Exception:
                    pass
            
            if lib is None:
                raise OSError("无法加载 interception.dll")
            
            self._lib = lib
            self._lib.interception_create_context.restype = ctypes.c_void_p
            self._lib.interception_destroy_context.argtypes = [ctypes.c_void_p]
            self._lib.interception_send.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint
            ]
            self._lib.interception_send.restype = ctypes.c_int
            self._lib.interception_is_keyboard.argtypes = [ctypes.c_int]
            self._lib.interception_is_keyboard.restype = ctypes.c_int
            self._lib.interception_is_mouse.argtypes = [ctypes.c_int]
            self._lib.interception_is_mouse.restype = ctypes.c_int
            
            self._ctx = self._lib.interception_create_context()
            if not self._ctx:
                raise OSError("无法创建 Interception 上下文")
            
            self._device = 11  # INTERCEPTION_MOUSE(0)
            self._keyboard_device = None
            self.logger.info("ActionExecutor Interception 已初始化")
        
        except Exception as e:
            self.logger.warning("Interception 初始化失败，将回退到用户模式: %s", e)
            self._lib = None
    
    def _send_mouse_stroke(self, stroke: InterceptionMouseStroke) -> bool:
        """发送鼠标 stroke"""
        if not self._lib or not self._ctx:
            return False
        try:
            arr = (InterceptionMouseStroke * 1)(stroke)
            result = self._lib.interception_send(self._ctx, self._device, ctypes.cast(arr, ctypes.c_void_p), 1)
            return result > 0
        except Exception as e:
            self.logger.error("发送鼠标 stroke 失败: %s", e)
            return False

    def _send_key_stroke(self, device: int, stroke: InterceptionKeyStroke) -> bool:
        """发送键盘 stroke。"""
        if not self._lib or not self._ctx:
            return False
        try:
            arr = (InterceptionKeyStroke * 1)(stroke)
            result = self._lib.interception_send(self._ctx, device, ctypes.cast(arr, ctypes.c_void_p), 1)
            return result > 0
        except Exception as e:
            self.logger.error("发送键盘 stroke 失败: %s", e)
            return False

    def _ensure_keyboard_device(self) -> Optional[int]:
        """按 MAA 的方式枚举一个键盘设备。"""
        if self._keyboard_device is not None:
            return self._keyboard_device
        if not self._lib or not self._ctx:
            return None
        for device in range(1, INTERCEPTION_MAX_DEVICE + 1):
            try:
                if self._lib.interception_is_keyboard(device) > 0:
                    self._keyboard_device = device
                    self.logger.info("已发现键盘设备: %d", device)
                    return device
            except Exception:
                continue
        self.logger.warning("未发现键盘设备，键盘注入将失败")
        return None

    def _send_key_event(self, scancode: int, state: int, extended: bool = False) -> bool:
        """发送单个键盘事件。"""
        device = self._ensure_keyboard_device()
        if device is None:
            return False
        stroke = InterceptionKeyStroke()
        stroke.code = scancode
        stroke.state = state | (INTERCEPTION_KEY_E0 if extended else 0)
        stroke.information = 0
        return self._send_key_stroke(device, stroke)

    def _vk_to_scancode(self, vk_code: int) -> tuple[Optional[int], bool]:
        return VK_TO_SCANCODE.get(vk_code, (None, False))

    def _apply_jitter(self, value: int, jitter: int, minimum: int = 0) -> int:
        """给数值添加随机扰动并限制下限。"""
        if jitter <= 0:
            return max(minimum, int(value))
        return max(minimum, int(round(value + random.uniform(-jitter, jitter))))

    def _screen_to_interception(self, x: int, y: int) -> tuple[int, int]:
        """把屏幕像素坐标转换为 Interception 绝对坐标。"""
        width = max(user32.GetSystemMetrics(0) - 1, 1)
        height = max(user32.GetSystemMetrics(1) - 1, 1)
        ix = int(max(0, min(x, width)) * 65535 / width)
        iy = int(max(0, min(y, height)) * 65535 / height)
        return ix, iy
    
    def _execute_click(self, action: ClickAction) -> None:
        """执行点击"""
        # 移动
        target_x = self._apply_jitter(action.x, action.x_jitter_px)
        target_y = self._apply_jitter(action.y, action.y_jitter_px)
        abs_x, abs_y = self._screen_to_interception(target_x, target_y)
        stroke = InterceptionMouseStroke()
        stroke.state = 0
        stroke.flags = 0x001  # absolute
        stroke.rolling = 0
        stroke.x = abs_x
        stroke.y = abs_y
        stroke.information = 0
        self._send_mouse_stroke(stroke)
        time.sleep(0.02)
        
        # 按下
        stroke = InterceptionMouseStroke()
        stroke.state = 0x001
        stroke.flags = 0
        stroke.x = 0
        stroke.y = 0
        stroke.information = 0
        self._send_mouse_stroke(stroke)
        hold_ms = self._apply_jitter(action.hold_ms, action.hold_jitter_ms, minimum=1)
        time.sleep(hold_ms / 1000.0)
        
        # 释放
        stroke = InterceptionMouseStroke()
        stroke.state = 0x002
        stroke.flags = 0
        stroke.x = 0
        stroke.y = 0
        stroke.information = 0
        self._send_mouse_stroke(stroke)
        
        self.logger.debug("点击 (%d, %d)", target_x, target_y)
    
    def _execute_move(self, action: MoveAction) -> None:
        """执行移动"""
        target_x = self._apply_jitter(action.x, action.x_jitter_px)
        target_y = self._apply_jitter(action.y, action.y_jitter_px)
        abs_x, abs_y = self._screen_to_interception(target_x, target_y)
        stroke = InterceptionMouseStroke()
        stroke.state = 0
        stroke.flags = 0x001  # absolute
        stroke.rolling = 0
        stroke.x = abs_x
        stroke.y = abs_y
        stroke.information = 0
        self._send_mouse_stroke(stroke)
        duration_ms = self._apply_jitter(action.duration_ms, action.duration_jitter_ms, minimum=1)
        time.sleep(duration_ms / 1000.0)
        self.logger.debug("移动到 (%d, %d)", target_x, target_y)
    
    def _execute_key(self, action: KeyAction) -> None:
        """执行按键。"""
        scancode, extended = self._vk_to_scancode(action.vk_code)
        if scancode is None:
            self.logger.warning("未知 VK，无法通过 Interception 发送: 0x%02x", action.vk_code)
            return

        if self._send_key_event(scancode, INTERCEPTION_KEY_DOWN, extended):
            hold_ms = self._apply_jitter(action.hold_ms, action.hold_jitter_ms, minimum=1)
            time.sleep(hold_ms / 1000.0)
            self._send_key_event(scancode, INTERCEPTION_KEY_UP, extended)
            self.logger.debug("按键 Interception VK=0x%02x SC=0x%02x", action.vk_code, scancode)
            return

        try:
            user32.keybd_event(action.vk_code, 0, 0, 0)
            hold_ms = self._apply_jitter(action.hold_ms, action.hold_jitter_ms, minimum=1)
            time.sleep(hold_ms / 1000.0)
            user32.keybd_event(action.vk_code, 0, KEYEVENTF_KEYUP, 0)
            self.logger.warning("按键回退 keybd_event VK=0x%02x", action.vk_code)
        except Exception as e:
            self.logger.error("按键失败: %s", e)

    def _execute_combo(self, action: ComboAction) -> None:
        """执行组合按键。"""
        key_specs: list[tuple[int, bool]] = []
        for vk_code in action.vk_codes:
            scancode, extended = self._vk_to_scancode(vk_code)
            if scancode is None:
                self.logger.warning("未知 VK，跳过组合键中的该键: 0x%02x", vk_code)
                continue
            key_specs.append((scancode, extended))

        if not key_specs:
            return

        sent_all = True
        for scancode, extended in key_specs:
            sent_all = self._send_key_event(scancode, INTERCEPTION_KEY_DOWN, extended) and sent_all

        hold_ms = self._apply_jitter(action.hold_ms, action.hold_jitter_ms, minimum=1)
        time.sleep(hold_ms / 1000.0)

        for scancode, extended in reversed(key_specs):
            self._send_key_event(scancode, INTERCEPTION_KEY_UP, extended)

        if sent_all:
            self.logger.debug("组合按键 Interception VK=%s", "+".join(f"0x{vk:02x}" for vk in action.vk_codes))
            return

        for vk_code in reversed(action.vk_codes):
            try:
                user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
            except Exception:
                pass
        self.logger.warning("组合按键部分失败，已回退 keybd_event VK=%s", "+".join(f"0x{vk:02x}" for vk in action.vk_codes))
    
    def _execute_wait(self, action: WaitAction) -> None:
        """执行等待"""
        duration_ms = self._apply_jitter(action.duration_ms, action.duration_jitter_ms, minimum=1)
        time.sleep(duration_ms / 1000.0)
        self.logger.debug("等待 %dms", duration_ms)

    def _wait_until_ready(
        self,
        stop_event: Optional[threading.Event],
        pause_event: Optional[threading.Event],
        poll_interval: float = 0.05,
    ) -> bool:
        """等待脚本恢复运行，返回 False 表示已请求停止。"""
        while True:
            if stop_event and stop_event.is_set():
                return False
            if pause_event is None or pause_event.is_set():
                return True
            time.sleep(poll_interval)

    def _sleep_with_controls(
        self,
        duration: float,
        stop_event: Optional[threading.Event],
        pause_event: Optional[threading.Event],
    ) -> bool:
        """支持暂停/停止的分段睡眠。"""
        deadline = time.time() + duration
        while True:
            if stop_event and stop_event.is_set():
                return False
            if pause_event is not None and not pause_event.is_set():
                if not self._wait_until_ready(stop_event, pause_event):
                    return False
                continue
            remaining = deadline - time.time()
            if remaining <= 0:
                return True
            time.sleep(min(0.05, remaining))

    def _execute_actions(
        self,
        actions: List[Any],
        stop_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None,
    ) -> bool:
        """执行动作序列的内部实现。"""
        for action in actions:
            if stop_event and stop_event.is_set():
                return False
            if not self._wait_until_ready(stop_event, pause_event):
                return False

            if isinstance(action, LoopAction):
                iteration = 0
                max_iterations = action.count if action.count > 0 else 1
                while action.forever or iteration < max_iterations:
                    if stop_event and stop_event.is_set():
                        return False
                    if not self._wait_until_ready(stop_event, pause_event):
                        return False
                    if not self._execute_actions(action.actions, stop_event, pause_event):
                        return False
                    if action.pause_ms > 0:
                        pause_ms = self._apply_jitter(action.pause_ms, action.pause_jitter_ms, minimum=0)
                        if pause_ms > 0 and not self._sleep_with_controls(pause_ms / 1000.0, stop_event, pause_event):
                            return False
                    iteration += 1
                continue

            if isinstance(action, ClickAction):
                self._execute_click(action)
            elif isinstance(action, MoveAction):
                self._execute_move(action)
            elif isinstance(action, KeyAction):
                self._execute_key(action)
            elif isinstance(action, ComboAction):
                self._execute_combo(action)
            elif isinstance(action, WaitAction):
                if not self._sleep_with_controls(action.duration_ms / 1000.0, stop_event, pause_event):
                    return False

        return True
    
    def execute_sequence(
        self,
        actions: List[Any],
        stop_event: Optional[threading.Event] = None,
        pause_event: Optional[threading.Event] = None,
    ) -> bool:
        """执行动作序列"""
        if self.target_window.is_bound():
            if not self.target_window.activate():
                self.logger.warning("无法激活目标窗口")
                return False
            time.sleep(0.1)
        
        try:
            return self._execute_actions(actions, stop_event, pause_event)
        except Exception as e:
            self.logger.error("执行序列失败: %s", e)
            return False


class ActionScriptManager:
    """动作脚本管理器"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.scripts_dir = self.data_dir / "action_scripts"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("action_manager")
    
    def load_script(self, script_name: str) -> List[Any]:
        """加载脚本"""
        path = self.scripts_dir / f"{script_name}.json"
        if not path.exists():
            self.logger.warning("脚本不存在: %s", path)
            return []
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            actions = [self._parse_action(item) for item in data.get("actions", [])]
            actions = [action for action in actions if action is not None]
            
            self.logger.info("已加载脚本: %s (%d 个动作)", script_name, len(actions))
            return actions
        
        except Exception as e:
            self.logger.error("加载脚本失败: %s", e)
            return []

    def _parse_action(self, item: dict) -> Any:
        """把 JSON 动作转换为内部动作对象。"""
        action_type = item.get("type")
        if action_type == "click":
            return ClickAction(
                item["x"],
                item["y"],
                item.get("hold_ms", 100),
                item.get("x_jitter_px", 0),
                item.get("y_jitter_px", 0),
                item.get("hold_jitter_ms", 0),
            )
        if action_type == "move":
            return MoveAction(
                item["x"],
                item["y"],
                item.get("duration_ms", 100),
                item.get("x_jitter_px", 0),
                item.get("y_jitter_px", 0),
                item.get("duration_jitter_ms", 0),
            )
        if action_type == "key":
            return KeyAction(item["vk_code"], item.get("hold_ms", 50), item.get("hold_jitter_ms", 0))
        if action_type == "combo":
            return ComboAction(
                item.get("vk_codes", []),
                item.get("hold_ms", 50),
                item.get("hold_jitter_ms", 0),
            )
        if action_type == "wait":
            return WaitAction(item["duration_ms"], item.get("duration_jitter_ms", 0))
        if action_type == "loop":
            nested = [self._parse_action(sub_item) for sub_item in item.get("actions", [])]
            nested = [action for action in nested if action is not None]
            count = int(item.get("count", 1))
            forever = bool(item.get("forever", False) or item.get("until_exit", False) or count <= 0)
            if count <= 0:
                count = 1
            return LoopAction(
                actions=nested,
                count=count,
                forever=forever,
                pause_ms=int(item.get("pause_ms", 0)),
                pause_jitter_ms=int(item.get("pause_jitter_ms", 0)),
            )
        self.logger.warning("未知动作类型: %s", action_type)
        return None
    
    def save_script(self, script_name: str, actions: List[Any]) -> bool:
        """保存脚本"""
        path = self.scripts_dir / f"{script_name}.json"
        try:
            data = {
                "name": script_name,
                "actions": [asdict(a) for a in actions]
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info("脚本已保存: %s", path)
            return True
        except Exception as e:
            self.logger.error("保存脚本失败: %s", e)
            return False
    
    def list_scripts(self) -> List[str]:
        """列出所有脚本"""
        return [f.stem for f in self.scripts_dir.glob("*.json")]
