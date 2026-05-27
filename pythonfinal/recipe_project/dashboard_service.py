"""
Dashboard data builders for nutrition charts.

This module keeps chart-data assembly out of Flask route handlers so the
routes can focus on request/response flow.
"""

from typing import Any, Dict, List, Optional

from models import NutritionCalculator, NutritionInfo, Recipe
from recommender import WeeklyPlan


RADAR_LABELS = ['蛋白质', '脂肪', '碳水', '纤维', '维生素A', '维生素C']
MACRO_LABELS = ['蛋白质', '脂肪', '碳水']


def build_recipe_nutrition_map(recipes: List[Recipe]) -> Dict[int, NutritionInfo]:
    """Calculate nutrition once per recipe for the current request."""
    return {
        id(recipe): NutritionCalculator.calculate_from_recipe(recipe)
        for recipe in recipes
    }


def recipe_nutrition_summary(
    recipe: Recipe,
    nutrition: Optional[NutritionInfo] = None
) -> Dict[str, Any]:
    """Build the compact nutrition shape used by dashboard charts."""
    if nutrition is None:
        nutrition = NutritionCalculator.calculate_from_recipe(recipe)

    return {
        'name': recipe.name,
        'calories': round(nutrition.calories, 1),
        'protein': round(nutrition.protein, 1),
        'fat': round(nutrition.fat, 1),
        'carbs': round(nutrition.carbs, 1),
        'fiber': round(nutrition.fiber, 1),
        'vitamin_a': round(nutrition.vitamin_a, 1),
        'vitamin_c': round(nutrition.vitamin_c, 1),
    }


def build_nutrition_radar_values(nutrition: NutritionInfo) -> List[float]:
    """Normalize nutrition values for radar chart axes."""
    return [
        round(min(nutrition.protein / 50 * 100, 100), 1),
        round(min(nutrition.fat / 30 * 100, 100), 1),
        round(min(nutrition.carbs / 80 * 100, 100), 1),
        round(min(nutrition.fiber / 10 * 100, 100), 1),
        round(min(nutrition.vitamin_a / 900 * 100, 100), 1),
        round(min(nutrition.vitamin_c / 90 * 100, 100), 1),
    ]


def build_summary_radar_values(summary: Dict[str, Any]) -> List[float]:
    """Normalize a recipe summary for multi-recipe radar comparison."""
    return [
        round(min(summary['protein'] / 50 * 100, 100), 1),
        round(min(summary['fat'] / 30 * 100, 100), 1),
        round(min(summary['carbs'] / 80 * 100, 100), 1),
        round(min(summary['fiber'] / 10 * 100, 100), 1),
        round(min(summary['vitamin_a'] / 900 * 100, 100), 1),
        round(min(summary['vitamin_c'] / 90 * 100, 100), 1),
    ]


def build_dashboard_chart_data(
    recipes: List[Recipe],
    weekly_plan: WeeklyPlan,
    nutrition_map: Optional[Dict[int, NutritionInfo]] = None
) -> Dict[str, Any]:
    """Build all Chart.js data used by the dashboard and chart API."""
    if nutrition_map is None:
        nutrition_map = build_recipe_nutrition_map(recipes)

    all_recipes = [
        recipe_nutrition_summary(recipe, nutrition_map[id(recipe)])
        for recipe in recipes
    ]
    top_recipes = sorted(all_recipes, key=lambda item: item['calories'], reverse=True)[:8]

    calorie_bar_data = {
        'labels': [recipe['name'] for recipe in top_recipes],
        'protein': [recipe['protein'] for recipe in top_recipes],
        'fat': [recipe['fat'] for recipe in top_recipes],
        'carbs': [recipe['carbs'] for recipe in top_recipes],
        'all': all_recipes,
    }

    radar_data = None
    if recipes:
        first_recipe = recipes[0]
        first_nutrition = nutrition_map[id(first_recipe)]
        radar_data = {
            'recipe': first_recipe.name,
            'labels': RADAR_LABELS,
            'values': build_nutrition_radar_values(first_nutrition),
            'raw': {
                'protein': round(first_nutrition.protein, 1),
                'fat': round(first_nutrition.fat, 1),
                'carbs': round(first_nutrition.carbs, 1),
                'fiber': round(first_nutrition.fiber, 1),
                'vitamin_a': round(first_nutrition.vitamin_a, 1),
                'vitamin_c': round(first_nutrition.vitamin_c, 1),
            },
        }

    multi_radar_data = {
        'labels': RADAR_LABELS,
        'recipes': [
            {
                'name': recipe['name'],
                'calories': recipe['calories'],
                'values': build_summary_radar_values(recipe),
            }
            for recipe in top_recipes[:4]
        ],
        'all_recipes': all_recipes,
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
    macro_calories = total_p * 4 + total_f * 9 + total_c * 4
    macro_dist_data = {
        'labels': MACRO_LABELS,
        'values': [round(total_p, 1), round(total_f, 1), round(total_c, 1)],
        'percentages': [
            round(total_p * 4 / macro_calories * 100, 1) if macro_calories > 0 else 0,
            round(total_f * 9 / macro_calories * 100, 1) if macro_calories > 0 else 0,
            round(total_c * 4 / macro_calories * 100, 1) if macro_calories > 0 else 0,
        ],
    }

    return {
        'calorie_bar': calorie_bar_data,
        'radar': radar_data,
        'multi_radar': multi_radar_data,
        'trend': trend_data,
        'macro_dist': macro_dist_data,
        'all_recipes': all_recipes,
    }
