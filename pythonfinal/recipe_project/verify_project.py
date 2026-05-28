"""
Lightweight project verification script.

Run from the recipe_project directory:
    python verify_project.py
"""

from io import BytesIO
import json
import sys
from typing import Callable, List, Tuple

from app import app


Check = Tuple[str, Callable[[], None]]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def post_json(client, url: str, payload: dict, filename: str = "data.json"):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return client.post(
        url,
        data={"file": (BytesIO(data), filename)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def build_checks() -> List[Check]:
    with app.test_client() as client:

        def homepage() -> None:
            response = client.get("/")
            assert_true(response.status_code == 200, "首页无法打开")
            html = response.get_data(as_text=True)
            assert_true("chart" in html.lower(), "首页未渲染图表区域")

        def recipes_page_filters() -> None:
            response = client.get("/recipes?q=西红柿&cuisine=家常菜")
            assert_true(response.status_code == 200, "食谱筛选页无法打开")
            html = response.get_data(as_text=True)
            assert_true("西红柿" in html or "暂无" in html, "关键词筛选结果异常")

        def recipes_api_filters() -> None:
            response = client.get("/api/recipes?cuisine=家常菜")
            assert_true(response.status_code == 200, "食谱 API 无法访问")
            payload = response.get_json()
            assert_true(payload and payload.get("success") is True, "食谱 API 返回格式异常")
            for recipe in payload.get("recipes", []):
                assert_true(recipe.get("cuisine") == "家常菜", "食谱 API 菜系筛选异常")

        def charts_api() -> None:
            response = client.get("/api/charts")
            assert_true(response.status_code == 200, "图表 API 无法访问")
            payload = response.get_json()
            assert_true(payload and payload.get("success") is True, "图表 API 返回格式异常")
            assert_true("radar" in payload and "raw" in payload["radar"], "雷达图数据缺少 raw 字段")

        def export_endpoints() -> None:
            for url, key in (("/export/recipes", b'"recipes"'), ("/export/ingredients", b'"ingredients"')):
                response = client.get(url)
                assert_true(response.status_code == 200, f"{url} 下载失败")
                assert_true(key in response.data, f"{url} 下载内容异常")

        def import_validation() -> None:
            bad_response = client.post(
                "/import/ingredients",
                data={"file": (BytesIO(b"{bad json"), "bad.json")},
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            bad_html = bad_response.get_data(as_text=True)
            assert_true("JSON 格式错误" in bad_html, "坏 JSON 未显示明确错误")

            missing_recipe_ingredient = {
                "recipes": [{
                    "name": "验证脚本缺失食材食谱",
                    "ingredients": [{"name": "不存在食材", "amount": 10, "unit": "g"}],
                }]
            }
            response = post_json(client, "/import/recipes", missing_recipe_ingredient)
            html = response.get_data(as_text=True)
            assert_true("不存在" in html, "缺失食材未显示明确错误")

        def add_form_validation() -> None:
            response = client.post(
                "/ingredients/add",
                data={"name": "验证脚本非法热量", "calories": "abc"},
                follow_redirects=True,
            )
            html = response.get_data(as_text=True)
            assert_true("热量必须是有效数字" in html, "新增食材数值校验异常")

            response = client.post(
                "/recipes/add",
                data={"name": "验证脚本无食材食谱", "prep_time": "10", "cook_time": "20"},
                follow_redirects=True,
            )
            html = response.get_data(as_text=True)
            assert_true("请至少添加一种有效食材" in html, "新增食谱食材校验异常")

        return [
            ("首页渲染", homepage),
            ("食谱页面筛选", recipes_page_filters),
            ("食谱 API 菜系筛选", recipes_api_filters),
            ("图表 API 数据", charts_api),
            ("导出接口", export_endpoints),
            ("导入错误提示", import_validation),
            ("新增表单校验", add_form_validation),
        ]


def main() -> int:
    failed = 0
    for name, check in build_checks():
        try:
            check()
            print(f"[PASS] {name}")
        except Exception as exc:
            failed += 1
            print(f"[FAIL] {name}: {exc}")

    if failed:
        print(f"\n{failed} checks failed.")
        return 1

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
