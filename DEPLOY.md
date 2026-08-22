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

Todo esto en PowerShell, dentro de la carpeta `mobile-app`. Todo el proceso
se puede hacer por comandos, firma del APK incluida — no hace falta pasar
por Android Studio en ningún momento. Se usa el mecanismo estándar de
Gradle para firmar en CI (`-Pandroid.injected.signing.*`): las credenciales
del keystore se pasan como propiedades al comando, sin tocar `build.gradle`
ni meter el keystore en el repo.

### 2.0 Configuración — solo la primera vez

Define estas 5 variables de entorno (una vez; abre una PowerShell **nueva**
después para que se apliquen):

```powershell
setx PYTHONANYWHERE_API_TOKEN "tu-token-de-pythonanywhere"
setx LIBRETA_KEYSTORE_PATH "C:\ruta\a\tu\keystore.jks"
setx LIBRETA_KEYSTORE_PASSWORD "contraseña-del-keystore"
setx LIBRETA_KEY_ALIAS "alias-de-tu-clave"
setx LIBRETA_KEY_PASSWORD "contraseña-de-la-clave"
```

(Si tu keystore usa la misma contraseña para el store y la key, repite el
mismo valor en las dos.)

### 2.1 Todo de un tirón

```powershell
.\release.ps1 -Notes "notas opcionales de esta versión"
```

Este script (nuevo, en la raíz de `mobile-app`) encadena los cuatro pasos
de siempre:

1. `python subir_version.py` — sube `APP_VERSION` en `www/js/version.js`
   y `versionCode`/`versionName` en `android/app/build.gradle` a la vez.
2. `npx cap copy android` — copia `www/` al proyecto Android.
3. `gradlew.bat assembleRelease` con las credenciales de firma inyectadas
   por `-P` — compila y firma el APK sin Android Studio. Sale en
   `android\app\build\outputs\apk\release\app-release.apk`.
4. `python publicar_release.py` con ese APK — lo sube a
   `mobile_releases/` en PythonAnywhere. No hace falta `git pull` ni
   reload para esto, es independiente del despliegue web.

### 2.2 Paso a paso, si prefieres ir viendo cada cosa

```powershell
python subir_version.py
npx cap copy android
cd android
.\gradlew.bat assembleRelease `
  "-Pandroid.injected.signing.store.file=$env:LIBRETA_KEYSTORE_PATH" `
  "-Pandroid.injected.signing.store.password=$env:LIBRETA_KEYSTORE_PASSWORD" `
  "-Pandroid.injected.signing.key.alias=$env:LIBRETA_KEY_ALIAS" `
  "-Pandroid.injected.signing.key.password=$env:LIBRETA_KEY_PASSWORD"
cd ..
python publicar_release.py "android\app\build\outputs\apk\release\app-release.apk" "notas de esta versión"
```

(`npx cap open android` + Build → Generate Signed Bundle/APK en Android
Studio sigue funcionando igual si alguna vez prefieres la interfaz
gráfica — ambos caminos firman con el mismo keystore, solo cambia cómo
se lo pasas a Gradle.)

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
