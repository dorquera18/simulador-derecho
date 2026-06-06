# ⚖️ Simulador Examen Complexivo – Carrera de Derecho
## Universidad Felipe Villanueva

Aplicación web para que los estudiantes de la carrera de Derecho practiquen y preparen el Examen Complexivo.

---

## ✨ Características

- 📝 **418 preguntas** extraídas del Banco Oficial (con respuestas correctas)
- 🔀 Preguntas y opciones **aleatorizadas** en cada examen
- ⏱️ **Contador regresivo** de 120 minutos
- 📱 **100% responsive** – funciona en celular, tablet y computadora
- ✅ Aprobación con **70/100 puntos**
- 📊 Resultados con desglose por área del Derecho
- 🎓 Panel administrativo para gestionar preguntas

---

## 🚀 Instalación Local

### Requisitos
- Python 3.9 o superior
- pip

### Pasos

```bash
# 1. Clonar o descomprimir el proyecto
cd simulador-derecho

# 2. Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar la aplicación
python app.py
```

5. Abrir en el navegador: **http://localhost:5000**

---

## 🌐 Despliegue en Render.com (Gratis, acceso desde cualquier lugar)

### Paso 1 – Crear cuenta en Render
- Ve a https://render.com y crea una cuenta gratuita (puedes usar tu cuenta de Google)

### Paso 2 – Subir el código a GitHub
```bash
# En la carpeta del proyecto:
git init
git add .
git commit -m "Simulador Derecho UFV"
```
- Ve a https://github.com → New repository → crea un repo (ej: `simulador-derecho`)
- Sigue las instrucciones para subir el código

### Paso 3 – Crear el Web Service en Render
1. En Render dashboard → **New** → **Web Service**
2. Conecta tu cuenta de GitHub y selecciona el repositorio
3. Configura:
   - **Name**: `simulador-derecho-ufv`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
4. En **Environment Variables** agrega:
   - `SECRET_KEY` → (genera un valor aleatorio, ej: `mi-clave-secreta-2024`)
   - `ADMIN_PASSWORD` → `derecho2024` (o la clave que desees)
5. Click **Create Web Service**

### Paso 4 – Obtener el link
- En 3-5 minutos Render despliega la app
- Tu URL será: `https://simulador-derecho-ufv.onrender.com`
- ¡Comparte ese link con los estudiantes!

> **Nota**: En el plan gratuito, Render "duerme" la app después de 15 min de inactividad. La primera visita puede tardar ~30 segundos. Para evitarlo, considera el plan Starter ($7/mes).

---

## 🔐 Panel Administrativo

Accede en: `https://tu-app.onrender.com/admin`

| Campo | Valor por defecto |
|-------|-------------------|
| Usuario | `admin` |
| Contraseña | `derecho2024` |

### Funciones del admin:
- Ver estadísticas de exámenes rendidos
- Agregar / editar / eliminar preguntas
- Importar preguntas masivamente desde CSV
- Ver historial de todos los exámenes

---

## 📥 Importar Preguntas via CSV

Formato del archivo CSV:

```
pregunta,opcion_a,opcion_b,opcion_c,opcion_d,respuesta_correcta,categoria
¿Cuál es el principal objetivo del derecho?,Regular la convivencia,Crear impuestos,Elegir gobernantes,Distribuir riqueza,a,Teoría General del Derecho
```

Columnas requeridas:
- `pregunta` – Texto de la pregunta
- `opcion_a` / `opcion_b` / `opcion_c` / `opcion_d` – Las 4 opciones
- `respuesta_correcta` – Letra de la respuesta correcta: `a`, `b`, `c` o `d`
- `categoria` – Área del derecho (Derecho Civil, Derecho Penal, etc.)

---

## 📁 Estructura del Proyecto

```
simulador-derecho/
├── app.py                    # Aplicación Flask principal
├── requirements.txt          # Dependencias Python
├── Procfile                  # Configuración para Render/Railway
├── render.yaml               # Config automática de Render
├── data/
│   └── questions.json        # Banco de preguntas (418 preguntas)
├── templates/
│   ├── base.html             # Template base
│   ├── index.html            # Página de inicio
│   ├── exam.html             # Página del examen
│   ├── results.html          # Página de resultados
│   └── admin/
│       ├── login.html
│       ├── dashboard.html
│       ├── questions.html
│       ├── question_form.html
│       ├── import.html
│       └── stats.html
└── static/
    └── css/
        └── styles.css        # Estilos globales
```

---

## 📋 Áreas del Derecho en el Banco de Preguntas

| Área | Preguntas |
|------|-----------|
| Derecho Constitucional | 46 |
| Derecho Civil | 45 |
| Derecho Laboral | 33 |
| Derecho Administrativo | 24 |
| Derecho General | 20 |
| Derecho Internacional | 19 |
| Derecho Procesal | 18 |
| Derecho Penal | 15 |

---

## 🆘 Soporte

Si la aplicación no inicia:
1. Verifica que Python ≥ 3.9 esté instalado: `python --version`
2. Reinstala dependencias: `pip install -r requirements.txt --force-reinstall`
3. Verifica que el archivo `data/questions.json` existe

---

*Desarrollado para la Universidad Felipe Villanueva – Carrera de Derecho*
