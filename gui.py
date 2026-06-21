import threading
from pathlib import Path

import webview

from Clicker import ClickerManager
from ConfigManager import ConfigManager

# Toast helper — available when webview.py (Tkinter GUI) is loaded.
try:
    from webview import push_toast
except ImportError:
    push_toast = None


APP_DIR = Path(__file__).resolve().parent
WEB_DIR = APP_DIR / "web"


class Api:
    def __init__(self, manager: ClickerManager):
        self.manager = manager

    def list_scripts(self):
        try:
            return self.manager.action_manager.list_scripts()
        except Exception:
            return []

    def run_script(self, name: str):
        # run in background thread to avoid blocking UI
        def worker():
            actions = self.manager.action_manager.load_script(name)
            if actions:
                self.manager._run_script_session(name, actions)

        threading.Thread(target=worker, daemon=True).start()
        return True

    def delete_script(self, name: str):
        path = self.manager.action_manager.scripts_dir / f"{name}.json"
        try:
            if path.exists():
                path.unlink()
                return True
            return False
        except Exception:
            return False

    def toggle_start_stop(self):
        def worker():
            if self.manager.clicker.running:
                self.manager._on_stop()
            else:
                self.manager._on_start()

        threading.Thread(target=worker, daemon=True).start()
        return True

    def toggle_move_mouse(self):
        cur = getattr(self.manager.clicker.config, 'move_mouse', True)
        self.manager.clicker.config.move_mouse = not cur
        ConfigManager.save_config(self.manager.clicker.config, "default")
        return self.manager.clicker.config.move_mouse

    def get_status(self):
        cfg = self.manager.clicker.config
        # 仅返回对用户有用的精简字段；在 move_mouse 为 True 时才包含位置信息
        status = {
            "interception_ready": bool(self.manager.clicker.is_ready()),
            "interception_error": getattr(self.manager.clicker, "init_error", None),
            "running": bool(self.manager.clicker.running),
            "script_running": bool(getattr(self.manager, 'script_running', False)),
            "script_paused": bool(getattr(self.manager, 'script_paused', False)),
            "script_name": getattr(self.manager, 'current_script_name', None),
            "click_interval": getattr(cfg, 'click_interval', None),
            "hold_duration": getattr(cfg, 'hold_duration', None),
            "move_mouse": getattr(cfg, 'move_mouse', True),
        }

        if status.get("move_mouse"):
            status.update({
                "center_x": getattr(cfg, 'center_x', None),
                "center_y": getattr(cfg, 'center_y', None),
                "radius": getattr(cfg, 'radius', None),
            })

        # 如果执行器存在，返回被忽略的移动计数（用于调试）
        try:
            ae = getattr(self.manager, 'action_executor', None)
            if ae is not None and hasattr(ae, 'ignored_moves'):
                status["ignored_moves"] = int(getattr(ae, 'ignored_moves', 0))
        except Exception:
            pass

        # 倒计时信息（如果存在）
        try:
            cd_end = getattr(self.manager, 'countdown_end', None)
            cd_label = getattr(self.manager, 'countdown_label', None)
            if cd_end and cd_end > 0:
                import time as _time
                remaining = max(0, int(cd_end - _time.time()))
                status['countdown'] = remaining
                status['countdown_label'] = cd_label
        except Exception:
            pass

        return status


def start_gui():
    manager = ClickerManager(push_toast=push_toast)

    api = Api(manager)

    # 如果 Interception 未就绪，在启动窗口时立即提示一次（避免用户进了界面还不知情）
    if not manager.clicker.is_ready():
        try:
            from Clicker import show_message_box
            msg = (
                "RocoKingdom Clicker 需要 Interception 驱动才能工作。\n\n"
                f"{manager.clicker.init_error or '无法加载 interception.dll。'}\n\n"
                "安装步骤：\n"
                "  1) 以【管理员身份】运行程序目录下 driver_installer\\install-interception.exe /install\n"
                "  2) 重启电脑后再运行本程序。\n\n"
                "（如果只浏览界面，不需要驱动；但点击操作会被拒绝。）"
            )
            show_message_box(msg, "驱动未就绪 - RocoKingdom Clicker", error=False)
        except Exception:
            pass

    index_path = (WEB_DIR / 'index.html').as_uri()

    # run webview in main thread
    webview.create_window('RocoKingdom Clicker', index_path, js_api=api, width=1180, height=780)
    webview.start()


if __name__ == '__main__':
    start_gui()
