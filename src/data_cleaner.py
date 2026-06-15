"""
泥炭深度原始数据清洗模块
========================

负责泥炭多指标实验原始数据的自动清洗，包括：
- 加载多种格式的原始数据（CSV/Excel）
- 剔除仪器噪声（高频小幅度噪声平滑
- 检测并剔除异常离群采样点（IQR/Z-score方法
- 统一数据有效性范围过滤
- 缺失值处理
"""

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import signal

from .config_manager import ConfigManager


class PeatDataCleaner:
    """泥炭沉积多指标数据清洗器"""

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.cleaning_rules = self.config.get_cleaning_rules()
        self.proxy_configs = self.config.stratigraphy.get("proxy_config", {})
        self._cleaning_log: Dict[str, Dict] = {}

    @property
    def cleaning_log(self) -> Dict[str, Dict]:
        """获取各指标的清洗日志"""
        return self._cleaning_log

    def load_raw_data(self, filepath: str, depth_col: str = "depth_cm") -> pd.DataFrame:
        """
        加载原始数据文件

        Args:
            filepath: 数据文件路径（支持.csv和.xlsx
            depth_col: 深度列名

        Returns:
            加载后的DataFrame
        """
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(filepath)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(filepath)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

        if depth_col not in df.columns:
            raise ValueError(f"数据中缺少深度列 '{depth_col}'")

        df = df.sort_values(depth_col).reset_index(drop=True)
        return df

    def remove_instrument_noise(self, df: pd.DataFrame, value_col: str,
                           method: str = "savgol",
                           window_length: int = 5,
                           polyorder: int = 2) -> pd.DataFrame:
        """
        去除仪器噪声

        Args:
            df: 输入数据
            value_col: 需要去噪的数值列名
            method: 去噪方法: 'savgol'（Savitzky-Golay滤波或'moving_average'移动平均
            window_length: 窗口长度
            polyorder: 多项式阶数（仅savgol方法）

        Returns:
            去噪后的数据
        """
        result = df.copy()
        values = result[value_col].values.astype(float)

        if method == "savgol":
            if len(values) >= window_length and window_length > polyorder:
                smoothed = signal.savgol_filter(values, window_length, polyorder)
            else:
                smoothed = values
        elif method == "moving_average":
            smoothed = pd.Series(values).rolling(window=window_length, center=True, min_periods=1).mean().values
        else:
            raise ValueError(f"不支持的去噪方法: {method}")

        noise_threshold = self.cleaning_rules.get("instrument_noise_threshold", 0.01)
        noise = np.abs(values - smoothed)
        result[value_col] = np.where(noise < noise_threshold, smoothed, values)
        return result

    def detect_outliers_iqr(self, series: pd.Series, multiplier: Optional[float] = None) -> pd.Series:
        """
        使用IQR方法检测离群值

        Args:
            series: 输入数据序列
            multiplier: IQR倍数

        Returns:
            布尔序列，True表示离群值
        """
        if multiplier is None:
            multiplier = self.cleaning_rules.get("iqr_multiplier", 1.5)
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - multiplier * iqr
        upper_bound = q3 + multiplier * iqr
        return (series < lower_bound) | (series > upper_bound)

    def detect_outliers_zscore(self, series: pd.Series, threshold: Optional[float] = None) -> pd.Series:
        """
        使用Z-score方法检测离群值

        Args:
            series: 输入数据序列
            threshold: Z-score阈值

        Returns:
            布尔序列，True表示离群值
        """
        if threshold is None:
            threshold = self.cleaning_rules.get("zscore_threshold", 3.0)
        z_scores = np.abs((series - series.mean()) / series.std())
        return z_scores > threshold

    def filter_by_valid_range(self, df: pd.DataFrame, value_col: str,
                           valid_range: Tuple[float, float]) -> pd.Series:
        """
        根据配置的有效范围过滤数据

        Args:
            df: 输入数据
            value_col: 数值列名
            valid_range: (min, max)有效范围

        Returns:
            布尔序列，True表示在有效范围内
        """
        return (df[value_col] >= valid_range[0]) & (df[value_col] <= valid_range[1])

    def clean_proxy_data(self, df: pd.DataFrame, proxy_name: str,
                        value_col: Optional[str] = None,
                        depth_col: str = "depth_cm") -> pd.DataFrame:
        """
        清洗单个代用指标数据

        Args:
            df: 输入数据
            proxy_name: 代用指标名称
            value_col: 数值列名，若为None则从配置中获取
            depth_col: 深度列名

        Returns:
            清洗后的数据
        """
        proxy_cfg = self.config.get_proxy_config(proxy_name)
        if value_col is None:
            value_col = proxy_cfg["column"]

        if value_col not in df.columns:
            raise ValueError(f"数据中缺少列 '{value_col}'")

        log_entry = {
            "original_count": len(df),
            "noise_removed": 0,
            "outliers_removed": 0,
            "range_invalid_removed": 0,
            "na_removed": 0,
            "final_count": 0
        }

        result = df.copy()
        result[value_col] = pd.to_numeric(result[value_col], errors="coerce")

        if self.cleaning_rules.get("remove_na", True):
            before = len(result)
            result = result.dropna(subset=[value_col])
            log_entry["na_removed"] = before - len(result)

        valid_range = tuple(proxy_cfg.get("valid_range", []))
        before = len(result)
        valid_mask = self.filter_by_valid_range(result, value_col, valid_range)
        result = result[valid_mask].copy()
        log_entry["range_invalid_removed"] = before - len(result)

        before = len(result)
        result = self.remove_instrument_noise(result, value_col)
        log_entry["noise_removed"] = before - len(result)

        method = self.cleaning_rules.get("outlier_method", "IQR")
        before = len(result)
        if method == "IQR":
            outlier_mask = self.detect_outliers_iqr(result[value_col])
        elif method == "zscore":
            outlier_mask = self.detect_outliers_zscore(result[value_col])
        else:
            outlier_mask = pd.Series([False] * len(result))
        result = result[~outlier_mask].copy()
        log_entry["outliers_removed"] = before - len(result)

        min_points = self.cleaning_rules.get("min_valid_points", 5)
        if len(result) < min_points:
            raise ValueError(f"清洗后有效数据点不足（{len(result)} < {min_points}）")

        result = result.sort_values(depth_col).reset_index(drop=True)
        log_entry["final_count"] = len(result)
        self._cleaning_log[proxy_name] = log_entry

        return result

    def merge_multi_proxy(self, isotope_df: pd.DataFrame,
                        plant_df: pd.DataFrame,
                        metal_df: pd.DataFrame,
                        depth_col: str = "depth_cm") -> pd.DataFrame:
        """
        合并多个代用指标数据

        Args:
            isotope_df: 碳同位素数据
            plant_df: 植物残体数据
            metal_df: 重金属数据
            depth_col: 深度列名

        Returns:
            合并后的DataFrame
        """
        merged = isotope_df.copy()
        for other_df in [plant_df, metal_df]:
            if other_df is not None and len(other_df) > 0:
                merged = pd.merge_asof(
                    merged.sort_values(depth_col),
                    other_df.sort_values(depth_col),
                    on=depth_col,
                    direction="nearest",
                    tolerance=2.0
                )
        return merged

    def clean_and_merge_all(self, core_id: Optional[str] = None,
                          save_processed: bool = True) -> pd.DataFrame:
        """
        清洗并合并所有代用指标

        Args:
            core_id: 钻孔ID

        Returns:
            清洗合并后的数据
        """
        data_source = self.config.get_data_source(core_id)

        isotope_path = self.config.get_raw_data_path(data_source["isotope_file"])
        plant_path = self.config.get_raw_data_path(data_source["plant_remain_file"])
        metal_path = self.config.get_raw_data_path(data_source["heavy_metal_file"])

        isotope_raw = self.load_raw_data(isotope_path)
        plant_raw = self.load_raw_data(plant_path)
        metal_raw = self.load_raw_data(metal_path)

        isotope_clean = self.clean_proxy_data(isotope_raw, "carbon_isotope")
        plant_clean = self.clean_proxy_data(plant_raw, "plant_remain_index")
        metal_clean = self.clean_proxy_data(metal_raw, "heavy_metal_index")

        merged = self.merge_multi_proxy(isotope_clean, plant_clean, metal_clean)

        if save_processed:
            output_path = self.config.get_processed_data_path(f"{core_id or 'default'}_cleaned.csv")
            merged.to_csv(output_path, index=False, encoding="utf-8-sig")

        return merged

    def get_cleaning_report(self) -> pd.DataFrame:
        """
        生成清洗报告"""
        records = []
        for proxy_name, log in self._cleaning_log.items():
            record = {"proxy": proxy_name}
            record.update(log)
            records.append(record)
        return pd.DataFrame(records)
