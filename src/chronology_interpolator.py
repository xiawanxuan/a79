"""
年代深度插值校准模块
====================

负责将不同代用指标的深度坐标统一转换为年代时间轴，
并通过线性插值补齐缺失年代观测数据，构建标准化万年尺度时序数据。
"""

import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

from .config_manager import ConfigManager


class ChronologyInterpolator:
    """年代-深度插值校准器"""

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.interp_rules = self.config.get_interpolation_rules()
        self._chronology_df: Optional[pd.DataFrame] = None
        self._depth_to_age_func = None
        self._age_to_depth_func = None

    def load_chronology(self, filepath: Optional[str] = None,
                       core_id: Optional[str] = None) -> pd.DataFrame:
        """
        加载年代深度校正数据

        Args:
            filepath: 年代学数据文件路径
            core_id: 钻孔ID（用于从配置中获取文件路径）

        Returns:
            年代学数据DataFrame
        """
        if filepath is None:
            if core_id is None:
                filepath = os.path.join(self.config.get_path("config_dir"), "chronology_calibration.csv")
            else:
                data_source = self.config.get_data_source(core_id)
                filepath = self.config.get_raw_data_path(data_source["chronology_file"])

        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(filepath)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(filepath)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

        required_cols = ["depth_cm", "age_yrBP"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"年代学数据缺少必需列: '{col}'")

        df = df.sort_values("depth_cm").reset_index(drop=True)
        self._chronology_df = df
        self._build_interpolation_functions()
        return df

    def _build_interpolation_functions(self) -> None:
        """构建深度-年代插值函数"""
        if self._chronology_df is None:
            raise ValueError("请先加载年代学数据")

        depths = self._chronology_df["depth_cm"].values
        ages = self._chronology_df["age_yrBP"].values

        extrapolate = self.interp_rules.get("extrapolate", False)
        fill_value = "extrapolate" if extrapolate else np.nan

        self._depth_to_age_func = interp1d(
            depths, ages,
            kind=self.interp_rules.get("method", "linear"),
            bounds_error=False,
            fill_value=fill_value
        )

        self._age_to_depth_func = interp1d(
            ages, depths,
            kind=self.interp_rules.get("method", "linear"),
            bounds_error=False,
            fill_value=fill_value
        )

    def depth_to_age(self, depth_cm: float) -> float:
        """
        将深度转换为年代

        Args:
            depth_cm: 深度（cm）

        Returns:
            对应的年代（yr BP）
        """
        if self._depth_to_age_func is None:
            raise ValueError("请先加载年代学数据")
        return float(self._depth_to_age_func(depth_cm))

    def age_to_depth(self, age_yrBP: float) -> float:
        """
        将年代转换为深度

        Args:
            age_yrBP: 年代（yr BP）

        Returns:
            对应的深度（cm）
        """
        if self._age_to_depth_func is None:
            raise ValueError("请先加载年代学数据")
        return float(self._age_to_depth_func(age_yrBP))

    def add_age_column(self, df: pd.DataFrame, depth_col: str = "depth_cm",
                      age_col: str = "age_yrBP") -> pd.DataFrame:
        """
        为数据添加年代列

        Args:
            df: 输入数据（需包含深度列）
            depth_col: 深度列名
            age_col: 输出年代列名

        Returns:
            添加了年代列的DataFrame
        """
        result = df.copy()
        result[age_col] = result[depth_col].apply(self.depth_to_age)
        result = result.dropna(subset=[age_col])
        result = result.sort_values(age_col).reset_index(drop=True)
        return result

    def build_uniform_time_series(self, df: pd.DataFrame,
                                 value_cols: List[str],
                                 age_col: str = "age_yrBP",
                                 age_step: Optional[int] = None,
                                 min_age: Optional[float] = None,
                                 max_age: Optional[float] = None) -> pd.DataFrame:
        """
        构建统一时间步长的时间序列，线性插值补齐缺失数据

        Args:
            df: 输入数据（需包含年代列和各指标值列
            value_cols: 需要插值的数值列名列表
            age_col: 年代列名
            age_step: 时间步长（年），默认从配置读取
            min_age: 最小年代，默认从配置读取
            max_age: 最大年代，默认从配置读取

        Returns:
            统一时间步长的DataFrame
        """
        if age_step is None:
            age_step = self.interp_rules.get("age_step", 10)
        if min_age is None:
            min_age = self.interp_rules.get("min_age", 0)
        if max_age is None:
            max_age = self.interp_rules.get("max_age", 12000)

        uniform_ages = np.arange(min_age, max_age + age_step, age_step)

        result_data = {age_col: uniform_ages}

        for value_col in value_cols:
            if value_col not in df.columns:
                raise ValueError(f"数据中缺少列 '{value_col}'")

            valid_data = df.dropna(subset=[age_col, value_col])
            valid_data = valid_data.sort_values(age_col)

            if len(valid_data) < 2:
                result_data[value_col] = np.nan
                continue

            ages = valid_data[age_col].values
            values = valid_data[value_col].values

            extrapolate = self.interp_rules.get("extrapolate", False)
            fill_value = (values[0], values[-1]) if extrapolate else np.nan

            interp_func = interp1d(
                ages, values,
                kind=self.interp_rules.get("method", "linear"),
                bounds_error=False,
                fill_value=fill_value
            )

            result_data[value_col] = interp_func(uniform_ages)

        result_df = pd.DataFrame(result_data)

        result_df["depth_cm"] = result_df[age_col].apply(self.age_to_depth)

        return result_df

    def derive_climate_indices(self, df: pd.DataFrame,
                              delta13C_col: str = "delta13C",
                              plant_index_col: str = "plant_index",
                              metal_col: str = "metal_pollution") -> pd.DataFrame:
        """
        从原始指标派生气候指标（湿度、温度指数

        Args:
            df: 包含原始指标的DataFrame
            delta13C_col: 碳同位素列名
            plant_index_col: 植物残体指标列名
            metal_col: 重金属列名

        Returns:
            添加了派生气候指标的DataFrame
        """
        result = df.copy()

        if plant_index_col in result.columns:
            plant_norm = (result[plant_index_col] - result[plant_index_col].min()) / \
                         (result[plant_index_col].max() - result[plant_index_col].min() + 1e-10)
            result["humidity"] = 0.6 * plant_norm + 0.4 * (1.0 - plant_norm.rolling(5, center=True, min_periods=1).std())

        if delta13C_col in result.columns:
            c13_norm = (result[delta13C_col] - result[delta13C_col].mean()) / \
                       (result[delta13C_col].std() + 1e-10)
            result["temperature"] = -0.8 * c13_norm + 0.2 * result.get("humidity", 0.5)

        return result

    def interpolate_core_data(self, cleaned_df: pd.DataFrame,
                             core_id: Optional[str] = None,
                             save_processed: bool = True) -> pd.DataFrame:
        """
        对钻孔数据执行完整的年代插值流程

        Args:
            cleaned_df: 清洗后的多指标数据
            core_id: 钻孔ID
            save_processed: 是否保存处理结果

        Returns:
            完成插值的标准化时间序列数据
        """
        if self._chronology_df is None:
            self.load_chronology(core_id=core_id)

        df_with_age = self.add_age_column(cleaned_df)

        proxy_cols = [
            col for col in ["delta13C", "plant_index", "metal_pollution"]
            if col in df_with_age.columns
        ]

        uniform_ts = self.build_uniform_time_series(df_with_age, proxy_cols)

        final_ts = self.derive_climate_indices(uniform_ts)

        if save_processed:
            output_path = self.config.get_processed_data_path(
                f"{core_id or 'default'}_chronology_interpolated.csv"
            )
            final_ts.to_csv(output_path, index=False, encoding="utf-8-sig")

        return final_ts

    def get_sedimentation_rate(self, age_yrBP: float, window: int = 500) -> float:
        """
        计算指定年代附近的沉积速率

        Args:
            age_yrBP: 指定年代
            window: 计算窗口（年）

        Returns:
            沉积速率（cm/yr）
        """
        if self._chronology_df is None:
            raise ValueError("请先加载年代学数据")

        df = self._chronology_df
        mask = (df["age_yrBP"] >= age_yrBP - window) & (df["age_yrBP"] <= age_yrBP + window)
        window_df = df[mask]

        if len(window_df) < 2:
            return np.nan

        depth_diff = window_df["depth_cm"].iloc[-1] - window_df["depth_cm"].iloc[0]
        age_diff = window_df["age_yrBP"].iloc[-1] - window_df["age_yrBP"].iloc[0]

        if age_diff == 0:
            return np.nan

        return depth_diff / age_diff
