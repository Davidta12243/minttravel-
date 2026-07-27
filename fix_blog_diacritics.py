# -*- coding: utf-8 -*-
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('dulich.db')
cur = conn.cursor()

updates = [
    (
        "H\u00e0 N\u1ed9i v\u1ec1 \u0111\u00eam v\u00e0 h\u00e0nh tr\u00ecnh \u1ea9m th\u1ef1c c\u1ed5 \u0111i\u1ec3n",
        "Kh\u00f4ng gian ph\u1ed1 c\u1ed5 l\u00fac l\u00ean \u0111\u00e8n l\u00e0 th\u1eddi \u0111i\u1ec3m \u0111\u1eb9p nh\u1ea5t \u0111\u1ec3 th\u1eed m\u00f3n \u0103n v\u1ec9a h\u00e8.",
        "H\u00e0 N\u1ed9i",
        1
    ),
    (
        "\u0110\u00e0 N\u1eb5ng \u2013 H\u1ed9i An: 3 ng\u00e0y c\u00e2n b\u1eb1ng gi\u1eefa bi\u1ec3n v\u00e0 ph\u1ed1",
        "H\u00e0nh tr\u00ecnh k\u1ebft h\u1ee3p c\u1ea3nh bi\u1ec3n, \u1ea9m th\u1ef1c mi\u1ec1n Trung v\u00e0 n\u00e9t \u0111\u1eb9p di s\u1ea3n.",
        "\u0110\u00e0 N\u1eb5ng",
        2
    ),
    (
        "Nha Trang cho ng\u01b0\u1eddi mu\u1ed1n ngh\u1ec9 d\u01b0\u1ee1ng nh\u01b0ng v\u1eabn n\u0103ng \u0111\u1ed9ng",
        "Bi\u1ec3n xanh v\u00e0 c\u00e1c ho\u1ea1t \u0111\u1ed9ng tr\u00ean \u0111\u1ea3o l\u00e0 \u0111i\u1ec3m nh\u1ea5n c\u1ee7a h\u00e0nh tr\u00ecnh.",
        "Nha Trang",
        3
    ),
]

for title, summary, destination, blog_id in updates:
    cur.execute(
        "UPDATE blogs SET title=?, summary=?, destination=? WHERE id=?",
        (title, summary, destination, blog_id)
    )

conn.commit()
conn.close()
print("Done! All blogs updated with Vietnamese diacritics.")
