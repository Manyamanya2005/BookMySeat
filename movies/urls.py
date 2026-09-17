from django.urls import path
from django.contrib.auth.views import PasswordResetView

from . import views
from . import dashboard_views


urlpatterns = [

    # ==========================================================
    # TASK 4 - ADMIN DASHBOARD
    # ==========================================================

    path(
        "admin-dashboard/",
        dashboard_views.admin_dashboard,
        name="admin_dashboard",
    ),

    path(
        "admin-dashboard/export/",
        dashboard_views.admin_dashboard_export,
        name="admin_dashboard_export",
    ),

    # ==========================================================
    # TASK 5 - MOVIE DISCOVERY
    # SEARCH + FILTERS + SORTING + PAGINATION
    # ==========================================================

    path(
        "",
        views.movie_list,
        name="movie_list",
    ),

    path(
        "movie/<int:movie_id>/",
        views.movie_detail,
        name="movie_detail",
    ),

    # ==========================================================
    # TASK 5 - THEATERS
    # ==========================================================

    path(
        "movie/<int:movie_id>/theaters/",
        views.theater_list,
        name="theater_list",
    ),

    # ==========================================================
    # TASK 5 - SEATS
    # ==========================================================

    path(
        "theater/<int:theater_id>/seats/",
        views.seat_selection,
        name="seat_selection",
    ),

    path(
        "theater/<int:theater_id>/seat-status/",
        views.seat_status,
        name="seat_status",
    ),

    path(
        "theater/<int:theater_id>/reserve/",
        views.reserve_seats,
        name="reserve_seats",
    ),

    # ==========================================================
    # PAYMENT - STRIPE
    # ==========================================================

    path(
        "theater/<int:theater_id>/payment/",
        views.payment_page,
        name="payment_page",
    ),

    path(
        "theater/<int:theater_id>/payment/complete/",
        views.complete_payment,
        name="complete_payment",
    ),

    path(
        "theater/<int:theater_id>/payment/failed/",
        views.payment_failed,
        name="payment_failed",
    ),

    path(
        "theater/<int:theater_id>/payment/cancelled/",
        views.payment_cancelled,
        name="payment_cancelled",
    ),

    # ==========================================================
    # STRIPE WEBHOOK
    # ==========================================================

    path(
        "stripe/webhook/",
        views.stripe_webhook,
        name="stripe_webhook",
    ),

    # ==========================================================
    # BOOKING
    # ==========================================================

    path(
        "seat/<int:seat_id>/booking/",
        views.seat_booking,
        name="seat_booking",
    ),

    path(
        "book-seats/",
        views.book_selected_seats,
        name="book_selected_seats",
    ),

    path(
        "booking/<int:booking_id>/watched/",
        views.mark_watched,
        name="mark_watched",
    ),

    # ==========================================================
    # TASK 6 - TICKET DOWNLOAD
    # ==========================================================

    path(
        "booking/<int:booking_id>/ticket/download/",
        views.download_ticket,
        name="download_ticket",
    ),

    # ==========================================================
    # TASK 6 - TICKET VERIFICATION
    # ==========================================================

    path(
        "ticket/verify/",
        views.verify_ticket,
        name="verify_ticket",
    ),

    # ==========================================================
    # REVIEWS
    # ==========================================================

    path(
        "review/<int:review_id>/edit/",
        views.edit_review,
        name="edit_review",
    ),

    path(
        "review/<int:review_id>/report/",
        views.report_review,
        name="report_review",
    ),

    # ==========================================================
    # PAYMENT RETRY
    # ==========================================================

    path(
        "payment/<int:payment_id>/retry/",
        views.retry_payment,
        name="retry_payment",
    ),

    # ==========================================================
    # PASSWORD RESET
    # ==========================================================

    path(
        "password-reset/",
        PasswordResetView.as_view(
            template_name="users/reset_password.html"
        ),
        name="password_reset",
    ),
]