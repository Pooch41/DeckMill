from django.urls import path
from . import views

urlpatterns = [
    path('', views.card_search, name='card_search'),
]