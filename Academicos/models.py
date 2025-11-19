import shortuuid
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone
from Base.models import BaseModel
from Usuarios.models import Usuario

def generar_codigo_unico():
    """
    Genera un código único de 8 caracteres usando shortuuid.
    """
    return shortuuid.uuid()[:8].upper()

class PeriodoAcademico(BaseModel):
    nombre = models.CharField(
        max_length=50, unique=True, verbose_name="Nombre del periodo"
    )
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de fin")

    class Meta:
        verbose_name = "Periodo académico"
        verbose_name_plural = "Periodos académicos"
        db_table = "periodo_academico"

    def __str__(self):
        return self.nombre.title()


class Asignatura(BaseModel):
    nombre = models.CharField(max_length=100, verbose_name="Nombre de la asignatura")
    codigo = models.CharField(
        max_length=8,
        unique=True,
        default=generar_codigo_unico,
        editable=False,
        verbose_name="Codigo Usuario"
    )
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    docente_responsable = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asignaturas_responsable",
        limit_choices_to={"groups__name": "Docente"},
        verbose_name="Docente responsable",
    )
    periodo_academico = models.ForeignKey(
        PeriodoAcademico,
        on_delete=models.CASCADE,
        related_name="asignaturas",
        verbose_name="Periodo académico",
    )

    class Meta:
        verbose_name = "Asignatura"
        verbose_name_plural = "Asignaturas"
        db_table = "asignatura"

    def __str__(self):
        return f"{self.codigo.upper()} - {self.nombre.title()}"

    def clean(self):
        if (
            self.docente_responsable
            and not self.docente_responsable.groups.filter(name="Docente").exists()
        ):
            raise ValidationError("El docente debe pertenecer al grupo 'Docente'.")

class Inscripcion(BaseModel):
    """
    Permite a un estudiante inscribirse en una asignatura específica.
    """
    estudiante = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="inscripciones_estudiante",
        limit_choices_to={"groups__name": "Estudiante"},
        verbose_name="estudiante"
    )
    asignatura = models.ForeignKey(
        "Asignatura", 
        on_delete=models.CASCADE,
        related_name="inscripciones_asignatura",
        verbose_name="asignatura"
    )
    fecha_inscripcion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="fecha de inscripción"
    )
    estado_inscripcion = models.CharField(
        max_length=1,
        choices=[
            ("A", "Activa"),
            ("R", "Retirada"),
            ("S", "Suspendida"),
        ],
        default="A",
        verbose_name="estado de la inscripción"
    )

    class Meta:
        verbose_name = "inscripción"
        verbose_name_plural = "inscripciones"
        db_table = "inscripcion"
        unique_together = ("estudiante", "asignatura")
        permissions = [
            ("puede_inscribirse", "Puede inscribirse a asignaturas"),
            ("puede_ver_inscripciones", "Puede ver todas las inscripciones"),
        ]

    def __str__(self):
        estado = dict(self._meta.get_field('estado_inscripcion').choices).get(self.estado_inscripcion, "")
        return f"{self.estudiante.obtener_nombre_completo().title()} → {self.asignatura.nombre.title()} ({estado})"

    def clean(self):
        super().clean()
        if self.asignatura and not self.asignatura.estado:
            raise ValidationError("No se puede inscribir a una asignatura inactiva.")

        if self.asignatura:
            hoy = timezone.now().date()
            periodo = self.asignatura.periodo_academico
            if periodo.fecha_inicio > hoy or periodo.fecha_fin < hoy:
                raise ValidationError(
                    "El periodo académico no está vigente para realizar inscripciones."
                )
            
class Tarea(BaseModel):
    TIPO_TAREA = [
        ("T", "Tarea"),
        ("E", "Examen"),
    ]

    asignatura = models.ForeignKey(
        Asignatura,
        on_delete=models.CASCADE,
        related_name="tareas",
        verbose_name="Asignatura",
    )
    titulo = models.CharField(max_length=100, verbose_name="Título de la tarea")
    descripcion = models.TextField(verbose_name="Descripción")
    fecha_publicacion = models.DateTimeField(
        default=timezone.now, verbose_name="Fecha de publicación"
    )
    fecha_vencimiento = models.DateTimeField(verbose_name="Fecha de vencimiento")
    peso_porcentual = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="Peso porcentual"
    )
    tipo_tarea = models.CharField(
        max_length=1, choices=TIPO_TAREA, default="T", verbose_name="Tipo de tarea"
    )

    class Meta:
        verbose_name = "Tarea"
        verbose_name_plural = "Tareas"
        db_table = "tarea"

    def __str__(self):
        return f"{self.titulo.title()} ({self.get_tipo_tarea_display()})"

    def clean(self):
        # Validar fechas
        if self.fecha_vencimiento <= self.fecha_publicacion:
            raise ValidationError(
                "La fecha de vencimiento debe ser posterior a la de publicación."
            )

        # Validar suma de pesos
        total = Tarea.objects.filter(asignatura=self.asignatura).exclude(pk=self.pk)
        total_peso = (
            total.aggregate(Sum("peso_porcentual"))["peso_porcentual__sum"] or 0
        )
        if total_peso + self.peso_porcentual > 100:
            raise ValidationError(
                f"La suma de pesos no puede exceder 100%. Actual: {total_peso + self.peso_porcentual}%"
            )


class Entrega(BaseModel):
    ESTADO_ENTREGA = [
        ("P", "Pendiente"),
        ("E", "Entregada"),
        ("C", "Calificada"),
    ]

    tarea = models.ForeignKey(
        Tarea, on_delete=models.CASCADE, related_name="entregas", verbose_name="Tarea"
    )
    estudiante = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="entregas",
        verbose_name="Estudiante",
    )
    archivo_entrega = models.FileField(
        upload_to="entregas/", null=True, blank=True, verbose_name="Archivo de entrega"
    )
    comentarios_estudiante = models.TextField(
        blank=True, null=True, verbose_name="Comentarios del estudiante"
    )
    fecha_entrega = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de entrega"
    )
    estado_entrega = models.CharField(
        max_length=1,
        choices=ESTADO_ENTREGA,
        default="E",
        verbose_name="Estado de la entrega",
    )

    class Meta:
        verbose_name = "Entrega"
        verbose_name_plural = "Entregas"
        db_table = "entrega"
        unique_together = ("tarea", "estudiante")

    def __str__(self):
        return f"Entrega de {self.estudiante.obtener_nombre_completo()} - {self.tarea.titulo.title()}"


    def clean(self):
        if self.tarea.fecha_vencimiento < timezone.now():
            raise ValidationError(
                "No se puede entregar después de la fecha de vencimiento."
            )


class Calificacion(BaseModel):
    entrega = models.OneToOneField(
        Entrega,
        on_delete=models.CASCADE,
        related_name="calificacion",
        verbose_name="Entrega",
    )
    nota = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Nota")
    retroalimentacion_docente = models.TextField(
        blank=True, null=True, verbose_name="Retroalimentación del docente"
    )
    fecha_calificacion = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de calificación"
    )

    class Meta:
        verbose_name = "Calificación"
        verbose_name_plural = "Calificaciones"
        db_table = "calificacion"

    def __str__(self):
        return f"Calificación {self.nota} - {self.entrega}"

    def clean(self):
        if self.nota < 0 or self.nota > 100:
            raise ValidationError("La nota debe estar entre 0 y 100.")
