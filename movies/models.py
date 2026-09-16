from django.db import models
from django.contrib.auth.models import User


class Genre(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True
    )

    def __str__(self):
        return self.name


class Language(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True
    )

    def __str__(self):
        return self.name


class CastMember(models.Model):
    name = models.CharField(
        max_length=200
    )

    def __str__(self):
        return self.name


class Movie(models.Model):

    name = models.CharField(
        max_length=200
    )

    image = models.ImageField(
        upload_to='movies/'
    )

    rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=0.0
    )

    cast = models.TextField(
        blank=True
    )

    genres = models.ManyToManyField(
        Genre,
        blank=True,
        related_name='movies'
    )

    languages = models.ManyToManyField(
        Language,
        blank=True,
        related_name='movies'
    )

    cast_members = models.ManyToManyField(
        CastMember,
        blank=True,
        related_name='movies'
    )

    genre = models.CharField(
        max_length=200,
        blank=True
    )

    language = models.CharField(
        max_length=200,
        blank=True
    )

    certification = models.CharField(
        max_length=20,
        blank=True
    )

    duration = models.CharField(
        max_length=50,
        blank=True
    )

    release_date = models.DateField(
        null=True,
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    trailer_url = models.URLField(
        blank=True
    )

    trailer_video = models.FileField(
        upload_to='trailers/',
        blank=True,
        null=True
    )

    class Meta:
        permissions = [
            (
                'view_business_dashboard',
                'Can view BookMySeat business dashboard'
            ),
        ]

        indexes = [
            models.Index(
                fields=['name'],
                name='movie_name_idx'
            ),
            models.Index(
                fields=['release_date'],
                name='movie_release_idx'
            ),
            models.Index(
                fields=['rating'],
                name='movie_rating_idx'
            ),
        ]

    def __str__(self):
        return self.name


class Theater(models.Model):

    name = models.CharField(
        max_length=200
    )

    location = models.CharField(
        max_length=300
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='theaters'
    )

    date = models.DateField(
        null=True,
        blank=True
    )

    time = models.CharField(
        max_length=100,
        default='10:00 AM'
    )

    class Meta:
        indexes = [
            models.Index(
                fields=['date'],
                name='theater_date_idx'
            ),
            models.Index(
                fields=['movie', 'date'],
                name='theater_movie_date_idx'
            ),
            models.Index(
                fields=['name', 'location'],
                name='theater_name_location_idx'
            ),
            models.Index(
                fields=['movie', 'time'],
                name='theater_movie_time_idx'
            ),
        ]

    def __str__(self):
        return self.name


class Seat(models.Model):

    SEAT_TYPE_CHOICES = [
        ('regular', 'Regular'),
        ('premium', 'Premium'),
    ]

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='seats'
    )

    seat_number = models.CharField(
        max_length=20
    )

    seat_type = models.CharField(
        max_length=20,
        choices=SEAT_TYPE_CHOICES,
        default='regular'
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=150.00
    )

    is_booked = models.BooleanField(
        default=False
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['theater', 'seat_number'],
                name='unique_theater_seat'
            )
        ]

        indexes = [
            models.Index(
                fields=['theater'],
                name='seat_theater_idx'
            ),
            models.Index(
                fields=['theater', 'seat_number'],
                name='seat_theater_number_idx'
            ),
            models.Index(
                fields=['theater', 'is_booked'],
                name='seat_theater_booked_idx'
            ),
        ]

    def __str__(self):
        return f'{self.theater.name} - {self.seat_number}'


class SeatReservation(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='seat_reservations'
    )

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='seat_reservations'
    )

    seat = models.OneToOneField(
        Seat,
        on_delete=models.CASCADE,
        related_name='reservation'
    )

    reserved_at = models.DateTimeField(
        auto_now_add=True
    )

    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(
                fields=['user', 'theater'],
                name='reservation_user_theater_idx'
            ),
            models.Index(
                fields=['theater', 'expires_at'],
                name='reservation_theater_exp_idx'
            ),
            models.Index(
                fields=['expires_at'],
                name='reservation_expiry_idx'
            ),
        ]

    def __str__(self):
        return (
            f'{self.user.username} - '
            f'{self.theater.name} - '
            f'{self.seat.seat_number}'
        )


