from app import app

with app.test_client() as client:
    # Test 1: Homepage charts
    resp = client.get('/')
    print('1. Homepage status:', resp.status_code)
    html = resp.get_data(as_text=True)
    chart_count = html.count('src="/static/charts/')
    print('   Charts found in homepage:', chart_count)
    print('   [PASS]' if chart_count >= 3 and resp.status_code == 200 else '   [FAIL]')

    # Test 2: Recipe filter by tag
    resp = client.get('/recipes?tag=川菜')
    html = resp.get_data(as_text=True)
    print()
    print('2. Filter by tag (川菜):', resp.status_code)
    print('   [PASS - contains 川菜]' if '川菜' in html else '   [FAIL - no 川菜 found]')

    # Test 3: Filter by keyword
    resp = client.get('/recipes?q=宫保')
    html = resp.get_data(as_text=True)
    print()
    print('3. Filter by keyword (宫保):', resp.status_code)
    print('   [PASS]' if '宫保' in html else '   [FAIL]')

    # Test 4: Recipe detail page
    resp = client.get('/recipes/宫保鸡丁')
    html = resp.get_data(as_text=True)
    print()
    print('4. Recipe detail (宫保鸡丁):', resp.status_code)
    has_macros = 'protein_pct' in html or 'protein' in html
    print('   Has macros data:', has_macros)
    print('   [PASS]' if resp.status_code == 200 and has_macros else '   [FAIL]')

    # Test 5: API recipe count
    resp = client.get('/api/recipes')
    data = resp.get_json()
    print()
    print('5. API recipes count:', data['count'])
    print('   [PASS]' if data['count'] == 32 else '   [FAIL - expected 32]')

    print()
    print('All tests done!')
