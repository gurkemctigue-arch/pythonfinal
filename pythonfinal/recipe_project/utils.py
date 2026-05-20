"""
阶段二：工具函数 - 正则解析与 JSON 导入导出

本模块负责：
    - 使用正则表达式解析用户输入的食材字符串
    - JSON 数据的导入导出
    - 通用辅助函数
"""

import re
import json
import os
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
from dataclasses import asdict

from models import Ingredient, Recipe, NutritionInfo


# ============================================================================
# 正则表达式解析：用户输入 -> 食材列表
# ============================================================================

# 正则模式说明：
#   食材名: 汉字、英文字母、数字的组合（支持复合名称如"西红柿炒鸡蛋"）
#   数量: 数字（支持小数）
#   单位: 克/g、千克/kg、个、ml/L、斤、两、勺、杯 等
INPUT_PATTERN = re.compile(
    r'(?P<name>[^\d,，]+?)'
    r'(?P<amount>\d+(?:\.\d+)?)'
    r'(?P<unit>g|kg|ml|L|个|斤|两|勺|杯|克|千克|毫升|升|公斤)?',
    re.UNICODE
)

# 备选模式：捕获没有单位的情况（默认为"个"或"g"）
SIMPLE_PATTERN = re.compile(
    r'(?P<name>[^,，\n]+?)'
    r'(?P<amount>\d+(?:\.\d+)?)'
    r'(?P<unit>个)?',
    re.UNICODE
)


class ParsedIngredient:
    """解析后的食材项"""

    def __init__(self, name: str, amount: float, unit: str):
        self.name = name.strip()
        self.amount = amount
        self.unit = unit

    def __repr__(self):
        return f"ParsedIngredient(name='{self.name}', amount={self.amount}, unit='{self.unit}')"


def normalize_unit(unit: str) -> str:
    """
    标准化单位名称

    Args:
        unit: 原始单位字符串

    Returns:
        标准化后的单位 ('g', 'kg', 'ml', 'L', '个', '斤', '两', '勺', '杯')
    """
    if not unit:
        return '个'  # 默认单位

    unit = unit.strip().lower()
    mapping = {
        '克': 'g', '千克': 'kg', '公斤': 'kg',
        '毫升': 'ml', '升': 'L',
        '斤': '斤', '两': '两',
        '勺': '勺', '杯': '杯',
        'g': 'g', 'kg': 'kg', 'ml': 'ml', 'l': 'L',
    }
    return mapping.get(unit, 'g')


def parse_ingredient_input(input_text: str) -> List[ParsedIngredient]:
    """
    解析用户输入的食材字符串

    支持的格式：
        "西红柿200g, 鸡蛋2个"
        "鸡胸肉150g 西兰花100g"
        "西红柿 200 克, 鸡蛋 2 个"

    Args:
        input_text: 用户输入的原始字符串

    Returns:
        ParsedIngredient 对象列表
    """
    results = []
    text = input_text.strip()

    # 优先尝试完整匹配（数字+单位）
    for match in INPUT_PATTERN.finditer(text):
        name = match.group('name').strip()
        amount_str = match.group('amount')
        unit = normalize_unit(match.group('unit') or 'g')

        if name and amount_str:
            try:
                amount = float(amount_str)
                if amount > 0:
                    results.append(ParsedIngredient(name, amount, unit))
            except ValueError:
                pass

    # 如果完整匹配失败，尝试简化模式
    if not results:
        for match in SIMPLE_PATTERN.finditer(text):
            name = match.group('name').strip()
            amount_str = match.group('amount')

            if name and amount_str:
                try:
                    amount = float(amount_str)
                    if amount > 0:
                        results.append(ParsedIngredient(name, amount, 'g'))
                except ValueError:
                    pass

    return results


