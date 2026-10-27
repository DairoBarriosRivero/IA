# Gestión de Calificaciones Académicas con integración MCP

Aplicación web y servidor MCP que leen **la misma fuente de datos** (`estudiantes.json`).

## Estructura

| Archivo | Función |
|---|---|
| `estudiantes.json` | Única fuente de datos: 10 estudiantes, 5 asignaturas, 3 cortes (RF01–RF03, RF07). |
| `calculos.py` | Lógica compartida: validación y escritura del JSON, definitivas, promedios, clasificación (RF04–RF05). |
| `app.py` | Servidor web (solo biblioteca estándar). API de lectura y escritura (`/api/estudiantes`) y sirve `static/`. |
| `static/` | Interfaz: `index.html`, `style.css`, `app.js` (RF06). No contiene notas escritas en el código. |
| `mcp_server.py` | Servidor MCP independiente con las 5 herramientas requeridas. |
| `test_calculos.py` | Pruebas unitarias. |

## Instalación

```bash
python -m venv venv
# Windows: venv\Scripts\activate      Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
```

La app web no necesita dependencias; `requirements.txt` solo es para el servidor MCP.

## Ejecutar la aplicación web

```bash
python app.py
```

Abre http://localhost:8000. Si editas `estudiantes.json`, basta con recargar la página.

## Agregar estudiantes y registrar notas

Desde la web:

1. **Agregar estudiante** (botón sobre la lista): escribe el nombre; el código es opcional y, si lo dejas vacío,
   se asigna el siguiente disponible. El estudiante nace con las 5 asignaturas y todas sus notas pendientes.
2. **Editar notas** (en el detalle del estudiante): llena los cortes que ya tengan nota y pulsa **Guardar notas**.
   Un corte vacío queda *pendiente*. Puedes volver a editar para corregir cualquier nota.

Todo se guarda en `estudiantes.json`, así que el servidor MCP ve los cambios en la siguiente consulta.

Reglas:

- Notas de 0,0 a 5,0 con **máximo dos decimales**; el servidor las valida aunque el navegador falle.
- Una asignatura con algún corte pendiente **no tiene definitiva** y se marca *Pendiente* (gris).
- El **promedio general** del estudiante usa solo las asignaturas con sus 3 cortes (la web indica
  "Con N de 5 asignaturas completas"). Si no tiene ninguna completa, se muestra "—".
- El **promedio del grupo** promedia los estudiantes que ya tienen promedio general.
- El guardado es todo o nada y atómico: si una nota es inválida no se modifica el archivo.

API (por si quieren probarla sin la interfaz; el cuerpo debe enviarse como `application/json`):

| Método y ruta | Cuerpo |
|---|---|
| `POST /api/estudiantes` | `{"nombre": "Ana Pérez", "codigo": "2026011"}` (`codigo` opcional) |
| `PUT /api/estudiantes/<codigo>/notas` | `{"asignaturas": [{"nombre": "Estadística", "cortes": [4.0, 3.5, null]}]}` |

## Ejecutar las pruebas

```bash
python -m unittest -v
```

Las pruebas de escritura usan archivos temporales y no modifican tu `estudiantes.json`.

## Servidor MCP

Herramientas expuestas:

| Herramienta | Retorna |
|---|---|
| `listar_estudiantes()` | Los 10 estudiantes (código y nombre). |
| `consultar_estudiante(codigo)` | Datos académicos completos del estudiante. |
| `consultar_notas(codigo)` | Las 5 asignaturas con 3 cortes, definitiva y clasificación (`Pendiente` si falta algún corte). |
| `consultar_promedio(codigo)` | Promedio general del estudiante (y del grupo, para comparar). Es `null` si aún no tiene asignaturas completas. |
| `consultar_reprobados()` | Estudiantes con al menos una asignatura perdida y cuáles perdieron. |

### Conectarlo a un cliente (por ejemplo Claude Desktop)

Agrega esto a `claude_desktop_config.json`, ajustando las rutas **absolutas**:

```json
{
  "mcpServers": {
    "calificaciones": {
      "command": "/ruta/a/venv/bin/python",
      "args": ["/ruta/a/gestion_calificaciones/mcp_server.py"]
    }
  }
}
```

En Windows usa `C:\\ruta\\venv\\Scripts\\python.exe`. Reinicia el cliente y pregunta, por ejemplo:
"¿Qué estudiantes tienen asignaturas perdidas?"

Para depurar sin cliente: `npx @modelcontextprotocol/inspector python mcp_server.py`.

## Decisiones de diseño

- **Clasificación sin redondear (RF05).** Se usa aritmética exacta (`Fraction`). Por ejemplo, 2,99 / 3,0 / 3,0
  da 2,9966…: se muestra como 3,00 pero la asignatura está **Perdida**. El estudiante 2026005 incluye este
  caso y el equivalente en 4,0 (3,99 / 4,0 / 4,0 se muestra 4,00 pero es "Ganó").
- **"Aprobadas"** cuenta las asignaturas con definitiva ≥ 3,0, es decir, **incluye las sobresalientes**.
  Por eso `aprobadas + reprobadas = 5`.
- **Promedio del grupo:** promedio de los promedios generales de los 10 estudiantes (equivale al promedio
  de las 50 definitivas, porque todos tienen 5 asignaturas).
- **Consistencia web ↔ MCP:** ambos importan `calculos.py` y leen el mismo JSON; no hay lógica duplicada.
- El JSON se valida al cargarse (códigos únicos, 5 asignaturas, 3 cortes, notas entre 0,0 y 5,0 o `null`) y los
  errores se muestran con un mensaje claro en la web y en el MCP.
- Las escrituras usan un candado y reemplazo atómico del archivo, y la API exige `application/json` para que
  otra página web abierta en tu navegador no pueda modificar los datos.
- Solo la web escribe en el JSON; el servidor MCP es de solo lectura, como pide el reto.
