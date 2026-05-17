"""
连点器主程序 - Interception 版本
使用标准库实现全局按键轮询和日志记录。
"""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from pathlib import Path
import threading

from InterceptionCore import InterceptionCore
from ConfigManager import ConfigManager
from ActionScript import (
    ActionScriptManager,
    ActionExecutor,
    ClickAction,
    MoveAction,
    KeyAction,
    WaitAction,
    TargetWindowBinding,
    list_windows_for_process,
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


class ClickerManager:
    """连点器管理类 - 处理热键和用户交互（Interception 版）。"""

    def __init__(self):
        self.logger = logging.getLogger("clicker")
        self.clicker = InterceptionCore()
        self.target_process_name = "NRC-Win64-Shipping.exe"
        self.target_window = TargetWindowBinding(self.target_process_name)
        self.action_executor = ActionExecutor(self.target_window)
        self.action_manager = ActionScriptManager(get_app_dir() / "data")
        self.running = True
        self.listening = False  # 标记是否在监听热键
        self.clicker.set_focus_callback(self._ensure_click_target_foreground)
        self.logger.info("连点器管理器已初始化")

    def _ensure_click_target_foreground(self) -> bool:
        """连点时的前台守护：若已绑定窗口则尝试保持目标窗口在前台。"""
        if not self.target_window.is_bound():
            return True
        activated = self.target_window.activate()
        if not activated:
            self.logger.warning("前台守护失败：%s", self.target_window.describe())
        return activated

    def _on_start(self):
        if not self.clicker.running:
            self.logger.info("连点器将在 3 秒后启动，请切换到游戏窗口...")
            print("\n⏳ 连点器将在 3 秒后启动...")
            for countdown in range(3, 0, -1):
                print(f"   倒计时: {countdown}...")
                time.sleep(1)

            # 如果已绑定目标窗口，启动前先尝试激活窗口
            if self.target_window.is_bound():
                activated = self.target_window.activate()
                self.logger.info("启动前激活目标窗口: %s | 结果=%s", self.target_window.describe(), activated)

            self.clicker.start()
            self.logger.info("连点器已启动")
            print("✓ 连点器已启动！")

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
        if "duration" in stats:
            self.logger.info("运行时长: %.2f秒", stats["duration"])
            self.logger.info("平均频率: %.2f次/秒", stats["clicks_per_second"])
        self.logger.info("====================================")

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
        print("  F4  - 返回菜单")
        print("  Delete + 0..9 - 游戏内快捷键（Delete+0 切换连点器；Delete+1..9 执行脚本）")
        print("\n【默认参数】")
        print(f"  点击中心位置: ({self.clicker.config.center_x}, {self.clicker.config.center_y})")
        print(f"  随机移动半径: {self.clicker.config.radius}px")
        print(f"  点击间隔: {self.clicker.config.click_interval}ms")
        print(f"  按压持续时间: {self.clicker.config.hold_duration}ms")
        print(f"  时间抖动范围: {self.clicker.config.jitter_range}ms")
        print("\n【参数调整】(输入数字选择)")
        print("  1 - 设置点击中心位置")
        print("  2 - 设置随机移动半径")
        print("  3 - 设置点击间隔")
        print("  4 - 设置按压持续时间")
        print("  5 - 设置时间抖动范围")
        print("  6 - 加载配置预设")
        print("  7 - 管理已保存的配置")
        print("  8 - 动作脚本管理（创建/执行/删除脚本）")
        print("  9 - 绑定目标窗口（NRC-Win64-Shipping.exe）")
        print("  0 - 开始监听热键")
        print("\n")
        print(f"【脚本目标窗口】{self.target_window.describe()}")
        print("\n")

    def interactive_config(self):
        """交互式配置。"""
        while True:
            choice = input("请选择操作 [0-9]: ").strip()

            if choice == "0":
                self.logger.info("开始监听热键... 请使用热键控制连点器")
                break
            if choice == "1":
                try:
                    x = int(input("请输入点击中心X坐标: "))
                    y = int(input("请输入点击中心Y坐标: "))
                    self.clicker.config.center_x = x
                    self.clicker.config.center_y = y
                    ConfigManager.save_config(self.clicker.config, "default")
                    print(f"✓ 点击中心已设置为 ({x}, {y})")
                except ValueError:
                    print("❌ 输入错误")
            elif choice == "2":
                try:
                    radius = int(input("请输入随机移动半径(像素): "))
                    self.clicker.config.radius = radius
                    ConfigManager.save_config(self.clicker.config, "default")
                    print(f"✓ 随机半径已设置为 {radius}px")
                except ValueError:
                    print("❌ 输入错误")
            elif choice == "3":
                try:
                    interval = int(input("请输入点击间隔(毫秒): "))
                    self.clicker.config.click_interval = interval
                    ConfigManager.save_config(self.clicker.config, "default")
                    print(f"✓ 点击间隔已设置为 {interval}ms")
                except ValueError:
                    print("❌ 输入错误")
            elif choice == "4":
                try:
                    duration = int(input("请输入按压持续时间(毫秒): "))
                    self.clicker.config.hold_duration = duration
                    ConfigManager.save_config(self.clicker.config, "default")
                    print(f"✓ 按压持续时间已设置为 {duration}ms")
                except ValueError:
                    print("❌ 输入错误")
            elif choice == "5":
                try:
                    jitter = int(input("请输入时间抖动范围(毫秒): "))
                    self.clicker.config.jitter_range = jitter
                    ConfigManager.save_config(self.clicker.config, "default")
                    print(f"✓ 时间抖动范围已设置为 {jitter}ms")
                except ValueError:
                    print("❌ 输入错误")
            elif choice == "6":
                self.load_config_menu()
            elif choice == "7":
                self.manage_configs_menu()
            elif choice == "8":
                self.action_script_menu()
            elif choice == "9":
                self._bind_target_window_menu()
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
                            threading.Thread(target=self.action_executor.execute_sequence, args=(actions,), daemon=True).start()
                            print(f"✓ 已开始执行脚本: {name}")
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

    def _bind_target_window_menu(self):
        """目标窗口绑定菜单。"""
        print(f"\n正在查询进程 '{self.target_process_name}' 的窗口...")
        windows = list_windows_for_process(self.target_process_name)
        
        if not windows:
            print(f"未找到进程 '{self.target_process_name}' 的窗口")
            return
        
        print("找到以下窗口:")
        for i, (hwnd, title) in enumerate(windows, 1):
            print(f"  {i}. {title} (hwnd={hwnd})")
        
        try:
            choice = input("请选择窗口编号 (按 Enter 取消): ").strip()
            if not choice:
                return
            
            idx = int(choice) - 1
            if 0 <= idx < len(windows):
                hwnd, title = windows[idx]
                self.target_window.bind(hwnd)
                print(f"✓ 已绑定窗口: {title}")
            else:
                print("❌ 编号无效")
        except ValueError:
            print("❌ 输入错误")

    def _on_delete_number(self, number: int):
        """Delete + 0..9 快捷键处理"""
        if number == 0:
            # Delete+0: 切换连点器
            if self.clicker.running:
                self._on_stop()
            else:
                self._on_start()
        else:
            # Delete+1..9: 执行对应脚本
            script_name = f"script_{number}"
            scripts = self.action_manager.list_scripts()
            
            if script_name in scripts:
                actions = self.action_manager.load_script(script_name)
                if actions:
                    self.logger.info("执行脚本: %s", script_name)
                    threading.Thread(
                        target=self.action_executor.execute_sequence,
                        args=(actions,),
                        daemon=True
                    ).start()
            else:
                self.logger.warning("脚本不存在: %s", script_name)

    def listen_hotkeys(self):
        """监听热键。"""
        self.listening = True
        self.logger.info("开始监听热键...")
        
        delete_pressed = False
        
        while self.listening:
            try:
                # F1: 启动
                if key_pressed(VK_F1):
                    self._on_start()
                    time.sleep(0.3)
                
                # F2: 停止
                if key_pressed(VK_F2):
                    self._on_stop()
                    time.sleep(0.3)
                
                # F3: 统计
                if key_pressed(VK_F3):
                    self._on_stats()
                    time.sleep(0.3)
                
                # F4: 返回菜单
                if key_pressed(VK_F4):
                    self._on_exit()
                    break
                
                # Delete 组合: Delete+0..9
                if key_pressed(VK_DELETE):
                    if not delete_pressed:
                        delete_pressed = True
                        # 检查 0-9
                        for digit in range(10):
                            vk = VK_0 + digit
                            if key_pressed(vk):
                                self._on_delete_number(digit)
                                time.sleep(0.3)
                                break
                else:
                    delete_pressed = False
                
                time.sleep(0.05)
            
            except Exception as e:
                self.logger.error("热键监听异常: %s", e)
                time.sleep(0.1)

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
        manager = ClickerManager()
        manager.run()
    except Exception as e:
        logging.error("致命错误: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
