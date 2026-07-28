from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
UPLOAD_DIR = Path("static") / "uploads" / "admin"


def _helpers():
    from web_du_lich import get_db_connection, query_all, query_one

    return get_db_connection, query_all, query_one


def dashboard_metrics() -> dict:
    _, query_all, query_one = _helpers()
    return {
        "orders": query_one("SELECT COUNT(*) AS total FROM FoodOrders")["total"],
        "articles": query_one("SELECT COUNT(*) AS total FROM Blogs")["total"],
        "feedback": query_one("SELECT COUNT(*) AS total FROM Reviews")["total"],
        "users": query_one("SELECT COUNT(*) AS total FROM Users")["total"],
        "menu_total": query_one("SELECT COUNT(*) AS total FROM Foods")["total"],
        "menu_available": query_one("SELECT COUNT(*) AS total FROM Foods WHERE COALESCE(is_active, 1) = 1")["total"],
        "menu_unavailable": query_one("SELECT COUNT(*) AS total FROM Foods WHERE COALESCE(is_active, 1) = 0")["total"],
    }


def list_orders(status: str = "all"):
    _, query_all, _ = _helpers()
    params = []
    sql = """
        SELECT o.*, u.full_name AS customer_name, u.phone AS customer_phone, u.email AS customer_email,
               (SELECT COUNT(*) FROM FoodOrderItems i WHERE i.order_id = o.id) AS item_count
        FROM FoodOrders o
        JOIN Users u ON o.user_id = u.id
        WHERE 1 = 1
    """
    if status != "all":
        sql += " AND o.status = ?"
        params.append(status)
    sql += " ORDER BY o.created_at DESC"
    return query_all(sql, tuple(params))


def get_order_detail(order_code: str):
    _, query_all, query_one = _helpers()
    order = query_one(
        """
        SELECT o.*, u.full_name AS customer_name, u.phone AS customer_phone, u.email AS customer_email
        FROM FoodOrders o
        JOIN Users u ON o.user_id = u.id
        WHERE o.order_code = ?
        """,
        (order_code,),
    )
    if order is None:
        return None, []

    items = query_all(
        """
        SELECT i.*, f.name AS food_name, f.category AS food_category, f.image_url AS food_image_url
        FROM FoodOrderItems i
        JOIN Foods f ON i.food_id = f.id
        WHERE i.order_id = ?
        ORDER BY i.id ASC
        """,
        (order["id"],),
    )
    return order, items


def update_order_status(order_code: str, status: str) -> bool:
    get_db_connection, _, _ = _helpers()
    conn = get_db_connection()
    cursor = conn.execute("UPDATE FoodOrders SET status = ? WHERE order_code = ?", (status, order_code))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def list_articles():
    _, query_all, _ = _helpers()
    return query_all(
        """
        SELECT b.*, t.name AS tour_name
        FROM Blogs b
        JOIN Tours t ON b.tour_id = t.id
        ORDER BY b.id DESC
        """
    )


def get_article(article_id: int):
    _, _, query_one = _helpers()
    return query_one(
        """
        SELECT b.*, t.name AS tour_name
        FROM Blogs b
        JOIN Tours t ON b.tour_id = t.id
        WHERE b.id = ?
        """,
        (article_id,),
    )


def list_tours():
    _, query_all, _ = _helpers()
    return query_all("SELECT id, name FROM Tours ORDER BY name ASC")


def save_article_image(upload_file) -> Optional[str]:
    if not upload_file or not upload_file.filename:
        return None

    filename = secure_filename(upload_file.filename)
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Chỉ hỗ trợ file ảnh png, jpg, jpeg, gif, webp.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(filename).stem
    final_name = f"{stem}-{datetime.now().strftime('%Y%m%d%H%M%S')}.{extension}"
    destination = UPLOAD_DIR / final_name
    upload_file.save(destination)
    return f"uploads/admin/{final_name}"


def save_menu_image(upload_file) -> Optional[str]:
    return save_article_image(upload_file)


def create_article(title: str, destination: str, summary: str, content: str, tour_id: int, image_url: str):
    get_db_connection, _, _ = _helpers()
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO Blogs (title, destination, summary, content, image_url, tour_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (title, destination, summary, content, image_url, tour_id),
    )
    conn.commit()
    conn.close()


def update_article(article_id: int, title: str, destination: str, summary: str, content: str, tour_id: int, image_url: str):
    get_db_connection, _, _ = _helpers()
    conn = get_db_connection()
    conn.execute(
        """
        UPDATE Blogs
        SET title = ?, destination = ?, summary = ?, content = ?, image_url = ?, tour_id = ?
        WHERE id = ?
        """,
        (title, destination, summary, content, image_url, tour_id, article_id),
    )
    conn.commit()
    conn.close()


