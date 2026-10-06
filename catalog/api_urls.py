from django.urls import path
from . import api

urlpatterns = [
    path('bootstrap/', api.bootstrap),
    path('parts/', api.parts),
    path('parts/exact/', api.exact),
    path('parts/<uuid:pk>/', api.part_detail),
    path('changes/', api.changes),
    path('catalogs/', api.catalogs),
]
