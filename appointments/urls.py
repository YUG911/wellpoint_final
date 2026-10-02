from django.urls import path
from . import views

urlpatterns = [
    path("book/<int:doctor_id>/", views.book_appointment, name="book_appointment"),
    path("confirmation/<int:appointment_id>/", views.appointment_confirmation, name="appointment_confirmation"),
    path("my-appointments/", views.my_appointments, name="my_appointments"),
    path("reschedule/<int:appointment_id>/", views.reschedule_appointment, name="reschedule_appointment"),
    path("cancel/<int:appointment_id>/", views.cancel_appointment, name="cancel_appointment"),
    path("review/<int:appointment_id>/", views.submit_review, name="submit_review"),
    path("payment/<int:appointment_id>/", views.payment_page, name="payment_page"),
]
