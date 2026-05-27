"""
阶段二：数据持久化 - SQLite 数据库交互

本模块负责：
    - 创建 SQLite 数据库和表结构
    - 实现食材和食谱的 CRUD 操作
    - 将 OOP 对象与数据库记录互相转换
"""

import sqlite3
import json
import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from models import (
    Ingredient, Recipe, RecipeIngredient, NutritionInfo
)


# ============================================================================
# 数据库路径配置
# ============================================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / 'recipe_nutrition.db'


# ============================================================================
# 数据库连接上下文管理器
# ============================================================================

class DatabaseConnection:
    """数据库连接上下文管理器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.conn: Optional[sqlite3.Connection] = None

    def __enter__(self) -> sqlite3.Connection:
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 支持列名访问
        # 启用外键约束
        self.conn.execute('PRAGMA foreign_keys = ON')
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
            self.conn.close()
            self.conn = None


# ============================================================================
# 数据库初始化
# ============================================================================

def init_database(db_path: str = None) -> None:
    """
    初始化数据库：创建所有必要的表

    表结构：
        ingredients: 食材表
        recipes: 食谱表
        recipe_ingredients: 食谱-食材关联表（多对多关系）
    """
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()

        # 食材表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT '其他',
                unit_per_100g REAL DEFAULT 100.0,
                -- 营养成分（每100g）
                calories REAL DEFAULT 0.0,
                protein REAL DEFAULT 0.0,
                fat REAL DEFAULT 0.0,
                carbs REAL DEFAULT 0.0,
                fiber REAL DEFAULT 0.0,
                vitamin_a REAL DEFAULT 0.0,
                vitamin_c REAL DEFAULT 0.0,
                calcium REAL DEFAULT 0.0,
                iron REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 食谱表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                cuisine TEXT DEFAULT '通用',
                difficulty TEXT DEFAULT '中等',
                prep_time INTEGER DEFAULT 15,
                cook_time INTEGER DEFAULT 30,
                tags TEXT DEFAULT '',
                description TEXT DEFAULT '',
                steps TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 食谱-食材关联表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recipe_ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                ingredient_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                unit TEXT DEFAULT 'g',
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
                FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT,
                UNIQUE(recipe_id, ingredient_id)
            )
        ''')

        # 创建索引以加速查询
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_recipe
            ON recipe_ingredients(recipe_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_ingredient
            ON recipe_ingredients(ingredient_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ingredients_category
            ON ingredients(category)
        ''')

        conn.commit()
        print(f"数据库初始化完成: {db_path or DB_PATH}")


# ============================================================================
# 食材 (Ingredient) CRUD 操作
# ============================================================================

def insert_ingredient(ingredient: Ingredient, db_path: str = None) -> int:
    """
    插入单个食材

    Returns:
        新记录的 id
    """
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        n = ingredient.nutrition_per_100g
        cursor.execute('''
            INSERT INTO ingredients
                (name, category, unit_per_100g,
                 calories, protein, fat, carbs, fiber,
                 vitamin_a, vitamin_c, calcium, iron)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ingredient.name,
            ingredient.category,
            ingredient.unit_per_100g,
            n.calories, n.protein, n.fat, n.carbs, n.fiber,
            n.vitamin_a, n.vitamin_c, n.calcium, n.iron
        ))
        return cursor.lastrowid


def insert_ingredients_batch(ingredients: List[Ingredient], db_path: str = None) -> int:
    """
    批量插入食材

    Returns:
        成功插入的数量
    """
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        count = 0
        for ing in ingredients:
            try:
                n = ing.nutrition_per_100g
                cursor.execute('''
                    INSERT OR IGNORE INTO ingredients
                        (name, category, unit_per_100g,
                         calories, protein, fat, carbs, fiber,
                         vitamin_a, vitamin_c, calcium, iron)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ing.name, ing.category, ing.unit_per_100g,
                    n.calories, n.protein, n.fat, n.carbs, n.fiber,
                    n.vitamin_a, n.vitamin_c, n.calcium, n.iron
                ))
                count += 1
            except sqlite3.IntegrityError:
                pass
        return count


def get_ingredient_by_name(name: str, db_path: str = None) -> Optional[Ingredient]:
    """根据名称查询单个食材"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ingredients WHERE name = ?', (name,))
        row = cursor.fetchone()
        if row:
            return _row_to_ingredient(row)
        return None


