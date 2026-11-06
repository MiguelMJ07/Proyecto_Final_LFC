# Conexión del servidor (despliegue)

Esta guía explica cómo se publica el servidor web del proyecto en internet, qué tipo de conexión usa y qué
beneficios da. Es el "extra" de conectar el servidor: en vez de que la aplicación solo funcione en el computador
de un integrante (`http://127.0.0.1:5000`), queda en una dirección pública con HTTPS que cualquiera puede abrir,
incluido el profesor desde su celular.

## 1. Tipo de conexión: cliente–servidor sobre HTTPS con una API REST

```
 Cliente                         Internet (HTTPS)              Render (la nube)
 ┌──────────────────────┐                                      ┌──────────────────────────────────────────┐
 │ navegador (páginas)  │                                      │ proxy de Render                          │
 │ curl / Postman       │  ── petición HTTPS (cifrada) ──────► │   termina TLS (HTTPS → HTTP)             │
 │ otro programa        │  ◄── respuesta JSON / texto / SVG ── │   └─► gunicorn en $PORT (2 procesos)     │
 └──────────────────────┘                                      │         └─► Flask: controllers →         │
                                                               │             gateways → functions         │
                                                               └──────────────────────────────────────────┘
```

- **Cliente–servidor.** El cliente (navegador, `curl`, otro programa) envía una petición; el servidor la
  procesa y responde. El cliente no necesita Python ni el código: solo una conexión a internet.
- **HTTP sobre TLS (HTTPS).** HTTP es el protocolo de petición y respuesta (método `GET`/`POST`, ruta, cabeceras,
  cuerpo, código de estado como 200 o 400). TLS cifra la conexión: nadie en la red puede leer ni cambiar lo que
  viaja. Render da el certificado TLS gratis; el proxy de Render recibe HTTPS y lo reenvía como HTTP a nuestro
  proceso dentro de su red.
- **API REST con JSON.** Cada operación es una ruta (`POST /grammar/analyze`, `POST /grammar/parse`, …). El cuerpo y
  la respuesta son JSON (o texto, CSV, LaTeX, SVG en los tres endpoints extra). La API es **sin estado**
  (*stateless*): cada petición trae todo lo que se necesita (la gramática y las cadenas) y el servidor no recuerda
  nada entre peticiones. Por eso pueden atenderla varios procesos a la vez, o varias máquinas.
- **Servidor de aplicación WSGI (gunicorn).** `python src/app.py` usa el servidor de desarrollo de Flask: atiende
  de a una petición, recarga el código y trae un depurador. En producción se usa **gunicorn**: importa el objeto
  `app` de `src/app.py` (por eso el comando es `gunicorn --chdir src app:app`), arranca varios procesos
  trabajadores (*workers*) que atienden peticiones en paralelo, reinicia un proceso si falla y corta una
  petición que pase de 60 s (`--timeout 60`). WSGI es la interfaz estándar de Python entre el servidor web y la
  aplicación; Flask la implementa.

## 2. Qué hay en el repositorio para esto

| Archivo | Para qué |
|---|---|
| `render.yaml` | "Blueprint" de Render: tipo de servicio, comando de instalación, comando de arranque, ruta de salud y versión de Python. Render lo lee del repositorio. |
| `requirements.txt` | Dependencias. `gunicorn` solo se instala fuera de Windows (no funciona allí; en Windows se usa `python src/app.py`). |
| `src/app.py` | Crea el objeto `app`. `run_options` lee `HOST`, `PORT` y `FLASK_DEBUG` del entorno para el servidor de desarrollo. |
| `GET /health` | Respuesta corta `{"status": "ok"}`. Render la consulta para saber si el servicio está vivo antes de mandarle tráfico. |

La configuración va en **variables de entorno** (`PORT`, `HOST`, `FLASK_DEBUG`, `PYTHON_VERSION`), no en el código:
el mismo código corre en el computador y en la nube. Render decide el puerto y lo pasa en `$PORT`.

## 3. Pasos para publicarlo en Render

1. Subir el proyecto a un repositorio de GitHub (con `render.yaml` en la raíz).
2. Crear una cuenta en <https://render.com> (se puede entrar con la cuenta de GitHub).
3. En el panel: **New → Blueprint**, elegir el repositorio y confirmar (**Apply**). Render lee `render.yaml`, instala
   `requirements.txt` y arranca `gunicorn`.
