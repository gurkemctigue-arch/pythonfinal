"""
阶段五：Flask Web 应用入口

路由设计：
    /                   首页 - 营养看板
    /recipes            食谱库
    /recipes/<id>       食谱详情
    /analyzer           食材输入分析
    /recommend          智能推荐
    /plan               膳食计划
    /api/recipes        REST API: 食谱列表
    /api/analyze        REST API: 食材分析
    /api/recommend      REST API: 推荐
    /api/plan           REST API: 膳食计划
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.exceptions import HTTPException

from models import (
    Ingredient, Recipe, NutritionInfo, NutritionCalculator,
    create_sample_ingredients, create_sample_recipes
)
from database import (
    init_database, seed_sample_data, get_all_recipes, get_all_ingredients,
    get_recipe_by_id, get_recipe_by_name, get_recipe_id_by_name,
    search_recipes, get_recipes_by_tag, get_recipes_by_difficulty,
    get_recipes_by_cuisine, get_ingredient_by_name,
    insert_ingredient, insert_recipe, delete_ingredient, DB_PATH
)
from recommender import (
    BasicRecommender, SmartRecommender, MealPlanGenerator,
    RecipeMatch, WeeklyPlan
)
from utils import (
    parse_ingredient_input, fuzzy_match_ingredient, match_parsed_to_inventory,
    export_recipes_to_json, export_ingredients_to_json,
    import_recipes_from_json, import_ingredients_from_json,
    import_recipes_from_json_str, import_ingredients_from_json_str,
    nutrition_to_display_dict, validate_recipe_data, validate_ingredient_data
)
from visualizer import (
    NutritionDashboard, plot_nutrition_radar, plot_calorie_pie,
    plot_weekly_calorie_trend, plot_macro_distribution,
    plot_multi_recipe_radar, _check_matplotlib
)


# ============================================================================
# Flask 应用初始化
# ============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'recipe-nutrition-secret-key-2024'
app.config['JSON_AS_ASCII'] = False  # 支持中文 JSON

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
STATIC_DIR = BASE_DIR / 'static'
TEMPLATES_DIR = BASE_DIR / 'templates'

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)


# ============================================================================
# 应用启动时的初始化
# ============================================================================

def init_app():
    """初始化应用：创建数据库和示例数据"""
    if not DB_PATH.exists():
        result = seed_sample_data(str(DB_PATH))
        print(f"首次启动：已导入 {result['ingredients']} 种食材, {result['recipes']} 个食谱")
    else:
        # 检查是否需要重新填充
        from database import get_recipe_count
        if get_recipe_count(str(DB_PATH)) == 0:
            result = seed_sample_data(str(DB_PATH))
            print(f"数据为空：已导入 {result['ingredients']} 种食材, {result['recipes']} 个食谱")


init_app()


# ============================================================================
# 辅助函数
# ============================================================================

def load_recipes():
    """加载所有食谱"""
    return get_all_recipes(str(DB_PATH))


def load_ingredients():
    """加载所有食材"""
    return get_all_ingredients(str(DB_PATH))


def recipe_to_display(recipe: Recipe, db_id: int = None) -> Dict[str, Any]:
    """将 Recipe 对象转换为前端展示用的字典"""
    # 如果没有传入 db_id，尝试从 recipe._db_id 获取，或查询数据库
    if db_id is None:
        db_id = getattr(recipe, '_db_id', None)
    if db_id is None:
        db_id = get_recipe_id_by_name(recipe.name, str(DB_PATH))

    nutrition = NutritionCalculator.calculate_from_recipe(recipe)
    macros = NutritionCalculator.analyze_macros(nutrition)

    return {
        'id': db_id if db_id is not None else id(recipe),
        'name': recipe.name,
        'cuisine': recipe.cuisine,
        'difficulty': recipe.difficulty,
        'prep_time': recipe.prep_time,
        'cook_time': recipe.cook_time,
        'total_time': recipe.total_time,
        'tags': recipe.tags,
        'description': recipe.description,
        'steps': recipe.steps,
        'ingredients': [
            {
                'name': ri.ingredient.name,
                'amount': ri.amount,
                'unit': ri.unit,
                'calories': ri.ingredient.nutrition_per_100g.calories * ri.amount / 100
            }
            for ri in recipe.ingredients
        ],
        'nutrition': nutrition_to_display_dict(nutrition),
        'macros': {k: round(v, 1) for k, v in macros.items()},
        'calories': round(nutrition.calories, 1),
        'protein': round(nutrition.protein, 1),
        'fat': round(nutrition.fat, 1),
        'carbs': round(nutrition.carbs, 1),
    }


# ============================================================================
# 页面路由
# ============================================================================

@app.route('/')
def index():
    """
    首页 - 营养看板
    展示所有食谱的营养对比图表
    """
    recipes = load_recipes()

    # 生成每周计划
    planner = MealPlanGenerator(recipes)
    weekly_plan = planner.generate_weekly_plan(days=7)

    # 生成图表
    dashboard = NutritionDashboard(recipes, weekly_plan)
    charts = dashboard.generate_all(save_to_disk=True)

    # 食谱列表（供前端卡片展示）
    recipe_list = [recipe_to_display(r, getattr(r, '_db_id', None)) for r in recipes]

    # 统计摘要
    ingredients = load_ingredients()

    # 计算平均热量
    if recipes:
        avg_cal = sum(
            NutritionCalculator.calculate_from_recipe(r).calories
            for r in recipes
        ) / len(recipes)
    else:
        avg_cal = 0

    # 标签统计
    tag_counts: Dict[str, int] = {}
    for r in recipes:
        for tag in r.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # 热量柱状图（全部食谱，供前端下拉切换）
    all_recipes_for_bar = [
        {
            'name': r.name,
            'protein': round(NutritionCalculator.calculate_from_recipe(r).protein, 1),
            'fat': round(NutritionCalculator.calculate_from_recipe(r).fat, 1),
            'carbs': round(NutritionCalculator.calculate_from_recipe(r).carbs, 1),
        }
        for r in recipes
    ]
    # 默认取热量最高的8道作为初始柱状图
    top_recipes = sorted(all_recipes_for_bar, key=lambda r: r['protein'] * 4 + r['fat'] * 9 + r['carbs'] * 4, reverse=True)[:8]

    calorie_bar_data = {
        'labels': [r['name'] for r in top_recipes],
        'protein': [r['protein'] for r in top_recipes],
        'fat': [r['fat'] for r in top_recipes],
        'carbs': [r['carbs'] for r in top_recipes],
        'all': all_recipes_for_bar,  # 前端切换时使用完整列表
    }

    first_nutrition = NutritionCalculator.calculate_from_recipe(recipes[0]) if recipes else None
    radar_data = None
    if first_nutrition:
        radar_data = {
            'recipe': recipes[0].name,
            'labels': ['蛋白质', '脂肪', '碳水', '纤维', '维生素A', '维生素C'],
            'values': [
                round(min(first_nutrition.protein / 50 * 100, 100), 1),
                round(min(first_nutrition.fat / 30 * 100, 100), 1),
                round(min(first_nutrition.carbs / 80 * 100, 100), 1),
                round(min(first_nutrition.fiber / 10 * 100, 100), 1),
                round(min(first_nutrition.vitamin_a / 900 * 100, 100), 1),
                round(min(first_nutrition.vitamin_c / 90 * 100, 100), 1),
            ],
        }

    # 多食谱雷达对比（默认取热量最高的4道，可供前端动态选择）
    multi_default = top_recipes[:4]
    multi_radar_data = {
        'labels': ['蛋白质', '脂肪', '碳水', '纤维', '维生素A', '维生素C'],
        'recipes': [
            {
                'name': r['name'],
                'calories': round(r['protein'] * 4 + r['fat'] * 9 + r['carbs'] * 4, 1),
                'values': [
                    round(min(r['protein'] / 50 * 100, 100), 1),
                    round(min(r['fat'] / 30 * 100, 100), 1),
                    round(min(r['carbs'] / 80 * 100, 100), 1),
                    50, 50, 50,
                ],
            }
            for r in multi_default
        ],
        'all_recipes': all_recipes_for_bar,  # 前端动态选择时使用
    }

    trend_data = {
        'labels': [f'第{i+1}天' for i in range(len(weekly_plan.days))],
        'calories': [round(day.total_calories, 1) for day in weekly_plan.days],
        'protein': [round(day.nutrition.protein, 1) for day in weekly_plan.days],
        'fat': [round(day.nutrition.fat, 1) for day in weekly_plan.days],
        'carbs': [round(day.nutrition.carbs, 1) for day in weekly_plan.days],
    }

    total_p = sum(day.nutrition.protein for day in weekly_plan.days)
    total_f = sum(day.nutrition.fat for day in weekly_plan.days)
    total_c = sum(day.nutrition.carbs for day in weekly_plan.days)
    macro_cal = total_p * 4 + total_f * 9 + total_c * 4
    macro_dist_data = {
        'labels': ['蛋白质', '脂肪', '碳水'],
        'values': [round(total_p, 1), round(total_f, 1), round(total_c, 1)],
        'percentages': [
            round(total_p * 4 / macro_cal * 100, 1) if macro_cal > 0 else 0,
            round(total_f * 9 / macro_cal * 100, 1) if macro_cal > 0 else 0,
            round(total_c * 4 / macro_cal * 100, 1) if macro_cal > 0 else 0,
        ],
    }

    chart_data = {
        'calorie_bar': calorie_bar_data,
        'radar': radar_data,
        'multi_radar': multi_radar_data,
        'trend': trend_data,
        'macro_dist': macro_dist_data,
        'all_recipes': all_recipes_for_bar,  # 供前端各图表通用
    }

    return render_template(
        'index.html',
        recipes=recipe_list,
        weekly_plan=weekly_plan.to_dict(),
        charts=charts,
        chart_data=chart_data,
        stats={
            'recipe_count': len(recipes),
            'ingredient_count': len(ingredients),
            'avg_calories': round(avg_cal, 1),
            'tag_counts': dict(sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
        },
        matplotlib_available=_check_matplotlib()
    )


@app.route('/recipes')
def recipes_page():
    """食谱库页面（支持多条件筛选）"""
    all_recipes = load_recipes()
    recipes = all_recipes

    # 读取筛选参数
    keyword = request.args.get('q', '').strip()
    tag_filter = request.args.get('tag', '').strip()
    cuisine_filter = request.args.get('cuisine', '').strip()
    difficulty_filter = request.args.get('difficulty', '').strip()

    # 应用组合筛选：每个条件都基于当前结果继续过滤
    if keyword:
        keyword_lower = keyword.lower()
        recipes = [
            r for r in recipes
            if keyword_lower in r.name.lower()
            or keyword_lower in r.description.lower()
            or any(keyword_lower in tag.lower() for tag in r.tags)
        ]
    if tag_filter:
        recipes = [r for r in recipes if tag_filter in r.tags]
    if cuisine_filter:
        recipes = [r for r in recipes if r.cuisine == cuisine_filter]
    if difficulty_filter:
        recipes = [r for r in recipes if r.difficulty == difficulty_filter]

    recipe_list = [recipe_to_display(r, getattr(r, '_db_id', None)) for r in recipes]

    # 所有标签（从全量数据统计，用于下拉选项）
    all_tags = set()
    for r in all_recipes:
        all_tags.update(r.tags)
    all_cuisines = sorted(set(r.cuisine for r in all_recipes))
    difficulties = ['简单', '中等', '困难']

    return render_template(
        'recipes.html',
        recipes=recipe_list,
        all_tags=sorted(all_tags),
        all_cuisines=all_cuisines,
        difficulties=difficulties,
    )


@app.route('/recipes/<name>')
def recipe_detail(name):
    """食谱详情页（支持 ID 或名称访问）"""
    import urllib.parse
    decoded_name = urllib.parse.unquote(name)

    # 优先尝试按 ID 查询（整数时）
    recipe = None
    try:
        recipe_id = int(name)
        recipe = get_recipe_by_id(recipe_id, str(DB_PATH))
    except (ValueError, TypeError):
        pass

    # 再尝试按名称查询
    if not recipe:
        recipe = get_recipe_by_name(decoded_name, str(DB_PATH))

    if not recipe:
        return render_template('error.html', message=f"未找到食谱「{decoded_name}」"), 404

    db_id = getattr(recipe, '_db_id', None) or get_recipe_id_by_name(recipe.name, str(DB_PATH))
    recipe_data = recipe_to_display(recipe, db_id)

    nutrition = NutritionCalculator.calculate_from_recipe(recipe)
    macros = NutritionCalculator.analyze_macros(nutrition)

    # 雷达图数据（Chart.js 用）
    radar_chart_data = {
        'labels': ['蛋白质', '脂肪', '碳水', '纤维', '维生素A', '维生素C'],
        'values': [
            round(nutrition.protein / 50 * 100, 1),
            round(nutrition.fat / 30 * 100, 1),
            round(nutrition.carbs / 80 * 100, 1),
            round(min(nutrition.fiber / 10 * 100, 100), 1),
            round(min(nutrition.vitamin_a / 900 * 100, 100), 1),
            round(min(nutrition.vitamin_c / 90 * 100, 100), 1),
        ],
        'raw': nutrition_to_display_dict(nutrition),
    }

    # 饼图数据（Chart.js 用）
    p_cal = nutrition.protein * 4
    f_cal = nutrition.fat * 9
    c_cal = nutrition.carbs * 4
    total_cal = p_cal + f_cal + c_cal
    pie_chart_data = {
        'labels': ['蛋白质', '脂肪', '碳水'],
        'values': [
            round(p_cal, 1) if total_cal > 0 else 0,
            round(f_cal, 1) if total_cal > 0 else 0,
            round(c_cal, 1) if total_cal > 0 else 0,
        ],
        'percentages': [
            round(p_cal / total_cal * 100, 1) if total_cal > 0 else 0,
            round(f_cal / total_cal * 100, 1) if total_cal > 0 else 0,
            round(c_cal / total_cal * 100, 1) if total_cal > 0 else 0,
        ],
    }

    return render_template(
        'recipe_detail.html',
        recipe=recipe_data,
        radar_chart=None,
        radar_chart_data=radar_chart_data,
        pie_chart=None,
        pie_chart_data=pie_chart_data,
        macros=macros,
    )


# ============================================================================
# 食材管理
# ============================================================================

@app.route('/ingredients')
def ingredients_page():
    """食材库管理页面"""
    ingredients = get_all_ingredients(str(DB_PATH))

    # 按分类分组
    categories = {}
    for ing in ingredients:
        cat = ing.category or '其他'
        if cat not in categories:
            categories[cat] = []
        n = ing.nutrition_per_100g
        categories[cat].append({
            'id': getattr(ing, '_db_id', None),
            'name': ing.name,
            'category': cat,
            'calories': round(n.calories, 1),
            'protein': round(n.protein, 1),
            'fat': round(n.fat, 1),
            'carbs': round(n.carbs, 1),
        })

    return render_template(
        'ingredients.html',
        categories=categories,
        total_count=len(ingredients),
    )


@app.route('/ingredients/add', methods=['GET', 'POST'])
def ingredient_add():
    """新增食材"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '蔬菜').strip()
        calories = float(request.form.get('calories', 0) or 0)
        protein = float(request.form.get('protein', 0) or 0)
        fat = float(request.form.get('fat', 0) or 0)
        carbs = float(request.form.get('carbs', 0) or 0)
        fiber = float(request.form.get('fiber', 0) or 0)
        vitamin_a = float(request.form.get('vitamin_a', 0) or 0)
        vitamin_c = float(request.form.get('vitamin_c', 0) or 0)
        calcium = float(request.form.get('calcium', 0) or 0)
        iron = float(request.form.get('iron', 0) or 0)

        if not name:
            return render_template('ingredient_add.html', error="食材名称不能为空")

        nutrition = NutritionInfo(
            calories=calories, protein=protein, fat=fat, carbs=carbs,
            fiber=fiber, vitamin_a=vitamin_a, vitamin_c=vitamin_c,
            calcium=calcium, iron=iron
        )
        ingredient = Ingredient(name=name, nutrition=nutrition, category=category)
        db_id = insert_ingredient(ingredient, str(DB_PATH))

        return redirect(url_for('ingredients_page'))

    return render_template('ingredient_add.html', error=None)


