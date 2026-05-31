"""
阶段三：推荐算法与每周膳食计划

本模块负责：
    - 基础推荐：按偏好标签筛选食谱
    - 智能推荐（加分项1）：基于已有食材的最大化匹配度算法
    - 膳食计划（加分项2）：随机+约束校验生成7天早中晚计划
"""

import random
import copy
import difflib
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from models import (
    Recipe, Ingredient, NutritionInfo, NutritionCalculator
)


# ============================================================================
# 数据结构：推荐结果
# ============================================================================

@dataclass
class RecipeMatch:
    """食谱匹配结果"""
    recipe: Recipe
    match_score: float          # 匹配度 0-100
    matched_ingredients: List[str]   # 匹配的食材名称
    missing_ingredients: List[str]     # 缺失的食材名称
    nutrition: NutritionInfo     # 营养成分
    reason: str                # 推荐理由


@dataclass
class DailyPlan:
    """单日饮食计划"""
    breakfast: Optional[Recipe]
    lunch: Optional[Recipe]
    dinner: Optional[Recipe]
    total_calories: float
    macros: Dict[str, float]
    nutrition: NutritionInfo

    def to_dict(self) -> Dict[str, Any]:
        return {
            'breakfast': self.breakfast.name if self.breakfast else None,
            'lunch': self.lunch.name if self.lunch else None,
            'dinner': self.dinner.name if self.dinner else None,
            'total_calories': round(self.total_calories, 1),
            'macros': {k: round(v, 1) for k, v in self.macros.items()},
            'nutrition': {
                'protein': round(self.nutrition.protein, 1),
                'fat': round(self.nutrition.fat, 1),
                'carbs': round(self.nutrition.carbs, 1),
                'fiber': round(self.nutrition.fiber, 1),
            }
        }


@dataclass
class WeeklyPlan:
    """每周饮食计划"""
    days: List[DailyPlan]
    total_calories: float
    avg_daily_calories: float
    avg_macros: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            'days': [day.to_dict() for day in self.days],
            'total_calories': round(self.total_calories, 1),
            'avg_daily_calories': round(self.avg_daily_calories, 1),
            'avg_macros': {k: round(v, 1) for k, v in self.avg_macros.items()}
        }


# ============================================================================
# 基础推荐算法
# ============================================================================

