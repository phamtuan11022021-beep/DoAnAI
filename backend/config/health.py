from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from pathlib import Path


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        root=Path(__file__).resolve().parents[2]
        ready=all((root/'data/dataset'/name).is_file() for name in
                  ['admission_scores_2023_2026_program_year.csv','predicted_cutoff_2027.csv'])
    except Exception:
        ready=False
    return JsonResponse({'status':'ok' if ready else 'unavailable'},status=200 if ready else 503)
