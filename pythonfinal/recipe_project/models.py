"""
阶段一：基础模型与数据管理 (OOP & 数据结构)

本模块定义三个核心类：
    - Ingredient: 食材及其营养成分
    - Recipe: 食谱及其食材组成
    - NutritionCalculator: 营养成分计算器
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
import json


# ============================================================================
# 数据类定义：存储营养成分信息
# ============================================================================

@dataclass
class NutritionInfo:
    """营养成分数据类，所有数值单位为每100g对应成分含量"""
    calories: float = 0.0       # 热量 (kcal)
    protein: float = 0.0       # 蛋白质 (g)
    fat: float = 0.0           # 脂肪 (g)
    carbs: float = 0.0         # 碳水化合物 (g)
    fiber: float = 0.0         # 膳食纤维 (g)
    vitamin_a: float = 0.0     # 维生素A (μg)
    vitamin_c: float = 0.0     # 维生素C (mg)
    calcium: float = 0.0       # 钙 (mg)
    iron: float = 0.0          # 铁 (mg)

    def __add__(self, other: 'NutritionInfo') -> 'NutritionInfo':
        """支持营养成分累加"""
        return NutritionInfo(
            calories=self.calories + other.calories,
            protein=self.protein + other.protein,
            fat=self.fat + other.fat,
            carbs=self.carbs + other.carbs,
            fiber=self.fiber + other.fiber,
            vitamin_a=self.vitamin_a + other.vitamin_a,
            vitamin_c=self.vitamin_c + other.vitamin_c,
            calcium=self.calcium + other.calcium,
            iron=self.iron + other.iron
        )

    def scale(self, factor: float) -> 'NutritionInfo':
        """按因子缩放营养成分（如按食材实际重量）"""
        return NutritionInfo(
            calories=self.calories * factor,
            protein=self.protein * factor,
            fat=self.fat * factor,
            carbs=self.carbs * factor,
            fiber=self.fiber * factor,
            vitamin_a=self.vitamin_a * factor,
            vitamin_c=self.vitamin_c * factor,
            calcium=self.calcium * factor,
            iron=self.iron * factor
        )

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'NutritionInfo':
        """从字典创建实例"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ============================================================================
# 核心类：食材 (Ingredient)
# ============================================================================

class Ingredient:
    """
    食材类

    Attributes:
        name: 食材名称
        nutrition_per_100g: 每100g对应的营养成分
        default_unit: 默认单位（克为单位）
    """

    # 常用单位到克的转换系数
    UNIT_TO_GRAMS: Dict[str, float] = {
        'g': 1.0,
        'kg': 1000.0,
        '斤': 500.0,
        '两': 50.0,
        'ml': 1.0,       # 近似，水和液体可通用
        'L': 1000.0,
        '个': 50.0,      # 通用默认值（可根据具体食材覆盖）
        '勺': 15.0,      # 通用默认值
        '杯': 250.0,     # 通用默认值
    }

    def __init__(
        self,
        name: str,
        nutrition: NutritionInfo,
        unit_per_100g: float = 100.0,
        category: str = '其他'
    ):
        self.name = name
        self.nutrition_per_100g = nutrition
        self.unit_per_100g = unit_per_100g   # 100g对应的单位数量（如鸡蛋约2个）
        self.category = category            # 食材分类：蔬菜/肉类/谷物等

    def get_nutrition(self, amount: float, unit: str = 'g') -> NutritionInfo:
        """
        计算指定数量食材的营养成分

        Args:
            amount: 数量
            unit: 单位 (g/kg/个/ml等)

        Returns:
            NutritionInfo 实例
        """
        # 转换为克
        if unit in self.UNIT_TO_GRAMS:
            grams = amount * self.UNIT_TO_GRAMS[unit]
        else:
            # 未知单位，假设为克
            grams = amount

        # 计算缩放因子（实际克数 / 100g）
        factor = grams / 100.0
        return self.nutrition_per_100g.scale(factor)

    def __repr__(self) -> str:
        return f"Ingredient(name='{self.name}', category='{self.category}')"

    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            'name': self.name,
            'category': self.category,
            'unit_per_100g': self.unit_per_100g,
            'nutrition_per_100g': self.nutrition_per_100g.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Ingredient':
        """从字典创建实例"""
        nutrition = NutritionInfo.from_dict(data['nutrition_per_100g'])
        return cls(
            name=data['name'],
            nutrition=nutrition,
            unit_per_100g=data.get('unit_per_100g', 100.0),
            category=data.get('category', '其他')
        )


# ============================================================================
# 核心类：食谱配方项 (RecipeIngredient)
# ============================================================================

@dataclass
class RecipeIngredient:
    """食谱中的食材配方项"""
    ingredient: Ingredient          # 关联的食材对象
    amount: float                   # 数量
    unit: str = 'g'                 # 单位，默认为克

    def get_nutrition(self) -> NutritionInfo:
        """获取该配方项的营养成分"""
        return self.ingredient.get_nutrition(self.amount, self.unit)

    def to_dict(self) -> Dict:
        return {
            'ingredient_name': self.ingredient.name,
            'amount': self.amount,
            'unit': self.unit
        }


# ============================================================================
# 核心类：食谱 (Recipe)
# ============================================================================