4. Esperar a que el estado diga **Live**. La dirección queda como `https://lfc-formal-languages.onrender.com`
   (si el nombre está ocupado, Render agrega un sufijo). Probar `https://…/health` y luego la página principal.
5. Probar la API desde otro computador:
   ```bash
   curl -s https://<tu-servicio>.onrender.com/grammar/report -H 'Content-Type: text/plain' --data-binary @examples/ex1.txt
   ```
6. Poner la dirección pública en el README.

Desde ese momento, **cada `git push` a la rama del servicio vuelve a desplegar** automáticamente (despliegue
continuo). Los registros (*logs*) de cada petición y de cada error se ven en el panel de Render.

**Plan gratuito (verificar en la página de Render, puede cambiar):** el servicio se "duerme" tras unos 15 minutos
sin peticiones y la primera petición después tarda cerca de un minuto en despertarlo. Antes de la sustentación hay
que abrir `/health` un par de minutos antes.

## 4. Plan B sin internet: red local

Si en la sustentación no hay internet, el servidor se puede abrir desde otros equipos de la misma red Wi-Fi:

```bash
HOST=0.0.0.0 python src/app.py            # macOS / Linux
$env:HOST="0.0.0.0"; python src/app.py    # Windows PowerShell
```

`0.0.0.0` significa "escuchar en todas las interfaces de red", no solo en `127.0.0.1` (que solo acepta conexiones
del mismo computador). Los demás abren `http://<IP del computador>:5000` (la IP se ve con `ipconfig` en Windows o
`ipconfig getifaddr en0` en macOS). Con `HOST=0.0.0.0` el depurador de Flask queda apagado, porque permitiría a
cualquiera de la red ejecutar código en el computador. Esta conexión es HTTP sin cifrar y solo dentro de la red.

## 5. Beneficios

- **Acceso desde cualquier lugar y dispositivo**: un enlace basta; no hay que instalar Python ni el proyecto.
- **Seguridad en el transporte**: HTTPS con certificado gratuito.
- **Un solo entorno para todos**: la misma versión de Python y de las dependencias para todo el grupo y el profesor.
- **Despliegue continuo**: `git push` → nueva versión publicada, sin pasos manuales.
- **Disponibilidad**: Render vigila `/health` y reinicia el servicio si deja de responder; gunicorn reinicia
  procesos caídos.
- **Concurrencia**: varios procesos atienden peticiones al mismo tiempo; como la API no guarda estado, se puede
  escalar a más procesos o más máquinas.
- **Reutilización**: la misma API la usan las páginas, `curl` u otros programas (el reporte de texto es la misma
  salida del programa de consola).

## 6. Protecciones que ya tiene el servidor (importan cuando es público)

- Cuerpos de máximo 2 MB; límites de 400 estados LR(0), 1000 estados en la construcción de subconjuntos, 200
  cadenas por petición, 2000 símbolos por cadena y 500 estados por AFD a minimizar.
- Los errores de entrada responden 400 con un JSON que explica el problema; nunca muestran trazas internas.
- Las reglas semánticas de los SDD se interpretan con un lenguaje restringido (`safe_expr.py`), nunca con `eval`.
- El depurador de Flask no se activa en producción (gunicorn no usa el bloque `if __name__ == "__main__"`).

## 7. Preguntas probables

- **¿Por qué no usar `python src/app.py` en la nube?** Es un servidor de desarrollo: una petición a la vez, sin
  manejo de procesos caídos, y con un depurador que no debe quedar expuesto.
- **¿Qué hace el proxy de Render?** Recibe las conexiones HTTPS de internet, descifra TLS y reenvía la petición a
  nuestro proceso en `$PORT`; también reparte la carga y hace la revisión de salud.
- **¿Por qué la API es sin estado y qué gana con eso?** Cada petición es independiente, así que cualquier proceso
  puede atenderla: permite varios workers, reinicios sin perder nada y escalar.
- **¿Qué pasa si el servidor recibe una gramática enorme?** Los límites de la sección 6 cortan la petición con un
  400 y el `--timeout` de gunicorn corta cualquier petición de más de 60 s.
- **¿Qué alternativas hay?** PythonAnywhere (siempre encendido, configuración manual), Railway o Fly.io (parecidos
  a Render), un servidor propio (VPS) con nginx + gunicorn + certificado de Let's Encrypt (más control y más
  trabajo), o un contenedor Docker que corre igual en cualquier nube.
