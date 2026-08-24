# MediaPipe vendorizado (no depender de CDN externo en cada sesión)

Antes, `workout.js`/`circuit.js` cargaban la librería y el modelo de
seguimiento en caliente desde `cdn.jsdelivr.net` y
`storage.googleapis.com` cada vez que alguien abría la cámara. Fijar la
versión (`MEDIAPIPE_VERSION`, nunca "latest") ya protegía de que
MediaPipe cambiara la API sin avisar, pero NO protegía de que esas URLs
dejaran de responder — jsdelivr caído, bloqueado en algún país, o que
Google reorganice el hosting del modelo (ya lo han hecho antes). Con
todo esto vendorizado aquí, ninguna de esas dos cosas nos puede dejar
sin cámara a media sesión de entreno.

## Qué hay aquí

Descargado el 2026-08-24 directamente del tarball oficial de npm
(`@mediapipe/tasks-vision@0.10.14`, checksum verificado contra el
registro de npm — sha1 `16c5ddc513408f2a416ccc6ce8ccc797ee02da3b`):

- `vision_bundle.mjs` — el módulo ES que antes se importaba desde
  jsdelivr (`import(".../tasks-vision@VERSION")`).
- `wasm/vision_wasm_internal.{js,wasm}` y
  `wasm/vision_wasm_nosimd_internal.{js,wasm}` — lo que
  `FilesetResolver.forVisionTasks()` pedía antes a
  `.../tasks-vision@VERSION/wasm`.
- `models/pose_landmarker_lite.task` — el modelo de seguimiento
  (`pose_landmarker_lite`, float16, v1), bajado a mano de
  `storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task`
  (el entorno donde se preparó el resto de este cambio no tenía salida
  a ese dominio, solo a un puñado de registros de paquetes — este
  fichero sí se pudo bajar desde un ordenador normal).

Todo vendorizado del todo: no se pide nada a jsdelivr ni a Google en
ninguna sesión de entreno.

## Único sitio donde se decide de dónde sale todo esto

`static/js/mediapipe-vendor.js` — versión vendorizada + las tres rutas
(`MEDIAPIPE_BUNDLE_URL`, `MEDIAPIPE_WASM_BASE_URL`, `MODEL_URL`),
calculadas con `import.meta.url` relativas a esta misma carpeta.
`workout.js` y `circuit.js` importan de ahí, nunca definen ni repiten
nada de esto por su cuenta — así que actualizar solo significa tocar
ESE fichero pequeño, nunca bucear por todo `workout.js`.

## Cómo actualizar de versión (cuando de verdad se quiera, no porque lo decida un tercero)

1. Bajar el tarball nuevo: `npm pack @mediapipe/tasks-vision@X.Y.Z` (o
   `curl -L https://registry.npmjs.org/@mediapipe/tasks-vision/-/tasks-vision-X.Y.Z.tgz -o pkg.tgz`),
   comprobar el `shasum`/`integrity` contra lo que devuelve
   `https://registry.npmjs.org/@mediapipe/tasks-vision/X.Y.Z` antes de
   usarlo.
2. Sustituir `vision_bundle.mjs` y los 4 ficheros de `wasm/` por los
   del tarball nuevo (mismos nombres).
3. Si el modelo también cambia de versión, repetir el paso manual de
   arriba con la URL nueva del modelo (misma carpeta, mismo nombre de
   fichero — o cambiar el nombre y actualizar `MODEL_URL` en
   `static/js/mediapipe-vendor.js` si cambia).
4. Cambiar `MEDIAPIPE_VERSION` en `static/js/mediapipe-vendor.js` (es
   solo informativo — documenta qué versión hay vendorizada aquí, no
   se usa para construir ninguna URL).
5. Probar de verdad con la cámara antes de dar por bueno el cambio —
   una versión nueva de MediaPipe puede cambiar sutilmente cómo
   reporta algún landmark, y eso es justo lo que la lógica de conteo
   de `workout.js`/`circuit.js` da por hecho.