class Recipe:
    """
    食谱类

    Attributes:
        name: 食谱名称
        ingredients: 所需食材列表 (List[RecipeIngredient])
        steps: 烹饪步骤 (List[str])
        cuisine: 菜系（如川菜/粤菜/西餐等）
        difficulty: 难度（简单/中等/困难）
        prep_time: 准备时间（分钟）
        cook_time: 烹饪时间（分钟）
        tags: 标签列表（如低脂/高蛋白/素食等）
    """

    def __init__(
        self,
        name: str,
        ingredients: Optional[List[RecipeIngredient]] = None,
        steps: Optional[List[str]] = None,
        cuisine: str = '通用',
        difficulty: str = '中等',
        prep_time: int = 15,
        cook_time: int = 30,
        tags: Optional[List[str]] = None,
        description: str = ''
    ):
        self.name = name
        self.ingredients = ingredients or []
        self.steps = steps or []
        self.cuisine = cuisine
        self.difficulty = difficulty
        self.prep_time = prep_time
        self.cook_time = cook_time
        self.tags = tags or []
        self.description = description

    @property
    def total_time(self) -> int:
        """总耗时（准备+烹饪）"""
        return self.prep_time + self.cook_time

    def add_ingredient(self, ingredient: Ingredient, amount: float, unit: str = 'g'):
        """添加食材到食谱"""
        recipe_ing = RecipeIngredient(
            ingredient=ingredient,
            amount=amount,
            unit=unit
        )
        self.ingredients.append(recipe_ing)

    def get_ingredient_names(self) -> List[str]:
        """获取所有食材名称列表"""
        return [ri.ingredient.name for ri in self.ingredients]

    def __repr__(self) -> str:
        return f"Recipe(name='{self.name}', ingredients={len(self.ingredients)})"

    def to_dict(self) -> Dict:
        """导出为字典"""
        return {
            'name': self.name,
            'cuisine': self.cuisine,
            'difficulty': self.difficulty,
            'prep_time': self.prep_time,
            'cook_time': self.cook_time,
            'total_time': self.total_time,
            'tags': self.tags,
            'description': self.description,
            'steps': self.steps,
            'ingredients': [ri.to_dict() for ri in self.ingredients]
        }

    @classmethod
    def from_dict(cls, data: Dict, ingredient_map: Dict[str, Ingredient]) -> 'Recipe':
        """
        从字典创建食谱实例

        Args:
            data: 食谱字典数据
            ingredient_map: 食材名称到Ingredient对象的映射
        """
        recipe_ingredients = []
        for ing_data in data.get('ingredients', []):
            # 兼容 'name' 和 'ingredient_name' 两种字段名
            ing_name = ing_data.get('name') or ing_data.get('ingredient_name', '')
            if ing_name in ingredient_map:
                ri = RecipeIngredient(
                    ingredient=ingredient_map[ing_name],
                    amount=ing_data['amount'],
                    unit=ing_data.get('unit', 'g')
                )
                recipe_ingredients.append(ri)

        return cls(
            name=data['name'],
            ingredients=recipe_ingredients,
            steps=data.get('steps', []),
            cuisine=data.get('cuisine', '通用'),
            difficulty=data.get('difficulty', '中等'),
            prep_time=data.get('prep_time', 15),
            cook_time=data.get('cook_time', 30),
            tags=data.get('tags', []),
            description=data.get('description', '')
        )


# ============================================================================
# 核心类：营养计算器 (NutritionCalculator)
# ============================================================================

class NutritionCalculator:
    """
    营养成分计算器

    提供多种方法计算食材和食谱的营养成分
    """

    @staticmethod
    def calculate_from_ingredients(
        ingredient_list: List[RecipeIngredient]
    ) -> NutritionInfo:
        """
        计算食材列表的总营养成分

        Args:
            ingredient_list: 食材配方项列表

        Returns:
            总营养成分
        """
        total = NutritionInfo()
        for ri in ingredient_list:
            total = total + ri.get_nutrition()
        return total

    @staticmethod
    def calculate_from_recipe(recipe: Recipe) -> NutritionInfo:
        """
        计算食谱的总营养成分

        Args:
            recipe: 食谱对象

        Returns:
            总营养成分
        """
        return NutritionCalculator.calculate_from_ingredients(recipe.ingredients)

    @staticmethod
    def calculate_per_serving(recipe: Recipe, servings: int = 1) -> NutritionInfo:
        """
        计算每份的营养成分

        Args:
            recipe: 食谱对象
            servings: 份数

        Returns:
            每份营养成分
        """
        total = NutritionCalculator.calculate_from_recipe(recipe)
        factor = 1.0 / servings if servings > 0 else 1.0
        return total.scale(factor)

    @staticmethod
    def analyze_macros(nutrition: NutritionInfo) -> Dict[str, float]:
        """
        分析宏量营养素比例

        Returns:
            各宏量营养素提供的热量占比（百分比）
        """
        # 热量计算：蛋白质4kcal/g，脂肪9kcal/g，碳水4kcal/g
        protein_cal = nutrition.protein * 4
        fat_cal = nutrition.fat * 9
        carbs_cal = nutrition.carbs * 4
        total_cal = protein_cal + fat_cal + carbs_cal

        if total_cal == 0:
            return {'protein_pct': 0, 'fat_pct': 0, 'carbs_pct': 0}

        return {
            'protein_pct': round(protein_cal / total_cal * 100, 1),
            'fat_pct': round(fat_cal / total_cal * 100, 1),
            'carbs_pct': round(carbs_cal / total_cal * 100, 1)
        }

    @staticmethod
    def daily_value_comparison(nutrition: NutritionInfo) -> Dict[str, float]:
        """
        与每日推荐摄入量对比（中国居民膳食指南参考值，成年人中等体力活动）

        Returns:
            各营养素占每日推荐值的百分比
        """
        # 每日参考摄入量（成年人）
        daily_values = {
            'calories': 2000,    # kcal
            'protein': 60,      # g
            'fat': 60,          # g
            'carbs': 300,       # g
            'fiber': 25,         # g
            'vitamin_a': 800,   # μg
            'vitamin_c': 100,   # mg
            'calcium': 800,     # mg
            'iron': 12          # mg
        }

        result = {}
        for key, daily in daily_values.items():
            value = getattr(nutrition, key, 0)
            result[key] = round(value / daily * 100, 1) if daily > 0 else 0

        return result


# ============================================================================
# 模块级便捷函数
# ============================================================================

