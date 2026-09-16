# BookMySeat

BookMySeat is a Django-based online movie ticket booking application.

## Features

- Movie management
- Movie trailers and reviews
- Movie ratings
- Theater and show management
- Live seat availability
- Temporary 2-minute seat reservation
- Stripe test-mode payment
- Payment success, failure and cancellation handling
- Payment retry
- Booking management
- Admin dashboard
- Movie search, filtering and sorting
- Movie recommendations
- PDF ticket generation
- QR code ticket verification
- Ticket download
- User booking and payment history

## Technologies Used

- Python
- Django
- SQLite
- HTML
- CSS
- JavaScript
- Stripe
- Celery
- Git & GitHub

## Project Structure

- `bookmyseat/` - Django project configuration
- `movies/` - Movie, theater, seat, booking and payment functionality
- `users/` - User authentication and profile functionality
- `templates/` - HTML templates
- `static/` - CSS, JavaScript and images
- `media/` - Uploaded media files
- `manage.py` - Django management script

## Payment

Stripe is configured in **Test Mode** for development and testing.

No real payments are processed.

## Admin

The Django admin panel is used to manage movies, theaters, shows, seats and other project data.

## Running the Project

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
