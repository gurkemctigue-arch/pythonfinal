"""
阶段四：数据可视化 - Matplotlib 图表生成

本模块负责：
    - 营养成分雷达图：展示多维度营养分布
    - 热量对比图：柱状图/饼图对比不同食谱热量
    - 每周热量趋势图：展示一周摄入趋势
    - 输出 Base64 字符串供 Web 端展示

依赖: matplotlib (pip install matplotlib)
"""

import os
import base64
import io
from typing import List, Dict, Optional, Any
from pathlib import Path

# 尝试导入 matplotlib，失败时使用降级方案
try:
    import matplotlib
    matplotlib.use('Agg')  # 无头模式，不依赖图形界面
    import matplotlib.pyplot as plt
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    np = None
    plt = None


from models import Recipe, NutritionInfo, NutritionCalculator
from recommender import WeeklyPlan


# ============================================================================
# 全局绘图样式配置
# ============================================================================

# 中文字体支持
if MATPLOTLIB_AVAILABLE:
    try:
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
    except Exception:
        pass

# 颜色方案
COLORS = {
    'primary': '#4CAF50',
    'secondary': '#2196F3',
    'accent': '#FF9800',
    'danger': '#F44336',
    'protein': '#E91E63',
    'fat': '#FFC107',
    'carbs': '#9C27B0',
    'fiber': '#00BCD4',
    'calories': '#FF5722',
    'background': '#FAFAFA',
    'grid': '#E0E0E0',
    'text': '#333333',
}


# ============================================================================
# 辅助函数
# ============================================================================

def _create_figure(width: int = 10, height: int = 6, dpi: int = 100):
    """创建统一尺寸的图表"""
    if not MATPLOTLIB_AVAILABLE:
        return None
    return plt.figure(figsize=(width, height), dpi=dpi, facecolor=COLORS['background'])


def _to_base64(fig) -> str:
    """将图表转换为 Base64 编码字符串"""
    if not MATPLOTLIB_AVAILABLE or fig is None:
        return ""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor=fig.get_facecolor())
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close(fig)
    return f"data:image/png;base64,{img_base64}"


def _save_figure(fig, filepath: str) -> str:
    """保存图表到文件，返回 Flask 可访问的 URL 路径"""
    if not MATPLOTLIB_AVAILABLE or fig is None:
        return ""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filepath, format='png', bbox_inches='tight', dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    # 返回 Flask URL 路径（而非文件系统路径）
    filename = Path(filepath).name
    return f"/static/charts/{filename}"


def _check_matplotlib() -> bool:
    """检查 matplotlib 是否可用"""
    return MATPLOTLIB_AVAILABLE


# ============================================================================
# 图表1：营养成分雷达图
# ============================================================================

def plot_nutrition_radar(
    nutrition: NutritionInfo,
    title: str = "营养成分分布",
    save_path: Optional[str] = None,
    return_base64: bool = True
) -> str:
    """
    绘制营养成分雷达图

    Args:
        nutrition: 营养成分对象
        title: 图表标题
        save_path: 可选，保存路径
        return_base64: 是否返回 Base64 字符串

    Returns:
        Base64 编码的图片字符串
    """
    if not MATPLOTLIB_AVAILABLE:
        return _generate_placeholder_svg(title, "雷达图 (matplotlib未安装)")

    labels = ['蛋白质', '脂肪', '碳水', '纤维', '维生素C', '钙', '铁']
    values = [
        min(nutrition.protein * 2, 100),
        min(nutrition.fat * 2, 100),
        min(nutrition.carbs * 1.5, 100),
        min(nutrition.fiber * 5, 100),
        min(nutrition.vitamin_c * 2, 100),
        min(nutrition.calcium / 8, 100),
        min(nutrition.iron * 5, 100),
    ]

    N = len(labels)
    angles = [n / float(N) * 2 * np.pi for n in range(N)]
    angles += angles[:1]
    values_plot = values + values[:1]

    fig = _create_figure(width=8, height=7)
    ax = fig.add_subplot(111, polar=True)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_rlabel_position(0)

    ax.plot(angles, values_plot, color=COLORS['primary'], linewidth=2, linestyle='solid')
    ax.fill(angles, values_plot, color=COLORS['primary'], alpha=0.25)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=11, color=COLORS['text'])

    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=8, color=COLORS['grid'])

    ax.set_title(title, fontsize=14, fontweight='bold', pad=20, color=COLORS['text'])

    for i, (angle, val) in enumerate(zip(angles[:-1], values[:-1])):
        ax.annotate(f'{val:.0f}', xy=(angle, val), fontsize=8, ha='center', va='bottom',
                    color=COLORS['primary'])

    plt.tight_layout()

    if save_path:
        return _save_figure(fig, save_path)
    return _to_base64(fig)


