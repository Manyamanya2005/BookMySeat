import csv
from datetime import datetime, time, timedelta
from decimal import Decimal
import uuid
from io import BytesIO

import stripe

from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.db.models import Avg, Count, Q, Min, Sum
from django.db import transaction, IntegrityError
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.core.mail import EmailMessage
from django.db.models.functions import TruncDate, TruncMonth, ExtractHour
from .task import send_booking_ticket_email

from .models import (
    Movie,
    Theater,
    Seat,
    SeatReservation,
    Booking,
    Payment,
    Event,
    Premiere,
    MusicStudio,
    Review,
)

# ==========================================================
# OPTIONAL CELERY TASK
# ==========================================================
#
# The import is kept here so the rest of the project does
# not crash if Celery has not been configured yet.
#
try:
    from .task import send_booking_ticket_email
except ImportError:
    send_booking_ticket_email = None


# ==========================================================
# HOME
# ==========================================================


# ==========================================================
# HOME
# ==========================================================

def home(request):

    movies = Movie.objects.all().order_by('-id')[:8]

    events = Event.objects.all()

    premieres = Premiere.objects.all()

    music_studios = MusicStudio.objects.all()

    return render(
        request,
        'users/home.html',
        {
            'movies': movies,
            'events': events,
            'premieres': premieres,
            'music_studios': music_studios,
        }
    )
# ==========================================================
# TASK 5
# MOVIE DISCOVERY
# SEARCH + FILTERS + SORTING + PAGINATION
# ==========================================================

def movie_list(request):
    """
    TASK 5 - Movie Discovery

    Supports:
    - title search
    - genre, language, city and theater filters
    - release date filter
    - minimum rating filter
    - show timing filter
    - popularity, newest, rating and ticket-price sorting
    - dynamic matching movie count
    - pagination
    - recommendations based on booking history and recently viewed movies

    All movie filtering and sorting is performed through Django ORM queries.
    """

    # ------------------------------------------------------
    # READ FILTERS
    # ------------------------------------------------------

    search_query = request.GET.get('q', '').strip()
    selected_genre = request.GET.get('genre', '').strip()
    selected_language = request.GET.get('language', '').strip()
    selected_city = request.GET.get('city', '').strip()
    selected_theater = request.GET.get('theater', '').strip()
    selected_release_date = request.GET.get('release_date', '').strip()
    selected_min_rating = request.GET.get('min_rating', '').strip()
    selected_show_time = request.GET.get('show_time', '').strip()
    selected_sort = request.GET.get('sort', 'popularity').strip()

    valid_sorts = {
        'popularity',
        'newest',
        'rating',
        'price_low',
        'price_high',
    }

    if selected_sort not in valid_sorts:
        selected_sort = 'popularity'

    # ------------------------------------------------------
    # BASE QUERYSET
    # ------------------------------------------------------

    movies = (
        Movie.objects
        .all()
        .annotate(
            booking_count=Count(
                'bookings',
                distinct=True,
            ),
            average_rating=Avg(
                'reviews__rating',
                filter=Q(
                    reviews__is_reported=False,
                ),
            ),
            lowest_ticket_price=Min(
                'theaters__seats__price',
            ),
        )
        .prefetch_related(
            'genres',
            'languages',
        )
    )

    # ------------------------------------------------------
    # TITLE SEARCH
    # ------------------------------------------------------

    if search_query:
        movies = movies.filter(
            name__icontains=search_query,
        )

    # ------------------------------------------------------
    # GENRE
    # ------------------------------------------------------
    # Supports both the ManyToMany field and the existing text field.

    if selected_genre:
        movies = movies.filter(
            Q(genres__name__iexact=selected_genre)
            | Q(genre__icontains=selected_genre)
        )

    # ------------------------------------------------------
    # LANGUAGE
    # ------------------------------------------------------
    # Supports both the ManyToMany field and the existing text field.

    if selected_language:
        movies = movies.filter(
            Q(languages__name__iexact=selected_language)
            | Q(language__icontains=selected_language)
        )

    # ------------------------------------------------------
    # CITY / LOCATION
    # ------------------------------------------------------
    # Theater model uses location for the city/location value.

    if selected_city:
        movies = movies.filter(
            theaters__location__icontains=selected_city,
        )

    # ------------------------------------------------------
    # THEATER
    # ------------------------------------------------------
    # IMPORTANT: Movie -> Theater uses related_name='theaters'.
    # Therefore the lookup must be theaters__, not theater__.

    if selected_theater:
        movies = movies.filter(
            theaters__name__iexact=selected_theater,
        )

    # ------------------------------------------------------
    # RELEASE DATE
    # ------------------------------------------------------

    if selected_release_date:
        try:
            release_date_value = datetime.strptime(
                selected_release_date,
                '%Y-%m-%d',
            ).date()

            movies = movies.filter(
                release_date=release_date_value,
            )
        except (TypeError, ValueError):
            selected_release_date = ''

    # ------------------------------------------------------
    # MINIMUM RATING
    # ------------------------------------------------------

    if selected_min_rating:
        try:
            rating_value = float(selected_min_rating)

            if 0 <= rating_value <= 5:
                movies = movies.filter(
                    average_rating__gte=rating_value,
                )
            else:
                selected_min_rating = ''

        except (TypeError, ValueError):
            selected_min_rating = ''

    # ------------------------------------------------------
    # SHOW TIMING
    # ------------------------------------------------------
    # Theater.time is a CharField, so the four UI time groups are
    # translated into database-side regular-expression filters.

    if selected_show_time == 'morning':
        movies = movies.filter(
            theaters__time__iregex=(
                r'^(0?[5-9]|1[01])(:[0-5][0-9])?\s*(AM)?$'
                r'|^(0?[5-9]|1[01]):[0-5][0-9]\s*AM$'
            )
        )

    elif selected_show_time == 'afternoon':
        movies = movies.filter(
            theaters__time__iregex=(
                r'^(12|0?[1-4])(:[0-5][0-9])?\s*PM$'
                r'|^(12|13|14|15|16):[0-5][0-9]$'
            )
        )

    elif selected_show_time == 'evening':
        movies = movies.filter(
            theaters__time__iregex=(
                r'^(0?[5-8])(:[0-5][0-9])?\s*PM$'
                r'|^(17|18|19|20):[0-5][0-9]$'
            )
        )

    elif selected_show_time == 'night':
        movies = movies.filter(
            theaters__time__iregex=(
                r'^(0?[9]|1[0-2])(:[0-5][0-9])?\s*PM$'
                r'|^(0?[1-4])(:[0-5][0-9])?\s*AM$'
                r'|^(0[0-4]|21|22|23):[0-5][0-9]$'
            )
        )

    # Theater and ManyToMany joins can produce duplicate movie rows.
    movies = movies.distinct()

    # ------------------------------------------------------
    # MATCHING MOVIE COUNT
    # ------------------------------------------------------

    matching_movies_count = movies.count()

    # ------------------------------------------------------
    # SORTING
    # ------------------------------------------------------

    if selected_sort == 'newest':
        movies = movies.order_by(
            '-release_date',
            '-id',
        )

    elif selected_sort == 'rating':
        movies = movies.order_by(
            '-average_rating',
            '-booking_count',
            '-id',
        )

    elif selected_sort == 'price_low':
        movies = movies.order_by(
            'lowest_ticket_price',
            '-id',
        )

    elif selected_sort == 'price_high':
        movies = movies.order_by(
            '-lowest_ticket_price',
            '-id',
        )

    else:
        movies = movies.order_by(
            '-booking_count',
            '-average_rating',
            '-id',
        )

    # ------------------------------------------------------
    # PAGINATION
    # ------------------------------------------------------

    paginator = Paginator(
        movies,
        12,
    )

    page_number = request.GET.get(
        'page',
        1,
    )

    movie_page = paginator.get_page(page_number)

    # ------------------------------------------------------
    # FILTER OPTIONS
    # ------------------------------------------------------

    genres = (
        Movie.objects
        .exclude(genre__isnull=True)
        .exclude(genre='')
        .values_list('genre', flat=True)
        .distinct()
        .order_by('genre')
    )

    languages = (
        Movie.objects
        .exclude(language__isnull=True)
        .exclude(language='')
        .values_list('language', flat=True)
        .distinct()
        .order_by('language')
    )

    theaters = (
        Theater.objects
        .all()
        .order_by('name', 'location')
    )

    cities = (
        Theater.objects
        .exclude(location__isnull=True)
        .exclude(location='')
        .values_list('location', flat=True)
        .distinct()
        .order_by('location')
    )

    # ------------------------------------------------------
    # RECOMMENDED FOR YOU
    # ------------------------------------------------------
    # Recommendation signals:
    # 1. Movies from the user's booking history
    # 2. Movies recently viewed in the user's session
    #
    # movie_detail() maintains the session list.

    recommended_movies = []
    recently_viewed_movies = []

    recently_viewed_ids = request.session.get(
        'recently_viewed_movies',
        [],
    )

    # Clean and preserve the session order.
    cleaned_recently_viewed_ids = []

    for movie_id in recently_viewed_ids:
        try:
            movie_id = int(movie_id)
        except (TypeError, ValueError):
            continue

        if movie_id not in cleaned_recently_viewed_ids:
            cleaned_recently_viewed_ids.append(movie_id)

    recently_viewed_ids = cleaned_recently_viewed_ids[:10]

    if recently_viewed_ids:
        viewed_movies = Movie.objects.filter(
            id__in=recently_viewed_ids,
        )

        viewed_movie_map = {
            movie.id: movie
            for movie in viewed_movies
        }

        recently_viewed_movies = [
            viewed_movie_map[movie_id]
            for movie_id in recently_viewed_ids
            if movie_id in viewed_movie_map
        ][:6]

    if request.user.is_authenticated:

        booked_movie_ids = list(
            Booking.objects
            .filter(
                user=request.user,
            )
            .values_list(
                'movie_id',
                flat=True,
            )
            .distinct()
        )

        preference_ids = list(
            dict.fromkeys(
                booked_movie_ids + recently_viewed_ids
            )
        )

        preferred_genres = set()
        preferred_languages = set()

        if preference_ids:
            preference_movies = (
                Movie.objects
                .filter(id__in=preference_ids)
                .values(
                    'genre',
                    'language',
                )
            )

            for item in preference_movies:
                if item['genre']:
                    preferred_genres.add(
                        item['genre'].strip()
                    )

                if item['language']:
                    preferred_languages.add(
                        item['language'].strip()
                    )

        recommendation_filter = Q()

        for preferred_genre in preferred_genres:
            recommendation_filter |= Q(
                genre__icontains=preferred_genre
            )
            recommendation_filter |= Q(
                genres__name__iexact=preferred_genre
            )

        for preferred_language in preferred_languages:
            recommendation_filter |= Q(
                language__icontains=preferred_language
            )
            recommendation_filter |= Q(
                languages__name__iexact=preferred_language
            )

        if preference_ids and recommendation_filter:
            recommended_movies = list(
                Movie.objects
                .filter(recommendation_filter)
                .exclude(id__in=booked_movie_ids)
                .exclude(id__in=recently_viewed_ids)
                .annotate(
                    booking_count=Count(
                        'bookings',
                        distinct=True,
                    ),
                    average_rating=Avg(
                        'reviews__rating',
                        filter=Q(
                            reviews__is_reported=False,
                        ),
                    ),
                )
                .order_by(
                    '-booking_count',
                    '-average_rating',
                    '-rating',
                    '-id',
                )
                .distinct()[:6]
            )

        # Fallback for users without enough history.
        if not recommended_movies:
            recommended_movies = list(
                Movie.objects
                .exclude(id__in=booked_movie_ids)
                .exclude(id__in=recently_viewed_ids)
                .annotate(
                    booking_count=Count(
                        'bookings',
                        distinct=True,
                    ),
                    average_rating=Avg(
                        'reviews__rating',
                        filter=Q(
                            reviews__is_reported=False,
                        ),
                    ),
                )
                .order_by(
                    '-booking_count',
                    '-average_rating',
                    '-rating',
                    '-id',
                )[:6]
            )

    else:
        recommended_movies = list(
            Movie.objects
            .exclude(id__in=recently_viewed_ids)
            .annotate(
                booking_count=Count(
                    'bookings',
                    distinct=True,
                ),
                average_rating=Avg(
                    'reviews__rating',
                    filter=Q(
                        reviews__is_reported=False,
                    ),
                ),
            )
            .order_by(
                '-booking_count',
                '-average_rating',
                '-rating',
                '-id',
            )[:6]
        )

    # ------------------------------------------------------
    # RENDER
    # ------------------------------------------------------

    return render(
        request,
        'movies/movie_list.html',
        {
            'movies': movie_page.object_list,
            'movie_page': movie_page,
            'paginator': paginator,

            'genres': genres,
            'languages': languages,
            'cities': cities,
            'theaters': theaters,

            'search_query': search_query,
            'selected_genre': selected_genre,
            'selected_language': selected_language,
            'selected_city': selected_city,
            'selected_theater': selected_theater,
            'selected_release_date': selected_release_date,
            'selected_min_rating': selected_min_rating,
            'selected_show_time': selected_show_time,
            'selected_sort': selected_sort,

            'matching_movies_count': matching_movies_count,
            'recommended_movies': recommended_movies,
            'recently_viewed_movies': recently_viewed_movies,
        },
    )


