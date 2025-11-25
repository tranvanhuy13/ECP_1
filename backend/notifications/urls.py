from django.urls import path
from .views import (
    NotificationView,
    NotificationDetailView,
    MarkNotificationReadView,
    NotificationPreferenceView
)

urlpatterns = [
    path('', NotificationView.as_view(), name='notification-list'),
    path('<int:pk>/', NotificationDetailView.as_view(), name='notification-detail'),
    path('<int:pk>/read/', MarkNotificationReadView.as_view(), name='notification-mark-read'),

    # Notification preferences
    path('preferences/', NotificationPreferenceView.as_view(), name='notification-preferences'),
]