@app.route('/ingredients/delete/<int:ingredient_id>', methods=['POST'])
def ingredient_delete(ingredient_id):
    """删除食材"""
    delete_ingredient(ingredient_id, str(DB_PATH))
    return redirect(url_for('ingredients_page'))


# ============================================================================
# 食谱管理
# ============================================================================

@app.route('/recipes/add', methods=['GET', 'POST'])
def recipe_add():
    """新增食谱"""
    all_ingredients = get_all_ingredients(str(DB_PATH))
    ing_options = [(ing.name, ing.name) for ing in all_ingredients]
    cuisine_options = ['家常菜', '川菜', '粤菜', '湘菜', '鲁菜', '西餐', '其他']
    difficulty_options = ['简单', '中等', '困难']

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        cuisine = request.form.get('cuisine', '家常菜')
        difficulty = request.form.get('difficulty', '简单')
        prep_time = int(request.form.get('prep_time', 10) or 10)
        cook_time = int(request.form.get('cook_time', 20) or 20)
        tags_raw = request.form.get('tags', '')
        description = request.form.get('description', '').strip()
        steps_raw = request.form.get('steps', '').strip()

        if not name:
            return render_template('recipe_add.html',
                error="食谱名称不能为空",
                cuisine_options=cuisine_options,
                difficulty_options=difficulty_options,
                ing_options=ing_options)

        tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
        steps = [s.strip() for s in steps_raw.split('\n') if s.strip()]

        recipe = Recipe(
            name=name, cuisine=cuisine, difficulty=difficulty,
            prep_time=prep_time, cook_time=cook_time,
            tags=tags, description=description, steps=steps
        )

        # 食材项
        ing_names = request.form.getlist('ing_name')
        ing_amounts = request.form.getlist('ing_amount')
        ing_units = request.form.getlist('ing_unit')
        ing_map = {ing.name: ing for ing in all_ingredients}

        for ing_name, amount, unit in zip(ing_names, ing_amounts, ing_units):
            ing_name = ing_name.strip()
            amount_str = amount.strip()
            unit = unit.strip()
            if ing_name and amount_str:
                try:
                    amount_val = float(amount_str)
                    if ing_name in ing_map:
                        recipe.add_ingredient(ing_map[ing_name], amount_val, unit)
                except ValueError:
                    pass

        insert_recipe(recipe, str(DB_PATH))
        return redirect(url_for('recipes_page'))

    return render_template('recipe_add.html',
        error=None,
        cuisine_options=cuisine_options,
        difficulty_options=difficulty_options,
        ing_options=ing_options)


