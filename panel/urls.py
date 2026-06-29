# panel/urls.py
from django.urls import path
from . import views

app_name = 'panel'

urlpatterns = [
    # Dashboard (lo implementaremos después)
    path('', views.dashboard, name='dashboard'),

    path('cursos/', views.CursoListView.as_view(), name='curso_list'),
    path('cursos/nuevo/', views.CursoCreateView.as_view(), name='curso_create'),
    path('cursos/<int:pk>/editar/', views.CursoUpdateView.as_view(), name='curso_update'),
    path('cursos/<int:pk>/eliminar/', views.CursoDeleteView.as_view(), name='curso_delete'),

    path('cursos/<int:curso_pk>/lecciones/', views.LeccionListView.as_view(), name='leccion_list'),
    path('cursos/<int:curso_pk>/lecciones/nueva/', views.LeccionCreateView.as_view(), name='leccion_create'),
    path('lecciones/<int:pk>/editar/', views.LeccionUpdateView.as_view(), name='leccion_update'),
    path('lecciones/<int:pk>/eliminar/', views.LeccionDeleteView.as_view(), name='leccion_delete'),

    path('inscripciones/', views.InscripcionListView.as_view(), name='inscripcion_list'),
    path('inscripciones/nueva/', views.InscripcionCreateView.as_view(), name='inscripcion_create'),
    path('inscripciones/<int:pk>/editar/', views.InscripcionUpdateView.as_view(), name='inscripcion_update'),
    path('inscripciones/<int:pk>/eliminar/', views.InscripcionDeleteView.as_view(), name='inscripcion_delete'),
    path('inscripciones/<int:pk>/', views.InscripcionDetailView.as_view(), name='inscripcion_detail'),

    path('estudiantes/buscar/', views.EstudianteSearchView.as_view(), name='estudiante_search'),
    path('estudiantes/crear-rapido/', views.EstudianteRapidoCreateView.as_view(), name='estudiante_crear_rapido'),

    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),
    path('usuarios/nuevo/', views.UsuarioCreateView.as_view(), name='usuario_create'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_update'),
    path('usuarios/<int:pk>/eliminar/', views.UsuarioDeleteView.as_view(), name='usuario_delete'),
    path('usuarios/<int:pk>/', views.UsuarioDetailView.as_view(), name='usuario_detail'),
    path('usuarios/<int:pk>/reset-password/', views.UsuarioResetPasswordView.as_view(), name='usuario_reset_password'),
]