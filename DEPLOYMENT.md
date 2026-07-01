# Guía de Despliegue de Producción: SecureDocs

Esta guía detalla los pasos para desplegar SecureDocs en una infraestructura en la nube compuesta por:
1. **Servidor Web**: AWS EC2 en una VPC (Virtual Private Cloud).
2. **Base de Datos**: OCI Autonomous AI Database (Oracle Database).
3. **Almacenamiento de Archivos**: Azure Blob Storage.

---

## 1. Configuración de Base de Datos: OCI Autonomous Database

Para conectar Django a una base de datos autónoma de Oracle en OCI:

1. **Descargar la Cartera (Wallet)**:
   - Descarga el archivo zip de credenciales del cliente (`Wallet_*.zip`) desde la consola de OCI.
   - Descomprímelo en una ruta segura del servidor EC2 (por ejemplo, `/app/wallet/`).

2. **Configurar el archivo sqlnet.ora**:
   - Abre `sqlnet.ora` dentro del directorio descomprimido de la cartera.
   - Ajusta la variable `DIRECTORY` para apuntar a la ruta exacta donde se encuentra el wallet.
     ```text
     WALLET_LOCATION = (SOURCE = (METHOD = FILE) (METHOD_DATA = (DIRECTORY = "/app/wallet")))
     ```

3. **Definir la variable de conexión en el archivo `.env`**:
   - Configura el URL de conexión usando el formato compatible con Oracle:
     ```text
     DATABASE_URL=oracle://admin:TuContraseñaSegura123@nombre_servicio_high?config_dir=/app/wallet/
     ```

---

## 2. Configuración de Almacenamiento: Azure Blob Storage

Para persistir las evidencias de forma duradera y privada en Azure:

1. **Crear una Cuenta de Almacenamiento (Storage Account)** en Azure Portal.
2. **Crear un Contenedor de Blobs** privado (por ejemplo, `securedocs-evidences`).
3. **Obtener las Credenciales de Acceso**:
   - En el menú lateral, ve a **Access Keys** (Claves de acceso) y copia el nombre de la cuenta y la clave principal (`key1`).
4. **Registrar las variables en el archivo `.env`**:
   - Añade los valores requeridos para activar el controlador en la aplicación:
     ```text
     AZURE_ACCOUNT_NAME=tu_cuenta_almacenamiento
     AZURE_ACCOUNT_KEY=tu_clave_larga_de_acceso
     AZURE_CONTAINER=securedocs-evidences
     ```
   *Nota: Si dejas estas variables en blanco, SecureDocs guardará los archivos de forma local en la carpeta `/media/`.*

---

## 3. Despliegue en AWS EC2 & VPC (Vía Docker Compose)

### A. Preparación del Servidor EC2
1. Lanza una instancia de EC2 (Ubuntu Server recomendado) dentro de tu VPC.
2. **Grupo de Seguridad (Security Group)**:
   - Permite tráfico de entrada en los puertos `80` (HTTP) y `443` (HTTPS) desde cualquier origen (`0.0.0.0/0`).
   - Permite tráfico SSH (`22`) únicamente desde tu IP de administración.
3. Instala Docker y Docker Compose en la instancia de EC2:
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose
   sudo systemctl enable --now docker
   ```

### B. Clonar y Configurar la Aplicación
1. Sube el código fuente de SecureDocs a la instancia.
2. Crea el archivo `.env` de producción a partir de `.env.example`:
   ```bash
   cp .env.example .env
   ```
3. Configura los parámetros críticos de producción:
   ```text
   DEBUG=False
   SECRET_KEY=GeneraUnaClaveFuerteParaProduccionAquí
   ENCRYPTION_KEY=GeneraUnaLlaveFernetBase64Fuerte
   ALLOWED_HOSTS=tu-dominio.com,ip-publica-ec2
   SECURE_SSL_REDIRECT=True
   SESSION_COOKIE_SECURE=True
   CSRF_COOKIE_SECURE=True
   ```

### C. Iniciar el Entorno
1. Construye e inicia los contenedores en segundo plano:
   ```bash
   sudo docker-compose up --build -d
   ```
2. Ejecuta las migraciones de base de datos iniciales dentro del contenedor:
   ```bash
   sudo docker-compose exec web python manage.py migrate
   ```
3. Crea tu cuenta de administrador inicial:
   ```bash
   sudo docker-compose exec web python manage.py createsuperuser
   ```
4. Recopila los archivos estáticos de Django:
   ```bash
   sudo docker-compose exec web python manage.py collectstatic --noinput
   ```

---

## 4. Controles de Mitigación OWASP en Producción

- **A01:2021-Broken Access Control**: El servidor Nginx bloquea el acceso directo a carpetas internas y la aplicación delega la descarga a través de URLs firmadas dinámicas con corta duración (SAS) o controlador Django.
- **A03:2021-Injection**: Django parametriza de manera forzada todas las sentencias SQL. Las políticas CSP añadidas en Nginx y Django detienen la ejecución de scripts externos inyectados en la cabecera.
- **A05:2021-Security Misconfiguration**: Al desactivar `DEBUG=False`, se previenen fugas de información sensible en los volcados de memoria y trazas de error en pantalla.
- **A07:2021-Identification and Authentication Failures**: El bloqueo de IPs de `django-axes` protege los endpoints contra ataques coordinados de fuerza bruta.
- **A09:2021-Security Logging and Monitoring Failures**: Los logs se escriben en la base de datos de auditoría y en archivos físicos locales (`security_warnings.log`), listos para ser consumidos por un SIEM o agregador como CloudWatch.
