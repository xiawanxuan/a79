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
新增：多钻孔跨区域对比分析模式
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
from src.cross_region_comparison import CrossRegionComparator


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


def run_cross_region_comparison(group_id: Optional[str] = None,
                               generate_sample: bool = True,
                               generate_report: bool = True,
                               verbose: bool = True) -> dict:
    """
    执行多钻孔跨区域对比分析流程

    Args:
        group_id: 对比组ID，None使用默认对比组
        generate_sample: 是否生成示例数据
        generate_report: 是否生成Word报告
        verbose: 是否打印进度信息

    Returns:
        包含所有对比分析结果的字典
    """
    results = {}
    t0 = datetime.datetime.now()

    def log(msg: str):
        if verbose:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] {msg}")

    log("=" * 70)
    log("跨区域湿地泥炭钻孔古环境对比分析")
    log("=" * 70)

    log("[1/7] 初始化配置管理器...")
    config = ConfigManager()
    results["config"] = config

    available_groups = config.list_comparison_groups()
    log(f"    可用对比组: {available_groups}")

    if group_id is None:
        group_id = config.paths.get("default_comparison_group", "china_wetland_network")
    group_config = config.get_comparison_group(group_id)
    log(f"    当前对比组: {group_config.get('name', group_id)}")
    log(f"    包含钻孔: {group_config['cores']}")
    log(f"    对比组描述: {group_config.get('description', '')}")

    log("[2/7] 批量处理对比组钻孔数据...")
    comparator = CrossRegionComparator(config)
    comparator.process_comparison_group(group_id, generate_sample=generate_sample, verbose=verbose)

    if len(comparator.core_timeseries) == 0:
        raise RuntimeError("没有成功处理任何钻孔数据，请检查数据源")

    log(f"    成功处理钻孔数: {len(comparator.core_timeseries)}")

    log("[3/7] 对齐多钻孔时序到统一时间网格...")
    aligned_df = comparator.align_timeseries_to_common_grid()
    log(f"    对齐后数据: {len(aligned_df)} 行")
    log(f"    时间范围: {aligned_df['age_yrBP'].min():.0f} - {aligned_df['age_yrBP'].max():.0f} yr BP")
    log(f"    对齐指标: {[c for c in aligned_df.columns if c not in ['core_id', 'region', 'location', 'latitude', 'longitude', 'elevation_m', 'age_yrBP']]}")
    results["aligned_data"] = aligned_df

    log("[4/7] 计算各时段钻孔对比统计...")
    period_stats = comparator.compute_period_stats(aligned_df)
    log(f"    时段统计记录数: {len(period_stats)}")
    log(f"    统计时段: {period_stats['period_label'].unique().tolist()}")
    results["period_statistics"] = period_stats

    log("[5/7] 计算钻孔间古环境差异矩阵...")
    diff_humidity = comparator.compute_difference_matrix(period_stats, "humidity", "mean")
    diff_temperature = comparator.compute_difference_matrix(period_stats, "temperature", "mean")
    diff_combined = comparator.compute_combined_difference(period_stats)
    log(f"    湿度差异矩阵维度: {diff_humidity.shape}")
    log(f"    温度差异矩阵维度: {diff_temperature.shape}")
    log(f"    综合差异矩阵维度: {diff_combined.shape}")
    results["difference_matrices"] = {
        "humidity_mean": diff_humidity,
        "temperature_mean": diff_temperature,
        "combined": diff_combined
    }

    log("[6/7] 生成跨区域对比可视化...")
    visualizer = PeatVisualizer(config)
    core_meta = config.get_all_core_metadata()

    comp_results_package = {
        "aligned_data": aligned_df,
        "period_statistics": period_stats,
        "difference_matrices": results["difference_matrices"],
        "core_metadata": core_meta
    }

    try:
        spatial_corr = comparator.compute_spatial_correlation(aligned_df, "humidity")
        comp_results_package["spatial_correlation"] = spatial_corr
        log(f"    空间相关性分析完成，{len(spatial_corr)} 条记录")
    except Exception:
        spatial_corr = None

    try:
        clusters = comparator.cluster_cores(diff_combined, n_clusters=3)
        results["clusters"] = clusters
        log(f"    区域聚类完成: {clusters[['core_id', 'cluster', 'region']].to_string(index=False)}")
    except Exception:
        pass

    cross_figure_paths = visualizer.generate_cross_region_figures(
        comp_results_package, group_prefix=group_id
    )
    for fig_name, paths in cross_figure_paths.items():
        for fmt, fpath in paths.items():
            log(f"    - {fig_name} ({fmt}): {os.path.basename(fpath)}")
    results["cross_figure_paths"] = cross_figure_paths

    if generate_report:
        log("[7/7] 生成跨区域对比Word报告...")
        reporter = ReportGenerator(config)
        try:
            report_path = reporter.generate_cross_region_report(
                comparison_results={
                    "core_timeseries": comparator.core_timeseries,
                    "core_chronology": comparator._core_chronology,
                    "aligned_data": aligned_df,
                    "period_statistics": period_stats,
                    "difference_matrices": results["difference_matrices"],
                    "clusters": results.get("clusters"),
                    "spatial_correlation": spatial_corr,
                    "core_metadata": core_meta,
                    "comparison_group": group_config
                },
                figure_paths=cross_figure_paths,
                group_id=group_id
            )
            log(f"    跨区域对比报告已保存: {report_path}")
            results["cross_report_path"] = report_path
        except ImportError as e:
            log(f"    警告: {e}")
            results["cross_report_path"] = None
    else:
        log("[7/7] 跳过Word报告生成...")

    elapsed = (datetime.datetime.now() - t0).total_seconds()
    log("=" * 70)
    log(f"跨区域对比分析完成！总耗时: {elapsed:.1f} 秒")
    log("=" * 70)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="湿地古气候泥炭沉积多指标数据分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                              # 使用默认钻孔运行单钻孔流程
  python main.py --core core_ZK02             # 指定钻孔ZK02运行单钻孔分析
  python main.py --cross-region               # 使用默认对比组执行跨区域对比
  python main.py --cross-region --group central_china  # 指定对比组
  python main.py --no-sample                  # 使用已有数据，不生成示例
  python main.py --no-report                  # 不生成Word报告
  python main.py --list-groups                # 列出所有可用对比组
        """
    )
    parser.add_argument("--core", type=str, default="core_ZK01",
                        help="单钻孔模式的数据源ID (默认: core_ZK01)")
    parser.add_argument("--cross-region", action="store_true",
                        help="启用多钻孔跨区域对比分析模式")
    parser.add_argument("--group", type=str, default=None,
                        help="跨区域模式下指定对比组ID")
    parser.add_argument("--list-groups", action="store_true",
                        help="列出所有可用的对比组配置")
    parser.add_argument("--no-sample", action="store_true",
                        help="不生成示例数据，使用 data/raw 目录下的已有数据")
    parser.add_argument("--no-report", action="store_true",
                        help="不生成Word科研报告")
    parser.add_argument("--quiet", action="store_true",
                        help="静默模式，减少输出信息")

    args = parser.parse_args()

    if args.list_groups:
        config = ConfigManager()
        print("可用对比组列表:")
        for gid in config.list_comparison_groups():
            g = config.get_comparison_group(gid)
            print(f"  {gid}:")
            print(f"    名称: {g.get('name', '')}")
            print(f"    描述: {g.get('description', '')}")
            print(f"    包含钻孔: {g.get('cores', [])}")
            print()
        return

    if args.cross_region:
        run_cross_region_comparison(
            group_id=args.group,
            generate_sample=not args.no_sample,
            generate_report=not args.no_report,
            verbose=not args.quiet
        )
    else:
        run_full_pipeline(
            core_id=args.core,
            generate_sample=not args.no_sample,
            generate_report=not args.no_report,
            verbose=not args.quiet
        )


if __name__ == "__main__":
    main()