@app.route('/analyzer', methods=['GET', 'POST'])
def analyzer():
    """
    食材输入分析页面
    GET: 显示分析表单
    POST: 处理用户输入，返回分析结果
    """
    if request.method == 'POST':
        input_text = request.form.get('ingredients', '').strip()
        if not input_text:
            return render_template('analyzer.html', error="请输入食材列表")

        ingredient_map = {ing.name: ing for ing in load_ingredients()}

        # 解析用户输入
        parsed_list = parse_ingredient_input(input_text)
        matched = match_parsed_to_inventory(parsed_list, ingredient_map)

        # 计算总营养
        total_nutrition = NutritionInfo()
        matched_items = []

        for parsed, ingredient in matched:
            if ingredient:
                factor = parsed.amount / 100
                n = ingredient.nutrition_per_100g
                total_nutrition = total_nutrition + NutritionInfo(
                    calories=n.calories * factor,
                    protein=n.protein * factor,
                    fat=n.fat * factor,
                    carbs=n.carbs * factor,
                    fiber=n.fiber * factor,
                    vitamin_a=n.vitamin_a * factor,
                    vitamin_c=n.vitamin_c * factor,
                    calcium=n.calcium * factor,
                    iron=n.iron * factor,
                )
                matched_items.append({
                    'name': parsed.name,
                    'amount': parsed.amount,
                    'unit': parsed.unit,
                    'matched_name': ingredient.name,
                    'found': True,
                    'calories': round(n.calories * factor, 1),
                })
            else:
                matched_items.append({
                    'name': parsed.name,
                    'amount': parsed.amount,
                    'unit': parsed.unit,
                    'matched_name': None,
                    'found': False,
                    'calories': 0,
                })

        # 生成雷达图
        radar_base64 = ""
        if total_nutrition.calories > 0:
            radar_base64 = plot_nutrition_radar(
                total_nutrition,
                title="食材营养成分汇总"
            )

        macros = NutritionCalculator.analyze_macros(total_nutrition)

        # 雷达图数据（Chart.js 用）
        radar_data = None
        if total_nutrition.calories > 0:
            radar_data = {
                'labels': ['蛋白质', '脂肪', '碳水', '纤维', '维生素A', '维生素C'],
                'values': [
                    round(total_nutrition.protein / 50 * 100, 1),
                    round(total_nutrition.fat / 30 * 100, 1),
                    round(total_nutrition.carbs / 80 * 100, 1),
                    round(min(total_nutrition.fiber / 10 * 100, 100), 1),
                    round(min(total_nutrition.vitamin_a / 900 * 100, 100), 1),
                    round(min(total_nutrition.vitamin_c / 90 * 100, 100), 1),
                ],
                'raw': nutrition_to_display_dict(total_nutrition),
            }

        return render_template(
            'analyzer.html',
            input_text=input_text,
            matched_items=matched_items,
            total=nutrition_to_display_dict(total_nutrition),
            macros={k: round(v, 1) for k, v in macros.items()},
            radar_chart=None,
            radar_chart_data=radar_data,
            matplotlib_available=_check_matplotlib()
        )

    return render_template('analyzer.html', radar_chart_data=None)


