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

Todo esto en PowerShell, dentro de la carpeta `mobile-app`.

### 2.1 Subir el número de versión

```powershell
python subir_version.py
```

Sube a la vez `APP_VERSION` en `www/js/version.js` y `versionCode`/
`versionName` en `android/app/build.gradle` — hazlo SIEMPRE antes de
compilar, los números quedan grabados dentro del APK.

### 2.2 Copiar los cambios web al proyecto Android

```powershell
npx cap copy android
```

(Usa `npx cap sync android` en vez de `copy` solo si además has añadido o
actualizado algún plugin de Capacitor — `copy` basta para cambios de
`www/`.)

### 2.3 Compilar y firmar el APK

```powershell
npx cap open android
```

Y en Android Studio: **Build → Generate Signed Bundle / APK → APK**, con tu
keystore de siempre. No hay una `signingConfig` en el `build.gradle` del
repo (a propósito — el keystore no va en git), así que este paso sigue
siendo por la interfaz gráfica, no por línea de comandos.

Te deja el `.apk` firmado en algo como
`android\app\release\app-release.apk`.

### 2.4 Publicarlo en PythonAnywhere

La primera vez, define el token (una PowerShell nueva después de esto):

```powershell
setx PYTHONANYWHERE_API_TOKEN "tu-token-aqui"
```

Luego, en cada release:

```powershell
python publicar_release.py "android\app\release\app-release.apk" "notas de esta versión"
```

Esto sube `latest.apk` y `latest.json` a `mobile_releases/` en el
servidor — no hace falta ni `git pull` ni reload para esto, es
independiente del despliegue web.

### 2.5 Instalarlo esta semana

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
