# panel/context_processors.py

def panel_roles(request):
    """
    Inyecta las variables de roles globalmente en todos los templates.
    Así el base_panel.html siempre sabrá qué mostrar en el menú.
    """
    # Si el usuario no ha iniciado sesión, no devolvemos nada para evitar errores
    if not request.user.is_authenticated:
        return {}

    # Calculamos los roles
    es_admin = request.user.is_staff or request.user.groups.filter(name='Administradores').exists()
    es_instructor = request.user.groups.filter(name='Instructores').exists()
    
    # Todo lo que devuelvas en este diccionario estará disponible en TODOS tus HTML
    return {
        'es_admin': es_admin,
        'es_instructor': es_instructor,
    }