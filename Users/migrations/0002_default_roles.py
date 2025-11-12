from django.db import migrations

def crear_roles(apps, schema_editor):
    Rol = apps.get_model('Users', 'Rol')
    roles = [
        {'codigo': 'admin', 'nombre': 'Administrador', 'descripcion': 'Admin del sistema'},
        {'codigo': 'estudiante', 'nombre': 'Estudiante', 'descripcion': 'Usuario estudiante'},
    ]
    for r in roles:
        Rol.objects.get_or_create(codigo=r['codigo'], defaults=r)

class Migration(migrations.Migration):
    dependencies = [('Users', '0001_initial')]
    operations = [migrations.RunPython(crear_roles)]