# Gestión de Calificaciones Académicas con integración MCP

Servidor **MCP** que permite consultar desde **claude.ai** las calificaciones de un curso de ejemplo
(10 estudiantes, 5 asignaturas, 3 cortes por asignatura). Está desplegado en Vercel y lee su información
de un único archivo, `estudiantes.json`. Todos los nombres y notas son **ficticios**.

> **URL del servidor MCP:** `https://gestioncalificaciones.vercel.app/mcp`

El repositorio incluye además una aplicación web local para editar las notas (ver
[Aplicación web (opcional, local)](#aplicación-web-opcional-local)).

## Qué se puede preguntar a Claude

Una vez conectado el servidor a claude.ai (ver más abajo), se puede preguntar en lenguaje natural:

- "¿Qué estudiantes hay registrados?"
- "¿Qué estudiantes tienen asignaturas perdidas?"
- "Dame las notas del estudiante 2026005."
- "¿Cuál es el promedio de 2026001 comparado con el del grupo?"

## Herramientas del servidor MCP

El servidor es de **solo lectura**: consulta los datos, pero no los modifica.

| Herramienta | Retorna |
|---|---|
| `listar_estudiantes()` | Los 10 estudiantes (código y nombre). |
| `consultar_estudiante(codigo)` | Datos académicos completos del estudiante. |
| `consultar_notas(codigo)` | Las 5 asignaturas con 3 cortes, definitiva y clasificación (`Pendiente` si falta algún corte). |
| `consultar_promedio(codigo)` | Promedio general del estudiante (y del grupo, para comparar). Es `null` si aún no tiene asignaturas completas. |
| `consultar_reprobados()` | Estudiantes con al menos una asignatura perdida y cuáles perdieron. |

## Conectarlo a claude.ai

1. En claude.ai ve a **Customize > Connectors** y agrega un **conector personalizado** (la disponibilidad
   depende de tu plan).
2. Pega la URL `https://gestioncalificaciones.vercel.app/mcp` y déjalo sin autenticación (los datos son ficticios).
3. En un chat nuevo, activa el conector desde las herramientas del cuadro de mensaje.
4. Haz las preguntas de ejemplo de la sección anterior.

**Qué ocurre por detrás:** Claude elige la herramienta según su descripción y envía una petición a `/mcp` en
Vercel; `api/index.py` la entrega a `mcp_server.py`, que llama a `calculos.py`; este lee `estudiantes.json`,
calcula el resultado y Claude redacta la respuesta con esos datos.

## Estructura

| Archivo | Función |
|---|---|
| `estudiantes.json` | Única fuente de datos: 10 estudiantes, 5 asignaturas, 3 cortes (RF01–RF03, RF07). |
| `calculos.py` | Lógica de negocio: validación y lectura del JSON, definitivas, promedios, clasificación (RF04–RF05). |
| `mcp_server.py` | Servidor MCP con las 5 herramientas requeridas. |
| `api/index.py` | Punto de entrada del servidor MCP en Vercel (expone la app ASGI y registra alias de ruta). |
| `vercel.json` | Redirige `/mcp` a `/api/index` e incluye `estudiantes.json` en el despliegue. |
| `requirements.txt` | Dependencia del servidor MCP (`mcp>=1.2,<2`); Vercel la usa para instalarla. |
| `test_calculos.py` | 17 pruebas unitarias de la lógica. |
| `.gitignore` | Excluye `venv/`, `__pycache__/` y `*.pyc`. |
| `app.py` y `static/` | Aplicación web local opcional (RF06). No se despliegan en Vercel. |

## Reglas de cálculo

- Notas de 0,0 a 5,0 con **máximo dos decimales** (o `null` si el corte está pendiente).
- La **definitiva** de una asignatura es el promedio aritmético de sus 3 cortes.
- Una asignatura con algún corte pendiente **no tiene definitiva** y se marca *Pendiente*.

| Clasificación | Definitiva |
|---|---|
| Perdió | de 0,0 a menos de 3,0 |
| Ganó | de 3,0 a menos de 4,0 |
| Sobresaliente | de 4,0 a 5,0 |

- El **promedio general** del estudiante usa solo las asignaturas con sus 3 cortes. Si no tiene ninguna completa,
  queda en `null`.
- El **promedio del grupo** promedia los estudiantes que ya tienen promedio general.

## Probar en local

```bash
python -m venv venv
# Windows: venv\Scripts\activate      Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
python mcp_server.py http
```

El servidor queda en `http://localhost:8000/mcp`. Sin argumentos, `python mcp_server.py` usa el transporte
stdio (modo local); con `http` usa **Streamable HTTP**, el que necesita claude.ai.

Para comprobar las herramientas sin cliente, abre el MCP Inspector en otra terminal:

```bash
npx @modelcontextprotocol/inspector
```

Elige el transporte **Streamable HTTP**, escribe la URL `http://localhost:8000/mcp`, pulsa **Connect** y en
**Tools > List Tools** deben aparecer las 5 herramientas. La misma prueba sirve contra la URL de Vercel.

## Despliegue en Vercel

claude.ai se conecta a los servidores MCP desde la nube, por eso el servidor debe estar publicado en internet.

1. Sube el proyecto a GitHub (el `.gitignore` evita subir `venv/`).
2. En [vercel.com/new](https://vercel.com/new) importa el repositorio (rama `main`, raíz `./`, preset Python)
   y pulsa **Deploy**.
3. La URL de producción termina en `/mcp`; pruébala en el Inspector antes de agregarla a claude.ai.

Detalles técnicos:

- **Modo sin estado.** `FastMCP` se crea con `stateless_http=True`, porque en Vercel cada petición puede
  ejecutarse en una instancia distinta.
- **Alias de ruta.** Tras el primer despliegue el Inspector devolvía `Not Found` en `/mcp`. Para cubrir las
  rutas con las que Vercel puede entregar la petición, `api/index.py` registra el mismo endpoint también en
  `/`, `/api` y `/api/index`.

### Actualizar los datos

El servidor de Vercel lee el `estudiantes.json` incluido en el despliegue, y el sistema de archivos de Vercel
no conserva cambios mientras corre. Para actualizar las notas edita el archivo y sube el cambio:

```bash
git add .
git commit -m "Actualizar notas"
git push
```

Vercel vuelve a desplegar automáticamente.

### Seguridad

El servidor **no tiene autenticación**: es aceptable porque los datos son ficticios. Con datos reales de
estudiantes habría que protegerlo (por ejemplo con OAuth) antes de publicarlo.

## Ejecutar las pruebas

```bash
python -m unittest -v
```

Las pruebas usan archivos temporales y no modifican tu `estudiantes.json`.

## Decisiones de diseño

- **Clasificación sin redondear (RF05).** Se usa aritmética exacta (`Fraction`). Por ejemplo, 2,99 / 3,0 / 3,0
  da 2,9966…: se muestra como 3,00 pero la asignatura está **Perdida**. El estudiante 2026005 incluye este
  caso y el equivalente en 4,0 (3,99 / 4,0 / 4,0 se muestra 4,00 pero es "Ganó").
- **"Aprobadas"** cuenta las asignaturas con definitiva ≥ 3,0, es decir, **incluye las sobresalientes**.
  Por eso `aprobadas + reprobadas = 5` cuando no hay asignaturas pendientes.
- **Promedio del grupo:** promedio de los promedios generales de los 10 estudiantes (equivale al promedio
  de las 50 definitivas, porque todos tienen 5 asignaturas).
- **Una sola fuente de lógica:** toda la lógica vive en `calculos.py`; `mcp_server.py` solo la expone como
  herramientas, por lo que el servidor se mantiene simple y la lógica se prueba por separado.
- El JSON se valida al cargarse (códigos únicos, 5 asignaturas, 3 cortes, notas entre 0,0 y 5,0 o `null`)
  y cualquier error se informa con un mensaje claro.

## Aplicación web (opcional, local)

Una interfaz para ver las notas, agregar estudiantes y registrar o corregir calificaciones. Usa solo la
biblioteca estándar de Python (no necesita instalar dependencias) y **no se despliega en Vercel**.

```bash
python app.py
```

Abre http://localhost:8000. Si editas `estudiantes.json`, basta con recargar la página.

### Agregar estudiantes y registrar notas

1. **Agregar estudiante** (botón sobre la lista): escribe el nombre; el código es opcional y, si lo dejas vacío,
   se asigna el siguiente disponible. El estudiante nace con las 5 asignaturas y todas sus notas pendientes.
2. **Editar notas** (en el detalle del estudiante): llena los cortes que ya tengan nota y pulsa **Guardar notas**.
   Un corte vacío queda *pendiente*. Puedes volver a editar para corregir cualquier nota.

Todo se guarda en `estudiantes.json` (guardado todo o nada y atómico: si una nota es inválida no se modifica
el archivo). Estos cambios **no llegan a claude.ai** hasta que subas el archivo actualizado con `git push`.

### API

Por si quieres probarla sin la interfaz; el cuerpo debe enviarse como `application/json`:

| Método y ruta | Cuerpo |
|---|---|
| `GET /api/estudiantes` | — |
| `POST /api/estudiantes` | `{"nombre": "Ana Pérez", "codigo": "2026011"}` (`codigo` opcional) |
| `PUT /api/estudiantes/<codigo>/notas` | `{"asignaturas": [{"nombre": "Estadística", "cortes": [4.0, 3.5, null]}]}` |
