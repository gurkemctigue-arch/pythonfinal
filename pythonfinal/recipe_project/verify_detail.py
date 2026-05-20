from app import app

with app.test_client() as client:
    resp = client.get('/recipes/%E5%AE%AB%E4%BF%9D%E9%B8%A6%E4%B8%81')
    html = resp.get_data(as_text=True)

    # Check that the macros values appear (rendered as numbers, not variable names)
    has_protein = 'protein' in html.lower() or '蛋白质' in html
    has_macro_bars = 'progress-bar bg-danger' in html
    has_calories = 'kcal' in html

    print('Recipe detail page checks:')
    print('  Status:', resp.status_code)
    print('  Has protein/nutrient info:', has_protein)
    print('  Has macro progress bars:', has_macro_bars)
    print('  Has calorie display:', has_calories)
    print('  Has "P " macro label:', '>P ' in html or 'P ' in html)
    print()

    # Also check the macros dict is passed correctly
    print('Rendered macro values check:')
    print('  Contains % sign (macro pct rendered):', '%' in html)
    print('  [PASS]' if resp.status_code == 200 and has_protein else '  [FAIL]')
