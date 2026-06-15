"""
跨区域泥炭钻孔对比分析模块
============================

导入多个区域泥炭沉积数据，执行：
- 多钻孔数据批量处理管道
- 统一时间轴对齐与标准化
- 古环境指标差异矩阵计算
- 区域聚类与对比统计
- 与原时序图表联动筛选的数据集准备
"""

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import pdist, squareform
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import AgglomerativeClustering

from .config_manager import ConfigManager
from .data_cleaner import PeatDataCleaner
from .chronology_interpolator import ChronologyInterpolator
from .correlation_analyzer import CorrelationAnalyzer


class CrossRegionComparator:
    """跨区域泥炭钻孔对比分析器"""

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self.cleaner = PeatDataCleaner(self.config)
        self.interpolator = ChronologyInterpolator(self.config)
        self.analyzer = CorrelationAnalyzer(self.config)

        self._core_timeseries: Dict[str, pd.DataFrame] = {}
        self._core_chronology: Dict[str, pd.DataFrame] = {}
        self._core_cleaning_report: Dict[str, pd.DataFrame] = {}
        self._aligned_data: Optional[pd.DataFrame] = None
        self._difference_matrix: Dict[str, pd.DataFrame] = {}
        self._comparison_stats: Optional[pd.DataFrame] = None

    @property
    def core_timeseries(self) -> Dict[str, pd.DataFrame]:
        """获取各钻孔标准化时序数据"""
        return self._core_timeseries

    @property
    def aligned_data(self) -> Optional[pd.DataFrame]:
        """获取对齐后的多钻孔联合数据表"""
        return self._aligned_data

    @property
    def difference_matrix(self) -> Dict[str, pd.DataFrame]:
        """获取各指标差异矩阵"""
        return self._difference_matrix

    @property
    def comparison_stats(self) -> Optional[pd.DataFrame]:
        """获取钻孔对比统计摘要"""
        return self._comparison_stats

    def process_single_core(self, core_id: str,
                           generate_sample: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        处理单个钻孔数据（清洗+插值）

        Args:
            core_id: 钻孔ID
            generate_sample: 是否生成示例数据

        Returns:
            (清洗后数据, 标准化时序数据)
        """
        if generate_sample:
            from .sample_data_generator import generate_all_sample_data
            generate_all_sample_data(self.config, core_id)

        cleaned_df = self.cleaner.clean_and_merge_all(core_id=core_id, save_processed=True)
        cleaning_report = self.cleaner.get_cleaning_report()
        self._core_cleaning_report[core_id] = cleaning_report

        chronology_df = self.interpolator.load_chronology(core_id=core_id)
        self._core_chronology[core_id] = chronology_df

        timeseries_df = self.interpolator.interpolate_core_data(cleaned_df, core_id=core_id, save_processed=True)
        self._core_timeseries[core_id] = timeseries_df

        return cleaned_df, timeseries_df

    def process_cores_batch(self, core_ids: List[str],
                           generate_sample: bool = False,
                           verbose: bool = True) -> Dict[str, pd.DataFrame]:
        """
        批量处理多个钻孔数据

        Args:
            core_ids: 钻孔ID列表
            generate_sample: 是否生成示例数据
            verbose: 是否打印进度

        Returns:
            钻孔ID映射到时序数据的字典
        """
        for i, core_id in enumerate(core_ids, 1):
            if verbose:
                print(f"[{i}/{len(core_ids)}] 处理钻孔: {core_id}")
            try:
                self.process_single_core(core_id, generate_sample=generate_sample)
            except Exception as e:
                print(f"  警告: 钻孔 {core_id} 处理失败: {e}")

        return self._core_timeseries

    def process_comparison_group(self, group_id: Optional[str] = None,
                                generate_sample: bool = False,
                                verbose: bool = True) -> Dict[str, pd.DataFrame]:
        """
        处理整个对比组

        Args:
            group_id: 对比组ID，None则使用默认对比组
            generate_sample: 是否生成示例数据
            verbose: 是否打印进度

        Returns:
            钻孔ID映射到时序数据的字典
        """
        group = self.config.get_comparison_group(group_id)
        if verbose:
            print(f"处理对比组: {group.get('name', group_id)}")
            print(f"包含钻孔: {group['cores']}")
        return self.process_cores_batch(group["cores"], generate_sample=generate_sample, verbose=verbose)

    def align_timeseries_to_common_grid(self,
                                       proxy_cols: Optional[List[str]] = None,
                                       age_step: Optional[int] = None,
                                       min_age: Optional[float] = None,
                                       max_age: Optional[float] = None) -> pd.DataFrame:
        """
        将多个钻孔时序对齐到统一时间网格

        Args:
            proxy_cols: 需要对齐的指标列，默认全部可用指标
            age_step: 时间步长，默认从配置读取
            min_age: 最小年代，默认取所有钻孔交集
            max_age: 最大年代，默认取所有钻孔交集

        Returns:
            长格式对齐数据表，列为 [age_yrBP, core_id, region, location, 各指标列]
        """
        if not self._core_timeseries:
            raise ValueError("请先处理至少一个钻孔数据")

        interp_rules = self.config.get_interpolation_rules()
        if age_step is None:
            age_step = interp_rules.get("age_step", 10)

        all_min_ages = []
        all_max_ages = []
        for core_id, ts_df in self._core_timeseries.items():
            all_min_ages.append(ts_df["age_yrBP"].min())
            all_max_ages.append(ts_df["age_yrBP"].max())

        if min_age is None:
            min_age = max(all_min_ages)
        if max_age is None:
            max_age = min(all_max_ages)

        common_ages = np.arange(min_age, max_age + age_step, age_step)

        if proxy_cols is None:
            proxy_cols = []
            for ts_df in self._core_timeseries.values():
                cols = [c for c in ts_df.columns
                       if c not in ["age_yrBP", "depth_cm"]]
                for c in cols:
                    if c not in proxy_cols:
                        proxy_cols.append(c)

        records = []
        for core_id, ts_df in self._core_timeseries.items():
            meta = self.config.get_core_metadata(core_id)

            ts_sorted = ts_df.sort_values("age_yrBP")
            core_ages = ts_sorted["age_yrBP"].values

            row_template = {
                "core_id": core_id,
                "region": meta.get("region", ""),
                "location": meta.get("location", ""),
                "latitude": meta.get("latitude"),
                "longitude": meta.get("longitude"),
                "elevation_m": meta.get("elevation_m")
            }

            for age in common_ages:
                row = row_template.copy()
                row["age_yrBP"] = float(age)

                age_idx = np.searchsorted(core_ages, age)
                for col in proxy_cols:
                    if col in ts_sorted.columns:
                        if age_idx < len(core_ages) and core_ages[age_idx] == age:
                            row[col] = ts_sorted.iloc[age_idx][col]
                        elif 0 < age_idx < len(core_ages):
                            from scipy.interpolate import interp1d
                            try:
                                valid = ts_sorted[[col]].dropna()
                                if len(valid) >= 2:
                                    interp = interp1d(
                                        ts_sorted["age_yrBP"].values,
                                        ts_sorted[col].values,
                                        kind="linear",
                                        bounds_error=False,
                                        fill_value=np.nan
                                    )
                                    row[col] = float(interp(age))
                                else:
                                    row[col] = np.nan
                            except Exception:
                                row[col] = np.nan
                        else:
                            row[col] = np.nan
                    else:
                        row[col] = np.nan

                records.append(row)

        aligned_df = pd.DataFrame(records)
        self._aligned_data = aligned_df
        return aligned_df

    def compute_period_stats(self, aligned_df: Optional[pd.DataFrame] = None,
                            age_bins: Optional[List[Tuple[int, int]]] = None,
                            proxy_cols: Optional[List[str]] = None) -> pd.DataFrame:
        """
        按气候时段计算各钻孔指标统计量

        Args:
            aligned_df: 对齐后的数据，None则使用内部数据
            age_bins: 年代分箱 [(start, end), ...]，默认使用地层配置
            proxy_cols: 需要统计的指标列

        Returns:
            分层统计DataFrame
        """
        if aligned_df is None:
            aligned_df = self._aligned_data
        if aligned_df is None:
            raise ValueError("请先执行对齐操作或传入aligned_df")

        if age_bins is None:
            layers = self.config.stratigraphy.get("stratigraphic_layers", [])
            age_bins = [(l["age_min"], l["age_max"]) for l in layers]

        if proxy_cols is None:
            proxy_cols = [c for c in aligned_df.columns
                         if c not in ["core_id", "region", "location",
                                      "latitude", "longitude", "elevation_m", "age_yrBP"]]

        records = []
        for core_id in aligned_df["core_id"].unique():
            core_df = aligned_df[aligned_df["core_id"] == core_id]
            meta = self.config.get_core_metadata(core_id)

            for age_start, age_end in age_bins:
                period_df = core_df[(core_df["age_yrBP"] >= age_start) &
                                   (core_df["age_yrBP"] < age_end)]

                if len(period_df) == 0:
                    continue

                record = {
                    "core_id": core_id,
                    "region": meta.get("region", ""),
                    "location": meta.get("location", ""),
                    "age_start": age_start,
                    "age_end": age_end,
                    "period_label": f"{age_start}-{age_end} yr BP",
                    "sample_count": len(period_df)
                }

                for col in proxy_cols:
                    if col in period_df.columns:
                        record[f"{col}_mean"] = period_df[col].mean()
                        record[f"{col}_std"] = period_df[col].std()
                        record[f"{col}_min"] = period_df[col].min()
                        record[f"{col}_max"] = period_df[col].max()
                        record[f"{col}_trend"] = self._compute_trend(period_df["age_yrBP"], period_df[col])

                records.append(record)

        stats_df = pd.DataFrame(records)
        self._comparison_stats = stats_df
        return stats_df

    def _compute_trend(self, ages: pd.Series, values: pd.Series) -> float:
        """计算线性趋势斜率（单位/1000年）"""
        valid = pd.DataFrame({"age": ages, "val": values}).dropna()
        if len(valid) < 3:
            return np.nan
        try:
            slope, _, _, _, _ = stats.linregress(valid["age"], valid["val"])
            return slope * 1000.0
        except Exception:
            return np.nan

    def compute_difference_matrix(self, period_stats: Optional[pd.DataFrame] = None,
                                 proxy: str = "humidity",
                                 stat: str = "mean",
                                 normalize: bool = True) -> pd.DataFrame:
        """
        计算指定指标和统计量的钻孔间差异矩阵

        Args:
            period_stats: 时段统计数据，None则使用内部数据
            proxy: 指标名（如 humidity, temperature, delta13C）
            stat: 统计量（mean, std, trend）
            normalize: 是否按极差标准化

        Returns:
            钻孔间绝对差异矩阵
        """
        if period_stats is None:
            period_stats = self._comparison_stats
        if period_stats is None:
            raise ValueError("请先计算时段统计或传入period_stats")

        col_name = f"{proxy}_{stat}"
        if col_name not in period_stats.columns:
            raise ValueError(f"统计列 '{col_name}' 不存在于统计数据中")

        pivot = period_stats.pivot_table(
            index="core_id",
            columns="period_label",
            values=col_name,
            aggfunc="first"
        )

        if normalize:
            scaler = StandardScaler()
            values_scaled = scaler.fit_transform(pivot.fillna(0))
            diff_condensed = pdist(values_scaled, metric="euclidean")
        else:
            values = pivot.fillna(pivot.mean()).values
            diff_condensed = pdist(values, metric="euclidean")

        diff_matrix = squareform(diff_condensed)
        core_labels = pivot.index.tolist()
        diff_df = pd.DataFrame(diff_matrix, index=core_labels, columns=core_labels)

        self._difference_matrix[f"{proxy}_{stat}"] = diff_df
        return diff_df

    def compute_combined_difference(self, period_stats: Optional[pd.DataFrame] = None,
                                   proxy_weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """
        计算多指标加权综合差异矩阵

        Args:
            period_stats: 时段统计数据
            proxy_weights: 指标权重字典，默认各指标等权

        Returns:
            综合差异矩阵
        """
        if proxy_weights is None:
            proxy_weights = {"humidity": 0.35, "temperature": 0.35,
                           "delta13C": 0.15, "metal_pollution": 0.15}

        matrices = []
        weights = []
        for proxy, weight in proxy_weights.items():
            try:
                diff = self.compute_difference_matrix(period_stats, proxy, "mean", normalize=True)
                matrices.append(diff.values)
                weights.append(weight)
            except Exception:
                pass

        if not matrices:
            raise ValueError("无法计算任何指标的差异矩阵")

        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        combined = np.zeros_like(matrices[0])
        for mat, w in zip(matrices, normalized_weights):
            combined += w * mat

        labels = matrices[0].shape[0]
        core_ids = list(self._core_timeseries.keys())[:labels]
        combined_df = pd.DataFrame(combined, index=core_ids, columns=core_ids)

        self._difference_matrix["combined"] = combined_df
        return combined_df

    def cluster_cores(self, difference_matrix: Optional[pd.DataFrame] = None,
                     n_clusters: int = 3) -> pd.DataFrame:
        """
        基于差异矩阵对钻孔进行层次聚类

        Args:
            difference_matrix: 差异矩阵，None则使用综合差异
            n_clusters: 聚类数量

        Returns:
            包含钻孔聚类标签的DataFrame
        """
        if difference_matrix is None:
            if "combined" not in self._difference_matrix:
                raise ValueError("请先计算差异矩阵")
            difference_matrix = self._difference_matrix["combined"]

        clustering = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric="precomputed",
            linkage="average"
        )
        labels = clustering.fit_predict(difference_matrix.values)

        result = pd.DataFrame({
            "core_id": difference_matrix.index.tolist(),
            "cluster": labels
        })

        meta_df = self.config.get_all_core_metadata()
        result = result.merge(meta_df, on="core_id", how="left")
        return result

    def compute_spatial_correlation(self, aligned_df: Optional[pd.DataFrame] = None,
                                   proxy: str = "humidity") -> pd.DataFrame:
        """
        计算各年代钻孔指标与海拔/纬度的空间相关性

        Args:
            aligned_df: 对齐后的数据
            proxy: 指标名

        Returns:
            各年代空间相关性系数
        """
        if aligned_df is None:
            aligned_df = self._aligned_data
        if aligned_df is None:
            raise ValueError("请先执行对齐操作或传入aligned_df")

        if proxy not in aligned_df.columns:
            raise ValueError(f"指标 '{proxy}' 不存在于对齐数据中")

        records = []
        for age in aligned_df["age_yrBP"].unique():
            age_df = aligned_df[aligned_df["age_yrBP"] == age].dropna(subset=[proxy])
            if len(age_df) < 4:
                continue

            for spatial_var in ["elevation_m", "latitude", "longitude"]:
                if spatial_var not in age_df.columns:
                    continue
                valid = age_df[[proxy, spatial_var]].dropna()
                if len(valid) >= 4:
                    try:
                        r, p = stats.pearsonr(valid[proxy], valid[spatial_var])
                        records.append({
                            "age_yrBP": age,
                            "spatial_variable": spatial_var,
                            "proxy": proxy,
                            "pearson_r": r,
                            "p_value": p,
                            "n_cores": len(valid)
                        })
                    except Exception:
                        pass

        return pd.DataFrame(records)

    def generate_comparison_report_data(self, group_id: Optional[str] = None,
                                       generate_sample: bool = False,
                                       n_clusters: int = 3) -> Dict:
        """
        生成完整的对比分析数据集（供可视化和报告使用）

        Args:
            group_id: 对比组ID
            generate_sample: 是否生成示例数据
            n_clusters: 聚类数量

        Returns:
            包含所有对比分析结果的字典
        """
        if not self._core_timeseries:
            self.process_comparison_group(group_id, generate_sample=generate_sample)

        aligned = self.align_timeseries_to_common_grid()
        period_stats = self.compute_period_stats(aligned)

        diff_humidity = self.compute_difference_matrix(period_stats, "humidity", "mean")
        diff_temperature = self.compute_difference_matrix(period_stats, "temperature", "mean")
        diff_combined = self.compute_combined_difference(period_stats)

        clusters = self.cluster_cores(diff_combined, n_clusters=n_clusters)

        spatial_corr = None
        if len(self._core_timeseries) >= 4:
            try:
                spatial_corr = self.compute_spatial_correlation(aligned, "humidity")
            except Exception:
                pass

        core_meta = self.config.get_all_core_metadata()

        return {
            "core_timeseries": self._core_timeseries,
            "core_chronology": self._core_chronology,
            "core_cleaning_report": self._core_cleaning_report,
            "aligned_data": aligned,
            "period_statistics": period_stats,
            "difference_matrices": {
                "humidity_mean": diff_humidity,
                "temperature_mean": diff_temperature,
                "combined": diff_combined
            },
            "clusters": clusters,
            "spatial_correlation": spatial_corr,
            "core_metadata": core_meta,
            "comparison_group": self.config.get_comparison_group(group_id) if group_id else None
        }