def get_ingredient_by_id(ingredient_id: int, db_path: str = None) -> Optional[Ingredient]:
    """根据ID查询单个食材"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ingredients WHERE id = ?', (ingredient_id,))
        row = cursor.fetchone()
        if row:
            return _row_to_ingredient(row)
        return None


def get_all_ingredients(db_path: str = None) -> List[Ingredient]:
    """获取所有食材"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ingredients ORDER BY category, name')
        rows = cursor.fetchall()
        return [_row_to_ingredient(row) for row in rows]


def get_ingredients_by_category(category: str, db_path: str = None) -> List[Ingredient]:
    """按分类获取食材"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM ingredients WHERE category = ? ORDER BY name',
            (category,)
        )
        rows = cursor.fetchall()
        return [_row_to_ingredient(row) for row in rows]


def update_ingredient(ingredient_id: int, ingredient: Ingredient, db_path: str = None) -> bool:
    """更新食材信息"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        n = ingredient.nutrition_per_100g
        cursor.execute('''
            UPDATE ingredients SET
                name = ?, category = ?, unit_per_100g = ?,
                calories = ?, protein = ?, fat = ?, carbs = ?, fiber = ?,
                vitamin_a = ?, vitamin_c = ?, calcium = ?, iron = ?
            WHERE id = ?
        ''', (
            ingredient.name, ingredient.category, ingredient.unit_per_100g,
            n.calories, n.protein, n.fat, n.carbs, n.fiber,
            n.vitamin_a, n.vitamin_c, n.calcium, n.iron,
            ingredient_id
        ))
        return cursor.rowcount > 0


def delete_ingredient(ingredient_id: int, db_path: str = None) -> bool:
    """删除食材（如果被食谱引用则拒绝删除）"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ingredients WHERE id = ?', (ingredient_id,))
        return cursor.rowcount > 0


def search_ingredients(keyword: str, db_path: str = None) -> List[Ingredient]:
    """模糊搜索食材（按名称）"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM ingredients WHERE name LIKE ? ORDER BY name',
            (f'%{keyword}%',)
        )
        rows = cursor.fetchall()
        return [_row_to_ingredient(row) for row in rows]


def get_all_ingredient_names(db_path: str = None) -> List[str]:
    """获取所有食材名称列表（用于推荐算法快速匹配）"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM ingredients ORDER BY name')
        return [row['name'] for row in cursor.fetchall()]


# ============================================================================
# 食谱 (Recipe) CRUD 操作
# ============================================================================

def insert_recipe(recipe: Recipe, db_path: str = None) -> int:
    """
    插入食谱及其关联食材

    Returns:
        新食谱的 id
    """
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO recipes (name, cuisine, difficulty, prep_time, cook_time, tags, description, steps)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            recipe.name,
            recipe.cuisine,
            recipe.difficulty,
            recipe.prep_time,
            recipe.cook_time,
            json.dumps(recipe.tags, ensure_ascii=False),
            recipe.description,
            json.dumps(recipe.steps, ensure_ascii=False)
        ))
        recipe_id = cursor.lastrowid

        # 插入关联食材
        for ri in recipe.ingredients:
            # 获取食材 id
            cursor.execute('SELECT id FROM ingredients WHERE name = ?', (ri.ingredient.name,))
            ing_row = cursor.fetchone()
            if ing_row:
                cursor.execute('''
                    INSERT INTO recipe_ingredients (recipe_id, ingredient_id, amount, unit)
                    VALUES (?, ?, ?, ?)
                ''', (recipe_id, ing_row['id'], ri.amount, ri.unit))

        return recipe_id


def insert_recipes_batch(recipes: List[Recipe], db_path: str = None) -> int:
    """批量插入食谱"""
    count = 0
    for recipe in recipes:
        try:
            insert_recipe(recipe, db_path)
            count += 1
        except sqlite3.IntegrityError:
            pass  # 跳过已存在的食谱
    return count


def get_recipe_by_name(name: str, db_path: str = None) -> Optional[Recipe]:
    """根据名称查询食谱"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recipes WHERE name = ?', (name,))
        row = cursor.fetchone()
        if row:
            return _row_to_recipe(row, cursor)
        return None


