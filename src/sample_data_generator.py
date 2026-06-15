"""
示例数据生成器
==============

生成模拟的泥炭沉积多指标实验原始数据，
用于演示和测试整个数据分析流程。
"""

import os
import numpy as np
import pandas as pd

from .config_manager import ConfigManager


def generate_carbon_isotope_data(n_samples: int = 150, seed: int = 42) -> pd.DataFrame:
    """生成碳同位素模拟数据"""
    np.random.seed(seed)
    depths = np.sort(np.random.uniform(0, 500, n_samples))

    age_trend = -26.0 - 0.004 * depths
    oscillation = 2.0 * np.sin(depths / 40) + 1.0 * np.sin(depths / 15)
    noise = np.random.normal(0, 0.5, n_samples)

    delta13C = age_trend + oscillation + noise

    outliers_idx = np.random.choice(n_samples, size=8, replace=False)
    delta13C[outliers_idx] += np.random.choice([-5, 5], size=8)

    df = pd.DataFrame({
        "depth_cm": depths.round(2),
        "delta13C": delta13C.round(3),
        "sample_id": [f"C{i+1:03d}" for i in range(n_samples)]
    })
    return df


def generate_plant_remain_data(n_samples: int = 120, seed: int = 43) -> pd.DataFrame:
    """生成植物残体模拟数据"""
    np.random.seed(seed)
    depths = np.sort(np.random.uniform(0, 500, n_samples))

    base_trend = 70 - 0.05 * depths
    cycles = 15 * np.sin(depths / 50 + 0.5) + 8 * np.sin(depths / 20)
    noise = np.random.normal(0, 5, n_samples)

    plant_index = np.clip(base_trend + cycles + noise, 5, 98)

    df = pd.DataFrame({
        "depth_cm": depths.round(2),
        "plant_index": plant_index.round(2),
        "aquatic_moss_pct": (plant_index * 0.6 + np.random.normal(0, 3, n_samples)).round(2),
        "herb_pct": (100 - plant_index * 0.6 + np.random.normal(0, 3, n_samples)).round(2)
    })
    return df


def generate_heavy_metal_data(n_samples: int = 100, seed: int = 44) -> pd.DataFrame:
    """生成重金属模拟数据"""
    np.random.seed(seed)
    depths = np.sort(np.random.uniform(0, 500, n_samples))

    recent_pollution = np.where(depths < 50, 50 * (1 - depths / 50) + 10, 8)
    base_background = 8 + 0.01 * depths
    natural_variation = 5 * np.sin(depths / 60)
    noise = np.random.exponential(3, n_samples)

    metal_pollution = recent_pollution + base_background + natural_variation + noise

    df = pd.DataFrame({
        "depth_cm": depths.round(2),
        "metal_pollution": metal_pollution.round(2),
        "Pb_ppm": (metal_pollution * 0.8 + np.random.normal(0, 2, n_samples)).round(2),
        "Cd_ppb": (metal_pollution * 15 + np.random.normal(0, 10, n_samples)).round(2)
    })
    return df


def generate_chronology_data(seed: int = 45) -> pd.DataFrame:
    """生成年代学测年数据"""
    np.random.seed(seed)
    data = [
        (0, 0, 5, "210Pb", "泥炭表层"),
        (5, 50, 8, "210Pb", "植物残体"),
        (10, 110, 12, "210Pb", "植物残体"),
        (20, 220, 20, "210Pb/137Cs", "植物残体"),
        (30, 380, 30, "14C-AMS", "植物残体"),
        (50, 680, 40, "14C-AMS", "种子"),
        (80, 1150, 50, "14C-AMS", "植物残体"),
        (100, 1650, 60, "14C-AMS", "木炭"),
        (130, 2300, 70, "14C-AMS", "植物残体"),
        (160, 3000, 80, "14C-AMS", "种子"),
        (200, 3900, 90, "14C-AMS", "植物残体"),
        (240, 4800, 100, "14C-AMS", "木炭"),
        (280, 5600, 110, "14C-AMS", "植物残体"),
        (320, 6500, 120, "14C-AMS", "种子"),
        (360, 7600, 130, "14C-AMS", "植物残体"),
        (400, 8800, 140, "14C-AMS", "木炭"),
        (450, 10200, 160, "14C-AMS", "植物残体"),
        (500, 11800, 180, "14C-AMS", "植物残体"),
    ]
    df = pd.DataFrame(data, columns=["depth_cm", "age_yrBP", "age_error", "method", "material"])
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

    files = {}

    df_iso = generate_carbon_isotope_data()
    path_iso = config.get_raw_data_path(data_source["isotope_file"])
    df_iso.to_csv(path_iso, index=False, encoding="utf-8-sig")
    files["isotope"] = path_iso

    df_plant = generate_plant_remain_data()
    path_plant = config.get_raw_data_path(data_source["plant_remain_file"])
    df_plant.to_csv(path_plant, index=False, encoding="utf-8-sig")
    files["plant_remain"] = path_plant

    df_metal = generate_heavy_metal_data()
    path_metal = config.get_raw_data_path(data_source["heavy_metal_file"])
    df_metal.to_csv(path_metal, index=False, encoding="utf-8-sig")
    files["heavy_metal"] = path_metal

    df_chrono = generate_chronology_data()
    path_chrono = config.get_raw_data_path(data_source["chronology_file"])
    df_chrono.to_csv(path_chrono, index=False, encoding="utf-8-sig")
    files["chronology"] = path_chrono

    return files