def plot_multi_recipe_radar(
    recipes: List[Recipe],
    title: str = "多食谱营养对比",
    save_path: Optional[str] = None
) -> str:
    """
    绘制多个食谱的雷达图叠加对比

    Args:
        recipes: 食谱列表（最多5个）

    Returns:
        Base64 编码的图片字符串
    """
    if not MATPLOTLIB_AVAILABLE:
        return _generate_placeholder_svg(title, "多食谱雷达对比图")

    colors_list = [COLORS['primary'], COLORS['secondary'], COLORS['accent'],
                    COLORS['danger'], COLORS['protein']]

    labels = ['蛋白质', '脂肪', '碳水', '纤维', '维生素C']
    N = len(labels)

    fig = _create_figure(width=10, height=8)
    ax = fig.add_subplot(111, polar=True)

    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)

    for i, recipe in enumerate(recipes[:5]):
        nutrition = NutritionCalculator.calculate_from_recipe(recipe)
        values = [
            min(nutrition.protein * 2, 100),
            min(nutrition.fat * 2, 100),
            min(nutrition.carbs * 1.5, 100),
            min(nutrition.fiber * 5, 100),
            min(nutrition.vitamin_c * 2, 100),
        ]

        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        angles += angles[:1]
        values_plot = values + values[:1]

        ax.plot(angles, values_plot, color=colors_list[i], linewidth=2,
                linestyle='solid', label=recipe.name)
        ax.fill(angles, values_plot, color=colors_list[i], alpha=0.1)

    ax.set_xticks([n / float(N) * 2 * np.pi for n in range(N)])
    ax.set_xticklabels(labels, fontsize=11, color=COLORS['text'])
    ax.set_ylim(0, 100)
    ax.set_title(title, fontsize=14, fontweight='bold', pad=20, color=COLORS['text'])
    ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=9)

    plt.tight_layout()
    if save_path:
        return _save_figure(fig, save_path)
    return _to_base64(fig)


# ============================================================================
# 图表2：热量对比图
# ============================================================================

def plot_calorie_comparison(
    recipes: List[Recipe],
    title: str = "食谱热量对比",
    sort_by: str = 'calories',
    save_path: Optional[str] = None
) -> str:
    """
    绘制食谱热量对比柱状图（堆叠柱状图，展示三大营养素热量构成）
    """
    if not MATPLOTLIB_AVAILABLE:
        return _generate_placeholder_svg(title, "热量对比柱状图")

    data = []
    for r in recipes:
        nutrition = NutritionCalculator.calculate_from_recipe(r)
        data.append({
            'name': r.name,
            'calories': nutrition.calories,
            'protein': nutrition.protein,
            'fat': nutrition.fat,
            'carbs': nutrition.carbs,
        })

    if sort_by == 'calories':
        data.sort(key=lambda x: x['calories'], reverse=True)
    else:
        data.sort(key=lambda x: x['name'])

    names = [d['name'] for d in data]
    calories = [d['calories'] for d in data]
    protein = [d['protein'] * 4 for d in data]
    fat = [d['fat'] * 9 for d in data]
    carbs = [d['carbs'] * 4 for d in data]

    fig = _create_figure(width=10, height=6)
    ax = fig.add_subplot(111)

    x = np.arange(len(names))
    bar_width = 0.6

    ax.bar(x, protein, bar_width, color=COLORS['protein'], label='蛋白质')
    ax.bar(x, fat, bar_width, bottom=protein, color=COLORS['fat'], label='脂肪')
    ax.bar(x, carbs, bar_width,
           bottom=[p + f for p, f in zip(protein, fat)],
           color=COLORS['carbs'], label='碳水')

    for i, cal in enumerate(calories):
        ax.annotate(f'{cal:.0f}kcal', xy=(i, cal), ha='center', va='bottom',
                    fontsize=9, color=COLORS['text'], fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha='right', fontsize=10)
    ax.set_ylabel('热量 (kcal)', fontsize=11, color=COLORS['text'])
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15, color=COLORS['text'])
    ax.legend(loc='upper right', fontsize=9)
    ax.set_ylim(0, max(calories) * 1.3 if calories else 500)
    ax.yaxis.grid(True, color=COLORS['grid'], linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    if save_path:
        return _save_figure(fig, save_path)
    return _to_base64(fig)


def plot_calorie_pie(
    recipe: Recipe,
    title: Optional[str] = None
) -> str:
    """
    绘制单个食谱的宏量营养素热量占比饼图
    """
    if not MATPLOTLIB_AVAILABLE:
        return _generate_placeholder_svg(title or recipe.name, "宏量营养素饼图")

    nutrition = NutritionCalculator.calculate_from_recipe(recipe)
    macros = NutritionCalculator.analyze_macros(nutrition)

    protein_cal = nutrition.protein * 4
    fat_cal = nutrition.fat * 9
    carbs_cal = nutrition.carbs * 4

    if protein_cal + fat_cal + carbs_cal == 0:
        return ""

    fig = _create_figure(width=8, height=6)
    ax = fig.add_subplot(111)

    sizes = [protein_cal, fat_cal, carbs_cal]
    labels = [
        f"蛋白质\n{macros['protein_pct']}%\n({nutrition.protein:.0f}g)",
        f"脂肪\n{macros['fat_pct']}%\n({nutrition.fat:.0f}g)",
        f"碳水\n{macros['carbs_pct']}%\n({nutrition.carbs:.0f}g)"
    ]
    colors = [COLORS['protein'], COLORS['fat'], COLORS['carbs']]
    explode = (0.05, 0.02, 0.02)

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        autopct='', startangle=90,
        wedgeprops={'edgecolor': 'white', 'linewidth': 2}
    )

    for text in texts:
        text.set_fontsize(10)
        text.set_color(COLORS['text'])

    chart_title = title or recipe.name
    total_cal = protein_cal + fat_cal + carbs_cal
    ax.set_title(f'{chart_title}\n总热量: {total_cal:.0f} kcal',
                 fontsize=13, fontweight='bold', pad=20, color=COLORS['text'])

    plt.tight_layout()
    return _to_base64(fig)