# ==========================================================
# MOVIE DETAIL
# ==========================================================

@login_required(login_url='/login/')
def movie_detail(request, movie_id):

    movie = get_object_or_404(
        Movie,
        id=movie_id
    )

    # ------------------------------------------------------
    # RECENTLY VIEWED
    # ------------------------------------------------------

    recently_viewed = request.session.get(
        'recently_viewed_movies',
        []
    )

    movie_id_as_int = movie.id

    recently_viewed = [
        int(movie_id)
        for movie_id in recently_viewed
        if str(movie_id).isdigit()
        and int(movie_id) != movie_id_as_int
    ]

    recently_viewed.insert(
        0,
        movie_id_as_int
    )

    # Keep latest 10
    recently_viewed = recently_viewed[:10]

    request.session[
        'recently_viewed_movies'
    ] = recently_viewed

    request.session.modified = True

    # ------------------------------------------------------
    # REVIEWS
    # ------------------------------------------------------

    reviews = (
        Review.objects
        .filter(
            movie=movie,
            is_reported=False
        )
        .select_related('user')
        .order_by('-created_at')
    )

    # ------------------------------------------------------
    # BOOKING CHECK
    # ------------------------------------------------------

    has_booked = Booking.objects.filter(
        user=request.user,
        movie=movie
    ).exists()

    # ------------------------------------------------------
    # WATCHED CHECK
    # ------------------------------------------------------

    has_watched = Booking.objects.filter(
        user=request.user,
        movie=movie,
        watched=True
    ).exists()

    # ------------------------------------------------------
    # REVIEW CHECK
    # ------------------------------------------------------

    has_reviewed = Review.objects.filter(
        user=request.user,
        movie=movie
    ).exists()

    # ------------------------------------------------------
    # AVERAGE RATING
    # ------------------------------------------------------

    average_rating = (
        Review.objects
        .filter(
            movie=movie,
            is_reported=False
        )
        .aggregate(
            average=Avg('rating')
        )['average']
    )

    if average_rating is not None:
        average_rating = round(
            average_rating,
            1
        )

    # ------------------------------------------------------
    # VERIFIED VIEWERS
    # ------------------------------------------------------

    watched_user_ids = set(
        Booking.objects.filter(
            movie=movie,
            watched=True
        ).values_list(
            'user_id',
            flat=True
        )
    )

    # ------------------------------------------------------
    # SIMILAR MOVIES
    # ------------------------------------------------------

    similar_movies = (
        Movie.objects
        .filter(
            Q(
                genre__icontains=movie.genre
            )
            |
            Q(
                language__iexact=movie.language
            )
        )
        .exclude(
            id=movie.id
        )[:4]
    )

    # ------------------------------------------------------
    # TRENDING MOVIES
    # ------------------------------------------------------

    trending_movies = (
        Movie.objects
        .annotate(
            booking_count=Count(
                'bookings'
            )
        )
        .exclude(
            id=movie.id
        )
        .order_by(
            '-booking_count',
            '-id'
        )[:4]
    )

    # ------------------------------------------------------
    # RECENT MOVIES
    # ------------------------------------------------------

    recent_movies = (
        Movie.objects
        .filter(
            release_date__isnull=False
        )
        .exclude(
            id=movie.id
        )
        .order_by(
            '-release_date'
        )[:4]
    )

    # ------------------------------------------------------
    # REVIEW SUBMISSION
    # ------------------------------------------------------

    if request.method == 'POST':

        if not has_booked or not has_watched:

            return redirect(
                'movie_detail',
                movie_id=movie.id
            )

        if has_reviewed:

            return redirect(
                'movie_detail',
                movie_id=movie.id
            )

        rating = request.POST.get(
            'rating'
        )

        comment = request.POST.get(
            'comment',
            ''
        ).strip()

        if rating and comment:

            try:

                rating = int(rating)

                if 1 <= rating <= 5:

                    Review.objects.create(
                        user=request.user,
                        movie=movie,
                        rating=rating,
                        comment=comment
                    )

            except ValueError:
                pass

        return redirect(
            'movie_detail',
            movie_id=movie.id
        )

    # ------------------------------------------------------
    # RENDER
    # ------------------------------------------------------

    return render(
        request,
        'movies/movie_detail.html',
        {
            'movie': movie,
            'reviews': reviews,

            'has_booked': has_booked,
            'has_watched': has_watched,
            'has_reviewed': has_reviewed,

            'average_rating': average_rating,

            'watched_user_ids':
                watched_user_ids,

            'similar_movies':
                similar_movies,

            'trending_movies':
                trending_movies,

            'recent_movies':
                recent_movies,
        }
    )


# ==========================================================
# THEATER LIST
# ==========================================================

def theater_list(request, movie_id):

    movie = get_object_or_404(
        Movie,
        id=movie_id
    )

    theaters = (
        Theater.objects
        .filter(
            movie_id=movie_id
        )
        .order_by(
            'name',
            'time'
        )
    )

    return render(
        request,
        'movies/theater_list.html',
        {
            'movie': movie,
            'theaters': theaters,
        }
    )


# ==========================================================
# REMOVE EXPIRED RESERVATIONS
# ==========================================================

