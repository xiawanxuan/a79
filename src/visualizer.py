"""
多层联动时序可视化模块
========================

基于 Plotly 构建科研级交互式可视化图表：
- 多面板联动时序子图（碳同位素、湿度、温度、重金属）
- 年代-深度双坐标轴展示
- 地层分界线标注
- 相关性热力图
- 支持导出为 HTML 交互式图表和 PNG 静态图片
"""

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import plotly.io as pio

from .config_manager import ConfigManager


class PeatVisualizer:
    """泥炭沉积多指标可视化器"""

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()
        self._proxy_colors = {
            "delta13C": "#2E86AB",
            "humidity": "#3CB371",
            "temperature": "#E63946",
            "plant_index": "#F4A261",
            "metal_pollution": "#6A4C93"
        }
        self._strata_colors = [
            "#E8F5E9", "#C8E6C9", "#A5D6A7", "#81C784", "#66BB6A"
        ]

    def add_strata_shading(self, fig: go.Figure, row: int, col: int = 1,
                          x_axis_type: str = "age") -> None:
        """
        在图表中添加地层背景色带

        Args:
            fig: Plotly Figure对象
            row: 子图行号
            col: 子图列号
            x_axis_type: 'age' 或 'depth'
        """
        layers = self.config.stratigraphy.get("stratigraphic_layers", [])
        for i, layer in enumerate(layers):
            if x_axis_type == "age":
                x0, x1 = layer["age_min"], layer["age_max"]
            else:
                x0, x1 = layer["depth_min"], layer["depth_max"]

            color = self._strata_colors[i % len(self._strata_colors)]
            fig.add_vrect(
                x0=x0, x1=x1,
                fillcolor=color, opacity=0.3,
                layer="below", line_width=0,
                row=row, col=col,
                annotation_text=layer["period"],
                annotation_position="top left",
                annotation_font_size=10,
                annotation_font_color="#555"
            )

    def _hex_to_rgba(self, hex_color: str, alpha: float = 0.15) -> str:
        """将十六进制颜色转换为RGBA格式"""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"

    def create_multi_panel_timeseries(self, df: pd.DataFrame,
                                     age_col: str = "age_yrBP",
                                     depth_col: str = "depth_cm",
                                     show_depth_axis: bool = True,
                                     title: Optional[str] = None) -> go.Figure:
        """
        创建多层联动时序子图

        Args:
            df: 标准化时序数据
            age_col: 年代列名
            depth_col: 深度列名
            show_depth_axis: 是否显示深度次坐标轴
            title: 图表标题

        Returns:
            Plotly Figure对象
        """
        if title is None:
            title = "湿地泥炭沉积多指标万年演化时序"

        panels_config = [
            {"col": "delta13C", "name": "有机碳同位素 δ¹³C", "unit": "‰ (VPDB)", "invert": True},
            {"col": "humidity", "name": "湿度指数", "unit": "标准化指数", "invert": False},
            {"col": "temperature", "name": "温度距平", "unit": "°C", "invert": False},
            {"col": "metal_pollution", "name": "重金属富集指数", "unit": "ppm", "invert": False},
        ]

        available_panels = [p for p in panels_config if p["col"] in df.columns]
        n_panels = len(available_panels)

        if n_panels == 0:
            raise ValueError("数据中没有可用的指标列")

        fig = make_subplots(
            rows=n_panels, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            subplot_titles=[p["name"] for p in available_panels]
        )

        for idx, panel in enumerate(available_panels):
            row = idx + 1
            y_data = df[panel["col"]].values
            color = self._proxy_colors.get(panel["col"], "#333")

            fig.add_trace(
                go.Scatter(
                    x=df[age_col], y=y_data,
                    mode="lines",
                    name=panel["name"],
                    line=dict(color=color, width=1.5),
                    fill="tozeroy" if not panel["invert"] else "tonexty",
                    fillcolor=self._hex_to_rgba(color, 0.15),
                    hovertemplate=f"年代: %{{x:.0f}} yr BP<br>{panel['name']}: %{{y:.3f}} {panel['unit']}<extra></extra>"
                ),
                row=row, col=1
            )

            smoothed = pd.Series(y_data).rolling(window=50, center=True, min_periods=5).mean()
            fig.add_trace(
                go.Scatter(
                    x=df[age_col], y=smoothed,
                    mode="lines",
                    name=f"{panel['name']} (500年滑动平均)",
                    line=dict(color=color, width=2.5, dash="solid"),
                    showlegend=False
                ),
                row=row, col=1
            )

            if panel["invert"]:
                fig.update_yaxes(autorange="reversed", row=row, col=1)

            fig.update_yaxes(
                title_text=f"{panel['name']}<br>({panel['unit']})",
                row=row, col=1,
                title_font_size=11
            )

            self.add_strata_shading(fig, row=row, x_axis_type="age")

        fig.update_xaxes(title_text="年代 (yr BP)", row=n_panels, col=1)

        if show_depth_axis and depth_col in df.columns:
            age_ticks = np.linspace(df[age_col].min(), df[age_col].max(), 6)
            depth_ticks = [np.interp(a, df[age_col], df[depth_col]) for a in age_ticks]

            for row in range(1, n_panels + 1):
                fig.layout[f"xaxis{row if row > 1 else ''}"].update(
                    tickmode="array",
                    tickvals=age_ticks,
                    ticktext=[f"{int(a)} yr<br>({int(d)} cm)" for a, d in zip(age_ticks, depth_ticks)]
                )

        fig.update_layout(
            title=dict(text=title, x=0.5, font_size=18),
            height=280 * n_panels,
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family="SimSun, Times New Roman, serif", size=12)
        )

        return fig

    def create_correlation_heatmap(self, corr_matrix: pd.DataFrame,
                                  p_value_matrix: Optional[pd.DataFrame] = None,
                                  title: Optional[str] = None) -> go.Figure:
        """
        创建相关性热力图

        Args:
            corr_matrix: 相关系数矩阵
            p_value_matrix: p值矩阵（可选，用于标注显著性
            title: 图表标题

        Returns:
            Plotly Figure对象
        """
        if title is None:
            title = "多指标皮尔逊相关性矩阵"

        labels = {
            "delta13C": "δ¹³C同位素",
            "humidity": "湿度指数",
            "temperature": "温度距平",
            "plant_index": "植物残体",
            "metal_pollution": "重金属",
            "age_yrBP": "年代",
            "depth_cm": "深度"
        }
        display_cols = [labels.get(c, c) for c in corr_matrix.columns]

        text_matrix = corr_matrix.round(3).astype(str)
        if p_value_matrix is not None:
            for i in range(len(corr_matrix)):
                for j in range(len(corr_matrix)):
                    p_val = p_value_matrix.iloc[i, j]
                    star = ""
                    if p_val < 0.001:
                        star = "***"
                    elif p_val < 0.01:
                        star = "**"
                    elif p_val < 0.05:
                        star = "*"
                    text_matrix.iloc[i, j] = f"{corr_matrix.iloc[i, j]:.3f}{star}"

        fig = px.imshow(
            corr_matrix,
            x=display_cols,
            y=display_cols,
            text_auto=False,
            color_continuous_scale="RdBu_r",
            range_color=[-1, 1],
            aspect="auto",
            title=title
        )

        fig.update_traces(
            text=text_matrix.values,
            texttemplate="%{text}",
            textfont_size=11
        )

        fig.update_layout(
            height=500,
            width=600,
            template="plotly_white",
            font=dict(family="SimSun, Times New Roman, serif")
        )

        return fig

    def create_age_depth_plot(self, chronology_df: pd.DataFrame,
                             title: Optional[str] = None) -> go.Figure:
        """
        创建年代-深度关系图

        Args:
            chronology_df: 年代学数据
            title: 图表标题

        Returns:
            Plotly Figure对象
        """
        if title is None:
            title = "泥炭沉积年代-深度关系曲线"

        fig = go.Figure()

        if "age_error" in chronology_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=chronology_df["age_yrBP"],
                    y=chronology_df["depth_cm"],
                    mode="markers",
                    marker=dict(color="#2E86AB", size=8),
                    error_x=dict(
                        type="data",
                        array=chronology_df["age_error"],
                        visible=True,
                        color="#888"
                    ),
                    name="测年控制点",
                    text=chronology_df.get("method", ""),
                    hovertemplate="年代: %{x:.0f} ± %{error_x_array:.0f} yr BP<br>深度: %{y:.1f} cm<extra></extra>"
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=chronology_df["age_yrBP"],
                    y=chronology_df["depth_cm"],
                    mode="markers+lines",
                    marker=dict(color="#2E86AB", size=8),
                    line=dict(color="#2E86AB", width=2),
                    name="年代-深度曲线"
                )
            )

        from scipy.interpolate import interp1d
        ages = chronology_df["age_yrBP"].values
        depths = chronology_df["depth_cm"].values
        interp_func = interp1d(ages, depths, kind="linear", bounds_error=False, fill_value="extrapolate")
        smooth_ages = np.linspace(ages.min(), ages.max(), 200)
        smooth_depths = interp_func(smooth_ages)

        fig.add_trace(
            go.Scatter(
                x=smooth_ages, y=smooth_depths,
                mode="lines",
                line=dict(color="#E63946", width=2, dash="dash"),
                name="线性插值"
            )
        )

        fig.update_yaxes(autorange="reversed", title_text="深度 (cm)")
        fig.update_xaxes(title_text="年代 (yr BP)")

        fig.update_layout(
            title=dict(text=title, x=0.5, font_size=16),
            height=500,
            width=700,
            template="plotly_white",
            font=dict(family="SimSun, Times New Roman, serif"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        return fig

    def create_rolling_correlation_plot(self, rolling_df: pd.DataFrame,
                                       col1: str, col2: str,
                                       age_col: str = "age_yrBP",
                                       title: Optional[str] = None) -> go.Figure:
        """
        创建滑动窗口相关性变化图

        Args:
            rolling_df: 滑动相关性数据
            col1: 变量1名称
            col2: 变量2名称
            age_col: 年代列名
            title: 图表标题

        Returns:
            Plotly Figure对象
        """
        if title is None:
            title = f"滑动窗口相关性: {col1} vs {col2}"

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=rolling_df[age_col], y=rolling_df["rolling_r"],
                mode="lines",
                line=dict(color="#6A4C93", width=2),
                fill="tozeroy",
                fillcolor="rgba(106, 76, 147, 0.2)",
                name="Pearson r"
            )
        )

        fig.add_hline(y=0, line_dash="dash", line_color="#888")

        fig.update_yaxes(title_text="Pearson相关系数", range=[-1, 1])
        fig.update_xaxes(title_text="年代 (yr BP)")

        fig.update_layout(
            title=dict(text=title, x=0.5, font_size=15),
            height=400,
            width=800,
            template="plotly_white",
            font=dict(family="SimSun, Times New Roman, serif")
        )

        return fig

    def save_figure(self, fig: go.Figure, filename: str,
                   save_html: bool = True, save_png: bool = True,
                   scale: int = 2) -> Dict[str, str]:
        """
        保存图表到文件

        Args:
            fig: Plotly Figure对象
            filename: 文件名（不含扩展名）
            save_html: 是否保存HTML交互式版本
            save_png: 是否保存PNG静态图片
            scale: PNG图片缩放比例

        Returns:
            保存的文件路径字典
        """
        saved = {}

        if save_html:
            html_path = self.config.get_figure_path(f"{filename}.html")
            pio.write_html(fig, file=html_path, include_plotlyjs="cdn")
            saved["html"] = html_path

        if save_png:
            png_path = self.config.get_figure_path(f"{filename}.png")
            try:
                pio.write_image(fig, file=png_path, scale=scale, engine="kaleido")
                saved["png"] = png_path
            except Exception:
                try:
                    pio.write_image(fig, file=png_path, scale=scale)
                    saved["png"] = png_path
                except Exception as e:
                    print(f"PNG导出失败（可能缺少kaleido）: {e}")

        return saved

    def generate_all_figures(self, timeseries_df: pd.DataFrame,
                            chronology_df: pd.DataFrame,
                            corr_report: Dict,
                            core_id: Optional[str] = None) -> Dict[str, Dict]:
        """
        批量生成所有图表

        Args:
            timeseries_df: 标准化时序数据
            chronology_df: 年代学数据
            corr_report: 相关性分析报告
            core_id: 钻孔ID

        Returns:
            各图表文件路径字典
        """
        prefix = core_id or "output"
        all_paths = {}

        fig_ts = self.create_multi_panel_timeseries(timeseries_df)
        all_paths["timeseries"] = self.save_figure(fig_ts, f"{prefix}_timeseries")

        fig_corr = self.create_correlation_heatmap(
            corr_report["full_correlation_matrix"],
            corr_report.get("p_value_matrix")
        )
        all_paths["correlation_heatmap"] = self.save_figure(fig_corr, f"{prefix}_correlation_heatmap")

        fig_ad = self.create_age_depth_plot(chronology_df)
        all_paths["age_depth"] = self.save_figure(fig_ad, f"{prefix}_age_depth")

        if "humidity" in timeseries_df.columns and "temperature" in timeseries_df.columns:
            from .correlation_analyzer import CorrelationAnalyzer
            analyzer = CorrelationAnalyzer(self.config)
            rolling = analyzer.compute_rolling_correlation(timeseries_df, "humidity", "temperature")
            if len(rolling) > 0:
                fig_roll = self.create_rolling_correlation_plot(rolling, "湿度指数", "温度距平")
                all_paths["rolling_correlation"] = self.save_figure(fig_roll, f"{prefix}_rolling_correlation")

        return all_paths

    def create_cross_region_diff_heatmap(self,
                                       difference_matrix: pd.DataFrame,
                                       core_metadata: Optional[pd.DataFrame] = None,
                                       title: Optional[str] = None,
                                       metric_label: str = "综合差异") -> go.Figure:
        """
        创建跨区域古环境差异热力图

        Args:
            difference_matrix: 钻孔间差异矩阵
            core_metadata: 钻孔元数据（用于标注区域信息）
            title: 图表标题
            metric_label: 差异度量标签

        Returns:
            Plotly Figure对象
        """
        if title is None:
            title = "跨区域湿地泥炭钻孔古环境差异热力图"

        display_labels = difference_matrix.index.tolist()
        if core_metadata is not None and "location" in core_metadata.columns:
            loc_map = dict(zip(core_metadata["core_id"], core_metadata["location"]))
            display_labels = [f"{cid}\n({loc_map.get(cid, cid)})" for cid in difference_matrix.index]

        values = difference_matrix.values
        np.fill_diagonal(values, np.nan)

        max_val = np.nanmax(values) if np.any(~np.isnan(values)) else 1.0
        if max_val == 0:
            max_val = 1.0

        fig = go.Figure(data=go.Heatmap(
            z=values,
            x=display_labels,
            y=display_labels,
            colorscale="Reds",
            zmid=0,
            zmin=0,
            zmax=max_val,
            text=[[f"{v:.3f}" if not np.isnan(v) else "-" for v in row] for row in values],
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate=(
                "钻孔X: %{x}<br>"
                "钻孔Y: %{y}<br>"
                f"{metric_label}: %{{z:.3f}}<extra></extra>"
            ),
            colorbar=dict(
                title=metric_label,
                titleside="right"
            )
        ))

        if core_metadata is not None and "region" in core_metadata.columns:
            regions = core_metadata.set_index("core_id")["region"].to_dict()
            unique_regions = list(set(regions.values()))
            region_colors = px.colors.qualitative.Set3[:len(unique_regions)]
            region_color_map = dict(zip(unique_regions, region_colors))

        fig.update_layout(
            title=dict(text=title, x=0.5, font_size=16),
            height=550 + 15 * len(display_labels),
            width=600 + 15 * len(display_labels),
            template="plotly_white",
            xaxis=dict(
                title="钻孔",
                tickangle=0,
                side="bottom"
            ),
            yaxis=dict(
                title="钻孔",
                autorange="reversed"
            ),
            font=dict(family="SimSun, Times New Roman, serif", size=11)
        )

        return fig

    def create_multi_core_timeseries_comparison(self,
                                              aligned_data: pd.DataFrame,
                                              proxy: str = "humidity",
                                              proxy_label: Optional[str] = None,
                                              age_col: str = "age_yrBP",
                                              core_filter: Optional[List[str]] = None,
                                              smooth_window: int = 5,
                                              title: Optional[str] = None) -> go.Figure:
        """
        创建多钻孔联动时序对比图（支持交互式筛选）

        Args:
            aligned_data: 对齐后的长格式数据
            proxy: 指标列名
            proxy_label: 指标显示名称
            age_col: 年代列名
            core_filter: 可选的钻孔ID过滤列表
            smooth_window: 平滑窗口（数据点数）
            title: 图表标题

        Returns:
            Plotly Figure对象
        """
        proxy_labels_map = {
            "humidity": "湿度指数",
            "temperature": "温度距平 (°C)",
            "delta13C": "δ¹³C同位素 (‰ VPDB)",
            "plant_index": "植物残体指数 (%)",
            "metal_pollution": "重金属富集 (ppm)"
        }
        if proxy_label is None:
            proxy_label = proxy_labels_map.get(proxy, proxy)

        if title is None:
            title = f"多钻孔{proxy_label}时序对比"

        if core_filter:
            plot_data = aligned_data[aligned_data["core_id"].isin(core_filter)].copy()
        else:
            plot_data = aligned_data.copy()

        if proxy not in plot_data.columns:
            raise ValueError(f"指标列 '{proxy}' 不存在于数据中")

        core_palette = [
            "#E63946", "#2E86AB", "#3CB371", "#F4A261",
            "#6A4C93", "#00B4D8", "#FF6B6B", "#2A9D8F"
        ]

        fig = go.Figure()

        unique_cores = plot_data["core_id"].unique().tolist()
        for i, core_id in enumerate(unique_cores):
            core_df = plot_data[plot_data["core_id"] == core_id].sort_values(age_col)
            if len(core_df) < 2:
                continue

            meta = self.config.get_core_metadata(core_id)
            location = meta.get("location", core_id)
            region = meta.get("region", "")
            legend_name = f"{location} ({region})" if region else location

            color = core_palette[i % len(core_palette)]

            raw_values = core_df[proxy].values
            if len(core_df) >= smooth_window * 2:
                smoothed = pd.Series(raw_values).rolling(
                    window=smooth_window, center=True, min_periods=1
                ).mean().values
            else:
                smoothed = raw_values

            rgba_color = self._hex_to_rgba(color, 0.12)

            fig.add_trace(go.Scatter(
                x=core_df[age_col].values,
                y=smoothed,
                mode="lines",
                name=legend_name,
                line=dict(color=color, width=2.0),
                legendgroup=core_id,
                hovertemplate=(
                    f"钻孔: {location}<br>"
                    "年代: %{x:.0f} yr BP<br>"
                    f"{proxy_label}: %{{y:.3f}}<extra></extra>"
                )
            ))

            fig.add_trace(go.Scatter(
                x=core_df[age_col].values,
                y=raw_values,
                mode="lines",
                name=f"{legend_name} (原始)",
                line=dict(color=color, width=0.8, dash="dot"),
                opacity=0.4,
                legendgroup=core_id,
                showlegend=False,
                hoverinfo="skip"
            ))

        self.add_strata_shading(fig, row=1, x_axis_type="age")

        fig.update_layout(
            title=dict(text=title, x=0.5, font_size=16),
            xaxis=dict(
                title="年代 (yr BP)",
                autorange="reversed"
            ),
            yaxis=dict(title=proxy_label),
            height=500,
            template="plotly_white",
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10)
            ),
            font=dict(family="SimSun, Times New Roman, serif", size=11),
            clickmode="event+select"
        )

        return fig

    def create_region_proxy_heatmap(self,
                                   period_statistics: pd.DataFrame,
                                   proxy: str = "humidity",
                                   stat: str = "mean",
                                   title: Optional[str] = None) -> go.Figure:
        """
        创建区域-时段指标热力图

        Args:
            period_statistics: 时段统计数据
            proxy: 指标名
            stat: 统计量名 (mean, std, trend)
            title: 图表标题

        Returns:
            Plotly Figure对象
        """
        proxy_display = {
            "humidity": "湿度指数",
            "temperature": "温度距平",
            "delta13C": "δ¹³C",
            "metal_pollution": "重金属"
        }.get(proxy, proxy)

        stat_display = {
            "mean": "平均值",
            "std": "标准差",
            "trend": "趋势斜率"
        }.get(stat, stat)

        if title is None:
            title = f"各区域钻孔分时段{proxy_display}{stat_display}对比"

        col_name = f"{proxy}_{stat}"
        if col_name not in period_statistics.columns:
            raise ValueError(f"统计列 '{col_name}' 不存在")

        pivot = period_statistics.pivot_table(
            index="location",
            columns="period_label",
            values=col_name,
            aggfunc="first"
        )

        sorted_cols = sorted(pivot.columns, key=lambda x: int(x.split("-")[0]))
        pivot = pivot[sorted_cols]

        colorscale = {
            "humidity": "Blues",
            "temperature": "RdYlBu_r",
            "delta13C": "Greens",
            "metal_pollution": "Oranges"
        }.get(proxy, "Viridis")

        fig = px.imshow(
            pivot.values,
            labels=dict(x="气候时段", y="钻孔位置", color=f"{proxy_display}"),
            x=list(pivot.columns),
            y=list(pivot.index),
            color_continuous_scale=colorscale,
            aspect="auto"
        )

        text_vals = [[f"{v:.2f}" if not np.isnan(v) else "-" for v in row] for row in pivot.values]
        fig.update_traces(
            text=text_vals,
            texttemplate="%{text}",
            textfont_size=11
        )

        fig.update_layout(
            title=dict(text=title, x=0.5, font_size=16),
            height=420 + 25 * len(pivot.index),
            width=800,
            template="plotly_white",
            font=dict(family="SimSun, Times New Roman, serif", size=11)
        )

        return fig

    def create_spatial_correlation_plot(self,
                                      spatial_corr_df: pd.DataFrame,
                                      title: Optional[str] = None) -> go.Figure:
        """
        创建空间相关性时序图

        Args:
            spatial_corr_df: 空间相关性数据
            title: 图表标题

        Returns:
            Plotly Figure对象
        """
        if title is None:
            title = "湿度-海拔/纬度空间相关性演变"

        var_display = {
            "elevation_m": "海拔 (m)",
            "latitude": "纬度 (°N)",
            "longitude": "经度 (°E)"
        }

        fig = go.Figure()

        colors = ["#2E86AB", "#E63946", "#3CB371"]
        for i, svar in enumerate(spatial_corr_df["spatial_variable"].unique()):
            sub = spatial_corr_df[spatial_corr_df["spatial_variable"] == svar].sort_values("age_yrBP")
            if len(sub) < 2:
                continue

            color = colors[i % len(colors)]
            label = var_display.get(svar, svar)

            fig.add_trace(go.Scatter(
                x=sub["age_yrBP"],
                y=sub["pearson_r"],
                mode="lines+markers",
                name=label,
                line=dict(color=color, width=2),
                marker=dict(size=5, color=color),
                error_y=dict(
                    type="data",
                    array=np.where(sub["p_value"] < 0.05, 0.05, 0),
                    visible=True,
                    color=color,
                    thickness=1
                ),
                hovertemplate=(
                    f"空间因子: {label}<br>"
                    "年代: %{x:.0f} yr BP<br>"
                    "Pearson r: %{y:.3f}<extra></extra>"
                )
            ))

        fig.add_hline(y=0, line_dash="dash", line_color="#888")
        fig.add_hrect(y0=-0.5, y1=0.5, fillcolor="#F5F5F5", opacity=0.3, layer="below", line_width=0)

        fig.update_layout(
            title=dict(text=title, x=0.5, font_size=16),
            xaxis=dict(
                title="年代 (yr BP)",
                autorange="reversed"
            ),
            yaxis=dict(title="Pearson 相关系数", range=[-1.1, 1.1]),
            height=420,
            width=800,
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            font=dict(family="SimSun, Times New Roman, serif", size=11)
        )

        return fig

    def generate_cross_region_figures(self,
                                    comparison_results: Dict,
                                    group_prefix: str = "cross_region") -> Dict[str, Dict]:
        """
        批量生成所有跨区域对比图表

        Args:
            comparison_results: 对比分析结果字典
            group_prefix: 文件名前缀

        Returns:
            图表文件路径字典
        """
        all_paths = {}

        diff_mats = comparison_results.get("difference_matrices", {})
        core_meta = comparison_results.get("core_metadata")

        for diff_name, diff_df in diff_mats.items():
            display_name = {
                "humidity_mean": "湿度差异",
                "temperature_mean": "温度差异",
                "combined": "综合古环境差异"
            }.get(diff_name, diff_name)
            fig = self.create_cross_region_diff_heatmap(
                diff_df, core_meta, metric_label=display_name
            )
            all_paths[f"diff_heatmap_{diff_name}"] = self.save_figure(
                fig, f"{group_prefix}_diff_{diff_name}"
            )

        aligned = comparison_results.get("aligned_data")
        if aligned is not None:
            for proxy in ["humidity", "temperature", "delta13C"]:
                if proxy in aligned.columns:
                    try:
                        fig = self.create_multi_core_timeseries_comparison(aligned, proxy=proxy)
                        all_paths[f"timeseries_comparison_{proxy}"] = self.save_figure(
                            fig, f"{group_prefix}_ts_compare_{proxy}"
                        )
                    except Exception:
                        pass

        period_stats = comparison_results.get("period_statistics")
        if period_stats is not None:
            for proxy in ["humidity", "temperature", "delta13C"]:
                if f"{proxy}_mean" in period_stats.columns:
                    try:
                        fig = self.create_region_proxy_heatmap(period_stats, proxy=proxy, stat="mean")
                        all_paths[f"region_period_heatmap_{proxy}"] = self.save_figure(
                            fig, f"{group_prefix}_region_period_{proxy}"
                        )
                    except Exception:
                        pass

        spatial_corr = comparison_results.get("spatial_correlation")
        if spatial_corr is not None and len(spatial_corr) > 0:
            try:
                fig = self.create_spatial_correlation_plot(spatial_corr)
                all_paths["spatial_correlation"] = self.save_figure(
                    fig, f"{group_prefix}_spatial_correlation"
                )
            except Exception:
                pass

        return all_paths
