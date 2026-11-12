from django.urls import path

from .views import (
    history_view,
    questions_view,
    submit_view,
)


urlpatterns = [
    path(
        "questions/",
        questions_view,
        name="career-questions",
    ),
    path(
        "submit/",
        submit_view,
        name="career-submit",
    ),
    path(
        "history/",
        history_view,
        name="career-history",
    ),
]
