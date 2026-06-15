"""
数据源路径配置管理器
====================

负责加载、管理和访问项目配置文件，包括路径配置、泥炭地层配置等。
支持多钻孔数据源的增量配置管理。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class ConfigManager:
    """项目配置管理器，统一管理所有配置文件的加载和访问"""

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
            config_dir = base_dir / "config"
        self.config_dir = Path(config_dir)
        self._paths_config: Optional[Dict] = None
        self._stratigraphy_config: Optional[Dict] = None
        self._chronology_data = None

    @property
    def paths(self) -> Dict[str, Any]:
        """获取路径配置"""
        if self._paths_config is None:
            self._load_paths_config()
        return self._paths_config

    @property
    def stratigraphy(self) -> Dict[str, Any]:
        """获取泥炭地层配置"""
        if self._stratigraphy_config is None:
            self._load_stratigraphy_config()
        return self._stratigraphy_config

    def _load_paths_config(self) -> None:
        """加载路径配置文件"""
        path_file = self.config_dir / "paths.json"
        if not path_file.exists():
            raise FileNotFoundError(f"路径配置文件不存在: {path_file}")
        with open(path_file, "r", encoding="utf-8") as f:
            self._paths_config = json.load(f)

    def _load_stratigraphy_config(self) -> None:
        """加载泥炭地层配置文件"""
        strat_file = self.config_dir / "peat_stratigraphy.json"
        if not strat_file.exists():
            raise FileNotFoundError(f"地层配置文件不存在: {strat_file}")
        with open(strat_file, "r", encoding="utf-8") as f:
            self._stratigraphy_config = json.load(f)

    def get_path(self, key: str) -> str:
        """
        获取指定路径

        Args:
            key: 路径键名

        Returns:
            对应的绝对路径字符串
        """
        if key not in self.paths:
            raise KeyError(f"路径键 '{key}' 不存在于配置中")
        path_value = self.paths[key]
        if isinstance(path_value, str):
            return os.path.abspath(path_value)
        raise ValueError(f"键 '{key}' 对应的不是路径字符串")

    def get_data_source(self, core_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指定钻孔数据源配置

        Args:
            core_id: 钻孔ID，若为None则使用默认钻孔

        Returns:
            数据源配置字典
        """
        if core_id is None:
            core_id = self.paths.get("default_core")
        data_sources = self.paths.get("data_sources", {})
        if core_id not in data_sources:
            raise KeyError(f"数据源 '{core_id}' 不存在，可用: {list(data_sources.keys())}")
        return data_sources[core_id]

    def list_data_sources(self) -> List[str]:
        """列出所有可用的钻孔数据源"""
        return list(self.paths.get("data_sources", {}).keys())

    def add_data_source(self, core_id: str, description: str, location: str,
                        isotope_file: str, plant_remain_file: str,
                        heavy_metal_file: str, chronology_file: str,
                        save: bool = True) -> None:
        """
        新增钻孔数据源配置

        Args:
            core_id: 钻孔唯一标识
            description: 钻孔描述
            location: 钻孔位置
            isotope_file: 碳同位素数据文件名
            plant_remain_file: 植物残体数据文件名
            heavy_metal_file: 重金属数据文件名
            chronology_file: 年代学数据文件名
            save: 是否立即保存到配置文件
        """
        if "data_sources" not in self._paths_config:
            self._paths_config["data_sources"] = {}
        self._paths_config["data_sources"][core_id] = {
            "description": description,
            "location": location,
            "isotope_file": isotope_file,
            "plant_remain_file": plant_remain_file,
            "heavy_metal_file": heavy_metal_file,
            "chronology_file": chronology_file
        }
        if save:
            self._save_paths_config()

    def _save_paths_config(self) -> None:
        """保存路径配置到文件"""
        path_file = self.config_dir / "paths.json"
        with open(path_file, "w", encoding="utf-8") as f:
            json.dump(self._paths_config, f, ensure_ascii=False, indent=2)

    def get_proxy_config(self, proxy_name: str) -> Dict[str, Any]:
        """
        获取指定代用指标的配置

        Args:
            proxy_name: 代用指标名称

        Returns:
            代用指标配置字典
        """
        proxy_configs = self.stratigraphy.get("proxy_config", {})
        if proxy_name not in proxy_configs:
            raise KeyError(f"代用指标 '{proxy_name}' 不存在，可用: {list(proxy_configs.keys())}")
        return proxy_configs[proxy_name]

    def get_cleaning_rules(self) -> Dict[str, Any]:
        """获取数据清洗规则"""
        return self.stratigraphy.get("cleaning_rules", {})

    def get_interpolation_rules(self) -> Dict[str, Any]:
        """获取插值规则"""
        return self.stratigraphy.get("interpolation_rules", {})

    def get_layer_by_depth(self, depth_cm: float) -> Optional[Dict[str, Any]]:
        """
        根据深度获取对应的地层信息

        Args:
            depth_cm: 深度（厘米）

        Returns:
            地层信息字典，若深度超出范围则返回None
        """
        layers = self.stratigraphy.get("stratigraphic_layers", [])
        for layer in layers:
            if layer["depth_min"] <= depth_cm < layer["depth_max"]:
                return layer
        return None

    def get_layer_by_age(self, age_yrBP: float) -> Optional[Dict[str, Any]]:
        """
        根据年代获取对应的地层信息

        Args:
            age_yrBP: 年代（yr BP）

        Returns:
            地层信息字典，若年代超出范围则返回None
        """
        layers = self.stratigraphy.get("stratigraphic_layers", [])
        for layer in layers:
            if layer["age_min"] <= age_yrBP < layer["age_max"]:
                return layer
        return None

    def get_raw_data_path(self, filename: str) -> str:
        """获取原始数据文件的完整路径"""
        return os.path.join(self.get_path("raw_data_dir"), filename)

    def get_processed_data_path(self, filename: str) -> str:
        """获取处理后数据文件的完整路径"""
        return os.path.join(self.get_path("processed_data_dir"), filename)

    def get_figure_path(self, filename: str) -> str:
        """获取图表输出文件的完整路径"""
        return os.path.join(self.get_path("figure_dir"), filename)

    def get_report_path(self, filename: str) -> str:
        """获取报告输出文件的完整路径"""
        return os.path.join(self.get_path("report_dir"), filename)

    def list_comparison_groups(self) -> List[str]:
        """列出所有可用的对比组"""
        return list(self.paths.get("comparison_groups", {}).keys())

    def get_comparison_group(self, group_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取指定对比组配置

        Args:
            group_id: 对比组ID，若为None则使用默认对比组

        Returns:
            对比组配置字典
        """
        groups = self.paths.get("comparison_groups", {})
        if group_id is None:
            group_id = self.paths.get("default_comparison_group")
        if group_id not in groups:
            raise KeyError(f"对比组 '{group_id}' 不存在，可用: {list(groups.keys())}")
        return groups[group_id]

    def add_comparison_group(self, group_id: str, name: str,
                           core_ids: List[str], description: str = "",
                           save: bool = True) -> None:
        """
        新增对比组配置

        Args:
            group_id: 对比组唯一标识
            name: 对比组名称
            core_ids: 包含的钻孔ID列表
            description: 对比组描述
            save: 是否立即保存到配置文件
        """
        if "comparison_groups" not in self._paths_config:
            self._paths_config["comparison_groups"] = {}
        for cid in core_ids:
            if cid not in self._paths_config.get("data_sources", {}):
                raise ValueError(f"钻孔 '{cid}' 不存在于数据源配置中")
        self._paths_config["comparison_groups"][group_id] = {
            "name": name,
            "cores": core_ids,
            "description": description
        }
        if save:
            self._save_paths_config()

    def get_core_metadata(self, core_id: str) -> Dict[str, Any]:
        """
        获取钻孔完整元数据

        Args:
            core_id: 钻孔ID

        Returns:
            包含区域、经纬度、海拔等元数据的字典
        """
        source = self.get_data_source(core_id)
        default_meta = {
            "region": "未知",
            "latitude": None,
            "longitude": None,
            "elevation_m": None
        }
        default_meta.update({k: v for k, v in source.items()
                            if k in ["region", "latitude", "longitude", "elevation_m", "location", "description"]})
        default_meta["core_id"] = core_id
        return default_meta

    def get_all_core_metadata(self) -> pd.DataFrame:
        """
        获取所有钻孔元数据表

        Returns:
            包含所有钻孔元数据的DataFrame
        """
        import pandas as pd
        records = []
        for core_id in self.list_data_sources():
            records.append(self.get_core_metadata(core_id))
        return pd.DataFrame(records)

    def get_cores_by_region(self) -> Dict[str, List[str]]:
        """
        按区域分组列出钻孔

        Returns:
            区域名映射到钻孔ID列表的字典
        """
        regions: Dict[str, List[str]] = {}
        for core_id in self.list_data_sources():
            meta = self.get_core_metadata(core_id)
            region = meta.get("region", "未分类")
            if region not in regions:
                regions[region] = []
            regions[region].append(core_id)
        return regions