@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    """
    智能推荐页面
    """
    recipes = load_recipes()

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'by_inventory':
            # 基于库存推荐
            inventory_text = request.form.get('inventory', '').strip()
            if inventory_text:
                # 解析用户已有的食材
                parsed_list = parse_ingredient_input(inventory_text)
                ingredient_map = {ing.name: ing for ing in load_ingredients()}
                user_ingredients = [
                    ing.name
                    for parsed, ing in match_parsed_to_inventory(parsed_list, ingredient_map)
                    if ing
                ]

                if user_ingredients:
                    recommender = SmartRecommender(recipes)
                    matches = recommender.recommend_by_inventory(user_ingredients, max_missing=3)

                    match_results = []
                    for m in matches[:10]:
                        match_results.append({
                            'recipe': recipe_to_display(m.recipe),
                            'match_score': round(m.match_score, 1),
                            'matched_ingredients': m.matched_ingredients,
                            'missing_ingredients': m.missing_ingredients,
                            'reason': m.reason,
                            'nutrition': nutrition_to_display_dict(m.nutrition),
                        })

                    return render_template(
                        'recommend.html',
                        action='by_inventory',
                        user_ingredients=user_ingredients,
                        match_results=match_results,
                        has_results=len(match_results) > 0,
                        recipes=[recipe_to_display(r) for r in recipes],
                    )

        elif action == 'by_tags':
            # 基于标签推荐
            tags_raw = request.form.get('tags', '')
            selected_tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
            min_cal = float(request.form.get('min_cal', 0) or 0)
            max_cal = float(request.form.get('max_cal', 5000) or 5000)
            max_time = int(request.form.get('max_time', 999) or 999)
            difficulty = request.form.get('difficulty', '')

            recommender = BasicRecommender(recipes)
            filtered = recommender.combined_filter(
                tags=selected_tags if selected_tags else None,
                min_cal=min_cal,
                max_cal=max_cal,
                max_time=max_time if max_time < 999 else None,
                difficulty=difficulty if difficulty else None,
            )

            ranked = recommender.rank_by_nutrition_score(filtered)
            results = []
            for r, score in ranked[:12]:
                rdata = recipe_to_display(r)
                rdata['nutrition_score'] = round(score, 1)
                results.append(rdata)

            all_tags = set()
            for r in recipes:
                all_tags.update(r.tags)

            return render_template(
                'recommend.html',
                action='by_tags',
                selected_tags=selected_tags,
                results=results,
                all_tags=sorted(all_tags),
                has_results=len(results) > 0,
                recipes=[recipe_to_display(r) for r in recipes],
            )

    # GET 请求：显示推荐页面
    all_tags = set()
    for r in recipes:
        all_tags.update(r.tags)

    return render_template(
        'recommend.html',
        action=None,
        all_tags=sorted(all_tags),
        recipes=[recipe_to_display(r) for r in recipes],
        has_results=False,
    )


