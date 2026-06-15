"""
示例数据生成器
==============

生成模拟的泥炭沉积多指标实验原始数据，
用于演示和测试整个数据分析流程。
支持多区域差异化参数，模拟真实古环境空间差异。
"""

import os
from typing import Dict, Optional
import numpy as np
import pandas as pd

from .config_manager import ConfigManager


_REGION_PARAMS = {
    "华中": {
        "delta13C_baseline": -26.0,
        "delta13C_trend": -0.004,
        "humidity_baseline": 0.70,
        "humidity_variability": 0.15,
        "temperature_amplitude": 1.0,
        "plant_index_baseline": 70,
        "metal_background": 8,
        "sed_rate_factor": 1.0,
        "max_depth": 500
    },
    "华东": {
        "delta13C_baseline": -27.5,
        "delta13C_trend": -0.0035,
        "humidity_baseline": 0.82,
        "humidity_variability": 0.10,
        "temperature_amplitude": 0.8,
        "plant_index_baseline": 82,
        "metal_background": 10,
        "sed_rate_factor": 1.15,
        "max_depth": 520
    },
    "西南": {
        "delta13C_baseline": -24.5,
        "delta13C_trend": -0.0045,
        "humidity_baseline": 0.55,
        "humidity_variability": 0.18,
        "temperature_amplitude": 1.2,
        "plant_index_baseline": 58,
        "metal_background": 6,
        "sed_rate_factor": 0.85,
        "max_depth": 480
    },
    "东北": {
        "delta13C_baseline": -28.0,
        "delta13C_trend": -0.005,
        "humidity_baseline": 0.65,
        "humidity_variability": 0.20,
        "temperature_amplitude": 1.5,
        "plant_index_baseline": 62,
        "metal_background": 5,
        "sed_rate_factor": 0.95,
        "max_depth": 550
    },
    "青藏": {
        "delta13C_baseline": -23.0,
        "delta13C_trend": -0.0055,
        "humidity_baseline": 0.42,
        "humidity_variability": 0.22,
        "temperature_amplitude": 1.8,
        "plant_index_baseline": 45,
        "metal_background": 4,
        "sed_rate_factor": 0.70,
        "max_depth": 450
    }
}


def _get_region_params(config: ConfigManager, core_id: str) -> Dict:
    """根据钻孔ID获取区域参数"""
    try:
        meta = config.get_core_metadata(core_id)
        region = meta.get("region", "华中")
    except Exception:
        region = "华中"
    return _REGION_PARAMS.get(region, _REGION_PARAMS["华中"])


def generate_carbon_isotope_data(n_samples: int = 150, seed: int = 42,
                                 config: Optional[ConfigManager] = None,
                                 core_id: Optional[str] = None) -> pd.DataFrame:
    """生成碳同位素模拟数据"""
    np.random.seed(seed)

    params = {"delta13C_baseline": -26.0, "delta13C_trend": -0.004, "max_depth": 500}
    if config and core_id:
        params.update(_get_region_params(config, core_id))

    max_depth = params["max_depth"]
    depths = np.sort(np.random.uniform(0, max_depth, n_samples))

    age_trend = params["delta13C_baseline"] + params["delta13C_trend"] * depths
    oscillation = 2.0 * np.sin(depths / 40) + 1.0 * np.sin(depths / 15)
    region_shift = np.sin(depths / 100 + seed * 0.1) * 0.5
    noise = np.random.normal(0, 0.5, n_samples)

    delta13C = age_trend + oscillation + region_shift + noise

    outliers_idx = np.random.choice(n_samples, size=8, replace=False)
    delta13C[outliers_idx] += np.random.choice([-5, 5], size=8)

    df = pd.DataFrame({
        "depth_cm": depths.round(2),
        "delta13C": delta13C.round(3),
        "sample_id": [f"C{i+1:03d}" for i in range(n_samples)]
    })
    return df


def generate_plant_remain_data(n_samples: int = 120, seed: int = 43,
                              config: Optional[ConfigManager] = None,
                              core_id: Optional[str] = None) -> pd.DataFrame:
    """生成植物残体模拟数据"""
    np.random.seed(seed)

    params = {"plant_index_baseline": 70, "humidity_variability": 0.15, "max_depth": 500}
    if config and core_id:
        params.update(_get_region_params(config, core_id))

    max_depth = params["max_depth"]
    depths = np.sort(np.random.uniform(0, max_depth, n_samples))

    base_val = params["plant_index_baseline"]
    base_trend = base_val - 0.05 * depths
    cycles = 15 * np.sin(depths / 50 + 0.5) + 8 * np.sin(depths / 20)
    region_phase = np.sin(depths / 80 + seed * 0.05) * (params["humidity_variability"] * 100)
    noise = np.random.normal(0, 5, n_samples)

    plant_index = np.clip(base_trend + cycles + region_phase + noise, 5, 98)

    df = pd.DataFrame({
        "depth_cm": depths.round(2),
        "plant_index": plant_index.round(2),
        "aquatic_moss_pct": (plant_index * 0.6 + np.random.normal(0, 3, n_samples)).round(2),
        "herb_pct": (100 - plant_index * 0.6 + np.random.normal(0, 3, n_samples)).round(2)
    })
    return df