def fuzzy_match_ingredient(
    parsed_name: str,
    available_names: List[str],
    threshold: float = 0.6
) -> Optional[str]:
    """
    模糊匹配食材名称

    使用简单的包含匹配和首字母匹配

    Args:
        parsed_name: 解析出的食材名称
        available_names: 可用的食材名称列表
        threshold: 相似度阈值（0-1）

    Returns:
        匹配的食材名称，未找到则返回 None
    """
    parsed_lower = parsed_name.lower()

    # 1. 精确包含匹配（最优先）
    for name in available_names:
        if parsed_lower in name.lower() or name.lower() in parsed_lower:
            return name

    # 2. 首字匹配（处理"番茄" vs "西红柿"等别名情况）
    if parsed_name and parsed_name[0] in '番茄土鸡猪牛羊鱼':
        for name in available_names:
            if name[0] == parsed_name[0] if name else False:
                # 简单首字匹配
                return name

    # 3. 返回最接近的（按名称长度差异排序）
    candidates = []
    for name in available_names:
        # 计算包含关系作为简单相似度
        if any(c in parsed_lower for c in name.lower()[:2]):
            candidates.append(name)

    if candidates:
        # 返回最短匹配的（更可能是完整名称）
        return min(candidates, key=len)

    return None


def match_parsed_to_inventory(
    parsed_list: List[ParsedIngredient],
    ingredient_map: Dict[str, Ingredient]
) -> List[Tuple[ParsedIngredient, Optional[Ingredient]]]:
    """
    将解析出的食材与库存食材进行匹配

    Args:
        parsed_list: 解析出的食材列表
        ingredient_map: 可用食材字典 {名称: Ingredient对象}

    Returns:
        [(解析项, 匹配的食材对象), ...]
    """
    available_names = list(ingredient_map.keys())
    results = []

    for parsed in parsed_list:
        # 精确匹配
        matched = ingredient_map.get(parsed.name)

        if not matched:
            # 模糊匹配
            matched_name = fuzzy_match_ingredient(parsed.name, available_names)
            if matched_name:
                matched = ingredient_map.get(matched_name)

        results.append((parsed, matched))

    return results


# ============================================================================
# JSON 导入导出
# ============================================================================

def export_recipes_to_json(
    recipes: List[Recipe],
    filepath: str,
    include_nutrition: bool = True
) -> bool:
    """
    将食谱列表导出为 JSON 文件

    Args:
        recipes: 食谱对象列表
        filepath: 输出文件路径
        include_nutrition: 是否包含营养成分计算结果

    Returns:
        是否成功
    """
    try:
        from models import NutritionCalculator

        output = {
            'version': '1.0',
            'export_time': str(Path(filepath).stat().st_mtime) if os.path.exists(filepath) else None,
            'recipe_count': len(recipes),
            'recipes': []
        }

        for recipe in recipes:
            recipe_data = recipe.to_dict()

            if include_nutrition:
                total = NutritionCalculator.calculate_from_recipe(recipe)
                recipe_data['nutrition_total'] = total.to_dict()
                macros = NutritionCalculator.analyze_macros(total)
                recipe_data['nutrition_macros'] = macros

            output['recipes'].append(recipe_data)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"导出失败: {e}")
        return False


def export_ingredients_to_json(
    ingredients: List[Ingredient],
    filepath: str
) -> bool:
    """
    将食材列表导出为 JSON 文件

    Args:
        ingredients: 食材对象列表
        filepath: 输出文件路径

    Returns:
        是否成功
    """
    try:
        output = {
            'version': '1.0',
            'ingredient_count': len(ingredients),
            'ingredients': [ing.to_dict() for ing in ingredients]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"导出失败: {e}")
        return False


def import_recipes_from_json_str(
    json_str: str,
    ingredient_map: Dict[str, Ingredient]
) -> List[Recipe]:
    """
    从 JSON 字符串导入食谱（Web 上传用）
    """
    recipes = []
    data = json.loads(json_str)
    for recipe_data in data.get('recipes', []):
        recipe = Recipe.from_dict(recipe_data, ingredient_map)
        recipes.append(recipe)
    return recipes


