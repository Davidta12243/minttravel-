from datetime import datetime
from datetime import timedelta
import io
import os
from flask import Flask, flash, make_response, redirect, render_template, request, session, url_for
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import random
import sqlite3
import string

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

load_dotenv()

app = Flask(__name__)
DB_PATH = "dulich.db"
LOW_SEAT_THRESHOLD = 5
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

oauth = OAuth(app)

google_client_id = os.getenv("GOOGLE_CLIENT_ID")
google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_OAUTH_ENABLED = bool(google_client_id and google_client_secret)
if google_client_id and google_client_secret:
    oauth.register(
        name="google",
        client_id=google_client_id,
        client_secret=google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

facebook_client_id = os.getenv("FACEBOOK_CLIENT_ID")
facebook_client_secret = os.getenv("FACEBOOK_CLIENT_SECRET")
FACEBOOK_OAUTH_ENABLED = bool(facebook_client_id and facebook_client_secret)
if facebook_client_id and facebook_client_secret:
    oauth.register(
        name="facebook",
        client_id=facebook_client_id,
        client_secret=facebook_client_secret,
        access_token_url="https://graph.facebook.com/v19.0/oauth/access_token",
        authorize_url="https://www.facebook.com/v19.0/dialog/oauth",
        api_base_url="https://graph.facebook.com/v19.0/",
        client_kwargs={"scope": "email public_profile"},
    )

apple_client_id = os.getenv("APPLE_CLIENT_ID")
apple_client_secret = os.getenv("APPLE_CLIENT_SECRET")
APPLE_OAUTH_ENABLED = bool(apple_client_id and apple_client_secret)
if apple_client_id and apple_client_secret:
    oauth.register(
        name="apple",
        client_id=apple_client_id,
        client_secret=apple_client_secret,
        server_metadata_url="https://appleid.apple.com/.well-known/openid-configuration",
        client_kwargs={"scope": "name email"},
    )


def ensure_column(cursor, table_name, column_name, definition_sql):
    columns = cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_names = [column[1] for column in columns]
    if column_name not in existing_names:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition_sql}")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS Tours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            image_url TEXT,
            slots_left INTEGER NOT NULL,
            slots_booked INTEGER NOT NULL,
            duration_days INTEGER DEFAULT 1,
            hours_left INTEGER DEFAULT 72,
            route_summary TEXT
        )
        """
    )

    ensure_column(cursor, "Tours", "duration_days", "INTEGER DEFAULT 1")
    ensure_column(cursor, "Tours", "hours_left", "INTEGER DEFAULT 72")
    ensure_column(cursor, "Tours", "route_summary", "TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS Foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            image_url TEXT,
            description TEXT,
            combo_percent REAL DEFAULT 0,
            tour_bundle_percent REAL DEFAULT 0
        )
        """
    )

    ensure_column(cursor, "Foods", "is_active", "INTEGER DEFAULT 1")
    ensure_column(cursor, "Foods", "sort_order", "INTEGER DEFAULT 0")
    ensure_column(cursor, "Foods", "created_at", "TEXT")
    ensure_column(cursor, "Foods", "updated_at", "TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS Blogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            destination TEXT NOT NULL,
            summary TEXT NOT NULL,
            content TEXT NOT NULL,
            image_url TEXT,
            tour_id INTEGER NOT NULL,
            FOREIGN KEY (tour_id) REFERENCES Tours (id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS Reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            blog_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY (blog_id) REFERENCES Blogs (id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS Users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            oauth_provider TEXT,
            oauth_sub TEXT
        )
        """
    )

    ensure_column(cursor, "Users", "oauth_provider", "TEXT")
    ensure_column(cursor, "Users", "oauth_sub", "TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS Bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tour_id INTEGER NOT NULL,
            booking_code TEXT NOT NULL UNIQUE,
            seats INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users (id),
            FOREIGN KEY (tour_id) REFERENCES Tours (id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS FoodCart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_key TEXT,
            food_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users (id),
            FOREIGN KEY (food_id) REFERENCES Foods (id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS FoodOrders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            order_code TEXT NOT NULL UNIQUE,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL,
            with_tour INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users (id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS FoodOrderItems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            food_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES FoodOrders (id),
            FOREIGN KEY (food_id) REFERENCES Foods (id)
        )
        """
    )

    cursor.execute("SELECT count(*) FROM Tours")
    if cursor.fetchone()[0] == 0:
        tours = [
            (
                "Food Tour Phố Cổ Hà Nội",
                550000,
                "https://images.unsplash.com/photo-1563492065599-3520f775eeed?auto=format&fit=crop&w=600&q=80",
                2,
                18,
                2,
                20,
                "Hồ Gươm - Tạ Hiện - Nhà Thờ Lớn",
            ),
            (
                "Sunrise Đà Nẵng Hội An",
                2390000,
                "https://images.unsplash.com/photo-1528127269322-539801943592",
                11,
                29,
                3,
                60,
                "Bán đảo Sơn Trà - Cầu Rồng - Phố cổ Hội An",
            ),
            (
                "Nha Trang Blue Escape",
                3290000,
                "https://images.unsplash.com/photo-1537996194471-e657df975ab4",
                4,
                21,
                3,
                44,
                "Hòn Mun - VinWonders - Chợ đêm",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO Tours
            (name, price, image_url, slots_left, slots_booked, duration_days, hours_left, route_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tours,
        )
    else:
        cursor.execute("UPDATE Tours SET duration_days = COALESCE(duration_days, 1)")
        cursor.execute("UPDATE Tours SET hours_left = COALESCE(hours_left, 72)")
        cursor.execute(
            """
            UPDATE Tours
            SET route_summary = COALESCE(route_summary, 'Hành trình được cập nhật trong chi tiết tour')
            """
        )

    nemta_foods = [
        (
            "Nem heo truyền thống",
            "Spring Rolls",
            39000,
            "https://images.unsplash.com/photo-1601050690597-df0568f70950",
            "Pork, trứng, rau củ, nấm và gia vị truyền thống.",
            5,
            3,
            1,
        ),
        (
            "Nem tôm thịt",
            "Spring Rolls",
            49000,
            "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38",
            "Tôm tươi kết hợp thịt heo, trứng, rau củ và nấm.",
            5,
            3,
            2,
        ),
        (
            "Nem cua thịt",
            "Spring Rolls",
            49000,
            "https://images.unsplash.com/photo-1467003909585-2f8a72700288",
            "Cua biển và thịt heo, vị ngọt tự nhiên, đậm đà.",
            5,
            3,
            3,
        ),
        (
            "Nem hải sản",
            "Spring Rolls",
            59000,
            "https://images.unsplash.com/photo-1544025162-d76694265947",
            "Hải sản tổng hợp, thịt heo, rau củ và gia vị truyền thống.",
            5,
            3,
            4,
        ),
        (
            "Nem chay",
            "Spring Rolls",
            39000,
            "https://images.unsplash.com/photo-1512621776951-a57141f2eefd",
            "Rau củ tươi, đậu và nấm, phù hợp thực đơn thanh đạm.",
            5,
            3,
            5,
        ),
        (
            "Salad ăn kèm",
            "Add-on",
            19000,
            "https://images.unsplash.com/photo-1512621776951-a57141f2eefd",
            "Salad tươi ăn kèm nem, cân bằng vị và giảm ngấy.",
            0,
            0,
            6,
        ),
        (
            "Combo Veggie",
            "Combo Meals",
            97000,
            "https://images.unsplash.com/photo-1546069901-ba9599a7e63c",
            "2 nem chay + 1 salad ăn kèm.",
            8,
            3,
            7,
        ),
        (
            "Combo Pork",
            "Combo Meals",
            97000,
            "https://images.unsplash.com/photo-1512058564366-18510be2db19",
            "2 nem heo truyền thống + 1 salad.",
            8,
            3,
            8,
        ),
        (
            "Combo Seafood Trio",
            "Combo Meals",
            167000,
            "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f",
            "Nem tôm thịt + nem cua thịt + nem hải sản + tặng 1 salad.",
            8,
            3,
            9,
        ),
        (
            "Combo Four Seasons",
            "Combo Meals",
            206000,
            "https://images.unsplash.com/photo-1547592180-85f173990554",
            "4 vị: heo, tôm, cua, hải sản + tặng 2 salad.",
            10,
            5,
            10,
        ),
        (
            "Combo All Five",
            "Combo Meals",
            245000,
            "https://images.unsplash.com/photo-1482049016688-2d3e1b311543",
            "5 cuốn đủ vị + tặng 2 salad.",
            10,
            5,
            11,
        ),
        (
            "Lavie Mineral Water",
            "Beverages",
            9000,
            "https://images.unsplash.com/photo-1602143407151-7111542de6e8",
            "Nước khoáng Lavie 500ml.",
            0,
            0,
            12,
        ),
        (
            "Coca Cola",
            "Beverages",
            19000,
            "https://images.unsplash.com/photo-1622483767028-3f66f32aef97",
            "Coca Cola lon mát lạnh.",
            0,
            0,
            13,
        ),
        (
            "Hanoi Beer",
            "Beverages",
            19000,
            "https://images.unsplash.com/photo-1516478177764-9fe5bd7e9717",
            "Bia Hà Nội lon.",
            0,
            0,
            14,
        ),
        (
            "Honey Kumquat Tea",
            "Beverages",
            19000,
            "https://images.unsplash.com/photo-1556679343-c7306c1976bc",
            "Trà tắc mật ong thanh mát.",
            0,
            0,
            15,
        ),
        (
            "Tropical Oolong Tea",
            "Beverages",
            19000,
            "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085",
            "Trà ô long nhiệt đới vị dịu nhẹ.",
            0,
            0,
            16,
        ),
    ]

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Keep historical rows for order/cart references but only show synced active menu.
    cursor.execute("UPDATE Foods SET is_active = 0")
    for item in nemta_foods:
        name, category, price, image_url, description, combo_percent, tour_bundle_percent, sort_order = item
        existing = cursor.execute("SELECT id FROM Foods WHERE name = ?", (name,)).fetchone()
        if existing:
            cursor.execute(
                """
                UPDATE Foods
                SET category = ?,
                    price = ?,
                    image_url = ?,
                    description = ?,
                    combo_percent = ?,
                    tour_bundle_percent = ?,
                    sort_order = ?,
                    is_active = 1,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    category,
                    price,
                    image_url,
                    description,
                    combo_percent,
                    tour_bundle_percent,
                    sort_order,
                    now_text,
                    existing[0],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO Foods
                (name, category, price, image_url, description, combo_percent, tour_bundle_percent, is_active, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (name, category, price, image_url, description, combo_percent, tour_bundle_percent, sort_order, now_text, now_text),
            )

    cursor.execute("UPDATE Foods SET created_at = COALESCE(created_at, ?) WHERE created_at IS NULL OR TRIM(created_at) = ''", (now_text,))
    cursor.execute("UPDATE Foods SET updated_at = COALESCE(updated_at, created_at, ?) WHERE updated_at IS NULL OR TRIM(updated_at) = ''", (now_text,))

    cursor.execute("SELECT count(*) FROM Blogs")
    if cursor.fetchone()[0] == 0:
        blogs = [
            (
                "Hà Nội về đêm và hành trình ẩm thực cổ điển",
                "Hà Nội",
                "Không gian phố cổ lúc lên đèn là thời điểm đẹp nhất để thử món ăn vỉa hè.",
                "Phố cổ về đêm tạo cảm giác vừa thân quen vừa sôi động. Bạn có thể bắt đầu từ Hồ Gươm, ghé Tạ Hiện và kết thúc bằng một ly cà phê trứng.",
                "https://images.unsplash.com/photo-1563492065599-3520f775eeed",
                1,
            ),
            (
                "Đà Nẵng Hội An: 3 ngày cân bằng giữa biển và phố",
                "Đà Nẵng",
                "Hành trình kết hợp cảnh biển, ẩm thực miền Trung và nét đẹp di sản.",
                "Ngày đầu khám phá Sơn Trà, ngày hai đi Hội An, ngày ba dành cho beach club và các quán ăn địa phương.",
                "https://images.unsplash.com/photo-1527838832700-5059252407fa",
                2,
            ),
            (
                "Nha Trang cho người muốn nghỉ dưỡng nhưng vẫn năng động",
                "Nha Trang",
                "Biển xanh và các hoạt động trên đảo là điểm nhấn của hành trình.",
                "Nếu bạn thích lặn ngắm san hô và ăn hải sản tươi, đây là chuyến đi rất đáng thử.",
                "https://images.unsplash.com/photo-1518509562904-e7ef99cdcc86",
                3,
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO Blogs (title, destination, summary, content, image_url, tour_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            blogs,
        )

    cursor.execute("SELECT count(*) FROM Reviews")
    if cursor.fetchone()[0] == 0:
        reviews = [
            (1, "Lê Minh", 5, "Lịch trình gọn gàng, hướng dẫn viên nhiệt tình."),
            (1, "Hà An", 4, "Ăn ngon, nhiều điểm check-in đẹp."),
            (2, "Ngọc Khánh", 5, "Hội An buổi tối đẹp hơn kỳ vọng."),
            (3, "Bảo Châu", 4, "Team support nhanh, đặt tour dễ."),
        ]
        cursor.executemany(
            """
            INSERT INTO Reviews (blog_id, customer_name, rating, content)
            VALUES (?, ?, ?, ?)
            """,
            reviews,
        )

    cursor.execute("SELECT count(*) FROM Users")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """
            INSERT INTO Users (full_name, phone, email)
            VALUES (?, ?, ?)
            """,
            ("Guest Demo", "0900000000", "guest@example.com"),
        )

    cursor.execute("SELECT count(*) FROM Bookings")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """
            INSERT INTO Bookings (user_id, tour_id, booking_code, seats, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (1, 2, "BK20260505001", 2, "Đã xác nhận", datetime.now().strftime("%Y-%m-%d %H:%M")),
        )

    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_all(sql, params=()):
    conn = get_db_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def query_one(sql, params=()):
    conn = get_db_connection()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return row


def build_date_filtered_sql(base_sql, status_field, created_at_field, status_value, from_date, to_date, params):
    sql = base_sql
    if status_value and status_value != "all":
        sql += f" AND {status_field} = ?"
        params.append(status_value)
    if from_date:
        sql += f" AND substr({created_at_field}, 1, 10) >= ?"
        params.append(from_date)
    if to_date:
        sql += f" AND substr({created_at_field}, 1, 10) <= ?"
        params.append(to_date)
    sql += f" ORDER BY {created_at_field} DESC"
    return sql, params


def get_or_create_oauth_user(provider, oauth_sub, full_name, email):
    conn = get_db_connection()
    user = conn.execute(
        '''
        SELECT * FROM Users
        WHERE oauth_provider = ? AND oauth_sub = ?
        ''',
        (provider, oauth_sub),
    ).fetchone()

    if user is None and email:
        user = conn.execute('SELECT * FROM Users WHERE email = ?', (email,)).fetchone()

    if user is None:
        conn.execute(
            '''
            INSERT INTO Users (full_name, phone, email, oauth_provider, oauth_sub)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (full_name or "OAuth User", "", email, provider, oauth_sub),
        )
        user = conn.execute(
            '''
            SELECT * FROM Users
            WHERE oauth_provider = ? AND oauth_sub = ?
            ''',
            (provider, oauth_sub),
        ).fetchone()
    else:
        conn.execute(
            '''
            UPDATE Users
            SET full_name = ?,
                email = COALESCE(?, email),
                oauth_provider = ?,
                oauth_sub = ?
            WHERE id = ?
            ''',
            (full_name or user["full_name"], email, provider, oauth_sub, user["id"]),
        )
        user = conn.execute('SELECT * FROM Users WHERE id = ?', (user["id"],)).fetchone()

    conn.commit()
    conn.close()
    return user


def get_session_cart_key():
    cart_key = session.get("cart_key")
    if not cart_key:
        cart_key = "S" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
        session["cart_key"] = cart_key
    return cart_key


def get_active_user_id():
    session_user = session.get("user")
    if not session_user:
        return None
    return session_user.get("id")


def get_cart_rows(user_id, session_key):
    if user_id:
        return query_all(
            '''
            SELECT c.id AS cart_id, c.quantity, f.*
            FROM FoodCart c
            JOIN Foods f ON c.food_id = f.id
            WHERE c.user_id = ?
            ORDER BY c.id DESC
            ''',
            (user_id,),
        )

    return query_all(
        '''
        SELECT c.id AS cart_id, c.quantity, f.*
        FROM FoodCart c
        JOIN Foods f ON c.food_id = f.id
        WHERE c.session_key = ?
        ORDER BY c.id DESC
        ''',
        (session_key,),
    )


def upsert_cart_item(user_id, session_key, food_id, quantity):
    conn = get_db_connection()
    if user_id:
        row = conn.execute(
            'SELECT * FROM FoodCart WHERE user_id = ? AND food_id = ?',
            (user_id, food_id),
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT * FROM FoodCart WHERE session_key = ? AND food_id = ?',
            (session_key, food_id),
        ).fetchone()

    if row:
        conn.execute(
            'UPDATE FoodCart SET quantity = quantity + ? WHERE id = ?',
            (quantity, row['id']),
        )
    else:
        conn.execute(
            '''
            INSERT INTO FoodCart (user_id, session_key, food_id, quantity, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (user_id, session_key if not user_id else None, food_id, quantity, datetime.now().strftime('%Y-%m-%d %H:%M')),
        )

    conn.commit()
    conn.close()


def merge_guest_cart_to_user(user_id, session_key):
    conn = get_db_connection()
    guest_rows = conn.execute(
        'SELECT food_id, quantity FROM FoodCart WHERE session_key = ?',
        (session_key,),
    ).fetchall()

    for row in guest_rows:
        existing = conn.execute(
            'SELECT * FROM FoodCart WHERE user_id = ? AND food_id = ?',
            (user_id, row['food_id']),
        ).fetchone()
        if existing:
            conn.execute(
                'UPDATE FoodCart SET quantity = quantity + ? WHERE id = ?',
                (row['quantity'], existing['id']),
            )
        else:
            conn.execute(
                '''
                INSERT INTO FoodCart (user_id, session_key, food_id, quantity, created_at)
                VALUES (?, NULL, ?, ?, ?)
                ''',
                (user_id, row['food_id'], row['quantity'], datetime.now().strftime('%Y-%m-%d %H:%M')),
            )

    conn.execute('DELETE FROM FoodCart WHERE session_key = ?', (session_key,))
    conn.commit()
    conn.close()


def generate_booking_code():
    now = datetime.now().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.digits, k=4))
    return f"BK{now}{suffix}"


def generate_food_order_code():
    now = datetime.now().strftime("%Y%m%d")
    suffix = "".join(random.choices(string.digits, k=4))
    return f"FD{now}{suffix}"


def parse_dt(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def can_cancel_tour(created_at):
    hours = (datetime.now() - parse_dt(created_at)).total_seconds() / 3600
    if hours <= 72:
        return True, "Đã hủy - hoàn 100%"
    if hours <= 120:
        return True, "Đã hủy - hoàn 50%"
    return False, "Quá thời gian hoàn hủy tự động"


def can_cancel_food_order(created_at, current_status):
    if current_status.startswith("Đã hủy"):
        return False, "Đơn đã hủy trước đó"
    if current_status != "Chờ xác nhận":
        return False, "Đơn đã xử lý, không thể hủy"
    hours = (datetime.now() - parse_dt(created_at)).total_seconds() / 3600
    if hours <= 2:
        return True, "Đã hủy - hoàn 100%"
    return False, "Đơn đồ ăn quá 2 giờ, không được hoàn"


def build_invoice_pdf(title, lines):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(40, y, title)
    y -= 28

    pdf.setFont("Helvetica", 11)
    for line in lines:
        if y < 40:
            pdf.showPage()
            pdf.setFont("Helvetica", 11)
            y = height - 50
        pdf.drawString(40, y, str(line))
        y -= 18

    pdf.save()
    buffer.seek(0)
    return buffer.read()


def apply_food_discounts(base_price, combo_percent, tour_bundle_percent, item_count, with_tour):
    final_price = float(base_price)
    if item_count >= 2 and combo_percent > 0:
        final_price = final_price * (1 - combo_percent / 100)
    if item_count >= 4:
        final_price = final_price * 0.9
    if with_tour and tour_bundle_percent > 0:
        final_price = final_price * (1 - tour_bundle_percent / 100)
    return round(final_price)

@app.route('/')
def home():
    featured_tours = query_all('SELECT * FROM Tours ORDER BY slots_left ASC LIMIT 3')
    featured_blogs = query_all('SELECT * FROM Blogs ORDER BY id DESC LIMIT 2')
    return render_template('index.html', featured_tours=featured_tours, featured_blogs=featured_blogs)


@app.context_processor
def inject_global_values():
    user_id = get_active_user_id()
    cart_key = get_session_cart_key()
    cart_count_row = query_one(
        '''
        SELECT COALESCE(SUM(quantity), 0) AS total_qty
        FROM FoodCart
        WHERE (user_id = ?)
           OR (session_key = ? AND ? IS NULL)
        ''',
        (user_id, cart_key, user_id),
    )
    cart_count = cart_count_row['total_qty'] if cart_count_row else 0

    return {
        "current_year": datetime.now().year,
        "low_seat_threshold": LOW_SEAT_THRESHOLD,
        "current_user": session.get("user"),
        "google_oauth_enabled": GOOGLE_OAUTH_ENABLED,
        "facebook_oauth_enabled": FACEBOOK_OAUTH_ENABLED,
        "apple_oauth_enabled": APPLE_OAUTH_ENABLED,
        "admin_authenticated": session.get("admin_authenticated", False),
        "cart_count": cart_count,
    }


@app.route('/login/google')
def login_google():
    if not GOOGLE_OAUTH_ENABLED:
        return redirect(url_for('about'))
    redirect_uri = url_for('auth_google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route('/auth/google/callback')
def auth_google_callback():
    if not GOOGLE_OAUTH_ENABLED:
        return redirect(url_for('about'))

    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get("userinfo")
        if not user_info:
            user_info = oauth.google.parse_id_token(token)
    except Exception:
        return render_template(
            'oauth_error.html',
            provider='Google',
            message='Đăng nhập thất bại hoặc đã bị hủy. Vui lòng thử lại.',
        )

    if not user_info:
        return render_template(
            'oauth_error.html',
            provider='Google',
            message='Không thể lấy thông tin tài khoản Google.',
        )

    user = get_or_create_oauth_user(
        provider="google",
        oauth_sub=user_info.get("sub", ""),
        full_name=user_info.get("name") or "Google User",
        email=user_info.get("email"),
    )
    merge_guest_cart_to_user(user["id"], get_session_cart_key())
    session["user"] = {"id": user["id"], "full_name": user["full_name"], "email": user["email"]}
    flash("Đăng nhập Google thành công.", "success")
    return redirect(url_for('personal'))


@app.route('/login/facebook')
def login_facebook():
    if not FACEBOOK_OAUTH_ENABLED:
        return redirect(url_for('about'))
    redirect_uri = url_for('auth_facebook_callback', _external=True)
    return oauth.facebook.authorize_redirect(redirect_uri)


@app.route('/auth/facebook/callback')
def auth_facebook_callback():
    if not FACEBOOK_OAUTH_ENABLED:
        return redirect(url_for('about'))

    try:
        oauth.facebook.authorize_access_token()
        profile = oauth.facebook.get('me?fields=id,name,email').json()
    except Exception:
        return render_template(
            'oauth_error.html',
            provider='Facebook',
            message='Đăng nhập thất bại hoặc đã bị hủy. Vui lòng thử lại.',
        )

    if not profile:
        return render_template(
            'oauth_error.html',
            provider='Facebook',
            message='Không thể lấy thông tin tài khoản Facebook.',
        )

    user = get_or_create_oauth_user(
        provider="facebook",
        oauth_sub=profile.get("id", ""),
        full_name=profile.get("name") or "Facebook User",
        email=profile.get("email"),
    )
    merge_guest_cart_to_user(user["id"], get_session_cart_key())
    session["user"] = {"id": user["id"], "full_name": user["full_name"], "email": user["email"]}
    flash("Đăng nhập Facebook thành công.", "success")
    return redirect(url_for('personal'))


@app.route('/login/apple')
def login_apple():
    if not APPLE_OAUTH_ENABLED:
        return redirect(url_for('about'))
    redirect_uri = url_for('auth_apple_callback', _external=True)
    return oauth.apple.authorize_redirect(redirect_uri)


@app.route('/auth/apple/callback', methods=['GET', 'POST'])
def auth_apple_callback():
    if not APPLE_OAUTH_ENABLED:
        return redirect(url_for('about'))

    try:
        token = oauth.apple.authorize_access_token()
        user_info = token.get("userinfo")
        if not user_info:
            user_info = oauth.apple.parse_id_token(token)
    except Exception:
        return render_template(
            'oauth_error.html',
            provider='Apple',
            message='Đăng nhập thất bại hoặc đã bị hủy. Vui lòng thử lại.',
        )

    if not user_info:
        return render_template(
            'oauth_error.html',
            provider='Apple',
            message='Không thể lấy thông tin tài khoản Apple.',
        )

    apple_sub = user_info.get("sub", "")
    email = user_info.get("email")
    full_name = "Apple User"
    if "name" in user_info:
        name_obj = user_info["name"]
        if isinstance(name_obj, dict):
            full_name = f"{name_obj.get('givenName', '')} {name_obj.get('familyName', '')}".strip() or "Apple User"
        else:
            full_name = name_obj

    user = get_or_create_oauth_user(
        provider="apple",
        oauth_sub=apple_sub,
        full_name=full_name,
        email=email,
    )
    merge_guest_cart_to_user(user["id"], get_session_cart_key())
    session["user"] = {"id": user["id"], "full_name": user["full_name"], "email": user["email"]}
    flash("Đăng nhập Apple ID thành công.", "success")
    return redirect(url_for('personal'))


@app.route('/logout')
def logout():
    session.pop("user", None)
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for('home'))


@app.route('/about')
def about():
    customer_feedback = [
        "Tư vấn nhanh, dễ chọn tour hợp ngân sách.",
        "Lịch trình rõ ràng, đội ngũ chăm sóc nhiệt tình.",
        "Đặt combo tour + món ăn rất tiết kiệm.",
    ]
    return render_template('about.html', customer_feedback=customer_feedback)


@app.route('/journeys')
def journeys():
    tours = query_all('SELECT * FROM Tours ORDER BY id DESC')
    return render_template('journeys.html', tours=tours)


@app.route('/foods')
def foods():
    selected_category = request.args.get("category", "Tat ca")
    with_tour = request.args.get("with_tour", "0") == "1"
    try:
        item_count = max(1, int(request.args.get("item_count", "1")))
    except ValueError:
        item_count = 1

    categories = [
        row["category"]
        for row in query_all(
            '''
            SELECT category
            FROM Foods
            WHERE is_active = 1
            GROUP BY category
            ORDER BY MIN(sort_order) ASC, category ASC
            '''
        )
    ]

    if selected_category == "Tat ca":
        foods_rows = query_all('SELECT * FROM Foods WHERE is_active = 1 ORDER BY sort_order ASC, id ASC')
    else:
        foods_rows = query_all(
            'SELECT * FROM Foods WHERE is_active = 1 AND category = ? ORDER BY sort_order ASC, id ASC',
            (selected_category,),
        )

    foods_data = []
    for row in foods_rows:
        item = dict(row)
        item["discounted_price"] = apply_food_discounts(
            row["price"],
            row["combo_percent"],
            row["tour_bundle_percent"],
            item_count,
            with_tour,
        )
        foods_data.append(item)

    user_id = get_active_user_id()
    cart_rows = get_cart_rows(user_id, get_session_cart_key())
    total_items = sum(row['quantity'] for row in cart_rows)
    cart_with_tour = request.args.get("cart_with_tour", "0") == "1"

    cart_data = []
    cart_total = 0
    for row in cart_rows:
        cart_item = dict(row)
        unit_price = apply_food_discounts(
            row['price'],
            row['combo_percent'],
            row['tour_bundle_percent'],
            total_items,
            cart_with_tour,
        )
        cart_item['unit_price'] = unit_price
        cart_item['line_total'] = unit_price * row['quantity']
        cart_total += cart_item['line_total']
        cart_data.append(cart_item)

    return render_template(
        'foods.html',
        foods=foods_data,
        categories=categories,
        selected_category=selected_category,
        with_tour=with_tour,
        item_count=item_count,
        cart_items=cart_data,
        cart_total=cart_total,
        cart_with_tour=cart_with_tour,
    )


@app.route('/cart/add', methods=['POST'])
def cart_add():
    try:
        food_id = int(request.form.get('food_id', '0'))
        quantity = max(1, int(request.form.get('quantity', '1')))
    except ValueError:
        return redirect(url_for('foods'))

    food = query_one('SELECT id FROM Foods WHERE id = ? AND is_active = 1', (food_id,))
    if food is None:
        return redirect(url_for('foods'))

    upsert_cart_item(get_active_user_id(), get_session_cart_key(), food_id, quantity)
    flash('Đã thêm món vào giỏ hàng.', 'success')
    return redirect(url_for('foods'))


@app.route('/cart/update', methods=['POST'])
def cart_update():
    try:
        cart_id = int(request.form.get('cart_id', '0'))
        quantity = max(1, int(request.form.get('quantity', '1')))
    except ValueError:
        return redirect(url_for('foods'))

    user_id = get_active_user_id()
    cart_key = get_session_cart_key()
    conn = get_db_connection()
    if user_id:
        conn.execute('UPDATE FoodCart SET quantity = ? WHERE id = ? AND user_id = ?', (quantity, cart_id, user_id))
    else:
        conn.execute('UPDATE FoodCart SET quantity = ? WHERE id = ? AND session_key = ?', (quantity, cart_id, cart_key))
    conn.commit()
    conn.close()
    return redirect(url_for('foods'))


@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    try:
        cart_id = int(request.form.get('cart_id', '0'))
    except ValueError:
        return redirect(url_for('foods'))

    user_id = get_active_user_id()
    cart_key = get_session_cart_key()
    conn = get_db_connection()
    if user_id:
        conn.execute('DELETE FROM FoodCart WHERE id = ? AND user_id = ?', (cart_id, user_id))
    else:
        conn.execute('DELETE FROM FoodCart WHERE id = ? AND session_key = ?', (cart_id, cart_key))
    conn.commit()
    conn.close()
    return redirect(url_for('foods'))


@app.route('/cart/checkout', methods=['POST'])
def cart_checkout():
    user_id = get_active_user_id()
    if not user_id:
        flash('Vui lòng đăng nhập để thanh toán giỏ đồ ăn.', 'error')
        return redirect(url_for('personal'))

    with_tour = request.form.get('cart_with_tour', '0') == '1'
    cart_rows = get_cart_rows(user_id, get_session_cart_key())
    if not cart_rows:
        flash('Giỏ hàng hiện đang trống.', 'info')
        return redirect(url_for('foods'))

    total_items = sum(row['quantity'] for row in cart_rows)
    order_code = generate_food_order_code()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M')

    order_items = []
    grand_total = 0
    for row in cart_rows:
        unit_price = apply_food_discounts(
            row['price'],
            row['combo_percent'],
            row['tour_bundle_percent'],
            total_items,
            with_tour,
        )
        line_total = unit_price * row['quantity']
        grand_total += line_total
        order_items.append((row['id'], row['quantity'], unit_price, line_total))

    conn = get_db_connection()
    conn.execute(
        '''
        INSERT INTO FoodOrders (user_id, order_code, total_amount, status, with_tour, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (user_id, order_code, grand_total, 'Chờ xác nhận', 1 if with_tour else 0, created_at),
    )
    order = conn.execute('SELECT id FROM FoodOrders WHERE order_code = ?', (order_code,)).fetchone()

    for food_id, qty, unit_price, line_total in order_items:
        conn.execute(
            '''
            INSERT INTO FoodOrderItems (order_id, food_id, quantity, unit_price, line_total)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (order['id'], food_id, qty, unit_price, line_total),
        )

    conn.execute('DELETE FROM FoodCart WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

    flash(f'Đặt đồ ăn thành công. Mã đơn: {order_code}', 'success')
    return redirect(url_for('personal'))


@app.route('/food-order/<order_code>')
def food_order_detail(order_code):
    user_id = get_active_user_id()
    if not user_id:
        flash('Vui lòng đăng nhập để xem chi tiết đơn.', 'error')
        return redirect(url_for('personal'))

    order = query_one(
        '''
        SELECT *
        FROM FoodOrders
        WHERE order_code = ? AND user_id = ?
        ''',
        (order_code, user_id),
    )
    if order is None:
        flash('Không tìm thấy đơn đồ ăn.', 'error')
        return redirect(url_for('personal'))

    items = query_all(
        '''
        SELECT i.*, f.name AS food_name
        FROM FoodOrderItems i
        JOIN Foods f ON i.food_id = f.id
        WHERE i.order_id = ?
        ORDER BY i.id ASC
        ''',
        (order['id'],),
    )
    return render_template('food_order_detail.html', order=order, items=items)


@app.route('/booking/<booking_code>')
def booking_detail(booking_code):
    user_id = get_active_user_id()
    if not user_id:
        flash('Vui lòng đăng nhập để xem chi tiết đơn tour.', 'error')
        return redirect(url_for('personal'))

    booking = query_one(
        '''
        SELECT b.*, t.name AS tour_name, t.price AS tour_price, t.duration_days, t.route_summary, t.image_url
        FROM Bookings b
        JOIN Tours t ON b.tour_id = t.id
        WHERE b.booking_code = ? AND b.user_id = ?
        ''',
        (booking_code, user_id),
    )
    if booking is None:
        flash('Không tìm thấy mã đặt tour.', 'error')
        return redirect(url_for('personal'))

    return render_template('booking_detail.html', booking=booking)


@app.route('/booking/cancel/<booking_code>', methods=['POST'])
def cancel_tour_booking(booking_code):
    user_id = get_active_user_id()
    if not user_id:
        flash('Vui lòng đăng nhập để hủy đơn tour.', 'error')
        return redirect(url_for('personal'))

    conn = get_db_connection()
    booking = conn.execute(
        '''
        SELECT *
        FROM Bookings
        WHERE booking_code = ? AND user_id = ?
        ''',
        (booking_code, user_id),
    ).fetchone()
    if booking is None:
        conn.close()
        flash('Không tìm thấy mã đặt chỗ.', 'error')
        return redirect(url_for('personal'))

    if booking['status'].startswith('Đã hủy'):
        conn.close()
        flash('Đơn tour này đã được hủy trước đó.', 'info')
        return redirect(url_for('personal'))

    allowed, status_text = can_cancel_tour(booking['created_at'])
    if not allowed:
        conn.close()
        flash(status_text, 'error')
        return redirect(url_for('personal'))

    conn.execute('UPDATE Bookings SET status = ? WHERE id = ?', (status_text, booking['id']))
    conn.execute(
        '''
        UPDATE Tours
        SET slots_left = slots_left + ?,
            slots_booked = CASE WHEN slots_booked >= ? THEN slots_booked - ? ELSE 0 END
        WHERE id = ?
        ''',
        (booking['seats'], booking['seats'], booking['seats'], booking['tour_id']),
    )
    conn.commit()
    conn.close()
    flash(f'Hủy tour thành công ({status_text}).', 'success')
    return redirect(url_for('personal'))


@app.route('/food-order/cancel/<order_code>', methods=['POST'])
def cancel_food_order(order_code):
    user_id = get_active_user_id()
    if not user_id:
        flash('Vui lòng đăng nhập để hủy đơn đồ ăn.', 'error')
        return redirect(url_for('personal'))

    conn = get_db_connection()
    order = conn.execute(
        '''
        SELECT *
        FROM FoodOrders
        WHERE order_code = ? AND user_id = ?
        ''',
        (order_code, user_id),
    ).fetchone()
    if order is None:
        conn.close()
        flash('Không tìm thấy đơn đồ ăn.', 'error')
        return redirect(url_for('personal'))

    allowed, status_text = can_cancel_food_order(order['created_at'], order['status'])
    if not allowed:
        conn.close()
        flash(status_text, 'error')
        return redirect(url_for('personal'))

    conn.execute('UPDATE FoodOrders SET status = ? WHERE id = ?', (status_text, order['id']))
    conn.commit()
    conn.close()
    flash(f'Hủy đơn đồ ăn thành công ({status_text}).', 'success')
    return redirect(url_for('personal'))


@app.route('/invoice/tour/<booking_code>.pdf')
def invoice_tour_pdf(booking_code):
    user_id = get_active_user_id()
    if not user_id:
        return redirect(url_for('personal'))

    booking = query_one(
        '''
        SELECT b.*, t.name AS tour_name, t.price AS tour_price
        FROM Bookings b
        JOIN Tours t ON b.tour_id = t.id
        WHERE b.booking_code = ? AND b.user_id = ?
        ''',
        (booking_code, user_id),
    )
    if booking is None:
        flash('Không tìm thấy invoice tour.', 'error')
        return redirect(url_for('personal'))

    total = booking['tour_price'] * booking['seats']
    lines = [
        f"Mã đặt chỗ: {booking['booking_code']}",
        f"Khách hàng: {session['user']['full_name']}",
        f"Tour: {booking['tour_name']}",
        f"Số chỗ: {booking['seats']}",
        f"Đơn giá: {booking['tour_price']:,.0f} VND",
        f"Tổng tiền: {total:,.0f} VND",
        f"Trạng thái: {booking['status']}",
        f"Thời gian tạo: {booking['created_at']}",
    ]
    pdf_data = build_invoice_pdf("TOUR INVOICE - INNERCOMPASS", lines)
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=tour_{booking_code}.pdf'
    return response


@app.route('/invoice/food/<order_code>.pdf')
def invoice_food_pdf(order_code):
    user_id = get_active_user_id()
    if not user_id:
        return redirect(url_for('personal'))

    order = query_one(
        '''
        SELECT *
        FROM FoodOrders
        WHERE order_code = ? AND user_id = ?
        ''',
        (order_code, user_id),
    )
    if order is None:
        flash('Không tìm thấy invoice đồ ăn.', 'error')
        return redirect(url_for('personal'))

    items = query_all(
        '''
        SELECT i.*, f.name AS food_name
        FROM FoodOrderItems i
        JOIN Foods f ON i.food_id = f.id
        WHERE i.order_id = ?
        ORDER BY i.id ASC
        ''',
        (order['id'],),
    )

    lines = [
        f"Mã đơn: {order['order_code']}",
        f"Khách hàng: {session['user']['full_name']}",
        f"Tổng tiền: {order['total_amount']:,.0f} VND",
        f"Kèm tour: {'Có' if order['with_tour'] == 1 else 'Không'}",
        f"Trạng thái: {order['status']}",
        f"Thời gian tạo: {order['created_at']}",
        "Chi tiết món:",
    ]
    for item in items:
        lines.append(
            f"- {item['food_name']}: {item['quantity']} x {item['unit_price']:,.0f} = {item['line_total']:,.0f} VND"
        )

    pdf_data = build_invoice_pdf("FOOD INVOICE - INNERCOMPASS", lines)
    response = make_response(pdf_data)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=food_{order_code}.pdf'
    return response


@app.route('/blogs')
def blogs():
    from admin.moderation import is_article_hidden

    blogs_data = query_all(
        '''
        SELECT b.*, t.name AS tour_name
        FROM Blogs b
        JOIN Tours t ON b.tour_id = t.id
        ORDER BY b.id DESC
        '''
    )
    blogs_data = [blog for blog in blogs_data if not is_article_hidden(blog['id'])]
    return render_template('blogs.html', blogs=blogs_data)


@app.route('/blog/<int:blog_id>')
def blog_detail(blog_id):
    from admin.moderation import get_review_status, is_article_hidden

    if is_article_hidden(blog_id):
        flash('Bài viết này hiện đang tạm ẩn.', 'info')
        return redirect(url_for('blogs'))

    blog = query_one(
        '''
        SELECT b.*, t.name AS tour_name, t.id AS linked_tour_id
        FROM Blogs b
        JOIN Tours t ON b.tour_id = t.id
        WHERE b.id = ?
        ''',
        (blog_id,),
    )
    if blog is None:
        return redirect(url_for("blogs"))

    reviews = [
        review
        for review in query_all('SELECT * FROM Reviews WHERE blog_id = ? ORDER BY id DESC', (blog_id,))
        if get_review_status(review['id']) != 'hidden'
    ]
    return render_template('blog_detail.html', blog=blog, reviews=reviews)


@app.route('/personal')
def personal():
    session_user = session.get("user")
    if session_user:
        user = query_one('SELECT * FROM Users WHERE id = ?', (session_user["id"],))
    else:
        user = None

    if user is None:
        return render_template('personal.html', user=None, bookings=[], food_orders=[])

    booking_status = request.args.get('booking_status', 'all')
    food_status = request.args.get('food_status', 'all')
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()

    booking_sql, booking_params = build_date_filtered_sql(
        '''
        SELECT b.*, t.name AS tour_name, t.price AS tour_price
        FROM Bookings b
        JOIN Tours t ON b.tour_id = t.id
        WHERE b.user_id = ?
        ''',
        'b.status',
        'b.created_at',
        booking_status,
        from_date,
        to_date,
        [user['id']],
    )
    bookings = query_all(booking_sql, tuple(booking_params))

    food_sql, food_params = build_date_filtered_sql(
        '''
        SELECT *
        FROM FoodOrders
        WHERE user_id = ?
        ''',
        'status',
        'created_at',
        food_status,
        from_date,
        to_date,
        [user['id']],
    )
    food_orders = query_all(food_sql, tuple(food_params))

    return render_template(
        'personal.html',
        user=user,
        bookings=bookings,
        food_orders=food_orders,
        booking_status=booking_status,
        food_status=food_status,
        from_date=from_date,
        to_date=to_date,
    )


@app.route('/book/<int:tour_id>', methods=['POST'])
def book_tour(tour_id):
    user_id = get_active_user_id()
    if not user_id:
        flash('Vui lòng đăng nhập Google/Facebook trước khi đặt tour.', 'error')
        return redirect(url_for('personal'))

    try:
        seats = max(1, int(request.form.get('seats', '1')))
    except ValueError:
        seats = 1

    conn = get_db_connection()
    tour = conn.execute('SELECT * FROM Tours WHERE id = ?', (tour_id,)).fetchone()
    if tour is None or tour['slots_left'] < seats:
        conn.close()
        return redirect(url_for('journeys'))

    booking_code = generate_booking_code()
    conn.execute(
        '''
        INSERT INTO Bookings (user_id, tour_id, booking_code, seats, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (user_id, tour_id, booking_code, seats, 'Chờ xác nhận', datetime.now().strftime('%Y-%m-%d %H:%M')),
    )
    conn.execute(
        '''
        UPDATE Tours
        SET slots_left = slots_left - ?,
            slots_booked = slots_booked + ?
        WHERE id = ?
        ''',
        (seats, seats, tour_id),
    )
    conn.commit()
    conn.close()
    flash(f'Đặt tour thành công. Mã đặt chỗ: {booking_code}', 'success')
    return redirect(url_for('personal'))


@app.route('/policy/privacy')
def policy_privacy():
    return render_template('policy.html', policy_type='privacy')


@app.route('/policy/cancellation')
def policy_cancellation():
    return render_template('policy.html', policy_type='cancellation')


from admin.routes import admin_bp

app.register_blueprint(admin_bp)

if __name__ == '__main__':
    init_db()
    debug_mode = os.getenv('FLASK_DEBUG', '1') == '1'
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '5000'))
    # Disabling reloader prevents SystemExit: 3 when running under VS Code debugger / debugpy
    use_reloader = os.getenv('FLASK_USE_RELOADER', '0') == '1'
    app.run(debug=debug_mode, host=host, port=port, use_reloader=use_reloader)