class BasicRecommender:
    """基础推荐器：按偏好标签筛选食谱"""

    def __init__(self, recipes: List[Recipe]):
        self.recipes = recipes
        self._nutrition_cache: Dict[int, NutritionInfo] = {}

    def _nutrition(self, recipe: Recipe) -> NutritionInfo:
        """缓存食谱营养计算结果，避免组合筛选和排序重复计算。"""
        cache_key = id(recipe)
        if cache_key not in self._nutrition_cache:
            self._nutrition_cache[cache_key] = NutritionCalculator.calculate_from_recipe(recipe)
        return self._nutrition_cache[cache_key]

    def filter_by_tags(self, tags: List[str]) -> List[Recipe]:
        """
        按标签筛选食谱

        Args:
            tags: 目标标签列表，如 ['低脂', '高蛋白']

        Returns:
            匹配的食谱列表
        """
        if not tags:
            return self.recipes

        results = []
        for recipe in self.recipes:
            # 检查是否包含所有目标标签
            if all(tag in recipe.tags for tag in tags):
                results.append(recipe)
        return results

    def filter_by_calorie_range(
        self,
        min_cal: float = 0,
        max_cal: float = float('inf')
    ) -> List[Recipe]:
        """
        按热量范围筛选食谱

        Args:
            min_cal: 最低热量
            max_cal: 最高热量

        Returns:
            符合条件的食谱
        """
        results = []
        for recipe in self.recipes:
            total = self._nutrition(recipe)
            if min_cal <= total.calories <= max_cal:
                results.append(recipe)
        return results

    def filter_by_difficulty(self, difficulty: str) -> List[Recipe]:
        """按难度筛选食谱"""
        return [r for r in self.recipes if r.difficulty == difficulty]

    def filter_by_max_time(self, max_minutes: int) -> List[Recipe]:
        """按总耗时筛选食谱"""
        return [r for r in self.recipes if r.total_time <= max_minutes]

    def filter_by_cuisine(self, cuisine: str) -> List[Recipe]:
        """按菜系筛选食谱"""
        return [r for r in self.recipes if r.cuisine == cuisine]

    def combined_filter(
        self,
        tags: Optional[List[str]] = None,
        min_cal: float = 0,
        max_cal: float = float('inf'),
        difficulty: Optional[str] = None,
        max_time: Optional[int] = None,
        cuisine: Optional[str] = None,
    ) -> List[Recipe]:
        """
        组合筛选

        所有条件使用 AND 逻辑
        """
        results = self.recipes

        if tags:
            results = [r for r in results if all(t in r.tags for t in tags)]

        if max_time is not None:
            results = [r for r in results if r.total_time <= max_time]

        if difficulty:
            results = [r for r in results if r.difficulty == difficulty]

        if cuisine:
            results = [r for r in results if r.cuisine == cuisine]

        # 热量筛选放最后（需要计算）
        if min_cal > 0 or max_cal < float('inf'):
            filtered = []
            for r in results:
                total = self._nutrition(r)
                if min_cal <= total.calories <= max_cal:
                    filtered.append(r)
            results = filtered

        return results

    def rank_by_nutrition_score(
        self,
        recipes: List[Recipe],
        target_macros: Optional[Dict[str, float]] = None
    ) -> List[Tuple[Recipe, float]]:
        """
        按营养均衡度排序

        Args:
            recipes: 食谱列表
            target_macros: 目标宏量比例 {'protein': 30, 'fat': 30, 'carbs': 40}

        Returns:
            [(食谱, 营养评分), ...]，评分越高越好（0-100）
        """
        if target_macros is None:
            # 默认目标：蛋白质30%，脂肪30%，碳水40%
            target_macros = {'protein': 30, 'fat': 30, 'carbs': 40}

        scored = []
        for recipe in recipes:
            total = self._nutrition(recipe)
            macros = NutritionCalculator.analyze_macros(total)

            # 计算与目标的偏差
            protein_diff = abs(macros['protein_pct'] - target_macros['protein'])
            fat_diff = abs(macros['fat_pct'] - target_macros['fat'])
            carbs_diff = abs(macros['carbs_pct'] - target_macros['carbs'])

            # 总偏差越小越好，转换为0-100分数
            total_diff = protein_diff + fat_diff + carbs_diff
            score = max(0, 100 - total_diff)

            scored.append((recipe, score))

        return sorted(scored, key=lambda x: x[1], reverse=True)


# ============================================================================
# 智能推荐算法（加分项1）：基于食材库存的最大化匹配
# ============================================================================

