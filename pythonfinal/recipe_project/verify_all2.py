from app import app

with app.test_client() as c:
    r = c.get('/plan?days=5')
    html = r.get_data(as_text=True)
    print('Status:', r.status_code)
    print('Has day-card class:', 'day-card' in html)

    # Find all day cards
    import re
    # Look for day header sections
    headers = re.findall(r'class="day-header">(.*?)</div>', html, re.DOTALL)
    print('Day headers found:', len(headers))
    for h in headers[:8]:
        label = re.search(r'<span>(.*?)</span>', h)
        if label:
            print(' -', label.group(1)[:20])

    # Count 周一 through 周五
    print('周一 count:', html.count('周一'))
    print('周五 count:', html.count('周五'))
    print('周六 count:', html.count('周六'))

    # Also test recommend
    print()
    r2 = c.post('/recommend', data={
        'action': 'by_inventory',
        'inventory': '鸡蛋 2个, 西红柿 200g, 油 10g'
    }, follow_redirects=True)
    html2 = r2.get_data(as_text=True)
    print('Recommend status:', r2.status_code)
    print('Has 推荐结果:', '推荐结果' in html2)
    print('Has recipe:', '鸡' in html2 or 'recipe' in html2.lower())

    # Test by tags
    r3 = c.post('/recommend', data={
        'action': 'by_tags',
        'tags': '川菜,家常',
        'min_cal': '0',
        'max_cal': '2000',
        'max_time': '60'
    }, follow_redirects=True)
    html3 = r3.get_data(as_text=True)
    print()
    print('Recommend by tags status:', r3.status_code)
    print('Has result or recipe:', '川菜' in html3 or '家' in html3)
