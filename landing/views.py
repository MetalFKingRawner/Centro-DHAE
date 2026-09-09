from django.shortcuts import render
from courses.models import Curso

from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from .forms import ContactoForm

def index(request):
    if request.method == 'POST':
        form = ContactoForm(request.POST)
        if form.is_valid():
            nombre = form.cleaned_data['nombre']
            email = form.cleaned_data['email']
            telefono = form.cleaned_data.get('telefono', '')
            servicio = form.cleaned_data.get('servicio', '')
            mensaje_cliente = form.cleaned_data['mensaje']

            asunto = f"Nuevo contacto desde la Landing Page: {nombre}"
            mensaje = f"""
Has recibido una nueva solicitud de contacto desde la Landing Page:

Nombre: {nombre}
Correo electrónico: {email}
Teléfono: {telefono if telefono else 'No proporcionado'}
Servicio de interés: {servicio if servicio else 'No especificado'}

Mensaje:
{mensaje_cliente}
            """

            send_mail(
                asunto,
                mensaje,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL],
                fail_silently=False,
            )
            messages.success(request, '¡Gracias por escribirnos! Hemos recibido tu mensaje y te responderemos a la brevedad.')
            return redirect('landing:index')  # Cambia 'landing:index' por el name de tu URL
        else:
            messages.error(request, 'Por favor corrige los datos ingresados en el formulario.')
    else:
        form = ContactoForm()

    return render(request, 'landing/index.html', {'form': form})

def home(request):
    cursos = Curso.objects.filter(publicado=True).order_by('-creado_en')[:4]
    return render(request, 'landing/home.html', {'cursos': cursos})

def nosotros(request):
    return render(request, 'landing/nosotros.html')

def servicios(request):
    return render(request, 'landing/servicios.html')