@app.route('/plan')
def plan():
    """
    膳食计划页面（支持自定义每日目标热量和天数）
    """
    recipes = load_recipes()

    if not recipes:
        return render_template('plan.html', error="食谱库为空，请先添加食谱", weekly_plan=None)

    # 读取用户自定义参数
    try:
        days = int(request.args.get('days', 7))
        days = max(1, min(days, 14))  # 限制 1-14 天
    except (ValueError, TypeError):
        days = 7

    try:
        target_cal = request.args.get('target_cal', '')
        target_calories = float(target_cal) if target_cal else None
        target_calories = max(800, min(target_calories, 4000)) if target_calories else None
    except (ValueError, TypeError):
        target_calories = None  # None = 使用默认随机范围

    planner = MealPlanGenerator(recipes)
    weekly_plan = planner.generate_weekly_plan(days=days, target_calories=target_calories)

    # 生成趋势图
    trend_chart = plot_weekly_calorie_trend(weekly_plan)
    macro_chart = plot_macro_distribution(weekly_plan)

    # 构建每日计划数据
    day_data = []
    meal_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日',
                  '第8天', '第9天', '第10天', '第11天', '第12天', '第13天', '第14天']

    for i, day in enumerate(weekly_plan.days):
        day_data.append({
            'label': meal_names[i] if i < len(meal_names) else f"第{i+1}天",
            'breakfast': recipe_to_display(day.breakfast) if day.breakfast else None,
            'lunch': recipe_to_display(day.lunch) if day.lunch else None,
            'dinner': recipe_to_display(day.dinner) if day.dinner else None,
            'calories': round(day.total_calories, 1),
            'macros': {k: round(v, 1) for k, v in day.macros.items()},
        })

    return render_template(
        'plan.html',
        weekly_plan=weekly_plan.to_dict(),
        day_data=day_data,
        trend_chart=None,
        trend_chart_data={
            'labels': [f'第{i+1}天' for i in range(len(weekly_plan.days))],
            'calories': [round(day.total_calories, 1) for day in weekly_plan.days],
            'protein': [round(day.nutrition.protein, 1) for day in weekly_plan.days],
            'fat': [round(day.nutrition.fat, 1) for day in weekly_plan.days],
            'carbs': [round(day.nutrition.carbs, 1) for day in weekly_plan.days],
        },
        macro_chart=None,
        macro_chart_data={
            'labels': ['蛋白质', '脂肪', '碳水'],
            'protein': [round(day.nutrition.protein, 1) for day in weekly_plan.days],
            'fat': [round(day.nutrition.fat, 1) for day in weekly_plan.days],
            'carbs': [round(day.nutrition.carbs, 1) for day in weekly_plan.days],
        },
        matplotlib_available=_check_matplotlib(),
        current_days=days,
        current_target=target_calories,
    )