# ============================================================================
# 图表3：每周热量趋势图
# ============================================================================

def plot_weekly_calorie_trend(
    weekly_plan: WeeklyPlan,
    title: str = "每周热量摄入趋势",
    save_path: Optional[str] = None
) -> str:
    """
    绘制每周热量趋势折线图（左：热量趋势 / 右：宏量营养素趋势）
    """
    if not MATPLOTLIB_AVAILABLE:
        return _generate_placeholder_svg(title, "每周热量趋势图")

    n = len(weekly_plan.days)
    day_labels = ['第' + str(i+1) + '天' for i in range(n)]
    calories = [day.total_calories for day in weekly_plan.days]
    protein = [day.nutrition.protein for day in weekly_plan.days]
    fat = [day.nutrition.fat for day in weekly_plan.days]
    carbs = [day.nutrition.carbs for day in weekly_plan.days]

    fig = _create_figure(width=12, height=6)

    # 子图1：总热量趋势
    ax1 = fig.add_subplot(121)
    x = np.arange(len(day_labels))

    ax1.plot(x, calories, color=COLORS['calories'], linewidth=2.5,
             marker='o', markersize=8, label='每日热量')
    ax1.fill_between(x, calories, alpha=0.2, color=COLORS['calories'])
    ax1.axhline(y=weekly_plan.avg_daily_calories, color=COLORS['secondary'],
                linestyle='--', linewidth=1.5,
                label=f'平均值: {weekly_plan.avg_daily_calories:.0f}kcal')

    ax1.set_xticks(x)
    ax1.set_xticklabels(day_labels, fontsize=10)
    ax1.set_ylabel('热量 (kcal)', fontsize=11, color=COLORS['text'])
    ax1.set_title('每日热量趋势', fontsize=12, fontweight='bold', color=COLORS['text'])
    ax1.legend(loc='upper right', fontsize=9)
    ax1.grid(True, color=COLORS['grid'], linestyle='--', alpha=0.5)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    for i, cal in enumerate(calories):
        ax1.annotate(f'{cal:.0f}', xy=(i, cal), textcoords="offset points",
                     xytext=(0, 8), ha='center', fontsize=9, color=COLORS['calories'])

    # 子图2：宏量营养素趋势
    ax2 = fig.add_subplot(122)
    ax2.plot(x, protein, color=COLORS['protein'], linewidth=2, marker='s',
             markersize=6, label=f'蛋白质 (平均{np.mean(protein):.0f}g)')
    ax2.plot(x, fat, color=COLORS['fat'], linewidth=2, marker='^',
             markersize=6, label=f'脂肪 (平均{np.mean(fat):.0f}g)')
    ax2.plot(x, carbs, color=COLORS['carbs'], linewidth=2, marker='D',
             markersize=6, label=f'碳水 (平均{np.mean(carbs):.0f}g)')

    ax2.set_xticks(x)
    ax2.set_xticklabels(day_labels, fontsize=10)
    ax2.set_ylabel('重量 (g)', fontsize=11, color=COLORS['text'])
    ax2.set_title('每日宏量营养素趋势', fontsize=12, fontweight='bold', color=COLORS['text'])
    ax2.legend(loc='upper right', fontsize=9)
    ax2.grid(True, color=COLORS['grid'], linestyle='--', alpha=0.5)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    fig.suptitle(title, fontsize=14, fontweight='bold', y=1.02, color=COLORS['text'])
    plt.tight_layout()
    if save_path:
        return _save_figure(fig, save_path)
    return _to_base64(fig)


