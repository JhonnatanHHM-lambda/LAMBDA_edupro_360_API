# Usa imagen oficial de Python
FROM python:3.12-slim

# Variables de entorno
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Directorio de trabajo
WORKDIR /app

# Copiar requirements primero (mejor caché)
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

# === EJECUTAR COMANDOS DE INICIO ===
# Migraciones + tu comando + collectstatic
RUN python manage.py migrate && \
    python manage.py setup_celery_tasks && \
    python manage.py collectstatic --noinput

# Exponer puerto (Render lo ignora, pero es buena práctica)
EXPOSE 8000

# Comando final: usar gunicorn
CMD ["gunicorn", "Edupro360.wsgi:application", "--bind", "0.0.0.0:8000"]