# accounts/urls.py
from django.urls import path
from .views import logout_view
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', logout_view, name='logout'),
    
]