def plot_macro_distribution(
    weekly_plan: WeeklyPlan,
    title: str = "每周宏量营养素分布",
    save_path: Optional[str] = None
) -> str:
    """
    绘制每周宏量营养素堆叠柱状图
    """
    if not MATPLOTLIB_AVAILABLE:
        return _generate_placeholder_svg(title, "宏量营养素分布图")

    n = len(weekly_plan.days)
    day_labels = ['第' + str(i+1) + '天' for i in range(n)]
    protein = [day.nutrition.protein for day in weekly_plan.days]
    fat = [day.nutrition.fat for day in weekly_plan.days]
    carbs = [day.nutrition.carbs for day in weekly_plan.days]

    fig = _create_figure(width=12, height=6)
    ax = fig.add_subplot(111)

    x = np.arange(len(day_labels))
    bar_width = 0.6

    ax.bar(x, protein, bar_width, color=COLORS['protein'], label='蛋白质')
    ax.bar(x, fat, bar_width, bottom=protein, color=COLORS['fat'], label='脂肪')
    ax.bar(x, carbs, bar_width,
           bottom=[p + f for p, f in zip(protein, fat)],
           color=COLORS['carbs'], label='碳水')

    for i, day in enumerate(weekly_plan.days):
        ax.annotate(f'{day.total_calories:.0f}kcal',
                     xy=(i, protein[i] + fat[i] + carbs[i]),
                     ha='center', va='bottom', fontsize=8, color=COLORS['text'])

    # 平均比例标注
    avg_p = np.mean(protein)
    avg_f = np.mean(fat)
    avg_c = np.mean(carbs)
    total = avg_p + avg_f + avg_c
    if total > 0:
        pct_text = (f"平均: P:{avg_p/total*100:.0f}% "
                    f"F:{avg_f/total*100:.0f}% "
                    f"C:{avg_c/total*100:.0f}%")
        ax.text(0.98, 0.98, pct_text, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax.set_xticks(x)
    ax.set_xticklabels(day_labels, fontsize=10)
    ax.set_ylabel('重量 (g)', fontsize=11, color=COLORS['text'])
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15, color=COLORS['text'])
    ax.legend(loc='upper right', fontsize=9)
    ax.yaxis.grid(True, color=COLORS['grid'], linestyle='--', alpha=0.5)
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    if save_path:
        return _save_figure(fig, save_path)
    return _to_base64(fig)


# ============================================================================
# 降级方案：SVG 占位图（matplotlib 不可用时）
# ============================================================================

def _generate_placeholder_svg(title: str, description: str) -> str:
    """
    当 matplotlib 不可用时，生成 SVG 格式的文本占位图
    """
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" style="background:#fafafa">
  <rect width="600" height="400" fill="#fafafa"/>
  <text x="300" y="120" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="18" font-weight="bold" fill="#4CAF50">{title}</text>
  <rect x="50" y="150" width="500" height="150" rx="10" ry="10"
        fill="white" stroke="#E0E0E0" stroke-width="2"/>
  <text x="300" y="215" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="14" fill="#666">{description}</text>
  <text x="300" y="245" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="12" fill="#999">提示: 运行 pip install matplotlib 以启用图表</text>
  <text x="300" y="340" text-anchor="middle" font-family="Arial,sans-serif"
        font-size="11" fill="#aaa">— 降级占位图 —</text>
