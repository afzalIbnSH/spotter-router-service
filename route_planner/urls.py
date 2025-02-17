from django.urls import path
from .views import get_optimal_route

urlpatterns = [
    path('optimal/', get_optimal_route, name='get_optimal_route'),
]