def create_sample_ingredients() -> Dict[str, Ingredient]:
    """
    创建示例食材库（约60种常见食材）

    Returns:
        食材名称到Ingredient对象的字典
    """
    ingredients = {}

    # ================================================================
    # 蔬菜类
    # ================================================================
    _add = lambda name, cal, pro, fat, carbs, **kw: ingredients.__setitem__(
        name, Ingredient(name=name, nutrition=NutritionInfo(
            calories=cal, protein=pro, fat=fat, carbs=carbs,
            fiber=kw.get('fiber', 0), vitamin_a=kw.get('vit_a', 0),
            vitamin_c=kw.get('vit_c', 0), calcium=kw.get('ca', 0), iron=kw.get('fe', 0)
        ), category=kw.get('cat', '蔬菜'))
    )

    _add('西红柿', 15, 0.9, 0.2, 3.3, fiber=1.0, vit_c=14, cat='蔬菜')
    _add('黄瓜', 16, 0.8, 0.2, 3.6, fiber=0.5, vit_c=2.8, cat='蔬菜')
    _add('茄子', 21, 1.1, 0.2, 4.9, fiber=1.3, vit_c=1.8, cat='蔬菜')
    _add('南瓜', 26, 1.0, 0.1, 5.3, fiber=0.8, vit_a=426, vit_c=8, cat='蔬菜')
    _add('菠菜', 23, 2.9, 0.4, 3.6, fiber=2.2, vit_a=487, vit_c=28, ca=99, fe=2.9, cat='蔬菜')
    _add('白菜', 17, 1.5, 0.1, 3.2, fiber=1.0, vit_c=31, ca=50, cat='蔬菜')
    _add('生菜', 15, 1.4, 0.2, 2.9, fiber=1.3, vit_c=9, cat='蔬菜')
    _add('油菜', 14, 1.5, 0.3, 2.0, fiber=1.1, vit_c=36, ca=108, cat='蔬菜')
    _add('娃娃菜', 13, 1.1, 0.1, 2.4, fiber=0.9, vit_c=22, cat='蔬菜')
    _add('青椒', 22, 1.0, 0.2, 4.6, fiber=1.4, vit_c=72, cat='蔬菜')
    _add('红椒', 31, 1.0, 0.3, 6.4, fiber=2.1, vit_c=127, vit_a=157, cat='蔬菜')
    _add('土豆', 76, 2.0, 0.1, 15.5, fiber=1.5, vit_c=20, cat='蔬菜')
    _add('红薯', 99, 1.1, 0.1, 23.6, fiber=2.3, vit_c=2.4, vit_a=709, cat='蔬菜')
    _add('莲藕', 73, 1.9, 0.2, 16.4, fiber=2.2, vit_c=44, ca=39, cat='蔬菜')
    _add('山药', 56, 1.5, 0.1, 12.4, fiber=0.8, vit_c=6, cat='蔬菜')
    _add('金针菇', 32, 2.4, 0.4, 3.3, fiber=2.7, vit_c=2.0, ca=2, cat='菌菇')
    _add('香菇', 26, 2.7, 0.3, 4.0, fiber=3.7, vit_c=1.0, ca=5, cat='菌菇')
    _add('木耳', 27, 1.5, 0.2, 5.5, fiber=29.9, vit_c=5.0, fe=5.3, cat='菌菇')
    _add('豆芽', 26, 2.1, 0.4, 3.2, fiber=1.5, vit_c=6, cat='蔬菜')

    # ================================================================
    # 肉蛋类
    # ================================================================
    _add('鸡蛋', 144, 13.3, 8.8, 2.2, ca=56, fe=2.0, cat='蛋类')
    _add('鸡胸肉', 133, 31.0, 3.6, 0, iron=1.0, cat='肉类')
    _add('鸡腿肉', 181, 25.2, 8.4, 0, iron=1.5, cat='肉类')
    _add('猪肉', 143, 21.3, 6.2, 0, iron=1.6, ca=6, cat='肉类')
    _add('牛肉', 125, 22.3, 4.2, 0, iron=2.8, ca=6, cat='肉类')
    _add('牛里脊', 107, 20.4, 2.4, 0, iron=2.0, cat='肉类')
    _add('虾仁', 93, 18.3, 1.4, 1.9, ca=83, fe=1.7, cat='水产')
    _add('三文鱼', 139, 20.4, 7.0, 0, vit_a=40, fe=0.3, cat='水产')
    _add('鳕鱼', 82, 18.1, 0.5, 0, ca=12, fe=0.4, cat='水产')

    # ================================================================
    # 豆制品
    # ================================================================
    _add('豆腐', 81, 8.1, 3.7, 3.8, ca=164, fe=1.9, cat='豆制品')
    _add('豆浆', 33, 2.9, 1.6, 1.8, ca=19, fe=0.5, cat='豆制品')
    _add('腐竹', 459, 25.3, 21.8, 22.7, ca=77, fe=13.2, cat='豆制品')
    _add('豆腐皮', 409, 44.6, 17.7, 14.0, ca=56, fe=9.7, cat='豆制品')

    # ================================================================
    # 谷物主食类
    # ================================================================
    _add('大米', 346, 7.4, 0.8, 77.2, fiber=0.4, cat='谷物')
    _add('面条', 284, 8.3, 1.1, 59.5, fiber=2.2, cat='谷物')
    _add('馒头', 223, 7.0, 1.1, 47.0, fiber=1.3, cat='谷物')
    _add('全麦面包', 247, 11.0, 3.4, 42.0, fiber=5.0, cat='谷物')
    _add('燕麦', 389, 16.9, 6.9, 66.0, fiber=10.6, cat='谷物')
    _add('小米', 361, 9.0, 3.1, 75.1, fiber=1.6, vit_a=17, cat='谷物')
    _add('玉米', 112, 4.0, 1.2, 23.6, fiber=2.9, vit_a=11, vit_c=10, cat='谷物')

    # ================================================================
    # 水果类（干重估算，用于配菜参考）
    # ================================================================
    _add('苹果', 52, 0.3, 0.2, 13.7, fiber=2.4, vit_c=5, cat='水果')
    _add('香蕉', 93, 1.4, 0.2, 23.0, fiber=1.7, vit_c=9, ca=7, cat='水果')
    _add('柠檬', 29, 1.1, 0.3, 6.2, fiber=2.8, vit_c=53, ca=26, cat='水果')

    # ================================================================
    # 奶类及坚果
    # ================================================================
    _add('牛奶', 54, 3.0, 3.2, 3.4, ca=104, fe=0.1, cat='奶类')
    _add('奶酪', 328, 25.7, 23.4, 3.1, ca=721, fe=0.7, cat='奶类')
    _add('杏仁', 579, 21.3, 49.9, 22.0, fiber=12.5, ca=264, fe=4.7, cat='坚果')
    _add('花生', 567, 24.8, 45.0, 16.1, fiber=5.5, ca=47, fe=4.6, cat='坚果')

    # ================================================================
    # 调味料类（低热量，仅提供风味）
    # ================================================================
    _add('食用油', 884, 0, 100, 0, cat='调味品')
    _add('芝麻油', 898, 0, 99.7, 0, cat='调味品')
    _add('盐', 0, 0, 0, 0, cat='调味品')
    _add('酱油', 63, 8.1, 0, 7.9, ca=3, cat='调味品')
    _add('蚝油', 66, 2.3, 0, 11.8, ca=2, cat='调味品')
    _add('香醋', 28, 0.3, 0, 4.9, ca=6, cat='调味品')
    _add('白糖', 400, 0, 0, 100, cat='调味品')
    _add('冰糖', 397, 0, 0, 99.5, cat='调味品')
    _add('淀粉', 332, 0.5, 0.1, 82.0, cat='调味品')
    _add('豆瓣酱', 59, 3.2, 2.1, 7.0, fiber=1.5, vit_c=2, cat='调味品')
    _add('番茄酱', 112, 1.0, 0.1, 26.4, fiber=1.5, vit_c=8, cat='调味品')
    _add('辣椒油', 450, 0, 45.0, 12.0, fiber=0.5, cat='调味品')

    # ================================================================
    # 其他
    # ================================================================
    _add('紫菜', 216, 26.7, 1.7, 22.3, fiber=21.6, ca=264, fe=54.0, vit_a=137, vit_c=2.0, cat='藻类')
    _add('虾皮', 153, 30.7, 2.2, 2.5, ca=991, fe=6.7, cat='水产')

    return ingredients