class Payment(models.Model):

    STATUS_CHOICES = [
        ('created', 'Created'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='payments'
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    currency = models.CharField(
        max_length=10,
        default='INR'
    )

    stripe_order_id = models.CharField(
        max_length=200,
        unique=True
    )

    stripey_payment_id = models.CharField(
        max_length=200,
        unique=True,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='created'
    )

    failure_reason = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        indexes = [
            models.Index(
                fields=['status', 'updated_at'],
                name='payment_status_date_idx'
            ),
            models.Index(
                fields=['theater', 'updated_at'],
                name='payment_theater_date_idx'
            ),
            models.Index(
                fields=['created_at'],
                name='payment_created_at_idx'
            ),
            models.Index(
                fields=['user', 'status'],
                name='payment_user_status_idx'
            ),
        ]

    def __str__(self):
        return (
            f'{self.user.username} - '
            f'{self.stripe_order_id} - '
            f'{self.status}'
        )


class Booking(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    seat = models.ForeignKey(
        Seat,
        on_delete=models.CASCADE,
        related_name='bookings'
    )

    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )

    watched = models.BooleanField(
        default=False
    )

    booked_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        indexes = [
            models.Index(
                fields=['booked_at'],
                name='booking_booked_at_idx'
            ),
            models.Index(
                fields=['theater', 'booked_at'],
                name='booking_theater_date_idx'
            ),
            models.Index(
                fields=['movie', 'booked_at'],
                name='booking_movie_date_idx'
            ),
            models.Index(
                fields=['user', 'booked_at'],
                name='booking_user_date_idx'
            ),
            models.Index(
                fields=['payment', 'booked_at'],
                name='booking_payment_date_idx'
            ),
        ]

    def __str__(self):
        return (
            f'{self.user.username} - '
            f'{self.movie.name} - '
            f'{self.seat}'
        )


class Event(models.Model):

    title = models.CharField(
        max_length=200
    )

    image = models.ImageField(
        upload_to='events/'
    )

    description = models.TextField(
        blank=True
    )

    def __str__(self):
        return self.title


class Premiere(models.Model):

    title = models.CharField(
        max_length=200
    )

    image = models.ImageField(
        upload_to='premieres/'
    )

    description = models.TextField(
        blank=True
    )

    def __str__(self):
        return self.title


class MusicStudio(models.Model):

    title = models.CharField(
        max_length=200
    )

    image = models.ImageField(
        upload_to='music/'
    )

    description = models.TextField(
        blank=True
    )

    def __str__(self):
        return self.title


class Review(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    rating = models.PositiveIntegerField()

    comment = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    is_reported = models.BooleanField(
        default=False
    )

    class Meta:
        indexes = [
            models.Index(
                fields=['movie', 'is_reported'],
                name='review_movie_report_idx'
            ),
            models.Index(
                fields=['user', 'movie'],
                name='review_user_movie_idx'
            ),
            models.Index(
                fields=['created_at'],
                name='review_created_idx'
            ),
        ]

    def __str__(self):
        return (
            f'{self.user.username} - '
            f'{self.movie.name} - '
            f'{self.rating}/5'
        )


class MoviePoster(models.Model):

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='posters'
    )

    image = models.ImageField(
        upload_to='movies/posters/'
    )

    def __str__(self):
        return f'{self.movie.name} Poster'


class RecentlyViewedMovie(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recently_viewed'
    )

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='viewed_by'
    )

    viewed_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'movie'],
                name='unique_recently_viewed_movie'
            )
        ]

        ordering = ['-viewed_at']

        indexes = [
            models.Index(
                fields=['user', '-viewed_at'],
                name='recently_viewed_user_idx'
            ),
            models.Index(
                fields=['movie', '-viewed_at'],
                name='recently_viewed_movie_idx'
            ),
        ]

    def __str__(self):
        return (
            f'{self.user.username} viewed '
            f'{self.movie.name}'
        )