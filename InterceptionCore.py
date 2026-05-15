"""
连点器核心模块 - 基于 Interception 驱动实现
使用 ctypes 调用 Interception 库来注入鼠标事件（内核级）。
"""

from __future__ import annotations

import ctypes
import logging
import math
import random
import threading
import time
from typing import Callable, Optional


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
try:
    user32.SetProcessDPIAware()
except Exception:
    pass

SW = user32.GetSystemMetrics(0)
SH = user32.GetSystemMetrics(1)


class InterceptionMouseStroke(ctypes.Structure):
    """Interception 鼠标 stroke 结构体"""
    _fields_ = [
        ("state", ctypes.c_ushort),
        ("flags", ctypes.c_ushort),
        ("rolling", ctypes.c_short),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("information", ctypes.c_uint),
    ]


class InterceptionKeyStroke(ctypes.Structure):
    """Interception 键盘 stroke 结构体"""
    _fields_ = [
        ("code", ctypes.c_ushort),
        ("state", ctypes.c_ushort),
        ("information", ctypes.c_uint),
    ]


class ClickerConfig:
    """连点器配置类。"""

    def __init__(self):
        self.enabled = False
        self.center_x = SW // 2
        self.center_y = SH // 2
        self.radius = 30
        # 默认：按住约800ms(每次会额外随机±200~400ms)，然后等待随机300~700ms再按下一次
        self.click_interval = 500
        self.hold_duration = 800
        self.jitter_range = 200


