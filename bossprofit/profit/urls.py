from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("menus/", views.menu_list, name="menu_list"),
    path("menus/<str:menu_id>/", views.menu_detail, name="menu_detail"),
    path("recalculate/", views.recalculate, name="recalculate"),
]
