# panel/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.core.exceptions import PermissionDenied

from users.models import CustomUser

from .mixins import (
    StaffRequiredMixin,
    AdminOrStaffRequiredMixin,
    InstructorGroupRequiredMixin,
    InstructorOrStaffMixin,
    CursoPermissionMixin,
    InstructorCanViewInscripcionesMixin,
)
from .forms import CursoForm, CursoLeccionFormSet
from courses.models import Curso, Leccion, RecursoLeccion, Inscripcion
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import LeccionForm, RecursoFormSet, InscripcionForm, EstudianteRapidoForm
from django.db.models import Q

import json
from django.http import JsonResponse
from django.views import View
from .utils import generar_username, generar_password_temporal
from .forms import CustomUserCreationForm, CustomUserChangeForm, UsuarioFiltroForm


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _form_errors_dict(form):
    return {field: [str(e) for e in errs] for field, errs in form.errors.items()}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

from django.core.exceptions import PermissionDenied  # Asegúrate de tener esta importación arriba

def dashboard(request):
    """
    Accesible para staff, administradores e instructores.
    Cada rol ve únicamente las estadísticas que le corresponden.
    """
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())

    user = request.user
    
    # 1. Validamos si es Administrador (ya sea por ser staff o por pertenecer al grupo)
    es_admin = user.is_staff or user.groups.filter(name='Administradores').exists()
    es_instructor = user.groups.filter(name='Instructores').exists()

    # 2. Control de acceso: Si no es admin ni instructor, se le deniega el acceso
    if not es_admin and not es_instructor:
        raise PermissionDenied("No tienes permisos para acceder al panel.")

    # 3. Filtrado de Querysets según el rol primario
    if es_admin:
        # Los administradores y staff ven todo
        cursos_qs = Curso.objects.all()
    else:
        # Los instructores ven solo sus cursos
        cursos_qs = Curso.objects.filter(instructor=user)

    total_cursos = cursos_qs.count()
    cursos_publicados = cursos_qs.filter(publicado=True).count()
    total_lecciones = Leccion.objects.filter(curso__in=cursos_qs).count()
    total_recursos = RecursoLeccion.objects.filter(leccion__curso__in=cursos_qs).count()
    
    # Las inscripciones totales solo las ve el administrador/staff
    total_inscripciones = Inscripcion.objects.filter(curso__in=cursos_qs).count() if es_admin else None

    # 4. Enviamos las variables limpias al contexto
    context = {
        'titulo_pagina': 'Dashboard',
        'total_cursos': total_cursos,
        'cursos_publicados': cursos_publicados,
        'total_lecciones': total_lecciones,
        'total_recursos': total_recursos,
        'total_inscripciones': total_inscripciones,
    }
    return render(request, 'panel/dashboard.html', context)


# ---------------------------------------------------------------------------
# Cursos
# ---------------------------------------------------------------------------

