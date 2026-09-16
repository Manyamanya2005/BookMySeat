from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings

from .models import Booking
from .ticket_utils import generate_ticket_pdf


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def send_booking_ticket_email(self, booking_ids):

    bookings = list(
        Booking.objects
        .filter(
            id__in=booking_ids
        )
        .select_related(
            "user",
            "movie",
            "theater",
            "seat",
            "payment",
        )
        .order_by("id")
    )

    if not bookings:
        return "No bookings found."

    first = bookings[0]

    user = first.user
    payment = first.payment

    if not user.email:
        raise ValueError(
            "User does not have an email address."
        )

    if payment is None:
        raise ValueError(
            "Payment record not found."
        )

    if payment.status != "paid":
        raise ValueError(
            "Payment is not marked as paid."
        )

    # ----------------------------------------------------------
    # STRIPE PAYMENT REFERENCE
    # ----------------------------------------------------------

    payment_reference = (
        getattr(
            payment,
            "stripe_payment_id",
            None
        )
        or getattr(
            payment,
            "stripey_payment_id",
            None
        )
        or getattr(
            payment,
            "razorpay_payment_id",
            None
        )
        or str(payment.id)
    )

    # ----------------------------------------------------------
    # GENERATE PDF TICKET
    # ----------------------------------------------------------

    pdf_data = generate_ticket_pdf(
        bookings
    )

    # ----------------------------------------------------------
    # SEAT NUMBERS
    # ----------------------------------------------------------

    seat_numbers = ", ".join(
        str(booking.seat.seat_number)
        for booking in bookings
    )

    # ----------------------------------------------------------
    # EMAIL
    # ----------------------------------------------------------

    email = EmailMessage(
        subject=(
            f"Movie Booking Confirmation - "
            f"{first.movie.name}"
        ),

        body=(
            f"Hello "
            f"{user.get_full_name() or user.username},\n\n"

            "Your movie booking has been confirmed "
            "successfully.\n\n"

            f"Movie: {first.movie.name}\n"
            f"Theater: {first.theater.name}\n"
            f"Show Time: {first.theater.time}\n"
            f"Seats: {seat_numbers}\n"
            f"Booking ID: {first.id}\n"
            f"Payment Reference: {payment_reference}\n"
            f"Payment Status: Paid\n"
            f"Amount: ₹{payment.amount}\n\n"

            "Your professional PDF ticket is attached "
            "to this email.\n\n"

            "The ticket contains a QR code that can be "
            "scanned to verify your ticket.\n\n"

            "Thank you for booking with BookMySeat."
        ),

        from_email=getattr(
            settings,
            "DEFAULT_FROM_EMAIL",
            None
        ),

        to=[
            user.email
        ],
    )

    # ----------------------------------------------------------
    # ATTACH PDF
    # ----------------------------------------------------------

    email.attach(
        f"ticket_{first.id}.pdf",
        pdf_data,
        "application/pdf",
    )

    # ----------------------------------------------------------
    # SEND EMAIL
    # ----------------------------------------------------------

    email.send(
        fail_silently=False
    )

    return "Ticket email sent successfully."