from django.urls import path
from . import views

app_name = 'catalog'
urlpatterns = [
    path('', views.part_list, name='list'),
    path('exportar/', views.export_parts, name='export'),
    path('piezas/nueva/', views.part_create, name='create'),
    path('piezas/<uuid:pk>/', views.part_detail, name='detail'),
    path('piezas/<uuid:pk>/editar/', views.part_edit, name='edit'),
    path('piezas/<uuid:pk>/estado/', views.part_toggle, name='toggle'),
    path('catalogos/<str:kind>/', views.related_values, name='related'),
    path('importaciones/', views.import_list, name='imports'),
    path('importaciones/subir/', views.import_upload, name='import_upload'),
    path('importaciones/plantilla/', views.import_template, name='import_template'),
    path('importaciones/<uuid:pk>/mapear/', views.import_map, name='import_map'),
    path('importaciones/<uuid:pk>/vista-previa/', views.import_preview, name='import_preview'),
    path('importaciones/<uuid:pk>/errores/', views.import_errors, name='import_errors'),
    path('importaciones/<uuid:pk>/eliminar/', views.import_delete, name='import_delete'),
    path('historial/', views.history, name='history'),
    path('usuarios/', views.users, name='users'),
    path('usuarios/nuevo/', views.user_edit, name='user_create'),
    path('usuarios/<int:pk>/', views.user_edit, name='user_edit'),
    path('integraciones/', views.integrations, name='integrations'),
]
