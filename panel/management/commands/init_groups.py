# panel/management/commands/init_groups.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from courses.models import Curso, Leccion, RecursoLeccion, Inscripcion


class Command(BaseCommand):
    help = 'Inicializa grupos y permisos para la plataforma'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Limpia los permisos de los grupos antes de reasignarlos (útil tras cambios)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('\nIniciando creación de grupos y permisos...\n'))

        if options['reset']:
            self.stdout.write(self.style.WARNING('⚠ Modo --reset: limpiando permisos de grupos existentes...\n'))
            for nombre in ('Administradores', 'Instructores', 'Estudiantes'):
                try:
                    grupo = Group.objects.get(name=nombre)
                    grupo.permissions.clear()
                    self.stdout.write(f'  • Permisos de "{nombre}" limpiados')
                except Group.DoesNotExist:
                    pass
            self.stdout.write('')

        # ----------------------------------------
        # 1. Crear grupos
        # ----------------------------------------
        self.stdout.write(self.style.HTTP_INFO('[ Grupos ]'))

        grupo_admins, created = Group.objects.get_or_create(name='Administradores')
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ "Administradores" {"creado" if created else "ya existe"}'
        ))

        grupo_instructores, created = Group.objects.get_or_create(name='Instructores')
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ "Instructores" {"creado" if created else "ya existe"}'
        ))

        grupo_estudiantes, created = Group.objects.get_or_create(name='Estudiantes')
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ "Estudiantes" {"creado" if created else "ya existe"}'
        ))

        # ----------------------------------------
        # 2. Obtener ContentTypes
        # ----------------------------------------
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('[ ContentTypes ]'))

        try:
            curso_ct      = ContentType.objects.get_for_model(Curso)
            leccion_ct    = ContentType.objects.get_for_model(Leccion)
            recurso_ct    = ContentType.objects.get_for_model(RecursoLeccion)
            inscripcion_ct = ContentType.objects.get_for_model(Inscripcion)
            self.stdout.write(self.style.SUCCESS('  ✓ ContentTypes obtenidos correctamente'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error al obtener ContentTypes: {e}'))
            self.stdout.write(self.style.ERROR('  Asegúrate de haber ejecutado migrate antes de este command.'))
            return

        # ----------------------------------------
        # 3. Permisos auto-generados por Django
        #    (add, change, delete, view por modelo)
        # ----------------------------------------
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('[ Permisos estándar de Django ]'))

        def get_perm(codename, content_type):
            """Obtiene un permiso estándar generado por Django."""
            try:
                perm = Permission.objects.get(codename=codename, content_type=content_type)
                self.stdout.write(f'  ✓ {codename}')
                return perm
            except Permission.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'  ✗ Permiso "{codename}" no encontrado. '
                    f'¿Ejecutaste migrate?'
                ))
                return None

        # Permisos sobre Curso (declarados en Meta del modelo, Django los crea al migrar)
        perm_ver_todos_cursos      = get_perm('puede_ver_todos_cursos', curso_ct)
        perm_asignar_instructores  = get_perm('puede_asignar_instructores', curso_ct)

        # Permisos CRUD estándar sobre Lección
        perm_add_leccion    = get_perm('add_leccion', leccion_ct)
        perm_change_leccion = get_perm('change_leccion', leccion_ct)
        perm_delete_leccion = get_perm('delete_leccion', leccion_ct)
        perm_view_leccion   = get_perm('view_leccion', leccion_ct)

        # Permisos CRUD estándar sobre RecursoLeccion
        perm_add_recurso    = get_perm('add_recursoleccion', recurso_ct)
        perm_change_recurso = get_perm('change_recursoleccion', recurso_ct)
        perm_delete_recurso = get_perm('delete_recursoleccion', recurso_ct)
        perm_view_recurso   = get_perm('view_recursoleccion', recurso_ct)

        # Permiso de lectura sobre Inscripcion (para que instructor vea avance)
        perm_view_inscripcion = get_perm('view_inscripcion', inscripcion_ct)

        # ----------------------------------------
        # 4. Permisos personalizados del command
        #    (los que NO están en ningún Meta)
        # ----------------------------------------
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('[ Permisos personalizados ]'))

        def get_or_create_perm(codename, name, content_type):
            """Crea un permiso personalizado si no existe, o lo obtiene si ya existe."""
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name},
            )
            estado = 'creado' if created else 'ya existe'
            self.stdout.write(self.style.SUCCESS(f'  ✓ {codename} ({estado})'))
            return perm

        perm_ver_avance = get_or_create_perm(
            codename='puede_ver_avance_estudiantes',
            name='Puede ver el avance de estudiantes en sus cursos',
            content_type=curso_ct,
        )

        # ----------------------------------------
        # 5. Asignar permisos a cada grupo
        # ----------------------------------------
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('[ Asignación de permisos ]'))

        # Administradores: todos los permisos relevantes a la plataforma de cursos
        # Nota: si el admin tiene is_superuser=True no necesita permisos explícitos,
        # pero los asignamos igualmente por consistencia y por si usas admins sin superuser.
        perms_admin = [
            perm_ver_todos_cursos,
            perm_asignar_instructores,
            perm_add_leccion, perm_change_leccion, perm_delete_leccion, perm_view_leccion,
            perm_add_recurso, perm_change_recurso, perm_delete_recurso, perm_view_recurso,
            perm_view_inscripcion,
            perm_ver_avance,
        ]
        perms_admin = [p for p in perms_admin if p is not None]
        grupo_admins.permissions.set(perms_admin)
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ "Administradores": {len(perms_admin)} permisos asignados'
        ))

        # Instructores: gestión de contenido de sus cursos y avance de estudiantes
        # Nota: el filtrado de "solo sus cursos" se maneja en la lógica de las views,
        # no en los permisos. Estos permisos solo abren la puerta.
        perms_instructor = [
            perm_add_leccion, perm_change_leccion, perm_delete_leccion, perm_view_leccion,
            perm_add_recurso, perm_change_recurso, perm_delete_recurso, perm_view_recurso,
            perm_view_inscripcion,
            perm_ver_avance,
        ]
        perms_instructor = [p for p in perms_instructor if p is not None]
        grupo_instructores.permissions.set(perms_instructor)
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ "Instructores": {len(perms_instructor)} permisos asignados'
        ))

        # Estudiantes: solo lectura de cursos en los que están inscritos
        # Nota: el acceso real se controla por la lógica de Inscripcion en las views.
        perms_estudiante = [
            perm_view_leccion,
            perm_view_recurso,
        ]
        perms_estudiante = [p for p in perms_estudiante if p is not None]
        grupo_estudiantes.permissions.set(perms_estudiante)
        self.stdout.write(self.style.SUCCESS(
            f'  ✓ "Estudiantes": {len(perms_estudiante)} permisos asignados'
        ))

        # ----------------------------------------
        # 6. Resumen final
        # ----------------------------------------
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('¡Inicialización completada exitosamente!'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write('')
        self.stdout.write('Resumen de grupos:')
        for grupo in (grupo_admins, grupo_instructores, grupo_estudiantes):
            self.stdout.write(
                f'  • {grupo.name}: '
                f'{grupo.user_set.count()} usuarios | '
                f'{grupo.permissions.count()} permisos'
            )
        self.stdout.write('')
        self.stdout.write(self.style.WARNING(
            'Recuerda: los permisos de grupo se cachean por sesión.\n'
            'Si asignaste un usuario a un grupo con sesión activa,\n'
            'cierra sesión y vuelve a entrar para que los permisos surtan efecto.\n'
        ))