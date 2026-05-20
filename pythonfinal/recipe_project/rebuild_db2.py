import os
from database import seed_sample_data, DB_PATH

# 删除旧数据库，重新生成
if DB_PATH.exists():
    os.remove(DB_PATH)
    print('Old database deleted')

result = seed_sample_data(str(DB_PATH))
print('New database created:')
print('  Ingredients:', result['ingredients'])
print('  Recipes:', result['recipes'])

# Verify
import sqlite3
conn = sqlite3.connect(str(DB_PATH))
c = conn.cursor()
c.execute("SELECT id, name FROM recipes ORDER BY id LIMIT 5")
print()
print('Sample recipes from DB:')
for row in c.fetchall():
    print(f'  ID={row[0]} | {row[1]}')
conn.close()
