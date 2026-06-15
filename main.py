"""
湿地古气候泥炭数据分析 - 主入口脚本
======================================

一键执行完整分析流程：
1. 生成/加载示例数据
2. 原始数据清洗
3. 年代深度插值校准
4. 多指标皮尔逊相关性分析
5. 多层联动时序可视化
6. 标准化Word科研报告生成
"""

import os
import sys
import argparse
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config_manager import ConfigManager
from src.data_cleaner import PeatDataCleaner
from src.chronology_interpolator import ChronologyInterpolator
from src.correlation_analyzer import CorrelationAnalyzer
from src.visualizer import PeatVisualizer
from src.report_generator import ReportGenerator
from src.sample_data_generator import generate_all_sample_data


def run_full_pipeline(core_id: str = "core_ZK01",
                     generate_sample: bool = True,
                     generate_report: bool = True,
                     verbose: bool = True) -> dict:
    """
    执行完整的泥炭沉积数据分析流程

    Args:
        core_id: 钻孔数据源ID
        generate_sample: 是否生成示例数据
        generate_report: 是否生成Word报告
        verbose: 是否打印进度信息

    Returns:
        包含所有中间结果和输出路径的字典
    """
    results = {}
    t0 = datetime.datetime.now()

    def log(msg: str):
        if verbose:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {msg}")

    log("=" * 60)
    log("湿地泥炭沉积多指标古气候分析")
    log("=" * 60)

    log("[1/6] 初始化配置管理器...")
    config = ConfigManager()
    results["config"] = config
    available_cores = config.list_data_sources()
    log(f"    可用钻孔数据源: {available_cores}")
    log(f"    当前分析钻孔: {core_id}")

    if generate_sample:
        log("[2/6] 生成示例模拟数据...")
        sample_files = generate_all_sample_data(config, core_id)
        for name, path in sample_files.items():
            log(f"    - {name}: {path}")
        results["sample_files"] = sample_files
    else:
        log("[2/6] 跳过示例数据生成，使用已有数据...")

    log("[3/6] 执行数据清洗...")
    cleaner = PeatDataCleaner(config)
    cleaned_df = cleaner.clean_and_merge_all(core_id=core_id, save_processed=True)
    cleaning_report = cleaner.get_cleaning_report()
    log(f"    清洗合并后数据: {len(cleaned_df)} 行, {len(cleaned_df.columns)} 列")
    log(f"    清洗报告:\n{cleaning_report.to_string(index=False)}")
    results["cleaned_data"] = cleaned_df
    results["cleaning_report"] = cleaning_report

    log("[4/6] 年代深度插值校准...")
    interpolator = ChronologyInterpolator(config)
    chronology_df = interpolator.load_chronology(core_id=core_id)
    log(f"    测年控制点: {len(chronology_df)} 个")
    log(f"    年代范围: {chronology_df['age_yrBP'].min():.0f} - {chronology_df['age_yrBP'].max():.0f} yr BP")

    timeseries_df = interpolator.interpolate_core_data(cleaned_df, core_id=core_id, save_processed=True)
    log(f"    标准化时序数据: {len(timeseries_df)} 行, 时间分辨率 10 年")
    log(f"    包含指标: {[c for c in timeseries_df.columns if c not in ['age_yrBP', 'depth_cm']]}")
    results["chronology_data"] = chronology_df
    results["timeseries_data"] = timeseries_df

    log("[5/6] 多指标相关性分析与可视化...")
    analyzer = CorrelationAnalyzer(config)
    analysis_cols = [c for c in ["delta13C", "humidity", "temperature", "plant_index", "metal_pollution"]
                     if c in timeseries_df.columns]
    corr_report = analyzer.generate_correlation_report(timeseries_df, analysis_cols)
    log(f"    检测到 {len(corr_report['significant_correlations'])} 对统计显著相关关系")
    results["correlation_report"] = corr_report

    visualizer = PeatVisualizer(config)
    figure_paths = visualizer.generate_all_figures(timeseries_df, chronology_df, corr_report, core_id)
    for fig_name, paths in figure_paths.items():
        for fmt, fpath in paths.items():
            log(f"    - {fig_name} ({fmt}): {os.path.basename(fpath)}")
    results["figure_paths"] = figure_paths

    if generate_report:
        log("[6/6] 生成标准化科研报告...")
        reporter = ReportGenerator(config)
        try:
            report_path = reporter.generate_research_report(
                timeseries_df=timeseries_df,
                corr_report=corr_report,
                cleaning_report=cleaning_report,
                figure_paths=figure_paths,
                chronology_df=chronology_df,
                core_id=core_id
            )
            log(f"    Word报告已保存: {report_path}")
            results["report_path"] = report_path
        except ImportError as e:
            log(f"    警告: {e}")
            log("    请安装 python-docx 后重新运行以生成Word报告: pip install python-docx")
            results["report_path"] = None
    else:
        log("[6/6] 跳过Word报告生成...")

    elapsed = (datetime.datetime.now() - t0).total_seconds()
    log("=" * 60)
    log(f"分析完成！总耗时: {elapsed:.1f} 秒")
    log("=" * 60)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="湿地古气候泥炭沉积多指标数据分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                              # 使用默认钻孔运行完整流程
  python main.py --core core_ZK02             # 指定钻孔ZK02
  python main.py --no-sample                  # 使用已有数据，不生成示例
  python main.py --no-report                  # 不生成Word报告
        """
    )
    parser.add_argument("--core", type=str, default="core_ZK01",
                        help="钻孔数据源ID (默认: core_ZK01)")
    parser.add_argument("--no-sample", action="store_true",
                        help="不生成示例数据，使用 data/raw 目录下的已有数据")
    parser.add_argument("--no-report", action="store_true",
                        help="不生成Word科研报告")
    parser.add_argument("--quiet", action="store_true",
                        help="静默模式，减少输出信息")

    args = parser.parse_args()

    run_full_pipeline(
        core_id=args.core,
        generate_sample=not args.no_sample,
        generate_report=not args.no_report,
        verbose=not args.quiet
    )


if __name__ == "__main__":
    main()
