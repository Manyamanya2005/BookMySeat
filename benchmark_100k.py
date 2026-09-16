import time
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate, ExtractHour
from django.utils import timezone

from movies.models import Booking


print("\n" + "=" * 60)
print("BOOKMYSEAT - 100,000 BOOKING ORM PERFORMANCE BENCHMARK")
print("=" * 60)

total = Booking.objects.count()

print(f"\nDataset size: {total:,} bookings")

# ---------------------------------------------------------
# 1. TOTAL BOOKING COUNT
# ---------------------------------------------------------
start = time.perf_counter()

count = Booking.objects.count()

elapsed = time.perf_counter() - start

print("\n1. Total booking count")
print(f"   Result: {count:,}")
print(f"   Time: {elapsed:.4f} seconds")


# ---------------------------------------------------------
# 2. DAILY BOOKING TREND
# ---------------------------------------------------------
start = time.perf_counter()

daily = list(
    Booking.objects
    .values("booked_at__date")
    .annotate(total=Count("id"))
    .order_by("booked_at__date")
)

elapsed = time.perf_counter() - start

print("\n2. Daily booking trend")
print(f"   Groups returned: {len(daily)}")
print(f"   Time: {elapsed:.4f} seconds")


# ---------------------------------------------------------
# 3. MOST BOOKED MOVIES
# ---------------------------------------------------------
start = time.perf_counter()

movies = list(
    Booking.objects
    .values("movie_id")
    .annotate(total=Count("id"))
    .order_by("-total")[:10]
)

elapsed = time.perf_counter() - start

print("\n3. Most booked movies")
print(f"   Movies returned: {len(movies)}")
print(f"   Time: {elapsed:.4f} seconds")


# ---------------------------------------------------------
# 4. TOP-PERFORMING THEATERS
# ---------------------------------------------------------
start = time.perf_counter()

theaters = list(
    Booking.objects
    .values("theater_id")
    .annotate(total=Count("id"))
    .order_by("-total")[:10]
)

elapsed = time.perf_counter() - start

print("\n4. Top-performing theaters")
print(f"   Theaters returned: {len(theaters)}")
print(f"   Time: {elapsed:.4f} seconds")


# ---------------------------------------------------------
# 5. CUSTOM DATE RANGE
# ---------------------------------------------------------
end_date = timezone.now()
start_date = end_date - timedelta(days=30)

start = time.perf_counter()

date_range_count = (
    Booking.objects
    .filter(
        booked_at__gte=start_date,
        booked_at__lt=end_date
    )
    .count()
)

elapsed = time.perf_counter() - start

print("\n5. Custom date-range filtering")
print(f"   Last 30 days: {date_range_count:,} bookings")
print(f"   Time: {elapsed:.4f} seconds")


# ---------------------------------------------------------
# 6. PEAK BOOKING HOURS
# ---------------------------------------------------------
start = time.perf_counter()

peak_hours = list(
    Booking.objects
    .values("booked_at__hour")
    .annotate(total=Count("id"))
    .order_by("-total")
)

elapsed = time.perf_counter() - start

print("\n6. Peak booking hours")
print(f"   Hours returned: {len(peak_hours)}")
print(f"   Time: {elapsed:.4f} seconds")


# ---------------------------------------------------------
# 7. INDEX TEST - booked_at
# ---------------------------------------------------------
print("\n" + "=" * 60)
print("DATABASE QUERY PLAN")
print("=" * 60)

query = Booking.objects.filter(
    booked_at__gte=start_date,
    booked_at__lt=end_date
)

print("\nQuery plan for booked_at date filtering:")
print(query.explain())


# ---------------------------------------------------------
# 8. INDEX TEST - theater + booked_at
# ---------------------------------------------------------
theater_id = Booking.objects.values_list(
    "theater_id", flat=True
).first()

if theater_id:

    query = Booking.objects.filter(
        theater_id=theater_id,
        booked_at__gte=start_date,
        booked_at__lt=end_date
    )

    print("\nQuery plan for theater_id + booked_at:")
    print(query.explain())


# ---------------------------------------------------------
# 9. INDEX TEST - movie + booked_at
# ---------------------------------------------------------
movie_id = Booking.objects.values_list(
    "movie_id", flat=True
).first()

if movie_id:

    query = Booking.objects.filter(
        movie_id=movie_id,
        booked_at__gte=start_date,
        booked_at__lt=end_date
    )

    print("\nQuery plan for movie_id + booked_at:")
    print(query.explain())


# ---------------------------------------------------------
# FINAL
# ---------------------------------------------------------
print("\n" + "=" * 60)
print("PERFORMANCE TEST COMPLETE")
print("=" * 60)

print(f"""
Dataset size: {total:,} bookings

The benchmark tested:
- Total booking count
- Daily booking trend
- Most booked movies
- Top-performing theaters
- Custom date-range filtering
- Peak booking hours

Index query plans tested:
- booked_at
- theater_id + booked_at
- movie_id + booked_at

All calculations use Django ORM aggregation.
Raw Booking objects are not loaded into memory.
""")