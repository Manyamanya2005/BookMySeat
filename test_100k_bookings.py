import time
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Count
from django.utils import timezone

from movies.models import Booking, Movie, Theater, Seat


# ============================================================
# SETTINGS
# ============================================================

TEST_USERNAME = "performance_test_100k"
TOTAL_BOOKINGS = 100_000
BATCH_SIZE = 5_000


print("\n" + "=" * 60)
print("BOOKMYSEAT - 100,000 BOOKING PERFORMANCE TEST")
print("=" * 60)


# ============================================================
# 1. CREATE / GET DEDICATED TEST USER
# ============================================================

user, created = User.objects.get_or_create(
    username=TEST_USERNAME,
    defaults={
        "email": "performance_test_100k@example.com",
        "is_active": True,
    },
)

print(f"\nTest user: {user.username}")


# ============================================================
# 2. GET MOVIES
# ============================================================

movies = list(Movie.objects.all())

if not movies:
    print("\nERROR: No movies exist in the database.")
    print("Please add at least one movie first.")
    raise SystemExit

print(f"Movies found: {len(movies)}")


# ============================================================
# 3. GET THEATERS
# ============================================================

theaters = list(
    Theater.objects.select_related("movie").all()
)

if not theaters:
    print("\nERROR: No theaters exist in the database.")
    print("Please add at least one theater first.")
    raise SystemExit

print(f"Theaters found: {len(theaters)}")


# ============================================================
# 4. GROUP SEATS BY THEATER
# ============================================================

all_seats = list(
    Seat.objects.select_related("theater").all()
)

if not all_seats:
    print("\nERROR: No seats exist in the database.")
    print("Please create seats first.")
    raise SystemExit


seats_by_theater = {}

for seat in all_seats:
    seats_by_theater.setdefault(
        seat.theater_id,
        []
    ).append(seat)


valid_theaters = [
    theater
    for theater in theaters
    if theater.id in seats_by_theater
]


if not valid_theaters:
    print("\nERROR: No theater has seats.")
    raise SystemExit


print(f"Seats found: {len(all_seats)}")
print(f"Theaters with seats: {len(valid_theaters)}")


# ============================================================
# 5. REMOVE OLD TEST DATA
# ============================================================

old_count = Booking.objects.filter(
    user=user
).count()

if old_count > 0:

    print(
        f"\nRemoving previous test bookings: "
        f"{old_count:,}"
    )

    Booking.objects.filter(
        user=user
    ).delete()

    print("Previous test data removed.")


# ============================================================
# 6. CREATE 100,000 BOOKINGS
# ============================================================

print("\n" + "=" * 60)
print("CREATING 100,000 TEST BOOKINGS")
print("=" * 60)

start_time = time.perf_counter()

booking_objects = []

now = timezone.now()

for i in range(TOTAL_BOOKINGS):

    # Select a theater
    theater = random.choice(valid_theaters)

    # Select a seat belonging to that theater
    theater_seats = seats_by_theater[theater.id]
    seat = random.choice(theater_seats)

    # Theater already has its movie
    movie = theater.movie

    # Spread booking dates across the last 365 days
    booking_date = (
        now
        - timedelta(
            days=random.randint(0, 364),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )
    )

    booking_objects.append(
        Booking(
            user=user,
            movie=movie,
            theater=theater,
            seat=seat,
            watched=True,
        )
    )

    # Insert in batches
    if len(booking_objects) >= BATCH_SIZE:

        Booking.objects.bulk_create(
            booking_objects,
            batch_size=BATCH_SIZE,
        )

        booking_objects.clear()

        created_count = i + 1

        if created_count % 25_000 == 0:

            elapsed = (
                time.perf_counter()
                - start_time
            )

            print(
                f"Created {created_count:,} / "
                f"{TOTAL_BOOKINGS:,} "
                f"({elapsed:.2f} seconds)"
            )


# Insert remaining records
if booking_objects:

    Booking.objects.bulk_create(
        booking_objects,
        batch_size=BATCH_SIZE,
    )

    booking_objects.clear()


creation_time = (
    time.perf_counter()
    - start_time
)


# ============================================================
# 7. VERIFY 100,000 BOOKINGS
# ============================================================

test_count = Booking.objects.filter(
    user=user
).count()

print("\n" + "=" * 60)
print("TEST DATA VERIFICATION")
print("=" * 60)

print(
    f"\nTest bookings in database: "
    f"{test_count:,}"
)

print(
    f"Creation time: "
    f"{creation_time:.2f} seconds"
)