def get_recipe_id_by_name(name: str, db_path: str = None) -> Optional[int]:
    """根据名称查询食谱的数据库ID"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM recipes WHERE name = ?', (name,))
        row = cursor.fetchone()
        if row:
            return row['id']
        return None


def get_recipe_by_id(recipe_id: int, db_path: str = None) -> Optional[Recipe]:
    """根据ID查询食谱"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recipes WHERE id = ?', (recipe_id,))
        row = cursor.fetchone()
        if row:
            return _row_to_recipe(row, cursor)
        return None


def get_all_recipes(db_path: str = None) -> List[Recipe]:
    """获取所有食谱"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM recipes ORDER BY name')
        rows = cursor.fetchall()
        return [_row_to_recipe(row, cursor) for row in rows]


def search_recipes(keyword: str, db_path: str = None) -> List[Recipe]:
    """模糊搜索食谱（按名称、描述、标签）"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        pattern = f'%{keyword}%'
        cursor.execute('''
            SELECT * FROM recipes
            WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY name
        ''', (pattern, pattern, pattern))
        rows = cursor.fetchall()
        return [_row_to_recipe(row, cursor) for row in rows]


def get_recipes_by_tag(tag: str, db_path: str = None) -> List[Recipe]:
    """按标签筛选食谱"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM recipes WHERE tags LIKE ? ORDER BY name",
            (f'%{tag}%',)
        )
        rows = cursor.fetchall()
        return [_row_to_recipe(row, cursor) for row in rows]


def get_recipes_by_difficulty(difficulty: str, db_path: str = None) -> List[Recipe]:
    """按难度筛选食谱"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM recipes WHERE difficulty = ? ORDER BY name',
            (difficulty,)
        )
        rows = cursor.fetchall()
        return [_row_to_recipe(row, cursor) for row in rows]


def get_recipes_by_cuisine(cuisine: str, db_path: str = None) -> List[Recipe]:
    """按菜系筛选食谱"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM recipes WHERE cuisine = ? ORDER BY name',
            (cuisine,)
        )
        rows = cursor.fetchall()
        return [_row_to_recipe(row, cursor) for row in rows]


def delete_recipe(recipe_id: int, db_path: str = None) -> bool:
    """删除食谱（关联食材会自动删除）"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM recipes WHERE id = ?', (recipe_id,))
        return cursor.rowcount > 0


def get_recipe_count(db_path: str = None) -> int:
    """获取食谱总数"""
    with DatabaseConnection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM recipes')
        return cursor.fetchone()['cnt']


# ============================================================================
# 辅助函数：数据库行转 Python 对象
# ============================================================================

def _row_to_ingredient(row: sqlite3.Row) -> Ingredient:
    """将数据库行转换为 Ingredient 对象"""
    nutrition = NutritionInfo(
        calories=row['calories'],
        protein=row['protein'],
        fat=row['fat'],
        carbs=row['carbs'],
        fiber=row['fiber'],
        vitamin_a=row['vitamin_a'],
        vitamin_c=row['vitamin_c'],
        calcium=row['calcium'],
        iron=row['iron']
    )
    return Ingredient(
        name=row['name'],
        nutrition=nutrition,
        unit_per_100g=row['unit_per_100g'],
        category=row['category']
    )


