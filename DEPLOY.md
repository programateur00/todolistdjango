# Cómo desplegar — Libreta / Strive

Guía rápida para las dos partes: la web Django en PythonAnywhere, y la app
móvil (Capacitor/Android), que también se publica a través de PythonAnywhere
(`mobile_releases/`) para que la app se autoactualice.

Cuenta de PythonAnywhere: `programateur00` (US, `www.pythonanywhere.com`).
Ruta del proyecto en el servidor: `/home/programateur00/todolistdjango`.

---

## 1. Web (Django → PythonAnywhere)

### 1.1 En tu PC (PowerShell), dentro de `libreta-todo-django`

Antes de nada, mira qué tienes sin commitear — puede que haya cosas a medias
que no quieras subir todavía:

```powershell
git status
git diff        # opcional, para revisar el contenido
```

Cuando estés conforme:

```powershell
git add -A
git commit -m "mensaje del cambio"
git push
```

Esto dispara el workflow de GitHub Actions (`tests.yml`), que corre los 115
tests y comprueba que no falte ninguna migración — échale un ojo en
GitHub (pestaña *Actions*) antes de tocar nada en PythonAnywhere, para no
desplegar algo que ya sabes que está roto.

### 1.2 En la consola Bash de PythonAnywhere

(Se abre desde su web: **Consoles** → **Bash** — no es accesible por SSH
desde tu PowerShell salvo que tengas un plan de pago con SSH activado.)

```bash
cd /home/programateur00/todolistdjango
git pull

# Actívala si usas una virtualenv (revisa su nombre en la pestaña Web →
# "Virtualenv" si no te acuerdas):
# workon nombre-de-tu-entorno

pip install -r requirements.txt

# Comprueba el estado ANTES de migrar — si 0011-0019 aparecen sin marcar,
# es la causa más probable de "pocos ejercicios" en los planes de IA:
python manage.py showmigrations tasks

python manage.py migrate
python manage.py collectstatic --noinput
```

### 1.3 Reload

Opción A — panel web: pestaña **Web** → botón **Reload**.

Opción B — desde tu PowerShell, con el mismo token que ya usas para
`publicar_release.py` (variable de entorno `PYTHONANYWHERE_API_TOKEN`):

```powershell
$domain = "programateur00.pythonanywhere.com"   # cambia si usas otro dominio
Invoke-RestMethod -Method Post `
  -Uri "https://www.pythonanywhere.com/api/v0/user/programateur00/webapps/$domain/reload/" `
  -Headers @{ Authorization = "Token $env:PYTHONANYWHERE_API_TOKEN" }
```

### 1.4 Comprobación rápida

Entra en la web, genera un plan de Deporte con IA y confirma que el
catálogo que te propone ya tiene variedad (tren superior e inferior, no
solo 2-3 ejercicios sueltos).

---

## 2. App móvil (Capacitor → APK → publicar en PythonAnywhere)

Todo esto en PowerShell, dentro de la carpeta `mobile-app`. La firma del
APK se sigue haciendo con el asistente de Android Studio, como siempre
lo has hecho — ahí tus datos ya salen rellenos solos, sin tener que
copiar ni buscar ninguna contraseña. El script solo automatiza lo de
alrededor (versión, sync, subida) y te avisa cuándo te toca compilar.

### 2.0 Configuración — solo la primera vez en cada PC

Una única variable de entorno, para poder subir el APK a PythonAnywhere
(una vez; abre una PowerShell **nueva** después para que se aplique):

```powershell
setx PYTHONANYWHERE_API_TOKEN "tu-token-de-pythonanywhere"
```

Nada de keystores ni JDK que configurar — de eso se sigue encargando
Android Studio como hasta ahora.

### 2.1 Todo de un tirón

```powershell
.\release.ps1 -Notes "notas opcionales de esta versión"
```

Este script (en la raíz de `mobile-app`) hace lo siguiente:

1. `python subir_version.py` — sube `APP_VERSION` en `www/js/version.js`
   y `versionCode`/`versionName` en `android/app/build.gradle` a la vez.
2. `npx cap copy android` — copia `www/` al proyecto Android.
3. Se para y te dice que compiles en Android Studio (**Build → Generate
   Signed App Bundle / APK… → APK → Next → Finish**, tus datos ya
   rellenos como siempre) — pulsas Enter cuando termine.
4. Busca el `.apk` que acabas de generar (el más reciente dentro de
   `android\`) y te pide confirmación antes de subirlo.
5. `python publicar_release.py` con ese APK — lo sube a
   `mobile_releases/` en PythonAnywhere. No hace falta `git pull` ni
   reload para esto, es independiente del despliegue web.

### 2.2 Paso a paso, si prefieres ir viendo cada cosa

```powershell
python subir_version.py
npx cap copy android
npx cap open android
```

Compila en Android Studio (Build → Generate Signed App Bundle / APK…
→ APK), y cuando tengas el `.apk`:

```powershell
python publicar_release.py "ruta\a\tu\app-release.apk" "notas de esta versión"
```

### 2.9 Alternativa: 100% por comandos, sin abrir Android Studio nunca

Si en algún momento prefieres que ni siquiera haga falta el clic en
Android Studio (por ejemplo, para automatizarlo del todo), existe la
opción de firmar por Gradle directamente — pero trae dos cosas que
configurar aparte (un JDK 21 para la consola, y las credenciales del
keystore en un fichero local `android/keystore.properties`). No hace
falta para el uso normal — Alex lo probó y prefirió quedarse con el
flujo de arriba (2.0-2.2), que reusa Android Studio. Si quieres retomar
esa vía más adelante, dilo y se recupera esa configuración.

### 2.3 Instalarlo esta semana

- Si ya tienes una build anterior instalada en el móvil: ábrela, el aviso
  de "hay una versión nueva" debería salir solo (compara `APP_VERSION`
  contra `/api/meta/`).
- Si prefieres asegurarte: instala el APK a mano por USB/`adb install`, o
  descárgalo desde el propio móvil (te pedirá el login de la app, porque
  toda la web va detrás del mismo candado usuario/contraseña).

---

## Notas

- Los pasos 1 y 2 son independientes entre sí — puedes desplegar solo la
  web, o solo una nueva build de la app, sin tocar el otro lado.
- Si algún cambio toca solo JS/CSS/plantillas (sin tocar modelos), puedes
  saltarte `migrate` en el paso 1.2 — pero `collectstatic` hace falta
  siempre que cambie algo en `static/`.