# ============================================================================
# 图表 API（返回 JSON，供 Chart.js 渲染动态图表）
# ============================================================================

@app.route('/api/charts')
def api_charts():
    """
    返回首页所有图表的原始数据（供 Chart.js 渲染动态图表）
    """
    recipes = load_recipes()
    planner = MealPlanGenerator(recipes)
    weekly_plan = planner.generate_weekly_plan(days=7)

    # 全部食谱（供前端动态选择）
    all_for_bar = [
        {
            'name': r.name,
            'protein': round(NutritionCalculator.calculate_from_recipe(r).protein, 1),
            'fat': round(NutritionCalculator.calculate_from_recipe(r).fat, 1),
            'carbs': round(NutritionCalculator.calculate_from_recipe(r).carbs, 1),
        }
        for r in recipes
    ]
    top_recipes = sorted(all_for_bar, key=lambda r: r['protein']*4 + r['fat']*9 + r['carbs']*4, reverse=True)[:8]

    calorie_bar_data = {
        'labels': [r['name'] for r in top_recipes],
        'protein': [r['protein'] for r in top_recipes],
        'fat': [r['fat'] for r in top_recipes],
        'carbs': [r['carbs'] for r in top_recipes],
        'all': all_for_bar,
    }

    # 营养雷达图数据（第一个食谱）
    if recipes:
        first_nutrition = NutritionCalculator.calculate_from_recipe(recipes[0])
        radar_data = {
            'recipe': recipes[0].name,
            'labels': ['蛋白质', '脂肪', '碳水', '纤维', '维生素A', '维生素C'],
            'values': [
                round(first_nutrition.protein / 50 * 100, 1),
                round(first_nutrition.fat / 30 * 100, 1),
                round(first_nutrition.carbs / 80 * 100, 1),
                round(min(first_nutrition.fiber / 10 * 100, 100), 1),
                round(min(first_nutrition.vitamin_a / 900 * 100, 100), 1),
                round(min(first_nutrition.vitamin_c / 90 * 100, 100), 1),
            ],
            'raw': {
                'protein': round(first_nutrition.protein, 1),
                'fat': round(first_nutrition.fat, 1),
                'carbs': round(first_nutrition.carbs, 1),
                'fiber': round(first_nutrition.fiber, 1),
                'vitamin_a': round(first_nutrition.vitamin_a, 1),
                'vitamin_c': round(first_nutrition.vitamin_c, 1),
            }
        }
    else:
        radar_data = None

    # 多食谱雷达对比（默认热量最高的4道）
    multi_default = top_recipes[:4]
    multi_radar_data = {
        'labels': ['蛋白质', '脂肪', '碳水', '纤维', '维生素A', '维生素C'],
        'recipes': [
            {
                'name': r['name'],
                'calories': round(r['protein']*4 + r['fat']*9 + r['carbs']*4, 1),
                'values': [
                    round(r['protein'] / 50 * 100, 1),
                    round(r['fat'] / 30 * 100, 1),
                    round(r['carbs'] / 80 * 100, 1),
                    50, 50, 50,
                ],
            }
            for r in multi_default
        ],
        'all_recipes': all_for_bar,
    }

    # 每周热量趋势
    trend_data = {
        'labels': [f'第{i+1}天' for i in range(len(weekly_plan.days))],
        'calories': [round(day.total_calories, 1) for day in weekly_plan.days],
        'protein': [round(day.nutrition.protein, 1) for day in weekly_plan.days],
        'fat': [round(day.nutrition.fat, 1) for day in weekly_plan.days],
        'carbs': [round(day.nutrition.carbs, 1) for day in weekly_plan.days],
    }

    # 宏量营养素分布（每周总量）
    total_p = sum(day.nutrition.protein for day in weekly_plan.days)
    total_f = sum(day.nutrition.fat for day in weekly_plan.days)
    total_c = sum(day.nutrition.carbs for day in weekly_plan.days)
    macro_cal = total_p * 4 + total_f * 9 + total_c * 4
    pct_p = round(total_p * 4 / macro_cal * 100, 1) if macro_cal > 0 else 0
    pct_f = round(total_f * 9 / macro_cal * 100, 1) if macro_cal > 0 else 0
    pct_c = round(total_c * 4 / macro_cal * 100, 1) if macro_cal > 0 else 0
    macro_dist_data = {
        'labels': ['蛋白质', '脂肪', '碳水'],
        'values': [round(total_p, 1), round(total_f, 1), round(total_c, 1)],
        'percentages': [pct_p, pct_f, pct_c],
    }

    return jsonify({
        'success': True,
        'calorie_bar': calorie_bar_data,
        'radar': radar_data,
        'multi_radar': multi_radar_data,
        'trend': trend_data,
        'macro_dist': macro_dist_data,
        'all_recipes': all_for_bar,
    })