def import_ingredients_from_json_str(json_str: str) -> List[Ingredient]:
    """
    从 JSON 字符串导入食材（Web 上传用）
    """
    data = json.loads(json_str)
    return [Ingredient.from_dict(ing_data) for ing_data in data.get('ingredients', [])]


def import_recipes_from_json(
    filepath: str,
    ingredient_map: Dict[str, Ingredient]
) -> List[Recipe]:
    """
    从 JSON 文件导入食谱
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [Recipe.from_dict(rd, ingredient_map) for rd in data.get('recipes', [])]


def import_ingredients_from_json(filepath: str) -> Dict[str, Ingredient]:
    """
    从 JSON 文件导入食材
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    result = {}
    for ing_data in data.get('ingredients', []):
        ing = Ingredient.from_dict(ing_data)
        result[ing.name] = ing
    return result


# ============================================================================
# 营养成分格式化工具
# ============================================================================

def format_nutrition_summary(nutrition: NutritionInfo) -> str:
    """
    格式化营养成分为易读字符串

    Args:
        nutrition: 营养成分对象

    Returns:
        格式化的字符串
    """
    lines = [
        f"热量: {nutrition.calories:.1f} kcal",
        f"蛋白质: {nutrition.protein:.1f}g",
        f"脂肪: {nutrition.fat:.1f}g",
        f"碳水: {nutrition.carbs:.1f}g",
        f"纤维: {nutrition.fiber:.1f}g",
        "---",
        f"维生素A: {nutrition.vitamin_a:.1f} μg",
        f"维生素C: {nutrition.vitamin_c:.1f} mg",
        f"钙: {nutrition.calcium:.1f} mg",
        f"铁: {nutrition.iron:.1f} mg",
    ]
    return "\n".join(lines)


def nutrition_to_display_dict(nutrition: NutritionInfo) -> Dict[str, Any]:
    """
    将营养成分转换为前端展示用的字典

    Args:
        nutrition: 营养成分对象

    Returns:
        适合前端渲染的字典
    """
    return {
        'calories': round(nutrition.calories, 1),
        'protein': round(nutrition.protein, 1),
        'fat': round(nutrition.fat, 1),
        'carbs': round(nutrition.carbs, 1),
        'fiber': round(nutrition.fiber, 1),
        'vitamin_a': round(nutrition.vitamin_a, 1),
        'vitamin_c': round(nutrition.vitamin_c, 1),
        'calcium': round(nutrition.calcium, 1),
        'iron': round(nutrition.iron, 1),
    }


# ============================================================================
# 单位换算工具
# ============================================================================

# 中文数字转换（支持"半"等）
CN_NUM_MAP = {
    '零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '半': 0.5
}


def convert_cn_number(text: str) -> Optional[float]:
    """
    将中文数字转换为阿拉伯数字

    Args:
        text: 包含中文数字的字符串

    Returns:
        转换后的数值，未找到则返回 None
    """
    try:
        # 尝试直接转换为浮点数
        return float(text)
    except ValueError:
        pass

    # 简单中文数字处理
    result = 0
    for char, val in CN_NUM_MAP.items():
        if char in text:
            result = val
            break
    return result if result else None


def normalize_weight(amount: float, from_unit: str, to_unit: str = 'g') -> float:
    """
    重量单位换算

    Args:
        amount: 数量
        from_unit: 原始单位
        to_unit: 目标单位

    Returns:
        换算后的数值
    """
    # 先转换为克
    to_grams = {
        'g': 1.0, '克': 1.0,
        'kg': 1000.0, '千克': 1000.0, '公斤': 1000.0,
        '斤': 500.0, '两': 50.0,
    }

    from_factor = to_grams.get(from_unit, 1.0)
    to_factor = to_grams.get(to_unit, 1.0)

    grams = amount * from_factor
    return grams / to_factor


# ============================================================================
# 数据验证工具
# ============================================================================

