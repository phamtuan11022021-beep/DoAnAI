from django.urls import path

from .views import (
    saved_universities_view,
    school_detail_view,
    schools_view,
    toggle_saved_university_view,
)


urlpatterns = [
    path("schools/", schools_view, name="catalog-schools"),
    path("school-detail/", school_detail_view, name="catalog-school-detail"),
    path("saved/", saved_universities_view, name="catalog-saved"),
    path(
        "saved/toggle/",
        toggle_saved_university_view,
        name="catalog-saved-toggle",
    ),
]