class InterceptionCore:
    """
    连点器核心类 - 基于 Interception 驱动。
    
    功能：
    - 在后台线程中循环发送点击事件
    - 支持圆形随机偏移
    - 支持持续时间和间隔的随机化
    - 可选的焦点回调函数（在每次点击前调用）
    """

    def __init__(self, config: ClickerConfig | None = None):
        self.config = config or ClickerConfig()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.click_count = 0
        self.start_time: Optional[float] = None
        self.focus_callback: Optional[Callable[[], bool]] = None
        self._next_micro_pause_at = random.randint(6, 13)
        self._next_idle_move_at = random.randint(4, 10)
        self.logger = logging.getLogger("interception_clicker")
        
        # 加载 Interception 库
        self._lib = None
        self._ctx = None
        self._device = None
        self._initialize_interception()
        self.logger.info("InterceptionCore 初始化完成")

    def _initialize_interception(self):
        """初始化 Interception 库和上下文"""
        try:
            # 尝试加载 interception.dll
            import os
            dll_paths = [
                os.path.join(os.path.dirname(__file__), "interception.dll"),
                "interception.dll",
            ]
            
            lib = None
            for path in dll_paths:
                try:
                    lib = ctypes.CDLL(path)
                    self.logger.info(f"成功加载 Interception 库: {path}")
                    break
                except Exception:
                    pass
            
            if lib is None:
                raise OSError("无法加载 interception.dll - 请检查驱动是否已安装")
            
            self._lib = lib
            
            # 绑定函数
            self._lib.interception_create_context.restype = ctypes.c_void_p
            self._lib.interception_destroy_context.argtypes = [ctypes.c_void_p]
            self._lib.interception_send.argtypes = [
                ctypes.c_void_p,  # context
                ctypes.c_int,     # device
                ctypes.POINTER(InterceptionMouseStroke),  # stroke
                ctypes.c_uint,    # nstroke
            ]
            self._lib.interception_send.restype = ctypes.c_int
            
            # 创建上下文
            self._ctx = self._lib.interception_create_context()
            if not self._ctx:
                raise OSError("无法创建 Interception 上下文")
            
            # 获取虚拟鼠标设备（INTERCEPTION_MAX_KEYBOARD=10, INTERCEPTION_MOUSE(0) = 11）
            self._device = 11
            self.logger.info("Interception 上下文已创建，设备 ID: %d", self._device)
            
        except Exception as e:
            self.logger.error("Interception 初始化失败: %s", e)
            self._lib = None
            self._ctx = None
            self._device = None
            raise

    def _send_mouse_stroke(self, stroke: InterceptionMouseStroke) -> bool:
        """发送单个鼠标 stroke"""
        if not self._lib or not self._ctx:
            return False
        
        try:
            arr = (InterceptionMouseStroke * 1)(stroke)
            result = self._lib.interception_send(self._ctx, self._device, arr, 1)
            return result > 0
        except Exception as e:
            self.logger.error("发送鼠标 stroke 失败: %s", e)
            return False

    def _screen_to_interception(self, x: int, y: int) -> tuple[int, int]:
        """把屏幕像素坐标转换为 Interception 的绝对坐标。"""
        max_x = max(SW - 1, 1)
        max_y = max(SH - 1, 1)
        ix = int(max(0, min(x, max_x)) * 65535 / max_x)
        iy = int(max(0, min(y, max_y)) * 65535 / max_y)
        return ix, iy

    def _move_mouse_to(self, x: int, y: int) -> bool:
        """移动鼠标到指定位置（绝对坐标）"""
        abs_x, abs_y = self._screen_to_interception(int(x), int(y))
        stroke = InterceptionMouseStroke()
        stroke.state = 0
        stroke.flags = 0x001  # INTERCEPTION_MOUSE_MOVE_ABSOLUTE
        stroke.rolling = 0
        stroke.x = abs_x
        stroke.y = abs_y
        stroke.information = 0
        return self._send_mouse_stroke(stroke)

    def _mouse_down(self) -> bool:
        """按下左键"""
        stroke = InterceptionMouseStroke()
        stroke.state = 0x001  # INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN
        stroke.flags = 0
        stroke.rolling = 0
        stroke.x = 0
        stroke.y = 0
        stroke.information = 0
        return self._send_mouse_stroke(stroke)

    def _mouse_up(self) -> bool:
        """释放左键"""
        stroke = InterceptionMouseStroke()
        stroke.state = 0x002  # INTERCEPTION_MOUSE_LEFT_BUTTON_UP
        stroke.flags = 0
        stroke.rolling = 0
        stroke.x = 0
        stroke.y = 0
        stroke.information = 0
        return self._send_mouse_stroke(stroke)

    def _perform_click(self) -> bool:
        """执行一次完整的点击"""
        # 计算目标坐标（圆形随机）
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(0, self.config.radius)
        offset_x = dist * math.cos(angle)
        offset_y = dist * math.sin(angle)
        
        target_x = self.config.center_x + offset_x
        target_y = self.config.center_y + offset_y
        
        # 移动鼠标
        self._move_mouse_to(target_x, target_y)
        time.sleep(0.02)
        
        # 按下左键
        self._mouse_down()
        
        # 随机持续时间
        hold_time = (self.config.hold_duration + 
                    random.uniform(-self.config.jitter_range, self.config.jitter_range)) / 1000.0
        time.sleep(max(0.05, hold_time))
        
        # 释放左键
        self._mouse_up()
        
        self.click_count += 1
        return True

    def _clicking_loop(self):
        """后台点击循环"""
        self.logger.info("点击循环已启动")
        
        try:
            while self.running:
                # 焦点回调（保持目标窗口在前台）
                if self.focus_callback:
                    try:
                        if not self.focus_callback():
                            time.sleep(0.1)
                            continue
                    except Exception as e:
                        self.logger.warning("焦点回调失败: %s", e)
                
                # 执行点击
                self._perform_click()
                
                # 微暂停（模拟人工 - 每 7~13 次随机）
                if self.click_count % self._next_micro_pause_at == 0:
                    time.sleep(random.uniform(0.15, 0.35))
                    self._next_micro_pause_at = random.randint(6, 13)
                
                # 空闲移动（模拟人工 - 每 4~10 次随机）
                if self.click_count % self._next_idle_move_at == 0:
                    idle_x = self.config.center_x + random.uniform(-30, 30)
                    idle_y = self.config.center_y + random.uniform(-30, 30)
                    self._move_mouse_to(idle_x, idle_y)
                    self._next_idle_move_at = random.randint(4, 10)
                
                # 点击间隔
                interval = self.config.click_interval / 1000.0
                time.sleep(interval)
        
        except Exception as e:
            self.logger.error("点击循环异常: %s", e)
        finally:
            self.logger.info("点击循环已结束")

    def start(self):
        """启动连点器。"""
        if self.running:
            self.logger.warning("连点器已在运行中")
            return

        if not self._lib or not self._ctx:
            self.logger.error("Interception 库未初始化")
            return

        self.running = True
        self.click_count = 0
        self.start_time = time.time()
        self._next_micro_pause_at = random.randint(6, 13)
        self._next_idle_move_at = random.randint(4, 10)
        
        self.thread = threading.Thread(target=self._clicking_loop, daemon=True)
        self.thread.start()
        self.logger.info("连点器已启动")

    def stop(self):
        """停止连点器。"""
        if not self.running:
            self.logger.warning("连点器未在运行")
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.logger.info("连点器已停止 | 总点击数: %d", self.click_count)

    def set_focus_callback(self, callback: Optional[Callable[[], bool]]) -> None:
        """设置焦点回调函数（在点击前调用）"""
        self.focus_callback = callback

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = {
            "running": self.running,
            "click_count": self.click_count,
            "center_x": self.config.center_x,
            "center_y": self.config.center_y,
            "radius": self.config.radius,
            "click_interval": self.config.click_interval,
            "hold_duration": self.config.hold_duration,
            "jitter_range": self.config.jitter_range,
        }
        
        if self.running and self.start_time:
            elapsed = time.time() - self.start_time
            stats["duration"] = elapsed
            stats["clicks_per_second"] = self.click_count / elapsed if elapsed > 0 else 0
        
        return stats

    def __del__(self):
        """清理资源"""
        if self._lib and self._ctx:
            try:
                self._lib.interception_destroy_context(self._ctx)
                self.logger.info("Interception 上下文已销毁")
            except Exception as e:
                self.logger.error("销毁 Interception 上下文失败: %s", e)
