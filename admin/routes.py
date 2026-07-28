from __future__ import annotations

import os

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from admin.queries import ORDER_STATUSES
from admin.moderation import load_state, set_article_hidden, set_review_status
from admin.services import (
    create_article,
    dashboard_metrics,
    delete_article,
    delete_feedback,
    get_article,
    get_order_detail,
    list_articles,
    list_feedback,
    list_orders,
    list_tours,
    save_article_image,
    update_article,
    update_order_status,
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
