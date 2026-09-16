from io import BytesIO
from urllib.parse import urlencode

import qrcode

from django.conf import settings
from django.urls import reverse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)


def generate_ticket_pdf(bookings):

    bookings = list(bookings)

    if not bookings:
        raise ValueError("No booking data supplied.")

    first = bookings[0]

    movie = first.movie
    theater = first.theater

    payment = getattr(first, "payment", None)

    booking_ids = [
        str(booking.id)
        for booking in bookings
    ]

    primary_booking_id = booking_ids[0]

    seats_list = []

    for booking in bookings:
        seat = getattr(booking, "seat", None)

        if seat:
            seat_number = getattr(
                seat,
                "seat_number",
                str(seat)
            )

            seats_list.append(
                str(seat_number)
            )

    seats = ", ".join(seats_list)

    if not seats:
        seats = "N/A"

    screen = (
        getattr(theater, "screen", None)
        or getattr(theater, "screen_name", None)
        or "Screen 1"
    )

    show_time = (
        getattr(theater, "time", None)
        or getattr(first, "show_time", None)
        or getattr(first, "showtime", None)
        or "N/A"
    )

    if payment:

        payment_reference = (
            getattr(payment, "stripe_payment_id", None)
            or getattr(payment, "stripey_payment_id", None)
            or getattr(payment, "stripe_order_id", None)
            or getattr(payment, "razorpay_payment_id", None)
            or getattr(payment, "razorpay_order_id", None)
            or str(payment.id)
        )

        payment_status = getattr(
            payment,
            "status",
            "paid"
        )

        amount = getattr(
            payment,
            "amount",
            None
        )

        if amount is None:
            amount = 0

    else:

        payment_reference = "N/A"

        payment_status = "paid"

        amount = 0

        for booking in bookings:

            seat = getattr(
                booking,
                "seat",
                None
            )

            if seat:

                seat_price = getattr(
                    seat,
                    "price",
                    0
                )

                try:
                    amount += seat_price
                except TypeError:
                    pass


    # ==========================================================
    # VERIFICATION URL
    # ==========================================================

    base_url = getattr(
        settings,
        "SITE_BASE_URL",
        "http://127.0.0.1:8000"
    )

    base_url = str(base_url).rstrip("/")

    verify_path = reverse(
        "verify_ticket"
    )

    query_string = urlencode(
        {
            "booking_id": primary_booking_id
        }
    )

    verify_url = (
        f"{base_url}"
        f"{verify_path}"
        f"?{query_string}"
    )


    # ==========================================================
    # GENERATE QR CODE
    # ==========================================================

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )

    qr.add_data(
        verify_url
    )

    qr.make(
        fit=True
    )

    qr_image_object = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    qr_buffer = BytesIO()

    qr_image_object.save(
        qr_buffer,
        format="PNG"
    )

    qr_buffer.seek(0)


    # ==========================================================
    # PDF BUFFER
    # ==========================================================

    pdf_buffer = BytesIO()


    # ==========================================================
    # PDF DOCUMENT
    # ==========================================================

    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"BookMySeat Ticket {primary_booking_id}",
        author="BookMySeat",
    )


    # ==========================================================
    # STYLES
    # ==========================================================

    styles = getSampleStyleSheet()


    title_style = ParagraphStyle(
        "TicketTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=20,
        leading=24,
        spaceAfter=8,
    )


    subtitle_style = ParagraphStyle(
        "TicketSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=16,
    )


    heading_style = ParagraphStyle(
        "TicketHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=15,
        spaceBefore=8,
        spaceAfter=8,
    )


    normal_style = ParagraphStyle(
        "TicketNormal",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
    )


    # ==========================================================
    # PDF CONTENT
    # ==========================================================

    story = []


    story.append(
        Paragraph(
            "BOOKMYSEAT",
            title_style
        )
    )


    story.append(
        Paragraph(
            "Movie Ticket / Booking Confirmation",
            subtitle_style
        )
    )


    # ==========================================================
    # BOOKING DETAILS
    # ==========================================================

    movie_name = getattr(
        movie,
        "name",
        "N/A"
    )

    theater_name = getattr(
        theater,
        "name",
        "N/A"
    )


    data = [

        [
            "Movie",
            str(movie_name)
        ],

        [
            "Theater",
            str(theater_name)
        ],

        [
            "Screen",
            str(screen)
        ],

        [
            "Show Time",
            str(show_time)
        ],

        [
            "Seats",
            seats
        ],

        [
            "Booking ID",
            primary_booking_id
        ],

        [
            "Payment Reference",
            str(payment_reference)
        ],

        [
            "Payment Status",
            str(payment_status).title()
        ],

        [
            "Amount",
            f"Rs. {amount}"
        ],

    ]


    table = Table(
        data,
        colWidths=[
            48 * mm,
            110 * mm
        ]
    )


    table.setStyle(
        TableStyle(
            [

                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#eeeeee")
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, -1),
                    colors.black
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold"
                ),

                (
                    "FONTNAME",
                    (1, 0),
                    (1, -1),
                    "Helvetica"
                ),

                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    10
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7
                ),

            ]
        )
    )


    story.append(
        table
    )


    story.append(
        Spacer(
            1,
            12
        )
    )


    # ==========================================================
    # QR VERIFICATION
    # ==========================================================

    story.append(
        Paragraph(
            "Ticket Verification",
            heading_style
        )
    )


    qr_image = Image(
        qr_buffer,
        width=42 * mm,
        height=42 * mm
    )


    qr_text = Paragraph(
        "Scan the QR code to verify your ticket.",
        normal_style
    )


    qr_url_text = Paragraph(
        f"Verification ID: {primary_booking_id}",
        normal_style
    )


    qr_content = Table(
        [
            [
                qr_image,
                [
                    qr_text,
                    Spacer(1, 8),
                    qr_url_text,
                ]
            ]
        ],
        colWidths=[
            55 * mm,
            100 * mm
        ]
    )


    qr_content.setStyle(
        TableStyle(
            [

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE"
                ),

                (
                    "ALIGN",
                    (0, 0),
                    (0, 0),
                    "CENTER"
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

            ]
        )
    )


    story.append(
        qr_content
    )


    story.append(
        Spacer(
            1,
            15
        )
    )


    story.append(
        Paragraph(
            "Please carry this ticket while visiting the theater.",
            subtitle_style
        )
    )


    # ==========================================================
    # BUILD PDF
    # ==========================================================

    doc.build(
        story
    )


    pdf_buffer.seek(0)

    return pdf_buffer.getvalue()