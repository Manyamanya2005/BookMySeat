import random
import time
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from movies.models import Booking


TEST_USERNAME = "performance_test_100k"
BATCH_SIZE = 5000


print("\n" + "=" * 60)
print("FIXING 100,000 TEST BOOKING DATES")
print("=" * 60)


user = User.objects.get(
    username=TEST_USERNAME
)

bookings = list(
    Booking.objects
    .filter(user=user)
    .order_by("id")
)


print(
    f"\nBookings found: {len(bookings):,}"
)


if len(bookings) < 100_000:
    print(
        "ERROR: Less than 100,000 test bookings found."
    )
    raise SystemExit


now = timezone.now()

start_time = time.perf_counter()


# ---------------------------------------------------------
# Assign dates across the previous 365 days
# ---------------------------------------------------------

for booking in bookings:

    booking.booked_at = (
        now
        - timedelta(
            days=random.randint(0, 364),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )
    )


# ---------------------------------------------------------
# Update in batches
# ---------------------------------------------------------

for start in range(
    0,
    len(bookings),
    BATCH_SIZE
):

    batch = bookings[
        start:start + BATCH_SIZE
    ]

    Booking.objects.bulk_update(
        batch,
        ["booked_at"],
        batch_size=BATCH_SIZE,
    )

    updated = min(
        start + BATCH_SIZE,
        len(bookings)
    )

    if updated % 25_000 == 0:
        print(
            f"Updated {updated:,} / "
            f"{len(bookings):,}"
        )


elapsed = (
    time.perf_counter()
    - start_time
)


# ---------------------------------------------------------
# Verify
# ---------------------------------------------------------

oldest = (
    Booking.objects
    .filter(user=user)
    .order_by("booked_at")
    .values_list("booked_at", flat=True)
    .first()
)

newest = (
    Booking.objects
    .filter(user=user)
    .order_by("-booked_at")
    .values_list("booked_at", flat=True)
    .first()
)


print("\n" + "=" * 60)
print("DATE CORRECTION COMPLETE")
print("=" * 60)

print(
    f"\nUpdated bookings : {len(bookings):,}"
)

print(
    f"Oldest booking   : {oldest}"
)

print(
    f"Newest booking   : {newest}"
)

print(
    f"Update time      : {elapsed:.2f} seconds"
)

print("\nSUCCESS: Test dates are now distributed across the year.")