@app.route('/api/charts/refresh', methods=['POST'])
def api_charts_refresh():
    """
    根据新的膳食计划参数刷新趋势图和宏量营养素图
    """
    data = request.get_json() or {}
    days = data.get('days', 7)
    target_calories = data.get('target_calories')

    recipes = load_recipes()
    planner = MealPlanGenerator(recipes)
    weekly_plan = planner.generate_weekly_plan(days=days, target_calories=target_calories)

    trend_data = {
        'labels': [f'第{i+1}天' for i in range(len(weekly_plan.days))],
        'calories': [round(day.total_calories, 1) for day in weekly_plan.days],
        'protein': [round(day.nutrition.protein, 1) for day in weekly_plan.days],
        'fat': [round(day.nutrition.fat, 1) for day in weekly_plan.days],
        'carbs': [round(day.nutrition.carbs, 1) for day in weekly_plan.days],
    }

    total_p = sum(day.nutrition.protein for day in weekly_plan.days)
    total_f = sum(day.nutrition.fat for day in weekly_plan.days)
    total_c = sum(day.nutrition.carbs for day in weekly_plan.days)
    macro_cal = total_p * 4 + total_f * 9 + total_c * 4
    macro_dist_data = {
        'labels': ['蛋白质', '脂肪', '碳水'],
        'values': [round(total_p, 1), round(total_f, 1), round(total_c, 1)],
        'percentages': [
            round(total_p * 4 / macro_cal * 100, 1) if macro_cal > 0 else 0,
            round(total_f * 9 / macro_cal * 100, 1) if macro_cal > 0 else 0,
            round(total_c * 4 / macro_cal * 100, 1) if macro_cal > 0 else 0,
        ],
    }

    return jsonify({
        'success': True,
        'trend': trend_data,
        'macro_dist': macro_dist_data,
    })


@app.route('/api/charts/recipe/<int:recipe_id>')
def api_recipe_chart(recipe_id):
    """返回指定食谱的雷达图数据"""
    recipe = get_recipe_by_id(recipe_id, str(DB_PATH))
    if not recipe:
        return jsonify({'success': False, 'error': '食谱未找到'}), 404

    n = NutritionCalculator.calculate_from_recipe(recipe)
    macros = NutritionCalculator.analyze_macros(n)
    return jsonify({
        'success': True,
        'recipe': recipe_to_display(recipe, recipe_id),
        'nutrition': nutrition_to_display_dict(n),
        'macros': {k: round(v, 1) for k, v in macros.items()},
        'radar': {
            'labels': ['蛋白质', '脂肪', '碳水', '纤维', '维生素A', '维生素C'],
            'values': [
                round(n.protein / 50 * 100, 1),
                round(n.fat / 30 * 100, 1),
                round(n.carbs / 80 * 100, 1),
                round(min(n.fiber / 10 * 100, 100), 1),
                round(min(n.vitamin_a / 900 * 100, 100), 1),
                round(min(n.vitamin_c / 90 * 100, 100), 1),
            ],
            'raw': nutrition_to_display_dict(n),
        }
    })


# ============================================================================
# 数据管理（导入/导出）
# ============================================================================

@app.route('/data')
def data_page():
    """数据管理页面：导入/导出食谱和食材"""
    recipes = load_recipes()
    ingredients = get_all_ingredients(str(DB_PATH))
    return render_template('data.html',
        stats={
            'recipe_count': len(recipes),
            'ingredient_count': len(ingredients),
        })


@app.route('/export/recipes')
def export_recipes():
    """导出全部食谱为 JSON 文件下载"""
    recipes = load_recipes()
    import tempfile, datetime
    from flask import send_file

    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False,
        encoding='utf-8'
    )
    tmp_path = tmp.name

    ok = export_recipes_to_json(recipes, tmp_path, include_nutrition=True)
    if not ok:
        return render_template('error.html', message="导出食谱失败"), 500

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'食谱库_{timestamp}.json'
    return send_file(
        tmp_path,
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )


@app.route('/export/ingredients')
def export_ingredients():
    """导出全部食材为 JSON 文件下载"""
    ingredients = get_all_ingredients(str(DB_PATH))
    import tempfile, datetime
    from flask import send_file

    tmp = tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False,
        encoding='utf-8'
    )
    tmp_path = tmp.name

    ok = export_ingredients_to_json(ingredients, tmp_path)
    if not ok:
        return render_template('error.html', message="导出食材失败"), 500

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'食材库_{timestamp}.json'
    return send_file(
        tmp_path,
        mimetype='application/json',
        as_attachment=True,
        download_name=filename
    )


@app.route('/import/recipes', methods=['POST'])
def import_recipes():
    """导入食谱 JSON 文件"""
    import os
    file = request.files.get('file')
    if not file:
        flash('请选择要上传的 JSON 文件', 'error')
        return redirect(url_for('data_page'))

    if not file.filename.endswith('.json'):
        flash('仅支持 .json 格式文件', 'error')
        return redirect(url_for('data_page'))

    try:
        content = file.read().decode('utf-8')
        ingredient_map = {ing.name: ing for ing in get_all_ingredients(str(DB_PATH))}
        imported = import_recipes_from_json_str(content, ingredient_map)
        count = 0
        for recipe in imported:
            existing = get_recipe_by_name(recipe.name, str(DB_PATH))
            if not existing:
                insert_recipe(recipe, str(DB_PATH))
                count += 1
        flash(f'成功导入 {count} 道食谱！', 'success')
        return redirect(url_for('data_page'))
    except Exception as e:
        flash(f'导入失败：{str(e)}', 'error')
        return redirect(url_for('data_page'))