def generate_heavy_metal_data(n_samples: int = 100, seed: int = 44,
                             config: Optional[ConfigManager] = None,
                             core_id: Optional[str] = None) -> pd.DataFrame:
    """生成重金属模拟数据"""
    np.random.seed(seed)

    params = {"metal_background": 8, "max_depth": 500}
    if config and core_id:
        params.update(_get_region_params(config, core_id))

    max_depth = params["max_depth"]
    depths = np.sort(np.random.uniform(0, max_depth, n_samples))

    bg = params["metal_background"]
    recent_pollution = np.where(depths < 50, (bg * 5) * (1 - depths / 50) + bg, bg)
    base_background = bg + 0.01 * depths
    natural_variation = 5 * np.sin(depths / 60 + seed * 0.08)
    noise = np.random.exponential(3, n_samples)

    metal_pollution = recent_pollution + base_background + natural_variation + noise

    df = pd.DataFrame({
        "depth_cm": depths.round(2),
        "metal_pollution": metal_pollution.round(2),
        "Pb_ppm": (metal_pollution * 0.8 + np.random.normal(0, 2, n_samples)).round(2),
        "Cd_ppb": (metal_pollution * 15 + np.random.normal(0, 10, n_samples)).round(2)
    })
    return df


def generate_chronology_data(seed: int = 45,
                            config: Optional[ConfigManager] = None,
                            core_id: Optional[str] = None) -> pd.DataFrame:
    """生成年代学测年数据"""
    np.random.seed(seed)

    params = {"sed_rate_factor": 1.0, "max_depth": 500}
    if config and core_id:
        params.update(_get_region_params(config, core_id))

    sed_factor = params["sed_rate_factor"]
    max_depth = params["max_depth"]

    base_data = [
        (0, 0, 5, "210Pb", "泥炭表层"),
        (5, int(50 / sed_factor), 8, "210Pb", "植物残体"),
        (10, int(110 / sed_factor), 12, "210Pb", "植物残体"),
        (20, int(220 / sed_factor), 20, "210Pb/137Cs", "植物残体"),
        (30, int(380 / sed_factor), 30, "14C-AMS", "植物残体"),
        (50, int(680 / sed_factor), 40, "14C-AMS", "种子"),
        (80, int(1150 / sed_factor), 50, "14C-AMS", "植物残体"),
        (100, int(1650 / sed_factor), 60, "14C-AMS", "木炭"),
        (130, int(2300 / sed_factor), 70, "14C-AMS", "植物残体"),
        (160, int(3000 / sed_factor), 80, "14C-AMS", "种子"),
        (200, int(3900 / sed_factor), 90, "14C-AMS", "植物残体"),
        (240, int(4800 / sed_factor), 100, "14C-AMS", "木炭"),
        (280, int(5600 / sed_factor), 110, "14C-AMS", "植物残体"),
        (320, int(6500 / sed_factor), 120, "14C-AMS", "种子"),
        (360, int(7600 / sed_factor), 130, "14C-AMS", "植物残体"),
        (400, int(8800 / sed_factor), 140, "14C-AMS", "木炭"),
    ]

    if max_depth >= 450:
        base_data.append((450, int(10200 / sed_factor), 160, "14C-AMS", "植物残体"))
    if max_depth >= 500:
        base_data.append((500, int(11800 / sed_factor), 180, "14C-AMS", "植物残体"))

    filtered = [(d, a, e, m, mat) for d, a, e, m, mat in base_data if d <= max_depth]

    df = pd.DataFrame(filtered, columns=["depth_cm", "age_yrBP", "age_error", "method", "material"])

    df["age_yrBP"] = df["age_yrBP"].apply(
        lambda x: int(x + np.random.normal(0, max(5, x * 0.02)))
    )
    return df


def generate_all_sample_data(config: ConfigManager = None, core_id: str = "core_ZK01") -> Dict[str, str]:
    """
    生成所有示例数据文件

    Args:
        config: 配置管理器
        core_id: 钻孔ID

    Returns:
        各数据文件路径字典
    """
    if config is None:
        config = ConfigManager()

    data_source = config.get_data_source(core_id)

    seed_offset = 0
    try:
        core_num = int(''.join(c for c in core_id if c.isdigit()))
        seed_offset = core_num * 7
    except Exception:
        pass

    files = {}

    df_iso = generate_carbon_isotope_data(seed=42 + seed_offset, config=config, core_id=core_id)
    path_iso = config.get_raw_data_path(data_source["isotope_file"])
    df_iso.to_csv(path_iso, index=False, encoding="utf-8-sig")
    files["isotope"] = path_iso

    df_plant = generate_plant_remain_data(seed=43 + seed_offset, config=config, core_id=core_id)
    path_plant = config.get_raw_data_path(data_source["plant_remain_file"])
    df_plant.to_csv(path_plant, index=False, encoding="utf-8-sig")
    files["plant_remain"] = path_plant

    df_metal = generate_heavy_metal_data(seed=44 + seed_offset, config=config, core_id=core_id)
    path_metal = config.get_raw_data_path(data_source["heavy_metal_file"])
    df_metal.to_csv(path_metal, index=False, encoding="utf-8-sig")
    files["heavy_metal"] = path_metal

    df_chrono = generate_chronology_data(seed=45 + seed_offset, config=config, core_id=core_id)
    path_chrono = config.get_raw_data_path(data_source["chronology_file"])
    df_chrono.to_csv(path_chrono, index=False, encoding="utf-8-sig")
    files["chronology"] = path_chrono

    return files