def create_sample_recipes(ingredient_map: Dict[str, Ingredient]) -> List[Recipe]:
    """
    创建示例食谱（40+道）

    Args:
        ingredient_map: 食材名称到对象的映射

    Returns:
        食谱列表
    """
    recipes = []

    def _r(name, cuisine, difficulty, prep, cook, tags, desc, steps, items):
        """快速创建食谱的辅助函数"""
        r = Recipe(
            name=name, cuisine=cuisine, difficulty=difficulty,
            prep_time=prep, cook_time=cook, tags=tags,
            description=desc, steps=steps
        )
        ok = True
        for ing_name, amount, unit in items:
            if ing_name in ingredient_map:
                r.add_ingredient(ingredient_map[ing_name], amount, unit)
            else:
                ok = False
        if ok:
            recipes.append(r)
        return r

    # ================================================================
    # 家常菜（15道）
    # ================================================================
    _r('西红柿炒鸡蛋', '家常菜', '简单', 10, 15,
       ['家常', '快手菜', '高蛋白'],
       '经典家常菜，酸甜可口，营养丰富',
       ['西红柿洗净切块，鸡蛋打散加少许盐',
        '热锅凉油，倒入蛋液炒至凝固盛出',
        '锅中留底油，放入西红柿翻炒出汁',
        '加入炒好的鸡蛋，调入盐和糖翻炒均匀即可'],
       [('鸡蛋', 2, '个'), ('西红柿', 200, 'g'),
        ('食用油', 15, 'g'), ('盐', 2, 'g'), ('白糖', 5, 'g')])

    _r('清炒西兰花', '家常菜', '简单', 5, 10,
       ['素食', '低脂', '高纤维', '减肥'],
       '清爽可口的家常素菜，富含维生素C',
       ['西兰花洗净切小朵，用淡盐水浸泡10分钟',
        '烧开水，加少许盐和油，放入西兰花焯烫30秒捞出',
        '热锅凉油，爆香蒜末',
        '倒入西兰花快速翻炒，加盐调味即可'],
       [('西兰花', 300, 'g'), ('食用油', 10, 'g'),
        ('盐', 2, 'g'), ('香菇', 30, 'g')])

    _r('青椒土豆丝', '家常菜', '简单', 10, 15,
       ['素食', '家常', '低脂', '快手菜'],
       '清爽脆口的家常小炒，色彩诱人',
       ['土豆去皮切细丝，用清水浸泡去淀粉',
        '青椒切丝备用',
        '热锅凉油，先放入土豆丝翻炒至半熟',
        '加入青椒丝继续翻炒',
        '加盐调味，炒至土豆丝熟透即可'],
       [('土豆', 200, 'g'), ('青椒', 100, 'g'),
        ('食用油', 10, 'g'), ('盐', 2, 'g')])

    _r('红烧豆腐', '家常菜', '简单', 5, 15,
       ['素食', '家常', '高蛋白', '补钙'],
       '豆腐嫩滑，酱香浓郁',
       ['豆腐切块，用盐水浸泡10分钟去豆腥',
        '热锅凉油，放入豆腐煎至两面金黄',
        '加入酱油、白糖和适量水',
        '大火烧开后转小火焖煮5分钟',
        '大火收汁即可'],
       [('豆腐', 300, 'g'), ('食用油', 10, 'g'),
        ('酱油', 15, 'ml'), ('白糖', 10, 'g'), ('盐', 2, 'g')])

    _r('蒜蓉西兰花', '家常菜', '简单', 5, 8,
       ['素食', '低脂', '高维生素', '减肥'],
       '蒜香浓郁，西兰花翠绿爽口',
       ['西兰花洗净切小朵，蒜切末',
        '烧开水，加少许盐，放入西兰花焯烫1分钟捞出',
        '热锅凉油，小火煸香蒜末',
        '倒入西兰花快速翻炒，加盐调味即可'],
       [('西兰花', 250, 'g'), ('香菇', 30, 'g'),
        ('食用油', 8, 'g'), ('盐', 2, 'g')])

    _r('洋葱炒鸡蛋', '家常菜', '简单', 5, 10,
       ['家常', '快手菜', '简单'],
       '洋葱甜香，鸡蛋嫩滑，简单又下饭',
       ['洋葱切丝，鸡蛋打散加少许盐',
        '热锅凉油，倒入蛋液炒至凝固盛出',
        '锅中再加油，放入洋葱丝翻炒至软',
        '加入鸡蛋，调入盐翻炒均匀即可'],
       [('鸡蛋', 2, '个'), ('洋葱', 150, 'g'),
        ('食用油', 10, 'g'), ('盐', 2, 'g')])

    _r('胡萝卜炒鸡蛋', '家常菜', '简单', 5, 10,
       ['家常', '护眼', '高维生素', '简单'],
       '胡萝卜富含维生素A，与鸡蛋搭配营养翻倍',
       ['胡萝卜切丝，鸡蛋打散加少许盐',
        '热锅凉油，倒入蛋液炒至凝固盛出',
        '锅中再加少许油，放入胡萝卜丝翻炒至软',
        '加入鸡蛋，调入盐翻炒均匀即可'],
       [('鸡蛋', 2, '个'), ('胡萝卜', 150, 'g'),
        ('食用油', 10, 'g'), ('盐', 2, 'g')])

    _r('黄瓜炒鸡蛋', '家常菜', '简单', 5, 8,
       ['素食', '清淡', '快手菜', '家常'],
       '清爽开胃，夏日首选',
       ['黄瓜洗净切片，鸡蛋打散',
        '热锅凉油，倒入蛋液炒至凝固盛出',
        '锅中再加少许油，放入黄瓜片翻炒片刻',
        '加入鸡蛋，调入盐翻炒均匀即可'],
       [('鸡蛋', 2, '个'), ('黄瓜', 200, 'g'),
        ('食用油', 10, 'g'), ('盐', 2, 'g')])

    _r('醋溜白菜', '家常菜', '简单', 5, 10,
       ['素食', '家常', '低脂', '开胃'],
       '酸辣爽口，开胃下饭',
       ['白菜洗净切块，蒜切末',
        '热锅凉油，爆香蒜末和干辣椒',
        '放入白菜大火翻炒至软',
        '加入醋、酱油和盐调味，翻炒均匀即可'],
       [('白菜', 300, 'g'), ('食用油', 10, 'g'),
        ('香醋', 15, 'ml'), ('酱油', 10, 'ml'), ('盐', 2, 'g')])

    _r('蒜蓉生菜', '家常菜', '简单', 3, 5,
       ['素食', '低脂', '快手菜', '清淡'],
       '最简单的绿色健康菜',
       ['生菜洗净撕成大块，蒜切末',
        '热锅凉油，小火煸香蒜末',
        '倒入生菜快速翻炒至微微变软',
        '加盐调味即可'],
       [('生菜', 250, 'g'), ('食用油', 8, 'g'),
        ('盐', 2, 'g')])

    _r('茄子烧豆角', '家常菜', '中等', 10, 20,
       ['素食', '家常', '高纤维'],
       '茄子软糯，豆角脆嫩，下饭佳品',
       ['茄子和豆角分别切段',
        '热锅凉油，先煸炒茄子至微软盛出',
        '再炒豆角至变色',
        '加入茄子，放酱油和盐，加少量水焖煮',
        '收汁后即可'],
       [('茄子', 200, 'g'), ('豆芽', 150, 'g'),
        ('食用油', 15, 'g'), ('酱油', 15, 'ml'), ('盐', 2, 'g')])

    _r('干煸四季豆', '家常菜', '中等', 8, 15,
       ['素食', '家常', '下饭'],
       '四季豆干香入味，越嚼越香',
       ['四季豆去头尾，掰成段',
        '热锅宽油，放入四季豆炸至表皮起皱盛出',
        '锅中留底油，爆香蒜末和干辣椒',
        '放回四季豆，加盐和酱油翻炒均匀即可'],
       [('豆芽', 250, 'g'), ('食用油', 15, 'g'),
        ('酱油', 10, 'ml'), ('盐', 2, 'g')])

    _r('番茄菜花', '家常菜', '简单', 5, 15,
       ['素食', '家常', '清淡', '高维生素'],
       '番茄酸甜，菜花爽脆',
       ['菜花切小朵焯水备用',
        '西红柿切块',
        '热锅凉油，炒西红柿至出汁',
        '放入菜花翻炒，加盐调味即可'],
       [('白菜', 200, 'g'), ('西红柿', 150, 'g'),
        ('食用油', 10, 'g'), ('盐', 2, 'g')])

    _r('香菇青菜', '家常菜', '简单', 5, 10,
       ['素食', '清淡', '高纤维'],
       '香菇鲜香，青菜爽口',
       ['青菜洗净，香菇切片',
        '热锅凉油，爆香蒜末',
        '放入香菇翻炒出香味',
        '加入青菜快速翻炒，加盐调味即可'],
       [('生菜', 200, 'g'), ('香菇', 80, 'g'),
        ('食用油', 10, 'g'), ('盐', 2, 'g')])

    _r('菠菜炒蛋', '家常菜', '简单', 5, 10,
       ['家常', '高蛋白', '补铁', '家常'],
       '菠菜含铁丰富，鸡蛋补优质蛋白',
       ['菠菜洗净焯水挤干备用',
        '鸡蛋打散',
        '热锅凉油，倒入蛋液炒至凝固盛出',
        '锅中再加油，放菠菜翻炒',
        '加入鸡蛋，调入盐翻炒均匀'],
       [('菠菜', 250, 'g'), ('鸡蛋', 2, '个'),
        ('食用油', 10, 'g'), ('盐', 2, 'g')])

    # ================================================================
    # 川菜（6道）
    # ================================================================
    _r('土豆烧鸡', '川菜', '中等', 20, 40,
       ['下饭菜', '高蛋白', '家常'],
       '经典川味，土豆软糯，鸡肉鲜嫩',
       ['鸡腿肉切块，土豆去皮切块',
        '锅中热油，放入鸡块翻炒至变色',
        '加入姜蒜、酱油翻炒均匀',
        '加水没过鸡块，大火烧开后转小火炖30分钟',
        '加入土豆块，继续炖15分钟',
        '大火收汁，加盐调味即可'],
       [('鸡胸肉', 200, 'g'), ('土豆', 200, 'g'),
        ('食用油', 15, 'g'), ('酱油', 20, 'ml'), ('盐', 3, 'g')])

    _r('宫保鸡丁', '川菜', '中等', 15, 20,
       ['川菜', '下饭菜', '高蛋白'],
       '经典川菜，麻辣鲜香，花生酥脆',
       ['鸡胸肉切丁，用盐和淀粉腌制10分钟',
        '调制宫保汁：酱油、醋、糖、淀粉、水混合',
        '热锅宽油，放入鸡丁滑熟盛出',
        '锅中留底油，爆香花椒和干辣椒',
        '放回鸡丁，倒入宫保汁快速翻炒',
        '出锅前撒入花生米即可'],
       [('鸡胸肉', 200, 'g'), ('花生', 30, 'g'),
        ('食用油', 20, 'g'), ('酱油', 15, 'ml'),
        ('香醋', 10, 'ml'), ('白糖', 15, 'g'), ('淀粉', 5, 'g')])

    _r('麻婆豆腐', '川菜', '简单', 10, 15,
       ['川菜', '家常', '下饭菜', '高蛋白'],
       '麻辣鲜香，豆腐嫩滑',
       ['豆腐切块，用盐水浸泡去腥',
        '热锅凉油，放入肉末炒散',
        '加入豆瓣酱、辣椒油炒出红油',
        '放入豆腐轻轻翻炒',
        '加酱油和水烧开后小火焖5分钟',
        '水淀粉勾芡，出锅撒花椒粉和葱花'],
       [('豆腐', 300, 'g'), ('猪肉', 80, 'g'),
        ('食用油', 15, 'g'), ('豆瓣酱', 20, 'g'),
        ('酱油', 10, 'ml'), ('淀粉', 5, 'g'), ('盐', 2, 'g')])

    _r('鱼香肉丝', '川菜', '中等', 15, 20,
       ['川菜', '下饭菜', '高蛋白'],
       '酸甜微辣，肉丝滑嫩',
       ['猪里脊切丝，用盐和淀粉腌制',
        '木耳、胡萝卜、青椒切丝',
        '调制鱼香汁：醋、糖、酱油、淀粉、水混合',
        '热锅宽油，炒肉丝至变色盛出',
        '锅中爆香葱姜蒜，放豆瓣酱',
        '放入各色蔬菜丝翻炒，倒回肉丝',
        '淋入鱼香汁翻炒均匀即可'],
       [('猪肉', 150, 'g'), ('木耳', 50, 'g'),
        ('胡萝卜', 50, 'g'), ('青椒', 50, 'g'),
        ('食用油', 15, 'g'), ('酱油', 10, 'ml'),
        ('香醋', 10, 'ml'), ('白糖', 10, 'g'), ('淀粉', 5, 'g')])

    _r('水煮牛肉', '川菜', '困难', 20, 25,
       ['川菜', '麻辣', '高蛋白'],
       '麻辣鲜烫，肉片滑嫩',
       ['牛肉逆纹切薄片，用盐和淀粉腌制',
        '豆芽和青菜焯水铺底',
        '热锅凉油，炒香豆瓣酱和辣椒油',
        '加入高汤或水烧开，放盐和酱油调味',
        '放入牛肉片滑熟，连汤倒在菜上',
        '撒上蒜末、干辣椒碎和花椒粉',
        '淋上热油激发香味即可'],
       [('牛肉', 200, 'g'), ('豆芽', 150, 'g'),
        ('食用油', 20, 'g'), ('豆瓣酱', 30, 'g'),
        ('酱油', 10, 'ml'), ('淀粉', 10, 'g'), ('盐', 2, 'g')])

    _r('回锅肉', '川菜', '中等', 15, 20,
       ['川菜', '下饭菜', '家常'],
       '肥而不腻，酱香浓郁',
       ['五花肉整块煮熟切片',
        '青蒜切段备用',
        '热锅不加油，放入肉片煸炒出油',
        '肉片盛出，锅中留油',
        '放入豆瓣酱、甜面酱炒香',
        '放回肉片和青蒜翻炒，加酱油调味即可'],
       [('猪肉', 250, 'g'), ('白菜', 100, 'g'),
        ('食用油', 10, 'g'), ('酱油', 10, 'ml'), ('盐', 2, 'g')])

    # ================================================================
    # 粤菜（4道）
    # ================================================================
    _r('白灼虾', '粤菜', '简单', 10, 10,
       ['粤菜', '清淡', '高蛋白', '原汁原味'],
       '虾肉鲜甜，原汁原味',
       ['鲜虾洗净，剪去虾须',
        '锅中水烧开，放姜片和料酒',
        '放入大虾煮至变红弯曲（约3分钟）',
        '捞出装盘，配蘸料（生抽+姜末）食用'],
       [('虾仁', 300, 'g'), ('盐', 2, 'g')])

    _r('清蒸鲈鱼', '粤菜', '中等', 10, 15,
       ['粤菜', '清淡', '高蛋白', '补脑'],
       '鱼肉鲜嫩，清淡少油',
       ['鲈鱼处理干净，两面划花刀',
        '鱼身抹盐和料酒，放姜片，腌制10分钟',
        '水开后放入蒸8-10分钟',
        '取出倒掉蒸出的水',
        '铺上葱丝和姜丝，淋上热油和蒸鱼豉油即可'],
       [('鳕鱼', 300, 'g'), ('酱油', 20, 'ml'),
        ('食用油', 10, 'g'), ('盐', 2, 'g')])

    _r('叉烧肉', '粤菜', '中等', 20, 30,
       ['粤菜', '高蛋白', '下饭菜'],
       '色泽红亮，甜香可口',
       ['梅花肉切成长条',
        '用叉烧酱、蜂蜜、酱油腌制过夜',
        '烤箱预热200度，烤25分钟（中途翻面刷腌料）',
        '出炉切片即可'],
       [('猪肉', 300, 'g'), ('酱油', 30, 'ml'),
        ('白糖', 20, 'g'), ('蚝油', 15, 'ml'), ('盐', 2, 'g')])

    _r('虾仁滑蛋', '粤菜', '简单', 10, 10,
       ['粤菜', '清淡', '高蛋白'],
       '虾仁Q弹，鸡蛋嫩滑',
       ['虾仁去虾线，用盐和淀粉腌制',
        '鸡蛋打散，加少许盐',
        '热锅宽油，炒虾仁至变色盛出',
        '锅中再加油，倒入蛋液',
        '蛋液半凝固时放入虾仁，轻轻翻动',
        '蛋完全凝固后即可出锅'],
       [('虾仁', 150, 'g'), ('鸡蛋', 3, '个'),
        ('食用油', 15, 'g'), ('盐', 2, 'g'), ('淀粉', 5, 'g')])

    # ================================================================
    # 主食类（5道）
    # ================================================================
    _r('番茄鸡蛋面', '家常菜', '简单', 10, 20,
       ['主食', '快手菜', '暖胃'],
       '汤鲜面滑，番茄的酸甜与鸡蛋的嫩滑完美结合',
       ['西红柿切块，鸡蛋打散',
        '水烧开下面条煮至8分熟捞出',
        '另起锅炒鸡蛋盛出',
        '锅中炒西红柿出汁，加水煮开',
        '放入面条和鸡蛋，加盐调味即可'],
       [('鸡蛋', 2, '个'), ('西红柿', 150, 'g'),
        ('面条', 100, 'g'), ('食用油', 10, 'g'), ('盐', 2, 'g')])

    _r('扬州炒饭', '家常菜', '简单', 10, 15,
       ['主食', '高蛋白', '家常'],
       '色彩丰富，营养均衡',
       ['米饭用鸡蛋拌匀备用',
        '虾仁、豌豆、胡萝卜丁分别焯熟',
        '热锅宽油，先炒鸡蛋盛出',
        '再炒虾仁和蔬菜',
        '放回米饭和鸡蛋，大火翻炒',
        '加盐和酱油调味，炒散均匀即可'],
       [('大米', 150, 'g'), ('鸡蛋', 2, '个'),
        ('虾仁', 50, 'g'), ('黄瓜', 30, 'g'),
        ('食用油', 15, 'g'), ('盐', 2, 'g')])

    _r('小米粥', '家常菜', '简单', 5, 30,
       ['主食', '清淡', '养胃', '早餐'],
       '绵密顺滑，养胃暖身',
       ['小米洗净，提前浸泡30分钟',
        '锅中加水烧开',
        '放入小米，大火煮开后转小火',
        '不断搅拌防止糊底',
        '煮至粥稠米烂即可'],
       [('小米', 50, 'g'), ('大米', 20, 'g')])

    _r('紫菜蛋花汤', '家常菜', '简单', 5, 10,
       ['汤', '清淡', '快手菜', '补碘'],
       '简单鲜美，富含微量元素',
       ['紫菜撕碎，鸡蛋打散',
        '锅中加水烧开',
        '放入紫菜煮2分钟',
        '慢慢淋入蛋液形成蛋花',
        '加盐和香油调味即可'],
       [('紫菜', 10, 'g'), ('鸡蛋', 1, '个'),
        ('盐', 2, 'g'), ('芝麻油', 3, 'g')])

    _r('葱油拌面', '家常菜', '简单', 10, 10,
       ['主食', '快手菜', '香味浓郁'],
       '葱香扑鼻，简单美味',
       ['面条煮熟捞出过凉水',
        '小葱切段，用热油炸香制成葱油',
        '碗中放酱油、糖和盐',
        '倒入面条，淋上葱油拌匀',
        '撒上葱花即可'],
       [('面条', 100, 'g'), ('酱油', 20, 'ml'),
        ('食用油', 15, 'g'), ('白糖', 5, 'g'), ('盐', 2, 'g')])

    # ================================================================
    # 健身/减脂餐（4道）
    # ================================================================
    _r('鸡胸肉沙拉', '西餐', '简单', 15, 20,
       ['健身餐', '高蛋白', '低脂', '减脂'],
       '健身人群首选，高蛋白低脂肪',
       ['鸡胸肉用盐和黑胡椒腌制10分钟',
        '平底锅少油，将鸡胸肉煎至两面金黄熟透',
        '鸡胸肉切片备用',
        '生菜撕碎，紫甘蓝切丝',
        '铺在盘底，放上鸡胸肉',
        '淋上柠檬汁即可'],
       [('鸡胸肉', 150, 'g'), ('生菜', 100, 'g'),
        ('黄瓜', 50, 'g'), ('食用油', 5, 'g'),
        ('盐', 2, 'g'), ('柠檬', 30, 'g')])

    _r('牛排配蔬菜', '西餐', '中等', 10, 20,
       ['健身餐', '高蛋白', '低碳'],
       '高蛋白低碳水，适合健身人士',
       ['牛里脊用盐和黑胡椒腌制',
        '热锅大火，将牛排每面煎3-4分钟至所需熟度',
        '静置5分钟后切片',
        '西兰花和胡萝卜焯熟',
        '摆盘，牛排旁边配蔬菜即可'],
       [('牛里脊', 200, 'g'), ('西兰花', 100, 'g'),
        ('胡萝卜', 50, 'g'), ('食用油', 10, 'g'),
        ('盐', 2, 'g')])

    _r('三文鱼刺身', '西餐', '简单', 15, 0,
       ['健身餐', '高蛋白', '低碳', 'Omega-3'],
       '富含Omega-3，入口即化',
       ['三文鱼切薄片',
        '配芥末和酱油蘸料食用'],
       [('三文鱼', 150, 'g')])

    _r('无油煎鸡胸', '健身餐', '简单', 5, 15,
       ['健身餐', '低脂', '高蛋白', '减脂'],
       '不放油，用不粘锅煎制，极低脂肪',
       ['鸡胸肉横向剖成两片，用刀背敲松',
        '撒盐、黑胡椒和大蒜粉腌制',
        '不粘锅大火烧热，放入鸡胸',
        '每面煎3-4分钟，盖盖子焖2分钟',
        '切片装盘'],
       [('鸡胸肉', 200, 'g'), ('盐', 2, 'g')])

    # ================================================================
    # 汤类（3道）
    # ================================================================
    _r('玉米排骨汤', '粤菜', '中等', 15, 90,
       ['汤', '滋补', '家常', '高钙'],
       '汤鲜味美，营养丰富',
       ['排骨焯水去血沫',
        '玉米切段，胡萝卜切块',
        '砂锅加水，放入排骨、玉米和胡萝卜',
        '大火烧开后转小火炖1.5小时',
        '加盐调味即可'],
       [('猪肉', 200, 'g'), ('玉米', 150, 'g'),
        ('胡萝卜', 50, 'g'), ('盐', 3, 'g')])

    _r('西红柿鸡蛋汤', '家常菜', '简单', 5, 15,
       ['汤', '清淡', '家常', '快手菜'],
       '酸甜开胃，老少皆宜',
       ['西红柿切块，鸡蛋打散',
        '锅中加水烧开，放西红柿煮出味',
        '加盐和酱油调味',
        '慢慢淋入蛋液形成蛋花',
        '淋香油出锅'],
       [('西红柿', 150, 'g'), ('鸡蛋', 2, '个'),
        ('食用油', 10, 'g'), ('盐', 2, 'g')])

    _r('虾皮紫菜汤', '家常菜', '简单', 3, 10,
       ['汤', '补钙', '快手菜', '清淡'],
       '补钙首选，简单鲜美',
       ['紫菜撕碎，虾皮洗净',
        '锅中加水烧开',
        '放紫菜和虾皮煮3分钟',
        '加盐和香油调味即可'],
       [('紫菜', 5, 'g'), ('虾皮', 10, 'g'),
        ('盐', 2, 'g'), ('芝麻油', 3, 'g')])

    # ================================================================
    # 甜品/小食（2道）
    # ================================================================
    _r('拔丝地瓜', '家常菜', '中等', 10, 20,
       ['甜品', '家常', '下午茶'],
       '外脆里嫩，糖丝缠绕',
       ['红薯去皮切滚刀块',
        '油温六成热，下红薯炸至金黄捞出',
        '锅中放白糖和少许水，小火熬至起大泡',
        '糖色变黄时放入红薯快速翻匀',
        '盛盘，趁热拉丝'],
       [('红薯', 300, 'g'), ('食用油', 30, 'g'),
        ('白糖', 80, 'g')])

    _r('香蕉奶昔', '西餐', '简单', 3, 0,
       ['饮品', '甜品', '快手'],
       '香甜顺滑，营养丰富',
       ['香蕉去皮切段',
        '放入搅拌机，加牛奶',
        '搅打至顺滑细腻',
        '倒入杯中即可饮用'],
       [('香蕉', 150, 'g'), ('牛奶', 200, 'ml')])

    return recipes

    return recipes


