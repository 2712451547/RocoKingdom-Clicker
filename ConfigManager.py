"""
连点器配置管理模块 - Interception 版
支持从文件加载和保存配置
"""

import json
import logging
import sys
from pathlib import Path

from InterceptionCore import ClickerConfig


class ConfigManager:
    """配置管理类"""

    logger = logging.getLogger("clicker")

    if getattr(sys, "frozen", False):
        BASE_DIR = Path(sys.executable).resolve().parent
    else:
        BASE_DIR = Path(__file__).resolve().parent

    CONFIG_DIR = BASE_DIR / "data" / "clicker_configs"
    DEFAULT_CONFIG_FILE = CONFIG_DIR / "default.json"

    def __init__(self, base_dir: Path | None = None):
        """兼容 click/ 项目的实例化调用。"""
        if base_dir is not None:
            self.BASE_DIR = Path(base_dir).resolve()
            self.CONFIG_DIR = self.BASE_DIR / "clicker_configs"
            self.DEFAULT_CONFIG_FILE = self.CONFIG_DIR / "default.json"
    
    # 预设配置
    PRESETS = {
        'fast': {
            'name': '快速模式（高频率）',
            'click_interval': 50,
            'hold_duration': 30,
            'radius': 20,
            'jitter_range': 10,
        },
        'balanced': {
            'name': '平衡模式（推荐）',
            'click_interval': 100,
            'hold_duration': 50,
            'radius': 30,
            'jitter_range': 20,
        },
        'stable': {
            'name': '稳定模式（低调）',
            'click_interval': 150,
            'hold_duration': 80,
            'radius': 40,
            'jitter_range': 30,
        },
        'custom': {
            'name': '自定义模式',
            'click_interval': 100,
            'hold_duration': 50,
            'radius': 30,
            'jitter_range': 20,
        }
    }
    
    @classmethod
    def ensure_config_dir(cls):
        """确保配置目录存在"""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def load_config(cls, config_name: str = 'default') -> ClickerConfig:
        """
        从文件加载配置
        
        Args:
            config_name: 配置文件名（不含.json后缀）
        
        Returns:
            ClickerConfig 对象
        """
        cls.ensure_config_dir()
        config_file = cls.CONFIG_DIR / f"{config_name}.json"
        
        config = ClickerConfig()
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if 'center_x' in data:
                    config.center_x = data['center_x']
                if 'center_y' in data:
                    config.center_y = data['center_y']
                if 'radius' in data:
                    config.radius = data['radius']
                if 'move_mouse' in data:
                    config.move_mouse = bool(data['move_mouse'])
                if 'click_interval' in data:
                    config.click_interval = data['click_interval']
                if 'hold_duration' in data:
                    config.hold_duration = data['hold_duration']
                if 'jitter_range' in data:
                    config.jitter_range = data['jitter_range']
                
                cls.logger.info("配置已从 %s 加载", config_file)
            except Exception as e:
                cls.logger.warning("加载配置失败: %s，使用默认配置", e)
        else:
            cls.logger.info("配置文件 %s 不存在，使用默认配置", config_file)
        
        return config
    
    @classmethod
    def save_config(cls, config_data, config_name: str = 'default'):
        """
        保存配置到文件
        
        Args:
            config_data: 配置对象或配置字典
            config_name: 配置文件名（不含.json后缀）
        """
        cls.ensure_config_dir()
        config_file = cls.CONFIG_DIR / f"{config_name}.json"
        
        try:
            if hasattr(config_data, "center_x"):
                data = {
                    'center_x': config_data.center_x,
                    'center_y': config_data.center_y,
                    'radius': config_data.radius,
                        'move_mouse': getattr(config_data, 'move_mouse', True),
                    'click_interval': config_data.click_interval,
                    'hold_duration': config_data.hold_duration,
                    'jitter_range': config_data.jitter_range,
                }
            else:
                data = dict(config_data)

            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            cls.logger.info("配置已保存到 %s", config_file)
        except Exception as e:
            cls.logger.error("保存配置失败: %s", e)
    
    @classmethod
    def load_preset(cls, preset_name: str) -> ClickerConfig:
        """
        加载预设配置
        
        Args:
            preset_name: 预设名称 ('fast', 'balanced', 'stable', 'custom')
        
        Returns:
            ClickerConfig 对象
        """
        config = ClickerConfig()
        
        if preset_name not in cls.PRESETS:
            cls.logger.warning("预设 '%s' 不存在", preset_name)
            return config
        
        preset = cls.PRESETS[preset_name]
        config.click_interval = preset.get('click_interval', config.click_interval)
        config.hold_duration = preset.get('hold_duration', config.hold_duration)
        config.radius = preset.get('radius', config.radius)
        config.jitter_range = preset.get('jitter_range', config.jitter_range)
        
        cls.logger.info("预设 '%s' 已加载", preset['name'])
        return config
    
    @classmethod
    def list_configs(cls) -> list:
        """
        列出所有保存的配置
        
        Returns:
            配置文件名列表
        """
        cls.ensure_config_dir()
        configs = []
        
        for f in cls.CONFIG_DIR.glob("*.json"):
            configs.append(f.stem)
        
        return sorted(configs)
    
    @classmethod
    def list_presets(cls) -> list:
        """
        列出所有预设
        
        Returns:
            预设列表
        """
        presets = []
        for name, info in cls.PRESETS.items():
            presets.append((name, info['name']))
        return presets
    
    @classmethod
    def delete_config(cls, config_name: str) -> bool:
        """
        删除配置文件
        
        Args:
            config_name: 配置文件名
        
        Returns:
            是否删除成功
        """
        cls.ensure_config_dir()
        config_file = cls.CONFIG_DIR / f"{config_name}.json"
        
        if config_file.exists():
            try:
                config_file.unlink()
                cls.logger.info("配置已删除: %s", config_file)
                return True
            except Exception as e:
                cls.logger.error("删除配置失败: %s", e)
                return False
        else:
            cls.logger.warning("配置文件不存在: %s", config_file)
            return False
