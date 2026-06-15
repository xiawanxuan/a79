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
