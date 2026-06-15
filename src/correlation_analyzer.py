"""
多指标皮尔逊相关性矩阵计算模块
================================

负责计算多代用指标之间的皮尔逊相关系数矩阵，
并支持按地层分段的相关性分析，以及相关性显著性检验。
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from .config_manager import ConfigManager


class CorrelationAnalyzer:
    """多指标相关性分析器"""

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self._correlation_matrix: Optional[pd.DataFrame] = None
        self._p_value_matrix: Optional[pd.DataFrame] = None

    @property
    def correlation_matrix(self) -> Optional[pd.DataFrame]:
        """获取最近计算的皮尔逊相关系数矩阵"""
        return self._correlation_matrix

    @property
    def p_value_matrix(self) -> Optional[pd.DataFrame]:
        """获取最近计算的相关性显著性p值矩阵"""
        return self._p_value_matrix

    def compute_pearson_correlation(self, df: pd.DataFrame,
                                   columns: Optional[List[str]] = None,
                                   min_periods: int = 10) -> pd.DataFrame:
        """
        计算皮尔逊相关系数矩阵

        Args:
            df: 输入数据
            columns: 需要计算相关性的列名列表，若为None则使用所有数值列
            min_periods: 计算每对相关性所需的最小有效观测数

        Returns:
            皮尔逊相关系数矩阵DataFrame
        """
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        data = df[columns].dropna(thresh=min_periods, axis=1)
        corr_matrix = data.corr(method="pearson", min_periods=min_periods)

        self._correlation_matrix = corr_matrix
        return corr_matrix

    def compute_p_values(self, df: pd.DataFrame,
                        columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        计算皮尔逊相关性的p值矩阵（显著性检验

        Args:
            df: 输入数据
            columns: 需要计算的列名列表

        Returns:
            p值矩阵DataFrame
        """
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()

        n_cols = len(columns)
        p_matrix = pd.DataFrame(np.ones((n_cols, n_cols)), columns=columns, index=columns)

        for i, col1 in enumerate(columns):
            for j, col2 in enumerate(columns):
                if i == j:
                    p_matrix.loc[col1, col2] = 0.0
                elif i < j:
                    valid_data = df[[col1, col2]].dropna()
                    if len(valid_data) >= 3:
                        _, p_val = stats.pearsonr(valid_data[col1], valid_data[col2])
                        p_matrix.loc[col1, col2] = p_val
                        p_matrix.loc[col2, col1] = p_val

        self._p_value_matrix = p_matrix
        return p_matrix

    def compute_correlation_with_significance(self, df: pd.DataFrame,
                                            columns: Optional[List[str]] = None) -> Dict:
        """
        同时计算相关系数矩阵和p值矩阵

        Args:
            df: 输入数据
            columns: 需要计算的列名列表

        Returns:
            包含 'correlation' 和 'p_values' 两个DataFrame的字典
        """
        corr = self.compute_pearson_correlation(df, columns)
        p_vals = self.compute_p_values(df, columns)
        return {"correlation": corr, "p_values": p_vals}

    def get_significant_correlations(self, alpha: float = 0.05) -> pd.DataFrame:
        """
        获取具有统计显著性的相关关系

        Args:
            alpha: 显著性水平

        Returns:
            包含显著相关关系的DataFrame
        """
        if self._correlation_matrix is None or self._p_value_matrix is None:
            raise ValueError("请先计算相关性矩阵和p值矩阵")

        records = []
        columns = self._correlation_matrix.columns.tolist()

        for i, col1 in enumerate(columns):
            for j, col2 in enumerate(columns):
                if i < j:
                    corr_val = self._correlation_matrix.loc[col1, col2]
                    p_val = self._p_value_matrix.loc[col1, col2]
                    if p_val < alpha and not np.isnan(corr_val):
                        records.append({
                            "variable_1": col1,
                            "variable_2": col2,
                            "pearson_r": round(corr_val, 4),
                            "p_value": round(p_val, 6),
                            "significant": p_val < alpha,
                            "strength": self._classify_strength(corr_val)
                        })

        result = pd.DataFrame(records)
        if len(result) > 0:
            result = result.sort_values("pearson_r", key=abs, ascending=False)
        return result

    def _classify_strength(self, r: float) -> str:
        """分类相关强度"""
        abs_r = abs(r)
        if abs_r >= 0.8:
            return "极强"
        elif abs_r >= 0.6:
            return "强"
        elif abs_r >= 0.4:
            return "中等"
        elif abs_r >= 0.2:
            return "弱"
        else:
            return "极弱或无"

    def compute_by_strata(self, df: pd.DataFrame,
                         columns: Optional[List[str]] = None,
                         age_col: str = "age_yrBP") -> Dict[str, pd.DataFrame]:
        """
        按地层分段计算相关性矩阵

        Args:
            df: 输入数据（需包含年代列）
            columns: 需要计算的列名列表
            age_col: 年代列名

        Returns:
            各地层名称映射到对应相关性矩阵的字典
        """
        strata_results = {}
        layers = self.config.stratigraphy.get("stratigraphic_layers", [])

        for layer in layers:
            age_min = layer["age_min"]
            age_max = layer["age_max"]
            layer_df = df[(df[age_col] >= age_min) & (df[age_col] < age_max)]

            if len(layer_df) >= 10:
                try:
                    corr = self.compute_pearson_correlation(layer_df, columns)
                    strata_results[layer["name"]] = corr
                except Exception:
                    pass

        return strata_results

    def compute_rolling_correlation(self, df: pd.DataFrame,
                                   col1: str, col2: str,
                                   window: int = 100,
                                   age_col: str = "age_yrBP") -> pd.DataFrame:
        """
        计算滑动窗口相关性（用于分析相关性随时间的变化

        Args:
            df: 输入数据
            col1: 第一个变量列名
            col2: 第二个变量列名
            window: 滑动窗口大小（数据点数）
            age_col: 年代列名

        Returns:
            包含滚动相关系数的DataFrame
        """
        data = df[[age_col, col1, col2]].dropna().sort_values(age_col)
        result = pd.DataFrame({age_col: data[age_col].values})
        result["rolling_r"] = data[col1].rolling(window=window, center=True).corr(data[col2])
        return result.dropna()

    def generate_correlation_report(self, df: pd.DataFrame,
                                   columns: Optional[List[str]] = None,
                                   alpha: float = 0.05) -> Dict:
        """
        生成完整的相关性分析报告

        Args:
            df: 输入数据
            columns: 需要分析的列名列表
            alpha: 显著性水平

        Returns:
            包含相关性矩阵、p值矩阵、显著相关关系、分地层相关性的完整报告字典
        """
        results = self.compute_correlation_with_significance(df, columns)
        significant = self.get_significant_correlations(alpha)
        by_strata = self.compute_by_strata(df, columns)

        return {
            "full_correlation_matrix": results["correlation"],
            "p_value_matrix": results["p_values"],
            "significant_correlations": significant,
            "by_strata_correlation": by_strata
        }