if test_count < TOTAL_BOOKINGS:

    print(
        "\nERROR: Less than 100,000 bookings "
        "were created."
    )

    raise SystemExit


print(
    "\nSUCCESS: 100,000 bookings exist."
)


# ============================================================
# 8. BENCHMARK - TOTAL BOOKING COUNT
# ============================================================

print("\n" + "=" * 60)
print("ORM PERFORMANCE TEST")
print("=" * 60)


start = time.perf_counter()

total_result = Booking.objects.filter(
    user=user
).count()

count_time = (
    time.perf_counter()
    - start
)

print(
    f"\n1. Total booking count"
)

print(
    f"   Result: {total_result:,}"
)

print(
    f"   Time: {count_time:.4f} seconds"
)


# ============================================================
# 9. BENCHMARK - DAILY BOOKING TREND
# ============================================================

start = time.perf_counter()

daily_trend = list(
    Booking.objects
    .filter(user=user)
    .values("booked_at__date")
    .annotate(
        total_bookings=Count("id")
    )
    .order_by("booked_at__date")
)

daily_time = (
    time.perf_counter()
    - start
)

print(
    "\n2. Daily booking trend"
)

print(
    f"   Groups returned: "
    f"{len(daily_trend)}"
)

print(
    f"   Time: {daily_time:.4f} seconds"
)


# ============================================================
# 10. BENCHMARK - MOST BOOKED MOVIES
# ============================================================

start = time.perf_counter()

movie_results = list(
    Booking.objects
    .filter(user=user)
    .values("movie__name")
    .annotate(
        total_bookings=Count("id")
    )
    .order_by("-total_bookings")
)

movie_time = (
    time.perf_counter()
    - start
)

print(
    "\n3. Most booked movies"
)

print(
    f"   Movies returned: "
    f"{len(movie_results)}"
)

print(
    f"   Time: {movie_time:.4f} seconds"
)


# ============================================================
# 11. BENCHMARK - TOP THEATERS
# ============================================================

start = time.perf_counter()

theater_results = list(
    Booking.objects
    .filter(user=user)
    .values("theater__name")
    .annotate(
        total_bookings=Count("id")
    )
    .order_by("-total_bookings")
)

theater_time = (
    time.perf_counter()
    - start
)

print(
    "\n4. Top-performing theaters"
)

print(
    f"   Theaters returned: "
    f"{len(theater_results)}"
)

print(
    f"   Time: {theater_time:.4f} seconds"
)


# ============================================================
# 12. BENCHMARK - CUSTOM DATE RANGE
# ============================================================

date_start = (
    now - timedelta(days=30)
)

date_end = now

start = time.perf_counter()

last_30_days = Booking.objects.filter(
    user=user,
    booked_at__gte=date_start,
    booked_at__lt=date_end,
).count()

date_time = (
    time.perf_counter()
    - start
)

print(
    "\n5. Custom date-range filtering"
)

print(
    f"   Last 30 days: "
    f"{last_30_days:,} bookings"
)

print(
    f"   Time: {date_time:.4f} seconds"
)


# ============================================================
# 13. QUERY PLAN
# ============================================================

print("\n" + "=" * 60)
print("DATABASE QUERY PLAN")
print("=" * 60)

query = Booking.objects.filter(
    user=user,
    booked_at__gte=date_start,
    booked_at__lt=date_end,
)

try:

    print(
        "\nQuery used for date filtering:\n"
    )

    print(
        query.explain()
    )

except Exception as e:

    print(
        "\nQuery plan could not be displayed:"
    )

    print(e)


# ============================================================
# 14. FINAL PERFORMANCE SUMMARY
# ============================================================

print("\n" + "=" * 60)
print("FINAL PERFORMANCE SUMMARY")
print("=" * 60)

print(
    f"""
Dataset size             : {test_count:,} bookings

Total count query        : {count_time:.4f} sec
Daily trend aggregation  : {daily_time:.4f} sec
Movie aggregation        : {movie_time:.4f} sec
Theater aggregation      : {theater_time:.4f} sec
Date-range query         : {date_time:.4f} sec

Database indexes:
    - booked_at
    - movie_id + booked_at
    - theater_id + booked_at

ORM aggregation:
    - Count()
    - values()
    - annotate()
    - aggregate/filter operations

Memory approach:
    Aggregated results are retrieved instead
    of loading all 100,000 Booking objects.
"""
)

print(
    "SUCCESS: 100,000+ booking performance "
    "test completed."
)

print(
    "\nIMPORTANT:"
)

print(
    "The test records are still in the database."
)

print(
    "Do NOT delete them until we finish "
    "checking the dashboard."
)

print("\n" + "=" * 60)