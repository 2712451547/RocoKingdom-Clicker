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

    index_path = (WEB_DIR / 'index.html').as_uri()

    # run webview in main thread
    webview.create_window('RocoKingdom Clicker', index_path, js_api=api, width=1180, height=780)
    webview.start()


if __name__ == '__main__':
    start_gui()
