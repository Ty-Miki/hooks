from django.urls import path
from . import views


app_name = 'manage_subs'

urlpatterns = [
    path('home/', views.subscriptions, name='home'),
]