class SmartRecommender:
    """
    智能推荐器：根据用户已有食材，推荐最匹配的食谱

    匹配策略：
        - 计算每个食谱与用户库存的食材匹配度
        - 按缺失食材数量最少排序（优先推荐可实现的菜谱）
        - 匹配度 = 匹配的食材数 / 食谱总食材数 * 100
    """

    def __init__(self, recipes: List[Recipe]):
        self.recipes = recipes
        self._nutrition_cache: Dict[int, NutritionInfo] = {}

    @staticmethod
    def _normalize_name(name: str) -> str:
        """标准化食材名称，提升包含空格/大小写时的匹配稳定性。"""
        return ''.join(str(name).lower().split())

    @staticmethod
    def _dedupe_names(names: List[str]) -> List[str]:
        """保持原顺序去重。"""
        seen = set()
        result = []
        for name in names:
            cleaned = str(name).strip()
            if not cleaned:
                continue
            key = SmartRecommender._normalize_name(cleaned)
            if key in seen:
                continue
            seen.add(key)
            result.append(cleaned)
        return result

    def _nutrition(self, recipe: Recipe) -> NutritionInfo:
        """缓存推荐过程中的营养计算结果。"""
        cache_key = id(recipe)
        if cache_key not in self._nutrition_cache:
            self._nutrition_cache[cache_key] = NutritionCalculator.calculate_from_recipe(recipe)
        return self._nutrition_cache[cache_key]

    def _has_ingredient(self, target_name: str, user_ingredients: List[str]) -> bool:
        """支持精确、包含和轻量相似度匹配。"""
        target = self._normalize_name(target_name)
        if not target:
            return False

        user_names = [self._normalize_name(name) for name in user_ingredients]
        if target in user_names:
            return True

        for user_name in user_names:
            if target in user_name or user_name in target:
                return True
            if difflib.SequenceMatcher(None, target, user_name).ratio() >= 0.72:
                return True

        return False

    def calculate_match_score(
        self,
        recipe: Recipe,
        user_ingredients: List[str]
    ) -> Tuple[float, List[str], List[str]]:
        """
        计算单个食谱的匹配度

        Returns:
            (匹配度分数0-100, 匹配的食材列表, 缺失的食材列表)
        """
        recipe_ing_names = recipe.get_ingredient_names()
        user_ingredients = self._dedupe_names(user_ingredients)

        matched = []
        missing = []

        for ing_name in recipe_ing_names:
            if self._has_ingredient(ing_name, user_ingredients):
                matched.append(ing_name)
            else:
                missing.append(ing_name)

        total = len(recipe_ing_names)
        if total == 0:
            return 0.0, [], []

        score = (len(matched) / total) * 100
        return score, matched, missing

    def recommend_by_inventory(
        self,
        user_ingredients: List[str],
        max_missing: int = 3,
        min_match_score: float = 30.0,
        exclude_missing: Optional[List[str]] = None
    ) -> List[RecipeMatch]:
        """
        基于库存食材推荐最匹配的食谱

        Args:
            user_ingredients: 用户已有的食材名称列表
            max_missing: 允许的最大缺失食材数（过滤掉缺失太多的食谱）
            min_match_score: 最低匹配度阈值
            exclude_missing: 需要排除的缺失食材（用户明确不想买的食材）

        Returns:
            RecipeMatch 列表，按匹配度从高到低排序
        """
        if exclude_missing is None:
            exclude_missing = []
        user_ingredients = self._dedupe_names(user_ingredients)
        exclude_keys = {
            self._normalize_name(name)
            for name in exclude_missing
            if str(name).strip()
        }

        results = []
        for recipe in self.recipes:
            score, matched, missing = self.calculate_match_score(recipe, user_ingredients)

            # 过滤：缺失过多
            if len(missing) > max_missing:
                continue

            # 过滤：匹配度过低
            if score < min_match_score:
                continue

            # 过滤：包含用户不想买的食材
            if any(self._normalize_name(ing) in exclude_keys for ing in missing):
                continue

            # 计算营养成分
            nutrition = self._nutrition(recipe)

            # 生成推荐理由
            if score >= 100:
                reason = "食材完全匹配，可以立即制作！"
            elif len(missing) == 1:
                reason = f"只需补充「{missing[0]}」即可制作"
            else:
                reason = f"缺少 {len(missing)} 种食材: {', '.join(missing[:2])}{'...' if len(missing) > 2 else ''}"

            match = RecipeMatch(
                recipe=recipe,
                match_score=score,
                matched_ingredients=matched,
                missing_ingredients=missing,
                nutrition=nutrition,
                reason=reason
            )
            results.append(match)

        # 优先缺失少，其次匹配高、耗时短，推荐结果更实用
        results.sort(key=lambda x: (
            len(x.missing_ingredients),
            -x.match_score,
            x.recipe.total_time,
            x.nutrition.calories,
        ))
        return results

    def find_complete_recipes(
        self,
        user_ingredients: List[str]
    ) -> List[Recipe]:
        """找出可以完全不依赖外部食材制作的食谱"""
        matches = self.recommend_by_inventory(
            user_ingredients,
            max_missing=0,
            min_match_score=100.0
        )
        return [m.recipe for m in matches]

    def suggest_shopping(
        self,
        user_ingredients: List[str],
        target_recipe: Recipe
    ) -> List[str]:
        """
        建议购买清单：列出制作目标食谱还需要购买的食材

        Args:
            user_ingredients: 用户已有食材
            target_recipe: 目标食谱

        Returns:
            还需要购买的食材名称列表
        """
        _, _, missing = self.calculate_match_score(target_recipe, user_ingredients)
        return missing


# ============================================================================
# 膳食计划生成器（加分项2）
# ============================================================================

