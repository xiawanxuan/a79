"""
标准化科研图表报告生成模块
============================

基于 python-docx 一键生成包含交互式时序图表、
相关性统计表的完整 Word 科研报告。
"""

import os
import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config_manager import ConfigManager


class ReportGenerator:
    """科研报告生成器"""

    def __init__(self, config: Optional[ConfigManager] = None):
        self.config = config or ConfigManager()

    def _try_import_docx(self):
        """尝试导入 python-docx 库"""
        try:
            from docx import Document
            from docx.shared import Inches, Pt, Cm, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.enum.table import WD_TABLE_ALIGNMENT
            from docx.oxml.ns import qn
            return Document, Inches, Pt, Cm, RGBColor, WD_ALIGN_PARAGRAPH, WD_TABLE_ALIGNMENT, qn
        except ImportError:
            raise ImportError(
                "请安装 python-docx 库: pip install python-docx"
            )

    def _setup_chinese_font(self, run, font_name: str = "宋体", size: int = 12, bold: bool = False):
        """设置中文字体"""
        _, _, Pt, _, RGBColor, _, _, qn = self._try_import_docx()
        run.font.name = font_name
        run.font.size = Pt(size)
        run.font.bold = bold
        r = run._element
        rPr = r.get_or_add_rPr()
        rFonts = rPr.find(qn('w:rFonts'))
        if rFonts is None:
            rFonts = rPr.makeelement(qn('w:rFonts'), {})
            rPr.append(rFonts)
        rFonts.set(qn('w:eastAsia'), font_name)

    def _add_heading_cn(self, doc, text: str, level: int = 1):
        """添加中文标题"""
        _, _, Pt, _, _, WD_ALIGN_PARAGRAPH, _, qn = self._try_import_docx()
        heading = doc.add_heading(text, level=level)
        for run in heading.runs:
            self._setup_chinese_font(run, size=18 - level * 2, bold=True)
        return heading

    def _add_paragraph_cn(self, doc, text: str, font_size: int = 12,
                        bold: bool = False, alignment: str = "left"):
        """添加中文段落"""
        _, _, _, _, _, WD_ALIGN_PARAGRAPH, _, _ = self._try_import_docx()
        para = doc.add_paragraph()
        align_map = {
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
            "justify": WD_ALIGN_PARAGRAPH.JUSTIFY
        }
        para.alignment = align_map.get(alignment, WD_ALIGN_PARAGRAPH.LEFT)
        run = para.add_run(text)
        self._setup_chinese_font(run, size=font_size, bold=bold)
        return para

    def _add_dataframe_table(self, doc, df: pd.DataFrame, title: str = "",
                            float_digits: int = 4):
        """将DataFrame转换为Word表格"""
        _, _, _, _, _, _, WD_TABLE_ALIGNMENT, _ = self._try_import_docx()

        if title:
            self._add_paragraph_cn(doc, title, font_size=12, bold=True)

        n_rows, n_cols = df.shape
        table = doc.add_table(rows=n_rows + 1, cols=n_cols)
        table.style = "Light Grid Accent 1"
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        for j, col_name in enumerate(df.columns):
            cell = table.rows[0].cells[j]
            cell.text = str(col_name)
            for para in cell.paragraphs:
                for run in para.runs:
                    self._setup_chinese_font(run, size=10, bold=True)

        for i in range(n_rows):
            for j in range(n_cols):
                cell = table.rows[i + 1].cells[j]
                value = df.iloc[i, j]
                if isinstance(value, float):
                    cell.text = f"{value:.{float_digits}f}"
                else:
                    cell.text = str(value)
                for para in cell.paragraphs:
                    for run in para.runs:
                        self._setup_chinese_font(run, size=10)

        doc.add_paragraph()

    def _add_image_safe(self, doc, image_path: str, width_inches: float = 6.0):
        """安全添加图片"""
        _, Inches, _, _, _, _, _, _ = self._try_import_docx()
        if image_path and os.path.exists(image_path):
            try:
                doc.add_picture(image_path, width=Inches(width_inches))
                last_paragraph = doc.paragraphs[-1]
                last_paragraph.alignment = 1
            except Exception as e:
                self._add_paragraph_cn(doc, f"[图片插入失败: {image_path} - {str(e)}]")
        else:
            self._add_paragraph_cn(doc, f"[图片文件不存在: {image_path}]")

    def generate_research_report(self,
                                timeseries_df: pd.DataFrame,
                                corr_report: Dict,
                                cleaning_report: pd.DataFrame,
                                figure_paths: Dict[str, Dict],
                                chronology_df: Optional[pd.DataFrame] = None,
                                core_id: Optional[str] = None,
                                output_filename: Optional[str] = None) -> str:
        """
        生成完整的科研报告

        Args:
            timeseries_df: 标准化时序数据
            corr_report: 相关性分析报告
            cleaning_report: 数据清洗报告
            figure_paths: 图表文件路径
            chronology_df: 年代学数据
            core_id: 钻孔ID
            output_filename: 输出文件名

        Returns:
            生成的Word报告文件路径
        """
        Document, Inches, Pt, Cm, RGBColor, WD_ALIGN_PARAGRAPH, WD_TABLE_ALIGNMENT, qn = self._try_import_docx()

        if core_id is None:
            core_id = self.config.paths.get("default_core", "unknown")
        if output_filename is None:
            output_filename = f"{core_id}_research_report_{datetime.datetime.now().strftime('%Y%m%d')}.docx"

        output_path = self.config.get_report_path(output_filename)

        doc = Document()

        section = doc.sections[0]
        section.page_height = Cm(29.7)
        section.page_width = Cm(21)
        section.top_margin = Cm(2.54)
        section.bottom_margin = Cm(2.54)
        section.left_margin = Cm(3.18)
        section.right_margin = Cm(3.18)

        self._add_heading_cn(doc, "湿地泥炭沉积多指标古气候分析报告", level=0)
        self._add_paragraph_cn(doc, f"钻孔编号: {core_id}", font_size=12, alignment="center")
        self._add_paragraph_cn(doc, f"报告生成日期: {datetime.datetime.now().strftime('%Y年%m月%d日')}", font_size=12, alignment="center")
        self._add_paragraph_cn(doc, f"编制单位: 湿地古气候研究所", font_size=12, alignment="center")

        doc.add_page_break()

        self._add_heading_cn(doc, "一、研究概述", level=1)
        self._add_paragraph_cn(doc,
            "本报告基于泥炭沉积多代用指标（碳同位素、植物残体、重金属）数据，"
            "通过年代-深度模型重建了研究区万年尺度的水文和温度演化历史。"
            "分析流程包括原始数据自动清洗、年代学插值校准、多指标皮尔逊相关性分析以及"
            "多层联动时序可视化。",
            font_size=12, alignment="justify"
        )

        try:
            data_source = self.config.get_data_source(core_id)
            self._add_paragraph_cn(doc, f"研究地点: {data_source.get('location', '未知')}", font_size=12)
            self._add_paragraph_cn(doc, f"数据描述: {data_source.get('description', '')}", font_size=12)
        except Exception:
            pass

        self._add_heading_cn(doc, "二、数据质量与清洗", level=1)
        self._add_paragraph_cn(doc,
            "原始实验数据经过严格的质量控制，主要清洗步骤包括：仪器噪声平滑（Savitzky-Golay滤波）、"
            "异常离群值剔除（IQR方法，1.5倍四分位距）、超出地球化学合理范围的数据过滤、"
            "以及缺失值处理。各代用指标的清洗统计如下：",
            font_size=12, alignment="justify"
        )

        cleaning_display = cleaning_report.copy()
        cleaning_display.columns = [
            "代用指标", "原始数据点数", "噪声平滑处理", "离群值剔除",
            "超出范围剔除", "缺失值剔除", "最终有效点数"
        ]
        self._add_dataframe_table(doc, cleaning_display, "表1 各代用指标数据清洗统计")

        self._add_heading_cn(doc, "三、年代学框架", level=1)
        if chronology_df is not None:
            self._add_paragraph_cn(doc,
                f"本次研究共获得 {len(chronology_df)} 个可靠的测年控制点，"
                f"年代范围覆盖 {chronology_df['age_yrBP'].min():.0f} – {chronology_df['age_yrBP'].max():.0f} yr BP，"
                f"对应沉积深度 {chronology_df['depth_cm'].min():.1f} – {chronology_df['depth_cm'].max():.1f} cm。"
                f"采用线性插值方法构建连续的年代-深度转换模型，时间分辨率为10年。",
                font_size=12, alignment="justify"
            )

            ad_png = figure_paths.get("age_depth", {}).get("png", "")
            if ad_png:
                self._add_image_safe(doc, ad_png, width_inches=5.5)
                self._add_paragraph_cn(doc, "图1 泥炭沉积年代-深度关系曲线", font_size=10, bold=True, alignment="center")
        else:
            self._add_paragraph_cn(doc, "年代学数据待补充。", font_size=12)

        self._add_heading_cn(doc, "四、多指标万年演化时序", level=1)
        self._add_paragraph_cn(doc,
            "下图同步展示了碳同位素（δ¹³C）、湿度指数、温度距平和重金属富集指数的万年波动趋势。"
            "各面板共享同一时间轴（yr BP），光标联动显示各指标在同一年代的数值。"
            "浅色填充区域指示不同地层单元，便于识别气候阶段。",
            font_size=12, alignment="justify"
        )

        ts_png = figure_paths.get("timeseries", {}).get("png", "")
        if ts_png:
            self._add_image_safe(doc, ts_png, width_inches=6.2)
            self._add_paragraph_cn(doc, "图2 湿地泥炭多指标万年演化联动时序图", font_size=10, bold=True, alignment="center")

        self._add_heading_cn(doc, "五、多指标相关性分析", level=1)
        self._add_paragraph_cn(doc,
            "采用皮尔逊相关分析量化各代用指标之间的线性关系。"
            "显著性水平设定为α=0.05，*表示p<0.05，**表示p<0.01，***表示p<0.001。",
            font_size=12, alignment="justify"
        )

        corr_png = figure_paths.get("correlation_heatmap", {}).get("png", "")
        if corr_png:
            self._add_image_safe(doc, corr_png, width_inches=5.0)
            self._add_paragraph_cn(doc, "图3 多指标皮尔逊相关性热力图", font_size=10, bold=True, alignment="center")

        significant_corr = corr_report.get("significant_correlations", pd.DataFrame())
        if len(significant_corr) > 0:
            sig_display = significant_corr.copy()
            sig_display.columns = [
                "变量1", "变量2", "Pearson相关系数", "p值", "统计显著", "相关强度"
            ]
            self._add_dataframe_table(doc, sig_display, "表2 统计显著的指标间相关关系 (α=0.05)")

        self._add_heading_cn(doc, "六、主要结论", level=1)

        conclusions = self._generate_conclusions(timeseries_df, corr_report)
        for i, conclusion in enumerate(conclusions, 1):
            self._add_paragraph_cn(doc, f"({i}) {conclusion}", font_size=12, alignment="justify")

        self._add_heading_cn(doc, "附录：数据统计摘要", level=1)

        numeric_cols = timeseries_df.select_dtypes(include=[np.number]).columns
        summary_stats = timeseries_df[numeric_cols].describe().T
        summary_stats = summary_stats[["count", "mean", "std", "min", "25%", "50%", "75%", "max"]]
        summary_stats.index.name = "指标"
        summary_display = summary_stats.reset_index()
        col_name_map = {
            "index": "指标", "count": "样本数", "mean": "均值", "std": "标准差",
            "min": "最小值", "25%": "25%分位", "50%": "中位数", "75%": "75%分位", "max": "最大值"
        }
        summary_display = summary_display.rename(columns=col_name_map)
        self._add_dataframe_table(doc, summary_display, "表A1 各指标统计摘要")

        try:
            doc.save(output_path)
        except PermissionError:
            alt_path = output_path.replace(".docx", "_v2.docx")
            doc.save(alt_path)
            output_path = alt_path

        return output_path

    def _generate_conclusions(self, timeseries_df: pd.DataFrame, corr_report: Dict) -> List[str]:
        """根据数据分析结果生成自动结论"""
        conclusions = []

        if "humidity" in timeseries_df.columns:
            recent_humidity = timeseries_df["humidity"].tail(50).mean()
            early_humidity = timeseries_df["humidity"].head(50).mean()
            if recent_humidity > early_humidity:
                trend = "升高"
            else:
                trend = "降低"
            conclusions.append(
                f"湿度指数显示研究区晚全新世以来整体呈{trend}趋势，"
                f"从早全新世的{early_humidity:.2f}变化至近期的{recent_humidity:.2f}。"
            )

        if "temperature" in timeseries_df.columns:
            temp_std = timeseries_df["temperature"].std()
            temp_max = timeseries_df["temperature"].max()
            temp_min = timeseries_df["temperature"].min()
            conclusions.append(
                f"温度距平在过去一万年间波动幅度达{temp_max - temp_min:.2f}°C，"
                f"标准差为{temp_std:.2f}°C，表明区域气候经历了显著的冷暖交替。"
            )

        if "delta13C" in timeseries_df.columns:
            c13_mean = timeseries_df["delta13C"].mean()
            conclusions.append(
                f"有机碳δ¹³C平均值为{c13_mean:.2f}‰，反映了湿地生态系统碳同位素组成的典型特征。"
            )

        significant = corr_report.get("significant_correlations", pd.DataFrame())
        if len(significant) > 0:
            top = significant.iloc[0]
            direction = "正相关" if top["pearson_r"] > 0 else "负相关"
            conclusions.append(
                f"统计分析表明{top['variable_1']}与{top['variable_2']}呈显著{direction}关系"
                f"(r = {top['pearson_r']:.3f}, p = {top['p_value']:.2e})。"
            )

        if len(conclusions) == 0:
            conclusions.append("数据分析结果待进一步解读。")

        return conclusions