def remove_expired_reservations():

    SeatReservation.objects.filter(
        expires_at__lte=timezone.now()
    ).delete()


# ==========================================================
# SEAT SELECTION
# ==========================================================

@login_required(login_url='/login/')
def seat_selection(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    remove_expired_reservations()

    seats = (
        Seat.objects
        .filter(
            theater=theater
        )
        .order_by(
            'seat_number'
        )
    )

    now = timezone.now()

    # ------------------------------------------------------
    # CURRENT USER RESERVATIONS
    # ------------------------------------------------------

    user_reservations = (
        SeatReservation.objects
        .filter(
            user=request.user,
            theater=theater,
            expires_at__gt=now
        )
    )

    user_reserved_seat_ids = set(
        user_reservations.values_list(
            'seat_id',
            flat=True
        )
    )

    # ------------------------------------------------------
    # OTHER USERS' RESERVATIONS
    # ------------------------------------------------------

    other_reservations = (
        SeatReservation.objects
        .filter(
            theater=theater,
            expires_at__gt=now
        )
        .exclude(
            user=request.user
        )
    )

    reserved_seat_ids = set(
        other_reservations.values_list(
            'seat_id',
            flat=True
        )
    )

    # ------------------------------------------------------
    # REMAINING TIME
    # ------------------------------------------------------

    remaining_seconds = 0

    if user_reservations.exists():

        earliest_expiry = min(
            reservation.expires_at
            for reservation in user_reservations
        )

        remaining_seconds = max(
            0,
            int(
                (
                    earliest_expiry - now
                ).total_seconds()
            )
        )

    return render(
        request,
        'movies/seat_selection.html',
        {
            'theater': theater,
            'seats': seats,

            'user_reserved_seat_ids':
                user_reserved_seat_ids,

            'reserved_seat_ids':
                reserved_seat_ids,

            'remaining_seconds':
                remaining_seconds,
        }
    )


# ==========================================================
# LIVE SEAT STATUS
# ==========================================================

@login_required(login_url='/login/')
def seat_status(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    remove_expired_reservations()

    now = timezone.now()

    reservations = (
        SeatReservation.objects
        .filter(
            theater=theater,
            expires_at__gt=now
        )
        .select_related(
            'user',
            'seat'
        )
    )

    reservation_map = {
        reservation.seat_id:
            reservation
        for reservation in reservations
    }

    seats = (
        Seat.objects
        .filter(
            theater=theater
        )
        .order_by(
            'seat_number'
        )
    )

    result = []

    remaining_seconds = 0

    for seat in seats:

        if seat.is_booked:

            status = 'booked'

        elif seat.id in reservation_map:

            reservation = reservation_map[
                seat.id
            ]

            if reservation.user_id == request.user.id:

                status = 'my_reserved'

                seconds = max(
                    0,
                    int(
                        (
                            reservation.expires_at
                            - now
                        ).total_seconds()
                    )
                )

                if (
                    remaining_seconds == 0
                    or seconds < remaining_seconds
                ):
                    remaining_seconds = seconds

            else:

                status = 'reserved'

        else:

            status = 'available'

        result.append(
            {
                'id': seat.id,
                'seat_number':
                    seat.seat_number,
                'status': status,
                'seat_type':
                    seat.seat_type,
                'price': str(
                    seat.price
                ),
            }
        )

    return JsonResponse(
        {
            'success': True,
            'seats': result,
            'remaining_seconds':
                remaining_seconds,
        }
    )


# ==========================================================
# RESERVE SELECTED SEATS
# ==========================================================

@login_required(login_url='/login/')
def reserve_seats(request, theater_id):

    if request.method != 'POST':

        return JsonResponse(
            {
                'success': False,
                'message':
                    'Invalid request.'
            },
            status=400
        )

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    remove_expired_reservations()

    now = timezone.now()

    # ------------------------------------------------------
    # GET SELECTED SEATS
    # ------------------------------------------------------

    seat_ids = request.POST.getlist(
        'seat_ids'
    )

    seat_ids = list(
        dict.fromkeys(
            str(seat_id)
            for seat_id in seat_ids
        )
    )

    if not seat_ids:

        return JsonResponse(
            {
                'success': False,
                'message':
                    'Please select at least one seat.'
            }
        )

    # ------------------------------------------------------
    # GET SEATS
    # ------------------------------------------------------

    seats = list(
        Seat.objects.filter(
            id__in=seat_ids,
            theater=theater
        )
    )

    if len(seats) != len(seat_ids):

        return JsonResponse(
            {
                'success': False,
                'message':
                    'One or more selected seats are invalid.'
            }
        )

    # ------------------------------------------------------
    # CHECK BOOKED SEATS
    # ------------------------------------------------------

    booked_seats = [
        seat.seat_number
        for seat in seats
        if seat.is_booked
    ]

    if booked_seats:

        return JsonResponse(
            {
                'success': False,
                'message':
                    'The following seats are already booked: '
                    + ', '.join(
                        booked_seats
                    ),
                'unavailable_seats':
                    booked_seats,
            }
        )

    # ------------------------------------------------------
    # CHECK OTHER USERS' RESERVATIONS
    # ------------------------------------------------------

    other_reservations = (
        SeatReservation.objects
        .filter(
            theater=theater,
            seat_id__in=seat_ids,
            expires_at__gt=now
        )
        .exclude(
            user=request.user
        )
        .select_related('seat')
    )

    if other_reservations.exists():

        unavailable_seats = [
            reservation.seat.seat_number
            for reservation in
            other_reservations
        ]

        return JsonResponse(
            {
                'success': False,
                'message':
                    'One of the selected seats was just '
                    'reserved by another user. Please select again.',
                'unavailable_seats':
                    unavailable_seats,
            }
        )

    # ------------------------------------------------------
    # RESERVE FOR 2 MINUTES
    # ------------------------------------------------------

    expires_at = (
        now + timedelta(minutes=2)
    )

    reserved_ids = []

    try:

        with transaction.atomic():

            for seat in seats:

                existing = (
                    SeatReservation.objects
                    .filter(
                        seat=seat,
                        theater=theater,
                        user=request.user,
                        expires_at__gt=now
                    )
                    .first()
                )

                if existing:

                    existing.expires_at = (
                        expires_at
                    )

                    existing.save(
                        update_fields=[
                            'expires_at'
                        ]
                    )

                    reserved_ids.append(
                        seat.id
                    )

                else:

                    SeatReservation.objects.create(
                        user=request.user,
                        theater=theater,
                        seat=seat,
                        expires_at=expires_at
                    )

                    reserved_ids.append(
                        seat.id
                    )

    except IntegrityError:

        return JsonResponse(
            {
                'success': False,
                'message':
                    'One of the selected seats was just '
                    'reserved by another user. Please select again.'
            }
        )

    return JsonResponse(
        {
            'success': True,
            'seat_ids': reserved_ids,
            'remaining_seconds': 120,
            'message':
                'Seats reserved successfully for 2 minutes.'
        }
    )


# ==========================================================
# STRIPE PAYMENT PAGE
# ==========================================================

@login_required(login_url='/login/')
def payment_page(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    remove_expired_reservations()

    reservations = (
        SeatReservation.objects
        .filter(
            user=request.user,
            theater=theater,
            expires_at__gt=timezone.now()
        )
        .select_related('seat')
    )

    if not reservations.exists():

        return redirect(
            'seat_selection',
            theater_id=theater.id
        )

    now = timezone.now()

    earliest_expiry = min(
        reservation.expires_at
        for reservation in reservations
    )

    remaining_seconds = max(
        0,
        int(
            (
                earliest_expiry - now
            ).total_seconds()
        )
    )

    total_amount = sum(
        (
            reservation.seat.price
            for reservation in reservations
        ),
        Decimal('0.00')
    )

    stripe_amount = int(
        total_amount * 100
    )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    if not stripe.api_key:

        return JsonResponse(
            {
                'error':
                    'Stripe secret key is not configured.'
            },
            status=500
        )

    # ------------------------------------------------------
    # CANCEL OLD PENDING PAYMENT
    # ------------------------------------------------------

    old_payment = (
        Payment.objects
        .filter(
            user=request.user,
            theater=theater,
            status__in=[
                'created',
                'pending'
            ]
        )
        .order_by(
            '-created_at'
        )
        .first()
    )

    if old_payment:

        old_payment.status = 'cancelled'

        old_payment.failure_reason = (
            'Previous payment session replaced.'
        )

        old_payment.save(
            update_fields=[
                'status',
                'failure_reason',
                'updated_at'
            ]
        )

    # ------------------------------------------------------
    # CREATE PAYMENT RECORD
    # ------------------------------------------------------

    payment = Payment.objects.create(
        user=request.user,
        theater=theater,
        amount=total_amount,
        currency='INR',

        stripe_order_id=(
            'TEMP_' +
            uuid.uuid4().hex
        ),

        status='pending'
    )

    stripe_metadata = {
        'payment_id':
            str(payment.id),

        'user_id':
            str(request.user.id),

        'theater_id':
            str(theater.id),
    }

    try:

        line_items = []

        for reservation in reservations:

            seat_price = int(
                reservation.seat.price * 100
            )

            line_items.append(
                {
                    'price_data': {
                        'currency': 'inr',

                        'product_data': {
                            'name':
                                f'{theater.movie.name} - '
                                f'Seat '
                                f'{reservation.seat.seat_number}',
                        },

                        'unit_amount':
                            seat_price,
                    },

                    'quantity': 1,
                }
            )

        checkout_session = (
            stripe.checkout.Session.create(
                mode='payment',

                line_items=line_items,

                customer_email=(
                    request.user.email
                    if request.user.email
                    else None
                ),

                metadata=stripe_metadata,

                payment_intent_data={
                    'metadata':
                        stripe_metadata
                },

                success_url=(
                    request.build_absolute_uri(
                        f'/movies/theater/'
                        f'{theater.id}/payment/complete/'
                    )
                    +
                    '?session_id='
                    '{CHECKOUT_SESSION_ID}'
                ),

                cancel_url=(
                    request.build_absolute_uri(
                        f'/movies/theater/'
                        f'{theater.id}/payment/cancelled/'
                    )
                    +
                    f'?payment_id={payment.id}'
                )
            )
        )

        payment.stripe_order_id = (
            checkout_session.id
        )

        payment.save(
            update_fields=[
                'stripe_order_id',
                'updated_at'
            ]
        )

        return redirect(
            checkout_session.url
        )

    except stripe.error.StripeError as e:

        payment.status = 'failed'

        payment.failure_reason = str(e)

        payment.save(
            update_fields=[
                'status',
                'failure_reason',
                'updated_at'
            ]
        )

        return JsonResponse(
            {
                'error':
                    'Unable to create Stripe payment.',
                'details':
                    str(e)
            },
            status=500
        )


# ==========================================================
# RETRY PAYMENT
# ==========================================================

@login_required(login_url='/login/')
def retry_payment(request, payment_id):

    payment = get_object_or_404(
        Payment,
        id=payment_id,
        user=request.user
    )

    if payment.status not in [
        'failed',
        'cancelled'
    ]:

        return redirect(
            'profile'
        )

    return redirect(
        'seat_selection',
        theater_id=payment.theater.id
    )


# ==========================================================
# COMPLETE STRIPE PAYMENT
# ==========================================================

@login_required(login_url='/login/')
def complete_payment(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    session_id = request.GET.get(
        'session_id'
    )

    if not session_id:

        return redirect(
            'payment_page',
            theater_id=theater.id
        )

    stripe.api_key = settings.STRIPE_SECRET_KEY

    if not stripe.api_key:

        return JsonResponse(
            {
                'error':
                    'Stripe secret key is not configured.'
            },
            status=500
        )

    # ------------------------------------------------------
    # RETRIEVE STRIPE SESSION
    # ------------------------------------------------------

    try:

        checkout_session = (
            stripe.checkout.Session.retrieve(
                session_id
            )
        )

    except stripe.error.StripeError:

        return redirect(
            'payment_page',
            theater_id=theater.id
        )

    # ------------------------------------------------------
    # GET METADATA
    # ------------------------------------------------------

    metadata_obj = getattr(
        checkout_session,
        'metadata',
        None
    )

    if hasattr(
        metadata_obj,
        'to_dict'
    ):

        metadata = metadata_obj.to_dict()

    else:

        metadata = (
            metadata_obj
            or {}
        )

    payment_id = metadata.get(
        'payment_id'
    )

    user_id = metadata.get(
        'user_id'
    )

    stripe_theater_id = metadata.get(
        'theater_id'
    )

    if not payment_id:

        return redirect(
            'seat_selection',
            theater_id=theater.id
        )

    # ------------------------------------------------------
    # VERIFY USER
    # ------------------------------------------------------

    if str(request.user.id) != str(user_id):

        return redirect(
            'seat_selection',
            theater_id=theater.id
        )

    # ------------------------------------------------------
    # VERIFY THEATER
    # ------------------------------------------------------

    if str(theater.id) != str(
        stripe_theater_id
    ):

        return redirect(
            'seat_selection',
            theater_id=theater.id
        )

    # ------------------------------------------------------
    # GET PAYMENT
    # ------------------------------------------------------

    payment = get_object_or_404(
        Payment,
        id=payment_id,
        user=request.user,
        theater=theater
    )

    # ------------------------------------------------------
    # DUPLICATE PAYMENT PROTECTION
    # ------------------------------------------------------

    if payment.status == 'paid':

        return redirect(
            'profile'
        )

    # ------------------------------------------------------
    # VERIFY SESSION ID
    # ------------------------------------------------------

    if (
        checkout_session.id
        != payment.stripe_order_id
    ):

        payment.status = 'failed'

        payment.failure_reason = (
            'Invalid Stripe Checkout Session.'
        )

        payment.save(
            update_fields=[
                'status',
                'failure_reason',
                'updated_at'
            ]
        )

        return redirect(
            'seat_selection',
            theater_id=theater.id
        )

    # ------------------------------------------------------
    # VERIFY PAYMENT STATUS
    # ------------------------------------------------------

    payment_status = getattr(
        checkout_session,
        'payment_status',
        None
    )

    if payment_status != 'paid':

        payment.status = 'failed'

        payment.failure_reason = (
            'Stripe payment was not completed.'
        )

        payment.save(
            update_fields=[
                'status',
                'failure_reason',
                'updated_at'
            ]
        )

        SeatReservation.objects.filter(
            user=request.user,
            theater=theater
        ).delete()

        return redirect(
            'seat_selection',
            theater_id=theater.id
        )

    # ------------------------------------------------------
    # VERIFY AMOUNT
    # ------------------------------------------------------

    expected_amount = int(
        payment.amount * 100
    )

    stripe_amount_total = getattr(
        checkout_session,
        'amount_total',
        None
    )

    if (
        stripe_amount_total
        != expected_amount
    ):

        payment.status = 'failed'

        payment.failure_reason = (
            'Stripe payment amount does not match booking amount.'
        )

        payment.save(
            update_fields=[
                'status',
                'failure_reason',
                'updated_at'
            ]
        )

        SeatReservation.objects.filter(
            user=request.user,
            theater=theater
        ).delete()

        return redirect(
            'seat_selection',
            theater_id=theater.id
        )

    # ------------------------------------------------------
    # GET STRIPE PAYMENT ID
    # ------------------------------------------------------

    stripe_payment_id = getattr(
        checkout_session,
        'payment_intent',
        None
    )

    if not stripe_payment_id:

        stripe_payment_id = (
            checkout_session.id
        )

    # ------------------------------------------------------
    # CONFIRM PAYMENT + CREATE BOOKINGS
    # ------------------------------------------------------

    created_booking_ids = []

    try:

        with transaction.atomic():

            # Lock payment
            payment = (
                Payment.objects
                .select_for_update()
                .get(
                    id=payment.id
                )
            )

            if payment.status == 'paid':

                return redirect(
                    'profile'
                )

            # --------------------------------------------------
            # LOCK RESERVATIONS
            # --------------------------------------------------

            reservations = list(
                SeatReservation.objects
                .select_for_update()
                .select_related(
                    'seat'
                )
                .filter(
                    user=request.user,
                    theater=theater,
                    expires_at__gt=timezone.now()
                )
            )

            if not reservations:

                payment.status = 'failed'

                payment.failure_reason = (
                    'Seat reservation expired before payment confirmation.'
                )

                payment.save(
                    update_fields=[
                        'status',
                        'failure_reason',
                        'updated_at'
                    ]
                )

                return redirect(
                    'seat_selection',
                    theater_id=theater.id
                )

            # --------------------------------------------------
            # VERIFY RESERVATION TOTAL
            # --------------------------------------------------

            reservation_total = sum(
                (
                    reservation.seat.price
                    for reservation in reservations
                ),
                Decimal('0.00')
            )

            if reservation_total != payment.amount:

                payment.status = 'failed'

                payment.failure_reason = (
                    'Reserved seat amount does not match payment amount.'
                )

                payment.save(
                    update_fields=[
                        'status',
                        'failure_reason',
                        'updated_at'
                    ]
                )

                for reservation in reservations:
                    reservation.delete()

                return redirect(
                    'seat_selection',
                    theater_id=theater.id
                )

            # --------------------------------------------------
            # LOCK SEATS
            # --------------------------------------------------

            seat_ids = [
                reservation.seat_id
                for reservation in reservations
            ]

            seats = list(
                Seat.objects
                .select_for_update()
                .filter(
                    id__in=seat_ids,
                    theater=theater
                )
            )

            if len(seats) != len(
                seat_ids
            ):

                payment.status = 'failed'

                payment.failure_reason = (
                    'One or more selected seats are invalid.'
                )

                payment.save(
                    update_fields=[
                        'status',
                        'failure_reason',
                        'updated_at'
                    ]
                )

                return redirect(
                    'seat_selection',
                    theater_id=theater.id
                )

            # --------------------------------------------------
            # CHECK SEATS
            # --------------------------------------------------

            if any(
                seat.is_booked
                for seat in seats
            ):

                payment.status = 'failed'

                payment.failure_reason = (
                    'One or more seats are no longer available.'
                )

                payment.save(
                    update_fields=[
                        'status',
                        'failure_reason',
                        'updated_at'
                    ]
                )

                for reservation in reservations:
                    reservation.delete()

                return redirect(
                    'seat_selection',
                    theater_id=theater.id
                )

            # --------------------------------------------------
            # MARK PAYMENT PAID
            # --------------------------------------------------

            payment.stripey_payment_id = (
                stripe_payment_id
            )

            payment.status = 'paid'

            payment.failure_reason = ''

            payment.save(
                update_fields=[
                    'stripey_payment_id',
                    'status',
                    'failure_reason',
                    'updated_at'
                ]
            )

            # --------------------------------------------------
            # CREATE BOOKINGS
            # --------------------------------------------------

            for reservation in reservations:

                seat = reservation.seat

                existing_booking = (
                    Booking.objects
                    .filter(
                        user=request.user,
                        theater=theater,
                        seat=seat,
                        payment=payment
                    )
                    .first()
                )

                if existing_booking:

                    created_booking_ids.append(
                        existing_booking.id
                    )

                    reservation.delete()

                    continue

                booking = Booking.objects.create(
                    user=request.user,
                    movie=theater.movie,
                    theater=theater,
                    seat=seat,
                    payment=payment
                )

                created_booking_ids.append(
                    booking.id
                )

                seat.is_booked = True

                seat.save(
                    update_fields=[
                        'is_booked'
                    ]
                )

                reservation.delete()

    except IntegrityError:

        return redirect(
            'seat_selection',
            theater_id=theater.id
        )

    # ======================================================
    # TASK 6
    # SEND TICKET ASYNC
    # ======================================================
    #
    # IMPORTANT:
    # We do NOT wait for email delivery.
    #

    if (
        created_booking_ids
        and send_booking_ticket_email
    ):

        try:

            send_booking_ticket_email.delay(
                created_booking_ids
            )

        except Exception:
            # Booking is already successful.
            # Email failure must not cancel booking.
            pass

    return redirect(
        'profile'
    )


# ==========================================================
# PAYMENT FAILED
# ==========================================================

@login_required(login_url='/login/')
def payment_failed(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    payment_id = (
        request.POST.get('payment_id')
        or
        request.GET.get('payment_id')
    )

    payment = None

    if payment_id:

        payment = (
            Payment.objects
            .filter(
                id=payment_id,
                user=request.user,
                theater=theater
            )
            .first()
        )

    if (
        payment
        and payment.status != 'paid'
    ):

        payment.status = 'failed'

        payment.failure_reason = (
            'Payment failed during checkout.'
        )

        payment.save(
            update_fields=[
                'status',
                'failure_reason',
                'updated_at'
            ]
        )

    SeatReservation.objects.filter(
        user=request.user,
        theater=theater
    ).delete()

    return redirect(
        'seat_selection',
        theater_id=theater.id
    )


# ==========================================================
# PAYMENT CANCELLED
# ==========================================================

@login_required(login_url='/login/')
def payment_cancelled(request, theater_id):

    theater = get_object_or_404(
        Theater,
        id=theater_id
    )

    payment_id = (
        request.GET.get('payment_id')
        or
        request.POST.get('payment_id')
    )

    payment = None

    if payment_id:

        payment = (
            Payment.objects
            .filter(
                id=payment_id,
                user=request.user,
                theater=theater
            )
            .first()
        )

    if (
        payment
        and payment.status != 'paid'
    ):

        payment.status = 'cancelled'

        payment.failure_reason = (
            'Payment cancelled by user.'
        )

        payment.save(
            update_fields=[
                'status',
                'failure_reason',
                'updated_at'
            ]
        )

    SeatReservation.objects.filter(
        user=request.user,
        theater=theater
    ).delete()

    return redirect(
        'seat_selection',
        theater_id=theater.id
    )


# ==========================================================
# STRIPE WEBHOOK
# ==========================================================

@csrf_exempt
def stripe_webhook(request):

    if request.method != 'POST':

        return HttpResponse(
            'Method not allowed',
            status=405
        )

    webhook_secret = getattr(
        settings,
        'STRIPE_WEBHOOK_SECRET',
        ''
    )

    if not webhook_secret:

        return JsonResponse(
            {
                'error':
                    'Stripe webhook secret is not configured.'
            },
            status=500
        )

    payload = request.body

    signature = request.META.get(
        'HTTP_STRIPE_SIGNATURE'
    )

    if not signature:

        return JsonResponse(
            {
                'error':
                    'Missing Stripe webhook signature.'
            },
            status=400
        )

    try:

        event = stripe.Webhook.construct_event(
            payload,
            signature,
            webhook_secret
        )

    except ValueError:

        return JsonResponse(
            {
                'error':
                    'Invalid webhook payload.'
            },
            status=400
        )

    except stripe.error.SignatureVerificationError:

        return JsonResponse(
            {
                'error':
                    'Invalid webhook signature.'
            },
            status=400
        )

    # ------------------------------------------------------
    # CHECKOUT COMPLETED
    # ------------------------------------------------------

    if event['type'] == (
        'checkout.session.completed'
    ):

        session = event[
            'data'
        ]['object']

        if hasattr(
            session,
            'to_dict'
        ):

            session_data = (
                session.to_dict()
            )

        else:

            session_data = session

        metadata = (
            session_data.get(
                'metadata'
            )
            or {}
        )

        payment_id = metadata.get(
            'payment_id'
        )

        if payment_id:

            payment = (
                Payment.objects
                .filter(
                    id=payment_id
                )
                .first()
            )

            if payment:

                if payment.status == 'pending':

                    payment.failure_reason = ''

                    payment.save(
                        update_fields=[
                            'failure_reason',
                            'updated_at'
                        ]
                    )

    # ------------------------------------------------------
    # PAYMENT FAILED
    # ------------------------------------------------------

    elif event['type'] == (
        'payment_intent.payment_failed'
    ):

        payment_intent = (
            event['data']['object']
        )

        if hasattr(
            payment_intent,
            'to_dict'
        ):

            payment_intent_data = (
                payment_intent.to_dict()
            )

        else:

            payment_intent_data = (
                payment_intent
            )

        metadata = (
            payment_intent_data.get(
                'metadata'
            )
            or {}
        )

        payment_id = metadata.get(
            'payment_id'
        )

        payment = None

        if payment_id:

            payment = (
                Payment.objects
                .filter(
                    id=payment_id
                )
                .first()
            )

        if (
            payment
            and payment.status != 'paid'
        ):

            last_payment_error = (
                payment_intent_data.get(
                    'last_payment_error'
                )
                or {}
            )

            if hasattr(
                last_payment_error,
                'to_dict'
            ):

                last_payment_error = (
                    last_payment_error.to_dict()
                )

            failure_message = (
                last_payment_error.get(
                    'message',
                    'Stripe payment failed.'
                )
            )

            payment.status = 'failed'

            payment.failure_reason = (
                failure_message
            )

            payment.save(
                update_fields=[
                    'status',
                    'failure_reason',
                    'updated_at'
                ]
            )

            SeatReservation.objects.filter(
                user=payment.user,
                theater=payment.theater
            ).delete()

    return JsonResponse(
        {
            'success': True
        }
    )


# ==========================================================
# SINGLE SEAT BOOKING
# ==========================================================

@login_required(login_url='/login/')
def seat_booking(request, seat_id):

    seat = get_object_or_404(
        Seat,
        id=seat_id
    )

    return redirect(
        'seat_selection',
        theater_id=seat.theater.id
    )


# ==========================================================
# OLD MULTI-SEAT BOOKING
# ==========================================================

@login_required(login_url='/login/')
def book_selected_seats(request):

    seat_ids = request.GET.get(
        'seats',
        ''
    )

    if not seat_ids:

        return redirect(
            'movie_list'
        )

    first_seat_id = (
        seat_ids.split(',')[0]
    )

    try:

        first_seat = Seat.objects.get(
            id=first_seat_id
        )

        return redirect(
            'seat_selection',
            theater_id=first_seat.theater.id
        )

    except Seat.DoesNotExist:

        return redirect(
            'movie_list'
        )


# ==========================================================
# MARK WATCHED
# ==========================================================

@login_required(login_url='/login/')
def mark_watched(request, booking_id):

    booking = get_object_or_404(
        Booking,
        id=booking_id,
        user=request.user
    )

    if request.method == 'POST':

        booking.watched = True

        booking.save(
            update_fields=[
                'watched'
            ]
        )

    return redirect(
        'profile'
    )


# ==========================================================
# EDIT REVIEW
# ==========================================================

@login_required(login_url='/login/')
def edit_review(request, review_id):

    review = get_object_or_404(
        Review,
        id=review_id,
        user=request.user
    )

    if request.method == 'POST':

        rating = request.POST.get(
            'rating'
        )

        comment = request.POST.get(
            'comment',
            ''
        ).strip()

        if rating and comment:

            try:

                rating = int(rating)

                if 1 <= rating <= 5:

                    review.rating = rating
                    review.comment = comment

                    review.save()

                    return redirect(
                        'movie_detail',
                        movie_id=review.movie.id
                    )

            except ValueError:

                pass

    return render(
        request,
        'movies/edit_review.html',
        {
            'review': review,
        }
    )


# ==========================================================
# REPORT REVIEW
# ==========================================================

@login_required(login_url='/login/')
def report_review(request, review_id):

    review = get_object_or_404(
        Review,
        id=review_id
    )

    if request.method == 'POST':

        review.is_reported = True

        review.save(
            update_fields=[
                'is_reported'
            ]
        )

    return redirect(
        'movie_detail',
        movie_id=review.movie.id
    )


# ==========================================================
# TASK 6
# DOWNLOAD BOOKING TICKET
# ==========================================================

@login_required(login_url='/login/')
def download_ticket(request, booking_id):

    booking = get_object_or_404(
        Booking.objects.select_related(
            'movie',
            'theater',
            'seat',
            'payment',
            'user'
        ),
        id=booking_id,
        user=request.user
    )

    # ------------------------------------------------------
    # Get every seat belonging to this payment
    # ------------------------------------------------------

    if not booking.payment or booking.payment.status != 'paid':
        return HttpResponse(
            'Ticket is available only after successful payment.',
            status=400
        )

    bookings = (
        Booking.objects
        .filter(
            user=request.user,
            payment=booking.payment
        )
        .select_related(
            'movie',
            'theater',
            'seat',
            'payment',
            'user'
        )
        .order_by(
            'seat__seat_number'
        )
    )

    try:
        from .ticket_utils import generate_ticket_pdf

        pdf_file = generate_ticket_pdf(
            bookings
        )

    except Exception as e:

        return HttpResponse(
            f'Unable to generate ticket: {e}',
            status=500
        )

    response = HttpResponse(
        pdf_file,
        content_type='application/pdf'
    )

    response[
        'Content-Disposition'
    ] = (
        'attachment; '
        f'filename="ticket_'
        f'{booking.payment_id}.pdf"'
    )

    return response



def verify_ticket(request):
    booking_id = request.GET.get("booking_id")

    if not booking_id:
        return render(
            request,
            "movies/verify_ticket.html",
            {
                "valid": False,
                "message": "No booking ID was provided.",
            },
        )

    try:
        booking = get_object_or_404(
            Booking.objects.select_related(
                "movie",
                "theater",
                "seat",
                "user",
            ),
            id=booking_id,
        )
    except (ValueError, TypeError):
        return render(
            request,
            "movies/verify_ticket.html",
            {
                "valid": False,
                "message": "Invalid booking ID.",
            },
        )

    payment = getattr(booking, "payment", None)

    if payment is None:
        return render(
            request,
            "movies/verify_ticket.html",
            {
                "valid": False,
                "booking": booking,
                "message": "No payment record found for this booking.",
            },
        )

    payment_status = str(
        getattr(payment, "status", "")
    ).lower()

    if payment_status != "paid":
        return render(
            request,
            "movies/verify_ticket.html",
            {
                "valid": False,
                "booking": booking,
                "payment": payment,
                "message": "This ticket is not valid because the payment is not completed.",
            },
        )

    return render(
        request,
        "movies/verify_ticket.html",
        {
            "valid": True,
            "booking": booking,
            "payment": payment,
            "message": "Ticket verified successfully.",
        },
    )
# ==========================================================
# TASK 4 - ADMIN BUSINESS DASHBOARD
# ==========================================================

def _dashboard_date_range(request):
    today = timezone.localdate()

    start_value = request.GET.get("start_date", "").strip()
    end_value = request.GET.get("end_date", "").strip()

    try:
        start_date = (
            datetime.strptime(start_value, "%Y-%m-%d").date()
            if start_value
            else today - timedelta(days=29)
        )
    except (ValueError, TypeError):
        start_date = today - timedelta(days=29)

    try:
        end_date = (
            datetime.strptime(end_value, "%Y-%m-%d").date()
            if end_value
            else today
        )
    except (ValueError, TypeError):
        end_date = today

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    start_datetime = timezone.make_aware(
        datetime.combine(start_date, time.min)
    )

    end_datetime = timezone.make_aware(
        datetime.combine(
            end_date + timedelta(days=1),
            time.min
        )
    )

    return (
        start_date,
        end_date,
        start_datetime,
        end_datetime,
    )


def _period_revenue(start_datetime, end_datetime):
    result = (
        Payment.objects
        .filter(
            status="paid",
            updated_at__gte=start_datetime,
            updated_at__lt=end_datetime,
        )
        .aggregate(total=Sum("amount"))
    )

    return result["total"] or Decimal("0.00")


@login_required(login_url="/admin/login/")
@permission_required(
    "movies.view_business_dashboard",
    raise_exception=True
)
def admin_dashboard(request):

    start_date, end_date, start_datetime, end_datetime = (
        _dashboard_date_range(request)
    )

    today = timezone.localdate()

    # ------------------------------------------------------
    # CURRENT PERIODS
    # ------------------------------------------------------

    today_start = timezone.make_aware(
        datetime.combine(today, time.min)
    )

    tomorrow_start = timezone.make_aware(
        datetime.combine(
            today + timedelta(days=1),
            time.min
        )
    )

    week_start_date = today - timedelta(days=today.weekday())

    week_start = timezone.make_aware(
        datetime.combine(week_start_date, time.min)
    )

    next_week_start = timezone.make_aware(
        datetime.combine(
            week_start_date + timedelta(days=7),
            time.min
        )
    )

    month_start_date = today.replace(day=1)

    if month_start_date.month == 12:
        next_month_date = month_start_date.replace(
            year=month_start_date.year + 1,
            month=1
        )
    else:
        next_month_date = month_start_date.replace(
            month=month_start_date.month + 1
        )

    month_start = timezone.make_aware(
        datetime.combine(month_start_date, time.min)
    )

    next_month_start = timezone.make_aware(
        datetime.combine(next_month_date, time.min)
    )

    year_start_date = today.replace(month=1, day=1)

    year_start = timezone.make_aware(
        datetime.combine(year_start_date, time.min)
    )

    next_year_start = timezone.make_aware(
        datetime.combine(
            year_start_date.replace(
                year=year_start_date.year + 1
            ),
            time.min
        )
    )

    # ------------------------------------------------------
    # REVENUE
    # Only successful PAID payments are revenue.
    # ------------------------------------------------------

    revenue_today = _period_revenue(
        today_start,
        tomorrow_start
    )

    revenue_week = _period_revenue(
        week_start,
        next_week_start
    )

    revenue_month = _period_revenue(
        month_start,
        next_month_start
    )

    revenue_year = _period_revenue(
        year_start,
        next_year_start
    )

    selected_revenue = _period_revenue(
        start_datetime,
        end_datetime
    )

    # ------------------------------------------------------
    # SELECTED BOOKINGS
    # ------------------------------------------------------

    booking_queryset = (
        Booking.objects
        .filter(
            booked_at__gte=start_datetime,
            booked_at__lt=end_datetime
        )
    )

    total_bookings = booking_queryset.count()

    # ------------------------------------------------------
    # BOOKING TRENDS
    # ------------------------------------------------------

    booking_trend_data = [
        {
            "day": item["day"],
            "bookings": item["bookings"],
        }
        for item in (
            booking_queryset
            .annotate(day=TruncDate("booked_at"))
            .values("day")
            .annotate(bookings=Count("id"))
            .order_by("day")
        )
    ]

    # ------------------------------------------------------
    # MOST BOOKED MOVIES
    # ------------------------------------------------------

    most_booked_movies = [
        {
            "movie__name": item["movie__name"],
            "bookings": item["bookings"],
            "booking_count": item["bookings"],
        }
        for item in (
            booking_queryset
            .values("movie_id", "movie__name")
            .annotate(bookings=Count("id"))
            .order_by("-bookings", "movie__name")[:10]
        )
    ]

    # ------------------------------------------------------
    # THEATER OCCUPANCY
    # ------------------------------------------------------
    # Capacity comes from the actual Seat records for each
    # Theater record. Bookings are counted independently so
    # Seat/Booking JOIN multiplication cannot occur.
    #
    # IMPORTANT: count Booking rows here, not distinct seat IDs.
    # The project contains large test data (100,000+ bookings),
    # and a seat can appear in different booking records over
    # the selected period.

    relevant_theater_ids = set(
        Theater.objects
        .filter(
            date__gte=start_date,
            date__lte=end_date
        )
        .values_list(
            "id",
            flat=True
        )
    )

    relevant_theater_ids.update(
        booking_queryset
        .values_list(
            "theater_id",
            flat=True
        )
        .distinct()
    )

    # ------------------------------------------------------
    # BOOKED SEATS / BOOKINGS PER THEATER
    # ------------------------------------------------------
    # Count booking rows by theater once. This is intentionally a
    # separate aggregation from seat-capacity counting so a JOIN
    # between Seat and Booking cannot multiply rows.

    booked_seat_map = {
        item["theater_id"]: item["booked_seats"]
        for item in (
            booking_queryset
            .values("theater_id")
            .annotate(booked_seats=Count("id"))
        )
    }

    # ------------------------------------------------------
    # THEATER DETAILS + TOTAL SEATS
    # ------------------------------------------------------
    # Count the physical Seat rows directly through the Theater
    # relationship. This keeps capacity tied to the actual theater
    # and avoids a separate seat-capacity dictionary becoming stale.

    theaters_for_occupancy = (
        Theater.objects
        .filter(
            id__in=relevant_theater_ids
        )
        .select_related(
            "movie"
        )
        .annotate(
            total_seats=Count(
                "seats",
                distinct=True
            )
        )
        .order_by(
            "name",
            "id"
        )
    )

    theater_occupancy = []

    for theater in theaters_for_occupancy:

        total_seats = theater.total_seats or 0

        booked_seats = (
            booked_seat_map.get(
                theater.id,
                0
            )
            or 0
        )

        # Do not allow occupancy to exceed physical capacity.
        # This protects the dashboard when historical/demo data
        # contains more booking rows than the current seat capacity.
        display_booked_seats = min(
            booked_seats,
            total_seats
        ) if total_seats > 0 else 0

        occupancy = (
            round(
                (display_booked_seats / total_seats) * 100,
                2
            )
            if total_seats > 0
            else 0
        )

        occupancy = min(
            max(occupancy, 0),
            100
        )

        theater_occupancy.append({
            "name": theater.name,
            "location": theater.location,
            "movie": (
                theater.movie.name
                if theater.movie
                else "All Shows"
            ),
            "movie__name": (
                theater.movie.name
                if theater.movie
                else "All Shows"
            ),
            "show_date": theater.date,
            "date": theater.date,
            "show_time": theater.time,
            "time": theater.time,
            "total_seats": total_seats,
            "booked_seats": display_booked_seats,
            "occupancy": occupancy,
            "occupancy_percentage": occupancy,
        })

    # ------------------------------------------------------
    # TOP PERFORMING THEATERS
    #
    # Revenue is calculated ONLY from paid payments.
    # Bookings are grouped by Theater ID.
    # ------------------------------------------------------

    theater_booking_totals = (
        booking_queryset
        .values(
            "theater_id",
            "theater__name",
            "theater__location",
        )
        .annotate(booking_count=Count("id"))
    )

    theater_revenue_totals = (
        Payment.objects
        .filter(
            status="paid",
            updated_at__gte=start_datetime,
            updated_at__lt=end_datetime
        )
        .values(
            "theater_id",
            "theater__name",
            "theater__location",
        )
        .annotate(revenue=Sum("amount"))
    )

    theater_booking_map = {
        item["theater_id"]: item
        for item in theater_booking_totals
    }

    theater_revenue_map = {
        item["theater_id"]: item
        for item in theater_revenue_totals
    }

    top_theaters = []

    for theater_id in (
        set(theater_booking_map.keys())
        | set(theater_revenue_map.keys())
    ):
        booking_item = theater_booking_map.get(
            theater_id,
            {}
        )

        revenue_item = theater_revenue_map.get(
            theater_id,
            {}
        )

        theater_name = (
            booking_item.get("theater__name")
            or revenue_item.get("theater__name")
            or ""
        )

        theater_location = (
            booking_item.get("theater__location")
            or revenue_item.get("theater__location")
            or ""
        )

        theater_revenue = (
            revenue_item.get("revenue")
            or Decimal("0.00")
        )

        theater_booking_count = (
            booking_item.get("booking_count")
            or 0
        )

        top_theaters.append(
            {
                "name": theater_name,
                "theater__name": theater_name,
                "location": theater_location,
                "theater__location": theater_location,
                "revenue": theater_revenue,
                "booking_count": theater_booking_count,
                "bookings": theater_booking_count,
            }
        )

    top_theaters.sort(
        key=lambda row: (
            row["revenue"],
            row["booking_count"],
            row["name"] or "",
        ),
        reverse=True
    )

    top_theaters = top_theaters[:10]

    # ------------------------------------------------------
    # PEAK BOOKING HOURS
    # ------------------------------------------------------

    peak_hours = []

    peak_hours_queryset = (
        booking_queryset
        .annotate(hour=ExtractHour("booked_at"))
        .values("hour")
        .annotate(bookings=Count("id"))
        .order_by("-bookings", "hour")
    )

    for item in peak_hours_queryset:
        hour = item["hour"]

        if hour is None:
            continue

        if hour == 0:
            display_hour = "12:00 AM"
        elif hour < 12:
            display_hour = f"{hour}:00 AM"
        elif hour == 12:
            display_hour = "12:00 PM"
        else:
            display_hour = f"{hour - 12}:00 PM"

        peak_hours.append(
            {
                "hour_display": display_hour,
                "hour": display_hour,
                "bookings": item["bookings"],
                "booking_count": item["bookings"],
            }
        )

    peak_hours = peak_hours[:10]

    # ------------------------------------------------------
    # PAYMENT STATISTICS
    # ------------------------------------------------------

    cancellation_count = 0
    cancellation_amount = Decimal("0.00")

    refund_count = 0
    refund_amount = Decimal("0.00")

    failed_payment_count = 0
    failed_payment_amount = Decimal("0.00")

    paid_count = 0
    paid_amount = Decimal("0.00")

    payment_statistics = (
        Payment.objects
        .filter(
            updated_at__gte=start_datetime,
            updated_at__lt=end_datetime
        )
        .values("status")
        .annotate(
            count=Count("id"),
            amount=Sum("amount")
        )
    )

    for item in payment_statistics:
        status = item["status"]
        count = item["count"]
        amount = item["amount"] or Decimal("0.00")

        if status == "cancelled":
            cancellation_count = count
            cancellation_amount = amount

        elif status == "refunded":
            refund_count = count
            refund_amount = amount

        elif status == "failed":
            failed_payment_count = count
            failed_payment_amount = amount

        elif status == "paid":
            paid_count = count
            paid_amount = amount

    # ------------------------------------------------------
    # USERS
    # ------------------------------------------------------

    total_users = User.objects.count()

    user_growth = [
        {
            "day": item["day"],
            "date": item["day"],
            "users": item["users"],
            "user_count": item["users"],
        }
        for item in (
            User.objects
            .filter(
                date_joined__gte=start_datetime,
                date_joined__lt=end_datetime
            )
            .annotate(day=TruncDate("date_joined"))
            .values("day")
            .annotate(users=Count("id"))
            .order_by("day")
        )
    ]

    # ------------------------------------------------------
    # BOOKING RECORDS / PAGINATION
    # ------------------------------------------------------

    booking_records_queryset = (
        booking_queryset
        .select_related(
            "user",
            "movie",
            "theater",
            "seat",
            "payment"
        )
        .values(
            "id",
            "user__username",
            "movie__name",
            "theater__name",
            "theater__location",
            "seat__seat_number",
            "booked_at",
            "payment__status",
            "payment__amount",
        )
        .order_by("id")
    )

    paginator = Paginator(
        booking_records_queryset,
        100
    )

    booking_page = paginator.get_page(
        request.GET.get("page", 1)
    )

    # ------------------------------------------------------
    # REVENUE BY DAY / MONTH
    # ------------------------------------------------------

    revenue_by_day = [
        {
            "date": item["day"],
            "revenue": float(item["revenue"] or 0),
        }
        for item in (
            Payment.objects
            .filter(
                status="paid",
                updated_at__gte=start_datetime,
                updated_at__lt=end_datetime
            )
            .annotate(day=TruncDate("updated_at"))
            .values("day")
            .annotate(revenue=Sum("amount"))
            .order_by("day")
        )
    ]

    revenue_by_month = [
        {
            "month": item["month"],
            "revenue": float(item["revenue"] or 0),
        }
        for item in (
            Payment.objects
            .filter(
                status="paid",
                updated_at__gte=start_datetime,
                updated_at__lt=end_datetime
            )
            .annotate(month=TruncMonth("updated_at"))
            .values("month")
            .annotate(revenue=Sum("amount"))
            .order_by("month")
        )
    ]

    # ------------------------------------------------------
    # TEMPLATE CONTEXT
    #
    # Both the clean names and compatibility aliases are
    # supplied so the dashboard template does not show blanks.
    # ------------------------------------------------------

    context = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),

        "revenue_today": revenue_today,
        "revenue_week": revenue_week,
        "revenue_month": revenue_month,
        "revenue_year": revenue_year,
        "selected_revenue": selected_revenue,

        # Names used by the current dashboard template.
        "daily_revenue": revenue_today,
        "weekly_revenue": revenue_week,
        "monthly_revenue": revenue_month,
        "yearly_revenue": revenue_year,
        "revenue_range": selected_revenue,

        "total_bookings": total_bookings,

        "paid_count": paid_count,
        "paid_amount": paid_amount,
        "total_paid_transactions": paid_count,

        "total_users": total_users,

        "cancellation_count": cancellation_count,
        "cancellation_amount": cancellation_amount,

        "refund_count": refund_count,
        "refund_amount": refund_amount,

        "failed_count": failed_payment_count,
        "failed_amount": failed_payment_amount,
        "failed_payment_count": failed_payment_count,
        "failed_payment_amount": failed_payment_amount,

        "booking_trend": booking_trend_data,
        "booking_trends": booking_trend_data,

        "most_booked_movies": most_booked_movies,

        "theater_occupancy": theater_occupancy,

        "top_theaters": top_theaters,

        "peak_hours": peak_hours,
        "peak_booking_hours": peak_hours,

        "user_growth": user_growth,

        "revenue_by_day": revenue_by_day,
        "revenue_by_month": revenue_by_month,

        "booking_page": booking_page,
        "booking_records": booking_page,
        "all_booking_details": booking_page,

        "generated_at": timezone.now(),
    }

    return render(
        request,
        "movies/admin_dashboard.html",
        context
    )


# ==========================================================
# ADMIN DASHBOARD CSV EXPORT
# ==========================================================

class Echo:
    def write(self, value):
        return value


@login_required(login_url="/admin/login/")
@permission_required(
    "movies.view_business_dashboard",
    raise_exception=True
)
def admin_dashboard_export(request):
    (
        start_date,
        end_date,
        start_datetime,
        end_datetime,
    ) = _dashboard_date_range(request)

    pseudo_buffer = Echo()

    def rows():
        yield ["BOOKMYSEAT ADMIN DASHBOARD"]
        yield ["Start Date", start_date]
        yield ["End Date", end_date]
        yield []

        selected_revenue = (
            Payment.objects
            .filter(
                status="paid",
                updated_at__gte=start_datetime,
                updated_at__lt=end_datetime
            )
            .aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        selected_bookings = Booking.objects.filter(
            booked_at__gte=start_datetime,
            booked_at__lt=end_datetime
        )

        total_bookings = selected_bookings.count()

        yield ["SUMMARY"]
        yield ["Total Bookings", total_bookings]
        yield ["Selected Period Revenue", selected_revenue]
        yield []

        # --------------------------------------------------
        # BOOKING TRENDS
        # --------------------------------------------------

        yield ["BOOKING TRENDS"]
        yield ["Date", "Bookings"]

        booking_trend = (
            selected_bookings
            .annotate(day=TruncDate("booked_at"))
            .values("day")
            .annotate(bookings=Count("id"))
            .order_by("day")
        )

        for item in booking_trend:
            yield [
                item["day"],
                item["bookings"]
            ]

        yield []

        # --------------------------------------------------
        # MOST BOOKED MOVIES
        # --------------------------------------------------

        yield ["MOST BOOKED MOVIES"]
        yield ["Movie", "Bookings"]

        movies = (
            selected_bookings
            .values("movie__name")
            .annotate(booking_count=Count("id"))
            .order_by(
                "-booking_count",
                "movie__name"
            )
        )

        for movie in movies:
            yield [
                movie["movie__name"],
                movie["booking_count"]
            ]

        yield []

        # --------------------------------------------------
        # THEATER OCCUPANCY
        # --------------------------------------------------

        yield ["THEATER OCCUPANCY"]

        yield [
            "Theater",
            "Location",
            "Movie",
            "Show Date",
            "Show Time",
            "Total Seats",
            "Booked Seats",
            "Occupancy %",
        ]

        export_theater_ids = set(
            Theater.objects
            .filter(
                date__gte=start_date,
                date__lte=end_date
            )
            .values_list("id", flat=True)
        )

        export_theater_ids.update(
            selected_bookings
            .values_list("theater_id", flat=True)
            .distinct()
        )

        # Aggregate capacity once per theater.
        seat_capacity_map = {
            item["theater_id"]: item["total_seats"]
            for item in (
                Seat.objects
                .filter(theater_id__in=export_theater_ids)
                .values("theater_id")
                .annotate(total_seats=Count("id"))
            )
        }

        # Aggregate booked seats once per theater.
        booked_capacity_map = {
            item["theater_id"]: item["booked_seats"]
            for item in (
                selected_bookings
                .values("theater_id")
                .annotate(
                    booked_seats=Count("id")
                )
            )
        }

        export_theaters = (
            Theater.objects
            .filter(id__in=export_theater_ids)
            .select_related("movie")
            .order_by("date", "name", "id")
        )

        for theater in export_theaters:
            total_seats = seat_capacity_map.get(theater.id, 0) or 0
            booked_seats = booked_capacity_map.get(theater.id, 0) or 0

            display_booked_seats = (
                min(booked_seats, total_seats)
                if total_seats > 0
                else 0
            )

            occupancy = (
                round(
                    (display_booked_seats / total_seats) * 100,
                    2
                )
                if total_seats > 0
                else 0
            )

            occupancy = min(max(occupancy, 0), 100)

            yield [
                theater.name,
                theater.location,
                theater.movie.name if theater.movie else "All Shows",
                theater.date,
                theater.time,
                total_seats,
                display_booked_seats,
                occupancy,
            ]

        yield []

        # --------------------------------------------------
        # TOP PERFORMING THEATERS
        # --------------------------------------------------

        yield ["TOP PERFORMING THEATERS"]

        yield [
            "Theater",
            "Location",
            "Revenue",
            "Bookings",
        ]

        theater_bookings = (
            selected_bookings
            .values(
                "theater_id",
                "theater__name",
                "theater__location",
            )
            .annotate(
                booking_count=Count("id")
            )
        )

        theater_revenue = (
            Payment.objects
            .filter(
                status="paid",
                updated_at__gte=start_datetime,
                updated_at__lt=end_datetime
            )
            .values(
                "theater_id",
                "theater__name",
                "theater__location",
            )
            .annotate(
                revenue=Sum("amount")
            )
        )

        booking_map = {
            item["theater_id"]: item
            for item in theater_bookings
        }

        revenue_map = {
            item["theater_id"]: item
            for item in theater_revenue
        }

        top_theaters = []

        for theater_id in (
            set(booking_map.keys())
            | set(revenue_map.keys())
        ):
            booking_item = booking_map.get(
                theater_id,
                {}
            )

            revenue_item = revenue_map.get(
                theater_id,
                {}
            )

            top_theaters.append(
                {
                    "name": (
                        booking_item.get("theater__name")
                        or revenue_item.get("theater__name")
                        or ""
                    ),
                    "location": (
                        booking_item.get("theater__location")
                        or revenue_item.get("theater__location")
                        or ""
                    ),
                    "revenue": (
                        revenue_item.get("revenue")
                        or Decimal("0.00")
                    ),
                    "bookings": (
                        booking_item.get("booking_count")
                        or 0
                    ),
                }
            )

        top_theaters.sort(
            key=lambda row: (
                row["revenue"],
                row["bookings"],
                row["name"],
            ),
            reverse=True
        )

        for theater in top_theaters[:10]:
            yield [
                theater["name"],
                theater["location"],
                theater["revenue"],
                theater["bookings"],
            ]

        yield []

        # --------------------------------------------------
        # PEAK BOOKING HOURS
        # --------------------------------------------------

        yield ["PEAK BOOKING HOURS"]
        yield ["Hour", "Bookings"]

        peak_hours = (
            selected_bookings
            .annotate(hour=ExtractHour("booked_at"))
            .values("hour")
            .annotate(bookings=Count("id"))
            .order_by("-bookings", "hour")
        )

        for item in peak_hours:
            hour = item["hour"]

            if hour is None:
                continue

            if hour == 0:
                display_hour = "12:00 AM"
            elif hour < 12:
                display_hour = f"{hour}:00 AM"
            elif hour == 12:
                display_hour = "12:00 PM"
            else:
                display_hour = f"{hour - 12}:00 PM"

            yield [
                display_hour,
                item["bookings"]
            ]

        yield []

        # --------------------------------------------------
        # PAYMENT STATISTICS
        # --------------------------------------------------

        yield ["PAYMENT STATISTICS"]
        yield ["Status", "Count", "Amount"]

        payment_statistics = (
            Payment.objects
            .filter(
                updated_at__gte=start_datetime,
                updated_at__lt=end_datetime
            )
            .values("status")
            .annotate(
                count=Count("id"),
                amount=Sum("amount")
            )
            .order_by("status")
        )

        for item in payment_statistics:
            yield [
                item["status"],
                item["count"],
                item["amount"] or Decimal("0.00")
            ]

        yield []

        # --------------------------------------------------
        # USER GROWTH
        # --------------------------------------------------

        yield ["USER GROWTH"]
        yield ["Date", "New Users"]

        user_growth = (
            User.objects
            .filter(
                date_joined__gte=start_datetime,
                date_joined__lt=end_datetime
            )
            .annotate(day=TruncDate("date_joined"))
            .values("day")
            .annotate(user_count=Count("id"))
            .order_by("day")
        )

        for item in user_growth:
            yield [
                item["day"],
                item["user_count"]
            ]

        yield []

        # --------------------------------------------------
        # ALL BOOKING DETAILS
        # --------------------------------------------------

        yield ["ALL BOOKING DETAILS"]

        yield [
            "Booking ID",
            "User",
            "Movie",
            "Theater",
            "Location",
            "Seat",
            "Booked At",
            "Payment Status",
            "Amount",
        ]

        bookings = (
            selected_bookings
            .select_related(
                "user",
                "movie",
                "theater",
                "seat",
                "payment"
            )
            .order_by("id")
        )

        for booking in bookings.iterator(
            chunk_size=2000
        ):
            payment_status = ""
            amount = ""

            if booking.payment:
                payment_status = booking.payment.status
                amount = booking.payment.amount

            yield [
                booking.id,
                booking.user.username if booking.user else "",
                booking.movie.name if booking.movie else "",
                booking.theater.name if booking.theater else "",
                booking.theater.location if booking.theater else "",
                booking.seat.seat_number if booking.seat else "",
                booking.booked_at,
                payment_status,
                amount,
            ]

    response = StreamingHttpResponse(
        (
            csv.writer(pseudo_buffer).writerow(row)
            for row in rows()
        ),
        content_type="text/csv"
    )

    response["Content-Disposition"] = (
        "attachment; "
        f'filename="bookmyseat_dashboard_'
        f'{start_date}_{end_date}.csv"'
    )

    return response