</svg>"""
    b64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{b64}"


# ============================================================================
# 综合看板类
# ============================================================================

class NutritionDashboard:
    """
    营养看板：生成一组标准图表

    Usage:
        dashboard = NutritionDashboard(recipes, weekly_plan)
        charts = dashboard.generate_all()
        # 返回 {'radar': base64_str, 'bar': base64_str, 'trend': base64_str, ...}
    """

    def __init__(self, recipes: List[Recipe], weekly_plan: WeeklyPlan = None):
        self.recipes = recipes
        self.weekly_plan = weekly_plan
        self._static_dir = Path(__file__).parent / 'static' / 'charts'
        self._static_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(self, save_to_disk: bool = True) -> Dict[str, str]:
        """
        生成所有标准图表

        Returns:
            {图表名称: Base64字符串}
        """
        results = {}

        if not self.recipes:
            return results

        # 热量对比柱状图
        results['calorie_bar'] = plot_calorie_comparison(
            self.recipes,
            save_path=str(self._static_dir / 'calorie_bar.png') if save_to_disk else None
        )

        # 营养雷达图
        first_nutrition = NutritionCalculator.calculate_from_recipe(self.recipes[0])
        results['radar'] = plot_nutrition_radar(
            first_nutrition,
            title=f"「{self.recipes[0].name}」营养成分",
            save_path=str(self._static_dir / 'radar.png') if save_to_disk else None
        )

        # 多食谱雷达对比
        results['multi_radar'] = plot_multi_recipe_radar(
            self.recipes,
            title="食谱营养成分对比",
            save_path=str(self._static_dir / 'multi_radar.png') if save_to_disk else None
        )

        if self.weekly_plan:
            # 每周热量趋势
            results['weekly_trend'] = plot_weekly_calorie_trend(
                self.weekly_plan,
                title="每周热量摄入趋势",
                save_path=str(self._static_dir / 'weekly_trend.png') if save_to_disk else None
            )
            # 宏量营养素分布
            results['macro_dist'] = plot_macro_distribution(
                self.weekly_plan,
                title="每周宏量营养素分布",
                save_path=str(self._static_dir / 'macro_dist.png') if save_to_disk else None
            )

        return results

    def get_chart_files(self) -> Dict[str, str]:
        """返回静态图表文件路径（供 Flask 直接读取）"""
        files = {}
        for fname in ['calorie_bar.png', 'radar.png', 'multi_radar.png',
                      'weekly_trend.png', 'macro_dist.png']:
            fpath = self._static_dir / fname
            if fpath.exists():
                files[fname] = f'/static/charts/{fname}'
        return files


# ============================================================================
# 主程序入口（用于测试）
# ============================================================================

if __name__ == '__main__':
    from database import get_all_recipes, seed_sample_data, DB_PATH
    from recommender import MealPlanGenerator

    print("=" * 60)
    print("阶段四测试：数据可视化")
    print("=" * 60)

    print(f"\nmatplotlib 可用: {MATPLOTLIB_AVAILABLE}")

    # 加载数据
    print("\n[1] 加载食谱数据...")
    seed_sample_data(str(DB_PATH))
    recipes = get_all_recipes(str(DB_PATH))
    print(f"    共加载 {len(recipes)} 个食谱")

    # 生成每周计划
    print("\n[2] 生成每周膳食计划...")
    planner = MealPlanGenerator(recipes)
    weekly_plan = planner.generate_weekly_plan(days=7)
    print(f"    周计划: {weekly_plan.avg_daily_calories:.0f} kcal/天")

    # 生成看板
    print("\n[3] 生成营养看板...")
    dashboard = NutritionDashboard(recipes, weekly_plan)
    charts = dashboard.generate_all(save_to_disk=True)
    print(f"    共生成 {len(charts)} 个图表:")
    for name, data in charts.items():
        size_kb = len(data) * 3 // 4 // 1024 if data.startswith('data:') else 0
        print(f"    - {name}: {size_kb} KB" if size_kb else f"    - {name}: (文件)")

    # 查看静态文件
    print("\n[4] 图表文件列表:")
    static_dir = Path(__file__).parent / 'static' / 'charts'
    if static_dir.exists():
        for f in sorted(static_dir.glob('*.png')):
            print(f"    - {f.name}: {f.stat().st_size // 1024} KB")
    else:
        print("    (目录不存在)")

    print("\n" + "=" * 60)
    print("阶段四测试完成！")
    print("=" * 60)
