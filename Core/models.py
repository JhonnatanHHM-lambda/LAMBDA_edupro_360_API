from django.db import models

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Fecha de Actualización")
    is_active = models.BooleanField(default=True, verbose_name="Estado")

    class Meta:
        abstract = True

    def is_active_status(self):
        return self.is_active