from __future__ import annotations

import os

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from admin.queries import ORDER_STATUSES
from admin.moderation import load_state, set_article_hidden, set_review_status
from admin.services import (
    create_article,
    create_menu_item,
    dashboard_metrics,
    delete_article,
    delete_feedback,
    delete_menu_item,
    get_article,
    get_menu_item,
    get_order_detail,
    list_articles,
    list_feedback,
    list_menu_categories,
    list_menu_items,
    list_orders,
    list_tours,
    save_article_image,
    save_menu_image,
    update_article,
    update_menu_item,
    update_order_status,
    toggle_menu_availability,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
ADMIN_ACCESS_CODE = os.getenv("ADMIN_ACCESS_CODE", "admin123")


@admin_bp.before_request
def require_admin_access():
    if request.endpoint in {"admin.admin_login", "admin.admin_logout"}:
        return None
    if session.get("admin_authenticated"):
        return None
    return redirect(url_for("admin.admin_login"))


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        access_code = request.form.get("access_code", "").strip()
        if access_code == ADMIN_ACCESS_CODE:
            session["admin_authenticated"] = True
            flash("Đăng nhập admin thành công.", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Mã truy cập không đúng.", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_authenticated", None)
    flash("Đã đăng xuất khỏi admin.", "info")
    return redirect(url_for("admin.admin_login"))


@admin_bp.route("/")
def dashboard():
    metrics = dashboard_metrics()
    recent_orders = list_orders()[0:5]
    recent_articles = list_articles()[0:5]
    recent_feedback = list_feedback()[0:5]
    return render_template(
        "admin/dashboard.html",
        metrics=metrics,
        recent_orders=recent_orders,
        recent_articles=recent_articles,
        recent_feedback=recent_feedback,
    )


@admin_bp.route("/orders")
def orders_index():
    status = request.args.get("status", "all")
    orders = list_orders(status=status)
    return render_template(
        "admin/orders/index.html",
        orders=orders,
        status=status,
        order_statuses=ORDER_STATUSES,
    )


@admin_bp.route("/orders/<order_code>")
def order_detail(order_code):
    order, items = get_order_detail(order_code)
    if order is None:
        flash("Không tìm thấy đơn hàng.", "error")
        return redirect(url_for("admin.orders_index"))
    return render_template("admin/orders/detail.html", order=order, items=items, order_statuses=ORDER_STATUSES)


@admin_bp.route("/orders/<order_code>/status", methods=["POST"])
def order_status_update(order_code):
    status = request.form.get("status", "").strip()
    if status not in ORDER_STATUSES:
        flash("Trạng thái không hợp lệ.", "error")
        return redirect(url_for("admin.order_detail", order_code=order_code))
    if update_order_status(order_code, status):
        flash("Đã cập nhật trạng thái đơn hàng.", "success")
    else:
        flash("Không tìm thấy đơn hàng để cập nhật.", "error")
    return redirect(url_for("admin.order_detail", order_code=order_code))


@admin_bp.route("/articles")
def articles_index():
    articles = list_articles()
    hidden_articles = {str(item) for item in load_state()["hidden_articles"]}
    return render_template("admin/articles/index.html", articles=articles, hidden_articles=hidden_articles)


@admin_bp.route("/articles/new", methods=["GET", "POST"])
def article_create():
    tours = list_tours()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        destination = request.form.get("destination", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        tour_id = request.form.get("tour_id", "").strip()
        image_url = request.form.get("image_url", "").strip()

        if not title or not destination or not summary or not content or not tour_id:
            flash("Vui lòng nhập đủ thông tin bài viết.", "error")
            return render_template("admin/articles/form.html", article=None, tours=tours, form_action=url_for("admin.article_create"))

        try:
            uploaded_image = save_article_image(request.files.get("image_file"))
            image_url = uploaded_image or image_url
            create_article(title, destination, summary, content, int(tour_id), image_url)
            flash("Đã tạo bài viết mới.", "success")
            return redirect(url_for("admin.articles_index"))
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template("admin/articles/form.html", article=None, tours=tours, form_action=url_for("admin.article_create"))


@admin_bp.route("/articles/<int:article_id>/edit", methods=["GET", "POST"])
def article_edit(article_id):
    article = get_article(article_id)
    if article is None:
        flash("Không tìm thấy bài viết.", "error")
        return redirect(url_for("admin.articles_index"))

    tours = list_tours()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        destination = request.form.get("destination", "").strip()
        summary = request.form.get("summary", "").strip()
        content = request.form.get("content", "").strip()
        tour_id = request.form.get("tour_id", "").strip()
        image_url = request.form.get("image_url", "").strip() or article["image_url"]

        if not title or not destination or not summary or not content or not tour_id:
            flash("Vui lòng nhập đủ thông tin bài viết.", "error")
            return render_template("admin/articles/form.html", article=article, tours=tours, form_action=url_for("admin.article_edit", article_id=article_id))

        try:
            uploaded_image = save_article_image(request.files.get("image_file"))
            if uploaded_image:
                image_url = uploaded_image
            update_article(article_id, title, destination, summary, content, int(tour_id), image_url)
            flash("Đã cập nhật bài viết.", "success")
            return redirect(url_for("admin.articles_index"))
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template("admin/articles/form.html", article=article, tours=tours, form_action=url_for("admin.article_edit", article_id=article_id))


@admin_bp.route("/articles/<int:article_id>/delete", methods=["POST"])
def article_delete(article_id):
    delete_article(article_id)
    flash("Đã xóa bài viết.", "success")
    return redirect(url_for("admin.articles_index"))


@admin_bp.route("/articles/<int:article_id>/visibility", methods=["POST"])
def article_visibility(article_id):
    hidden = request.form.get("hidden", "1") == "1"
    set_article_hidden(article_id, hidden)
    flash("Đã cập nhật trạng thái hiển thị bài viết.", "success")
    return redirect(url_for("admin.articles_index"))


@admin_bp.route("/feedback")
def feedback_index():
    blog_id = request.args.get("blog_id", "all")
    feedback_items = [dict(item) for item in list_feedback(blog_id=blog_id)]
    articles = list_articles()
    review_states = load_state()["review_states"]
    for item in feedback_items:
        item["moderation_status"] = review_states.get(str(item["id"]), "approved")
    return render_template("admin/feedback/index.html", feedback_items=feedback_items, articles=articles, blog_id=blog_id)


@admin_bp.route("/feedback/<int:review_id>/delete", methods=["POST"])
def feedback_delete(review_id):
    delete_feedback(review_id)
    flash("Đã xóa phản hồi.", "success")
    return redirect(url_for("admin.feedback_index"))


@admin_bp.route("/feedback/<int:review_id>/status", methods=["POST"])
def feedback_status(review_id):
    status = request.form.get("status", "approved").strip()
    if status not in {"approved", "hidden"}:
        flash("Trạng thái phản hồi không hợp lệ.", "error")
        return redirect(url_for("admin.feedback_index"))
    set_review_status(review_id, status)
    flash("Đã cập nhật trạng thái phản hồi.", "success")
    return redirect(url_for("admin.feedback_index"))


@admin_bp.route("/menus")
def menus_index():
    category = request.args.get("category", "all").strip()
    availability = request.args.get("availability", "all").strip()
    keyword = request.args.get("keyword", "").strip()
    page_raw = request.args.get("page", "1").strip()

    try:
        page = max(1, int(page_raw))
    except ValueError:
        page = 1

    if availability not in {"all", "available", "unavailable"}:
        availability = "all"

    menu_items, pagination = list_menu_items(
        category=category,
        availability=availability,
        keyword=keyword,
        page=page,
        page_size=10,
    )
    categories = list_menu_categories()
    return render_template(
        "admin/menus/index.html",
        menu_items=menu_items,
        categories=categories,
        category=category,
        availability=availability,
        keyword=keyword,
        pagination=pagination,
    )


def _parse_menu_form(form, files, existing_image_url=""):
    name = form.get("name", "").strip()
    category = form.get("category", "").strip()
    price_raw = form.get("price", "").strip()
    description = form.get("description", "").strip()
    image_url = form.get("image_url", "").strip() or existing_image_url
    is_active = form.get("is_active", "1") == "1"

    if not name:
        raise ValueError("Tên món ăn không được để trống.")
    if not category:
        raise ValueError("Danh mục không được để trống.")

    try:
        price = float(price_raw)
    except ValueError as exc:
        raise ValueError("Giá món ăn không hợp lệ.") from exc

    if price < 0:
        raise ValueError("Giá món ăn không được âm.")

    uploaded_image = save_menu_image(files.get("image_file"))
    if uploaded_image:
        image_url = uploaded_image

    return {
        "name": name,
        "category": category,
        "price": price,
        "description": description,
        "image_url": image_url,
        "is_active": is_active,
    }


@admin_bp.route("/menus/new", methods=["GET", "POST"])
def menu_create():
    categories = list_menu_categories()
    if request.method == "POST":
        try:
            payload = _parse_menu_form(request.form, request.files)
            create_menu_item(**payload)
            flash("Đã thêm món mới vào thực đơn.", "success")
            return redirect(url_for("admin.menus_index"))
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template(
        "admin/menus/form.html",
        menu_item=None,
        categories=categories,
        form_action=url_for("admin.menu_create"),
    )


@admin_bp.route("/menus/<int:food_id>/edit", methods=["GET", "POST"])
def menu_edit(food_id):
    menu_item = get_menu_item(food_id)
    if menu_item is None:
        flash("Không tìm thấy món ăn.", "error")
        return redirect(url_for("admin.menus_index"))

    categories = list_menu_categories()
    if request.method == "POST":
        try:
            payload = _parse_menu_form(request.form, request.files, existing_image_url=menu_item["image_url"] or "")
            update_menu_item(food_id=food_id, **payload)
            flash("Đã cập nhật món ăn.", "success")
            return redirect(url_for("admin.menus_index"))
        except ValueError as exc:
            flash(str(exc), "error")

    return render_template(
        "admin/menus/form.html",
        menu_item=menu_item,
        categories=categories,
        form_action=url_for("admin.menu_edit", food_id=food_id),
    )


@admin_bp.route("/menus/<int:food_id>/toggle", methods=["POST"])
def menu_toggle(food_id):
    is_active = request.form.get("is_active", "0") == "1"
    if toggle_menu_availability(food_id, is_active):
        flash("Đã cập nhật trạng thái món ăn.", "success")
    else:
        flash("Không tìm thấy món ăn để cập nhật.", "error")
    return redirect(url_for("admin.menus_index", **request.args.to_dict()))


@admin_bp.route("/menus/<int:food_id>/delete", methods=["POST"])
def menu_delete(food_id):
    result = delete_menu_item(food_id)
    if result == "deleted":
        flash("Đã xóa món ăn khỏi menu.", "success")
    elif result == "archived":
        flash("Món ăn đã có trong lịch sử đơn, hệ thống chuyển sang Hết hàng thay vì xóa cứng.", "info")
    else:
        flash("Không tìm thấy món ăn để xóa.", "error")
    return redirect(url_for("admin.menus_index", **request.args.to_dict()))


def _serialize_menu_item(menu_item):
    return {
        "id": menu_item["id"],
        "name": menu_item["name"],
        "category": menu_item["category"],
        "price": menu_item["price"],
        "description": menu_item["description"],
        "image": menu_item["image_url"],
        "isAvailable": bool(menu_item["is_active"]),
        "createdAt": menu_item["created_at"],
        "updatedAt": menu_item["updated_at"],
    }


def _parse_menu_payload(payload, *, existing_image_url=""):
    data = payload or {}

    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()
    price_raw = data.get("price", "")
    description = str(data.get("description", "")).strip()
    image_url = str(data.get("image", "")).strip() or existing_image_url

    is_available_raw = data.get("isAvailable", True)
    if isinstance(is_available_raw, bool):
        is_active = is_available_raw
    else:
        is_active = str(is_available_raw).strip().lower() in {"1", "true", "yes", "on"}

    if not name:
        raise ValueError("Tên món ăn không được để trống.")
    if not category:
        raise ValueError("Danh mục không được để trống.")

    try:
        price = float(price_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Giá món ăn không hợp lệ.") from exc

    if price < 0:
        raise ValueError("Giá món ăn không được âm.")

    return {
        "name": name,
        "category": category,
        "price": price,
        "description": description,
        "image_url": image_url,
        "is_active": is_active,
    }


@admin_bp.route("/api/menus", methods=["GET"])
def api_menus_list():
    category = request.args.get("category", "all").strip()
    availability = request.args.get("availability", "all").strip()
    keyword = request.args.get("keyword", "").strip()

    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1

    try:
        page_size = max(1, min(50, int(request.args.get("pageSize", "10"))))
    except ValueError:
        page_size = 10

    if availability not in {"all", "available", "unavailable"}:
        availability = "all"

    rows, pagination = list_menu_items(
        category=category,
        availability=availability,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

    return jsonify(
        {
            "items": [_serialize_menu_item(item) for item in rows],
            "pagination": pagination,
            "filters": {
                "category": category,
                "availability": availability,
                "keyword": keyword,
            },
        }
    )


@admin_bp.route("/api/menus", methods=["POST"])
def api_menus_create():
    payload = request.get_json(silent=True) or {}
    try:
        parsed = _parse_menu_payload(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    food_id = create_menu_item(**parsed)
    menu_item = get_menu_item(food_id)
    return jsonify({"item": _serialize_menu_item(menu_item)}), 201


@admin_bp.route("/api/menus/<int:food_id>", methods=["PUT", "PATCH"])
def api_menus_update(food_id):
    existing = get_menu_item(food_id)
    if existing is None:
        return jsonify({"error": "Không tìm thấy món ăn."}), 404

    payload = request.get_json(silent=True) or {}

    if request.method == "PATCH":
        merged = {
            "name": payload.get("name", existing["name"]),
            "category": payload.get("category", existing["category"]),
            "price": payload.get("price", existing["price"]),
            "description": payload.get("description", existing["description"]),
            "image": payload.get("image", existing["image_url"]),
            "isAvailable": payload.get("isAvailable", bool(existing["is_active"])),
        }
    else:
        merged = payload

    try:
        parsed = _parse_menu_payload(merged, existing_image_url=existing["image_url"] or "")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    update_menu_item(food_id=food_id, **parsed)
    menu_item = get_menu_item(food_id)
    return jsonify({"item": _serialize_menu_item(menu_item)})


@admin_bp.route("/api/menus/<int:food_id>/availability", methods=["PATCH"])
def api_menus_toggle(food_id):
    payload = request.get_json(silent=True) or {}
    is_available_raw = payload.get("isAvailable")
    if is_available_raw is None:
        return jsonify({"error": "Thiếu trường isAvailable."}), 400

    if isinstance(is_available_raw, bool):
        is_active = is_available_raw
    else:
        is_active = str(is_available_raw).strip().lower() in {"1", "true", "yes", "on"}

    if not toggle_menu_availability(food_id, is_active):
        return jsonify({"error": "Không tìm thấy món ăn để cập nhật."}), 404

    menu_item = get_menu_item(food_id)
    return jsonify({"item": _serialize_menu_item(menu_item)})


@admin_bp.route("/api/menus/<int:food_id>", methods=["DELETE"])
def api_menus_delete(food_id):
    result = delete_menu_item(food_id)
    if result == "missing":
        return jsonify({"error": "Không tìm thấy món ăn để xóa."}), 404
    if result == "archived":
        return jsonify({"status": "archived", "message": "Món ăn đã có trong lịch sử đơn nên được chuyển sang hết hàng."})
    return jsonify({"status": "deleted"})