@app.route('/import/ingredients', methods=['POST'])
def import_ingredients():
    """导入食材 JSON 文件"""
    import os
    file = request.files.get('file')
    if not file:
        flash('请选择要上传的 JSON 文件', 'error')
        return redirect(url_for('data_page'))

    if not file.filename.endswith('.json'):
        flash('仅支持 .json 格式文件', 'error')
        return redirect(url_for('data_page'))

    try:
        content = file.read().decode('utf-8')
        imported = import_ingredients_from_json_str(content)
        count = 0
        for ing in imported:
            existing = get_ingredient_by_name(ing.name, str(DB_PATH))
            if not existing:
                insert_ingredient(ing, str(DB_PATH))
                count += 1
        flash(f'成功导入 {count} 种食材！', 'success')
        return redirect(url_for('data_page'))
    except Exception as e:
        flash(f'导入失败：{str(e)}', 'error')
        return redirect(url_for('data_page'))


# ============================================================================
# REST API 路由
# ============================================================================

@app.route('/api/recipes')
def api_recipes():
    """API: 获取食谱列表"""
    tag = request.args.get('tag')
    cuisine = request.args.get('cuisine')
    difficulty = request.args.get('difficulty')
    keyword = request.args.get('q')

    recipes = load_recipes()

    if keyword:
        recipes = search_recipes(keyword, str(DB_PATH))
    elif tag:
        recipes = get_recipes_by_tag(tag, str(DB_PATH))
    elif difficulty:
        recipes = get_recipes_by_difficulty(difficulty, str(DB_PATH))
    elif cuisine:
        recipes = get_recipes_by_cuisine(cuisine, str(DB_PATH))

    return jsonify({
        'success': True,
        'count': len(recipes),
        'recipes': [recipe_to_display(r) for r in recipes]
    })


@app.route('/api/recipes/<int:recipe_id>')
def api_recipe_detail(recipe_id):
    """API: 获取食谱详情"""
    recipe = get_recipe_by_id(recipe_id, str(DB_PATH))
    if not recipe:
        return jsonify({'success': False, 'error': '食谱未找到'}), 404

    return jsonify({
        'success': True,
        'recipe': recipe_to_display(recipe)
    })


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """API: 分析食材营养"""
    data = request.get_json()
    input_text = data.get('ingredients', '')

    if not input_text:
        return jsonify({'success': False, 'error': '缺少食材参数'}), 400

    ingredient_map = {ing.name: ing for ing in load_ingredients()}
    parsed_list = parse_ingredient_input(input_text)
    matched = match_parsed_to_inventory(parsed_list, ingredient_map)

    total_nutrition = NutritionInfo()

    for parsed, ingredient in matched:
        if ingredient:
            factor = parsed.amount / 100
            n = ingredient.nutrition_per_100g
            total_nutrition = total_nutrition + NutritionInfo(
                calories=n.calories * factor,
                protein=n.protein * factor,
                fat=n.fat * factor,
                carbs=n.carbs * factor,
                fiber=n.fiber * factor,
                vitamin_a=n.vitamin_a * factor,
                vitamin_c=n.vitamin_c * factor,
                calcium=n.calcium * factor,
                iron=n.iron * factor,
            )

    macros = NutritionCalculator.analyze_macros(total_nutrition)

    return jsonify({
        'success': True,
        'nutrition': nutrition_to_display_dict(total_nutrition),
        'macros': {k: round(v, 1) for k, v in macros.items()},
    })


@app.route('/api/recommend', methods=['POST'])
def api_recommend():
    """API: 智能推荐"""
    data = request.get_json()
    user_ingredients = data.get('ingredients', [])
    max_missing = data.get('max_missing', 3)

    recipes = load_recipes()
    recommender = SmartRecommender(recipes)
    matches = recommender.recommend_by_inventory(user_ingredients, max_missing=max_missing)

    results = []
    for m in matches[:20]:
        results.append({
            'recipe': recipe_to_display(m.recipe),
            'match_score': round(m.match_score, 1),
            'matched_ingredients': m.matched_ingredients,
            'missing_ingredients': m.missing_ingredients,
            'reason': m.reason,
        })

    return jsonify({
        'success': True,
        'count': len(results),
        'recommendations': results
    })


@app.route('/api/plan', methods=['POST'])
def api_plan():
    """API: 生成膳食计划"""
    data = request.get_json()
    days = data.get('days', 7)
    target_calories = data.get('target_calories')

    recipes = load_recipes()
    planner = MealPlanGenerator(recipes)
    weekly = planner.generate_weekly_plan(
        days=min(days, 14),
        target_calories=target_calories
    )

    return jsonify({
        'success': True,
        'plan': weekly.to_dict()
    })


# ============================================================================
# 错误处理
# ============================================================================

@app.errorhandler(HTTPException)
def handle_http_exception(e):
    """处理 HTTP 异常"""
    return render_template('error.html', message=str(e.description)), e.code


@app.errorhandler(Exception)
def handle_exception(e):
    """处理通用异常"""
    return render_template('error.html', message=f"服务器内部错误: {str(e)}"), 500


# ============================================================================
# 主程序入口
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("食谱营养计算器 Web 应用")
    print("=" * 60)
    print(f"数据库: {DB_PATH}")
    print(f"图表库 matplotlib: {'已启用' if _check_matplotlib() else '未安装 (将显示占位图)'}")
    print("-" * 60)
    print("访问地址: http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5000, debug=True)