class MealPlanGenerator:
    """
    每周膳食计划生成器

    使用随机+约束校验策略：
        - 每天早中晚三餐分配不同的热量比例（20%/40%/40%）
        - 每天总热量约束：1800-2400 kcal
        - 每周营养均衡：宏量营养素比例控制在合理范围
    """

    # 每日热量目标范围（kcal）
    DAILY_CAL_MIN = 1800
    DAILY_CAL_MAX = 2400

    # 每日三餐热量分配比例
    MEAL_RATIO = {'breakfast': 0.20, 'lunch': 0.40, 'dinner': 0.40}

    # 推荐宏量营养素比例范围（%）
    MACRO_RANGES = {
        'protein': (15, 30),   # 蛋白质 15-30%
        'fat': (20, 35),      # 脂肪 20-35%
        'carbs': (35, 55),    # 碳水 35-55%
    }

    def __init__(self, recipes: List[Recipe]):
        self.recipes = recipes
        self._nutrition_cache: Dict[int, NutritionInfo] = {}
        self._categorize_recipes()

    def _nutrition(self, recipe: Recipe) -> NutritionInfo:
        """缓存膳食计划中的营养计算结果。"""
        cache_key = id(recipe)
        if cache_key not in self._nutrition_cache:
            self._nutrition_cache[cache_key] = NutritionCalculator.calculate_from_recipe(recipe)
        return self._nutrition_cache[cache_key]

    def _categorize_recipes(self):
        """将食谱按热量分为轻食/正餐两类"""
        self.light_recipes = []   # 轻食（早餐/沙拉类）
        self.main_recipes = []    # 主餐（午/晚餐）

        for r in self.recipes:
            total = self._nutrition(r)
            if total.calories < 300 or '沙拉' in r.name or '水果' in r.tags:
                self.light_recipes.append(r)
            else:
                self.main_recipes.append(r)

        # 确保非空
        if not self.light_recipes:
            self.light_recipes = self.recipes[:]
        if not self.main_recipes:
            self.main_recipes = self.recipes[:]

    def _select_recipe_for_slot(
        self,
        target_calories: float,
        tolerance: float = 0.3,
        prefer_light: bool = False,
        used_names: Optional[set] = None
    ) -> Optional[Recipe]:
        """
        为特定餐次槽选择合适的食谱

        Args:
            target_calories: 目标热量
            tolerance: 容许偏差（0.3表示±30%）
            prefer_light: 是否优先选择轻食

        Returns:
            选中的食谱，未找到则返回 None
        """
        candidates = self.light_recipes if prefer_light else self.main_recipes
        pool = candidates if candidates else self.recipes
        used_names = used_names or set()

        min_cal = target_calories * (1 - tolerance)
        max_cal = target_calories * (1 + tolerance)

        # 筛选符合热量范围的食谱
        valid = []
        for r in pool:
            if r.name in used_names:
                continue
            total = self._nutrition(r)
            if min_cal <= total.calories <= max_cal:
                valid.append(r)

        if not valid:
            # 放宽范围重新搜索
            for r in pool:
                if r.name in used_names:
                    continue
                total = self._nutrition(r)
                if total.calories > 0:
                    valid.append(r)

        if not valid and used_names:
            return self._select_recipe_for_slot(
                target_calories,
                tolerance=tolerance,
                prefer_light=prefer_light,
                used_names=set()
            )

        if not valid:
            return None

        valid.sort(key=lambda r: abs(self._nutrition(r).calories - target_calories))
        best_pool = valid[:min(5, len(valid))]
        return random.choice(best_pool)

    def _calculate_daily_nutrition(
        self,
        breakfast: Optional[Recipe],
        lunch: Optional[Recipe],
        dinner: Optional[Recipe]
    ) -> Tuple[float, Dict[str, float], NutritionInfo]:
        """计算单日营养总和"""
        total = NutritionInfo()
        recipes = [r for r in [breakfast, lunch, dinner] if r]

        for r in recipes:
            total = total + self._nutrition(r)

        calories = total.calories
        macros = NutritionCalculator.analyze_macros(total)

        return calories, macros, total

    def _validate_daily_plan(
        self,
        calories: float,
        macros: Dict[str, float]
    ) -> Tuple[bool, List[str]]:
        """验证单日计划是否满足约束"""
        warnings = []

        # 热量检查
        if calories < self.DAILY_CAL_MIN:
            warnings.append(f"热量过低: {calories:.0f} kcal (建议≥{self.DAILY_CAL_MIN})")
        elif calories > self.DAILY_CAL_MAX:
            warnings.append(f"热量过高: {calories:.0f} kcal (建议≤{self.DAILY_CAL_MAX})")

        # 宏量营养素检查
        for macro, (min_pct, max_pct) in self.MACRO_RANGES.items():
            actual = macros.get(f'{macro}_pct', 0)
            if actual < min_pct:
                warnings.append(f"{macro}偏低: {actual:.1f}% (建议≥{min_pct}%)")
            elif actual > max_pct:
                warnings.append(f"{macro}偏高: {actual:.1f}% (建议≤{max_pct}%)")

        return (len(warnings) == 0, warnings)

    def generate_daily_plan(
        self,
        target_calories: Optional[float] = None
    ) -> DailyPlan:
        """
        生成单日饮食计划

        Args:
            target_calories: 目标每日热量（None则随机在范围内）

        Returns:
            DailyPlan 对象
        """
        if target_calories is None:
            target_calories = random.uniform(self.DAILY_CAL_MIN, self.DAILY_CAL_MAX)

        # 为三餐分配热量目标
        breakfast_target = target_calories * self.MEAL_RATIO['breakfast']
        lunch_target = target_calories * self.MEAL_RATIO['lunch']
        dinner_target = target_calories * self.MEAL_RATIO['dinner']

        used_names = set()
        breakfast = self._select_recipe_for_slot(
            breakfast_target,
            prefer_light=True,
            used_names=used_names
        )
        if breakfast:
            used_names.add(breakfast.name)

        lunch = self._select_recipe_for_slot(lunch_target, used_names=used_names)
        if lunch:
            used_names.add(lunch.name)

        dinner = self._select_recipe_for_slot(dinner_target, used_names=used_names)

        # 计算营养
        calories, macros, nutrition = self._calculate_daily_nutrition(
            breakfast, lunch, dinner
        )

        return DailyPlan(
            breakfast=breakfast,
            lunch=lunch,
            dinner=dinner,
            total_calories=calories,
            macros=macros,
            nutrition=nutrition
        )

    def generate_weekly_plan(
        self,
        days: int = 7,
        target_calories: Optional[float] = None
    ) -> WeeklyPlan:
        """
        生成每周饮食计划

        Args:
            days: 天数（默认7天）
            target_calories: 每日目标热量（None则每天在范围内随机）

        Returns:
            WeeklyPlan 对象
        """
        daily_plans = []
        days = max(1, min(int(days), 14))
        weekly_calories = 0
        weekly_protein = 0
        weekly_fat = 0
        weekly_carbs = 0

        for _ in range(days):
            day_plan = self.generate_daily_plan(target_calories)
            daily_plans.append(day_plan)

            weekly_calories += day_plan.total_calories
            weekly_protein += day_plan.nutrition.protein
            weekly_fat += day_plan.nutrition.fat
            weekly_carbs += day_plan.nutrition.carbs

        avg_calories = weekly_calories / days if days > 0 else 0

        # 计算每周平均宏量比例
        total_macro_cal = (weekly_protein * 4 + weekly_fat * 9 + weekly_carbs * 4)
        if total_macro_cal > 0:
            avg_macros = {
                'protein_pct': round(weekly_protein * 4 / total_macro_cal * 100, 1),
                'fat_pct': round(weekly_fat * 9 / total_macro_cal * 100, 1),
                'carbs_pct': round(weekly_carbs * 4 / total_macro_cal * 100, 1),
            }
        else:
            avg_macros = {'protein_pct': 0, 'fat_pct': 0, 'carbs_pct': 0}

        return WeeklyPlan(
            days=daily_plans,
            total_calories=weekly_calories,
            avg_daily_calories=avg_calories,
            avg_macros=avg_macros
        )

    def print_weekly_plan(self, plan: WeeklyPlan) -> str:
        """格式化打印每周计划"""
        lines = []
        lines.append("=" * 60)
        lines.append("每周膳食计划")
        lines.append("=" * 60)
        lines.append(f"总热量: {plan.total_calories:.0f} kcal")
        lines.append(f"日均热量: {plan.avg_daily_calories:.0f} kcal")
        lines.append(f"平均宏量: 蛋白质{plan.avg_macros['protein_pct']}% | 脂肪{plan.avg_macros['fat_pct']}% | 碳水{plan.avg_macros['carbs_pct']}%")
        lines.append("-" * 60)

        meal_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        for i, day in enumerate(plan.days):
            day_label = meal_names[i] if i < len(meal_names) else f"第{i+1}天"
            lines.append(f"\n{day_label}:")
            lines.append(f"  早餐: {day.breakfast.name if day.breakfast else '无'} ({NutritionCalculator.calculate_from_recipe(day.breakfast).calories:.0f}kcal)" if day.breakfast else "  早餐: 无")
            lines.append(f"  午餐: {day.lunch.name if day.lunch else '无'} ({NutritionCalculator.calculate_from_recipe(day.lunch).calories:.0f}kcal)" if day.lunch else "  午餐: 无")
            lines.append(f"  晚餐: {day.dinner.name if day.dinner else '无'} ({NutritionCalculator.calculate_from_recipe(day.dinner).calories:.0f}kcal)" if day.dinner else "  晚餐: 无")
            lines.append(f"  合计: {day.total_calories:.0f} kcal | P:{day.macros.get('protein_pct', 0):.0f}% F:{day.macros.get('fat_pct', 0):.0f}% C:{day.macros.get('carbs_pct', 0):.0f}%")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