def validate_recipe_data(recipe_data: Dict) -> Tuple[bool, List[str]]:
    """
    验证食谱数据的完整性

    Args:
        recipe_data: 食谱字典数据

    Returns:
        (是否有效, 错误信息列表)
    """
    errors = []

    # 必填字段
    if not recipe_data.get('name'):
        errors.append("食谱名称不能为空")

    if not recipe_data.get('ingredients'):
        errors.append("食谱至少需要一种食材")

    # 时间验证
    prep_time = recipe_data.get('prep_time', 0)
    cook_time = recipe_data.get('cook_time', 0)
    if prep_time < 0 or cook_time < 0:
        errors.append("时间不能为负数")

    # 食材数据验证
    for i, ing in enumerate(recipe_data.get('ingredients', [])):
        if not ing.get('ingredient_name'):
            errors.append(f"第{i+1}种食材缺少名称")
        if ing.get('amount', 0) <= 0:
            errors.append(f"第{i+1}种食材的数量必须大于0")

    return (len(errors) == 0, errors)


def validate_ingredient_data(ingredient_data: Dict) -> Tuple[bool, List[str]]:
    """
    验证食材数据的完整性

    Args:
        ingredient_data: 食材字典数据

    Returns:
        (是否有效, 错误信息列表)
    """
    errors = []

    if not ingredient_data.get('name'):
        errors.append("食材名称不能为空")

    nutrition = ingredient_data.get('nutrition_per_100g', {})

    # 营养成分范围检查（防止异常数据）
    if nutrition.get('calories', 0) < 0:
        errors.append("热量不能为负数")
    if nutrition.get('protein', 0) < 0:
        errors.append("蛋白质含量不能为负数")

    return (len(errors) == 0, errors)


# ============================================================================
# 主程序入口（用于测试）
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("阶段二测试：正则解析与 JSON 导入导出")
    print("=" * 60)

    # 测试正则解析
    print("\n[1] 测试正则解析...")
    test_inputs = [
        "西红柿200g, 鸡蛋2个",
        "鸡胸肉150g 西兰花100g",
        "大米100g, 鸡蛋 3 个",
        "豆腐200g",
    ]

    for inp in test_inputs:
        parsed = parse_ingredient_input(inp)
        print(f"    输入: '{inp}'")
        print(f"    解析: {[str(p) for p in parsed]}")

    # 测试模糊匹配
    print("\n[2] 测试模糊匹配...")
    from models import create_sample_ingredients
    ingredient_map = create_sample_ingredients()
    available = list(ingredient_map.keys())

    test_names = ['西红柿', '番茄', '鸡胸', '鸡蛋']
    for name in test_names:
        matched = fuzzy_match_ingredient(name, available)
        print(f"    '{name}' -> {matched}")

    # 测试 JSON 导出
    print("\n[3] 测试 JSON 导出...")
    from models import create_sample_recipes
    from pathlib import Path

    recipes = create_sample_recipes(ingredient_map)
    export_path = Path(__file__).parent / 'data' / 'sample_recipes.json'
    export_path.parent.mkdir(exist_ok=True)

    success = export_recipes_to_json(recipes, str(export_path))
    print(f"    导出{'成功' if success else '失败'}: {export_path}")

    # 测试 JSON 导入
    print("\n[4] 测试 JSON 导入...")
    imported = import_recipes_from_json(str(export_path), ingredient_map)
    print(f"    成功导入 {len(imported)} 个食谱")
    for r in imported:
        print(f"    - {r.name}")

    # 测试食材数据验证
    print("\n[5] 测试数据验证...")
    valid, errors = validate_recipe_data({
        'name': '测试食谱',
        'ingredients': [{'ingredient_name': '西红柿', 'amount': 100}]
    })
    print(f"    有效数据验证: {'通过' if valid else '失败'}")

    invalid, errors = validate_recipe_data({
        'name': '',
        'ingredients': []
    })
    print(f"    无效数据验证: {'正确拒绝' if not invalid else '错误通过'}")

    print("\n" + "=" * 60)
    print("阶段二测试完成！")
    print("=" * 60)