class CursoListView(InstructorOrStaffMixin, ListView):
    """
    - Staff: ve todos los cursos.
    - Instructor: ve solo los cursos donde está asignado como instructor.
    """
    model = Curso
    template_name = 'panel/curso_list.html'
    context_object_name = 'cursos'
    ordering = ['-creado_en']

    def test_func(self):
        user = self.request.user
        # Validamos si es Admin (staff o grupo) o si es instructor
        es_admin = user.is_staff or user.groups.filter(name='Administradores').exists()
        return es_admin or user.groups.filter(name='Instructores').exists()

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Validamos el grupo administrador aquí también
        es_admin = user.is_staff or user.groups.filter(name='Administradores').exists()

        if es_admin:
            return queryset # El admin ve todos los cursos

        # El Instructor filtra solo sus cursos
        return queryset.filter(instructor=user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        return context


class CursoCreateView(AdminOrStaffRequiredMixin, CreateView):
    """Solo staff puede crear cursos."""
    model = Curso
    form_class = CursoForm
    template_name = 'panel/curso_form.html'
    success_url = reverse_lazy('panel:curso_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = CursoLeccionFormSet(self.request.POST, self.request.FILES)
        else:
            context['formset'] = CursoLeccionFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            if formset.is_valid():
                formset.save()
            else:
                return self.form_invalid(form)
        messages.success(self.request, 'Curso creado correctamente.')
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        messages.error(self.request, 'Hubo errores en el formulario. Por favor, corrígelos.')
        return self.render_to_response(context)


class CursoUpdateView(AdminOrStaffRequiredMixin, UpdateView):
    """Solo staff puede editar cursos."""
    model = Curso
    form_class = CursoForm
    template_name = 'panel/curso_form.html'
    success_url = reverse_lazy('panel:curso_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['formset'] = CursoLeccionFormSet(
                self.request.POST, self.request.FILES, instance=self.object
            )
        else:
            context['formset'] = CursoLeccionFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            if formset.is_valid():
                formset.save()
            else:
                return self.form_invalid(form)
        messages.success(self.request, 'Curso actualizado correctamente.')
        return super().form_valid(form)

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        messages.error(self.request, 'Hubo errores en el formulario. Por favor, corrígelos.')
        return self.render_to_response(context)


class CursoDeleteView(AdminOrStaffRequiredMixin, DeleteView):
    """Solo staff puede eliminar cursos."""
    model = Curso
    template_name = 'panel/curso_confirm_delete.html'
    success_url = reverse_lazy('panel:curso_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Curso eliminado correctamente.')
        return super().delete(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Lecciones
# ---------------------------------------------------------------------------

class LeccionListView(InstructorOrStaffMixin, ListView):
    """
    Lista todas las lecciones de un curso.
    - Staff: acceso libre.
    - Instructor: solo si es el instructor del curso.
    """
    model = Leccion
    template_name = 'panel/leccion_list.html'
    context_object_name = 'lecciones'

    def get_queryset(self):
        self.curso = get_object_or_404(Curso, pk=self.kwargs['curso_pk'])
        user = self.request.user
        
        es_admin = user.is_staff or user.groups.filter(name='Administradores').exists()
        
        # Verificar pertenencia al curso si no es admin o staff
        if not es_admin and self.curso.instructor != user:
            raise PermissionDenied("No tienes permiso para ver las lecciones de este curso.")

        return Leccion.objects.filter(curso=self.curso).order_by('orden')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['curso'] = self.curso
        context['titulo_pagina'] = f'Lecciones de {self.curso.titulo}'
        return context


class LeccionCreateView(CursoPermissionMixin, CreateView):
    """
    Crear una nueva lección para un curso.
    Permitido para staff o el instructor asignado al curso.
    """
    model = Leccion
    form_class = LeccionForm
    template_name = 'panel/leccion_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.curso = get_object_or_404(Curso, pk=self.kwargs['curso_pk'])
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        return (
            self.request.user.is_staff or
            self.request.user == self.curso.instructor
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Nueva lección para {self.curso.titulo}'
        context['curso'] = self.curso

        if 'recurso_formset' not in kwargs:
            if self.request.POST:
                context['recurso_formset'] = RecursoFormSet(
                    self.request.POST, self.request.FILES
                )
            else:
                context['recurso_formset'] = RecursoFormSet()
        else:
            context['recurso_formset'] = kwargs['recurso_formset']

        return context

    def form_valid(self, form):
        recurso_formset = RecursoFormSet(self.request.POST, self.request.FILES)

        # DEBUG TEMPORAL — borra esto después
        print("=== FORM ERRORS ===", form.errors)
        print("=== FORMSET ERRORS ===", recurso_formset.errors)
        print("=== FORMSET NON FORM ERRORS ===", recurso_formset.non_form_errors())
        print("=== POST DATA ===", self.request.POST)
        # FIN DEBUG

        form.instance.curso = self.curso

        if recurso_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                recurso_formset.instance = self.object
                recurso_formset.save()
            messages.success(self.request, 'Lección creada correctamente.')
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(
                self.get_context_data(form=form, recurso_formset=recurso_formset)
            )

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse('panel:leccion_list', kwargs={'curso_pk': self.curso.pk})


class LeccionUpdateView(CursoPermissionMixin, UpdateView):
    """
    Editar una lección existente y sus recursos.
    Permitido para staff o el instructor asignado al curso.
    """
    model = Leccion
    form_class = LeccionForm
    template_name = 'panel/leccion_form.html'

    def test_func(self):
        leccion = get_object_or_404(Leccion, pk=self.kwargs['pk'])
        curso = leccion.curso
        return (
            self.request.user.is_staff or
            self.request.user == curso.instructor
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Editar lección: {self.object.titulo}'
        context['curso'] = self.object.curso

        if 'recurso_formset' not in kwargs:
            if self.request.POST:
                context['recurso_formset'] = RecursoFormSet(
                    self.request.POST, self.request.FILES, instance=self.object
                )
            else:
                context['recurso_formset'] = RecursoFormSet(instance=self.object)
        else:
            context['recurso_formset'] = kwargs['recurso_formset']

        return context

    def form_valid(self, form):
        recurso_formset = RecursoFormSet(
            self.request.POST, self.request.FILES, instance=self.object
        )

        # DEBUG TEMPORAL — borra esto después
        print("=== FORM ERRORS ===", form.errors)
        print("=== FORMSET ERRORS ===", recurso_formset.errors)
        print("=== FORMSET NON FORM ERRORS ===", recurso_formset.non_form_errors())
        print("=== POST DATA ===", self.request.POST)
        # FIN DEBUG

        if recurso_formset.is_valid():
            with transaction.atomic():
                self.object = form.save()
                recurso_formset.instance = self.object
                recurso_formset.save()
            messages.success(self.request, 'Lección actualizada correctamente.')
            return redirect(self.get_success_url())
        else:
            return self.render_to_response(
                self.get_context_data(form=form, recurso_formset=recurso_formset)
            )

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse('panel:leccion_list', kwargs={'curso_pk': self.object.curso.pk})


class LeccionDeleteView(CursoPermissionMixin, DeleteView):
    """Solo staff o el instructor del curso puede eliminar lecciones."""
    model = Leccion
    template_name = 'panel/leccion_confirm_delete.html'

    def test_func(self):
        leccion = get_object_or_404(Leccion, pk=self.kwargs['pk'])
        curso = leccion.curso
        return (
            self.request.user.is_staff or
            self.request.user == curso.instructor
        )

    def get_success_url(self):
        return reverse('panel:leccion_list', kwargs={'curso_pk': self.object.curso.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Eliminar lección'
        context['curso'] = self.object.curso
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Lección eliminada correctamente.')
        return super().delete(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Inscripciones  (solo staff)
# ---------------------------------------------------------------------------

class InscripcionListView(InstructorCanViewInscripcionesMixin, ListView):
    """Listado de inscripciones con filtros. 
    Admins ven todas; Instructores ven solo las de sus cursos."""
    model = Inscripcion
    template_name = 'panel/inscripcion_list.html'
    context_object_name = 'inscripciones'
    paginate_by = 20

    def get_queryset(self):
        # 1. Obtenemos todas las inscripciones inicialmente
        queryset = Inscripcion.objects.select_related('estudiante', 'curso').order_by('-inscrito_en')

        # 2. Validamos el rol del usuario actual
        user = self.request.user
        es_admin = user.is_staff or user.groups.filter(name='Administradores').exists()

        # 3. FILTRO DE SEGURIDAD: Si es instructor, limitamos a sus propios cursos
        if not es_admin:
            queryset = queryset.filter(curso__instructor=user)

        # 4. Aplicamos los filtros de búsqueda que ya tenías (GET params)
        curso_id = self.request.GET.get('curso')
        usuario_id = self.request.GET.get('usuario')
        estado = self.request.GET.get('estado')
        busqueda = self.request.GET.get('busqueda')

        if curso_id:
            queryset = queryset.filter(curso_id=curso_id)
        if usuario_id:
            queryset = queryset.filter(estudiante_id=usuario_id)
        if estado == 'completado':
            queryset = queryset.filter(completado=True)
        elif estado == 'en_progreso':
            queryset = queryset.filter(completado=False)
        if busqueda:
            queryset = queryset.filter(
                Q(estudiante__username__icontains=busqueda) |
                Q(estudiante__email__icontains=busqueda) |
                Q(estudiante__first_name__icontains=busqueda) |
                Q(estudiante__last_name__icontains=busqueda) |
                Q(curso__titulo__icontains=busqueda)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Inscripciones'
        
        user = self.request.user
        es_admin = user.is_staff or user.groups.filter(name='Administradores').exists()

        # El selector de "Cursos" en el HTML solo debe mostrar los cursos permitidos
        if es_admin:
            cursos_qs = Curso.objects.filter(publicado=True).order_by('titulo')
        else:
            cursos_qs = Curso.objects.filter(instructor=user, publicado=True).order_by('titulo')

        context['cursos'] = cursos_qs
        context['usuarios'] = CustomUser.objects.filter(is_active=True).order_by('username')
        context['curso_seleccionado'] = self.request.GET.get('curso', '')
        context['usuario_seleccionado'] = self.request.GET.get('usuario', '')
        context['estado_seleccionado'] = self.request.GET.get('estado', '')
        context['busqueda'] = self.request.GET.get('busqueda', '')
        return context


class EstudianteSearchView(LoginRequiredMixin, View):
    """
    GET /panel/estudiantes/buscar/?q=ana
    Devuelve hasta 20 estudiantes que coincidan por nombre, username o email.
    """
    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '').strip()

        if len(q) < 2:
            return JsonResponse({'results': []})

        estudiantes = CustomUser.objects.filter(
            Q(full_name__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q)
        ).order_by('full_name')[:20]

        results = [
            {
                'id': u.id,
                'username': u.username,
                'full_name': u.full_name,
                'email': u.email,
            }
            for u in estudiantes
        ]
        return JsonResponse({'results': results})


class EstudianteRapidoCreateView(LoginRequiredMixin, View):
    """
    POST /panel/estudiantes/crear-rapido/
    Crea una cuenta mínima de estudiante con username y password generados automáticamente.
    """
    def post(self, request, *args, **kwargs):
        form = EstudianteRapidoForm(request.POST)

        if not form.is_valid():
            return JsonResponse(
                {'success': False, 'errors': _form_errors_dict(form)},
                status=422,
            )

        full_name = form.cleaned_data['full_name']
        email = form.cleaned_data['email']

        username = generar_username(full_name, email)
        password = generar_password_temporal()

        estudiante = form.save(commit=False)
        estudiante.username = username
        estudiante.set_password(password)
        estudiante.save()

        messages.success(
            request,
            f'Cuenta creada para {estudiante.full_name} (usuario: {username})'
        )

        return JsonResponse({
            'success': True,
            'estudiante': {
                'id': estudiante.id,
                'username': estudiante.username,
                'full_name': estudiante.full_name,
                'email': estudiante.email,
            },
            'credenciales': {
                'username': username,
                'password': password,
            },
        })


class InscripcionCreateView(AdminOrStaffRequiredMixin, CreateView):
    """Solo staff puede inscribir usuarios."""
    model = Inscripcion
    form_class = InscripcionForm
    template_name = 'panel/inscripcion_form.html'
    success_url = reverse_lazy('panel:inscripcion_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Nueva inscripción'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f'Usuario {form.instance.estudiante.username} inscrito correctamente en {form.instance.curso.titulo}'
        )
        if _is_ajax(self.request):
            return JsonResponse({'success': True})
        return response

    def form_invalid(self, form):
        if _is_ajax(self.request):
            return JsonResponse(
                {'success': False, 'errors': _form_errors_dict(form)},
                status=422,
            )
        return super().form_invalid(form)


class InscripcionUpdateView(AdminOrStaffRequiredMixin, UpdateView):
    """Solo staff puede editar inscripciones."""
    model = Inscripcion
    form_class = InscripcionForm
    template_name = 'panel/inscripcion_form.html'
    success_url = reverse_lazy('panel:inscripcion_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Editar inscripción: {self.object.estudiante.username} - {self.object.curso.titulo}'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Inscripción actualizada correctamente')
        if _is_ajax(self.request):
            return JsonResponse({'success': True})
        return response

    def form_invalid(self, form):
        if _is_ajax(self.request):
            return JsonResponse(
                {'success': False, 'errors': _form_errors_dict(form)},
                status=422,
            )
        return super().form_invalid(form)


class InscripcionDeleteView(AdminOrStaffRequiredMixin, DeleteView):
    """Solo staff puede eliminar inscripciones."""
    model = Inscripcion
    template_name = 'panel/inscripcion_confirm_delete.html'
    success_url = reverse_lazy('panel:inscripcion_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Eliminar inscripción'
        return context

    def delete(self, request, *args, **kwargs):
        inscripcion = self.get_object()
        messages.success(
            request,
            f'Inscripción de {inscripcion.estudiante.username} en {inscripcion.curso.titulo} eliminada correctamente'
        )
        return super().delete(request, *args, **kwargs)


class InscripcionDetailView(AdminOrStaffRequiredMixin, DetailView):
    """Solo staff puede ver detalles de inscripciones."""
    model = Inscripcion
    template_name = 'panel/inscripcion_detail.html'
    context_object_name = 'inscripcion'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Detalles de inscripción: {self.object.estudiante.username}'
        from courses.models import LeccionCompletada
        lecciones_completadas = LeccionCompletada.objects.filter(
            inscripcion=self.object
        ).select_related('leccion')
        context['lecciones_completadas'] = lecciones_completadas
        context['total_lecciones'] = self.object.curso.lecciones.count()
        return context


# ---------------------------------------------------------------------------
# Usuarios  (AdminOrStaffRequiredMixin — staff o grupo "Administradores")
# ---------------------------------------------------------------------------

class UsuarioListView(AdminOrStaffRequiredMixin, ListView):
    """Staff o administradores pueden ver el listado de usuarios."""
    model = CustomUser
    template_name = 'panel/usuario_list.html'
    context_object_name = 'usuarios'
    paginate_by = 20

    def get_queryset(self):
        queryset = CustomUser.objects.all().order_by('-date_joined')

        busqueda = self.request.GET.get('busqueda', '')
        rol = self.request.GET.get('rol', '')
        activo = self.request.GET.get('activo', '')

        if busqueda:
            queryset = queryset.filter(
                Q(username__icontains=busqueda) |
                Q(email__icontains=busqueda) |
                Q(full_name__icontains=busqueda)
            )
        if rol == 'staff':
            queryset = queryset.filter(is_staff=True)
        elif rol == 'admin':
            queryset = queryset.filter(is_superuser=True)
        elif rol == 'estudiante':
            queryset = queryset.filter(is_staff=False, is_superuser=False)
        if activo == 'si':
            queryset = queryset.filter(is_active=True)
        elif activo == 'no':
            queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Usuarios'
        context['form_filtro'] = UsuarioFiltroForm(self.request.GET)
        context['total_usuarios'] = CustomUser.objects.count()
        context['total_activos'] = CustomUser.objects.filter(is_active=True).count()
        context['total_staff'] = CustomUser.objects.filter(is_staff=True).count()
        return context


class UsuarioCreateView(AdminOrStaffRequiredMixin, CreateView):
    """Staff o administradores pueden crear usuarios."""
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'panel/usuario_form.html'

    def get(self, request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return redirect('panel:usuario_list')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Crear usuario'
        return context

    def form_valid(self, form):
        if not form.cleaned_data.get('password'):
            password_temporal = generar_password_temporal()
            form.instance.set_password(password_temporal)
        else:
            password_temporal = form.cleaned_data.get('password')

        response = super().form_valid(form)

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'usuario': {
                    'id': self.object.pk,
                    'username': self.object.username,
                    'email': self.object.email,
                    'full_name': self.object.get_full_name(),
                },
                'credenciales': {
                    'username': self.object.username,
                    'password': password_temporal,
                }
            })

        messages.success(self.request, f'Usuario {self.object.username} creado correctamente.')
        return response

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {field: [str(e) for e in errs] for field, errs in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors}, status=422)

        context = self.get_context_data(form=form)
        messages.error(self.request, 'Hubo errores en el formulario.')
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse('panel:usuario_list')


class UsuarioUpdateView(AdminOrStaffRequiredMixin, UpdateView):
    """Staff o administradores pueden editar usuarios."""
    model = CustomUser
    form_class = CustomUserChangeForm
    template_name = 'panel/usuario_form.html'

    def get(self, request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return redirect('panel:usuario_list')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Editar usuario: {self.object.username}'
        return context

    def form_valid(self, form):
        response = super().form_valid(form)

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'usuario': {
                    'id': self.object.pk,
                    'username': self.object.username,
                    'email': self.object.email,
                    'full_name': self.object.get_full_name(),
                }
            })

        messages.success(self.request, f'Usuario {self.object.username} actualizado correctamente.')
        return response

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {field: [str(e) for e in errs] for field, errs in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors}, status=422)

        context = self.get_context_data(form=form)
        messages.error(self.request, 'Hubo errores en el formulario.')
        return self.render_to_response(context)

    def get_success_url(self):
        return reverse('panel:usuario_list')


class UsuarioDeleteView(AdminOrStaffRequiredMixin, DeleteView):
    """Staff o administradores pueden eliminar usuarios."""
    model = CustomUser
    template_name = 'panel/usuario_confirm_delete.html'
    success_url = reverse_lazy('panel:usuario_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = 'Eliminar usuario'
        context['tiene_inscripciones'] = self.object.inscripciones.exists()
        context['total_inscripciones'] = self.object.inscripciones.count()
        return context

    def delete(self, request, *args, **kwargs):
        usuario = self.get_object()
        username = usuario.username

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            usuario.delete()
            return JsonResponse({'success': True})

        messages.success(request, f'Usuario {username} eliminado correctamente.')
        return super().delete(request, *args, **kwargs)


class UsuarioDetailView(AdminOrStaffRequiredMixin, DetailView):
    """Staff o administradores pueden ver el detalle de un usuario."""
    model = CustomUser
    template_name = 'panel/usuario_detail.html'
    context_object_name = 'usuario'

    def get(self, request, *args, **kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            usuario = self.get_object()
            inscripciones = Inscripcion.objects.filter(
                estudiante=usuario
            ).select_related('curso')
            return JsonResponse({
                'inscripciones': [
                    {
                        'curso': ins.curso.titulo,
                        'completado': ins.completado,
                    }
                    for ins in inscripciones
                ]
            })
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f'Detalles de {self.object.username}'
        from courses.models import Inscripcion, LeccionCompletada
        inscripciones = Inscripcion.objects.filter(estudiante=self.object).select_related('curso')
        context['inscripciones'] = inscripciones
        context['total_inscripciones'] = inscripciones.count()
        context['total_completados'] = inscripciones.filter(completado=True).count()
        context['lecciones_completadas'] = LeccionCompletada.objects.filter(
            inscripcion__estudiante=self.object
        ).count()
        return context


class UsuarioResetPasswordView(AdminOrStaffRequiredMixin, View):
    """Staff o administradores pueden restablecer contraseñas."""
    def post(self, request, *args, **kwargs):
        usuario = get_object_or_404(CustomUser, pk=kwargs['pk'])
        nueva_password = generar_password_temporal()
        usuario.set_password(nueva_password)
        usuario.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'username': usuario.username,
                'password': nueva_password,
            })

        messages.success(request, f'Contraseña restablecida para {usuario.username}')
        return redirect('panel:usuario_detail', pk=usuario.pk)