# ============================================================================
# 主程序入口（用于测试）
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("阶段一测试：食材、食谱与营养计算")
    print("=" * 60)

    # 创建示例数据
    print("\n[1] 创建食材库...")
    ingredient_map = create_sample_ingredients()
    print(f"    共创建 {len(ingredient_map)} 种食材:")
    for name, ing in ingredient_map.items():
        print(f"    - {ing}")

    # 创建示例食谱
    print("\n[2] 创建示例食谱...")
    recipes = create_sample_recipes(ingredient_map)
    print(f"    共创建 {len(recipes)} 个食谱:")
    for recipe in recipes:
        print(f"    - {recipe.name} (耗时{recipe.total_time}分钟)")

    # 计算营养成分
    print("\n[3] 计算营养成分示例：")
    for recipe in recipes:
        total_nutrition = NutritionCalculator.calculate_from_recipe(recipe)
        macros = NutritionCalculator.analyze_macros(total_nutrition)
        daily_values = NutritionCalculator.daily_value_comparison(total_nutrition)

        print(f"\n    {recipe.name}:")
        print(f"      总热量: {total_nutrition.calories:.1f} kcal")
        print(f"      蛋白质: {total_nutrition.protein:.1f}g | 脂肪: {total_nutrition.fat:.1f}g | 碳水: {total_nutrition.carbs:.1f}g")
        print(f"      宏量比例: 蛋白质{macros['protein_pct']}% | 脂肪{macros['fat_pct']}% | 碳水{macros['carbs_pct']}%")
        print(f"      每日摄入占比: 热量{daily_values['calories']}% | 蛋白质{daily_values['protein']}%")

    print("\n" + "=" * 60)
    print("阶段一测试完成！")
    print("=" * 60)