def delete_article(article_id: int):
    get_db_connection, _, _ = _helpers()
    conn = get_db_connection()
    conn.execute("DELETE FROM Blogs WHERE id = ?", (article_id,))
    conn.commit()
    conn.close()


def list_feedback(blog_id: str = "all"):
    _, query_all, _ = _helpers()
    params = []
    sql = """
        SELECT r.*, b.title AS article_title, b.destination AS article_destination
        FROM Reviews r
        JOIN Blogs b ON r.blog_id = b.id
        WHERE 1 = 1
    """
    if blog_id != "all":
        sql += " AND r.blog_id = ?"
        params.append(blog_id)
    sql += " ORDER BY r.id DESC"
    return query_all(sql, tuple(params))


def delete_feedback(review_id: int):
    get_db_connection, _, _ = _helpers()
    conn = get_db_connection()
    conn.execute("DELETE FROM Reviews WHERE id = ?", (review_id,))
    conn.commit()
    conn.close()


def list_menu_categories():
    _, query_all, _ = _helpers()
    rows = query_all(
        """
        SELECT category
        FROM Foods
        WHERE category IS NOT NULL AND TRIM(category) <> ''
        GROUP BY category
        ORDER BY category ASC
        """
    )
    return [row["category"] for row in rows]


def list_menu_items(category: str = "all", availability: str = "all", keyword: str = "", page: int = 1, page_size: int = 10):
    _, query_all, query_one = _helpers()
    params = []
    where_sql = "WHERE 1 = 1"

    if category != "all":
        where_sql += " AND category = ?"
        params.append(category)

    if availability == "available":
        where_sql += " AND is_active = 1"
    elif availability == "unavailable":
        where_sql += " AND COALESCE(is_active, 1) = 0"

    clean_keyword = keyword.strip()
    if clean_keyword:
        where_sql += " AND LOWER(name) LIKE ?"
        params.append(f"%{clean_keyword.lower()}%")

    total_row = query_one(f"SELECT COUNT(*) AS total FROM Foods {where_sql}", tuple(params))
    total = total_row["total"] if total_row else 0

    safe_page_size = max(1, min(page_size, 50))
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    safe_page = max(1, min(page, total_pages))
    offset = (safe_page - 1) * safe_page_size

    sql = f"""
        SELECT id, name, category, price, description, image_url, is_active, created_at, updated_at
        FROM Foods
        {where_sql}
        ORDER BY COALESCE(sort_order, 0) ASC, id DESC
        LIMIT ? OFFSET ?
    """
    result_params = list(params)
    result_params.extend([safe_page_size, offset])
    rows = query_all(sql, tuple(result_params))

    return rows, {
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": total_pages,
    }


def get_menu_item(food_id: int):
    _, _, query_one = _helpers()
    return query_one(
        """
        SELECT id, name, category, price, description, image_url, is_active, created_at, updated_at
        FROM Foods
        WHERE id = ?
        """,
        (food_id,),
    )


def create_menu_item(name: str, category: str, price: float, description: str, image_url: str, is_active: bool):
    get_db_connection, _, _ = _helpers()
    conn = get_db_connection()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor = conn.execute(
        """
        INSERT INTO Foods
        (name, category, price, description, image_url, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (name, category, price, description, image_url, 1 if is_active else 0, now, now),
    )
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id


def update_menu_item(food_id: int, name: str, category: str, price: float, description: str, image_url: str, is_active: bool):
    get_db_connection, _, _ = _helpers()
    conn = get_db_connection()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        """
        UPDATE Foods
        SET name = ?,
            category = ?,
            price = ?,
            description = ?,
            image_url = ?,
            is_active = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (name, category, price, description, image_url, 1 if is_active else 0, now, food_id),
    )
    conn.commit()
    conn.close()


def toggle_menu_availability(food_id: int, is_active: bool) -> bool:
    get_db_connection, _, _ = _helpers()
    conn = get_db_connection()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cursor = conn.execute(
        "UPDATE Foods SET is_active = ?, updated_at = ? WHERE id = ?",
        (1 if is_active else 0, now, food_id),
    )
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def delete_menu_item(food_id: int) -> str:
    get_db_connection, _, _ = _helpers()
    conn = get_db_connection()

    used_in_orders = conn.execute(
        "SELECT 1 FROM FoodOrderItems WHERE food_id = ? LIMIT 1",
        (food_id,),
    ).fetchone()

    if used_in_orders:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute(
            "UPDATE Foods SET is_active = 0, updated_at = ? WHERE id = ?",
            (now, food_id),
        )
        conn.commit()
        conn.close()
        return "archived"

    conn.execute("DELETE FROM FoodCart WHERE food_id = ?", (food_id,))
    cursor = conn.execute("DELETE FROM Foods WHERE id = ?", (food_id,))
    conn.commit()
    conn.close()
    return "deleted" if cursor.rowcount > 0 else "missing"