def _row_to_recipe(row: sqlite3.Row, cursor: sqlite3.Cursor) -> Recipe:
    """将数据库行转换为 Recipe 对象（需要额外查询关联食材）"""
    recipe_id = row['id']

    # 查询关联食材
    cursor.execute('''
        SELECT ri.amount, ri.unit, i.*
        FROM recipe_ingredients ri
        JOIN ingredients i ON ri.ingredient_id = i.id
        WHERE ri.recipe_id = ?
    ''', (recipe_id,))

    recipe_ingredients = []
    for ri_row in cursor.fetchall():
        ingredient = _row_to_ingredient(ri_row)
        ri = RecipeIngredient(
            ingredient=ingredient,
            amount=ri_row['amount'],
            unit=ri_row['unit']
        )
        recipe_ingredients.append(ri)

    # 解析 JSON 字段
    try:
        tags = json.loads(row['tags']) if row['tags'] else []
    except json.JSONDecodeError:
        tags = []

    try:
        steps = json.loads(row['steps']) if row['steps'] else []
    except json.JSONDecodeError:
        steps = []

    recipe = Recipe(
        name=row['name'],
        ingredients=recipe_ingredients,
        steps=steps,
        cuisine=row['cuisine'],
        difficulty=row['difficulty'],
        prep_time=row['prep_time'],
        cook_time=row['cook_time'],
        tags=tags,
        description=row['description']
    )
    recipe._db_id = recipe_id
    return recipe


# ============================================================================
# 便捷函数：初始化示例数据
# ============================================================================

def seed_sample_data(db_path: str = None) -> Dict[str, int]:
    """
    初始化示例数据（食材库 + 食谱）

    Returns:
        dict: {'ingredients': 数量, 'recipes': 数量}
    """
    from models import create_sample_ingredients, create_sample_recipes

    init_database(db_path)

    # 导入示例食材
    ingredient_map = create_sample_ingredients()
    ing_list = list(ingredient_map.values())
    ing_count = insert_ingredients_batch(ing_list, db_path)

    # 导入示例食谱
    recipes = create_sample_recipes(ingredient_map)
    recipe_count = insert_recipes_batch(recipes, db_path)

    return {'ingredients': ing_count, 'recipes': recipe_count}


# ============================================================================
# 主程序入口（用于测试）
# ============================================================================

if __name__ == '__main__':
    import sys

    # 重置数据库
    test_db = str(DATA_DIR / 'test_recipe.db')
    if os.path.exists(test_db):
        os.remove(test_db)

    print("=" * 60)
    print("阶段二测试：SQLite 数据库操作")
    print("=" * 60)

    # 初始化数据库
    print("\n[1] 初始化数据库...")
    init_database(test_db)

    # 导入示例数据
    print("\n[2] 导入示例食材和食谱...")
    result = seed_sample_data(test_db)
    print(f"    成功导入 {result['ingredients']} 种食材, {result['recipes']} 个食谱")

    # 测试食材查询
    print("\n[3] 测试食材查询...")
    all_ingredients = get_all_ingredients(test_db)
    print(f"    共有 {len(all_ingredients)} 种食材")
    tomato = get_ingredient_by_name('西红柿', test_db)
    if tomato:
        print(f"    查询'西红柿': 热量={tomato.nutrition_per_100g.calories}kcal/100g")

    # 测试食谱查询
    print("\n[4] 测试食谱查询...")
    all_recipes = get_all_recipes(test_db)
    print(f"    共有 {len(all_recipes)} 个食谱")
    for r in all_recipes:
        print(f"    - {r.name} (耗时{r.total_time}分钟)")

    # 测试食谱营养计算
    print("\n[5] 测试食谱营养计算...")
    from models import NutritionCalculator
    for recipe in all_recipes:
        total = NutritionCalculator.calculate_from_recipe(recipe)
        print(f"    {recipe.name}: {total.calories:.1f} kcal")

    # 测试搜索功能
    print("\n[6] 测试搜索功能...")
    results = search_recipes('鸡', test_db)
    print(f"    搜索'鸡': 找到 {len(results)} 个食谱")
    results = search_ingredients('西', test_db)
    print(f"    搜索'西': 找到 {len(results)} 个食材")

    # 测试标签筛选
    print("\n[7] 测试标签筛选...")
    low_fat_recipes = get_recipes_by_tag('低脂', test_db)
    print(f"    标签'低脂': 找到 {len(low_fat_recipes)} 个食谱")

    print("\n" + "=" * 60)
    print("阶段二测试完成！")
    print("=" * 60)