# ============================================================================
# 主程序入口（用于测试）
# ============================================================================

if __name__ == '__main__':
    from models import create_sample_ingredients, create_sample_recipes
    from database import get_all_recipes, seed_sample_data, DB_PATH

    print("=" * 60)
    print("阶段三测试：推荐算法与膳食计划")
    print("=" * 60)

    # 加载数据
    print("\n[1] 加载数据...")
    seed_sample_data(str(DB_PATH))
    recipes = get_all_recipes(str(DB_PATH))
    print(f"    共加载 {len(recipes)} 个食谱")

    # 测试基础推荐
    print("\n[2] 测试基础推荐...")
    basic_rec = BasicRecommender(recipes)

    low_fat = basic_rec.filter_by_tags(['低脂'])
    print(f"    '低脂'标签筛选: {len(low_fat)} 个")

    quick = basic_rec.filter_by_max_time(20)
    print(f"    20分钟内可完成: {len(quick)} 个")

    high_protein = basic_rec.filter_by_tags(['高蛋白'])
    print(f"    '高蛋白'标签筛选: {len(high_protein)} 个")

    # 测试智能推荐
    print("\n[3] 测试智能推荐（基于库存）...")
    user_ingredients = ['西红柿', '鸡蛋', '食用油', '盐']
    smart_rec = SmartRecommender(recipes)

    matches = smart_rec.recommend_by_inventory(user_ingredients, max_missing=2)
    print(f"    用户库存: {', '.join(user_ingredients)}")
    print(f"    找到 {len(matches)} 个匹配食谱:")
    for m in matches[:5]:
        print(f"    - {m.recipe.name}: 匹配度{m.match_score:.0f}% | {m.reason}")

    # 测试完全匹配的食谱
    complete = smart_rec.find_complete_recipes(user_ingredients)
    print(f"\n    可立即制作的食谱: {len(complete)} 个")
    for r in complete:
        print(f"    - {r.name}")

    # 测试购物建议
    print("\n[4] 测试购物建议...")
    if recipes:
        target = recipes[0]
        shopping = smart_rec.suggest_shopping(user_ingredients, target)
        print(f"    制作'{target.name}'还需购买: {shopping if shopping else '无需购买'}")

    # 测试每周膳食计划
    print("\n[5] 测试每周膳食计划...")
    planner = MealPlanGenerator(recipes)
    weekly = planner.generate_weekly_plan(days=7)
    print(planner.print_weekly_plan(weekly))

    # 测试组合筛选+排序
    print("\n[6] 测试组合筛选+营养排序...")
    filtered = basic_rec.combined_filter(
        tags=['简单'],
        max_time=30
    )
    ranked = basic_rec.rank_by_nutrition_score(filtered)
    print(f"    '简单'且30分钟内，共{len(ranked)}个，按营养均衡排序:")
    for r, score in ranked[:3]:
        total = NutritionCalculator.calculate_from_recipe(r)
        print(f"    - {r.name}: 评分{score:.1f} | {total.calories:.0f}kcal")

    print("\n" + "=" * 60)
    print("阶段三测试完成！")
    print("=" * 60)
