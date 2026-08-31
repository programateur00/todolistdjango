/* ============================================================
   Contador de dominadas con MediaPipe (100% en el navegador).
   No se sube ni se guarda ningún vídeo — solo los números que
   salen de aquí (reps, duración de cada rep, avisos de descanso).
   ============================================================ */

// De dónde sale MediaPipe (versión vendorizada + rutas a los ficheros
// locales en static/vendor/mediapipe/) se decide en UN ÚNICO fichero,
// static/js/mediapipe-vendor.js — nunca aquí. Así, si algún día hay
// que revendorizar una versión nueva o volver a un CDN externo, solo
// hace falta tocar ese fichero pequeño, no bucear por todo workout.js.
// Ver static/vendor/mediapipe/README.md para el paso a paso.
import { MEDIAPIPE_BUNDLE_URL, MEDIAPIPE_WASM_BASE_URL, MODEL_URL } from "./mediapipe-vendor.js";

// Etiqueta de versión de ESTE fichero, a mano, para poder comprobar en dos
// segundos si un registro exportado (ver exportScissorLog) viene de verdad
// del código que se acaba de entregar o de una copia vieja que el navegador
// (o una pestaña que llevaba rato abierta) seguía ejecutando por debajo.
// Se estampa como primera línea del registro exportado, tal cual está
// cargada en la pestaña que lo generó — así, si no coincide con la que se
// esperaba, la explicación ya no es una suposición: se ve. Cambiar este
// valor cada vez que se toque processDip (o cualquier otra parte que use
// logScissor) de verdad ayuda a diagnosticar.
const WORKOUT_JS_BUILD = "2026-08-31-dominadas-fin-serie-y-sin-distancia";

// Umbral de movimiento (proporcional al ancho de hombros) para
// considerar que hay un cambio de estado real y no ruido de la cámara.
const MOVE_FACTOR = 0.12;
const LIFTOFF_FACTOR = 0.04; // primer indicio de movimiento real (para medir bien la duracion)
const BAR_MARGIN_FACTOR = 0.25; // cuanto por debajo de la barra ya cuenta como "llegaste arriba"
const BAR_OFFSET_FACTOR = 0.05; // empuja la linea de la barra hacia arriba respecto a la muñeca (~2cm en un adulto medio, ver nota abajo)
const HANG_MARGIN_FACTOR = 0.08; // cuanto tienen que estar las munecas por encima de los hombros para considerar que estas colgado
// Umbral, bastante mas generoso que HANG_MARGIN_FACTOR, para decidir que
// de verdad te has SOLTADO de la barra a mitad de serie (no solo que
// hayas dejado de estar "colgado" segun el margen fino de arriba). En lo
// mas alto de una dominada los hombros suben tanto que casi tocan la
// altura de las munecas -siguen agarradas a la barra- asi que con el
// margen fino de HANG_MARGIN_FACTOR una dominada aguantada arriba se
// tomaba por "te has soltado" y cerraba la serie sola (reportado: "he
// aguantado un poco arriba y me ha contado como el principio de una
// serie nueva"). Aqui se exige que la muneca haya bajado CLARAMENTE por
// debajo del hombro -senal inequivoca de brazos ya extendidos hacia
// abajo- antes de dar la serie por terminada.
const RELEASE_MARGIN_FACTOR = 0.15;
const SCALE_TOLERANCE = 0.3; // cuanto puede variar el ancho de hombros (te acercas/alejas) antes de desconfiar del frame
const MIN_REP_SECONDS = 0.3; // por debajo de esto, se descarta como ruido
const HANG_STABLE_MS = 500;   // cuanto tiempo seguido con los brazos en alto para empezar a calibrar
const ARMS_DOWN_STABLE_MS = 400; // cuanto tiempo seguido con los brazos abajo para dar la serie por terminada (evita falsos positivos por un frame ruidoso)
const CALIBRATION_MS = 1200;  // tiempo colgado quieto que se usa como referencia
const REST_ALERT_SECONDS = 90;
// Descanso obligatorio entre series: mientras no haya pasado esto desde
// que se cerró la serie anterior, countRep()/notePostureOk() no cuentan
// nada aunque vuelvas a colocarte y te muevas antes de tiempo — antes
// se contaban repeticiones calladas en pleno descanso si probabas a
// moverte (pedido explícitamente, ver announceRestBlocked). Mismo
// número que REST_ALERT_SECONDS a propósito: es el mismo "90 segundos"
// del que se avisa al usuario al cerrar la serie.
const MIN_REST_MS = REST_ALERT_SECONDS * 1000;
// Dominadas de arquero: mismo criterio de barra/subida-bajada que las
// dominadas normales (ver processArcherPullup), con un añadido — en el
// punto más alto de cada repetición, un brazo tiene que estar doblado
// (el que tira) y el otro estirado (el que se desliza por la barra).
// Igual de laxos que el resto de ángulos del fichero (ver
// PUSHUP_UP_ANGLE_DEG / PUSHUP_DOWN_ANGLE_DEG más abajo): no hace falta
// que sean exactos, solo que uno esté claramente doblado y el otro
// claramente recto.
const ARCHER_BENT_MAX_DEG = 115;     // codo del brazo que tira: como mucho esto para contar como "a 90° más o menos"
const ARCHER_STRAIGHT_MIN_DEG = 150; // codo del brazo que se desliza: al menos esto para contar como "estirado"
// Cuánto tiempo seguido sin detectarte NADA (o casi nada) en el encuadre
// para dar la serie en curso por terminada — sentadillas y los tres
// abdominales tumbado no tienen su propio "te has soltado" como
// dominadas o fondos, así que sin esto una serie se quedaba abierta para
// siempre en silencio si te ibas del encuadre. Salirse del encuadre a
// propósito sirve entonces de "siguiente serie" para quien no quiera
// levantarse del suelo entre series de abdominales (basta con salirse
// un momento y volver a entrar). Más largo que ARMS_DOWN_STABLE_MS a
// propósito: perder la detección un instante (oclusión, un giro brusco)
// es más común que soltarte de una barra, y no debería cerrar la serie
// por un despiste de la cámara.
const OUT_OF_FRAME_STABLE_MS = 1200;
// Ejercicios sin ningún cierre de serie propio (a diferencia de
// dominadas y fondos, que ya se cierran solos al soltarte) — a estos se
// les aplica el cierre por salir del encuadre de arriba, y también el
// cierre por ponerte de pie en el caso de los abdominales tumbado (ver
// ON_GROUND_STABLE_MS más abajo).
const GROUND_STYLE_COUNTERS = new Set(["squat", "crunch", "legraise", "situp", "scissor", "doublecrunch", "pushup", "dip", "inclinepushup", "dumbbellcurl"]);
// Plancha / plancha lateral: a diferencia del resto de GROUND_STYLE_COUNTERS
// (que cuentan repeticiones), aquí se cuenta TIEMPO aguantando la postura
// — el cierre de serie no es "te has puesto de pie o has salido del
// encuadre" en sí (aunque las dos cosas también rompen la postura y acaban
// cerrando la serie de todas formas, ver notePostureBroken) sino "llevas
// PLANK_INVALID_STABLE_MS con la postura rota, sea cual sea el motivo" —
// levantar un brazo para el gesto del vaivén también rompe la postura
// ("apoya los dos brazos"), así que ni siquiera hace falta comprobar
// checkWaveGesture aparte: las mismas tres formas de terminar (ponerte de
// pie, salir del encuadre, agitar la mano) ya rompen la postura por sí
// solas. Por eso plank/sideplank no viven en GROUND_STYLE_COUNTERS ni
// comparten su lógica de cierre.
const CAMERA_POSTURE_COUNTERS = new Set(["plank", "sideplank", "wallsit", "kneeholdbar", "handstand"]);
// Vaivén de la mano para terminar una serie sin ponerte de pie ni salir
// del encuadre — ver checkWaveGesture. Solo para GROUND_STYLE_COUNTERS:
// ya se pueden cerrar poniéndote de pie o saliendo del encuadre, esto es
// una tercera forma para cuando ninguna de esas dos te venga bien en
// ese momento (p.ej. abdominales tumbado sin querer levantarte).
const WAVE_RAISE_MARGIN_FACTOR = 0.05; // cuánto por encima del hombro tiene que estar la muñeca para considerarla "levantada"
const WAVE_MIN_VISIBILITY = 0.4;
const WAVE_WINDOW_MS = 1800; // cuánto historial de la muñeca se guarda para ver el vaivén
const WAVE_MIN_AMPLITUDE_FACTOR = 0.12; // cuánto tiene que moverse a los lados (proporcional al ancho de hombros) para contar como vaivén y no un temblor
const WAVE_MIN_DIRECTION_CHANGES = 2; // al menos dos cambios de sentido (izq-der-izq o al revés) para dar el gesto por válido
// Sentadillas: alternativa a salir del encuadre para terminar la serie
// sin agitar la mano — ponerte de frente a la cámara (dejar de estar de
// perfil). Se detecta con la MISMA visibilidad que ya se calcula para
// elegir de qué lado medir el ángulo de rodilla: de perfil, un lado
// queda tapado por el cuerpo (visibilidades muy distintas); de frente,
// los dos lados se ven parecido.
const SQUAT_FRONTAL_VIS_DIFF_MAX = 0.12; // cuánto pueden diferir left/rightVis y aun así considerarse "de frente"
const SQUAT_FRONTAL_STABLE_MS = 700; // cuánto tiempo de frente y quieto para dar la serie por terminada
// Avisos hablados de estado (que no te ve bien, fin de serie…): el texto
// en pantalla se actualiza siempre, pero repetir el MISMO aviso por voz
// a menudo cansa rápido — así que un aviso idéntico al anterior no se
// repite antes de este tiempo. Subido a propósito: mejor que se sienta
// tranquilo que pesado.
const STATUS_VOICE_REPEAT_GAP_MS = 25000;
// Aun así, si el aviso es DISTINTO al anterior (p.ej. pasas de "no te
// veo bien" a "fin de serie"), se dice enseguida — no tiene sentido
// hacerte esperar. Este margen mínimo es solo para evitar una ráfaga si
// la detección parpadea entre dos estados en un par de frames seguidos.
const STATUS_VOICE_MIN_GAP_MS = 2000;
// No se aplica nada de esto al conteo de repeticiones (speakRep), que
// va aparte y siempre suena al momento.

// Fondos (2ª versión — ver git log para la anterior, basada en nariz
// vs. codos): ahora se cuentan por el ÁNGULO DEL CODO
// (hombro-codo-muñeca), igual que las flexiones, de perfil. La versión
// anterior evitaba el ángulo a propósito porque "solo se mide bien de
// perfil" — pero un ángulo no depende de la distancia a la cámara,
// mientras que nariz-vs-codos (normalizado por ancho de hombros) sí se
// degradaba a cierta distancia (mismo problema real que dominadas: el
// ruido de seguimiento se come el margen cuando el ancho de hombros en
// píxeles se hace pequeño). Y de perfil, además, entras en el encuadre
// mucho más estrecho que de frente (no hace falta encajar las dos
// paralelas a lo ancho), así que también arregla el fallo de "de cerca
// no me ve entera/o".
//
// El problema que resuelve todo lo de abajo: un ángulo de codo recto
// por sí solo NO distingue estar agarrado a las paralelas de estar
// simplemente de pie con los brazos colgando — el ángulo es ~180° en
// los dos casos. Hace falta algo que sea verdad SOLO cuando estás de
// verdad montado en las paralelas.
//
// Primer intento (ya retirado): usar la CADERA como referencia — cuánto
// sube respecto a tu altura de pie. Dos ajustes de umbral sobre ese
// enfoque no arreglaron el problema real, así que se le pidió a Alex un
// registro real de cámara (ver logScissor/exportScissorLog) — y ese
// registro demostró que la cadera es, en la práctica, el punto MENOS
// fiable de los que sigue MediaPipe con esta barra/encuadre: con Alex
// quieto y montado de verdad, "cadera subida" oscilaba de forma salvaje
// entre 0.7 y más de 13 (y llegó a salir negativa), y la recalibración
// automática (al volver a estado null tras bajarse) llegó a fijar la
// referencia de pie en un valor imposible (1.889) a partir de un único
// frame con la cadera mal vista — eso dejó el sistema incapaz de volver
// a armar una serie nueva después de la primera. La causa: el chequeo
// de visibilidad de más abajo promedia CUATRO puntos (hombro, codo,
// muñeca, cadera), así que una cadera apenas vista podía colar igual si
// los otros tres se veían bien.
//
// En ese mismo registro, en cambio, el ángulo de codo (hombro-codo-
// muñeca, que nunca toca la cadera) se movió siempre de forma suave y
// físicamente creíble durante toda la sesión. Así que el criterio de
// "¿sigues montada/o?" usa ahora el HOMBRO en su lugar, con dos
// salvaguardas que la cadera no tenía:
//
//  - El hombro solo actualiza la referencia de pie (dipGroundShoulderY)
//    en frames donde ÉL MISMO (no el promedio de los 4 puntos de más
//    abajo) se ve razonablemente bien (DIP_CALIBRATION_MIN_VISIBILITY)
//    — así un frame puntual con mala lectura no puede arruinar la
//    referencia para el resto de la sesión, que es justo lo que le pasó
//    a la cadera.
//
//  - En vez de un número fijo adivinado en abstracto (que fue el propio
//    problema con la cadera: los umbrales no se correspondían con nada
//    real en cámara), los umbrales de "sigues montada/o" y "te has
//    bajado de verdad" se calculan como una FRACCIÓN del pico de subida
//    de hombro que TÚ MISMA/O has enseñado en ESTA serie
//    (dipSetPeakShoulderRise, ver processDip) — se adaptan solos a tu
//    cuerpo y a tu barra concreta, en vez de una cifra fija que puede no
//    corresponder a nada en tu configuración real.
//
// Segundo bug real, visto en el mismo registro: Alex se subió, hizo
// unos fondos bien contados y, al levantar una mano para rascarse la
// nariz (sin bajarse de las paralelas), esa "repetición" también se
// contó. Causa: el ciclo arriba↔abajo solo miraba el ÁNGULO DEL CODO —
// doblar y estirar el brazo, aunque sea solo para rascarte o ajustarte
// algo, reproduce la misma secuencia de ángulos que un fondo real. La
// diferencia física real es que un fondo de verdad baja el CUERPO
// ENTERO (el hombro baja una cantidad apreciable), mientras que un
// gesto aislado del brazo casi no mueve el hombro. Arreglo: además del
// ciclo de ángulo, se exige que el hombro haya bajado un mínimo
// (DIP_MIN_SHOULDER_DROP_FACTOR) durante el tramo de abajada para que
// la repetición cuente de verdad — si no, se descarta sin cerrar la
// serie (ver countRep en processDip).
//
// Tercer bug real, visto en el PRIMER registro ya con el hombro (tras
// el cambio de arriba): el rediseño contaba bien y ya no colaba el
// gesto de rascarse, pero el cierre automático de serie (bajarte de
// las paralelas) falló al menos una vez y Alex tuvo que recurrir al
// gesto de la mano. El registro mostró la misma FAMILIA de problema que
// tenía la cadera, solo que más sutil: un salto de Y de un solo frame a
// otro (p.ej. 0.966→1.051 en un paso, algo que ningún cuerpo real hace
// en ese tiempo) que, según cuándo pasaba:
//  - si pasaba con this.state === null, arrastraba dipGroundShoulderY
//    (la referencia de pie) lejos de su valor real — se vio
//    0.914→1.064 en poco más de un segundo — dejando después varios
//    segundos sin poder volver a armar una serie nueva;
//  - si pasaba con this.state === "top", inflaba de golpe
//    dipSetPeakShoulderRise (se llegó a ver pico_serie=4.01 cuando el
//    valor real sostenido rondaba 1.4-2.0), lo que subía
//    mountedThreshold por encima de lo alcanzable de verdad y dejaba
//    "montada/o=no" fijo cerca de 22 segundos seguidos aun estando
//    montada/o de verdad.
// Arreglo: el mismo filtro de dos pasos que ya usan las tijeretas desde
// antes (recorte de salto bruto ANTES de suavizar, luego media móvil
// exponencial — ver SCISSOR_MAX_LIFT_JUMP/SCISSOR_SMOOTHING_ALPHA más
// abajo), aplicado a la Y del hombro (DIP_SHOULDER_MAX_Y_JUMP /
// DIP_SHOULDER_SMOOTHING_ALPHA, ver processDip) — así un solo frame con
// mala lectura ya no puede arrastrar ni la referencia de pie ni el pico
// de la serie. El ángulo del codo (elbowAngle) sigue usando el hombro
// BRUTO, sin este suavizado, para no restarle inmediatez a la detección
// de la propia repetición.
//
// Cuarto y quinto ajuste, del siguiente registro real (con el
// suavizado ya puesto): la cuenta de repeticiones y el armado inicial
// iban bien, pero el cierre automático de serie SEGUÍA yendo lento — el
// registro mostró casi 8 segundos de pie, ya claramente bajado de las
// paralelas, sin que se cerrara la serie sola, porque hombro_subido se
// quedaba pegado justo por encima del umbral de desmonte (p.ej. 0.41
// contra un umbral de 0.36) y tardaba en cruzarlo. La raíz: ese umbral
// se compara contra dipGroundShoulderY, una referencia de pie fijada al
// PRINCIPIO de toda la sesión — si te quedas de pie después en una
// postura o a una distancia ligeramente distinta a la de aquel momento,
// el margen entre "de pie de verdad" y el umbral puede ser tan pequeño
// que cualquier ruido tarda varios segundos en cruzarlo. Arreglo,
// idea de Alex: de perfil (como se hace el ejercicio) solo se ve bien
// UN hombro — el otro queda tapado por el propio cuerpo. En cuanto se
// ven los DOS hombros a la vez con buena confianza, es porque te has
// girado a mirar de frente a la cámara — algo que nunca pasa a media
// repetición — así que es una señal binaria, mucho más rápida y fiable
// que esperar a que un número cruce un umbral (ver DIP_FACE_CAMERA_
// VISIBILITY/DIP_FACE_CAMERA_STABLE_MS, processDip). Cerrar la serie así
// se suma a las otras dos formas que ya había (desmonte "de perfil" por
// umbral, y el gesto de la mano) — no las sustituye.
//
// ACTUALIZACIÓN (undécimo bug, ver el comentario largo junto a
// DIP_FACE_CAMERA_STABLE_MS en processDip): con datos reales de más de
// una cámara/postura de perfil, ambos hombros salen visibles ~0.95-1.00
// SIEMPRE, no solo al girarte de frente — así que esta idea, tal como
// estaba, no distinguía nada y quedó DESACTIVADA en processDip.
//
// De paso, otro bug real visto en el mismo tipo de sesiones: a veces no
// llegaba a armar al subirte a las paralelas. La visibilidad para armar
// promediaba CUATRO puntos (hombro+codo+muñeca+cadera), y la cadera no
// se usa para NADA más en esta función desde el rediseño (ver arriba) —
// era el mismo error que ya tuvo el chequeo de la cadera como
// referencia: un punto que ni hace falta puede arruinar la media si se
// ve mal (encuadre justo, cadera tapada por la propia barra, etc.).
// Arreglo: la visibilidad ahora promedia solo hombro+codo+muñeca, los
// tres puntos que de verdad se usan.
//
// Sexto bug real, el más grave con diferencia: tras los arreglos de
// arriba, un registro real mostró CERO fondos contados en toda la
// sesión (30 segundos, con bajadas y subidas claramente reales y
// profundas en el ángulo de codo: 9°, 24°, 47°...) porque el estado NUNCA
// llegaba a "bottom". Causa: hombro_subido (shoulderRise) se normalizaba
// dividiendo por upperArmLength, el largo hombro-codo medido en 2D FRAME
// A FRAME. Ese largo se ve bien de pie (brazo casi vertical, bien de
// perfil a la cámara), pero en el punto más bajo de un fondo real el
// brazo gira hacia atrás y se sale del plano de la cámara — su
// proyección en 2D se acorta mucho aunque el brazo en sí (en 3D) no
// cambie de largo. Un denominador que se encoge así infla artificialmente
// el cociente: el registro mostró hombro_subido cayendo hasta -2.94 en
// mitad de una bajada real, muy por debajo de mountedThreshold, así que
// stillMounted se volvía falso ANTES de que el ángulo de codo llegara a
// DIP_DOWN_ANGLE_DEG — la transición arriba→abajo nunca se cumplía y no
// se contaba ni una repetición. Arreglo: dejar de medir el largo de
// referencia frame a frame y, en su lugar, aprenderlo UNA VEZ, de pie
// (igual que dipGroundShoulderY), usando el largo hombro-CADERA (el
// tronco gira mucho menos que el brazo al bajar/subir) — ver
// dipTorsoLength, DIP_TORSO_LENGTH_MAX_JUMP, processDip. Esto reintroduce
// la cadera en la función, pero SOLO para esta calibración de pie — sigue
// sin formar parte del chequeo de visibilidad de "te veo" (ver el bug de
// arriba) ni de nada que se mida ya montada/o.
const DIP_UP_ANGLE_DEG = 155;   // codo casi recto -> arriba/armado (posición de partida / cuenta la repetición al volver aquí)
const DIP_DOWN_ANGLE_DEG = 90;  // codo doblado en ángulo recto o más -> abajo (mismo criterio "~90°" que ya se usaba antes)
const DIP_MIN_VISIBILITY = 0.4; // visibilidad MEDIA de hombro+codo+muñeca (los tres puntos que se usan de verdad — ya no la cadera, ver arriba), para saber que se te ve en absoluto
const DIP_CALIBRATION_MIN_VISIBILITY = 0.6; // visibilidad del HOMBRO EN SÍ (no la media de arriba) exigida para fiarse de él al (re)calibrar la referencia de pie — ver el bug real de la cadera corrupta, arriba
const DIP_ARM_STABLE_MS = 600;  // cuánto tiempo con el codo recto y quieto para armar el contador — ya NO exige nada de cadera/hombro para armar (ver más abajo, en processDip, por qué)
const DIP_BREAK_STABLE_MS = 1000; // cuánto tiempo seguido con la combinación de desmonte "de perfil" (hombro cerca de la referencia de pie) para dar la serie por terminada
const DIP_BREAK_INTERRUPT_GRACE_MS = 300; // octavo bug: un solo frame (o unos pocos) que deja de cumplir la forma de desmonte, por ruido de un landmark, NO reinicia la cuenta de arriba al momento — hace falta que la interrupción misma se sostenga esto para darla por real (ver processDip)
const DIP_SHOULDER_RISE_MOUNTED_RATIO = 0.5;  // fracción del pico de subida de hombro de ESTA serie por debajo de la cual el ciclo de repetición se congela (te estás bajando/subiendo, no haciendo un fondo)
const DIP_SHOULDER_RISE_DISMOUNT_RATIO = 0.25; // fracción, más estricta todavía, por debajo de la cual se considera que te has bajado de verdad "de perfil"
const DIP_MIN_SHOULDER_DROP_FACTOR = 0.15; // cuánto (en largo de tronco, hombro-cadera — ver el sexto bug, arriba) tiene que bajar el hombro en el tramo de abajada para que la repetición cuente — ver el bug de "rascarse la nariz", arriba
const DIP_SHOULDER_SMOOTHING_ALPHA = 0.3; // media móvil exponencial sobre la Y del hombro (calibración/subida/pico/bajada — NO el ángulo del codo) — mismo valor que SCISSOR_SMOOTHING_ALPHA, ya probado
const DIP_SHOULDER_MAX_Y_JUMP = 0.04; // cuánto puede cambiar como mucho la Y bruta del hombro de un frame al siguiente antes de pasar por la media móvil — un salto mayor no es el cuerpo moviéndose, es un fallo puntual de tracking (ver el tercer bug, arriba, y SCISSOR_MAX_LIFT_JUMP)
const DIP_TORSO_LENGTH_MAX_JUMP = 0.05; // igual que DIP_SHOULDER_MAX_Y_JUMP pero para el largo hombro-cadera (dipTorsoLength) — ver el sexto bug, arriba
const DIP_FACE_CAMERA_VISIBILITY = 0.4; // visibilidad mínima exigida a AMBOS hombros a la vez para entender que te has girado de frente a la cámara (ver el cuarto ajuste, arriba). Bajado de 0.6 a 0.4 (el mismo umbral que DIP_MIN_VISIBILITY, ya probado) — con 0.6 hacía falta acercarse mucho a la cámara para que llegara a dispararse; de momento sin datos exactos de a qué visibilidad se queda un hombro tapado de perfil a distancia normal, así que se deja también sitio en el registro por frame (hombro_izq_vis/hombro_der_vis, más abajo en processDip) para afinar este número con datos reales si 0.4 se queda corto o se pasa
const DIP_FACE_CAMERA_STABLE_MS = 500; // cuánto tiempo seguido con los dos hombros visibles para dar la serie por terminada así — más corto que DIP_BREAK_STABLE_MS porque es una señal mucho más explícita e inequívoca

// Altura de las paralelas: BAJAS (te quedan las piernas dobladas, cerca
// de 90°, para no arrastrar los pies) o ALTAS (a la altura del pecho,
// piernas colgando estiradas, la cadera sube de verdad al montarte). Se
// detecta una vez por serie, nada más armar (dipBarType, ver processDip),
// para saber por CUÁL señal guiarse al detectar que te has bajado
// (desmonte): la cadera (paralelas altas, mismo concepto que ya se hacía
// con el hombro) o la rodilla (paralelas bajas). No hacen falta umbrales
// nuevos: los ángulos de rodilla reutilizan los MISMOS ya probados en
// sentadillas (SQUAT_UP_ANGLE_DEG/SQUAT_DOWN_ANGLE_DEG, más abajo en el
// archivo — misma idea de articulación doblada/estirada) y la subida de
// cadera reutiliza DIP_SHOULDER_RISE_MOUNTED_RATIO/DISMOUNT_RATIO, ya
// probados para el hombro. Esto NO toca cómo se cuentan las repeticiones
// (stillMounted, DIP_MIN_SHOULDER_DROP_FACTOR, dipRepShoulderTopY/MaxY,
// todo eso sigue igual) — solo cómo se decide que has terminado la serie.

// ── Flexiones (push-ups) ────────────────────────────────────────────
// Igual que los fondos, se detectan por un ÁNGULO, no por posición: no
// hay barra ni referencia que calibrar, y un ángulo no depende de lo
// cerca que estés de la cámara. Pero a diferencia de los fondos (que
// evitan a propósito el ángulo del codo porque "solo se mide bien de
// perfil" y el movimiento se ve igual de frente), aquí SÍ se usa el
// ángulo del codo (hombro-codo-muñeca): una flexión se hace boca abajo,
// con el cuerpo horizontal, así que el movimiento YA es de perfil por
// definición y el codo se ve doblarse perfectamente desde el lado.
//
// Justo por eso el aviso de colocación insiste en que LOS CODOS MIREN
// HACIA ATRÁS (pegados al cuerpo), no hacia los lados: un codo que se
// abre hacia fuera se mueve sobre todo en PROFUNDIDAD respecto a la
// cámara (hacia/desde el objetivo), y MediaPipe con una sola cámara no
// mide bien esa profundidad (angle() solo usa x/y, ver más abajo) — el
// ángulo saldría aplanado y las repeticiones no se contarían bien. Con
// el codo hacia atrás, el brazo se dobla en el mismo plano que ve la
// cámara de perfil, y el ángulo se mide de verdad.
//
// Antes de armar el contador hace falta confirmarte en la posición de
// ARRIBA: tumbado boca abajo de verdad (tiltFromHorizontal respecto al
// suelo, no un simple ángulo de línea — ver por qué en processPushup),
// cuerpo estirado (hombro-cadera-tobillo), brazos estirados y manos a
// la altura del pecho con los codos pegados al cuerpo, sostenido un
// rato (igual que crunch/situp con ON_GROUND_STABLE_MS) — así ponerte
// en posición no cuenta como nada. El chequeo de tilt (tumbado de
// verdad, no de pie) es lo que evita que estar de pie con los brazos
// rectos arme el contador por error, así que no hace falta exigir el
// codo doblado para eso.
const PUSHUP_UP_ANGLE_DEG = 160;   // brazo casi recto -> arriba (posición de partida / cuenta la repetición al volver aquí)
const PUSHUP_DOWN_ANGLE_DEG = 90;  // codo doblado en ángulo recto o más -> abajo (mitad de la repetición)
const PUSHUP_MIN_VISIBILITY = 0.4;
const PUSHUP_LINE_MIN_DEG = 150;   // hombro-cadera-tobillo casi recto (cuerpo estirado, no encogido)
// Cierre de serie por romper la postura (te levantas): usa el mismo
// tilt que el gate de armado pero con MENOS sensibilidad a propósito —
// ver el fallo real que arregla en el docstring de processPushup: con
// el codo pegado al cuerpo (como se pide), el brazo tapa la cadera en
// la imagen justo al bajar, y eso ensuciaba la lectura del tilt lo
// bastante como para cerrar la serie sola a media flexión. Un umbral
// más laxo (60° en vez de los 40° de ON_GROUND_MAX_TILT_DEG) y más
// tiempo seguido (1000ms en vez de los 400ms de OFF_GROUND_STABLE_MS)
// dejan pasar ese ruido de seguimiento sin dejar de detectar que te has
// puesto de pie de verdad, que tarda mucho más que eso.
const PUSHUP_BROKEN_TILT_DEG = 60;
const PUSHUP_BREAK_STABLE_MS = 1000;

// ── Curl de bíceps con mancuernas ───────────────────────────────────────
// Se cuenta por el ÁNGULO DEL CODO (hombro-codo-muñeca), igual que
// flexiones/fondos/sentadillas — y, como esos tres, DE PERFIL, no de
// frente.
//
// SEGUNDA VERSIÓN: la primera (cámara de frente, como dominadas, para
// ver las dos mancuernas a la vez) no contaba NINGUNA repetición en
// cámara real — Alex lo probó y el contador se quedaba a cero. La causa
// física: un curl dobla el antebrazo en el plano SAGITAL del cuerpo (de
// delante hacia atrás, respecto a ti) — de frente a la cámara ese plano
// queda casi de canto, perpendicular a la imagen, así que el movimiento
// real apenas se ve en las coordenadas x/y de MediaPipe (que no da
// profundidad fiable con una sola cámara): el ángulo del codo proyectado
// se movía mucho menos que el ángulo real y nunca llegaba a cruzar
// CURL_FLEXED_ANGLE_DEG. De perfil, en cambio, ese plano sagital
// coincide con el plano de la imagen — el antebrazo sube dibujando un
// arco grande y bien visible, exactamente el mismo motivo por el que
// sentadillas/flexiones/fondos ya se miden de perfil (ver el bloque de
// comentarios de processDip más arriba). Por eso ahora, igual que esos
// tres, solo se trackea el lado (izq/der) que mejor se vea — el otro
// queda tapado por el propio cuerpo de perfil, así que no hace falta
// (ni se puede) ver los dos brazos a la vez.
//
// El problema real que pidió Alex resolver, en sus propias palabras: que
// no cuente una repetición falsa si "levanto las manos por error" o si
// "tengo el móvil agarrado [delante] de la cámara". Mirado SOLO por el
// ángulo del codo, esos dos gestos son indistinguibles de un curl de
// verdad (el codo también pasa de recto a doblado). MediaPipe Pose no da
// la forma de la mano (¿cerrada sujetando algo, o abierta?) ni reconoce
// objetos — solo hombro/codo/muñeca — así que "notar si hay algo
// agarrado" no se puede comprobar de forma literal. Lo que SÍ se puede
// comprobar, y sigue siendo válido de perfil, es la FORMA del
// movimiento:
//
//  - Un curl de verdad mantiene el CODO PEGADO AL COSTADO: solo gira el
//    antebrazo, el brazo (hombro-codo) apenas se mueve — de perfil, eso
//    quiere decir que el codo no se adelanta ni se atrasa respecto a la
//    cadera (ver curlElbowDrift en processDumbbellCurl). Levantar las
//    manos sin querer, rascarte o subir el móvil hacia la cara SIEMPRE
//    separa el codo del cuerpo o lo levanta hacia el hombro.
//  - Un curl de verdad NUNCA sube la muñeca por encima de la cara: el
//    punto más alto de un curl con mancuerna queda sobre el pecho/hombro.
//    Mirar el móvil, en cambio, sube la mano a la altura de los ojos.
//    Ver curlWristDrop en processDumbbellCurl.
//
// Estas comprobaciones (codo pegado, muñeca bajo la cara, cámara
// estable) se hacen en TODOS los frames mientras la serie está armada,
// no solo al principio — así un gesto suelto que rompa la forma real de
// un curl a medio ángulo nunca se cuenta como repetición, aunque el
// ángulo de codo por sí solo dibuje un ciclo estirado-doblado-estirado.
//
// Valores de partida, sin probar del todo en cámara real todavía — ver
// processDumbbellCurl si en el próximo test siguen sin cuadrar.
const CURL_EXTENDED_ANGLE_DEG = 155; // codo casi recto -> brazo colgando (posición de partida / cuenta la repetición al volver aquí)
const CURL_FLEXED_ANGLE_DEG = 70;    // codo doblado -> arriba del curl (mitad de la repetición)
const CURL_MIN_VISIBILITY = 0.4;
const CURL_ELBOW_DRIFT_MAX_FACTOR = 0.45; // cuánto puede alejarse el codo de la cadera EN HORIZONTAL, de perfil (proporción al tronco hombro-cadera) y seguir considerándose "pegado al costado"
const CURL_ELBOW_RISE_MAX_FACTOR = 0.25;  // cuánto puede subir el codo respecto a su altura AL ARMAR (proporción al tronco) antes de dejar de considerarse un curl — evita que levantar el BRAZO entero por el hombro (en vez de solo doblar el antebrazo) cuente como curl. Es relativo a la referencia guardada al armar (curlElbowBaselineY), NO a la cadera — ver processDumbbellCurl para el porqué del cambio.
const CURL_WRIST_FACE_MARGIN_FACTOR = 0.15; // margen (proporción al tronco) que la muñeca tiene que quedar POR DEBAJO de la nariz — mirar el móvil sube la mano a la cara, un curl real no pasa de pecho/hombro
const CURL_BROKEN_STABLE_MS = 400; // cuánto tiempo seguido con la forma rota (codo despegado, muñeca a la altura de la cara, o cámara temblando) para dar la serie por rota y cerrarla — corto a propósito: aquí importa más cortar un falso positivo que aguantar un parpadeo de la detección
const CURL_ARM_STABLE_MS = 500; // cuánto tiempo con el brazo estirado y en posición, seguido, para armar el contador
// Temporizador de "aguantando arriba" que pidió Alex: si te quedas con
// el brazo doblado (arriba del curl) sin volver a bajar, no es un curl
// — es una sujeción aguantada (una bolsa, el propio móvil...). No cuenta
// como repetición hasta que de verdad bajes y vuelvas a subir (eso ya lo
// garantiza el ciclo estirado→doblado→estirado de más abajo: aquí no
// hace falta ningún cambio para NO contarlo), pero además se avisa en
// pantalla de cuánto llevas así, para que quede claro que no se está
// contando nada mientras tanto — ver processDumbbellCurl.
const CURL_TOP_HOLD_WARN_MS = 1500;
// Detección de cámara inestable (el móvil sujeto en la mano en vez de
// apoyado en algún sitio fijo, otra forma de leer "tengo el móvil
// agarrado"): se mide cuánto se mueve el punto medio de los hombros de
// un frame al siguiente, en proporción al ancho de hombros — con el
// móvil apoyado ese punto apenas tiembla; sujeto en la mano tiembla de
// forma sostenida. Ver checkCameraShake.
const CURL_CAMERA_SHAKE_FACTOR = 0.03;
const CURL_CAMERA_SHAKE_STABLE_MS = 600;
// Cierre automático de serie por descanso, pedido por Alex: si te
// quedas con el brazo ESTIRADO DEL TODO y quieto (sin ni doblarlo ni
// moverte) más de CURL_REST_AUTO_CLOSE_MS, se interpreta como que has
// terminado la serie y quieres descansar — igual que agitar la mano o
// salirte del encuadre (ver closeActiveSet), pero sin tener que hacer
// ningún gesto: basta con pararse. La siguiente vez que vuelvas a
// armar (CURL_ARM_STABLE_MS con el brazo estirado) empieza una serie
// NUEVA sola, sin tocar nada. Solo se aplica si ya llevas alguna
// repetición contada en la serie (currentSetReps > 0): si todavía no
// has empezado a mover el brazo no hay nada que cerrar. El umbral es
// bastante más largo que una pausa normal entre repeticiones (la mayoría
// de la gente no aguanta 6s parada del todo entre una rep y la
// siguiente sin querer descansar) — vale también para un plan con
// objetivo de series/reps: cerrar la serie aquí solo empieza a contar
// una serie nueva, no fuerza a parar si quieres hacer más de lo que
// pide el objetivo.
const CURL_REST_AUTO_CLOSE_MS = 6000;
const CURL_REST_WARN_MS = 2000; // a partir de aquí se avisa en pantalla de la cuenta atrás, para que no pille por sorpresa



// ── Flexiones inclinadas (pies en alto) ─────────────────────────────
// A petición de Alex: mismo gesto de brazo que una flexión normal (mismo
// ángulo de codo cuenta la repetición, ver más arriba), pero con los pies
// apoyados en alto (una silla, un escalón, un sofá...) en vez de en el
// suelo.
//
// PRIMER intento (retirado tras probarlo en cámara real): usar
// tiltFromHorizontal(hombro, cadera) con un SUELO en vez de un techo —
// por debajo de un mínimo de inclinación, no cuenta como flexión
// inclinada. Falló de dos formas reales, las dos vistas por Alex en la
// primera prueba:
//  (1) una flexión NORMAL, plana, se contó igual — el ángulo hombro-
//      cadera puede salir mayor de lo esperado por el simple ángulo de
//      cámara/postura, sin que los pies estén elevados de verdad, así
//      que un suelo de inclinación por sí solo no distingue "pies en
//      alto" de "flexión plana vista con cierto ángulo";
//  (2) tras armar, cualquier ciclo de ángulo de codo contaba una
//      repetición SIN volver a comprobar nada — al coger el portátil y
//      recolocarlo delante, el gesto de doblar y estirar el brazo para
//      cogerlo se contó como una flexión, porque solo se miraba
//      elbowAngle una vez armado (mismo tipo de bug que "rascarse la
//      nariz" en fondos, ver processDip).
//
// Arreglo, en dos partes:
//
//  A) La señal de "pies en alto" ya NO es un ángulo indirecto
//     (hombro-cadera vs. horizontal), sino la comparación DIRECTA que
//     describe el propio ejercicio: la MUÑECA tiene que quedar
//     claramente por DEBAJO del TOBILLO en la imagen (Y crece hacia
//     abajo, así que tobillo.y < muñeca.y con margen — ver
//     INCLINE_PUSHUP_MIN_FOOT_RISE_FACTOR). Sin techo: por mucho que se
//     eleven los pies, la diferencia solo crece, así que sigue contando
//     igual ("da igual lo alto que pongas los pies"), pero SIN el falso
//     positivo de (1) — una flexión plana de verdad no cumple esto (los
//     pies y las manos quedan a una altura parecida en la imagen), y
//     estar de pie tampoco (de pie, la muñeca queda muy por ENCIMA del
//     tobillo, justo lo contrario).
//
//  B) La postura (pies en alto + cuerpo recto, ver bodyStraight) se
//     comprueba en TODOS los frames mientras la serie está armada, no
//     solo al empezar. En cuanto deja de cumplirse, el frame se
//     descarta sin mirar el ángulo de codo (así un gesto suelto de
//     brazo — coger el portátil, rascarte — nunca se puede convertir en
//     repetición aunque el ángulo por sí solo dibuje el ciclo
//     arriba-abajo-arriba) y, si se sostiene fuera de posición
//     (INCLINE_PUSHUP_BROKEN_STABLE_MS), se cierra la serie sola — el
//     equivalente de "te has puesto de pie" para esta variante, ahora sí
//     posible porque el criterio (B) no se confunde con estar de pie.
//
// El resto de condiciones (ángulo de codo para contar, visibilidad
// mínima) son las de processPushup — mismo gesto de brazo, mismas
// constantes (PUSHUP_UP_ANGLE_DEG, PUSHUP_DOWN_ANGLE_DEG,
// PUSHUP_MIN_VISIBILITY, PUSHUP_LINE_MIN_DEG, ON_GROUND_STABLE_MS).
const INCLINE_PUSHUP_MIN_FOOT_RISE_FACTOR = 0.12; // (muñeca.y - tobillo.y) en proporción al largo de tronco (hombro-cadera) — cuánto tiene que quedar el tobillo por ENCIMA de la muñeca en la imagen. Valor de partida, sin probar en cámara real: si cuesta armar con los pies solo un poco elevados, bajarlo; si sigue colándose una flexión plana, subirlo.
const INCLINE_PUSHUP_BROKEN_STABLE_MS = 400; // cuánto tiempo seguido fuera de posición (pies ya no en alto, o cuerpo encogido) para dar la serie por rota y cerrarla — más corto que PUSHUP_BREAK_STABLE_MS (1000ms) a propósito: aquí un falso positivo importa más que cortar por un parpadeo de la detección

// Sentadillas: se cuentan por el ÁNGULO DE LA RODILLA (cadera-rodilla-tobillo),
// no por la altura de la nariz como en fondos. Un ángulo no depende de lo
// cerca que estés de la cámara, así que tampoco hace falta calibrar nada.
// A diferencia de los fondos (donde se evitó a propósito el ángulo del
// codo porque "solo se mide bien de perfil" y de frente ya se ve la nariz
// bajar igual de bien), aquí SÍ interesa el ángulo — pero eso significa
// que la sentadilla solo se puede contar bien vista DE PERFIL: de frente,
// la cámara no puede distinguir cuánto se dobla la rodilla en profundidad.
// Por eso el aviso en pantalla pide colocarse de lado.
const SQUAT_UP_ANGLE_DEG = 160;   // pierna casi recta -> de pie ("arriba")
const SQUAT_DOWN_ANGLE_DEG = 100; // rodilla suficientemente doblada -> sentadilla ("abajo")
const SQUAT_MIN_VISIBILITY = 0.4;

// ── Abdominales tumbado (crunch, elevación de piernas, abdominal
// completo) ──────────────────────────────────────────────────────────
// Los tres se hacen BOCA ARRIBA con la cámara A UN LADO (de perfil), no
// de frente — así se ve bien cuánto se levantan los hombros o las
// piernas del suelo. El aviso de colocación sale al empezar cada serie
// (ver beginPrep). Los tres arrancan en reposo ("tumbado") y cuentan
// una repetición por cada ciclo completo tumbado→arriba→tumbado, igual
// que dominadas o fondos.
//
// Los tres necesitan saber que el usuario está DE VERDAD tumbado en el
// suelo antes de armar el contador — si no, levantarte de la silla o
// ponerte en posición ya contaba como una repetición completa por sí
// solo (visto en pruebas reales). Se mide con la INCLINACIÓN de la
// línea hombro-cadera respecto a la HORIZONTAL: tumbado, esa línea es
// casi horizontal; de pie o sentado, casi vertical — funciona pase lo
// que pase con la rodilla o el cuello, que no entran en esta cuenta.
// Y, como al colgarte de la barra en dominadas, hace falta verte
// tumbado y QUIETO un rato (ON_GROUND_STABLE_MS) antes de armar, no
// solo un frame — así ponerte en el suelo no cuenta como repetición.
const ON_GROUND_MAX_TILT_DEG = 40;  // por encima de esto, no se considera "tumbado"
const ON_GROUND_STABLE_MS = 600;    // cuanto tiempo tumbado y quieto para armar el contador
const OFF_GROUND_STABLE_MS = 400;   // cuanto tiempo "de pie" seguido para dar la serie por terminada

// Crunch: solo se levantan cabeza y hombros, la cadera casi no se
// dobla — por eso NO se mide un ángulo de cadera (apenas cambiaría),
// sino cuánto sube el HOMBRO por encima de la CADERA (que se queda
// quieta y sirve de referencia). En proporción al muslo (cadera-
// rodilla, que no se mueve en este ejercicio) para no depender de lo
// cerca que estés de la cámara.
const CRUNCH_UP_FACTOR = 0.15;   // hombro claramente por encima de la cadera -> arriba
const CRUNCH_DOWN_FACTOR = 0.05; // hombro casi a la altura de la cadera -> tumbado
const CRUNCH_MIN_VISIBILITY = 0.4;

// Elevación de piernas: aquí la cadera SÍ es el pivote (las piernas
// suben mientras el torso se queda en el suelo), así que se mide el
// ÁNGULO de cadera (hombro-cadera-tobillo) — mismo enfoque que la
// rodilla en sentadillas, y por el mismo motivo no hace falta calibrar
// nada ni depende de la distancia a la cámara. Además, las piernas
// tienen que estar ESTIRADAS para armar el contador (ángulo de rodilla
// cadera-rodilla-tobillo casi recto) — con las rodillas dobladas no es
// elevación de piernas.
const LEG_RAISE_DOWN_ANGLE_DEG = 165; // piernas estiradas en el suelo, en línea con el torso
const LEG_RAISE_UP_ANGLE_DEG = 100;   // piernas levantadas
const LEG_RAISE_STRAIGHT_MIN_DEG = 155; // rodilla casi recta -> pierna estirada, hace falta para armar
const LEG_RAISE_MIN_VISIBILITY = 0.4;
// Consejo de forma: los talones no deberían llegar a tocar el suelo al
// bajar (mejor mantener la tensión y parar justo antes) — a diferencia
// de LEG_RAISE_DOWN_ANGLE_DEG, que solo marca cuándo se da la rep por
// completada, este umbral está pegado a "piernas totalmente en el
// suelo" (~180°) y solo dispara un aviso hablado ocasional, sin afectar
// para nada al conteo de repeticiones.
const LEG_RAISE_TOUCHDOWN_ANGLE_DEG = 172;

// Tijeretas: piernas ESTIRADAS, levantadas "a un palmo" del suelo (ni
// tocando el suelo, ni levantadas del todo como en elevación de
// piernas), alternando cuál pierna queda más alta. La cadera se queda
// apoyada en el suelo y sirve de referencia de altura "0" — se mide
// cuánto sube cada TOBILLO por encima de esa referencia, en proporción
// al muslo (igual que el resto de medidas de este bloque, para no
// depender de la distancia a la cámara). No hay un ciclo "abajo-arriba"
// como en el resto de abdominales tumbado: se cuenta cada vez que
// cambia cuál pierna está arriba, no un ciclo completo.
const SCISSOR_MIN_VISIBILITY = 0.4;
const SCISSOR_LIFT_MIN_FACTOR = 0.10; // tobillo por encima de la cadera, en proporción al muslo — mínimo para contar como "a un palmo"
const SCISSOR_LIFT_MAX_FACTOR = 0.6;  // por encima de esto ya no es "a un palmo" sino una elevación de piernas completa
// Subir solo el margen y el tiempo de confirmación (lo que se probó
// primero) resultó ser perseguirse la cola: subirlos evita los conteos
// de más por ruido, pero el mismo ruido en frames sueltos a veces
// también hacía que la lectura nunca llegara a mantenerse tan alta y
// tanto tiempo seguido, y entonces dejaba de contar repeticiones reales
// una temporada. La causa de fondo es que la altura de cada tobillo,
// frame a frame, viene con ruido — sobre todo justo cuando se cruzan y
// se tapan el uno al otro — así que además de un margen/tiempo
// razonables se suaviza la señal en sí con una media móvil (ver
// SCISSOR_SMOOTHING_ALPHA) antes de compararla.
//
// Un registro real (ver logScissor) enseñó además dos cosas que ni el
// margen ni la media móvil arreglaban por sí solas:
//   1) Con el cuerpo quieto, la diferencia "natural" entre tobillos ya
//      llega a 0.05-0.06 solo por la imprecisión normal de mantener las
//      dos piernas exactamente a la misma altura — un margen tan
//      pequeño contaba eso como un cambio de pierna real.
//   2) De un frame al siguiente aparecían saltos de altura enormes e
//      imposibles para una pierna real (de +0.5 a -2, en una fracción
//      de segundo) — eso no es la pierna moviéndose así de rápido, es
//      MediaPipe confundiendo el tobillo con otro punto durante un
//      frame suelto. Sin nada que lo filtre, ese pico entra tal cual en
//      la media móvil y dispara un cambio que no ha pasado de verdad.
// SCISSOR_MAX_LIFT_JUMP recorta esos saltos ANTES de suavizar (no se
// puede confiar en que la media los absorba sola, ver más abajo).
const SCISSOR_SWITCH_MARGIN_FACTOR = 0.20; // diferencia mínima entre los dos tobillos (ya suavizados) para dar una pierna por claramente "arriba" — bastante más que el "ruido de estar quieto" visto en el registro
const SCISSOR_SWITCH_STABLE_MS = 150; // cuánto tiempo seguido tiene que verse la otra pierna arriba para confirmar el cambio
const SCISSOR_SMOOTHING_ALPHA = 0.3; // media móvil exponencial sobre la altura de cada tobillo: cuánto pesa el frame actual frente al historial reciente. Un pico de un solo frame (típico al cruzarse los tobillos) apenas mueve la media, así que no hace falta un margen/tiempo grandes para ignorarlo
const SCISSOR_MAX_LIFT_JUMP = 0.15; // cuánto puede cambiar como mucho la altura de un tobillo (bruta) de un frame al siguiente. Un salto mayor no es la pierna moviéndose (ninguna pierna real cambia tanto en ~33ms) — es un fallo puntual de tracking, y se recorta a este máximo antes de que llegue a la media móvil

// Abdominal completo (situp): sube el torso ENTERO hasta sentarte — a
// diferencia del crunch, que solo levanta cabeza y hombros. Se mide
// igual que el gate de "tumbado" de arriba (inclinación hombro-cadera
// respecto a la horizontal), de tumbado (~0-30°) a sentado (~55-90°) —
// y no un ángulo de cadera con la rodilla, a propósito: así da igual
// que las rodillas estén dobladas (lo normal, con los pies apoyados) o
// que el cuello esté levantado — ninguno de los dos entra en la cuenta.
const SITUP_DOWN_TILT_DEG = 30; // torso casi horizontal -> tumbado
const SITUP_UP_TILT_DEG = 55;   // torso bien levantado -> sentado
const SITUP_MIN_VISIBILITY = 0.4;

// Doble crunch: a diferencia de crunch/elevación de piernas/abdominal
// completo, el torso se queda LEVANTADO todo el rato, en una posición
// intermedia (ni tumbado del todo ni sentado del todo) — mientras las
// piernas se doblan y estiran, llevando las rodillas al pecho y
// volviendo a estirar, una y otra vez. No hay fase "tumbado" en el
// ciclo, así que el gate de armado/cierre no es "¿estás tumbado?" (como
// en el resto) sino "¿tienes el torso dentro de la banda de inclinación
// de la postura?" — se sale de la serie tanto si te vuelves a tumbar del
// todo como si te llegas a sentar/poner de pie del todo.
//
// Los grados de más abajo son una traducción aproximada de cómo lo narró
// quien pidió esto ("el torso entre 100 y 150 grados") a la misma
// inclinación hombro-cadera respecto a la HORIZONTAL que ya usa
// tiltFromHorizontal() en el resto de este bloque (0°=tumbado,
// 90°=sentado del todo) — no es literalmente el mismo ángulo (el suyo
// suena a cadera-hombro-rodilla, que aquí se evita a propósito, ver
// DOUBLECRUNCH_TUCK_MAX_FACTOR más abajo) pero sí la misma idea: una
// postura reclinada, a medio camino entre tumbado y sentado.
const DOUBLECRUNCH_TILT_MIN_DEG = 30;
const DOUBLECRUNCH_TILT_MAX_DEG = 68;
const DOUBLECRUNCH_MIN_VISIBILITY = 0.4;
// Las repeticiones se cuentan por la distancia RODILLA-HOMBRO, en
// proporción al torso (hombro-cadera, que no cambia mientras se
// mantiene la postura) — y NO por un ángulo de cadera-rodilla como en
// elevación de piernas: ese ángulo se vería contaminado por el propio
// movimiento de levantar el torso, que aquí se supone ya fijo.
const DOUBLECRUNCH_EXTEND_MIN_FACTOR = 1.1; // rodilla lejos del hombro -> piernas estiradas
const DOUBLECRUNCH_TUCK_MAX_FACTOR = 0.7;   // rodilla cerca del hombro -> rodillas al pecho

// Índices de landmarks de MediaPipe Pose que usamos
// Exportados (además de usarse aquí dentro): circuit.js los reutiliza
// para comprobar la postura de plancha/plancha lateral sin duplicar
// los índices de landmarks ni la función de ángulo.
export const NOSE = 0, L_SHOULDER = 11, R_SHOULDER = 12, L_ELBOW = 13, R_ELBOW = 14, L_WRIST = 15, R_WRIST = 16;
export const L_HIP = 23, R_HIP = 24, L_KNEE = 25, R_KNEE = 26, L_ANKLE = 27, R_ANKLE = 28;

/**
 * Ángulo (en grados) en el punto b, formado por los puntos a-b-c. Se usa
 * para medir cuánto se dobla la rodilla (cadera-rodilla-tobillo) en las
 * sentadillas. Solo usa x/y (2D) porque MediaPipe no da una profundidad
 * fiable con una sola cámara — de perfil, x/y ya capturan bien la flexión.
 */
export function angle(a, b, c) {
  const abx = a.x - b.x, aby = a.y - b.y;
  const cbx = c.x - b.x, cby = c.y - b.y;
  const magAB = Math.hypot(abx, aby);
  const magCB = Math.hypot(cbx, cby);
  if (!magAB || !magCB) return null;
  const cos = Math.min(1, Math.max(-1, (abx * cbx + aby * cby) / (magAB * magCB)));
  return (Math.acos(cos) * 180) / Math.PI;
}

/**
 * Inclinación (en grados, 0-90) de la línea a-b respecto a la HORIZONTAL.
 * 0° = línea horizontal (tumbado), 90° = línea vertical (de pie o
 * sentado erguido). Se usa para el gate de "¿está tumbado en el suelo?"
 * en crunch/elevación de piernas/abdominal completo — a diferencia de
 * angle() (el ángulo de una articulación entre tres puntos), esto da la
 * orientación de un solo segmento en la imagen, y a propósito no
 * depende de la rodilla ni del cuello para nada: da igual que las
 * rodillas estén dobladas o la cabeza levantada, la línea hombro-cadera
 * se mide igual.
 */
export function tiltFromHorizontal(a, b) {
  const dx = b.x - a.x, dy = b.y - a.y;
  if (!dx && !dy) return null;
  return (Math.atan2(Math.abs(dy), Math.abs(dx)) * 180) / Math.PI;
}

// ── Plancha / plancha lateral: comprobación de postura ─────────────────
// Se usan tanto aquí (entreno suelto de una tarea) como en circuit.js /
// session-runner.js (dentro de un circuito) — de ahí que vivan en este
// archivo, exportadas, igual que angle()/tiltFromHorizontal() y los
// índices de landmarks: un solo sitio de verdad para la comprobación,
// en vez de mantenerla duplicada en cada reproductor.
//
// LIMITACIÓN CONOCIDA: MediaPipe Pose da la posición 2D de los
// landmarks, no hacia dónde mira la cara — "la nariz boca abajo" no se
// puede comprobar tal cual. Se aproxima con la nariz sin subir por
// encima de la línea de hombros (cabeza no levantada mirando al frente)
// + cuerpo en línea recta + los brazos apoyados. Es una aproximación
// razonable, no una detección exacta de hacia dónde miras.
const PLANK_LINE_MIN_DEG = 148;      // hombro-cadera-tobillo casi recto — algo de margen para cadera/hombros que no salen perfectos por el ruido de la cámara
// Cadera-rodilla-tobillo casi recto — la pierna no puede estar doblada.
// Distingue la plancha de verdad de estar sentada/o con la rodilla
// doblada hacia un lado (delante del portátil, por ejemplo), postura
// que sin este chequeo podía colarse como plancha válida — ver el
// porqué junto a checkPlankPosture.
const PLANK_KNEE_MIN_DEG = 150;
const PLANK_ARMS_DOWN_MARGIN = 0.05; // las muñecas deben quedar a la altura del hombro o por debajo
// Un codo doblado, apoyado en el suelo justo debajo del hombro, en vez
// de un brazo estirado — ver el porqué junto a checkPlankPosture.
const PLANK_ELBOW_BELOW_SHOULDER_MARGIN = 0.35;
// El cuerpo tiene que estar CLARAMENTE alzado del suelo — el hombro
// bastante más arriba en la imagen que el tobillo (los pies se quedan
// apoyados, pero el resto del cuerpo sube, apoyado solo en los
// antebrazos) — ver el porqué junto a checkPlankPosture.
const PLANK_MIN_INCLINE_FACTOR = 0.35;
const PLANK_MIN_VISIBILITY = 0.4;

// La mano de arriba puede ir donde sea (cadera, estirada al techo, sobre
// la pierna...) — no se exige apoyarla en ningún sitio en concreto. Antes
// sí se comprobaba (SIDEPLANK_HIP_TOUCH_FACTOR, ya retirado): la idea era
// solo ayudar a MediaPipe a "leer" bien la postura, nunca una exigencia
// real del ejercicio, pero al ser un requisito bloqueante, un side plank
// hecho tal cual (de lado, apoyado en el codo y los pies, sin tocarse la
// cadera) nunca llegaba a darse por correcto — el aviso "Apoya la mano de
// arriba en la cadera" se repetía sin parar y el aguante no arrancaba
// nunca. Lo que de verdad identifica un side plank correcto es la línea
// del cuerpo, la cadera alzada y el codo de apoyo bien colocado (ver
// justo debajo); ninguno de los tres depende de la mano de arriba.
const SIDEPLANK_LINE_MIN_DEG = 145;      // algo más laxo que la plancha normal: la cadera sube un poco de forma natural
const SIDEPLANK_MIN_VISIBILITY = 0.4;
// La cadera tiene que quedar CLARAMENTE alzada respecto al codo de apoyo
// y el tobillo de abajo (los dos puntos que tocan el suelo) — igual que
// PLANK_MIN_INCLINE_FACTOR en la plancha normal, distingue una plancha
// lateral de verdad de estar simplemente tumbada/o de lado en el suelo,
// relajada/o (esa postura también da una línea recta hombro-cadera-
// tobillo, pero con la cadera a ras de suelo) — ver el porqué junto a
// checkSidePlankPosture. Se deja algo más laxo que en la plancha normal
// porque la elevación de la cadera de lado es, de por sí, más pequeña.
const SIDEPLANK_MIN_HIP_LIFT = 0.22;
// Tope de arriba para hipLift: solo hay mínimo, no máximo, así que nada
// impedía que una cadera disparatadamente alta (te has puesto de pie a
// medias, la cámara te capta a media incorporación) siguiera contando
// como "postura correcta" con tal de superar el mínimo. Según un registro
// real (aguantado subiendo de 6s a 25s mientras la persona ya se había
// puesto de pie y se movía por delante de la cámara), hipLift subía de
// forma continua y suave de ~0.5 (aguante real) a más de 2 según se
// incorporaba — nada ruidoso, un movimiento real de levantarse. Por
// encima de este tope ya no es una plancha lateral con la cadera bien
// alta, es que te has separado del suelo del todo.
const SIDEPLANK_MAX_HIP_LIFT = 1.2;
// SIDEPLANK_MAX_HIP_LIFT arregló levantarte DESPACIO, de forma continua,
// en medio de un aguante — pero según un registro real posterior, no
// cubre otro caso distinto: terminar la serie de verdad (la cadera ya
// vuelve a 0 — "confirmado=no" — y el tramo se cierra bien) y LUEGO
// alejarte de pie, caminando hacia la cámara/ordenador (hace falta,
// para caber en el encuadre). Caminando de pie, con los brazos a los
// lados, hombro-cadera-tobillo puede seguir saliendo casi recto
// (lineAngle 170-180°, como al tumbarte de lado) y hipLift se queda
// DENTRO del rango 0-0.9 (no llega a superar el tope de arriba) — así
// que sin más comprobación, unos segundos de caminar de pie se
// contaban como un aguante nuevo empezando de cero ("me lo ha contado
// como plank" al ir hacia el ordenador tras 41s de plancha lateral
// correctos). Lo que de verdad falta comprobar es la ORIENTACIÓN del
// cuerpo en la imagen: tumbada/o de lado, el tramo hombro-cadera tiene
// que salir prácticamente HORIZONTAL en la imagen (cerca de 0°); de
// pie, ese mismo tramo sale prácticamente VERTICAL (cerca de 90°) —
// algo que ni lineAngle (mide si el cuerpo está doblado, no su
// orientación) ni hipLift (una altura relativa, no un ángulo respecto
// a la imagen) llegan a distinguir. Se usa tiltFromHorizontal(), ya
// definida más arriba y usada en crunch/elevación de piernas/
// abdominal completo para el mismo tipo de comprobación.
const SIDEPLANK_MAX_TILT_DEG = 45;
// Codo de apoyo bien por debajo del hombro — apoyo real en el
// antebrazo (lo pedido: "el codo en el suelo"), no un brazo estirado
// apoyando solo la mano ni un brazo que no llega a apoyar peso.
const SIDEPLANK_ELBOW_BELOW_SHOULDER_MARGIN = 0.22;
// Margen (como fracción del ancho de hombros) que el hombro contrario
// tiene que bajar para que se cambie qué lado se considera "de abajo"
// — ver el porqué junto a checkSidePlankPosture: sin este margen, con
// los dos hombros casi a la misma altura, la decisión saltaba de un
// lado a otro cada frame y desbarataba todas las medidas.
const SIDEPLANK_DOWN_SWITCH_MARGIN_FACTOR = 0.15;

// Pedir la postura de plancha o plancha lateral (alzada, apoyada en el
// antebrazo) de entrada, nada más empezar la serie, es pedir demasiado
// de golpe — sobre todo porque el primer aviso que se puede oír, si algo
// del encuadre no está bien, es "no se te ve entera/o", que no explica
// qué hacer. Por eso las dos pasan primero por un paso más sencillo:
// tumbarte del todo, en CUALQUIER orientación (boca arriba vale igual
// que boca abajo — aquí solo se comprueba que se te ve entera/o y que el
// cuerpo está estirado, nada de brazos ni de si estás alzada/o), para
// confirmar que el encuadre está bien. Solo entonces se pide el paso 2:
// ponerte en la plancha (o plancha lateral) de verdad — ver
// postureGroundConfirmed en processPosture.
//
// La plancha lateral SÍ pasaba antes directa al paso 2, sin este primer
// paso (se asumía que, de lado con las piernas estiradas, ya era fácil
// de detectar a la primera) — pero según lo reportado, no lo era: nada
// más empezar la serie ya se pedía directamente la postura completa
// (incluida, en su momento, la mano de arriba apoyada en la cadera, ver
// más abajo por qué eso ya no se exige), sin ningún paso previo que
// guiara cómo colocarse. Ahora sigue el mismo patrón que la plancha
// normal.
const LYING_FLAT_MIN_DEG = 155;
const LYING_FLAT_MIN_VISIBILITY = 0.4;
// De perfil de verdad, el cuerpo entero (del hombro al tobillo) ocupa
// un buen tramo de la imagen — bastante más que el ancho de hombros.
// Si en vez de eso apuntas el cuerpo HACIA la cámara (los pies "mirando
// hacia abajo" en la imagen pero en realidad mirando al objetivo), la
// profundidad no se ve en una imagen 2D: el cuerpo se "encoge" en la
// imagen aunque el ángulo hombro-cadera-tobillo pueda seguir saliendo
// cerca de recto por casualidad — así que el ángulo solo no basta,
// hace falta comprobar también que el cuerpo se vea realmente
// extendido de lado. Se usa tanto para el paso 1 (tumbarte del todo)
// como para la plancha en sí (ver checkPlankPosture).
const MIN_BODY_LENGTH_FACTOR = 2.2; // tramo hombro-tobillo en la imagen, en proporción al ancho de hombros

export function checkLyingFlat(lm) {
  const lS = lm[L_SHOULDER], rS = lm[R_SHOULDER];
  const lH = lm[L_HIP], rH = lm[R_HIP];
  const lA = lm[L_ANKLE], rA = lm[R_ANKLE];
  // Igual que en tijeretas: de perfil, el lado de detrás pierde
  // confianza aunque MediaPipe siga estimando su posición razonablemente
  // bien — exigir visibilidad alta en los DOS lados a la vez casi nunca
  // se cumplía y el gate de "te veo" fallaba casi todo el rato. Ahora
  // solo hace falta ver bien el lado más cercano a la cámara.
  const leftVis = ((lS.visibility ?? 1) + (lH.visibility ?? 1) + (lA.visibility ?? 1)) / 3;
  const rightVis = ((rS.visibility ?? 1) + (rH.visibility ?? 1) + (rA.visibility ?? 1)) / 3;
  const useLeft = leftVis >= rightVis;
  const sideVis = useLeft ? leftVis : rightVis;
  if (sideVis < LYING_FLAT_MIN_VISIBILITY) {
    return { ok: false, reason: "vis" };
  }
  const shoulder = useLeft ? lS : rS;
  const hip = useLeft ? lH : rH;
  const ankle = useLeft ? lA : rA;
  const shoulderWidth = Math.hypot(lS.x - rS.x, lS.y - rS.y) || 1;
  const lineAngle = angle(shoulder, hip, ankle);
  const bodyLength = Math.hypot(shoulder.x - ankle.x, shoulder.y - ankle.y);
  const bodyLengthFactor = bodyLength / shoulderWidth;
  const angleOk = lineAngle !== null && lineAngle >= LYING_FLAT_MIN_DEG;
  const lengthOk = bodyLengthFactor >= MIN_BODY_LENGTH_FACTOR;
  return {
    ok: angleOk && lengthOk,
    reason: !angleOk ? "angle" : !lengthOk ? "length" : null,
    lineAngle: lineAngle === null ? null : lineAngle.toFixed(0),
    bodyLengthFactor: bodyLengthFactor.toFixed(2),
  };
}

export function checkPlankPosture(lm) {
  const lS = lm[L_SHOULDER], rS = lm[R_SHOULDER];
  const lE = lm[L_ELBOW], rE = lm[R_ELBOW];
  const lH = lm[L_HIP], rH = lm[R_HIP];
  const lK = lm[L_KNEE], rK = lm[R_KNEE];
  const lA = lm[L_ANKLE], rA = lm[R_ANKLE];
  const lW = lm[L_WRIST], rW = lm[R_WRIST];

  // Igual que en tijeretas: de perfil, el lado de detrás pierde
  // confianza aunque MediaPipe siga estimando su posición razonablemente
  // bien — exigir visibilidad alta en los DIEZ puntos (ambos lados) a
  // la vez casi nunca se cumplía y el gate de "te veo" fallaba casi
  // todo el rato aunque la postura fuera correcta (justo lo que
  // mostraba el registro de depuración: "No se te ve entera/o" sin
  // parar). Ahora solo hace falta ver bien el lado más cercano a la
  // cámara (hombro, codo, cadera, rodilla, tobillo y muñeca de ESE
  // lado); el otro lado se usa tal cual lo reporte MediaPipe, tenga la
  // confianza que tenga.
  const leftVis = ((lS.visibility ?? 1) + (lE.visibility ?? 1) + (lH.visibility ?? 1) + (lK.visibility ?? 1) + (lA.visibility ?? 1) + (lW.visibility ?? 1)) / 6;
  const rightVis = ((rS.visibility ?? 1) + (rE.visibility ?? 1) + (rH.visibility ?? 1) + (rK.visibility ?? 1) + (rA.visibility ?? 1) + (rW.visibility ?? 1)) / 6;
  const useLeft = leftVis >= rightVis;
  const sideVis = useLeft ? leftVis : rightVis;

  if (sideVis < PLANK_MIN_VISIBILITY) {
    return { ok: false, reason: "No se te ve entera/o. Ponte de perfil a la cámara, con todo el cuerpo en el encuadre.", debug: { fail: "vis" } };
  }

  const shoulder = useLeft ? lS : rS;
  const hip = useLeft ? lH : rH;
  const knee = useLeft ? lK : rK;
  const ankle = useLeft ? lA : rA;
  const elbow = useLeft ? lE : rE;
  const wrist = useLeft ? lW : rW;

  const shoulderWidth = Math.hypot(lS.x - rS.x, lS.y - rS.y) || 1;
  const shoulderMidY = (lS.y + rS.y) / 2;
  // Antes se promediaba la altura de las DOS muñecas — pero si una
  // apenas se ve, su posición es ruido y desvía la media. Ahora se usa
  // solo la muñeca del lado mejor visto, igual que el resto de medidas.
  const wristMidY = wrist.y;

  // Se calculan TODAS las medidas de golpe, de una — incluso las que
  // ya han fallado un umbral anterior — para que el objeto `debug` de
  // cada return lleve siempre los números completos: así, si hace
  // falta reajustar algún umbral con un registro real (ver logScissor/
  // exportScissorLog, reutilizado aquí para la plancha), no hay que
  // adivinar qué valor tenía en el momento del fallo.
  const lineAngle = angle(shoulder, hip, ankle);
  // Cadera-rodilla-tobillo, aparte de hombro-cadera-tobillo: sentarte
  // con la rodilla doblada hacia un lado (por ejemplo delante del
  // portátil) puede, vista de perfil, dar un tramo hombro-cadera-tobillo
  // que sale casi recto por casualidad — pero la rodilla doblada lo
  // delata. Sin esta comprobación, esa postura sentada se contaba como
  // plancha (lo que se reportó tras ~7s aguantados sin estar haciendo
  // el ejercicio).
  const kneeAngle = angle(hip, knee, ankle);
  const bodyLength = Math.hypot(shoulder.x - ankle.x, shoulder.y - ankle.y);
  const bodyLengthFactor = bodyLength / shoulderWidth;
  const armsDown = (wristMidY - shoulderMidY) / shoulderWidth;
  const incline = (ankle.y - shoulder.y) / shoulderWidth;
  const elbowDrop = (elbow.y - shoulder.y) / shoulderWidth;
  const debug = {
    lineAngle: lineAngle === null ? null : lineAngle.toFixed(0),
    kneeAngle: kneeAngle === null ? null : kneeAngle.toFixed(0),
    bodyLengthFactor: bodyLengthFactor.toFixed(2),
    armsDown: armsDown.toFixed(2),
    incline: incline.toFixed(2),
    elbowDrop: elbowDrop.toFixed(2),
  };

  if (lineAngle === null || lineAngle < PLANK_LINE_MIN_DEG) {
    return { ok: false, reason: "Cadera desalineada — mantén el cuerpo en línea recta, de los hombros a los tobillos.", debug };
  }
  if (kneeAngle === null || kneeAngle < PLANK_KNEE_MIN_DEG) {
    return { ok: false, reason: "Estira las piernas del todo — la rodilla no puede quedar doblada en la plancha.", debug };
  }
  // Si apuntas el cuerpo HACIA la cámara en vez de estar de perfil (los
  // pies "mirando hacia abajo" en la imagen pero en realidad mirando al
  // objetivo), el ángulo de arriba puede salir recto por casualidad
  // aunque no estés de perfil de verdad — ver la nota junto a
  // MIN_BODY_LENGTH_FACTOR, más arriba, para el porqué.
  if (bodyLengthFactor < MIN_BODY_LENGTH_FACTOR) {
    return { ok: false, reason: "Ponte de perfil de verdad (de lado a la cámara), no con los pies apuntando hacia ella.", debug };
  }
  // La cabeza (mirar al suelo o no) NO se comprueba a propósito: no
  // cambia la línea del cuerpo que de verdad importa (pies-cadera-
  // hombros-codos, ver más abajo), y moverla para respirar o mirar
  // alrededor no debería romper una plancha que por lo demás es
  // correcta — antes sí se comprobaba y cada movimiento de cabeza
  // partía el tramo aguantado en una serie nueva.
  if (armsDown < -PLANK_ARMS_DOWN_MARGIN) {
    return { ok: false, reason: "Apoya los dos brazos en el suelo.", debug };
  }
  // "Cuerpo en línea recta" (el check de arriba, hombro-cadera-tobillo)
  // lo cumple TANTO una plancha de verdad, alzada del suelo, COMO estar
  // simplemente tumbado del todo en el suelo, boca abajo — un cuerpo
  // estirado en el suelo también forma una línea recta, solo que a
  // ras de suelo en vez de alzada. MediaPipe no dice si estás tocando
  // el suelo o no (solo posiciones 2D en la imagen), así que sin más
  // comprobación el aviso de "postura correcta" podía dispararse
  // estando tumbado del todo, sin aguantar nada con los brazos — es
  // justo el fallo que describiste: codos en el suelo, cuerpo tumbado,
  // contando como plancha.
  //
  // Lo que de verdad distingue una plancha real: el cuerpo entero tiene
  // que quedar ALZADO del suelo, apoyado solo en los antebrazos y los
  // pies — así que, vista de perfil, la silueta tiene que ir de los
  // pies (abajo, tocando el suelo) subiendo en diagonal hasta los
  // hombros/codos (bastante más arriba en la imagen), en vez de ir
  // todo al mismo nivel. Se comprueba con dos medidas:
  //   1) el HOMBRO tiene que quedar bastante más arriba en la imagen
  //      que el TOBILLO (el cuerpo alzado, no a ras de suelo);
  //   2) el CODO tiene que quedar claramente por debajo del hombro que
  //      sostiene (brazo doblado apoyando peso, no estirado ni
  //      simplemente posado).
  if (incline < PLANK_MIN_INCLINE_FACTOR) {
    return { ok: false, reason: "Sube las caderas: el cuerpo entero tiene que quedar alzado del suelo, apoyado en los antebrazos y los pies, no tumbado.", debug };
  }
  if (elbowDrop < PLANK_ELBOW_BELOW_SHOULDER_MARGIN) {
    return { ok: false, reason: "Ponte boca abajo, apoyada/o en los antebrazos, con los codos doblados justo debajo de los hombros.", debug };
  }
  return { ok: true, debug };
}

/**
 * Bring Sally Up (reto de flexiones, ver static/js/challenges.js) —
 * aguante isométrico ARRIBA o ABAJO, no repeticiones. Reutiliza
 * EXACTAMENTE los mismos umbrales que el contador de flexiones normal
 * (PUSHUP_UP_ANGLE_DEG / PUSHUP_DOWN_ANGLE_DEG / PUSHUP_LINE_MIN_DEG /
 * PUSHUP_MIN_VISIBILITY / ON_GROUND_MAX_TILT_DEG, ver processPushup más
 * abajo) para que "postura correcta" signifique lo mismo en el reto que
 * en una flexión contada de verdad — la única diferencia es qué se
 * pide: aquí no hay repetición que contar, hay que MANTENER el ángulo
 * de codo pedido (recto o doblado) el tiempo que dure ese tramo del
 * guion, igual que checkPlankPosture/checkKneeHoldBarPosture con el
 * suyo. Copia exacta de la misma función en la app móvil (ver
 * mobile-app/www/js/workout.js) — mismo criterio en las dos partes.
 */
function checkPushupHoldPosture(lm, holdTop) {
  const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
  const lElbow = lm[L_ELBOW], rElbow = lm[R_ELBOW];
  const lWrist = lm[L_WRIST], rWrist = lm[R_WRIST];
  const lHip = lm[L_HIP], rHip = lm[R_HIP];
  const lAnkle = lm[L_ANKLE], rAnkle = lm[R_ANKLE];

  const leftVis = (
    (lShoulder.visibility ?? 1) + (lElbow.visibility ?? 1) + (lWrist.visibility ?? 1) +
    (lHip.visibility ?? 1) + (lAnkle.visibility ?? 1)
  ) / 5;
  const rightVis = (
    (rShoulder.visibility ?? 1) + (rElbow.visibility ?? 1) + (rWrist.visibility ?? 1) +
    (rHip.visibility ?? 1) + (rAnkle.visibility ?? 1)
  ) / 5;
  const useLeft = leftVis >= rightVis;
  const vis = useLeft ? leftVis : rightVis;

  if (vis < PUSHUP_MIN_VISIBILITY) {
    return {
      ok: false,
      reason: "No se te ven bien el hombro, el codo, la muñeca, la cadera y el tobillo. Ponte de perfil a la cámara.",
      debug: { fail: "vis" },
    };
  }

  const shoulder = useLeft ? lShoulder : rShoulder;
  const elbow = useLeft ? lElbow : rElbow;
  const wrist = useLeft ? lWrist : rWrist;
  const hip = useLeft ? lHip : rHip;
  const ankle = useLeft ? lAnkle : rAnkle;

  const elbowAngle = angle(shoulder, elbow, wrist);
  const lineAngle = angle(shoulder, hip, ankle);
  const tilt = tiltFromHorizontal(shoulder, hip);
  if (elbowAngle === null || lineAngle === null || tilt === null) {
    return { ok: false, reason: "No se te ve bien de perfil.", debug: { fail: "angle" } };
  }

  const debug = { elbowAngle: elbowAngle.toFixed(0), lineAngle: lineAngle.toFixed(0), tilt: tilt.toFixed(0) };

  if (tilt > ON_GROUND_MAX_TILT_DEG) {
    return { ok: false, reason: "Túmbate boca abajo, de perfil a la cámara.", debug };
  }
  if (lineAngle < PUSHUP_LINE_MIN_DEG) {
    return { ok: false, reason: "Estira el cuerpo — de los hombros a los tobillos en línea recta, sin encoger la cadera.", debug };
  }
  if (holdTop) {
    if (elbowAngle < PUSHUP_UP_ANGLE_DEG) {
      return { ok: false, reason: "Estira los brazos del todo — posición de arriba.", debug };
    }
  } else if (elbowAngle > PUSHUP_DOWN_ANGLE_DEG) {
    return { ok: false, reason: "Dobla los codos hasta abajo — pecho cerca del suelo.", debug };
  }
  return { ok: true, debug };
}

/** Aguante arriba (brazos estirados) — fase "Sube y aguanta" del reto. */
export function checkPushupTopHoldPosture(lm) {
  return checkPushupHoldPosture(lm, true);
}

/** Aguante abajo (codos doblados) — fase "Baja y aguanta" del reto. */
export function checkPushupBottomHoldPosture(lm) {
  return checkPushupHoldPosture(lm, false);
}

export function checkSidePlankPosture(lm, downSideHint = null) {
  const lS = lm[L_SHOULDER], rS = lm[R_SHOULDER];
  const lE = lm[L_ELBOW], rE = lm[R_ELBOW];
  const lH = lm[L_HIP], rH = lm[R_HIP];
  const lA = lm[L_ANKLE], rA = lm[R_ANKLE];
  const lW = lm[L_WRIST], rW = lm[R_WRIST];

  // Igual que en la plancha normal: de perfil, el lado que queda
  // "detrás" (más lejos de la cámara, a veces parcialmente tapado por
  // el propio cuerpo) pierde confianza aunque MediaPipe siga estimando
  // su posición razonablemente bien. Antes se exigía visibilidad mínima
  // en los DIEZ puntos (los dos lados) A LA VEZ, y bastaba con que uno
  // solo (típicamente la muñeca de apoyo, semitapada por la cadera) se
  // fuera un instante por debajo del umbral para que saltara "no se te
  // ve entera/o" sin parar — el mismo problema, ya visto y arreglado,
  // de la plancha normal. Ahora se exige una visibilidad MEDIA
  // razonable entre los diez puntos, no que cada uno por separado la
  // supere.
  const points = [lS, rS, lE, rE, lH, rH, lA, rA, lW, rW];
  const avgVis = points.reduce((sum, p) => sum + (p.visibility ?? 1), 0) / points.length;
  if (avgVis < SIDEPLANK_MIN_VISIBILITY) {
    return { ok: false, reason: "No se te ve entera/o. Ponte de perfil a la cámara, con todo el cuerpo en el encuadre.", debug: { fail: "vis" } };
  }

  const shoulderWidth = Math.hypot(lS.x - rS.x, lS.y - rS.y) || 1;
  // Antes se decidía qué lado está "abajo" (el que apoya en el suelo)
  // mirando qué MUÑECA queda más baja en la imagen — pero la muñeca de
  // arriba suele acabar posada sobre la cadera, medio tapada, que es
  // justo de las partes que peor detecta MediaPipe en esta postura. Los
  // HOMBROS, en cambio, se ven bien de perfil en la plancha lateral
  // (quedan uno claramente encima del otro, sin taparse) — así que
  // ahora se usan ellos para decidir qué lado es el de apoyo: más
  // fiable, como pediste.
  // Antes esto se decidía frame a frame, sin más: en cuanto un hombro
  // quedaba un pelín más bajo que el otro, ESE pasaba a ser "abajo". Con
  // los dos hombros casi a la misma altura (que es lo normal aquí, de
  // perfil) el más mínimo ruido de un frame a otro hacía que la
  // decisión saltara de un lado a otro sin parar — y como TODAS las
  // medidas (línea, altura de cadera, mano-cadera…) dependen de qué
  // lado es "abajo", cada salto mezclaba puntos de un lado con puntos
  // del otro y disparaba lecturas absurdas (p.ej. hipLift saltando de
  // -0.2 a 0.9 en un par de frames) — justo lo que se ve en el registro
  // que mandaste, y por lo que nunca llegaba a confirmarse la postura.
  // Ahora, una vez decidido un lado, hace falta que el OTRO lado quede
  // claramente más bajo (más de SIDEPLANK_DOWN_SWITCH_MARGIN_FACTOR de
  // margen) para cambiar de idea — así un empate o un frame ruidoso no
  // cambia nada.
  const shoulderGap = lS.y - rS.y; // positivo = hombro izquierdo más abajo
  const switchMargin = SIDEPLANK_DOWN_SWITCH_MARGIN_FACTOR * shoulderWidth;
  let leftIsDown;
  if (downSideHint === "left") {
    leftIsDown = shoulderGap > -switchMargin;
  } else if (downSideHint === "right") {
    leftIsDown = shoulderGap > switchMargin;
  } else {
    leftIsDown = shoulderGap > 0;
  }
  const downSide = leftIsDown ? "left" : "right";
  const downShoulder = leftIsDown ? lS : rS;
  const downElbow = leftIsDown ? lE : rE;
  const downWrist = leftIsDown ? lW : rW;
  const downHip = leftIsDown ? lH : rH;
  const downAnkle = leftIsDown ? lA : rA;

  const lineAngle = angle(downShoulder, downHip, downAnkle);
  const armDown = (downWrist.y - downShoulder.y) / shoulderWidth;
  // Codo de apoyo bien por debajo del hombro — ver SIDEPLANK_ELBOW_BELOW_SHOULDER_MARGIN.
  const elbowDrop = (downElbow.y - downShoulder.y) / shoulderWidth;
  // Cadera alzada respecto a los dos puntos que de verdad tocan el
  // suelo (el codo de apoyo y el tobillo de abajo) — ver el porqué
  // junto a SIDEPLANK_MIN_HIP_LIFT: sin esto, tumbarte de lado en el
  // suelo, relajada/o, también pasaría el chequeo de "línea recta" de
  // arriba.
  const groundY = (downElbow.y + downAnkle.y) / 2;
  const hipLift = (groundY - downHip.y) / shoulderWidth;
  // Orientación del cuerpo en la imagen (0°=horizontal/tumbado de lado,
  // 90°=vertical/de pie) — ver SIDEPLANK_MAX_TILT_DEG para el porqué.
  const tilt = tiltFromHorizontal(downShoulder, downHip);

  const debug = {
    lado: downSide === "left" ? "izq. abajo" : "der. abajo",
    lineAngle: lineAngle === null ? null : lineAngle.toFixed(0),
    hipLift: hipLift.toFixed(2),
    elbowDrop: elbowDrop.toFixed(2),
    armDown: armDown.toFixed(2),
    tilt: tilt === null ? null : tilt.toFixed(0),
  };

  if (lineAngle === null || lineAngle < SIDEPLANK_LINE_MIN_DEG) {
    return { ok: false, reason: "Cadera desalineada — mantén el cuerpo en línea recta, de los hombros a los tobillos.", debug, downSide };
  }
  if (tilt === null || tilt > SIDEPLANK_MAX_TILT_DEG) {
    return { ok: false, reason: "Postura rota — pareces estar de pie. Vuelve a tumbarte de lado para la plancha lateral.", debug, downSide };
  }
  if (hipLift < SIDEPLANK_MIN_HIP_LIFT) {
    return { ok: false, reason: "Sube la cadera: el cuerpo entero tiene que quedar alzado del suelo, apoyado en el antebrazo y el lateral de los pies, no tumbada/o de lado.", debug, downSide };
  }
  if (hipLift > SIDEPLANK_MAX_HIP_LIFT) {
    return { ok: false, reason: "Postura rota — parece que te has levantado. Vuelve a la plancha lateral.", debug, downSide };
  }
  if (elbowDrop < SIDEPLANK_ELBOW_BELOW_SHOULDER_MARGIN) {
    return { ok: false, reason: "Apoya el codo en el suelo, justo debajo del hombro — no el brazo estirado.", debug, downSide };
  }
  if (armDown < PLANK_ARMS_DOWN_MARGIN) {
    return { ok: false, reason: "Apoya el antebrazo de abajo en el suelo.", debug, downSide };
  }
  return { ok: true, debug, downSide };
}

// ── Silla en pared (wall sit): comprobación de postura ─────────────────
// La cámara se coloca A UN LADO (de perfil) y algo alejada, para que
// quepa la pierna entera en el encuadre — mismo motivo que en
// sentadillas (ver SQUAT_UP_ANGLE_DEG más arriba): de frente no se
// puede medir cuánto se dobla la rodilla en profundidad.
//
// A diferencia de la sentadilla (que cuenta repeticiones subiendo y
// bajando), aquí se AGUANTA la postura con la espalda apoyada en la
// pared — mismo patrón que la plancha (checkPlankPosture): se
// comprueba la postura frame a frame y se cuenta el TIEMPO aguantado,
// no repeticiones. Reutiliza el mismo mecanismo de aguante
// (CAMERA_POSTURE_COUNTERS, _flushPostureHold, notePostureOk/Broken,
// PLANK_INVALID_STABLE_MS, PLANK_MIN_HOLD_TO_COUNT_SECONDS…) que la
// plancha y la plancha lateral, así que no hace falta duplicar esas
// constantes de tiempo aquí.
//
// A diferencia también de la plancha, no hay un primer paso de
// "túmbate para confirmar que te veo": la postura de partida (de pie)
// ya es trivial de detectar, así que se pide la postura de la silla
// directamente, igual que en sentadillas.
//
// Dos ángulos, de perfil, definen la postura:
//   - RODILLA (cadera-rodilla-tobillo) cerca de 90° — el muslo queda
//     paralelo al suelo, como sentada/o en una silla invisible.
//   - CADERA (hombro-cadera-rodilla) cerca de 90° — el torso, apoyado
//     en la pared, queda perpendicular al muslo.
// Y una comprobación de inclinación del torso respecto a la VERTICAL
// (no a la horizontal, al revés que en checkLyingFlat) para asegurar
// que la espalda está recta y apoyada en la pared, en vez de inclinada
// hacia delante como en una sentadilla libre sin apoyo.
const WALLSIT_KNEE_MIN_DEG = 80;  // rodilla algo más doblada que 90° todavía vale
const WALLSIT_KNEE_MAX_DEG = 100; // por encima de esto, las piernas no están lo bastante dobladas
const WALLSIT_HIP_MIN_DEG = 75;
const WALLSIT_HIP_MAX_DEG = 105;
// Cuánto puede inclinarse el torso hacia delante y aun así contar como
// "espalda apoyada en la pared". tiltFromHorizontal() da 90° con el
// torso en vertical del todo; un valor bastante alto pero con algo de
// margen (una espalda real nunca queda perfectamente a plomo).
const WALLSIT_TORSO_MIN_TILT_DEG = 65;
const WALLSIT_MIN_VISIBILITY = 0.4;

export function checkWallSitPosture(lm) {
  const lS = lm[L_SHOULDER], rS = lm[R_SHOULDER];
  const lH = lm[L_HIP], rH = lm[R_HIP];
  const lK = lm[L_KNEE], rK = lm[R_KNEE];
  const lA = lm[L_ANKLE], rA = lm[R_ANKLE];

  // Igual que en sentadillas/plancha: de perfil, solo hace falta ver
  // bien el lado más cercano a la cámara — exigir buena visibilidad en
  // los dos lados a la vez casi nunca se cumple de perfil.
  const leftVis = ((lS.visibility ?? 1) + (lH.visibility ?? 1) + (lK.visibility ?? 1) + (lA.visibility ?? 1)) / 4;
  const rightVis = ((rS.visibility ?? 1) + (rH.visibility ?? 1) + (rK.visibility ?? 1) + (rA.visibility ?? 1)) / 4;
  const useLeft = leftVis >= rightVis;
  const sideVis = useLeft ? leftVis : rightVis;

  if (sideVis < WALLSIT_MIN_VISIBILITY) {
    return {
      ok: false,
      reason: "No se te ve entera/o. Ponte de perfil a la cámara, algo alejada/o, con la pierna entera (de la cadera al tobillo) en el encuadre.",
      debug: { fail: "vis" },
    };
  }

  const shoulder = useLeft ? lS : rS;
  const hip = useLeft ? lH : rH;
  const knee = useLeft ? lK : rK;
  const ankle = useLeft ? lA : rA;

  const kneeAngle = angle(hip, knee, ankle);
  const hipAngle = angle(shoulder, hip, knee);
  // 0°=torso horizontal (tumbado), 90°=torso en vertical del todo —
  // aquí interesa que sea ALTO (torso recto, apoyado en la pared).
  const tilt = tiltFromHorizontal(shoulder, hip);

  const debug = {
    kneeAngle: kneeAngle === null ? null : kneeAngle.toFixed(0),
    hipAngle: hipAngle === null ? null : hipAngle.toFixed(0),
    tilt: tilt === null ? null : tilt.toFixed(0),
  };

  if (tilt === null || tilt < WALLSIT_TORSO_MIN_TILT_DEG) {
    return { ok: false, reason: "Espalda desalineada — apoya toda la espalda en la pared, sin inclinarte hacia delante.", debug };
  }
  if (kneeAngle === null || kneeAngle < WALLSIT_KNEE_MIN_DEG) {
    return { ok: false, reason: "Te has agachado de más — sube un poco, hasta que la rodilla ronde los 90°.", debug };
  }
  if (kneeAngle > WALLSIT_KNEE_MAX_DEG) {
    return { ok: false, reason: "Baja un poco más, deslizando la espalda por la pared, hasta que el muslo quede paralelo al suelo.", debug };
  }
  if (hipAngle === null || hipAngle < WALLSIT_HIP_MIN_DEG || hipAngle > WALLSIT_HIP_MAX_DEG) {
    return { ok: false, reason: "Ajusta la altura: la cadera tiene que quedar más o menos a 90°, como sentada/o en una silla.", debug };
  }
  return { ok: true, debug };
}

// A diferencia de plancha/plancha lateral/silla en pared, aquí SÍ hace
// falta comprobar que sigues colgada/o de la barra (brazos estirados,
// agarre activo) — no solo la postura de las piernas. Se reutiliza el
// mismo margen que ya usan las dominadas (HANG_MARGIN_FACTOR): cuánto
// tienen que estar las muñecas por encima de los hombros para contar
// como "colgado".
//
// De frente a la cámara (no de perfil, como plancha/silla en pared): al
// colgarte de una barra ya te pones mirando hacia ella, así que pedir
// perfil sería forzar una postura rara. De frente también se ven bien
// los dos lados a la vez (hombros, cadera, rodillas, muñecas), así que
// aquí se promedian izquierda y derecha en vez de elegir "el lado mejor
// visto" como en los ejercicios de perfil.
const KNEEHOLDBAR_MIN_VISIBILITY = 0.4;
// Se probaron dos versiones anteriores antes de esta: un ángulo en
// cadera+rodilla (con un punto ciego de frente a la cámara, ver commits
// previos), y luego la distancia cadera-tobillo (normalizada por el ancho
// de hombros) — que sobre el papel tenía sentido (colgada/o con la pierna
// estirada el tobillo queda lejos de la cadera; al "encoger" se acerca),
// pero en la práctica NUNCA llegaba a marcar bien, según lo reportado y
// confirmado con el registro de depuración real: raiseRatio se quedaba
// entre 1.2 y 4 sin bajar de 1.0 por mucho que se subieran las rodillas a
// la altura de la cadera de verdad.
//
// El fallo: "subir las rodillas a la altura de la cadera" no significa
// que el TOBILLO se acerque a la cadera — con la rodilla doblada en
// ángulo (la espinilla colgando hacia abajo desde la rodilla, no pegada
// al muslo, que es justo la postura pedida — ver KNEEHOLDBAR_TIPS/
// notePostureOk), el tobillo se queda por debajo de la rodilla y por
// tanto lejos de la cadera, aunque el MUSLO (y la rodilla) ya estén
// perfectamente a la altura de la cadera. Medir tobillo-cadera es medir
// lo que sube el tobillo, no lo que sube la rodilla — y son cosas
// distintas en cuanto la rodilla se dobla.
//
// Ahora se mide directamente lo que se pide: la altura (posición Y en la
// imagen) de la rodilla respecto a la cadera, nada de distancias con el
// tobillo ni el propio tobillo como punto necesario — con la cámara de
// frente (confirmado: así se usa este ejercicio), subir el muslo hasta
// la cadera se ve directamente como que la rodilla sube en la imagen
// hasta quedar a la altura de la cadera o más arriba. Se normaliza por
// el ancho de hombros (no por el torso cadera-hombro: colgada/o con los
// brazos estirados por encima de la cabeza el torso se estira hacia
// arriba, así que usarlo de referencia encogía el margen también con las
// piernas quietas).
const KNEEHOLDBAR_KNEE_HIP_MAX_GAP_FACTOR = 0.4;

export function checkKneeHoldBarPosture(lm) {
  const lS = lm[L_SHOULDER], rS = lm[R_SHOULDER];
  const lH = lm[L_HIP], rH = lm[R_HIP];
  const lK = lm[L_KNEE], rK = lm[R_KNEE];
  const lW = lm[L_WRIST], rW = lm[R_WRIST];

  // Ya no hace falta el tobillo (ver más arriba el porqué) — con eso
  // fuera, la rodilla es el punto más "exigente" y de frente, encogida o
  // no, suele verse bien.
  if ([lS, rS, lH, rH, lK, rK, lW, rW].some((p) => (p.visibility ?? 1) < KNEEHOLDBAR_MIN_VISIBILITY)) {
    return {
      ok: false,
      reason: "No se te ve entera/o. Ponte de frente a la cámara, algo alejada/o, para que se vea todo el cuerpo colgado, de las manos a las rodillas.",
      debug: { fail: "vis" },
    };
  }

  const shoulderMid = { x: (lS.x + rS.x) / 2, y: (lS.y + rS.y) / 2 };
  const hipMidY = (lH.y + rH.y) / 2;
  const kneeMidY = (lK.y + rK.y) / 2;
  const wristMidY = (lW.y + rW.y) / 2;
  const shoulderWidth = Math.hypot(lS.x - rS.x, lS.y - rS.y);

  const debug = {
    hanging: shoulderWidth ? (wristMidY < shoulderMid.y - HANG_MARGIN_FACTOR * shoulderWidth ? "sí" : "no") : null,
  };

  if (!shoulderWidth || wristMidY >= shoulderMid.y - HANG_MARGIN_FACTOR * shoulderWidth) {
    return { ok: false, reason: "No pareces estar colgada/o de la barra — agárrate con los brazos estirados.", debug };
  }

  // Y crece hacia abajo en la imagen: positivo = la rodilla queda por
  // debajo de la cadera (sin subir todavía), negativo o cero = la
  // rodilla ya está a la altura de la cadera o por encima.
  const kneeHipGap = (kneeMidY - hipMidY) / shoulderWidth;
  debug.kneeHipGap = kneeHipGap.toFixed(2);

  if (kneeHipGap > KNEEHOLDBAR_KNEE_HIP_MAX_GAP_FACTOR) {
    return { ok: false, reason: "Dobla más las rodillas, subiéndolas hasta dejarlas más o menos a la altura de la cadera.", debug };
  }
  return { ok: true, debug };
}

// Paso 1 de kneehold en barra (ver postureGroundConfirmed en processPosture,
// mismo patrón de dos pasos que plancha/plancha lateral): antes de pedir
// que subas las rodillas hace falta confirmar que ya te has agarrado a la
// barra — solo mira hombros y muñecas (ni cadera ni tobillo), así que
// vale aunque todavía no se te vea entero/a en el encuadre (por ejemplo,
// mientras te estás colocando). Con esto, el aviso de "no se te ve" que
// antes salía sin más mientras te acercabas a la barra pasa a ser un
// "ve y agárrate a la barra" bien concreto — ver postureWaitingMessage.
//
// Devuelve también "visible" (hombros y muñecas detectados, da igual si
// ya estás colgada/o o no) por separado de "ok" (además colgada/o de
// verdad) — así, en processPosture, se puede avisar por voz nada más
// verte aparecer en la cámara ("Te veo. ¡Listo! Cuélgate…"), igual que
// hace dominadas con startupVoiceGiven, sin esperar a que ya estés
// colgada/o para decir nada.
function checkKneeHoldBarHanging(lm) {
  const lS = lm[L_SHOULDER], rS = lm[R_SHOULDER];
  const lW = lm[L_WRIST], rW = lm[R_WRIST];

  const visible = ![lS, rS, lW, rW].some((p) => (p.visibility ?? 1) < KNEEHOLDBAR_MIN_VISIBILITY);
  if (!visible) {
    return { ok: false, visible: false };
  }

  const shoulderMidY = (lS.y + rS.y) / 2;
  const wristMidY = (lW.y + rW.y) / 2;
  const shoulderWidth = Math.hypot(lS.x - rS.x, lS.y - rS.y);
  if (!shoulderWidth || wristMidY >= shoulderMidY - HANG_MARGIN_FACTOR * shoulderWidth) {
    return { ok: false, visible: true };
  }
  return { ok: true, visible: true };
}

// Pino (handstand): a diferencia de dead hang (ver historial de este
// archivo más abajo — un caso especialmente difícil, con varios intentos
// descartados, porque "colgarte" y "estar de pie estirando los brazos"
// se ven casi igual para MediaPipe), un pino no tiene ese problema de
// raíz: el cuerpo entero queda INVERTIDO, con la cadera por encima de
// los hombros en la imagen — algo que ninguna postura normal (de pie,
// agachada/o, o incluso tocándose los pies) puede producir. Esa única
// señal ya distingue un pino de cualquier otra cosa sin ambigüedad, así
// que no hace falta ningún truco de suavizado ni de referencia personal
// como los que sí hicieron falta en dead hang.
//
// Solo dos condiciones, tal y como se pidió: la cadera por encima de
// los hombros (cuerpo invertido) y los codos/muñecas por debajo de la
// cadera (los brazos aguantando el peso cerca del suelo, no estirados
// hacia arriba). No se exige nada de las piernas — ni que estén rectas
// ni que se vean siquiera — porque en un pino real los pies suelen
// salirse del encuadre (sobre todo con apoyo en la pared, muy cerca de
// esta), y exigir visibilidad ahí solo generaría fallos falsos por
// encuadre, no por mala postura.
//
// Sin paso 1 de confirmación (a diferencia de plancha/kneehold/dead
// hang): con una señal tan clara no hace falta pedir una postura
// intermedia antes de la de verdad — mismo criterio que silla en pared
// (ver checkWallSitPosture y postureWaitingMessage/processPosture, más
// abajo, donde "handstand" tampoco entra en el paso 1).
//
// Vale igual con o sin apoyo (pared, compañera/o…): la cámara no ve la
// pared, así que la postura del cuerpo que se mide es la misma se apoye
// o no — no hace falta ninguna lógica aparte para cada caso.
const HANDSTAND_MIN_VISIBILITY = 0.35; // algo más laxo que el resto: bocabajo, MediaPipe pierde algo de confianza y no debe tumbar la cuenta por eso
// Margen relativo al ancho de hombros, igual que HANG_MARGIN_FACTOR en
// dead hang/kneehold — pequeño a propósito, para que baste con estar
// claramente invertida/o o con los brazos claramente abajo, sin exigir
// una separación exagerada que sea fácil de perder por el balanceo
// normal de un pino.
const HANDSTAND_MARGIN_FACTOR = 0.08;

export function checkHandstandPosture(lm) {
  const lS = lm[L_SHOULDER], rS = lm[R_SHOULDER];
  const lE = lm[L_ELBOW], rE = lm[R_ELBOW];
  const lW = lm[L_WRIST], rW = lm[R_WRIST];
  const lH = lm[L_HIP], rH = lm[R_HIP];

  if ([lS, rS, lE, rE, lW, rW, lH, rH].some((p) => (p.visibility ?? 1) < HANDSTAND_MIN_VISIBILITY)) {
    return {
      ok: false,
      reason: "No se te ve entera/o. Ponte de forma que se vean las manos, los brazos y la cadera en el encuadre.",
      debug: { fail: "vis" },
    };
  }

  const shoulderWidth = Math.hypot(lS.x - rS.x, lS.y - rS.y);
  if (!shoulderWidth) {
    return { ok: false, reason: "No se te ve bien. Aléjate un poco de la cámara.", debug: { fail: "vis" } };
  }
  const margin = HANDSTAND_MARGIN_FACTOR * shoulderWidth;

  const shoulderMidY = (lS.y + rS.y) / 2;
  const elbowMidY = (lE.y + rE.y) / 2;
  const wristMidY = (lW.y + rW.y) / 2;
  const hipMidY = (lH.y + rH.y) / 2;

  const debug = {
    invertido: hipMidY < shoulderMidY - margin ? "sí" : "no",
  };

  // Y crece hacia abajo en la imagen: la cadera tiene que quedar POR
  // ENCIMA de los hombros (Y menor) para que el cuerpo esté invertido.
  if (hipMidY >= shoulderMidY - margin) {
    return { ok: false, reason: "Todavía no pareces estar en el pino — sube la cadera por encima de los hombros.", debug };
  }

  // Brazos por debajo de la cintura: codos y muñecas por debajo de la
  // cadera en la imagen (Y mayor), como pide el ejercicio — manos en el
  // suelo aguantando el peso, no estiradas hacia arriba.
  if (elbowMidY <= hipMidY + margin || wristMidY <= hipMidY + margin) {
    return { ok: false, reason: "Lleva los brazos hacia el suelo, por debajo de la cadera.", debug };
  }

  return { ok: true, debug };
}

// Cuánto tiempo seguido con la postura rota (por el motivo que sea: te
// has puesto de pie, has salido del encuadre, has levantado un brazo…)
// antes de dar la serie (el tramo aguantado) por terminada — igual que
// ARMS_DOWN_STABLE_MS en dominadas, para no cortar la serie por un
// parpadeo de la cámara o un ajuste rápido de postura.
//
// Este valor estaba en 2000ms, y con eso "seguía contando" bastante
// después de dejar la postura de verdad — según lo reportado y un
// registro real: al levantarte, notePostureOk() pone postureInvalidSince
// a null en CUANTO hay un frame confirmado como correcto (aunque sea un
// parpadeo de apenas 350ms en medio del ruido de la cámara mientras te
// levantas), así que el reloj de "llevas tanto tiempo mal" se reiniciaba
// una y otra vez sin llegar nunca a acumular 2 segundos SEGUIDOS de
// postura rota — y la serie no se cerraba en 15+ segundos de estar ya
// de pie. Bajado a un valor bastante más corto: sigue siendo más del
// doble de POSTURE_FLICKER_STABLE_MS (así que un parpadeo real de la
// cámara no corta nada), pero ya no da tanto margen a que una postura
// realmente rota, con solo algún frame ruidoso "de vuelta a correcto"
// de por medio, seguido contando como si nada.
const PLANK_INVALID_STABLE_MS = 800;
// Un tramo aguantado tan corto (medio segundo, un frame ruidoso que por
// casualidad cruzó el umbral) no es una serie de verdad — contarlo como
// tal (y sumar 1 al número de serie en pantalla) es justo el "me ha
// contado 4 series de 0 segundos" que se reportó: cada parpadeo breve
// de "postura correcta" en medio del ruido, seguido de
// PLANK_INVALID_STABLE_MS roto, cerraba una "serie" vacía. Por debajo de
// este mínimo, el tramo se descarta en silencio (ver _flushPostureHold)
// en vez de contarse. Subido de 1.5s a 2s: con PLANK_INVALID_STABLE_MS
// más corto (arriba), un tramo aún colándose por ruido durante la
// colocación tiene menos margen para llegar a 1.5s seguidos — 2s da un
// poco más de aire de sobra sin afectar a ningún aguante real (que dura
// muchos segundos de largo).
const PLANK_MIN_HOLD_TO_COUNT_SECONDS = 2;
// Un par de frames sueltos con una lectura ruidosa (justo en el borde
// de un umbral) no deberían hacer parpadear el aviso en pantalla y por
// voz entre "aguantando" y "no se te ve/postura incorrecta" todo el
// rato — eso es justo lo que se reportó como estresante. Por eso, antes
// de reflejar un cambio de correcto↔incorrecto en pantalla, hace falta
// que se mantenga así un ratito seguido — el mismo patrón de
// "candidato + tiempo seguido" que se usa en el resto del fichero (ver
// SCISSOR_SWITCH_STABLE_MS) aplicado aquí a si la postura es válida o
// no, en vez de a qué pierna está arriba. Nótese que esto es aparte de
// PLANK_INVALID_STABLE_MS (arriba): ese decide cuándo CERRAR la serie;
// esto decide cuándo cambiar lo que se ve/oye en pantalla.
const POSTURE_FLICKER_STABLE_MS = 350;
// Kneehold en barra a veces necesita más margen que el resto de
// CAMERA_POSTURE_COUNTERS: con la rodilla ya muy flexionada (subida de
// verdad hasta la cadera o más arriba), de frente a la cámara, la propia
// rodilla puede quedar parcialmente tapada por el muslo o el tronco —
// justo cuando MÁS arriba está, no cuando menos — y eso hace que
// MediaPipe se equivoque de vez en cuando durante un segundo largo, no
// solo un frame suelto. Según lo reportado: subir aún más las rodillas
// en mitad de un aguante que iba bien hacía que dejara de contar, y el
// registro real muestra kneeHipGap saltando a valores altos (como si la
// rodilla hubiera bajado mucho) varios frames seguidos mientras
// hanging=sí — un fallo de seguimiento, no un cambio real de postura.
// Plancha/plancha lateral no tienen este problema (de perfil, con las
// piernas quietas, no hay flexión extrema ni autoclusión), así que se
// deja su margen tal cual y solo se amplía para kneeholdbar.
const KNEEHOLDBAR_FLICKER_STABLE_MS = 700;
const KNEEHOLDBAR_INVALID_STABLE_MS = 1800;
// Pino: igual que kneehold en barra, se usa un margen más largo que
// plancha — bocabajo y en equilibrio, es normal que MediaPipe tenga
// alguna racha de seguimiento ruidoso mientras te balanceas un poco
// (algo inevitable en un pino de verdad), y eso no debería bastar para
// dar la postura por rota ni hacer parpadear el aviso en pantalla.
const HANDSTAND_FLICKER_STABLE_MS = 700;
const HANDSTAND_INVALID_STABLE_MS = 1800;
// Consejos rotativos mientras se aguanta: el primero no sale hasta pasado
// un rato (deja asentar la postura, no interrumpas nada más empezar), y
// van rotando cada PLANK_TIP_INTERVAL_MS mientras dure el aguante — se
// hablan directamente con speak(), no con announceStatus(), para no
// pisar el texto en pantalla del cronómetro de aguante (ver notePostureOk).
// Cada consejo se dice UNA sola vez por serie (sin dar la vuelta a la
// lista): en un aguante largo, antes se repetían en bucle cada 20s todo
// el rato, lo cual, sumado a los avisos de postura, se sentía como que
// "no se callaba" — ahora, tras los 3 consejos, se queda callado el
// resto de la serie.
const PLANK_TIP_FIRST_AT_SECONDS = 8;
const PLANK_TIP_INTERVAL_MS = 25000;
const PLANK_TIPS = [
  "Consejo: aprieta el abdomen y los glúteos, como si te fueran a dar un golpe en la tripa — no dejes que la cadera caiga.",
  "Consejo: no subas la cadera en forma de tejado. Mantén el cuerpo en línea recta, de los hombros a los tobillos.",
  "Consejo: respira con normalidad, no aguantes el aire — se aguanta más tiempo respirando bien.",
];
const SIDEPLANK_TIPS = [
  "Consejo: empuja la cadera hacia arriba, no dejes que caiga hacia el suelo.",
  "Consejo: apila los pies uno sobre otro y mantén el cuerpo en línea recta, sin doblarte por la cintura.",
  "Consejo: si te cuesta aguantar, apoya la rodilla de abajo en el suelo para quitar carga, sin perder la línea del cuerpo.",
];
const WALLSIT_TIPS = [
  "Consejo: reparte el peso entre los dos pies y no dejes que las rodillas se junten hacia dentro.",
  "Consejo: mantén toda la espalda pegada a la pared, sin arquear la zona baja.",
  "Consejo: respira con normalidad, no aguantes el aire — se aguanta más tiempo respirando bien.",
];
const KNEEHOLDBAR_TIPS = [
  "Consejo: no balancees el cuerpo para ayudarte a subir las rodillas — el impulso hace trampa, controla el movimiento.",
  "Consejo: aprieta el abdomen mientras aguantas, como en un crunch, en vez de dejar que cuelguen solo del agarre.",
  "Consejo: respira con normalidad, no aguantes el aire — se aguanta más tiempo respirando bien.",
];
const HANDSTAND_TIPS = [
  "Consejo: reparte el peso entre los dedos y la base de la mano, no solo la palma — así controlas mejor el equilibrio.",
  "Consejo: aprieta el abdomen y los glúteos para mantener el cuerpo recto, como en la plancha.",
  "Consejo: mira a un punto fijo entre las manos, en vez de al frente — ayuda a mantener el equilibrio.",
];

/** Segundos aguantados -> texto para el contador grande ("14s"). */
function formatHoldSeconds(totalSeconds) {
  return `${Math.max(0, Math.round(totalSeconds))}s`;
}

// Números en palabras para la voz (1–99). No basta con pasarle el
// dígito tal cual a SpeechSynthesisUtterance: según el motor de TTS
// del navegador, un número compuesto como "23" a veces se lee dígito a
// dígito ("dos, tres") en vez de "veintitrés". Escribiéndolo en
// palabras se elimina esa ambigüedad. Cubre de sobra hasta el 50 (lo
// pedido), y no hay techo duro: si algún día alguien encadena más de
// 99 reps en una sola serie, se lee el número tal cual como último
// recurso, pero eso ya no es un caso realista.
const UNIDADES_ES = ["", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"];
const ESPECIALES_ES = {
  10: "diez", 11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "quince",
  16: "dieciséis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve",
  20: "veinte", 21: "veintiuno", 22: "veintidós", 23: "veintitrés",
  24: "veinticuatro", 25: "veinticinco", 26: "veintiséis", 27: "veintisiete",
  28: "veintiocho", 29: "veintinueve",
};
const DECENAS_ES = { 30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa" };

export function numeroEnPalabras(n) {
  if (n < 10) return UNIDADES_ES[n];
  if (n < 30) return ESPECIALES_ES[n];
  if (n < 100) {
    const decena = Math.floor(n / 10) * 10;
    const resto = n % 10;
    return resto === 0 ? DECENAS_ES[decena] : `${DECENAS_ES[decena]} y ${UNIDADES_ES[resto]}`;
  }
  return String(n);
}

// Si la voz de conteo está activada — mismo ajuste que WorkoutSession usa
// (ver voiceEnabled en el constructor), expuesto suelto para que
// circuit.js/plan-session.js puedan respetarlo también en la cuenta
// atrás/adelante de plancha/plancha lateral/etc. dentro de un circuito o
// una sesión de plan, donde no hay ninguna instancia de WorkoutSession.
export function isVoiceEnabled() {
  return localStorage.getItem("libreta.voiceReps") !== "0";
}

/**
 * Habla un texto en voz alta con la Web Speech API — extraído de
 * WorkoutSession.speak() (que ahora es un envoltorio fino de esto, ver
 * más abajo) para que circuit.js/plan-session.js puedan usarlo también,
 * sin duplicar aquí la misma llamada a speechSynthesis.
 */
export function speakOut(texto, { flush = true, rate = 1 } = {}) {
  if (typeof speechSynthesis === "undefined") return;
  try {
    if (flush) speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(texto);
    u.lang = "es-ES";
    u.volume = 1;
    u.rate = rate;
    u.pitch = 1;
    speechSynthesis.speak(u);
  } catch (e) {
    console.error("speechSynthesis", e);
  }
}

function el(id) { return document.getElementById(id); }

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.55);
    // segundo pitido, un poco más agudo, medio segundo después
    setTimeout(() => {
      const ctx2 = new (window.AudioContext || window.webkitAudioContext)();
      const osc2 = ctx2.createOscillator();
      const gain2 = ctx2.createGain();
      osc2.type = "sine";
      osc2.frequency.value = 1046.5;
      gain2.gain.setValueAtTime(0.0001, ctx2.currentTime);
      gain2.gain.exponentialRampToValueAtTime(0.3, ctx2.currentTime + 0.02);
      gain2.gain.exponentialRampToValueAtTime(0.0001, ctx2.currentTime + 0.5);
      osc2.connect(gain2).connect(ctx2.destination);
      osc2.start();
      osc2.stop(ctx2.currentTime + 0.55);
    }, 550);
  } catch (e) {
    console.warn("No se pudo reproducir el aviso sonoro:", e);
  }
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

class WorkoutSession {
  constructor(root) {
    this.root = root;
    this.saveUrl = root.dataset.saveUrl;
    // Objetivo del ejercicio (si viene de un plan o de un circuito con
    // meta fija) — solo para avisar al llegar, NO para parar el conteo.
    // Sin esto (o si no viene ninguno) simplemente no hay aviso.
    this.targetSets = root.dataset.targetSets ? parseInt(root.dataset.targetSets, 10) : null;
    this.targetReps = root.dataset.targetReps ? parseInt(root.dataset.targetReps, 10) : null;
    this.targetAnnounced = false;
    // Objetivo de plancha/plancha lateral/etc. (segundos a aguantar) — ver
    // notePostureOk para la cuenta atrás/adelante hablada que usa esto.
    this.targetSeconds = root.dataset.targetSeconds ? parseInt(root.dataset.targetSeconds, 10) : null;
    this.postureCountdownLastSecond = null;   // último entero (cuenta atrás o adelante) ya dicho en el tramo de aguante actual
    this.postureGoalAnnouncedThisHold = false; // si ya se ha avisado "objetivo cumplido" en el tramo actual
    // Voz que cuenta las reps en alto ("¡uno! ¡dos! ¡tres!") — Web Speech
    // API, la trae el propio navegador. Activada por defecto; se puede
    // desactivar poniendo localStorage["libreta.voiceReps"] = "0" (misma
    // clave que usa la app móvil, por si algún día hay un ajuste aquí
    // también). Ver speakRep() más abajo.
    this.voiceEnabled = localStorage.getItem("libreta.voiceReps") !== "0";
    // Qué contador usar. Lo decide el ejercicio (counter_key en el
    // catálogo), no la pantalla.
    this.counterKey = root.dataset.counterKey || "pullup";
    this.video = el("workout-video");
    this.canvas = el("workout-canvas");
    this.ctx = this.canvas.getContext("2d");

    // this.statusEl Y this.debugEl van los dos al mismo sitio: ningún
    // aviso, ni texto, ni "movimiento" bajo la cámara — pedido
    // explícito, ni siquiera un aviso fijo tipo "Preparando cámara…",
    // porque estorba al probar la app "in real life". En vez de
    // elementos reales del DOM, son objetos con un setter de
    // "textContent" que redirige TODO (avisos de estado normales,
    // avisos de fin de serie, descanso obligatorio, calibración, y
    // el texto de depuración de cada ejercicio) al registro exportable
    // (this.scissorLog, ver logScissor / exportScissorLog) en vez de a
    // la pantalla. Los ~40 sitios que hacen "this.statusEl.textContent
    // = ..." (directamente o vía setStatus/announceStatus/
    // announceSetComplete/announceRestBlocked) y los ~60 que hacen
    // "this.debugEl.textContent = ..." siguen funcionando tal cual, sin
    // tocar ni un sitio más. La VOZ no se toca — sigue hablando igual
    // que antes (speak()/speakOut no dependen de statusEl ni debugEl) —
    // solo se quita el texto visual bajo la cámara.
    // Cuando la app esté validada del todo y ya no haga falta
    // depurarla, quitar este shim (y el botón/registro entero) deja el
    // código donde estaba antes, sin más cambios que deshacer.
    const self = this;
    this.statusEl = {
      set textContent(text) {
        self.logScissor(`[status] ${text}`);
      },
    };
    this.goalBannerEl = el("workout-goal-banner");
    this.repsEl = el("workout-reps");
    this.setsEl = el("workout-sets");
    this.timerEl = el("workout-timer");
    this.restEl = el("workout-rest");
    this.finishBtn = el("workout-finish");
    this.cancelBtn = el("workout-cancel");
    this.debugEl = {
      set textContent(text) {
        self.logScissor(text);
      },
    };
    this.debugExportBtn = el("workout-debug-export");
    this.debugExportStatusEl = el("workout-debug-export-status");

    this.poseLandmarker = null;
    this.stream = null;
    this.running = false;

    this.calibrating = false;
    this.prepping = false;
    this.prepStartTs = null;
    this.hangStableSince = null;
    this.armsDownSince = null; // desde cuándo llevas los brazos abajo seguido, de verdad soltado (ver RELEASE_MARGIN_FACTOR) — para no cerrar la serie por un frame ruidoso
    this.groundStableSince = null; // crunch/legraise/situp: desde cuándo llevas tumbado y quieto seguido (para armar el contador, como hangStableSince en dominadas)
    this.offGroundSince = null;    // crunch/legraise/situp: desde cuándo llevas "de pie" seguido (para cerrar la serie, como armsDownSince en fondos)
    this.outOfFrameSince = null;   // sentadillas y abdominales tumbado: desde cuándo no se te detecta en el encuadre (para cerrar la serie, ver noteAbsence)
    this.waveSamples = [];         // sentadillas y abdominales tumbado: historial reciente de la muñeca levantada, para detectar el vaivén de "quiero terminar" (ver checkWaveGesture)
    this.frontalStableSince = null; // sentadillas: desde cuándo llevas de frente a la cámara (en vez de perfil) seguido, otra forma de terminar la serie
    this.torsoBandStableSince = null; // doble crunch: desde cuándo llevas el torso dentro de la banda de inclinación de la postura seguido (para armar el contador)
    this.torsoOutOfBandSince = null;  // doble crunch: desde cuándo llevas el torso FUERA de esa banda seguido (para cerrar la serie)
    this.scissorSide = null;          // tijeretas: qué pierna está más alta, YA CONFIRMADO (para detectar el cambio)
    this.scissorCandidateSide = null; // tijeretas: qué pierna parece estar poniéndose arriba, aún sin confirmar (ver SCISSOR_SWITCH_STABLE_MS)
    this.scissorCandidateSince = null; // tijeretas: desde cuándo lleva esa pierna candidata arriba seguido
    this.scissorSmoothA = null;       // tijeretas: altura ya suavizada de la pierna rastreada "1" (ver SCISSOR_SMOOTHING_ALPHA)
    this.scissorSmoothB = null;       // tijeretas: lo mismo para la pierna rastreada "2"
    this.scissorRawPrevA = null;      // tijeretas: altura BRUTA de la pierna "1" en el frame anterior, para recortar saltos imposibles (ver SCISSOR_MAX_LIFT_JUMP)
    this.scissorRawPrevB = null;      // tijeretas: lo mismo para la pierna "2"
    this.scissorTrackA = null;        // tijeretas: última posición (x,y) conocida de la pierna rastreada "1", para reconocerla por cercanía frame a frame (no por la etiqueta izq/dcha de MediaPipe, que se confunde de perfil)
    this.scissorTrackB = null;        // tijeretas: lo mismo para la pierna rastreada "2"
    this.scissorSwitchCount = 0;      // tijeretas: cambios de pierna confirmados desde que se armó — una repetición es un vaivén COMPLETO, así que solo se cuenta cada dos cambios
    this.scissorLog = [];             // tijeretas: registro de depuración en memoria (ver logScissor/exportScissorLog)
    this.scissorLogMax = 900;         // tijeretas: tope de líneas del registro (FIFO) — de sobra para unos 30s a 30fps
    this.scissorLogStart = performance.now(); // tijeretas: instante de referencia para los timestamps del registro
    // Plancha / plancha lateral: aquí no se cuentan repeticiones, se
    // cuenta TIEMPO aguantando la postura — ver processPosture,
    // notePostureOk/notePostureBroken y closeActivePostureSet.
    this.postureValidSince = null;   // desde cuándo llevas la postura correcta seguida en el tramo actual
    this.postureInvalidSince = null; // desde cuándo llevas la postura rota seguida (para cerrar la serie, PLANK_INVALID_STABLE_MS)
    this.lastPostureTickTs = null;   // último frame contado hacia currentHoldSeconds, para medir el hueco entre frames
    this.currentHoldSeconds = 0;     // segundos aguantados en el tramo en curso (aún sin cerrar como serie)
    this.totalHeldSeconds = 0;       // suma de todos los tramos aguantados de la sesión — esto es lo que se manda como session_duration_seconds al guardar (ver finish())
    this.tipIndex = 0;               // qué consejo rotativo toca decir a continuación
    this.lastTipAt = null;           // performance.now() del último consejo hablado
    this.sidePlankDownSide = null;   // plancha lateral: "left"/"right" — qué lado se consideró "de abajo" el frame anterior, para no dejar que la decisión salte cada frame (ver checkSidePlankPosture)
    this.postureGroundConfirmed = false; // plancha/plancha lateral: ya se ha confirmado que te ha visto tumbado del todo en el suelo (paso 1) antes de pedir la postura en sí (paso 2) — ver processPosture
    this.postureGroundSince = null;      // plancha/plancha lateral: desde cuándo llevas tumbado del todo, seguido, para confirmar el paso 1
    this.postureLastOk = null;         // plancha/plancha lateral: último estado (correcto/incorrecto) ya CONFIRMADO y reflejado en pantalla — ver POSTURE_FLICKER_STABLE_MS
    this.postureCandidateOk = null;    // plancha/plancha lateral: estado que parece estarse dando, aún sin confirmar
    this.postureCandidateSince = null; // plancha/plancha lateral: desde cuándo lleva ese estado candidato seguido
    this.calibrationSamples = [];
    this.calibrationStartTs = null;
    this.shoulderWidth = null;

    this.state = "down"; // "down" | "up"
    this.reps = 0;
    this.repDurations = [];
    this.sets = [];              // series ya cerradas: [{reps, durations}, ...]
    this.currentSetReps = 0;     // reps de la serie en curso
    this.currentSetDurations = [];
    this.localBottomY = null;  // y (0-1) del punto mas bajo visto en la fase actual
    this.localTopY = null;     // y (0-1) del punto mas alto visto en la fase actual
    this.barY = null;          // y (0-1) de la barra, medida por la altura de tus muñecas
    this.repStartTime = null;
    this.liftoffTime = null;   // instante en que detectamos que empezaste a moverte de verdad
    this.dipGroundShoulderY = null; // y (0-1) de tu hombro de pie, junto a las paralelas — referencia para saber si estás montado (ver processDip)
    this.dipArmedSince = null;  // desde cuándo llevas seguido con el codo recto, armando el contador
    this.dipBreakSince = null;  // desde cuándo llevas seguido con la combinación de desmonte (hombro abajo + codo recto), ya armado
    this.dipBreakInterruptSince = null; // desde cuándo el frame actual YA NO cumple la forma de desmonte, mientras dipBreakSince sigue vivo — un solo frame de ruido (ver DIP_BREAK_INTERRUPT_GRACE_MS/processDip) no debe tirar la cuenta de desmonte a la basura
    this.dipSetPeakShoulderRise = null; // pico de "hombro subido" visto en la serie en curso — de aquí salen los umbrales de montada/o y desmonte, adaptados a tu cuerpo (ver processDip)
    this.dipRepShoulderTopY = null; // y (0-1) del hombro justo al empezar a bajar en la repetición en curso
    this.dipRepShoulderMaxY = null; // y (0-1) más baja (más abajo en la imagen) que ha alcanzado el hombro en la repetición en curso
    this.dipTopShoulderY = null; // y (0-1) MÁS ALTA (Y más pequeña) vista mientras estás de verdad arriba (state==="top", brazos estirados) DESDE que se armó esta serie — décimo bug real, ver processDip: dipRepShoulderTopY se copiaba de un solo frame suelto (el del cruce de ángulo) en vez de esto. Se reinicia al armar cada serie (no solo al Recalibrar) para no arrastrar una lectura vieja de una serie anterior — ver el comentario junto a la reasignación, en processDip
    // (dipTopShoulderY: se probó aquí, y en la asignación de
    // dipRepShoulderTopY más abajo en processDip, una referencia de
    // "arriba" acumulada durante todo el tramo en top en vez del frame
    // suelto del cruce de ángulo. REVERTIDO por completo: el usuario
    // confirmó una repetición contada por accidente solo al colocar el
    // portátil/ponerte en posición, antes de hacer fondos de verdad — y
    // que la versión de antes, la de aquí debajo, SÍ contaba los fondos
    // bien, con la cámara de perfil confirmada.)
    this.dipShoulderSmoothY = null; // y (0-1) del hombro YA suavizada (recorte de saltos + media móvil) — se usa para todo excepto elbowAngle (ver DIP_SHOULDER_SMOOTHING_ALPHA/DIP_SHOULDER_MAX_Y_JUMP, processDip)
    this.dipShoulderRawPrevY = null; // y (0-1) bruta del hombro en el frame anterior, para recortar saltos imposibles antes de suavizar (mismo patrón que scissorRawPrevA)
    this.dipTorsoLength = null; // largo hombro-cadera aprendido UNA VEZ de pie y congelado para toda la serie — reemplaza al largo de brazo (hombro-codo) como referencia para normalizar hombro_subido, ver el sexto bug arriba y processDip
    this.dipTorsoLengthRawPrev = null; // largo hombro-cadera bruto del frame anterior, para recortar saltos imposibles antes de suavizar (mismo patrón que dipShoulderRawPrevY)
    this.dipFaceCameraSince = null; // desde cuándo llevas seguido con los DOS hombros visibles (te has girado de frente a la cámara) — otra forma de dar la serie por terminada, ver DIP_FACE_CAMERA_VISIBILITY/STABLE_MS
    this.dipGroundHipY = null; // y (0-1) de tu cadera de pie — mismo concepto que dipGroundShoulderY, para el caso de paralelas ALTAS (ver dipBarType, processDip)
    this.dipHipSmoothY = null; // y (0-1) de la cadera YA suavizada — mismo filtro que dipShoulderSmoothY
    this.dipHipRawPrevY = null; // y (0-1) bruta de la cadera del frame anterior, para el mismo recorte de salto que dipShoulderRawPrevY
    this.dipSetPeakHipRise = null; // pico de "cadera subida" visto en la serie en curso — mismo concepto que dipSetPeakShoulderRise, para paralelas ALTAS
    this.dipBarType = null; // "alta" | "baja" | null (aún sin determinar esta serie) — de qué altura son las paralelas, decidido una vez por serie nada más armar (ver processDip)
    this.squatSide = null;     // "left" | "right" — qué lado del cuerpo se ve mejor este frame (de perfil solo se ve bien uno)
    this.squatKneeAngle = null; // último ángulo de rodilla medido, solo para overlay/debug
    this.curlSide = null;            // curl: "left" | "right" — qué lado del cuerpo se ve mejor este frame (de perfil solo se ve bien uno), mismo concepto que squatSide/pushupSide
    this.curlElbowAngle = null;      // curl: último ángulo de codo medido, solo para overlay/debug
    this.curlTopHoldSince = null;    // curl: performance.now() de cuándo se llegó arriba (codo doblado) en la repetición en curso — para el aviso de "llevas aguantando, esto no cuenta todavía" (ver CURL_TOP_HOLD_WARN_MS/processDumbbellCurl)
    this.curlShoulderMidPrev = null; // curl: {x,y} del punto medio de hombros del frame anterior, para medir cuánto tiembla la cámara (ver checkCameraShake)
    this.curlCameraShakeSince = null; // curl: desde cuándo lleva la cámara temblando por encima del umbral, seguido (ver checkCameraShake)
    this.curlElbowBaselineY = null;  // curl: altura (y) del codo en el momento de armar — referencia para medir si el codo SUBE durante la serie (ver processDumbbellCurl, CURL_ELBOW_RISE_MAX_FACTOR)
    this.curlRestSince = null;       // curl: desde cuándo lleva el brazo estirado y quieto, seguido, en el estado "bottom" — para el cierre automático de serie por descanso (ver CURL_REST_AUTO_CLOSE_MS)
    this.legRaiseSide = null;  // mismo concepto que squatSide, para elevación de piernas
    this.pushupSide = null;    // mismo concepto que squatSide, para flexiones
    this.archerPeakLeftAngle = null;  // dominadas de arquero: ángulo de codo izquierdo en el punto más alto visto de la subida en curso
    this.archerPeakRightAngle = null; // idem, codo derecho
    this.archerLastSide = null;       // dominadas de arquero: "left" | "right" — lado detectado en la última repetición contada (para avisar si repites)
    this.archerLiveLeftAngle = null;  // dominadas de arquero: ángulo de codo izquierdo de ESTE frame, solo para overlay/debug
    this.archerLiveRightAngle = null; // idem, codo derecho

    this.sessionStart = null;
    this.lastRepTime = null;
    this.setClosedAt = null; // performance.now() de cuándo se cerró la última serie (con reps o con tiempo aguantado) — para el descanso obligatorio (ver MIN_REST_MS, countRep, notePostureOk, announceRestBlocked)
    this.restAlerted = false;
    // Silencia CUALQUIER voz (avisos, consejos, "te veo"/"no te veo",
    // "¡listo!"...) desde que termina una serie hasta que el reloj de
    // descanso llega a REST_ALERT_SECONDS (1:30). Se pone a true justo
    // al cerrar una serie (con reps o con tiempo aguantado), y se quita
    // en dos sitios: cuando de verdad arranca la siguiente serie
    // (countRep, o al entrar en postura válida en notePostureOk) o
    // cuando el aviso automático de "descanso acabado" salta a los 90s
    // (tickRestTimer). Mientras esté a true, el texto en pantalla se
    // sigue actualizando como siempre — solo la voz se calla.
    this.restVoiceQuiet = false;
    this.restAlertsTriggered = 0;
    this.lastSpokenStatusAt = null; // performance.now() del último aviso de estado hablado, sea cual sea el tipo (ver announceStatus)
    // Antes había un único "lastSpokenStatusKey" compartido por TODOS los
    // tipos de aviso: en cuanto sonaba un aviso de un tipo distinto (p.ej.
    // "Serie de 41s terminada…" al cerrar la plancha), se perdía el
    // recuerdo de cuándo había sonado por última vez "cadera desalineada",
    // así que el siguiente aviso de postura rota volvía a hablar casi al
    // momento (solo 2s después) en vez de esperar los 25s previstos — el
    // "no se calla" que se reportó. Ahora cada tipo de aviso (cada key)
    // lleva su propio cronómetro de 25s, independiente de los demás.
    this.lastSpokenAtByKey = new Map(); // key del aviso -> performance.now() de la última vez que SE DIJO (no solo se intentó) ese tipo
    // Aviso de "ya te veo bien, puedes empezar" — solo una vez en toda la
    // sesión (primera serie), no hace falta repetirlo entre series: para
    // la segunda serie ya sabes cómo colocarte.
    this.startupVoiceGiven = false;
    // Cuántas veces se ha anunciado por voz un "serie terminada" en esta
    // sesión — ver announceSetComplete(). La PRIMERA vez se dice la chapa
    // completa (cómo colocarte para la siguiente serie); a partir de la
    // segunda ya la sabes, así que solo se dice "Serie de N terminada." a
    // secas, sin repetir la misma explicación en cada serie.
    this.setsCompletedVoiceCount = 0;

    this.finishBtn.addEventListener("click", () => this.finish());
    this.cancelBtn.addEventListener("click", () => {
      this.stopCamera();
      window.location.href = root.dataset.cancelUrl;
    });
    this.recalBtn = el("workout-recalibrate");
    if (this.recalBtn) {
      this.recalBtn.addEventListener("click", () => this.beginPrep());
    }
    if (this.debugExportBtn) {
      this.debugExportBtn.addEventListener("click", () => this.exportScissorLog());
    }
  }

  /**
   * Copia (o, si el portapapeles no está disponible, descarga como
   * .txt) el registro de depuración acumulado en this.scissorLog — para
   * poder mandarlo tal cual sin tener que leer nada en la pantalla
   * mientras estás haciendo el ejercicio, tumbado y lejos de la cámara.
   * A pesar del nombre (nació con las tijeretas), este registro cubre
   * TODOS los ejercicios de cámara por igual: this.debugEl ya no es un
   * elemento real del DOM, es un shim cuyo setter de "textContent"
   * mete la línea aquí (ver el constructor) — así que cualquier sitio
   * del fichero que hiciera "if (this.debugEl) this.debugEl.textContent
   * = ..." (uno por ejercicio) ya queda registrado sin haber tenido que
   * tocar ese código. El botón que lo exporta (#workout-debug-export)
   * sale siempre, para cualquier ejercicio.
   */
  async exportScissorLog() {
    if (!this.debugExportStatusEl) return;
    if (!this.scissorLog.length) {
      this.debugExportStatusEl.textContent = "Todavía no hay datos registrados — haz unos segundos del ejercicio primero.";
      return;
    }
    // Primera línea del registro exportado: versión del fichero que está
    // EJECUTANDO ESTA PESTAÑA ahora mismo (ver WORKOUT_JS_BUILD, arriba del
    // todo). Si no coincide con la última entregada, el registro entero es
    // de una copia vieja del código — no hace falta adivinarlo.
    const text = `=== workout.js build: ${WORKOUT_JS_BUILD} ===\n` + this.scissorLog.join("\n");
    try {
      await navigator.clipboard.writeText(text);
      this.debugExportStatusEl.textContent = `Copiado al portapapeles (${this.scissorLog.length} líneas, build ${WORKOUT_JS_BUILD}) — ya puedes pegarlo donde lo quieras mandar.`;
    } catch (e) {
      console.warn("No se pudo copiar el registro al portapapeles, se descarga como archivo:", e);
      try {
        const blob = new Blob([text], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${this.counterKey}-debug.txt`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        this.debugExportStatusEl.textContent = `Descargado como archivo (${this.scissorLog.length} líneas, build ${WORKOUT_JS_BUILD}).`;
      } catch (e2) {
        console.error("Tampoco se pudo descargar el registro:", e2);
        this.debugExportStatusEl.textContent = "No se ha podido copiar ni descargar — mira la consola del navegador (F12).";
      }
    }
  }

  setStatus(text) {
    this.statusEl.textContent = text;
  }

  /**
   * Habla un texto suelto (no un número de repetición — para eso está
   * speakRep). flush:true corta lo que se esté diciendo para decir esto
   * ya (para avisos urgentes); flush:false lo encola detrás sin cortar
   * nada, para no tragarse a media palabra el "¡tres!" de una repetición
   * que acabas de contar.
   */
  speak(text, { flush = true } = {}) {
    if (!this.voiceEnabled) return;
    // Todavía en el tramo silencioso del descanso (ver restVoiceQuiet):
    // ni avisos, ni consejos, ni "te veo"/"no te veo" — nada de voz. El
    // descanso es de verdad de los 90s (REST_ALERT_SECONDS), cámara
    // colocada una vez al principio de la sesión incluido — así que
    // esto no necesita excepciones.
    if (this.restVoiceQuiet) return;
    // El motor de verdad (Web Speech API) vive en speakOut(), suelto más
    // arriba en este mismo fichero — así circuit.js/plan-session.js
    // también pueden hablar (la cuenta atrás de plancha/plancha
    // lateral/etc. dentro de un circuito o una sesión de plan) sin
    // duplicar aquí esa misma llamada.
    speakOut(text, { flush });
  }

  /**
   * Como setStatus(), pero además lo dice en voz alta — para los avisos
   * importantes (que no te ve bien, fin de serie…) que antes solo salían
   * como texto bajo la cámara, donde no los ves si estás en mitad del
   * ejercicio y no mirando la pantalla.
   *
   * El texto en pantalla se actualiza siempre, pero la voz es más
   * selectiva: si el aviso es del MISMO tipo que el anterior, no se
   * repite antes de STATUS_VOICE_REPEAT_GAP_MS — si no, sería un
   * "no te veo bien… no te veo bien… no te veo bien…" sin parar. Si es
   * de un tipo DISTINTO, se dice casi al momento (STATUS_VOICE_MIN_GAP_MS,
   * solo de sobra para no pillar un parpadeo de un par de frames entre
   * dos estados).
   *
   * `key` identifica el TIPO de aviso para esta comparación — por
   * defecto es el propio texto, pero hace falta pasarlo aparte cuando el
   * texto cambia cada vez aunque sea "la misma" repetición (p.ej. una
   * cuenta atrás con los segundos dentro del texto: sin esto, cada
   * segundo se trataría como un aviso "nuevo" y se leería sin parar).
   *
   * El cronómetro de los 25s es POR KEY (ver lastSpokenAtByKey): que
   * suene un aviso de un tipo distinto no reinicia la espera de este
   * tipo. Aparte, hay un margen corto (STATUS_VOICE_MIN_GAP_MS) frente a
   * CUALQUIER aviso hablado, sea del tipo que sea, solo para no
   * solapar dos avisos casi en el mismo instante.
   */
  announceStatus(text, key = text) {
    this.setStatus(text);
    if (!this.voiceEnabled) return;
    const now = performance.now();
    const lastForKey = this.lastSpokenAtByKey.get(key) ?? null;
    const keyGap = lastForKey === null ? Infinity : now - lastForKey;
    if (keyGap < STATUS_VOICE_REPEAT_GAP_MS) return;
    const anyGap = this.lastSpokenStatusAt === null ? Infinity : now - this.lastSpokenStatusAt;
    if (anyGap < STATUS_VOICE_MIN_GAP_MS) return;
    this.lastSpokenStatusAt = now;
    this.lastSpokenAtByKey.set(key, now);
    this.speak(text, { flush: false });
  }

  /**
   * Anuncia el cierre de una serie ("Serie de N terminada. <cómo
   * colocarte para la siguiente>"). En pantalla se ve siempre el aviso
   * completo, pero por VOZ la explicación de "cómo volver a colocarte"
   * solo se dice la primera vez de toda la sesión — a partir de la
   * segunda serie ya sabes cómo empezar, y repetirla en cada serie es
   * justo el "dar la tabarra" que hace tediosa la app. Así que a partir
   * de ahí solo se dice "Serie de N terminada.", corto y al grano.
   */
  announceSetComplete(prefix, waitingMessage) {
    // Descanso obligatorio: la explicación completa ("mínimo N segundos")
    // se decía SIEMPRE, en cada serie — pero es la misma tabarra que el
    // resto de este aviso (cómo colocarte), así que ahora sigue la misma
    // regla: la chapa completa solo la PRIMERA vez de la sesión; a partir
    // de la segunda serie ya sabes que hay descanso obligatorio y cuánto
    // dura, así que por voz basta con "Descanso.", a secas. La regla de
    // "no cuento nada hasta que no pasen los 90s" en sí no cambia (ver
    // MIN_REST_MS, countRep, notePostureOk) — si intentas algo antes de
    // tiempo, announceRestBlocked() sí te lo explica con detalle cada vez,
    // porque ahí hace falta.
    const restNoteFull = `Descanso obligatorio: mínimo ${Math.round(MIN_REST_MS / 1000)} segundos.`;
    const restNoteShort = "Descanso.";
    const fullText = `${prefix} terminada. ${restNoteFull} ${waitingMessage}`;
    this.setStatus(fullText);
    if (!this.voiceEnabled) return;
    const isFirst = this.setsCompletedVoiceCount === 0;
    this.setsCompletedVoiceCount += 1;
    const now = performance.now();
    const anyGap = this.lastSpokenStatusAt === null ? Infinity : now - this.lastSpokenStatusAt;
    if (anyGap < STATUS_VOICE_MIN_GAP_MS) return;
    this.lastSpokenStatusAt = now;
    this.speak(isFirst ? fullText : `${prefix} terminada. ${restNoteShort}`, { flush: false });
  }

  /**
   * Has intentado contar algo (una repetición, o arrancar un tramo de
   * postura) mientras todavía dura el descanso obligatorio (MIN_REST_MS
   * desde que se cerró la serie anterior) — no se cuenta, pero SÍ hay
   * que decírtelo: a diferencia de announceStatus()/speak(), pasa por
   * alto restVoiceQuiet a propósito (igual que speakRep(), ver su
   * comentario) porque si esto se llama es justo porque has intentado
   * hacer algo en pleno descanso — quedarte callado ahí sería confuso,
   * parecería que la app no funciona o que no te ha visto.
   */
  announceRestBlocked(now) {
    const remaining = Math.max(0, Math.ceil((MIN_REST_MS - (now - this.setClosedAt)) / 1000));
    const text = `Todavía en descanso obligatorio — quedan ${remaining}s. No se cuenta nada hasta entonces.`;
    this.setStatus(text);
    if (!this.voiceEnabled) return;
    const key = "rest_blocked";
    const lastForKey = this.lastSpokenAtByKey.get(key) ?? null;
    const keyGap = lastForKey === null ? Infinity : now - lastForKey;
    if (keyGap < STATUS_VOICE_REPEAT_GAP_MS) return;
    const anyGap = this.lastSpokenStatusAt === null ? Infinity : now - this.lastSpokenStatusAt;
    if (anyGap < STATUS_VOICE_MIN_GAP_MS) return;
    this.lastSpokenStatusAt = now;
    this.lastSpokenAtByKey.set(key, now);
    speakOut(text, { flush: false });
  }

  async start() {
    // "Pidiendo acceso a la cámara…" / "Cargando el modelo…" son ruido
    // técnico y mecánico, no guía útil — y ahora, con this.statusEl
    // convertido en shim (ver constructor), da igual usar setStatus()
    // o logScissor() directamente: los dos acaban en el mismo sitio,
    // el registro de depuración, sin pintar nada en pantalla.
    this.logScissor("Pidiendo acceso a la cámara…");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        // 1280x720, no 640x480: con poca resolución, a cierta distancia
        // de la cámara el cuerpo ocupa muy pocos píxeles y el seguimiento
        // de MediaPipe se vuelve inestable (afecta sobre todo a
        // dominadas, calibradas por posición y no por ángulo). Son
        // valores "ideales" (sin exact/min), así que si la cámara no da
        // para tanto, el navegador se queda con la resolución más
        // cercana que sí soporte — no falla, degrada.
        video: { facingMode: "user", width: 1280, height: 720 },
        audio: false,
      });
    } catch (err) {
      this.announceStatus(
        "No se pudo acceder a la cámara. Revisa los permisos del navegador y recarga la página."
      );
      console.error(err);
      return;
    }

    this.video.srcObject = this.stream;
    await this.video.play();
    this.canvas.width = this.video.videoWidth || 640;
    this.canvas.height = this.video.videoHeight || 480;

    this.logScissor("Cargando el modelo de seguimiento…");
    try {
      const { FilesetResolver, PoseLandmarker } = await import(MEDIAPIPE_BUNDLE_URL);
      const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_BASE_URL);
      this.poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
        runningMode: "VIDEO",
        numPoses: 1,
      });
    } catch (err) {
      this.announceStatus("No se pudo cargar el modelo de seguimiento. Comprueba tu conexión y recarga.");
      console.error(err);
      return;
    }

    this.running = true;
    this.sessionStart = performance.now();
    this.beginPrep();

    this.restIntervalId = setInterval(() => this.tickRestTimer(), 500);
    this.loop();
  }

  beginPrep() {
    // Cuenta atrás para darte tiempo a llegar a la barra y colgarte
    // ANTES de que se tome ninguna medida (esto es lo que fallaba:
    // calibrar de golpe al abrir la cámara, con nadie aún en la barra).

    // Cada (re)calibración marca el final de la serie en curso (si
    // tenía alguna repetición) y el principio de la siguiente.
    if (this.currentSetReps > 0) {
      this.sets.push({ reps: this.currentSetReps, durations: [...this.currentSetDurations] });
      this.currentSetReps = 0;
      this.currentSetDurations = [];
      this.updateSetDisplay();
      this.setClosedAt = performance.now();
    }
    // Plancha / plancha lateral: el equivalente de lo de arriba pero para
    // un tramo de tiempo aguantado en vez de repeticiones (ver
    // _flushPostureHold) — así pulsar Recalibrar a media plancha también
    // guarda lo aguantado hasta ese momento como una serie, en vez de
    // perderlo.
    if (CAMERA_POSTURE_COUNTERS.has(this.counterKey)) {
      this._flushPostureHold();
    }
    // El contador grande siempre arranca en 0 al empezar una serie nueva.
    if (this.repsEl) this.repsEl.textContent = "0";

    this.prepping = true;
    this.calibrating = false;
    this.prepStartTs = performance.now();
    this.hangStableSince = null;
    this.armsDownSince = null;
    this.groundStableSince = null;
    this.offGroundSince = null;
    this.outOfFrameSince = null;
    this.waveSamples = [];
    this.frontalStableSince = null;
    this.torsoBandStableSince = null;
    this.torsoOutOfBandSince = null;
    this.postureValidSince = null;
    this.postureInvalidSince = null;
    this.lastPostureTickTs = null;
    this.tipIndex = 0;
    this.lastTipAt = null;
    this.calibrationSamples = [];
    this.localBottomY = null;
    this.localTopY = null;
    this.barY = null;
    this.archerPeakLeftAngle = null;
    this.archerPeakRightAngle = null;
    this.archerLastSide = null;
    this.archerLiveLeftAngle = null;
    this.archerLiveRightAngle = null;

    // Los fondos no se calibran ni se cuelgan de ninguna barra: el
    // estado arranca vacío y se fija solo cuando te pones arriba.
    // setStatus, no announceStatus: el aviso hablado de "ya puedes
    // empezar" lo da processDip/processSquat la primera vez que te ve
    // bien en toda la sesión — no hace falta repetirlo en cada serie.
    //
    // dipGroundShoulderY SÍ se reinicia aquí (a diferencia de entre
    // series, ver closeActiveSet): esto es "principio de sesión, o has
    // pulsado Recalibrar" — la cámara puede haberse movido, así que toca
    // volver a aprender tu altura de pie desde cero. Entre series NO se
    // toca, para que no haga falta bajarse y volver a subir para que la
    // referencia sea válida otra vez.
    if (this.counterKey === "dip") {
      this.prepping = false;
      this.state = null;
      this.dipGroundShoulderY = null;
      this.dipArmedSince = null;
      this.dipBreakSince = null;
      this.dipBreakInterruptSince = null;
      this.dipSetPeakShoulderRise = null;
      this.dipShoulderSmoothY = null;
      this.dipShoulderRawPrevY = null;
      this.dipTorsoLength = null;
      this.dipTorsoLengthRawPrev = null;
      this.dipFaceCameraSince = null;
      this.dipGroundHipY = null;
      this.dipHipSmoothY = null;
      this.dipHipRawPrevY = null;
      this.dipSetPeakHipRise = null;
      this.dipBarType = null;
      this.dipTopShoulderY = null;
      this.setStatus("Ponte de pie junto a las paralelas, de perfil a la cámara, un momento — así aprendo tu altura de referencia.");
    } else if (this.counterKey === "pushup") {
      // Tampoco hay nada que calibrar: el ángulo del codo no depende de
      // la distancia a la cámara. Solo hace falta confirmarte tumbado
      // boca abajo, en la posición de arriba (brazos estirados, manos a
      // la altura del pecho, codos pegados al cuerpo), antes de empezar
      // a contar (ver processPushup).
      this.prepping = false;
      this.state = null;
      this.pushupSide = null;
      this.groundStableSince = null;
      this.setStatus(
        "Túmbate boca abajo, de perfil a la cámara, con los brazos estirados, las manos a la altura del " +
        "pecho y los codos pegados al cuerpo (mirando hacia atrás), para empezar."
      );
    } else if (this.counterKey === "squat") {
      // Tampoco hay barra que calibrar aquí: el ángulo de rodilla no
      // depende de la distancia a la cámara. Solo hace falta esperar a
      // verte de pie para no contar media repetición al entrar.
      this.prepping = false;
      this.state = null;
      this.squatSide = null;
      this.squatKneeAngle = null;
      this.setStatus("Ponte de perfil a la cámara, de pie, para empezar.");
    } else if (this.counterKey === "crunch") {
      // Tampoco hay nada que calibrar: se mide el hombro frente a la
      // cadera, en proporción al muslo — ningún valor depende de la
      // distancia a la cámara.
      this.prepping = false;
      this.state = null;
      this.setStatus("Túmbate boca arriba, con la cámara a un lado (de perfil), y encuadra el hombro, la cadera y la rodilla.");
    } else if (this.counterKey === "legraise") {
      this.prepping = false;
      this.state = null;
      this.legRaiseSide = null;
      this.setStatus("Túmbate boca arriba, con la cámara a un lado (de perfil), y encuadra el cuerpo entero, de los hombros a los tobillos.");
    } else if (this.counterKey === "situp") {
      this.prepping = false;
      this.state = null;
      this.setStatus("Túmbate boca arriba con las rodillas dobladas, con la cámara a un lado (de perfil).");
    } else if (this.counterKey === "scissor") {
      this.prepping = false;
      this.state = null;
      this.scissorSide = null;
      this.scissorCandidateSide = null;
      this.scissorCandidateSince = null;
      this.scissorSmoothA = null;
      this.scissorSmoothB = null;
      this.scissorRawPrevA = null;
      this.scissorRawPrevB = null;
      this.scissorTrackA = null;
      this.scissorTrackB = null;
      this.scissorSwitchCount = 0;
      this.setStatus("Túmbate boca arriba, con la cámara a un lado (de perfil), y levanta los pies a un palmo del suelo.");
    } else if (this.counterKey === "doublecrunch") {
      this.prepping = false;
      this.state = null;
      this.setStatus("Túmbate boca arriba, con la cámara a un lado (de perfil), y levanta el torso hasta una posición intermedia.");
    } else if (this.counterKey === "dumbbellcurl") {
      // Tampoco hay nada que calibrar: el ángulo de codo no depende de
      // la distancia a la cámara. Solo hace falta confirmarte DE PERFIL
      // (no de frente — ver el bloque CURL_* más arriba para el
      // porqué), de pie, con el brazo colgando estirado, antes de
      // empezar a contar (ver processDumbbellCurl).
      this.prepping = false;
      this.state = null;
      this.curlSide = null;
      this.curlTopHoldSince = null;
      this.curlShoulderMidPrev = null;
      this.curlCameraShakeSince = null;
      this.curlElbowBaselineY = null;
      this.curlRestSince = null;
      this.setStatus(
        "Ponte de perfil a la cámara, de pie, con la mancuerna colgando, el brazo estirado y el codo pegado " +
        "al cuerpo, para empezar."
      );
    } else if (CAMERA_POSTURE_COUNTERS.has(this.counterKey)) {
      // Plancha / plancha lateral: no hay ni calibración ni ciclo de
      // reps que armar — solo empezar a contar en cuanto la postura sea
      // correcta (ver processPosture/notePostureOk). Antes de pedir la
      // postura en sí (plancha o plancha lateral) se pide un primer paso
      // más fácil (tumbarse del todo, en cualquier orientación) — ver
      // postureGroundConfirmed en processPosture.
      this.prepping = false;
      this.state = null;
      this.currentHoldSeconds = 0;
      this.postureGroundConfirmed = false;
      this.postureGroundSince = null;
      this.postureLastOk = null;
      this.postureCandidateOk = null;
      this.postureCandidateSince = null;
      this.postureCountdownLastSecond = null;
      this.postureGoalAnnouncedThisHold = false;
      if (this.repsEl) this.repsEl.textContent = formatHoldSeconds(0);
      this.setStatus(this.postureWaitingMessage());
    } else {
      this.state = "down";
    }
  }

  updateSetDisplay() {
    if (this.setsEl) this.setsEl.textContent = String(this.sets.length + 1);
  }

  loop() {
    if (!this.running) return;
    const now = performance.now();
    const result = this.poseLandmarker.detectForVideo(this.video, now);
    this.drawOverlay(result);
    this.processResult(result, now);
    requestAnimationFrame(() => this.loop());
  }

  drawOverlay(result) {
    const ctx = this.ctx;
    ctx.save();
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    // Espejo, para que se vea natural (como un espejo real)
    ctx.translate(this.canvas.width, 0);
    ctx.scale(-1, 1);

    if (result.landmarks && result.landmarks.length) {
      const lm = result.landmarks[0];
      const nose = lm[NOSE];
      ctx.fillStyle = "#D8654A";
      ctx.beginPath();
      ctx.arc(nose.x * this.canvas.width, nose.y * this.canvas.height, 8, 0, Math.PI * 2);
      ctx.fill();

      if (this.shoulderWidth && this.barY !== null) {
        const moveThresh = MOVE_FACTOR * this.shoulderWidth;
        const barThresh = (this.barY + BAR_MARGIN_FACTOR * this.shoulderWidth) * this.canvas.height;

        // Línea de la barra (medida por tus muñecas al calibrar)
        ctx.strokeStyle = "rgba(201,162,39,0.95)";
        ctx.setLineDash([]);
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(0, this.barY * this.canvas.height);
        ctx.lineTo(this.canvas.width, this.barY * this.canvas.height);
        ctx.stroke();

        ctx.strokeStyle = "rgba(201,162,39,0.5)";
        ctx.setLineDash([4, 4]);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(0, barThresh);
        ctx.lineTo(this.canvas.width, barThresh);
        ctx.stroke();

        const ref = this.state === "down" ? this.localBottomY : this.localTopY;
        if (ref !== null) {
          const refY = ref * this.canvas.height;
          const triggerY =
            this.state === "down"
              ? (ref - moveThresh) * this.canvas.height
              : (ref + moveThresh) * this.canvas.height;
          ctx.strokeStyle = "rgba(122,139,111,0.7)";
          ctx.setLineDash([3, 5]);
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.moveTo(0, refY);
          ctx.lineTo(this.canvas.width, refY);
          ctx.stroke();

          ctx.strokeStyle = "rgba(216,101,74,0.9)";
          ctx.setLineDash([6, 6]);
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(0, triggerY);
          ctx.lineTo(this.canvas.width, triggerY);
          ctx.stroke();
        }
      }

      if (this.counterKey === "squat" && this.squatSide) {
        const hip = this.squatSide === "left" ? lm[L_HIP] : lm[R_HIP];
        const knee = this.squatSide === "left" ? lm[L_KNEE] : lm[R_KNEE];
        const ankle = this.squatSide === "left" ? lm[L_ANKLE] : lm[R_ANKLE];
        // Verde cuando estás de pie, naranja en el tramo de bajada/sentadilla
        // — así se ve de un vistazo si el ángulo se está midiendo bien.
        ctx.strokeStyle = this.state === "bottom" ? "rgba(216,101,74,0.9)" : "rgba(122,139,111,0.9)";
        ctx.lineWidth = 3;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(hip.x * this.canvas.width, hip.y * this.canvas.height);
        ctx.lineTo(knee.x * this.canvas.width, knee.y * this.canvas.height);
        ctx.lineTo(ankle.x * this.canvas.width, ankle.y * this.canvas.height);
        ctx.stroke();
        [hip, knee, ankle].forEach((p) => {
          ctx.beginPath();
          ctx.arc(p.x * this.canvas.width, p.y * this.canvas.height, 6, 0, Math.PI * 2);
          ctx.fillStyle = "#D8654A";
          ctx.fill();
        });
      }

      if (this.counterKey === "archerpullup" && (this.archerLiveLeftAngle !== null || this.archerLiveRightAngle !== null)) {
        // Un brazo y otro a la vez (a diferencia de pushup/squat, que solo
        // trackean el lado que se ve mejor de perfil): aquí la cámara es
        // frontal, como en dominadas normales, así que se ven los dos.
        // Verde el que está claramente estirado, naranja el que está
        // claramente doblado (~90°), gris si no se distingue con
        // claridad ninguna de las dos cosas todavía.
        const drawArm = (shoulder, elbow, wrist, angleDeg) => {
          const color =
            angleDeg === null
              ? "rgba(150,150,150,0.6)"
              : angleDeg <= ARCHER_BENT_MAX_DEG
              ? "rgba(216,101,74,0.9)"
              : angleDeg >= ARCHER_STRAIGHT_MIN_DEG
              ? "rgba(122,139,111,0.9)"
              : "rgba(150,150,150,0.6)";
          ctx.strokeStyle = color;
          ctx.lineWidth = 3;
          ctx.setLineDash([]);
          ctx.beginPath();
          ctx.moveTo(shoulder.x * this.canvas.width, shoulder.y * this.canvas.height);
          ctx.lineTo(elbow.x * this.canvas.width, elbow.y * this.canvas.height);
          ctx.lineTo(wrist.x * this.canvas.width, wrist.y * this.canvas.height);
          ctx.stroke();
          [shoulder, elbow, wrist].forEach((p) => {
            ctx.beginPath();
            ctx.arc(p.x * this.canvas.width, p.y * this.canvas.height, 6, 0, Math.PI * 2);
            ctx.fillStyle = "#D8654A";
            ctx.fill();
          });
        };
        drawArm(lm[L_SHOULDER], lm[L_ELBOW], lm[L_WRIST], this.archerLiveLeftAngle);
        drawArm(lm[R_SHOULDER], lm[R_ELBOW], lm[R_WRIST], this.archerLiveRightAngle);
      }

      if ((this.counterKey === "pushup" || this.counterKey === "inclinepushup") && this.pushupSide) {
        const shoulder = this.pushupSide === "left" ? lm[L_SHOULDER] : lm[R_SHOULDER];
        const elbow = this.pushupSide === "left" ? lm[L_ELBOW] : lm[R_ELBOW];
        const wrist = this.pushupSide === "left" ? lm[L_WRIST] : lm[R_WRIST];
        // Verde con el brazo estirado (arriba), naranja doblándose
        // (abajo) — así se ve de un vistazo si el ángulo se está
        // midiendo bien.
        ctx.strokeStyle = this.state === "bottom" ? "rgba(216,101,74,0.9)" : "rgba(122,139,111,0.9)";
        ctx.lineWidth = 3;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(shoulder.x * this.canvas.width, shoulder.y * this.canvas.height);
        ctx.lineTo(elbow.x * this.canvas.width, elbow.y * this.canvas.height);
        ctx.lineTo(wrist.x * this.canvas.width, wrist.y * this.canvas.height);
        ctx.stroke();
        [shoulder, elbow, wrist].forEach((p) => {
          ctx.beginPath();
          ctx.arc(p.x * this.canvas.width, p.y * this.canvas.height, 6, 0, Math.PI * 2);
          ctx.fillStyle = "#D8654A";
          ctx.fill();
        });
      }
      if (this.counterKey === "dumbbellcurl" && this.curlSide) {
        const shoulder = this.curlSide === "left" ? lm[L_SHOULDER] : lm[R_SHOULDER];
        const elbow = this.curlSide === "left" ? lm[L_ELBOW] : lm[R_ELBOW];
        const wrist = this.curlSide === "left" ? lm[L_WRIST] : lm[R_WRIST];
        // Verde con el brazo estirado (posición de partida), naranja
        // doblado (arriba del curl) — igual que en flexiones/fondos.
        ctx.strokeStyle = this.state === "top" ? "rgba(216,101,74,0.9)" : "rgba(122,139,111,0.9)";
        ctx.lineWidth = 3;
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(shoulder.x * this.canvas.width, shoulder.y * this.canvas.height);
        ctx.lineTo(elbow.x * this.canvas.width, elbow.y * this.canvas.height);
        ctx.lineTo(wrist.x * this.canvas.width, wrist.y * this.canvas.height);
        ctx.stroke();
        [shoulder, elbow, wrist].forEach((p) => {
          ctx.beginPath();
          ctx.arc(p.x * this.canvas.width, p.y * this.canvas.height, 6, 0, Math.PI * 2);
          ctx.fillStyle = "#D8654A";
          ctx.fill();
        });
      }
    }
    ctx.restore();
  }

  /**
   * Registra una repetición. Común a todos los ejercicios: lo único que
   * cambia entre dominadas y fondos es CÓMO se detecta, no qué se
   * apunta después.
   */
  /**
   * Dice la repetición en voz alta — para poder contar sin mirar la
   * pantalla, que es justo cuando hace falta (a media dominada).
   *
   * cancel() antes de hablar, no encolar: si las reps vienen más rápido
   * de lo que da tiempo a decir el número, mejor saltarse los
   * intermedios y decir siempre el último de verdad — como haría un
   * entrenador contando en directo, no una cola de mensajes atascada.
   */
  speakRep(n) {
    if (!this.voiceEnabled) return;
    // Ojo: a propósito NO comprueba restVoiceQuiet (a diferencia de
    // speak()) — si esto se llama es porque se acaba de contar una
    // repetición de verdad, así que el descanso ya ha terminado por
    // definición (ver countRep, que además pone restVoiceQuiet a false
    // justo antes de llamar aquí).
    speakOut(numeroEnPalabras(n), { rate: 1.1 }); // un poco más rápido que el habla normal, para no quedarse atrás
  }

  countRep(duration, now, label) {
    if (duration < MIN_REP_SECONDS) return false;   // ruido, no cuenta
    if (this.currentSetReps === 0 && this.setClosedAt !== null && now - this.setClosedAt < MIN_REST_MS) {
      // Descanso obligatorio en curso: aunque te coloques y te muevas
      // antes de tiempo, esto NO cuenta como repetición — antes sí se
      // contaba en silencio si probabas a moverte en pleno descanso.
      this.announceRestBlocked(now);
      return false;
    }
    const d = Math.round(duration * 100) / 100;
    this.reps += 1;
    this.repDurations.push(d);
    this.currentSetReps += 1;
    this.currentSetDurations.push(d);
    this.lastRepTime = now;
    this.restAlerted = false;
    // Repetición de verdad contada: se acabó el descanso (si lo había),
    // vuelve la voz.
    this.restVoiceQuiet = false;
    // Se muestran las reps de ESTA serie, no el total de la sesión (el
    // total sigue guardándose bien en this.reps al terminar). currentSetReps
    // se reinicia a 0 al cerrar cada serie (más abajo), así que la voz
    // vuelve a empezar en "uno" en la siguiente serie automáticamente.
    this.repsEl.textContent = String(this.currentSetReps);
    this.speakRep(this.currentSetReps);

    // Aviso al llegar al objetivo — una sola vez, y sin parar nada: se
    // puede seguir contando por encima del 100% si te apetece (se
    // guarda tal cual, el backend no lo recorta). Es solo un chivatazo,
    // la decisión de seguir o terminar la tomas tú con el botón.
    //
    // Va en un aviso APARTE (workout-goal-banner), no solo en el texto
    // de estado normal: ese cambia con cada repetición siguiente y el
    // mensaje del objetivo podía pasar sin que te dieras ni cuenta si no
    // estabas mirando esa línea justo en ese instante. El banner se
    // queda puesto todo lo que quieras, hasta que termines o recalibres.
    if (this.targetSets && this.targetReps && !this.targetAnnounced) {
      const meta = this.targetSets * this.targetReps;
      if (this.reps >= meta) {
        this.targetAnnounced = true;
        // Al número ya dicho justo antes le sigue el aviso de meta, sin
        // cancelarlo (flush:false) — cancel() en speakRep() ya se encargó
        // de que no se pisen entre sí.
        if (this.voiceEnabled) speakOut("¡Objetivo cumplido!", { flush: false });
        if (this.goalBannerEl) {
          this.goalBannerEl.hidden = false;
          this.goalBannerEl.textContent = `🎯 ¡Objetivo cumplido! (${meta}) Sigue si quieres, o termina cuando acabes.`;
        }
        this.setStatus(`🎯 ¡Objetivo cumplido (${meta})!`);
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          [0, 0.14].forEach((t, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.frequency.value = i === 0 ? 880 : 1175;
            osc.connect(gain);
            gain.connect(ctx.destination);
            gain.gain.setValueAtTime(0.18, ctx.currentTime + t);
            osc.start(ctx.currentTime + t);
            osc.stop(ctx.currentTime + t + 0.13);
          });
        } catch (e) { /* si el navegador bloquea audio, no pasa nada */ }
        return true;
      }
    }
    this.setStatus(`¡${label} ${this.currentSetReps} de esta serie! (${duration.toFixed(1)}s)`);
    return true;
  }

  /**
   * Fondos: se cuentan por el ÁNGULO DEL CODO (hombro-codo-muñeca), de
   * perfil — ver el bloque DIP_* más arriba para el porqué del cambio
   * de método (antes nariz-vs-codos) y del rediseño que sustituyó la
   * cadera por el hombro como referencia de "¿sigues montada/o?" (con
   * datos reales de por qué).
   *
   * Se usa el lado (izq/der) que mejor se vea, igual que sentadillas:
   * de perfil solo se ve bien un lado del cuerpo.
   *
   * ARMADO: ya solo exige el codo recto y quieto (DIP_ARM_STABLE_MS) —
   * a propósito no se exige ninguna condición de hombro aquí. El coste
   * de armar un pelín pronto (p.ej. estando de pie con los brazos
   * rectos junto a la barra) es mínimo, porque ninguna repetición se
   * cuenta hasta que el codo se doble Y el hombro baje de verdad (ver
   * más abajo) — y a cambio se evita el problema real que sí tenía
   * exigir cadera/muñeca para armar: tardaba mucho en decir "te veo", o
   * directamente no llegaba a armar nunca.
   *
   * Mientras no estás armado (this.state === null) se va aprendiendo tu
   * altura de hombro de pie (dipGroundShoulderY, el valor MÁS BAJO
   * visto — Y crece hacia abajo), que sirve de referencia para saber
   * cuánto ha subido el hombro al montarte en las paralelas. No se
   * reinicia entre series (ver beginPrep/closeActiveSet): la cámara no
   * se mueve entre series, así que la referencia sigue siendo válida.
   * En el mismo tramo de pie se aprende TAMBIÉN, una sola vez, el largo
   * de tronco (dipTorsoLength, hombro-cadera) que se usa para normalizar
   * "cuánto ha subido/bajado el hombro" — ver el sexto bug, en el
   * bloque DIP_* de más arriba, sobre por qué ya no se mide ese largo
   * de referencia frame a frame con el brazo (hombro-codo).
   *
   * Una vez armado, cada fondo se cuenta en dos pasos, igual que
   * flexiones/sentadillas: el codo se dobla hasta ABAJO
   * (elbowAngle <= DIP_DOWN_ANGLE_DEG) y luego vuelve a estar recto
   * (elbowAngle >= DIP_UP_ANGLE_DEG) — ese regreso a ARRIBA es el que
   * intenta contar la repetición. Los dos pasos exigen ADEMÁS que el
   * hombro siga por encima de una fracción de su propio pico de subida
   * en esta serie (DIP_SHOULDER_RISE_MOUNTED_RATIO) — si no, el propio
   * gesto de montarte o bajarte de las paralelas (el codo también pasa
   * de doblado a recto, o al revés, sin ser un fondo de verdad) se
   * contaría como repetición. Y, justo antes de dar la repetición por
   * buena, se exige que el hombro haya bajado un mínimo de verdad
   * durante el tramo de abajada (DIP_MIN_SHOULDER_DROP_FACTOR) — esto
   * descarta gestos del brazo (rascarte, ajustarte algo) que doblan y
   * estiran el codo sin mover el cuerpo.
   *
   * El desmonte (bajarte de las paralelas) usa la misma idea en espejo,
   * con un umbral más estricto (DIP_SHOULDER_RISE_DISMOUNT_RATIO): codo
   * recto Y hombro de vuelta cerca de la referencia de pie. Un fondo
   * profundo de verdad nunca cumple esto a media repetición porque el
   * codo está DOBLADO en el punto más bajo. Reutiliza
   * closeActiveSet/noteAbsence/checkWaveGesture, igual que el resto de
   * GROUND_STYLE_COUNTERS, en vez de un cierre de serie propio.
   *
   * Todo lo anterior (calibración, shoulderRise, pico de la serie,
   * bajada de la repetición) usa la Y del hombro YA FILTRADA
   * (shoulderY: recorte de salto + media móvil, ver DIP_SHOULDER_MAX_
   * Y_JUMP/DIP_SHOULDER_SMOOTHING_ALPHA y el tercer bug real en el
   * bloque DIP_* de más arriba) — un salto puntual de un solo frame ya
   * no puede arrastrar ni la referencia de pie ni el pico de subida.
   * elbowAngle sigue usando el hombro BRUTO, sin este filtro, porque ahí
   * interesa la lectura más inmediata posible.
   *
   * Hay una TERCERA forma (además del desmonte "de perfil" por umbral,
   * arriba, y el gesto de la mano vía checkWaveGesture) de dar una serie
   * por terminada: girarte de frente a la cámara, para que se te vean
   * los DOS hombros a la vez con buena confianza — algo que nunca pasa
   * a media repetición, porque de perfil uno de los dos siempre queda
   * tapado por el propio cuerpo (ver DIP_FACE_CAMERA_VISIBILITY/STABLE_
   * MS y el cuarto ajuste en el bloque DIP_* de más arriba, con los
   * datos reales que lo motivaron). Se comprueba nada más entrar en la
   * función, antes incluso del chequeo de visibilidad por lado, porque
   * de frente los dos hombros se ven bien aunque de perfil uno de ellos
   * no llegara al mínimo.
   */
  processDip(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lElbow = lm[L_ELBOW], rElbow = lm[R_ELBOW];
    const lWrist = lm[L_WRIST], rWrist = lm[R_WRIST];
    const lHip = lm[L_HIP], rHip = lm[R_HIP];
    const lKnee = lm[L_KNEE], rKnee = lm[R_KNEE];
    const lAnkle = lm[L_ANKLE], rAnkle = lm[R_ANKLE];

    // Tercera forma de terminar la serie: girarte de frente a la cámara.
    // De perfil (como se hace el ejercicio) SOLO se ve bien un hombro —
    // el otro queda tapado por el propio cuerpo — así que ver los DOS a
    // la vez con buena confianza es una señal inequívoca de que te has
    // girado a mirar a la cámara, algo que nunca pasa a media
    // repetición. Se comprueba aquí, antes del chequeo de visibilidad
    // por lado de más abajo, para que funcione aunque de perfil un
    // hombro no llegara al mínimo (ver el cuarto ajuste, DIP_* arriba).
    //
    // NOVENO BUG REAL (visto en un registro con build
    // 2026-08-25-fondos-octavo-bug-desmonte, o sea código YA con el
    // octavo arreglo puesto — este es nuevo, no es el mismo de antes):
    // con la cámara del PC colocada DE FRENTE (el usuario probando
    // "desde localhost" sentado delante del portátil, no de perfil en
    // las paralelas), hombro_izq_vis y hombro_der_vis salen ~0.99–1.00
    // TODO el rato, incluso recién armado el contador. Eso hace que
    // facingCamera sea true casi siempre y, a los DIP_FACE_CAMERA_
    // STABLE_MS (500ms) de estar armado, esto cerraba la serie solo.
    // El primer arreglo (no dejar que dispare hasta contar AL MENOS UNA
    // repetición, this.currentSetReps > 0) tapaba el caso de "nunca
    // arranca", pero UNDÉCIMO BUG REAL, con un registro de build
    // 2026-08-25-fondos-solo-baja-por-rodilla (cámara de perfil de
    // verdad esta vez, confirmado por el usuario — "llevo dejando la
    // PUTA CAMARA DE LADO TODO ESTE RATO"): hombro_izq_vis/hombro_der_vis
    // se quedan en ~0.95–1.00 SIEMPRE, en top Y TAMBIÉN en bottom —
    // ejemplos reales del registro: a 45.6s, en pleno fondo (estado=
    // bottom, ángulo=89°), hombro_izq_vis=1.00 hombro_der_vis=1.00; a
    // 46.3s, también en bottom (ángulo=162°... bajando), igual. O sea:
    // para la cámara/postura real de este usuario, MediaPipe da los DOS
    // hombros por buenos SIEMPRE, sin importar si está de perfil de
    // verdad o girado — la señal simplemente no distingue nada para él.
    // Resultado, con currentSetReps > 0 ya puesto: en cuanto se cuenta
    // la primera repetición de una serie y el cuerpo vuelve a "top"
    // (brazos estirados) más de 500ms seguidos — que es exactamente lo
    // normal entre una repetición y la siguiente — esto disparaba y
    // cerraba la serie con 1 sola repetición. Se repite IDÉNTICO tres
    // veces en el mismo registro: cierra en 47.0s (1 rep), 49.4s (1 rep)
    // y 54.6s (1 rep) — siempre justo ~500-530ms después de la rep
    // contada, nunca por un desmonte de verdad. Esto es el "cuenta 1,
    // 1, 1..." que reporta el usuario: no es que el conteo de
    // repeticiones falle, es que la serie se cierra sola después de la
    // primera.
    //
    // Con dos registros reales ahora demostrando que esta señal no sirve
    // para distinguir "de perfil, entre repeticiones" de "girado de
    // frente a la cámara" en NINGUNA cámara/postura probada hasta ahora,
    // el arreglo tampoco es subir DIP_FACE_CAMERA_VISIBILITY (ya está al
    // máximo posible, 1.00, así que no hay margen — no es adivinar un
    // número nuevo, es que el propio dato ya no deja hueco para ningún
    // umbral que funcione). Así que esta tercera forma de cerrar la
    // serie queda DESACTIVADA por ahora: this.state y
    // this.currentSetReps ya no se consultan aquí, y closeActiveSet()
    // nunca se llama desde este bloque. Las otras dos formas de cerrar
    // la serie (el desmonte por ángulo/hombro/rodilla/cadera, más abajo
    // — que si funciona: ver [DESMONTE DETECTADO] a los 63.9s del mismo
    // registro — y el gesto de la mano, checkWaveGesture) siguen intactas
    // y no dependían de esto.
    this.dipFaceCameraSince = null;

    const leftVis = (
      (lShoulder.visibility ?? 1) + (lElbow.visibility ?? 1) + (lWrist.visibility ?? 1)
    ) / 3;
    const rightVis = (
      (rShoulder.visibility ?? 1) + (rElbow.visibility ?? 1) + (rWrist.visibility ?? 1)
    ) / 3;
    const useLeft = leftVis >= rightVis;
    const vis = useLeft ? leftVis : rightVis;

    if (vis < DIP_MIN_VISIBILITY) {
      this.announceStatus("No se te ven bien el hombro, el codo y la muñeca de un lado. Ponte de perfil a la cámara.");
      if (this.debugEl) this.debugEl.textContent = "buscando hombro, codo y muñeca de perfil…";
      this.logScissor(
        `[visibilidad baja] vis=${vis.toFixed(2)} (mín ${DIP_MIN_VISIBILITY}) estado=${this.state ?? "null"} — se reinicia dipArmedSince/dipBreakSince`
      );
      this.dipArmedSince = null;
      this.dipBreakSince = null;
      this.dipBreakInterruptSince = null;
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    const shoulder = useLeft ? lShoulder : rShoulder;
    const elbow = useLeft ? lElbow : rElbow;
    const wrist = useLeft ? lWrist : rWrist;
    const hip = useLeft ? lHip : rHip;
    const knee = useLeft ? lKnee : rKnee;
    const ankle = useLeft ? lAnkle : rAnkle;

    const elbowAngle = angle(shoulder, elbow, wrist);
    if (elbowAngle === null) return;

    // Ángulo de rodilla del mismo lado — para saber si las paralelas son
    // bajas (rodilla doblada cerca de 90°, ver dipBarType más abajo). NO
    // se exige (a diferencia de elbowAngle) porque en paralelas ALTAS la
    // pierna puede quedar fuera de encuadre sin que eso sea un problema
    // — solo se usa si además se ve razonablemente bien (kneeVisOk, más
    // abajo).
    const kneeAngle = angle(hip, knee, ankle);

    // Recorte de salto + media móvil sobre la Y del hombro — SOLO para lo
    // que sigue (calibración, "cuánto ha subido", pico de la serie,
    // cuánto ha bajado en la repetición). "shoulder" de arriba (bruto,
    // sin retraso) se sigue usando tal cual para elbowAngle, porque ahí
    // interesa la lectura más inmediata posible. Mismo patrón de dos
    // pasos que las tijeretas (SCISSOR_MAX_LIFT_JUMP + SCISSOR_SMOOTHING_
    // ALPHA): primero se recorta el salto bruto de un frame al siguiente
    // a un máximo físico (DIP_SHOULDER_MAX_Y_JUMP) y LUEGO se pasa por una
    // media móvil exponencial (DIP_SHOULDER_SMOOTHING_ALPHA) — ver el
    // tercer bug (arriba, en el bloque DIP_*) para los datos reales que
    // motivaron esto: un salto puntual de Y sin recortar llegó a arrastrar
    // tanto la referencia de pie (dipGroundShoulderY) como el pico de
    // subida de la serie (dipSetPeakShoulderRise).
    let rawShoulderY = shoulder.y;
    if (this.dipShoulderRawPrevY !== null) {
      const deltaShoulderY = rawShoulderY - this.dipShoulderRawPrevY;
      if (Math.abs(deltaShoulderY) > DIP_SHOULDER_MAX_Y_JUMP) {
        rawShoulderY = this.dipShoulderRawPrevY + Math.sign(deltaShoulderY) * DIP_SHOULDER_MAX_Y_JUMP;
      }
    }
    this.dipShoulderRawPrevY = rawShoulderY;
    if (this.dipShoulderSmoothY === null) {
      this.dipShoulderSmoothY = rawShoulderY;
    } else {
      this.dipShoulderSmoothY += DIP_SHOULDER_SMOOTHING_ALPHA * (rawShoulderY - this.dipShoulderSmoothY);
    }
    const shoulderY = this.dipShoulderSmoothY;

    // Mismo recorte de salto + media móvil, pero sobre la Y de la
    // CADERA — para el caso de paralelas altas (dipBarType, más abajo),
    // donde la referencia de desmonte es la cadera en vez del hombro.
    let rawHipY = hip.y;
    if (this.dipHipRawPrevY !== null) {
      const deltaHipY = rawHipY - this.dipHipRawPrevY;
      if (Math.abs(deltaHipY) > DIP_SHOULDER_MAX_Y_JUMP) {
        rawHipY = this.dipHipRawPrevY + Math.sign(deltaHipY) * DIP_SHOULDER_MAX_Y_JUMP;
      }
    }
    this.dipHipRawPrevY = rawHipY;
    if (this.dipHipSmoothY === null) {
      this.dipHipSmoothY = rawHipY;
    } else {
      this.dipHipSmoothY += DIP_SHOULDER_SMOOTHING_ALPHA * (rawHipY - this.dipHipSmoothY);
    }
    const hipY = this.dipHipSmoothY;

    // Referencia de "altura de pie": se toma nota mientras NO estés
    // montado (this.state === null) — así, en cuanto te subes a las
    // paralelas y el hombro sube de verdad, hay algo con qué comparar.
    // Solo guarda el valor MÁS BAJO visto (Math.max de la coordenada Y,
    // que crece hacia abajo), y SOLO en frames donde el hombro en sí se
    // ve razonablemente bien (DIP_CALIBRATION_MIN_VISIBILITY) — así un
    // único frame con mala lectura no puede arruinar la referencia para
    // el resto de la sesión (ver el bloque DIP_* de más arriba para el
    // bug real que esto arregla). No se reinicia entre series (ver
    // beginPrep): la cámara no se mueve entre series, así que no hace
    // falta bajarse y volver a subir para que siga siendo válida. Si
    // por lo que sea queda mal aprendida, pulsar Recalibrar la reinicia
    // desde cero.
    const shoulderVisOk = (shoulder.visibility ?? 1) >= DIP_CALIBRATION_MIN_VISIBILITY;
    if (this.state === null && shoulderVisOk) {
      this.dipGroundShoulderY =
        this.dipGroundShoulderY === null ? shoulderY : Math.max(this.dipGroundShoulderY, shoulderY);
    }

    // Misma referencia, pero de la cadera de pie — para el caso de
    // paralelas altas (dipBarType, más abajo).
    const hipVisOk = (hip.visibility ?? 1) >= DIP_CALIBRATION_MIN_VISIBILITY;
    if (this.state === null && hipVisOk) {
      this.dipGroundHipY = this.dipGroundHipY === null ? hipY : Math.max(this.dipGroundHipY, hipY);
    }

    // Largo de referencia para normalizar "cuánto ha subido/bajado el
    // hombro": TRONCO (hombro-cadera), aprendido UNA VEZ de pie y
    // congelado para el resto de la serie — igual que dipGroundShoulderY,
    // y con el mismo filtro de recorte de salto + media móvil que la Y
    // del hombro. Ya NO se mide frame a frame con el largo de brazo
    // (hombro-codo): ese largo se acorta mucho en 2D cuando el brazo gira
    // fuera del plano de la cámara al doblarse del todo, lo que disparaba
    // hombro_subido a valores como -2.94 en mitad de fondos reales y
    // bloqueaba para siempre la transición arriba→abajo (ver el sexto bug,
    // en el bloque DIP_* de más arriba, con los datos reales).
    let rawTorsoLength = Math.hypot(shoulder.x - hip.x, shoulder.y - hip.y);
    if (this.dipTorsoLengthRawPrev !== null) {
      const deltaTorsoLength = rawTorsoLength - this.dipTorsoLengthRawPrev;
      if (Math.abs(deltaTorsoLength) > DIP_TORSO_LENGTH_MAX_JUMP) {
        rawTorsoLength = this.dipTorsoLengthRawPrev + Math.sign(deltaTorsoLength) * DIP_TORSO_LENGTH_MAX_JUMP;
      }
    }
    this.dipTorsoLengthRawPrev = rawTorsoLength;
    const torsoVisOk = shoulderVisOk && (hip.visibility ?? 1) >= DIP_CALIBRATION_MIN_VISIBILITY;
    if (this.state === null && torsoVisOk) {
      this.dipTorsoLength =
        this.dipTorsoLength === null
          ? rawTorsoLength
          : this.dipTorsoLength + DIP_SHOULDER_SMOOTHING_ALPHA * (rawTorsoLength - this.dipTorsoLength);
    }

    const shoulderRise =
      this.dipGroundShoulderY === null || !this.dipTorsoLength
        ? 0
        : (this.dipGroundShoulderY - shoulderY) / this.dipTorsoLength;

    // Mismo cálculo, con la cadera — solo se usa de verdad en paralelas
    // altas (dipBarType === "alta", más abajo), pero se calcula siempre
    // para poder decidir dipBarType nada más armar.
    const hipRise =
      this.dipGroundHipY === null || !this.dipTorsoLength
        ? 0
        : (this.dipGroundHipY - hipY) / this.dipTorsoLength;

    if (this.state === null) {
      if (this.dipGroundShoulderY === null || !this.dipTorsoLength) {
        // No debería pasar salvo que el hombro o la cadera lleven toda la
        // sesión mal vistos (shoulderVisOk/torsoVisOk siempre falso).
        this.setStatus("Ponte de pie junto a las paralelas, de perfil a la cámara, un momento…");
      } else if (elbowAngle >= DIP_UP_ANGLE_DEG) {
        // Armado solo por el ángulo del codo — ver el docstring de
        // processDip para por qué ya no se exige nada de hombro aquí.
        if (this.dipArmedSince === null) this.dipArmedSince = now;
        if (now - this.dipArmedSince >= DIP_ARM_STABLE_MS) {
          this.state = "top";
          this.dipArmedSince = null;
          // Pico de subida de hombro de la serie que empieza ahora — de
          // aquí salen, más abajo, los umbrales de montada/o y desmonte
          // (ver DIP_SHOULDER_RISE_MOUNTED_RATIO/DISMOUNT_RATIO). Mínimo
          // 0.01 para no dividir cerca de cero si por lo que sea el
          // hombro no ha subido nada todavía en este primer frame.
          this.dipSetPeakShoulderRise = Math.max(shoulderRise, 0.01);
          this.dipSetPeakHipRise = Math.max(hipRise, 0.01);
          // Se redetermina la altura de las paralelas en cada serie
          // nueva (por si acaso, aunque la cámara no se mueva entre
          // series) — ver dipBarType, más abajo, mientras estés arriba.
          this.dipBarType = null;
          // dipTopShoulderY también se reinicia en cada serie nueva (no
          // solo al Recalibrar): si no, una lectura puntual mala de un
          // solo frame en una serie podía quedarse fija como referencia
          // de "arriba" para TODAS las series siguientes de la sesión,
          // sin corregirse nunca — ver el comentario largo, más abajo,
          // junto a dipRepShoulderTopY.
          this.dipTopShoulderY = null;
          this.dipFaceCameraSince = null;
          if (!this.startupVoiceGiven) {
            this.startupVoiceGiven = true;
            this.announceStatus(
              "Te veo. ¡Listo! Baja y sube. Para terminar una serie, bájate de las paralelas, ponte de frente a la cámara, sal del encuadre, o levanta un brazo y agita la mano.",
              "startup_ready"
            );
          } else {
            this.announceStatus("¡Listo! Baja y sube.", "ready_to_go");
          }
        } else {
          this.setStatus("Postura vista… confirmando (no te muevas).");
        }
      } else {
        this.dipArmedSince = null;
        this.setStatus("Agárrate a las paralelas con los brazos estirados para empezar.");
      }
      if (this.debugEl) {
        this.debugEl.textContent =
          `ángulo codo (${useLeft ? "izq" : "der"}): ${elbowAngle.toFixed(0)}° | hombro subido: ${shoulderRise.toFixed(2)} | esperando`;
      }
      this.logScissor(
        `[esperando armar] ángulo=${elbowAngle.toFixed(0)}° hombro_subido=${shoulderRise.toFixed(2)} ` +
        `hombro_y=${shoulderY.toFixed(3)}(bruto ${shoulder.y.toFixed(3)}) ` +
        `dipGroundShoulderY=${this.dipGroundShoulderY === null ? "-" : this.dipGroundShoulderY.toFixed(3)}`
      );
      return;
    }

    // Ya armado: el pico de subida de hombro de ESTA serie se sigue
    // actualizando mientras estás arriba — así los umbrales de más
    // abajo se adaptan a lo que TÚ has enseñado en esta serie concreta,
    // no a un número fijo adivinado sin datos reales.
    if (this.state === "top") {
      this.dipSetPeakShoulderRise = Math.max(this.dipSetPeakShoulderRise ?? 0.01, shoulderRise);
      this.dipSetPeakHipRise = Math.max(this.dipSetPeakHipRise ?? 0.01, hipRise);

      // Décimo bug real (reaplicado): mientras estás de verdad arriba,
      // se guarda aquí la Y MÁS ALTA (más pequeña) vista DESDE que se
      // armó esta serie — así, cuando empiece la bajada, hay una
      // referencia de "arriba" de la repetición ENTERA, no solo del
      // último frame antes de cruzar el ángulo de abajo (ver el
      // comentario largo junto a dipRepShoulderTopY, más abajo, con los
      // datos que motivaron esto).
      this.dipTopShoulderY =
        this.dipTopShoulderY === null ? shoulderY : Math.min(this.dipTopShoulderY, shoulderY);

      // Altura de las paralelas (dipBarType): se decide UNA VEZ por
      // serie, mientras estés arriba, y se congela en cuanto se decide
      // (no se vuelve a tocar hasta la siguiente serie armada).
      //
      // Solo se clasifica "baja" por rodilla (≤SQUAT_DOWN_ANGLE_DEG, el
      // mismo umbral ya probado en sentadillas, con visibilidad de
      // rodilla/tobillo comprobada) — es la única señal fiable que
      // tenemos: la cadera sube al montar TANTO en paralelas bajas como
      // en altas (el propio usuario lo confirmó: montar en posición de
      // soporte sube el torso el largo del brazo en los dos casos), así
      // que un umbral de "cadera ha subido algo" no distingue nada — solo
      // distinguiría paralelas altas de verdad (estilo street workout, en
      // las que el cuerpo sube 40-50cm porque los brazos están
      // completamente estirados) si tuviéramos un umbral validado con
      // datos reales de ESE caso, que no tenemos todavía. Así que, de
      // momento, NO hay clasificación automática de "alta": si la rodilla
      // no se ve doblada (o no se ve bien), dipBarType se queda sin
      // decidir y dismountShape (más abajo) sigue usando el hombro, tal
      // como se hacía antes de este cambio — el camino "alta" (cadera)
      // queda ya escrito más abajo para el día que haya un umbral real
      // con el que activarlo, pero por ahora nada lo activa.
      if (this.dipBarType === null) {
        const kneeVisOk =
          (knee.visibility ?? 1) >= DIP_CALIBRATION_MIN_VISIBILITY &&
          (ankle.visibility ?? 1) >= DIP_CALIBRATION_MIN_VISIBILITY;
        if (kneeVisOk && kneeAngle !== null && kneeAngle <= SQUAT_DOWN_ANGLE_DEG) {
          this.dipBarType = "baja";
          this.logScissor(
            `[PARALELAS BAJAS] rodilla=${kneeAngle.toFixed(0)}° (≤${SQUAT_DOWN_ANGLE_DEG}) — se usará la rodilla para el desmonte`
          );
        }
      }
    }
    const mountedThreshold = DIP_SHOULDER_RISE_MOUNTED_RATIO * (this.dipSetPeakShoulderRise ?? 0.01);
    const dismountThreshold = DIP_SHOULDER_RISE_DISMOUNT_RATIO * (this.dipSetPeakShoulderRise ?? 0.01);
    const hipDismountThreshold = DIP_SHOULDER_RISE_DISMOUNT_RATIO * (this.dipSetPeakHipRise ?? 0.01);

    // Chequeo de desmonte — codo recto Y hombro de vuelta cerca de la
    // referencia de pie DE VERDAD (dismountThreshold, más estricto que
    // mountedThreshold — ver el bloque DIP_* de más arriba). Un fondo
    // profundo de verdad tiene el codo DOBLADO en el punto más bajo, así
    // que nunca cumple esto a media repetición.
    // Octavo bug real, con datos de un registro real donde te quedaste de
    // pie, quieto, más de diez segundos después de bajarte de las
    // paralelas, y NUNCA se cerró la serie: el contador de desmonte
    // (dipBreakSince/DIP_BREAK_STABLE_MS) llegó a 969ms de los 1000 que
    // hacían falta — dos veces — y en ambas lo tiró todo a la basura un
    // ÚNICO frame suelto en el que elbowAngle bajó a 154° (un grado por
    // debajo de DIP_UP_ANGLE_DEG) por puro ruido de un landmark, con el
    // hombro clarísimamente ya abajo (hombro_subido=0.28, muy por debajo
    // del umbral de desmonte). Ese único frame reiniciaba dipBreakSince a
    // null entero, así que el segundo siguiente volvía a empezar de cero
    // — y así indefinidamente mientras estuvieras quieto, sin que la
    // cuenta llegara nunca a buen puerto. dismountShape en sí NO se
    // suaviza (sigue siendo el ángulo bruto de este frame, igual que en
    // las transiciones top/bottom) — lo que cambia es que una interrupción
    // de un solo frame ya NO tira dipBreakSince a la basura al momento:
    // hace falta que la interrupción misma se sostenga
    // DIP_BREAK_INTERRUPT_GRACE_MS (dipBreakInterruptSince, más abajo)
    // para darla por real y reiniciar de verdad — un volver A SUBIR de
    // verdad tarda mucho más que eso, así que sigue protegido igual.
    //
    // Con paralelas bajas o altas ya identificadas (dipBarType, más
    // arriba, mientras estabas en top), esta forma de "postura de
    // desmonte" se comprueba con la señal que toca — rodilla ESTIRADA de
    // nuevo (bajas) o cadera de vuelta cerca de tu altura de pie
    // (altas) — en vez de siempre el hombro. Sin clasificar todavía
    // (dipBarType === null, por ejemplo mientras la rodilla no se ve
    // bien y la cadera tampoco ha subido lo bastante para decidir), se
    // sigue con el hombro, exactamente como se hacía antes de este
    // cambio — así que en ese caso no cambia nada del comportamiento ya
    // confirmado.
    let dismountShape;
    if (this.dipBarType === "baja") {
      dismountShape = elbowAngle >= DIP_UP_ANGLE_DEG && kneeAngle !== null && kneeAngle >= SQUAT_UP_ANGLE_DEG;
    } else if (this.dipBarType === "alta") {
      dismountShape = elbowAngle >= DIP_UP_ANGLE_DEG && hipRise < hipDismountThreshold;
    } else {
      dismountShape = elbowAngle >= DIP_UP_ANGLE_DEG && shoulderRise < dismountThreshold;
    }
    if (dismountShape) {
      this.dipBreakInterruptSince = null;
      if (this.dipBreakSince === null) this.dipBreakSince = now;
      const breakElapsed = now - this.dipBreakSince;
      if (breakElapsed >= DIP_BREAK_STABLE_MS) {
        this.logScissor(
          `[DESMONTE DETECTADO] tipo=${this.dipBarType ?? "sin_determinar(hombro)"} ángulo=${elbowAngle.toFixed(0)}° ` +
          `hombro_subido=${shoulderRise.toFixed(2)}(<${dismountThreshold.toFixed(2)}) ` +
          `cadera_subida=${hipRise.toFixed(2)}(<${hipDismountThreshold.toFixed(2)}) ` +
          `rodilla=${kneeAngle === null ? "-" : kneeAngle.toFixed(0) + "°"}(≥${SQUAT_UP_ANGLE_DEG}) ` +
          `sostenido=${breakElapsed.toFixed(0)}ms — cerrando serie`
        );
        this.dipBreakSince = null;
        this.closeActiveSet();
        return;
      }
    } else if (this.dipBreakSince !== null) {
      if (this.dipBreakInterruptSince === null) this.dipBreakInterruptSince = now;
      const interruptElapsed = now - this.dipBreakInterruptSince;
      if (interruptElapsed >= DIP_BREAK_INTERRUPT_GRACE_MS) {
        this.logScissor(
          `[desmonte interrumpido] tipo=${this.dipBarType ?? "sin_determinar(hombro)"} ángulo=${elbowAngle.toFixed(0)}° ` +
          `hombro_subido=${shoulderRise.toFixed(2)}(<${dismountThreshold.toFixed(2)}) ` +
          `cadera_subida=${hipRise.toFixed(2)}(<${hipDismountThreshold.toFixed(2)}) ` +
          `rodilla=${kneeAngle === null ? "-" : kneeAngle.toFixed(0) + "°"}(≥${SQUAT_UP_ANGLE_DEG}) ` +
          `sostenido ${interruptElapsed.toFixed(0)}ms — se reinicia el conteo de desmonte`
        );
        this.dipBreakSince = null;
        this.dipBreakInterruptSince = null;
      }
      // si no, un solo frame (o unos pocos) de ruido — se ignora, ver el
      // octavo bug arriba, y dipBreakSince sigue vivo tal cual estaba.
    } else {
      this.dipBreakInterruptSince = null;
    }

    // La transición de vuelta a ARRIBA (más abajo) exige ADEMÁS que el
    // hombro siga claramente elevado (mountedThreshold) — sin esto, el
    // propio gesto de bajarte de las paralelas contaría como repetición
    // (ver el bloque DIP_* de más arriba).
    const stillMounted = shoulderRise >= mountedThreshold;
    if (this.state === "top") {
      // Séptimo bug real, con el largo de tronco ya puesto (sexto bug,
      // arriba): en un registro real la cuenta SEGUÍA en cero — el
      // estado nunca llegaba a "bottom" en toda la sesión, aunque el
      // ángulo de codo bajara de verdad y hondo (42°, 9°...). Aquí ya NO
      // era el largo de referencia (eso lo arregló el sexto bug): con
      // el tronco puesto, hombro_subido llegó "solo" a -1.05 (antes
      // -2.94), pero seguía cruzando por debajo de mountedThreshold
      // ANTES de que el ángulo llegara a DIP_DOWN_ANGLE_DEG (se vio
      // montada/o=no ya en ángulo=127°, muy lejos de los 90° que hacen
      // falta) — con lo que exigir stillMounted AQUÍ, para entrar en
      // "bottom", seguía bloqueando la transición para siempre. La razón
      // de fondo: al inclinarte hacia delante en el tramo bajo de un
      // fondo real, el hombro se mueve también hacia delante en la
      // imagen, no solo hacia abajo, y esa componente contamina
      // shoulderRise — un ruido de cámara que ninguna referencia de
      // largo (brazo o tronco) puede arreglar por sí sola. Arreglo:
      // dejar de exigir stillMounted para ENTRAR en "bottom" (solo hace
      // falta el ángulo) — la protección real contra falsos positivos ya
      // no depende de este chequeo aquí: sigue estando, sin tocar, en la
      // transición de VUELTA a arriba (stillMounted, más abajo — evita
      // contar el punto final de un desmonte real como si fuera una
      // repetición) y en la bajada mínima de verdad del hombro
      // (DIP_MIN_SHOULDER_DROP_FACTOR, ver el bug de "rascarse la
      // nariz") antes de dar la repetición por buena.
      // DÉCIMO BUG REAL (reaplicado tras revertirlo una vez — historial
      // completo aquí porque ya se dio marcha atrás una vez sin datos
      // suficientes): en un registro real (build fondos-noveno-bug-de-
      // frente) dos fondos de verdad, con el codo llegando a 9°-21°,
      // fueron descartados con bajada_hombro=0.08 contra el mínimo de
      // 0.15 — porque aquí se copiaba shoulderY de ESTE MISMO FRAME (el
      // del cruce del ángulo de abajo), perdiendo toda la bajada previa
      // desde que tenías los brazos estirados. Se cambió a usar
      // dipTopShoulderY (la Y más alta vista de verdad desde que se
      // armó la serie, actualizada más arriba mientras this.state ===
      // "top") — el usuario reportó entonces una repetición contada por
      // accidente al "dejar el portátil en posición", así que se
      // revirtió del todo por no tener un registro de ESE caso concreto
      // con el que diagnosticarlo. Pero el registro build fondos-altura-
      // paralelas (ya con la cámara de perfil confirmada, no de frente)
      // volvió a mostrar EXACTAMENTE el mismo problema: dos fondos
      // reales, con el ángulo llegando a 5°-50°, descartados con
      // bajada_hombro=0.03 y 0.10 contra el mínimo de 0.15 — con el
      // arreglo revertido, o sea con el bug original otra vez. Se
      // reaplica aquí, y esta vez dipTopShoulderY se reinicia también al
      // armar cada serie nueva (no solo al Recalibrar, ver más arriba en
      // esta función) — para que una lectura mala de un solo frame no
      // pueda quedarse fija de por vida como referencia de "arriba" para
      // toda la sesión, que es la explicación más probable del efecto
      // que describió el usuario, aunque sin un registro de ese momento
      // exacto no se puede confirmar del todo.
      if (elbowAngle <= DIP_DOWN_ANGLE_DEG) {
        this.state = "bottom";
        this.repStartTime = now;      // la repetición empieza al bajar
        this.dipRepShoulderTopY = this.dipTopShoulderY ?? shoulderY;
        this.dipRepShoulderMaxY = shoulderY;
      }
    } else {
      // state === "bottom": sigue el punto más bajo (Y más grande) que
      // alcanza el hombro durante la bajada, para poder comprobar luego
      // que de verdad ha bajado (y no solo el codo — ver el bug de
      // "rascarse la nariz" en el bloque DIP_* de más arriba).
      this.dipRepShoulderMaxY = Math.max(this.dipRepShoulderMaxY ?? shoulderY, shoulderY);
      if (elbowAngle >= DIP_UP_ANGLE_DEG && stillMounted) {
        const shoulderDrop =
          ((this.dipRepShoulderMaxY ?? shoulderY) - (this.dipRepShoulderTopY ?? shoulderY)) / this.dipTorsoLength;
        if (shoulderDrop >= DIP_MIN_SHOULDER_DROP_FACTOR) {
          this.countRep((now - this.repStartTime) / 1000, now, "Fondo");
          this.logScissor(
            `[REP CONTADA] ángulo=${elbowAngle.toFixed(0)}° bajada_hombro=${shoulderDrop.toFixed(2)} reps_serie=${this.currentSetReps}`
          );
        } else {
          this.logScissor(
            `[rep descartada — el hombro no ha bajado] ángulo=${elbowAngle.toFixed(0)}° bajada_hombro=${shoulderDrop.toFixed(2)} ` +
            `(mín ${DIP_MIN_SHOULDER_DROP_FACTOR}) — probablemente un gesto del brazo, no un fondo`
          );
        }
        this.state = "top";
      }
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `ángulo codo (${useLeft ? "izq" : "der"}): ${elbowAngle.toFixed(0)}° | hombro subido: ${shoulderRise.toFixed(2)} ` +
        `(mín. montada/o ${mountedThreshold.toFixed(2)}, desmonte <${dismountThreshold.toFixed(2)}) | estado: ${this.state} ` +
        `(abajo ≤${DIP_DOWN_ANGLE_DEG}°, arriba ≥${DIP_UP_ANGLE_DEG}°)`;
    }
    // Registro por frame para poder exportar y diagnosticar con datos
    // reales si hiciera falta (ver logScissor/exportScissorLog).
    this.logScissor(
      `ángulo=${elbowAngle.toFixed(0)}° hombro_subido=${shoulderRise.toFixed(2)} hombro_y=${shoulderY.toFixed(3)}(bruto ${shoulder.y.toFixed(3)}) ` +
      `(montada/o≥${mountedThreshold.toFixed(2)}, desmonte<${dismountThreshold.toFixed(2)}, pico_serie=${(this.dipSetPeakShoulderRise ?? 0).toFixed(2)}) estado=${this.state} ` +
      `tipo_paralelas=${this.dipBarType ?? "sin_determinar"} cadera_subida=${hipRise.toFixed(2)}(<${hipDismountThreshold.toFixed(2)}, pico=${(this.dipSetPeakHipRise ?? 0).toFixed(2)}) ` +
      `rodilla=${kneeAngle === null ? "-" : kneeAngle.toFixed(0) + "°"}(baja≤${SQUAT_DOWN_ANGLE_DEG}°/estirada≥${SQUAT_UP_ANGLE_DEG}°) ` +
      `montada/o=${stillMounted ? "sí" : "no"} forma_desmonte=${dismountShape ? "sí" : "no"} ` +
      `desmonte_sostenido=${this.dipBreakSince === null ? "-" : (now - this.dipBreakSince).toFixed(0) + "ms"} ` +
      // hombro_izq_vis/hombro_der_vis: se añaden aquí (aparte del chequeo
      // de "de frente a la cámara", más arriba en esta misma función) para
      // poder ver, con datos reales, a qué visibilidad se queda el hombro
      // TAPADO mientras trabajas de perfil a tu distancia normal de
      // cámara — así, si DIP_FACE_CAMERA_VISIBILITY (ver el bloque DIP_*
      // de más arriba) se queda corto o se pasa, se puede afinar con el
      // número exacto en vez de volver a adivinar.
      `hombro_izq_vis=${(lShoulder.visibility ?? 0).toFixed(2)} hombro_der_vis=${(rShoulder.visibility ?? 0).toFixed(2)}`
    );
  }

  /**
   * Flexiones: se cuentan por el ÁNGULO DEL CODO (hombro-codo-muñeca) —
   * ver el bloque PUSHUP_* más arriba para el porqué (a diferencia de
   * los fondos, aquí el ángulo SÍ se mide bien porque el movimiento ya
   * es de perfil por definición).
   *
   * ARRANQUE (corregido tras un fallo real: contaba reps sin que el
   * usuario se hubiera puesto en posición): antes solo se exigía brazo
   * recto + cuerpo en línea recta hombro-cadera-tobillo — pero esa línea
   * recta NO distingue estar tumbado boca abajo de estar de pie con los
   * brazos sueltos (de pie, esa misma línea también sale casi recta), así
   * que ponerte simplemente de pie delante de la cámara ya armaba el
   * contador. Arreglo: hace falta confirmar que estás TUMBADO Y BOCA
   * ABAJO de verdad, con la inclinación hombro-cadera respecto a la
   * HORIZONTAL (tiltFromHorizontal, la misma que usan crunch/abdominal
   * completo para su gate de "tumbado") — de pie esa inclinación es
   * ~90°, tumbado es ~0°. Con este chequeo de tilt ya no hace falta
   * exigir el codo doblado para distinguir tumbado de pie: de pie, por
   * mucho que el brazo esté recto, el tilt sale ~90° y el gate lo
   * descarta igual.
   *
   * Se pide la posición de ARRIBA para arrancar: tumbado boca abajo,
   * cuerpo en línea recta, brazos estirados (elbowAngle >=
   * PUSHUP_UP_ANGLE_DEG) y manos a la altura del pecho, codos pegados al
   * cuerpo (mirando hacia atrás, no hacia los lados). Es la postura de
   * plancha con la que se empieza una serie de flexiones de verdad —
   * igual que sentadillas arranca de pie (arriba) en vez de en cuclillas.
   * Hace falta mantener esa posición ON_GROUND_STABLE_MS seguidos (igual
   * que crunch/situp con groundStableSince) antes de armar — así
   * ponerte en posición no cuenta como nada, ni un frame ruidoso arma el
   * contador por error.
   *
   * Una vez armado (state "top"), cada flexión se cuenta en dos pasos,
   * igual que sentadillas: el codo se dobla hasta ABAJO
   * (elbowAngle <= PUSHUP_DOWN_ANGLE_DEG, state "bottom") y luego vuelve
   * a estar recto (elbowAngle >= PUSHUP_UP_ANGLE_DEG) — ese regreso a
   * ARRIBA es el que cuenta la repetición.
   *
   * Se usa el brazo que mejor se vea: de perfil, el brazo de atrás
   * queda tapado por el cuerpo — igual que en fondos y sentadillas.
   *
   * Cierre de serie: como el resto de ejercicios de suelo (crunch,
   * elevación de piernas, abdominal completo…), romper la postura —
   * levantarte, o simplemente dejar de estar tumbado boca abajo — un
   * rato seguido (OFF_GROUND_STABLE_MS) da la serie por terminada y
   * empieza la siguiente en cuanto vuelves a colocarte; también se
   * cierra saliendo del encuadre o con el gesto de agitar la mano, ver
   * noteAbsence/checkWaveGesture.
   */
  processPushup(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lElbow = lm[L_ELBOW], rElbow = lm[R_ELBOW];
    const lWrist = lm[L_WRIST], rWrist = lm[R_WRIST];
    const lHip = lm[L_HIP], rHip = lm[R_HIP];
    const lAnkle = lm[L_ANKLE], rAnkle = lm[R_ANKLE];

    const leftVis = (
      (lShoulder.visibility ?? 1) + (lElbow.visibility ?? 1) + (lWrist.visibility ?? 1) +
      (lHip.visibility ?? 1) + (lAnkle.visibility ?? 1)
    ) / 5;
    const rightVis = (
      (rShoulder.visibility ?? 1) + (rElbow.visibility ?? 1) + (rWrist.visibility ?? 1) +
      (rHip.visibility ?? 1) + (rAnkle.visibility ?? 1)
    ) / 5;
    const useLeft = leftVis >= rightVis;
    const vis = useLeft ? leftVis : rightVis;

    if (vis < PUSHUP_MIN_VISIBILITY) {
      this.announceStatus(
        "No se te ven bien el hombro, el codo, la muñeca, la cadera y el tobillo. Ponte de perfil a la " +
        "cámara, boca abajo, con las manos a la altura del pecho y los codos pegados al cuerpo."
      );
      if (this.debugEl) this.debugEl.textContent = "buscando hombro, codo, muñeca, cadera y tobillo de perfil…";
      this.pushupSide = null;
      this.groundStableSince = null;
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    const shoulder = useLeft ? lShoulder : rShoulder;
    const elbow = useLeft ? lElbow : rElbow;
    const wrist = useLeft ? lWrist : rWrist;
    const hip = useLeft ? lHip : rHip;
    const ankle = useLeft ? lAnkle : rAnkle;

    const elbowAngle = angle(shoulder, elbow, wrist);
    const lineAngle = angle(shoulder, hip, ankle);
    const tilt = tiltFromHorizontal(shoulder, hip);
    if (elbowAngle === null || lineAngle === null || tilt === null) return;

    this.pushupSide = useLeft ? "left" : "right";
    // TUMBADO BOCA ABAJO de verdad (tilt, no la línea del cuerpo — ver
    // docstring): de pie sale ~90°, tumbado sale ~0°. Se usa tanto para
    // armar el contador como, ya armado, para detectar que has roto la
    // postura (te has levantado) y cerrar la serie — ver más abajo.
    const onGround = tilt <= ON_GROUND_MAX_TILT_DEG;

    // Ya armado (en mitad de una serie): si dejas de estar tumbado boca
    // abajo un rato seguido, se acabó la postura — se cierra la serie en
    // curso y la siguiente empieza en cuanto vuelvas a tumbarte. A
    // diferencia de crunch/elevación de piernas/abdominal completo, aquí
    // se usa un umbral MÁS LAXO (PUSHUP_BROKEN_TILT_DEG) y MÁS TIEMPO
    // seguido (PUSHUP_BREAK_STABLE_MS) que el simple onGround del gate de
    // armado — ver por qué en el bloque PUSHUP_* de más arriba (el brazo
    // pegado al cuerpo tapa la cadera en la imagen y ensucia el tilt
    // justo al bajar, así que hace falta más margen para no cortar una
    // serie real a medias).
    if (this.state !== null) {
      const broken = tilt > PUSHUP_BROKEN_TILT_DEG;
      if (broken) {
        if (this.offGroundSince === null) this.offGroundSince = now;
        if (now - this.offGroundSince >= PUSHUP_BREAK_STABLE_MS) {
          this.closeActiveSet();
          return;
        }
      } else {
        this.offGroundSince = null;
      }
    }

    if (this.state === null) {
      // Para armar el contador hace falta verte TUMBADO BOCA ABAJO de
      // verdad Y en la posición de ARRIBA (brazos estirados, manos a la
      // altura del pecho, codos pegados al cuerpo), sostenida un rato —
      // no un solo frame, para no armar por un vistazo de pasada mientras
      // te colocas. Es la misma posición de plancha con la que se
      // arranca una serie de flexiones real.
      const bodyStraight = lineAngle >= PUSHUP_LINE_MIN_DEG;
      const armsStraight = elbowAngle >= PUSHUP_UP_ANGLE_DEG;

      if (onGround && bodyStraight && armsStraight) {
        if (this.groundStableSince === null) this.groundStableSince = now;
        if (now - this.groundStableSince >= ON_GROUND_STABLE_MS) {
          this.state = "top";
          this.groundStableSince = null;
          this.offGroundSince = null;
          if (!this.startupVoiceGiven) {
            this.startupVoiceGiven = true;
            this.announceStatus(
              "Te veo. ¡Listo! Puedes empezar. Para terminar una serie, ponte de pie, sal del " +
              "encuadre, o levanta un brazo y agita la mano.",
              "startup_ready"
            );
          } else {
            this.announceStatus("¡Listo! Puedes empezar.", "ready_to_go");
          }
        } else {
          this.setStatus("Postura vista… confirmando (no te muevas).");
        }
      } else {
        this.groundStableSince = null;
        this.setStatus(
          "Túmbate boca abajo, de perfil a la cámara, con los brazos estirados, las manos a la altura del " +
          "pecho y los codos pegados al cuerpo (mirando hacia atrás), para empezar."
        );
      }
    } else if (this.state === "top") {
      if (elbowAngle <= PUSHUP_DOWN_ANGLE_DEG) {
        // Empieza a bajar: arranca la flexión.
        this.state = "bottom";
        this.repStartTime = now;
      }
    } else if (elbowAngle >= PUSHUP_UP_ANGLE_DEG) {
      // El brazo ha vuelto a estar recto: repetición completa.
      this.countRep((now - this.repStartTime) / 1000, now, "Flexión");
      this.state = "top";
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `ángulo codo (${useLeft ? "izq" : "der"}): ${elbowAngle.toFixed(0)}° | inclinación: ${tilt.toFixed(0)}° | estado: ${this.state ?? "esperando"} ` +
        `(abajo ≤${PUSHUP_DOWN_ANGLE_DEG}°, arriba ≥${PUSHUP_UP_ANGLE_DEG}°)`;
    }
  }

  /**
   * Flexiones inclinadas: MISMO gesto de brazo que processPushup (mismo
   * ángulo de codo cuenta la repetición), pero con los pies en alto — ver
   * el bloque INCLINE_PUSHUP_* más arriba para el porqué del diseño
   * (comparación directa muñeca/tobillo, no un ángulo de inclinación) y
   * de los dos bugs reales que corrigió (flexión plana contando como
   * inclinada; un gesto de brazo suelto, ya armado, contando como
   * repetición). A diferencia de la primera versión, aquí SÍ hay cierre
   * automático de serie al romper la postura (dejar de tener los pies en
   * alto, o encogerte) — ver inPosition/INCLINE_PUSHUP_BROKEN_STABLE_MS
   * más abajo.
   */
  processInclinePushup(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lElbow = lm[L_ELBOW], rElbow = lm[R_ELBOW];
    const lWrist = lm[L_WRIST], rWrist = lm[R_WRIST];
    const lHip = lm[L_HIP], rHip = lm[R_HIP];
    const lAnkle = lm[L_ANKLE], rAnkle = lm[R_ANKLE];

    const leftVis = (
      (lShoulder.visibility ?? 1) + (lElbow.visibility ?? 1) + (lWrist.visibility ?? 1) +
      (lHip.visibility ?? 1) + (lAnkle.visibility ?? 1)
    ) / 5;
    const rightVis = (
      (rShoulder.visibility ?? 1) + (rElbow.visibility ?? 1) + (rWrist.visibility ?? 1) +
      (rHip.visibility ?? 1) + (rAnkle.visibility ?? 1)
    ) / 5;
    const useLeft = leftVis >= rightVis;
    const vis = useLeft ? leftVis : rightVis;

    if (vis < PUSHUP_MIN_VISIBILITY) {
      this.announceStatus(
        "No se te ven bien el hombro, el codo, la muñeca, la cadera y el tobillo. Ponte de perfil a la " +
        "cámara, boca abajo, con los pies apoyados en alto, las manos a la altura del pecho y los codos " +
        "pegados al cuerpo."
      );
      if (this.debugEl) this.debugEl.textContent = "buscando hombro, codo, muñeca, cadera y tobillo de perfil…";
      this.pushupSide = null;
      this.groundStableSince = null;
      // Sin ver el cuerpo entero no se puede confirmar que sigues con
      // los pies en alto — no hay motivo para seguir contando nada, así
      // que esto también cuenta como salir de posición (ver más abajo)
      // además de la señal de "fuera de encuadre" ya existente
      // (noteAbsence/OUT_OF_FRAME_STABLE_MS, que sigue corriendo aparte).
      if (this.state !== null) {
        if (this.offGroundSince === null) this.offGroundSince = now;
        if (now - this.offGroundSince >= INCLINE_PUSHUP_BROKEN_STABLE_MS) {
          this.closeActiveSet();
          return;
        }
      }
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    const shoulder = useLeft ? lShoulder : rShoulder;
    const elbow = useLeft ? lElbow : rElbow;
    const wrist = useLeft ? lWrist : rWrist;
    const hip = useLeft ? lHip : rHip;
    const ankle = useLeft ? lAnkle : rAnkle;

    const elbowAngle = angle(shoulder, elbow, wrist);
    const lineAngle = angle(shoulder, hip, ankle);
    if (elbowAngle === null || lineAngle === null) return;

    // "Pies en alto de verdad", medido en DIRECTO (no con un ángulo de
    // inclinación, que se coló con una flexión plana en la primera
    // versión — ver el bloque INCLINE_PUSHUP_* de más arriba): el tobillo
    // tiene que quedar claramente por ENCIMA de la muñeca en la imagen.
    // Y crece hacia abajo, así que "por encima" es tobillo.y < muñeca.y.
    // Normalizado por el largo de tronco (hombro-cadera) del frame actual
    // para que el umbral sirva igual da igual lo lejos que estés de la
    // cámara.
    const torsoLength = Math.hypot(shoulder.x - hip.x, shoulder.y - hip.y);
    const footRise = torsoLength > 0 ? (wrist.y - ankle.y) / torsoLength : 0;
    const feetElevated = footRise >= INCLINE_PUSHUP_MIN_FOOT_RISE_FACTOR;
    const bodyStraight = lineAngle >= PUSHUP_LINE_MIN_DEG;
    const inPosition = feetElevated && bodyStraight;

    this.pushupSide = useLeft ? "left" : "right";

    if (this.state !== null) {
      // Ya armado: SIEMPRE se comprueba la postura, no solo al empezar.
      // En cuanto deja de cumplirse (pies ya no en alto, o cuerpo
      // encogido), este frame se descarta ANTES de mirar el ángulo de
      // codo — así un gesto suelto de brazo (coger el portátil,
      // rascarte…) nunca puede colarse como repetición, aunque el propio
      // ángulo de codo dibuje un ciclo arriba-abajo-arriba de casualidad.
      // Si se sostiene fuera de posición, se cierra la serie sola — el
      // equivalente de "te has puesto de pie" para esta variante.
      if (!inPosition) {
        if (this.offGroundSince === null) this.offGroundSince = now;
        if (now - this.offGroundSince >= INCLINE_PUSHUP_BROKEN_STABLE_MS) {
          this.closeActiveSet();
          return;
        }
        if (this.debugEl) {
          this.debugEl.textContent =
            `fuera de posición (pies sobre manos: ${(footRise * 100).toFixed(0)}% tronco, mínimo ` +
            `${(INCLINE_PUSHUP_MIN_FOOT_RISE_FACTOR * 100).toFixed(0)}% · cuerpo recto: ${bodyStraight ? "sí" : "no"}) — se descarta este frame`;
        }
        return;
      }
      this.offGroundSince = null;
    }

    if (this.state === null) {
      // Para armar el contador hace falta verte en la posición de ARRIBA
      // (brazos estirados, manos a la altura del pecho, codos pegados al
      // cuerpo, cuerpo estirado) Y con los pies claramente en alto —
      // sostenida un rato, no un solo frame.
      const armsStraight = elbowAngle >= PUSHUP_UP_ANGLE_DEG;

      if (inPosition && armsStraight) {
        if (this.groundStableSince === null) this.groundStableSince = now;
        if (now - this.groundStableSince >= ON_GROUND_STABLE_MS) {
          this.state = "top";
          this.groundStableSince = null;
          this.offGroundSince = null;
          if (!this.startupVoiceGiven) {
            this.startupVoiceGiven = true;
            this.announceStatus(
              "Te veo. ¡Listo! Puedes empezar. Para terminar una serie, ponte de pie, sal del " +
              "encuadre, o levanta un brazo y agita la mano.",
              "startup_ready"
            );
          } else {
            this.announceStatus("¡Listo! Puedes empezar.", "ready_to_go");
          }
        } else {
          this.setStatus("Postura vista… confirmando (no te muevas).");
        }
      } else {
        this.groundStableSince = null;
        this.setStatus(
          "Túmbate boca abajo con los pies CLARAMENTE más altos que las manos (una silla, un escalón, " +
          "un sofá…), de perfil a la cámara, con los brazos estirados, las manos a la altura del pecho " +
          "y los codos pegados al cuerpo (mirando hacia atrás), para empezar."
        );
      }
    } else if (this.state === "top") {
      if (elbowAngle <= PUSHUP_DOWN_ANGLE_DEG) {
        // Empieza a bajar: arranca la flexión.
        this.state = "bottom";
        this.repStartTime = now;
      }
    } else if (elbowAngle >= PUSHUP_UP_ANGLE_DEG) {
      // El brazo ha vuelto a estar recto: repetición completa.
      this.countRep((now - this.repStartTime) / 1000, now, "Flexión inclinada");
      this.state = "top";
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `ángulo codo (${useLeft ? "izq" : "der"}): ${elbowAngle.toFixed(0)}° | pies sobre manos: ${(footRise * 100).toFixed(0)}% tronco (mínimo ${(INCLINE_PUSHUP_MIN_FOOT_RISE_FACTOR * 100).toFixed(0)}%) | estado: ${this.state ?? "esperando"} ` +
        `(abajo ≤${PUSHUP_DOWN_ANGLE_DEG}°, arriba ≥${PUSHUP_UP_ANGLE_DEG}°)`;
    }
  }

  /**
   * Sentadillas: se cuentan por el ángulo de la rodilla (cadera-rodilla-
   * tobillo), medido de PERFIL. Es la postura que mejor deja ver la
   * flexión real de la rodilla — de frente la cámara no puede distinguir
   * bien cuánto bajas (la pierna se acorta en la imagen igual al doblarse
   * que al alejarse un poco de la cámara).
   *
   * De perfil solo se ve bien una pierna (la otra queda tapada por el
   * cuerpo), así que cada frame se usa la que tenga mejor visibilidad —
   * no se fija un lado de antemano, porque te puedes colocar de perfil
   * por cualquiera de los dos lados y hasta puedes girarte a media sesión.
   *
   * No hace falta ningún paso de calibración (a diferencia de las
   * dominadas): un ángulo no cambia aunque te acerques o alejes de la
   * cámara, así que los umbrales sirven tal cual para cualquiera.
   */
  processSquat(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const lHip = lm[L_HIP], rHip = lm[R_HIP];
    const lKnee = lm[L_KNEE], rKnee = lm[R_KNEE];
    const lAnkle = lm[L_ANKLE], rAnkle = lm[R_ANKLE];

    const leftVis = ((lHip.visibility ?? 1) + (lKnee.visibility ?? 1) + (lAnkle.visibility ?? 1)) / 3;
    const rightVis = ((rHip.visibility ?? 1) + (rKnee.visibility ?? 1) + (rAnkle.visibility ?? 1)) / 3;
    const useLeft = leftVis >= rightVis;
    const vis = useLeft ? leftVis : rightVis;

    // Ponerte de frente a la cámara (dejar de estar de perfil) es otra
    // forma de terminar la serie — ver SQUAT_FRONTAL_VIS_DIFF_MAX. De
    // perfil un lado siempre queda tapado por el cuerpo (visibilidades
    // muy distintas); de frente, los dos lados se ven parecido.
    const isFrontal = leftVis >= SQUAT_MIN_VISIBILITY && rightVis >= SQUAT_MIN_VISIBILITY
      && Math.abs(leftVis - rightVis) < SQUAT_FRONTAL_VIS_DIFF_MAX;
    if (this.state !== null && isFrontal) {
      if (this.frontalStableSince === null) this.frontalStableSince = now;
      if (now - this.frontalStableSince >= SQUAT_FRONTAL_STABLE_MS) {
        this.closeActiveSet();
        return;
      }
    } else {
      this.frontalStableSince = null;
    }

    if (vis < SQUAT_MIN_VISIBILITY) {
      this.announceStatus("No se te ve bien la cadera, la rodilla y el tobillo. Ponte de perfil a la cámara, con toda la pierna en el encuadre.");
      if (this.debugEl) this.debugEl.textContent = "buscando cadera, rodilla y tobillo de perfil…";
      this.squatSide = null;
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    // La primera vez en toda la sesión que se te ve bien, un aviso de
    // que ya puedes empezar — en las siguientes series no hace falta
    // repetirlo, ya sabes cómo colocarte.
    if (!this.startupVoiceGiven) {
      this.startupVoiceGiven = true;
      this.announceStatus(
        "Cadera, rodilla y tobillo a la vista. ¡Listo! Ya puedes empezar. Para terminar una serie, ponte de frente a la cámara, sal del encuadre, o levanta un brazo y agita la mano.",
        "startup_ready"
      );
    }

    const hip = useLeft ? lHip : rHip;
    const knee = useLeft ? lKnee : rKnee;
    const ankle = useLeft ? lAnkle : rAnkle;
    const kneeAngle = angle(hip, knee, ankle);
    if (kneeAngle === null) return;

    this.squatSide = useLeft ? "left" : "right";
    this.squatKneeAngle = kneeAngle;

    if (this.state === null) {
      // Hay que empezar de pie, para no contar media repetición al entrar.
      if (kneeAngle >= SQUAT_UP_ANGLE_DEG) {
        this.state = "top";
        this.announceStatus("¡Listo! Baja en sentadilla y vuelve a subir.", "ready_to_go");
      } else {
        this.setStatus("Ponte de pie, de perfil a la cámara, para empezar.");
      }
    } else if (this.state === "top") {
      if (kneeAngle <= SQUAT_DOWN_ANGLE_DEG) {
        this.state = "bottom";
        this.repStartTime = now; // la repetición empieza al bajar
      }
    } else if (kneeAngle >= SQUAT_UP_ANGLE_DEG) {
      // Ha vuelto a subir del todo: repetición completa.
      this.countRep((now - this.repStartTime) / 1000, now, "Sentadilla");
      this.state = "top";
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `ángulo rodilla (${useLeft ? "izq" : "der"}): ${kneeAngle.toFixed(0)}° | estado: ${this.state ?? "esperando"} ` +
        `(abajo ≤${SQUAT_DOWN_ANGLE_DEG}°, arriba ≥${SQUAT_UP_ANGLE_DEG}°)`;
    }
  }

  /**
   * Mensaje de "vuelve a colocarte" propio de cada ejercicio de este
   * grupo (sentadillas y los tres abdominales tumbado) — usado tanto al
   * esperar la primera vez como al reabrir tras cerrar una serie.
   */
  groundWaitingMessage() {
    switch (this.counterKey) {
      case "crunch":
        return "Túmbate boca arriba, con los hombros en el suelo, para empezar.";
      case "legraise":
        return "Túmbate boca arriba con las piernas estiradas para empezar.";
      case "situp":
        return "Túmbate boca arriba del todo para empezar.";
      case "squat":
        return "Ponte de pie, de perfil a la cámara, para empezar.";
      case "scissor":
        return "Túmbate boca arriba y levanta los pies a un palmo del suelo para empezar.";
      case "doublecrunch":
        return "Túmbate boca arriba, levanta el torso hasta una posición intermedia y mantenla, para empezar.";
      case "pushup":
        return "Túmbate boca abajo, de perfil a la cámara, con los brazos estirados, las manos a la altura del pecho y los codos pegados al cuerpo, para empezar.";
      case "dip":
        return "Ponte de perfil a la cámara, agárrate a las paralelas con los brazos estirados, para empezar.";
      case "dumbbellcurl":
        return "Ponte de perfil a la cámara, de pie, con la mancuerna colgando y el brazo estirado, para empezar.";
      default:
        return "Ponte en posición para empezar.";
    }
  }

  /**
   * Mensaje de "vuelve a colocarte" para plancha/plancha lateral —
   * equivalente a groundWaitingMessage() pero para CAMERA_POSTURE_COUNTERS,
   * que no comparten su lógica de cierre (ver esa constante).
   */
  postureWaitingMessage() {
    // Pedir la postura (plancha o plancha lateral) directamente, de
    // entrada, es pedir demasiado de golpe — primero hace falta un paso
    // más sencillo: tumbarte del todo (en cualquier postura, boca arriba
    // vale) para que la cámara confirme que te ve entera/o de perfil, y
    // solo entonces pedir la postura de verdad — ver postureGroundConfirmed
    // en processPosture.
    if (this.counterKey === "sideplank") {
      return this.postureGroundConfirmed
        ? "Ponte de lado, apoyada/o en el codo y en los pies, y levanta el cuerpo del suelo hasta quedar en línea recta."
        : "Túmbate boca arriba, con la cámara de lado, y encuadra el cuerpo entero.";
    }
    if (this.counterKey === "plank") {
      return this.postureGroundConfirmed
        ? "Ponte boca abajo, en posición de plancha, apoyada/o en los antebrazos, con el cuerpo en línea recta."
        : "Túmbate boca arriba en el suelo, de perfil a la cámara, con el cuerpo entero en el encuadre.";
    }
    // Silla en pared: a diferencia de plancha/plancha lateral, no hay
    // paso 1 (la postura de partida, de pie, ya es trivial de
    // detectar) — se pide la postura de la silla directamente, igual
    // que en sentadillas.
    if (this.counterKey === "wallsit") {
      return "Ponte de espaldas a la pared, de perfil a la cámara y algo alejada/o (para que quepa la pierna entera), y dobla las rodillas deslizando la espalda por la pared hasta que los muslos queden paralelos al suelo.";
    }
    // Kneehold en barra: SÍ tiene paso 1 (a diferencia de silla en pared),
    // pero uno más simple que plancha/plancha lateral: solo confirmar que
    // te has agarrado a la barra (checkKneeHoldBarHanging), no hace falta
    // una postura intermedia rara como tumbarse. Antes se pedía la
    // postura completa (colgarte Y subir las rodillas) de golpe desde el
    // principio, con lo que mientras te acercabas a la barra el único
    // aviso que salía era el genérico de "no se te ve entera/o" — nada
    // que te dijera qué hacer. Ahora, mientras no se confirma el
    // agarre, el aviso es accionable de verdad.
    if (this.counterKey === "kneeholdbar") {
      return this.postureGroundConfirmed
        ? "Dobla las rodillas y súbelas hasta dejarlas más o menos a la altura de la cadera."
        : "Ve y agárrate a la barra, con los brazos estirados, de frente a la cámara y algo alejada/o (para que quepa el cuerpo entero).";
    }
    // Pino: como silla en pared, sin paso 1 — la señal de "cuerpo
    // invertido" ya es lo bastante clara como para pedir la postura
    // directamente (ver checkHandstandPosture).
    if (this.counterKey === "handstand") {
      return "Sube a un pino (con o sin apoyo en la pared) hasta que la cadera quede por encima de los hombros y los brazos por debajo de la cadera, aguantando el peso cerca del suelo.";
    }
    return "Ponte en posición de plancha, apoyada/o en los antebrazos, con el cuerpo en línea recta, para empezar.";
  }

  /**
   * Se cierra la serie en curso por cualquiera de las formas de "quiero
   * terminar" de este grupo de ejercicios (ver GROUND_STYLE_COUNTERS):
   * ponerte de pie (abdominales tumbado, ON_GROUND_STABLE_MS), ponerte
   * de frente a la cámara (sentadillas, SQUAT_FRONTAL_STABLE_MS), salir
   * del encuadre (noteAbsence), o agitar la mano con el brazo levantado
   * (checkWaveGesture) — o, para cualquier ejercicio, pulsando el botón
   * de Recalibrar. Igual que soltarte de la barra en dominadas o de las
   * paralelas en fondos: si tenías alguna repetición en la serie en
   * curso, se da por terminada. Si no tenías ninguna repetición todavía,
   * simplemente se vuelve a esperar a que te coloques.
   */
  closeActiveSet() {
    this.state = null;
    this.groundStableSince = null;
    this.offGroundSince = null;
    this.outOfFrameSince = null;
    this.waveSamples = [];
    this.frontalStableSince = null;
    this.torsoBandStableSince = null;
    this.torsoOutOfBandSince = null;
    const waitingMessage = this.groundWaitingMessage();

    if (this.currentSetReps > 0) {
      const closedReps = this.currentSetReps;
      this.sets.push({ reps: this.currentSetReps, durations: [...this.currentSetDurations] });
      this.currentSetReps = 0;
      this.currentSetDurations = [];
      this.updateSetDisplay();
      if (this.repsEl) this.repsEl.textContent = "0";
      this.setClosedAt = performance.now();
      // El aviso de descanso obligatorio SÍ tiene que oírse — por eso va
      // antes de silenciar la voz (restVoiceQuiet), no después.
      this.announceSetComplete(`Serie de ${closedReps}`, waitingMessage);
      this.restVoiceQuiet = true;
    } else {
      this.setStatus(waitingMessage);
    }
  }

  /**
   * No se te detecta (nada, o casi nada) este frame, en un ejercicio de
   * los que no tienen su propio cierre de serie (ver GROUND_STYLE_COUNTERS).
   * Si se mantiene un rato seguido (OUT_OF_FRAME_STABLE_MS, más largo
   * que un simple parpadeo de la detección), se interpreta como que te
   * has salido del encuadre a propósito y se cierra la serie en curso.
   */
  noteAbsence(now) {
    if (this.outOfFrameSince === null) this.outOfFrameSince = now;
    if (now - this.outOfFrameSince >= OUT_OF_FRAME_STABLE_MS) {
      this.closeActiveSet();
    }
  }

  /**
   * Guarda (si había algo que guardar) el tramo de plancha/plancha
   * lateral aguantado hasta ahora como una serie más — reps: 0, con la
   * duración aguantada en vez de un ciclo de repeticiones (mismo formato
   * que ya usa routine_save en el backend para ejercicios cronometrados).
   * Devuelve los segundos guardados (0 si no había ningún tramo abierto).
   * Solo mueve datos de sitio, no anuncia nada ni toca el texto en
   * pantalla — eso lo hace quien la llama (closeActivePostureSet, o
   * beginPrep si se pulsa Recalibrar a media plancha).
   */
  _flushPostureHold() {
    if (this.currentHoldSeconds < PLANK_MIN_HOLD_TO_COUNT_SECONDS) {
      this.currentHoldSeconds = 0;
      return 0;
    }
    const held = Math.round(this.currentHoldSeconds * 10) / 10;
    this.sets.push({ reps: 0, durations: [held] });
    this.totalHeldSeconds += held;
    this.currentHoldSeconds = 0;
    this.updateSetDisplay();
    return held;
  }

  /**
   * Postura de plancha/plancha lateral correcta este frame: suma el
   * tiempo transcurrido desde el último frame válido al tramo en curso,
   * actualiza el cronómetro en pantalla, y de vez en cuando suelta un
   * consejo rotativo (ver PLANK_TIPS/SIDEPLANK_TIPS).
   */
  notePostureOk(now) {
    this.postureInvalidSince = null;

    if (this.postureValidSince === null && this.setClosedAt !== null && now - this.setClosedAt < MIN_REST_MS) {
      // Mismo descanso obligatorio que countRep() (ver MIN_REST_MS): no
      // arranca el cronómetro de aguante hasta que pase, aunque vuelvas
      // a colocarte en postura antes de tiempo.
      this.announceRestBlocked(now);
      return;
    }

    if (!this.startupVoiceGiven) {
      this.startupVoiceGiven = true;
      // El consejo de apretar abdomen/glúteos salía solo como consejo
      // rotativo pasados PLANK_TIP_FIRST_AT_SECONDS (8s) — pero es lo
      // primero que hay que saber para aguantar bien, no algo que
      // esperar a que salga a mitad de la serie. Ahora se dice también
      // aquí, nada más confirmarse la postura.
      const startupTip =
        this.counterKey === "sideplank"
          ? "Postura correcta. ¡Listo! Aguanta la postura, con el abdomen apretado y la cadera alineada, sin caer ni subir. Para terminar una serie, rompe la postura, ponte de pie, sal del encuadre, o levanta un brazo y agita la mano."
          : this.counterKey === "wallsit"
          ? "Postura correcta. ¡Listo! Aguanta la postura, con la espalda bien pegada a la pared y el peso repartido entre los dos pies. Para terminar una serie, ponte de pie del todo, sal del encuadre, o levanta un brazo y agita la mano."
          : this.counterKey === "kneeholdbar"
          ? "Postura correcta. ¡Listo! Aguanta con las rodillas arriba, sin balancearte. Para terminar una serie, suelta la barra o sal del encuadre."
          : this.counterKey === "handstand"
          ? "Postura correcta. ¡Listo! Aguanta el pino, con el abdomen apretado y el cuerpo recto. Para terminar una serie, baja del pino o sal del encuadre."
          : "Postura correcta. ¡Listo! Aguanta la postura, apretando el abdomen y metiendo el culo hacia dentro, sin dejar caer la cadera. Para terminar una serie, rompe la postura, ponte de pie, sal del encuadre, o levanta un brazo y agita la mano.";
      this.announceStatus(startupTip, "startup_ready");
    }

    if (this.postureValidSince === null) {
      this.state = "holding";
      this.postureValidSince = now;
      this.lastPostureTickTs = now;
      // Postura válida de verdad: se acabó el descanso (si lo había),
      // vuelve la voz.
      this.restVoiceQuiet = false;
      // OJO: tipIndex NO se reinicia aquí. Antes se ponía a 0 cada vez que
      // arrancaba un tramo nuevo, así que los mismos consejos se repetían
      // en CADA serie de la sesión — justo la "tabarra" de la que se quejó
      // el usuario. Ahora tipIndex es por sesión (solo se reinicia en
      // beginPrep, al empezar de cero o recalibrar): cada consejo se dice
      // una vez y, una vez agotada la lista, no vuelve a sonar más en esta
      // sesión aunque hagas más series aguantando.
      this.lastTipAt = now; // no sueltes un consejo en el primer instante, deja asentar la postura
      // La cuenta atrás/adelante SÍ es por tramo (a diferencia de
      // tipIndex): cada vez que empiezas a aguantar de cero, vuelve a
      // contar desde el objetivo.
      this.postureCountdownLastSecond = null;
      this.postureGoalAnnouncedThisHold = false;
    }

    const delta = (now - this.lastPostureTickTs) / 1000;
    this.lastPostureTickTs = now;
    this.currentHoldSeconds += Math.max(0, delta);
    if (this.repsEl) this.repsEl.textContent = formatHoldSeconds(this.currentHoldSeconds);
    this.setStatus(`Aguantando… ${formatHoldSeconds(this.currentHoldSeconds)}`);

    // Cuenta atrás/adelante hablada hacia el objetivo de este tramo
    // (targetSeconds, si el ejercicio viene de un plan o de un circuito
    // con meta fija) — igual que se dice en voz alta cada repetición en
    // los ejercicios de repeticiones (speakRep), aquí se dice cada
    // segundo entero: cuenta atrás mientras falta para el objetivo, y en
    // cuanto se alcanza, pasa a contar hacia ADELANTE los segundos de
    // propina — así se nota de oído que vas por encima del 100%, igual
    // que seguir oyendo "9", "10" al pasarte de un objetivo de 8
    // dominadas. Sustituye a los consejos rotativos mientras dura (ver
    // más abajo): los dos se hablan por el mismo canal de voz y se
    // pisarían entre sí sonando cada segundo.
    if (this.targetSeconds) {
      if (this.currentHoldSeconds < this.targetSeconds) {
        const remaining = Math.ceil(this.targetSeconds - this.currentHoldSeconds);
        if (remaining >= 1 && remaining !== this.postureCountdownLastSecond) {
          this.postureCountdownLastSecond = remaining;
          this.speak(numeroEnPalabras(remaining), { flush: true });
        }
      } else if (!this.postureGoalAnnouncedThisHold) {
        this.postureGoalAnnouncedThisHold = true;
        this.postureCountdownLastSecond = 0;
        this.speak("¡Objetivo cumplido!", { flush: false });
        if (this.goalBannerEl) {
          this.goalBannerEl.hidden = false;
          this.goalBannerEl.textContent = `🎯 ¡Objetivo cumplido! (${formatHoldSeconds(this.targetSeconds)}) Sigue si quieres, o termina cuando acabes.`;
        }
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          [0, 0.14].forEach((t, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.frequency.value = i === 0 ? 880 : 1175;
            osc.connect(gain);
            gain.connect(ctx.destination);
            gain.gain.setValueAtTime(0.18, ctx.currentTime + t);
            osc.start(ctx.currentTime + t);
            osc.stop(ctx.currentTime + t + 0.13);
          });
        } catch (e) { /* si el navegador bloquea audio, no pasa nada */ }
      } else {
        const over = Math.floor(this.currentHoldSeconds - this.targetSeconds) + 1;
        if (over !== this.postureCountdownLastSecond) {
          this.postureCountdownLastSecond = over;
          this.speak(numeroEnPalabras(over), { flush: true });
        }
      }
      return; // sin consejos rotativos mezclándose por encima, ver comentario de arriba
    }

    const tips =
      this.counterKey === "sideplank"
        ? SIDEPLANK_TIPS
        : this.counterKey === "wallsit"
        ? WALLSIT_TIPS
        : this.counterKey === "kneeholdbar"
        ? KNEEHOLDBAR_TIPS
        : this.counterKey === "handstand"
        ? HANDSTAND_TIPS
        : PLANK_TIPS;
    if (
      this.currentHoldSeconds >= PLANK_TIP_FIRST_AT_SECONDS &&
      this.tipIndex < tips.length &&
      (this.lastTipAt === null || now - this.lastTipAt >= PLANK_TIP_INTERVAL_MS)
    ) {
      this.lastTipAt = now;
      this.speak(tips[this.tipIndex], { flush: false });
      this.tipIndex += 1;
    }
  }

  /**
   * Postura de plancha/plancha lateral rota este frame (o no se te
   * detecta en absoluto). No se cierra la serie a la primera — se da un
   * margen (PLANK_INVALID_STABLE_MS) por si es solo un parpadeo de la
   * cámara o un ajuste rápido, igual que ARMS_DOWN_STABLE_MS en
   * dominadas — y solo entonces se cierra el tramo aguantado (si había
   * alguno) como una serie terminada.
   */
  notePostureBroken(now, reason) {
    if (this.postureInvalidSince === null) this.postureInvalidSince = now;
    this.postureValidSince = null;
    this.lastPostureTickTs = null;
    if (reason) this.announceStatus(reason, "posture_broken");

    // Kneehold en barra usa un margen más largo que el resto (ver
    // KNEEHOLDBAR_INVALID_STABLE_MS, junto a POSTURE_FLICKER_STABLE_MS):
    // más propenso a rachas de mal seguimiento de más de un frame suelto
    // con la rodilla muy flexionada.
    const invalidStableMs =
      this.counterKey === "kneeholdbar" ? KNEEHOLDBAR_INVALID_STABLE_MS
      : this.counterKey === "handstand" ? HANDSTAND_INVALID_STABLE_MS
      : PLANK_INVALID_STABLE_MS;
    if (now - this.postureInvalidSince >= invalidStableMs) {
      this.closeActivePostureSet();
    }
  }

  /**
   * Cierra el tramo de plancha/plancha lateral en curso — equivalente a
   * closeActiveSet() pero para CAMERA_POSTURE_COUNTERS (ver esa
   * constante para por qué no comparten la misma lógica).
   */
  closeActivePostureSet() {
    this.postureInvalidSince = null;
    this.postureValidSince = null;
    this.lastPostureTickTs = null;
    this.postureLastOk = null;
    this.postureCandidateOk = null;
    this.postureCandidateSince = null;
    this.sidePlankDownSide = null;
    this.state = null;
    const held = this._flushPostureHold();
    if (this.repsEl) this.repsEl.textContent = formatHoldSeconds(0);
    // tipIndex NO se reinicia aquí — ver notePostureOk() para el porqué.
    this.lastTipAt = null;
    // La cuenta atrás/adelante SÍ es por tramo — se reinicia también al
    // arrancar uno nuevo (ver notePostureOk), pero limpiarla aquí además
    // evita arrastrar un "objetivo ya cumplido" al primer frame del
    // siguiente tramo por si acaso.
    this.postureCountdownLastSecond = null;
    this.postureGoalAnnouncedThisHold = false;

    if (held > 0) {
      this.setClosedAt = performance.now();
      this.announceSetComplete(`Serie de ${formatHoldSeconds(held)}`, this.postureWaitingMessage());
      this.restVoiceQuiet = true;
    } else {
      this.setStatus(this.postureWaitingMessage());
    }
  }

  /**
   * Plancha / plancha lateral: usa checkPlankPosture()/checkSidePlankPosture()
   * (compartidas con circuit.js/session-runner.js, ver esas funciones más
   * arriba) para decidir, frame a frame, si la postura es correcta.
   */
  processPosture(lm, now) {
    // Paso 1, común a plancha y plancha lateral: tumbarte del todo, en
    // cualquier orientación, antes de pedir la postura en sí — ver la
    // nota junto a checkLyingFlat/postureGroundConfirmed. Antes la
    // plancha lateral no pasaba por esto (se asumía que su postura de
    // partida ya era fácil de detectar a la primera), pero en la
    // práctica pedía la postura completa de golpe nada más empezar la
    // serie — ahora sigue el mismo patrón de dos pasos que la plancha
    // normal.
    // Silla en pared no pasa por este paso 1 (ver postureWaitingMessage):
    // postureGroundConfirmed se queda en false toda la sesión para
    // "wallsit", así que esta condición nunca se cumple para ese
    // contador y se va directa a la comprobación de la postura, más
    // abajo.
    //
    // Kneehold en barra reutiliza el mismo patrón de dos pasos, pero con
    // su propio paso 1 (checkKneeHoldBarHanging: confirmar el agarre) en
    // vez de tumbarte del todo — ver postureWaitingMessage/
    // checkKneeHoldBarHanging para el porqué.
    const isKneeHoldStep1 = this.counterKey === "kneeholdbar" && !this.postureGroundConfirmed;
    if (((this.counterKey === "plank" || this.counterKey === "sideplank") && !this.postureGroundConfirmed) || isKneeHoldStep1) {
      const flat = isKneeHoldStep1 ? checkKneeHoldBarHanging(lm) : checkLyingFlat(lm);
      const stableMs = isKneeHoldStep1 ? HANG_STABLE_MS : ON_GROUND_STABLE_MS;
      // Igual que dominadas (ver startupVoiceGiven junto a HANG_STABLE_MS,
      // más abajo): nada más verte aparecer en la cámara, aunque todavía
      // no estés colgada/o, un aviso por voz de qué hacer — antes esto se
      // quedaba en texto en pantalla nada más, sin decirse en voz alta.
      if (isKneeHoldStep1 && flat.visible && !this.startupVoiceGiven) {
        this.startupVoiceGiven = true;
        this.announceStatus("¡Listo! Cuélgate de la barra con los brazos estirados para empezar.", "startup_ready");
      }
      if (flat.ok) {
        if (this.postureGroundSince === null) this.postureGroundSince = now;
        if (now - this.postureGroundSince >= stableMs) {
          this.postureGroundConfirmed = true;
          this.postureGroundSince = null;
          this.postureLastOk = null;
          this.postureCandidateOk = null;
          this.postureCandidateSince = null;
          const flipMessage = isKneeHoldStep1
            ? "¡Listo! Ya puedes subir las rodillas, doblándolas, hasta dejarlas más o menos a la altura de la cadera."
            : this.counterKey === "sideplank"
            ? "¡Bien, te veo! Ahora ponte de lado, apoya el codo justo debajo del hombro y los pies uno sobre otro, y levanta el cuerpo del suelo hasta quedar en línea recta, de los hombros a los tobillos."
            : "¡Bien, te veo! Ahora date la vuelta, boca abajo, y ponte en posición de plancha: apoyada/o en los antebrazos, con los codos justo debajo de los hombros y el cuerpo entero alzado del suelo, en línea recta.";
          this.announceStatus(flipMessage, isKneeHoldStep1 ? "kneehold_ready" : "plank_flip");
        } else {
          this.setStatus(isKneeHoldStep1 ? "Colgada/o… confirmando (no te muevas)" : "Tumbada/o… confirmando (no te muevas)");
        }
      } else {
        this.postureGroundSince = null;
        this.setStatus(this.postureWaitingMessage());
      }
      if (this.debugEl) {
        this.debugEl.textContent = isKneeHoldStep1
          ? `paso 1 de 2: agarrada/o a la barra — ${flat.ok ? "sí, confirmando" : "todavía no"}`
          : `paso 1 de 2: tumbarte del todo — ${flat.ok ? "sí, confirmando" : "todavía no"} | ` +
            `ángulo cadera: ${flat.lineAngle ?? "-"}° (mínimo ${LYING_FLAT_MIN_DEG}) | ` +
            `largo cuerpo/hombros: ${flat.bodyLengthFactor} (mínimo ${MIN_BODY_LENGTH_FACTOR})`;
      }
      this.logScissor(
        isKneeHoldStep1
          ? `[kneehold en barra, paso 1] ok=${flat.ok ? "sí" : "no"}`
          : `[${this.counterKey === "sideplank" ? "plancha lateral" : "plancha"}, paso 1] ok=${flat.ok ? "sí" : "no"} motivo=${flat.reason ?? "-"} ` +
            `angulo=${flat.lineAngle ?? "-"} largo=${flat.bodyLengthFactor}`
      );
      return;
    }

    const check =
      this.counterKey === "sideplank"
        ? checkSidePlankPosture(lm, this.sidePlankDownSide)
        : this.counterKey === "wallsit"
        ? checkWallSitPosture(lm)
        : this.counterKey === "kneeholdbar"
        ? checkKneeHoldBarPosture(lm)
        : this.counterKey === "handstand"
        ? checkHandstandPosture(lm)
        : checkPlankPosture(lm);
    if (this.counterKey === "sideplank" && check.downSide) this.sidePlankDownSide = check.downSide;
    // Antes este texto tenía los nombres de los campos de checkPlankPosture
    // escritos a mano — para checkSidePlankPosture (campos distintos:
    // hipLift, elbowDrop…) siempre salía en blanco ("-"). Ahora se vuelca
    // sin más lo que devuelva check.debug, sirva para el contador que sirva.
    if (this.debugEl && check.debug) {
      const parts = Object.entries(check.debug).map(([k, v]) => `${k}: ${v ?? "-"}`);
      this.debugEl.textContent = `${parts.join(" | ")} | ${check.ok ? "postura OK" : "postura incorrecta"}`;
    }

    // Un par de frames sueltos con una lectura ruidosa, justo en el
    // borde de un umbral, no deberían hacer parpadear el aviso entre
    // "aguantando" y "postura incorrecta" todo el rato — ver
    // POSTURE_FLICKER_STABLE_MS. Se actúa según el último estado ya
    // CONFIRMADO (this.postureLastOk), no según la lectura de este
    // frame suelto.
    if (this.postureLastOk === null) {
      this.postureLastOk = check.ok;
      this.postureCandidateOk = null;
      this.postureCandidateSince = null;
    } else if (check.ok === this.postureLastOk) {
      this.postureCandidateOk = null;
      this.postureCandidateSince = null;
    } else if (check.ok === this.postureCandidateOk) {
      const flickerStableMs =
        this.counterKey === "kneeholdbar" ? KNEEHOLDBAR_FLICKER_STABLE_MS
        : this.counterKey === "handstand" ? HANDSTAND_FLICKER_STABLE_MS
        : POSTURE_FLICKER_STABLE_MS;
      if (now - this.postureCandidateSince >= flickerStableMs) {
        this.postureLastOk = check.ok;
        this.postureCandidateOk = null;
        this.postureCandidateSince = null;
      }
    } else {
      this.postureCandidateOk = check.ok;
      this.postureCandidateSince = now;
    }

    const debugStr = check.debug
      ? Object.entries(check.debug).map(([k, v]) => `${k}=${v ?? "-"}`).join(" ")
      : "-";
    const postureLabel =
      this.counterKey === "sideplank"
        ? "plancha lateral"
        : this.counterKey === "wallsit"
        ? "silla en pared"
        : this.counterKey === "kneeholdbar"
        ? "kneehold en barra"
        : this.counterKey === "handstand"
        ? "pino"
        : "plancha";
    this.logScissor(
      `[${postureLabel}, paso 2] frame_ok=${check.ok ? "sí" : "no"} confirmado=${this.postureLastOk ? "sí" : "no"} ` +
      `motivo=${check.reason ?? "-"} ${debugStr} ` +
      `aguantado=${this.currentHoldSeconds.toFixed(1)}s`
    );

    if (!this.postureLastOk) {
      this.notePostureBroken(now, check.reason);
      return;
    }
    this.notePostureOk(now);
  }

  /**
   * Gesto para terminar la serie sin ponerte de pie ni salir del
   * encuadre: levanta un brazo por encima del hombro y agita la mano a
   * los lados un par de veces. Guarda un historial corto (WAVE_WINDOW_MS)
   * de la posición horizontal de la muñeca levantada y cuenta los
   * cambios de sentido (izquierda-derecha-izquierda…) de amplitud
   * suficiente (WAVE_MIN_AMPLITUDE_FACTOR) para no confundir un temblor
   * de la mano con un vaivén de verdad. Devuelve true en cuanto detecta
   * suficientes cambios de sentido (WAVE_MIN_DIRECTION_CHANGES).
   */
  checkWaveGesture(lm, now) {
    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lWrist = lm[L_WRIST], rWrist = lm[R_WRIST];
    const shoulderWidth = Math.hypot(lShoulder.x - rShoulder.x, lShoulder.y - rShoulder.y);
    if (!shoulderWidth) return false;
    const shoulderMidY = (lShoulder.y + rShoulder.y) / 2;
    const raiseThreshold = shoulderMidY - WAVE_RAISE_MARGIN_FACTOR * shoulderWidth;

    const lRaised = (lWrist.visibility ?? 1) >= WAVE_MIN_VISIBILITY && lWrist.y < raiseThreshold;
    const rRaised = (rWrist.visibility ?? 1) >= WAVE_MIN_VISIBILITY && rWrist.y < raiseThreshold;

    if (!lRaised && !rRaised) {
      this.waveSamples = [];
      return false;
    }
    // Si se levantan los dos brazos a la vez, cualquiera de los dos vale
    // — no hace falta saber cuál, solo que se mueva de un lado a otro.
    const wrist = lRaised ? lWrist : rWrist;

    this.waveSamples.push({ t: now, x: wrist.x });
    this.waveSamples = this.waveSamples.filter((s) => now - s.t <= WAVE_WINDOW_MS);
    if (this.waveSamples.length < 3) return false;

    let dirChanges = 0;
    let lastDir = null;
    let extremeX = this.waveSamples[0].x;
    for (let i = 1; i < this.waveSamples.length; i++) {
      const dx = this.waveSamples[i].x - extremeX;
      if (Math.abs(dx) < WAVE_MIN_AMPLITUDE_FACTOR * shoulderWidth) continue;
      const dir = dx > 0 ? "right" : "left";
      if (lastDir !== null && dir !== lastDir) dirChanges++;
      lastDir = dir;
      extremeX = this.waveSamples[i].x;
    }

    if (dirChanges >= WAVE_MIN_DIRECTION_CHANGES) {
      this.waveSamples = [];
      return true;
    }
    return false;
  }

  /**
   * Crunch: cuenta cuánto sube el HOMBRO por encima de la CADERA (que
   * se queda fija en el suelo y sirve de referencia de escala junto al
   * muslo). Ver el bloque de comentarios junto a CRUNCH_UP_FACTOR más
   * arriba para por qué no se usa un ángulo aquí, a diferencia de
   * elevación de piernas o abdominal completo.
   *
   * Antes de armar el contador hace falta verte tumbado (inclinación
   * hombro-cadera) y QUIETO un rato (ON_GROUND_STABLE_MS) — si no,
   * ponerte en el suelo, o el rato en que te levantas de la silla para
   * ir a tumbarte, ya contaba como una repetición por sí solo (visto en
   * pruebas reales). Ese mismo gate, una vez armado, también sirve para
   * cerrar la serie en cuanto te vuelves a poner de pie, te sales del
   * encuadre un momento, o agitas la mano con el brazo levantado (ver
   * closeActiveSet, noteAbsence y checkWaveGesture) — así hay varias
   * formas de pasar a la siguiente serie sin tener que levantarte si no
   * quieres (o, como siempre, pulsando el botón de Recalibrar).
   */
  processCrunch(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lHip = lm[L_HIP], rHip = lm[R_HIP];
    const lKnee = lm[L_KNEE], rKnee = lm[R_KNEE];

    const leftVis = ((lShoulder.visibility ?? 1) + (lHip.visibility ?? 1) + (lKnee.visibility ?? 1)) / 3;
    const rightVis = ((rShoulder.visibility ?? 1) + (rHip.visibility ?? 1) + (rKnee.visibility ?? 1)) / 3;
    const useLeft = leftVis >= rightVis;
    const vis = useLeft ? leftVis : rightVis;

    if (vis < CRUNCH_MIN_VISIBILITY) {
      this.announceStatus("No se te ven bien el hombro, la cadera y la rodilla. Ponte de perfil a la cámara, tumbado boca arriba.");
      if (this.debugEl) this.debugEl.textContent = "buscando hombro, cadera y rodilla de perfil…";
      this.groundStableSince = null;
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    const shoulder = useLeft ? lShoulder : rShoulder;
    const hip = useLeft ? lHip : rHip;
    const knee = useLeft ? lKnee : rKnee;
    const thighLength = Math.hypot(hip.x - knee.x, hip.y - knee.y);
    if (!thighLength) return;

    if (!this.startupVoiceGiven) {
      this.startupVoiceGiven = true;
      this.announceStatus(
        "Te veo. ¡Listo! Túmbate boca arriba y empieza cuando quieras. Para terminar una serie, levántate, sal del encuadre, o levanta un brazo y agita la mano.",
        "startup_ready"
      );
    }

    // Cuánto sube el hombro por ENCIMA de la cadera (en pantalla, arriba
    // es "y" menor), en proporción al muslo.
    const lift = (hip.y - shoulder.y) / thighLength;
    const tilt = tiltFromHorizontal(shoulder, hip);
    if (tilt === null) return;
    const onGround = tilt <= ON_GROUND_MAX_TILT_DEG;

    if (this.state === null) {
      if (onGround) {
        if (this.groundStableSince === null) this.groundStableSince = now;
        if (now - this.groundStableSince >= ON_GROUND_STABLE_MS) {
          this.state = "down";
          this.offGroundSince = null;
          this.announceStatus("¡Listo! Sube los hombros y vuelve a bajar.", "ready_to_go");
        } else {
          this.setStatus("Tumbado… confirmando (no te muevas)");
        }
      } else {
        this.groundStableSince = null;
        this.setStatus("Túmbate boca arriba, con los hombros en el suelo, para empezar.");
      }
      if (this.debugEl) {
        this.debugEl.textContent = `inclinación torso: ${tilt.toFixed(0)}° | tumbado: ${onGround ? "sí" : "no"} | esperando a armar`;
      }
      return;
    }

    if (this.state === "down") {
      if (!onGround) {
        if (this.offGroundSince === null) this.offGroundSince = now;
        if (now - this.offGroundSince >= OFF_GROUND_STABLE_MS) {
          this.closeActiveSet();
          return;
        }
      } else {
        this.offGroundSince = null;
      }
    }

    if (this.state === "down") {
      if (lift >= CRUNCH_UP_FACTOR) {
        this.state = "up";
        this.repStartTime = now;
      }
    } else if (lift <= CRUNCH_DOWN_FACTOR) {
      this.countRep((now - this.repStartTime) / 1000, now, "Crunch");
      this.state = "down";
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `hombro sobre cadera: ${lift.toFixed(2)} | estado: ${this.state ?? "esperando"} ` +
        `(tumbado ≤${CRUNCH_DOWN_FACTOR}, arriba ≥${CRUNCH_UP_FACTOR})`;
    }
  }

  /**
   * Elevación de piernas: ángulo de cadera (hombro-cadera-tobillo).
   * Mismo enfoque que la rodilla en sentadillas, aplicado a la cadera
   * como pivote — ver el comentario junto a LEG_RAISE_DOWN_ANGLE_DEG.
   *
   * Igual que en crunch, hace falta verte tumbado y quieto un rato para
   * armar el contador (ver processCrunch) — y aquí, ADEMÁS, con las
   * piernas estiradas del todo (ángulo de rodilla cadera-rodilla-tobillo
   * ≥ LEG_RAISE_STRAIGHT_MIN_DEG): con las rodillas dobladas no es
   * elevación de piernas. Antes de este cambio, levantarte de la silla
   * para ir a tumbarte ya colaba una repetición completa sin haber
   * llegado siquiera a tumbarte (visto en pruebas reales) — el gate de
   * "tumbado y quieto" lo evita.
   */
  processLegRaise(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lHip = lm[L_HIP], rHip = lm[R_HIP];
    const lKnee = lm[L_KNEE], rKnee = lm[R_KNEE];
    const lAnkle = lm[L_ANKLE], rAnkle = lm[R_ANKLE];

    const leftVis = ((lShoulder.visibility ?? 1) + (lHip.visibility ?? 1) + (lKnee.visibility ?? 1) + (lAnkle.visibility ?? 1)) / 4;
    const rightVis = ((rShoulder.visibility ?? 1) + (rHip.visibility ?? 1) + (rKnee.visibility ?? 1) + (rAnkle.visibility ?? 1)) / 4;
    const useLeft = leftVis >= rightVis;
    const vis = useLeft ? leftVis : rightVis;

    if (vis < LEG_RAISE_MIN_VISIBILITY) {
      this.announceStatus("No se te ven bien el hombro, la cadera, la rodilla y el tobillo. Ponte de perfil a la cámara, tumbado boca arriba, con las piernas enteras en el encuadre.");
      if (this.debugEl) this.debugEl.textContent = "buscando hombro, cadera, rodilla y tobillo de perfil…";
      this.legRaiseSide = null;
      this.groundStableSince = null;
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    if (!this.startupVoiceGiven) {
      this.startupVoiceGiven = true;
      this.announceStatus(
        "Te veo. ¡Listo! Túmbate boca arriba con las piernas estiradas y empieza cuando quieras. Para terminar una serie, levántate, sal del encuadre, o levanta un brazo y agita la mano.",
        "startup_ready"
      );
    }

    const shoulder = useLeft ? lShoulder : rShoulder;
    const hip = useLeft ? lHip : rHip;
    const knee = useLeft ? lKnee : rKnee;
    const ankle = useLeft ? lAnkle : rAnkle;
    const hipAngle = angle(shoulder, hip, ankle);
    const kneeAngle = angle(hip, knee, ankle);
    const tilt = tiltFromHorizontal(shoulder, hip);
    if (hipAngle === null || kneeAngle === null || tilt === null) return;

    this.legRaiseSide = useLeft ? "left" : "right";
    const onGround = tilt <= ON_GROUND_MAX_TILT_DEG;
    const legsStraight = kneeAngle >= LEG_RAISE_STRAIGHT_MIN_DEG;

    if (this.state === null) {
      if (onGround && legsStraight) {
        if (this.groundStableSince === null) this.groundStableSince = now;
        if (now - this.groundStableSince >= ON_GROUND_STABLE_MS) {
          this.state = "down";
          this.offGroundSince = null;
          this.announceStatus("¡Listo! Sube las piernas y vuelve a bajar.", "ready_to_go");
        } else {
          this.setStatus("Tumbado, piernas estiradas… confirmando (no te muevas)");
        }
      } else {
        this.groundStableSince = null;
        this.setStatus(
          !onGround ? "Túmbate boca arriba para empezar." : "Estira las piernas del todo, en el suelo, para empezar."
        );
      }
      if (this.debugEl) {
        this.debugEl.textContent =
          `tumbado: ${onGround ? "sí" : "no"} | piernas estiradas: ${legsStraight ? "sí" : "no"} (rodilla ${kneeAngle.toFixed(0)}°) | esperando a armar`;
      }
      return;
    }

    if (this.state === "down") {
      if (!onGround) {
        if (this.offGroundSince === null) this.offGroundSince = now;
        if (now - this.offGroundSince >= OFF_GROUND_STABLE_MS) {
          this.closeActiveSet();
          return;
        }
      } else {
        this.offGroundSince = null;
      }
    }

    if (this.state === "down") {
      if (hipAngle <= LEG_RAISE_UP_ANGLE_DEG) {
        this.state = "up";
        this.repStartTime = now;
      }
    } else if (hipAngle >= LEG_RAISE_DOWN_ANGLE_DEG) {
      this.countRep((now - this.repStartTime) / 1000, now, "Elevación");
      this.state = "down";
      // Consejo de forma, no cada vez (sería cansino) sino con el mismo
      // margen que cualquier otro aviso hablado (STATUS_VOICE_REPEAT_GAP_MS) —
      // ver LEG_RAISE_TOUCHDOWN_ANGLE_DEG. No afecta al conteo: la
      // repetición ya se ha contado justo arriba, esto es solo un aviso.
      if (hipAngle >= LEG_RAISE_TOUCHDOWN_ANGLE_DEG) {
        this.announceStatus("Consejo: intenta no tocar el suelo con los talones al bajar, para justo antes.", "tip_legraise_touchdown");
      }
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `ángulo cadera (${useLeft ? "izq" : "der"}): ${hipAngle.toFixed(0)}° | rodilla: ${kneeAngle.toFixed(0)}° | estado: ${this.state ?? "esperando"} ` +
        `(abajo ≥${LEG_RAISE_DOWN_ANGLE_DEG}°, arriba ≤${LEG_RAISE_UP_ANGLE_DEG}°)`;
    }
  }

  /**
   * Abdominal completo (situp): a diferencia del crunch (que solo
   * levanta cabeza y hombros), aquí sube el torso ENTERO hasta sentarte.
   * Se mide con la misma inclinación hombro-cadera respecto a la
   * horizontal que el gate de "tumbado" (ver tiltFromHorizontal) — de
   * tumbado (≤SITUP_DOWN_TILT_DEG) a sentado (≥SITUP_UP_TILT_DEG) — y a
   * propósito NO con un ángulo de cadera-rodilla como en la versión
   * anterior: ese dependía de dónde estuviera la rodilla, así que
   * alguien tumbado con las rodillas dobladas (lo normal, con los pies
   * apoyados) nunca llegaba al ángulo de "tumbado" y el contador iba a
   * su aire. La inclinación del torso no se entera de si la rodilla está
   * doblada, ni de si el cuello está levantado — ninguno de los dos
   * afecta a la cuenta.
   *
   * El gate de "tumbado y quieto" para armar/cerrar la serie es el mismo
   * que en crunch y elevación de piernas (ver processCrunch).
   */
  processSitup(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lHip = lm[L_HIP], rHip = lm[R_HIP];

    const leftVis = ((lShoulder.visibility ?? 1) + (lHip.visibility ?? 1)) / 2;
    const rightVis = ((rShoulder.visibility ?? 1) + (rHip.visibility ?? 1)) / 2;
    const useLeft = leftVis >= rightVis;
    const vis = useLeft ? leftVis : rightVis;

    if (vis < SITUP_MIN_VISIBILITY) {
      this.announceStatus("No se te ven bien el hombro y la cadera. Ponte de perfil a la cámara, tumbado boca arriba.");
      if (this.debugEl) this.debugEl.textContent = "buscando hombro y cadera de perfil…";
      this.groundStableSince = null;
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    if (!this.startupVoiceGiven) {
      this.startupVoiceGiven = true;
      this.announceStatus(
        "Te veo. ¡Listo! Túmbate boca arriba, con las rodillas dobladas si quieres, y empieza cuando quieras. Para terminar una serie, levántate, sal del encuadre, o levanta un brazo y agita la mano.",
        "startup_ready"
      );
    }

    const shoulder = useLeft ? lShoulder : rShoulder;
    const hip = useLeft ? lHip : rHip;
    const tilt = tiltFromHorizontal(shoulder, hip);
    if (tilt === null) return;
    const onGround = tilt <= ON_GROUND_MAX_TILT_DEG;

    if (this.state === null) {
      if (onGround) {
        if (this.groundStableSince === null) this.groundStableSince = now;
        if (now - this.groundStableSince >= ON_GROUND_STABLE_MS) {
          this.state = "down";
          this.offGroundSince = null;
          this.announceStatus("¡Listo! Sube hasta sentarte y vuelve a bajar.", "ready_to_go");
        } else {
          this.setStatus("Tumbado… confirmando (no te muevas)");
        }
      } else {
        this.groundStableSince = null;
        this.setStatus("Túmbate boca arriba del todo para empezar.");
      }
      if (this.debugEl) {
        this.debugEl.textContent = `inclinación torso: ${tilt.toFixed(0)}° | tumbado: ${onGround ? "sí" : "no"} | esperando a armar`;
      }
      return;
    }

    if (this.state === "down") {
      if (!onGround) {
        if (this.offGroundSince === null) this.offGroundSince = now;
        if (now - this.offGroundSince >= OFF_GROUND_STABLE_MS) {
          this.closeActiveSet();
          return;
        }
      } else {
        this.offGroundSince = null;
      }
    }

    if (this.state === "down") {
      if (tilt >= SITUP_UP_TILT_DEG) {
        this.state = "up";
        this.repStartTime = now;
      }
    } else if (tilt <= SITUP_DOWN_TILT_DEG) {
      this.countRep((now - this.repStartTime) / 1000, now, "Abdominal");
      this.state = "down";
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `inclinación torso: ${tilt.toFixed(0)}° | estado: ${this.state ?? "esperando"} ` +
        `(tumbado ≤${SITUP_DOWN_TILT_DEG}°, sentado ≥${SITUP_UP_TILT_DEG}°)`;
    }
  }

  /**
   * Guarda una línea en el registro de depuración de tijeretas (buffer
   * en memoria, sin mandar nada a ningún sitio) — pensado para poder
   * revisar luego, con el botón "Copiar registro" de la pantalla, qué
   * estaba viendo el contador justo en el momento de un fallo, sin tener
   * que leer el texto de depuración en directo (que queda ilegible si
   * estás tumbado lejos de la cámara). Se recorta a scissorLogMax líneas
   * (FIFO) para no crecer sin límite en una sesión larga.
   */
  logScissor(line) {
    this.scissorLog.push(`${((performance.now() - this.scissorLogStart) / 1000).toFixed(1)}s ${line}`);
    if (this.scissorLog.length > this.scissorLogMax) this.scissorLog.shift();
  }

  /**
   * Tijeretas: piernas estiradas, levantadas "a un palmo" del suelo, y
   * alternando cuál pierna queda más alta (como una tijera). Se cuenta
   * cada vez que cambia cuál tobillo está más arriba — no hay un ciclo
   * "abajo-arriba" como en el resto de abdominales tumbado, así que se
   * cuenta cada cambio de lado en vez de un ciclo completo.
   *
   * El gate de armado exige, además de estar tumbado (como el resto de
   * este bloque), tener las dos piernas YA levantadas dentro del rango
   * "a un palmo" (ver SCISSOR_LIFT_MIN/MAX_FACTOR) — esa es la postura
   * de partida del propio ejercicio, no solo "estar tumbado".
   */
  processScissor(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lHip = lm[L_HIP], rHip = lm[R_HIP];
    const lKnee = lm[L_KNEE], rKnee = lm[R_KNEE];
    const lAnkle = lm[L_ANKLE], rAnkle = lm[R_ANKLE];

    // A diferencia del resto de este bloque (que solo necesita ver bien
    // UN lado del cuerpo, el más cercano a la cámara), aquí hace falta
    // seguir los DOS tobillos para compararlos entre sí. Vistos de
    // perfil, un tobillo tapa parcialmente al otro sobre todo cuando
    // están a una altura parecida — que es justo lo que pasa todo el
    // rato en este ejercicio — así que MediaPipe le baja la confianza al
    // que queda detrás, aunque siga estimando su posición razonablemente
    // bien. Exigir visibilidad alta en los DOS tobillos A LA VEZ (como se
    // hacía antes, con el mínimo de los 8 puntos de ambos lados) casi
    // nunca se cumplía a la vez y el contador no llegaba ni a armarse —
    // por eso no contaba NINGUNA repetición, ni una. El gate de "te veo"
    // ahora solo mira el torso (hombros + cadera, del lado mejor visto —
    // igual que en crunch/elevación de piernas/abdominal); los tobillos
    // se usan tal cual los reporte MediaPipe, tenga la confianza que
    // tenga cada uno.
    const leftTrunkVis = ((lShoulder.visibility ?? 1) + (lHip.visibility ?? 1)) / 2;
    const rightTrunkVis = ((rShoulder.visibility ?? 1) + (rHip.visibility ?? 1)) / 2;
    const useLeft = leftTrunkVis >= rightTrunkVis;
    const trunkVis = useLeft ? leftTrunkVis : rightTrunkVis;

    if (trunkVis < SCISSOR_MIN_VISIBILITY) {
      this.announceStatus("No se te ve entera/o. Túmbate boca arriba, de perfil (de lado a la cámara), con el cuerpo entero en el encuadre.");
      if (this.debugEl) this.debugEl.textContent = "buscando el cuerpo entero en el encuadre…";
      this.groundStableSince = null;
      this.scissorSide = null;
      this.scissorCandidateSide = null;
      this.scissorCandidateSince = null;
      this.scissorSmoothA = null;
      this.scissorSmoothB = null;
      this.scissorRawPrevA = null;
      this.scissorRawPrevB = null;
      this.scissorTrackA = null;
      this.scissorTrackB = null;
      this.scissorSwitchCount = 0;
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    // Solo hace falta ver hombro, cadera y rodilla (para la referencia
    // del muslo) del lado mejor visto.
    const shoulder = useLeft ? lShoulder : rShoulder;
    const hip = useLeft ? lHip : rHip;
    const knee = useLeft ? lKnee : rKnee;
    const thighLength = Math.hypot(hip.x - knee.x, hip.y - knee.y) || 1;

    // La cadera se queda apoyada en el suelo durante todo el ejercicio y
    // sirve de referencia de altura "0" — se mide cuánto sube cada
    // TOBILLO por encima de esa referencia, en proporción al muslo.
    const groundY = (lHip.y + rHip.y) / 2;

    // === Seguir cada pierna por su POSICIÓN, no por la etiqueta
    // izquierda/derecha de MediaPipe ===
    // De perfil, cuando los dos pies están a una altura parecida (que es
    // todo el rato en este ejercicio, sobre todo justo en el cruce),
    // MediaPipe tiene que ADIVINAR en cada frame, desde cero y sin
    // memoria del frame anterior, cuál tobillo es el "izquierdo" y cuál
    // el "derecho" del cuerpo — una decisión anatómica ambigua vista de
    // lado. El modelo se equivoca y se corrige solo de un frame al
    // siguiente, haciendo que la etiqueta salte de un tobillo físico a
    // otro sin que hayas movido nada. Esto explica el síntoma que se
    // veía: el MISMO movimiento, repetido igual, contado unas veces 1,
    // otras 2, otras hasta 4 o 6 — no era ruido en la posición (eso ya
    // se filtraba), era la etiqueta izq/dcha cambiando de pierna a media
    // repetición.
    //
    // La solución: en vez de fiarnos de esa etiqueta, reconocemos cada
    // tobillo por CERCANÍA con el frame anterior (el que esté más cerca
    // de donde estaba esa pierna antes, se queda con esa identidad). Así
    // aunque MediaPipe cambie la etiqueta izq/dcha, la pierna que
    // rastreamos como "1" sigue siendo la misma pierna física de
    // principio a fin — el emparejamiento se decide comparando la suma
    // de distancias de las dos asignaciones posibles y quedándose con la
    // más corta.
    const p1 = { x: lAnkle.x, y: lAnkle.y };
    const p2 = { x: rAnkle.x, y: rAnkle.y };
    let trackA, trackB;
    if (this.scissorTrackA === null || this.scissorTrackB === null) {
      trackA = p1;
      trackB = p2;
    } else {
      const distKeep =
        Math.hypot(this.scissorTrackA.x - p1.x, this.scissorTrackA.y - p1.y) +
        Math.hypot(this.scissorTrackB.x - p2.x, this.scissorTrackB.y - p2.y);
      const distSwap =
        Math.hypot(this.scissorTrackA.x - p2.x, this.scissorTrackA.y - p2.y) +
        Math.hypot(this.scissorTrackB.x - p1.x, this.scissorTrackB.y - p1.y);
      if (distSwap < distKeep) {
        trackA = p2;
        trackB = p1;
      } else {
        trackA = p1;
        trackB = p2;
      }
    }
    this.scissorTrackA = trackA;
    this.scissorTrackB = trackB;

    let rawLiftA = (groundY - trackA.y) / thighLength;
    let rawLiftB = (groundY - trackB.y) / thighLength;

    // Recorta saltos de un frame al siguiente que ninguna pierna real
    // puede hacer (ver SCISSOR_MAX_LIFT_JUMP) — ANTES de la media móvil:
    // un salto así de grande, si se deja entrar aunque sea para
    // suavizarlo, puede arrastrar la media lo bastante como para
    // disparar un cambio de pierna que en realidad no ha pasado (un
    // registro real enseñó saltos de hasta varias veces la longitud del
    // muslo en una fracción de segundo — eso es un fallo de tracking
    // puntual, no la pierna moviéndose).
    if (this.scissorRawPrevA !== null) {
      const deltaA = rawLiftA - this.scissorRawPrevA;
      if (Math.abs(deltaA) > SCISSOR_MAX_LIFT_JUMP) {
        rawLiftA = this.scissorRawPrevA + Math.sign(deltaA) * SCISSOR_MAX_LIFT_JUMP;
      }
    }
    if (this.scissorRawPrevB !== null) {
      const deltaB = rawLiftB - this.scissorRawPrevB;
      if (Math.abs(deltaB) > SCISSOR_MAX_LIFT_JUMP) {
        rawLiftB = this.scissorRawPrevB + Math.sign(deltaB) * SCISSOR_MAX_LIFT_JUMP;
      }
    }
    this.scissorRawPrevA = rawLiftA;
    this.scissorRawPrevB = rawLiftB;

    // Suaviza la altura de cada pierna con una media móvil exponencial
    // (ver SCISSOR_SMOOTHING_ALPHA) antes de usarla para nada: el ruido
    // de un frame suelto —típico justo cuando un tobillo tapa al otro al
    // cruzarse— apenas mueve la media, así que todo lo de aquí en
    // adelante (armar el contador, los consejos, y sobre todo detectar
    // el cambio de pierna) trabaja con una lectura más limpia sin
    // necesitar un margen ni un tiempo de confirmación exagerados.
    if (this.scissorSmoothA === null) {
      this.scissorSmoothA = rawLiftA;
      this.scissorSmoothB = rawLiftB;
    } else {
      this.scissorSmoothA += SCISSOR_SMOOTHING_ALPHA * (rawLiftA - this.scissorSmoothA);
      this.scissorSmoothB += SCISSOR_SMOOTHING_ALPHA * (rawLiftB - this.scissorSmoothB);
    }
    const liftA = this.scissorSmoothA;
    const liftB = this.scissorSmoothB;
    const legsLifted =
      liftA >= SCISSOR_LIFT_MIN_FACTOR && liftA <= SCISSOR_LIFT_MAX_FACTOR &&
      liftB >= SCISSOR_LIFT_MIN_FACTOR && liftB <= SCISSOR_LIFT_MAX_FACTOR;

    if (!this.startupVoiceGiven) {
      this.startupVoiceGiven = true;
      this.announceStatus(
        "Te veo. Túmbate boca arriba, levanta los pies a un palmo del suelo y alterna las piernas, sin llegar a tocar el suelo ni subirlas de más. Para terminar una serie, baja las piernas y ponte de pie, sal del encuadre, o levanta un brazo y agita la mano.",
        "startup_ready"
      );
    }

    if (this.state === null) {
      if (legsLifted) {
        if (this.groundStableSince === null) this.groundStableSince = now;
        if (now - this.groundStableSince >= ON_GROUND_STABLE_MS) {
          this.state = "active";
          this.scissorSide = liftA >= liftB ? "1" : "2";
          this.scissorCandidateSide = null;
          this.scissorCandidateSince = null;
          this.scissorSwitchCount = 0;
          this.repStartTime = now;
          this.offGroundSince = null;
          this.announceStatus("¡Listo! Alterna las piernas.", "ready_to_go");
        } else {
          this.setStatus("Piernas a un palmo del suelo… confirmando (no te muevas)");
        }
      } else {
        this.groundStableSince = null;
        this.setStatus("Levanta los pies a un palmo del suelo, piernas estiradas, para empezar.");
      }
      if (this.debugEl) {
        this.debugEl.textContent = `piernas a la altura: ${legsLifted ? "sí" : "no"} | esperando a armar`;
      }
      this.logScissor(
        `[esperando armar] piernasAltura=${legsLifted ? "sí" : "no"} ` +
        `1=${liftA.toFixed(2)}(${rawLiftA.toFixed(2)}) 2=${liftB.toFixed(2)}(${rawLiftB.toFixed(2)})`
      );
      return;
    }

    // Cierre de serie por "te has parado": las dos piernas caídas cerca
    // del suelo un rato seguido. También se puede cerrar la serie
    // saliendo del encuadre o con el gesto de la mano (ver arriba).
    const bothLegsDown = liftA < SCISSOR_LIFT_MIN_FACTOR * 0.5 && liftB < SCISSOR_LIFT_MIN_FACTOR * 0.5;
    if (bothLegsDown) {
      if (this.offGroundSince === null) this.offGroundSince = now;
      if (now - this.offGroundSince >= OFF_GROUND_STABLE_MS) {
        this.closeActiveSet();
        return;
      }
    } else {
      this.offGroundSince = null;
    }

    // El consejo de forma (no tocar el suelo / no subir de más) ya se
    // dice una vez al empezar (ver startupVoiceGiven más arriba) — antes
    // se repetía por voz aquí mismo cada pocos segundos mientras haces
    // el ejercicio, y sonaba a media repetición, molestando. No afecta
    // al conteo, así que no hace falta más que decirlo una vez.

    // Justo cuando un pie pasa por encima/detrás del otro (el momento
    // exacto del cambio, y también si te quedas con los pies pegados o
    // montados uno sobre el otro) es cuando peor se distingue una pierna
    // de otra — ahí es fácil que la lectura salte de un lado a otro y
    // hacia atrás en un puñado de frames sin que hayas hecho un cambio
    // real, contando de más (varias reps por un solo cambio de pierna).
    // Por eso un cambio de lado no se cuenta al instante: hace falta que
    // la nueva pierna "de arriba" se mantenga así un ratito seguido
    // (SCISSOR_SWITCH_STABLE_MS) antes de darlo por bueno — el mismo
    // patrón de "candidato + tiempo seguido" que groundStableSince/
    // hangStableSince usan en el resto del fichero, aplicado aquí a cuál
    // pierna está arriba en vez de a una postura.
    //
    // Un registro real (con el seguimiento por cercanía ya puesto)
    // enseñó cambios de pierna limpios y bien separados — el problema
    // real no era ruido, era la definición de "repetición": cada cruce
    // de piernas (pierna 1 arriba → pierna 2 arriba) se estaba contando
    // como una repetición entera, así que un vaivén completo (pierna 1
    // arriba → pierna 2 arriba → pierna 1 arriba de nuevo, que es "una
    // tijereta") contaba 2. Encaja con lo que describías: el doble todo
    // el rato. Ahora una repetición es un vaivén COMPLETO — se cuenta
    // solo cuando la pierna que estaba arriba al principio del ejercicio
    // vuelve a estar arriba (cada dos cambios de pierna, no cada uno).
    let scissorRepCountedThisFrame = false;
    const diff = liftA - liftB;
    if (Math.abs(diff) >= SCISSOR_SWITCH_MARGIN_FACTOR) {
      const topLeg = diff > 0 ? "1" : "2";
      if (topLeg === this.scissorSide) {
        // Sigues con la misma pierna arriba: no hay cambio en marcha.
        this.scissorCandidateSide = null;
        this.scissorCandidateSince = null;
      } else if (topLeg === this.scissorCandidateSide) {
        // Llevas un rato dando la otra pierna por arriba: si ya ha
        // pasado suficiente tiempo seguido, se confirma el cambio.
        if (now - this.scissorCandidateSince >= SCISSOR_SWITCH_STABLE_MS) {
          this.scissorSwitchCount = (this.scissorSwitchCount ?? 0) + 1;
          if (this.scissorSwitchCount % 2 === 0) {
            const counted = this.countRep((now - this.repStartTime) / 1000, now, "Repetición");
            scissorRepCountedThisFrame = counted !== false;
            this.repStartTime = now;
          }
          this.scissorSide = topLeg;
          this.scissorCandidateSide = null;
          this.scissorCandidateSince = null;
        }
      } else {
        // Primera lectura de un posible cambio: empieza a contar el
        // tiempo, sin confirmar nada todavía.
        this.scissorCandidateSide = topLeg;
        this.scissorCandidateSince = now;
      }
    }

    this.logScissor(
      `1=${liftA.toFixed(2)}(${rawLiftA.toFixed(2)}) 2=${liftB.toFixed(2)}(${rawLiftB.toFixed(2)}) ` +
      `diff=${diff.toFixed(2)} pierna=${this.scissorSide ?? "-"} candidata=${this.scissorCandidateSide ?? "-"} cambios=${this.scissorSwitchCount ?? 0} reps=${this.currentSetReps}` +
      (scissorRepCountedThisFrame ? "  ←←← REP CONTADA AQUÍ" : "")
    );

    if (this.debugEl) {
      this.debugEl.textContent =
        `pierna 1: ${liftA.toFixed(2)} (bruto ${rawLiftA.toFixed(2)}) | pierna 2: ${liftB.toFixed(2)} (bruto ${rawLiftB.toFixed(2)}) | ` +
        `arriba: ${this.scissorSide ?? "-"}${this.scissorCandidateSide ? ` (candidata: ${this.scissorCandidateSide})` : ""} ` +
        `(rango ${SCISSOR_LIFT_MIN_FACTOR}-${SCISSOR_LIFT_MAX_FACTOR})`;
    }
  }

  /**
   * Doble crunch: el torso se mantiene LEVANTADO todo el rato (una
   * posición intermedia entre tumbado del todo y sentado del todo) —
   * mientras se doblan y estiran las piernas, llevando las rodillas al
   * pecho y volviendo a estirar, una y otra vez. Ver el bloque de
   * comentarios junto a DOUBLECRUNCH_TILT_MIN_DEG más arriba para el
   * porqué del rango de inclinación, y junto a DOUBLECRUNCH_TUCK_MAX_FACTOR
   * para el porqué de medir la distancia rodilla-hombro en vez de un
   * ángulo de cadera-rodilla.
   */
  processDoubleCrunch(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lHip = lm[L_HIP], rHip = lm[R_HIP];
    const lKnee = lm[L_KNEE], rKnee = lm[R_KNEE];

    const leftVis = ((lShoulder.visibility ?? 1) + (lHip.visibility ?? 1) + (lKnee.visibility ?? 1)) / 3;
    const rightVis = ((rShoulder.visibility ?? 1) + (rHip.visibility ?? 1) + (rKnee.visibility ?? 1)) / 3;
    const useLeft = leftVis >= rightVis;
    const vis = useLeft ? leftVis : rightVis;

    if (vis < DOUBLECRUNCH_MIN_VISIBILITY) {
      this.announceStatus("No se te ven bien el hombro, la cadera y la rodilla. Ponte de perfil a la cámara, tumbado boca arriba.");
      if (this.debugEl) this.debugEl.textContent = "buscando hombro, cadera y rodilla de perfil…";
      this.torsoBandStableSince = null;
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    const shoulder = useLeft ? lShoulder : rShoulder;
    const hip = useLeft ? lHip : rHip;
    const knee = useLeft ? lKnee : rKnee;
    const torsoLength = Math.hypot(shoulder.x - hip.x, shoulder.y - hip.y);
    if (!torsoLength) return;

    if (!this.startupVoiceGiven) {
      this.startupVoiceGiven = true;
      this.announceStatus(
        "Te veo. Levanta el torso y mantenlo ahí, doblando y estirando las piernas para llevar las rodillas al pecho. Para terminar una serie, túmbate del todo, ponte de pie, sal del encuadre, o levanta un brazo y agita la mano.",
        "startup_ready"
      );
    }

    const tilt = tiltFromHorizontal(hip, shoulder);
    if (tilt === null) return;
    const inBand = tilt >= DOUBLECRUNCH_TILT_MIN_DEG && tilt <= DOUBLECRUNCH_TILT_MAX_DEG;
    const kneeToShoulder = Math.hypot(knee.x - shoulder.x, knee.y - shoulder.y) / torsoLength;

    if (this.state === null) {
      if (inBand) {
        if (this.torsoBandStableSince === null) this.torsoBandStableSince = now;
        if (now - this.torsoBandStableSince >= ON_GROUND_STABLE_MS) {
          this.state = "extended";
          this.torsoOutOfBandSince = null;
          this.announceStatus("¡Listo! Lleva las rodillas al pecho y vuelve a estirar.", "ready_to_go");
        } else {
          this.setStatus("Torso levantado… confirmando (no te muevas)");
        }
      } else {
        this.torsoBandStableSince = null;
        this.setStatus("Levanta el torso hasta una posición intermedia y mantenla ahí para empezar.");
      }
      if (this.debugEl) {
        this.debugEl.textContent = `inclinación torso: ${tilt.toFixed(0)}° | en banda: ${inBand ? "sí" : "no"} | esperando a armar`;
      }
      return;
    }

    if (!inBand) {
      if (this.torsoOutOfBandSince === null) this.torsoOutOfBandSince = now;
      if (now - this.torsoOutOfBandSince >= OFF_GROUND_STABLE_MS) {
        this.closeActiveSet();
        return;
      }
    } else {
      this.torsoOutOfBandSince = null;
    }

    if (this.state === "extended") {
      if (kneeToShoulder <= DOUBLECRUNCH_TUCK_MAX_FACTOR) {
        this.state = "tucked";
        this.repStartTime = now;
      }
    } else if (kneeToShoulder >= DOUBLECRUNCH_EXTEND_MIN_FACTOR) {
      this.countRep((now - this.repStartTime) / 1000, now, "Crunch");
      this.state = "extended";
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `inclinación torso: ${tilt.toFixed(0)}° | rodilla-hombro: ${kneeToShoulder.toFixed(2)} | estado: ${this.state ?? "esperando"} ` +
        `(estirado ≥${DOUBLECRUNCH_EXTEND_MIN_FACTOR}, doblado ≤${DOUBLECRUNCH_TUCK_MAX_FACTOR})`;
    }
  }

  /**
   * Dominadas de arquero: mismo criterio de subida/bajada que las
   * dominadas normales (calibrar la altura de la barra colgado quieto y
   * seguir la nariz respecto a esa barra — ver el bloque para
   * counterKey "pullup" un poco más abajo en processResult), con un
   * añadido: en el punto más alto de cada repetición, un brazo tiene
   * que estar doblado a ~90° (el que tira) y el otro estirado (el que
   * se desliza por la barra) — ver ARCHER_BENT_MAX_DEG /
   * ARCHER_STRAIGHT_MIN_DEG y archerDetectSide().
   *
   * La repetición cuenta igual aunque no se distinga bien qué lado
   * usaste (cámara mal encuadrada, ángulo ambiguo, ambos brazos muy
   * parecidos): el aviso de lado es una ayuda de técnica para recordarte
   * que alternes, no un requisito para que la rep cuente.
   */
  processArcherPullup(lm, now) {
    const nose = lm[NOSE];
    const lShoulder = lm[L_SHOULDER];
    const rShoulder = lm[R_SHOULDER];
    const lElbow = lm[L_ELBOW];
    const rElbow = lm[R_ELBOW];
    const lWrist = lm[L_WRIST];
    const rWrist = lm[R_WRIST];
    const shoulderWidth = Math.hypot(lShoulder.x - rShoulder.x, lShoulder.y - rShoulder.y);
    const y = nose.y; // 0 = arriba del todo del encuadre, 1 = abajo del todo
    const wristMidY = (lWrist.y + rWrist.y) / 2;
    const elbowMidY = (lElbow.y + rElbow.y) / 2;
    const wristVisible = ((lWrist.visibility ?? 1) + (rWrist.visibility ?? 1)) / 2 > 0.4;
    const elbowVisible = ((lElbow.visibility ?? 1) + (rElbow.visibility ?? 1)) / 2 > 0.4;

    const shoulderMidYRaw = (lShoulder.y + rShoulder.y) / 2;
    const armsUpNow = wristVisible
      ? wristMidY < shoulderMidYRaw - HANG_MARGIN_FACTOR * shoulderWidth
      : elbowVisible && elbowMidY < shoulderMidYRaw - HANG_MARGIN_FACTOR * shoulderWidth;
    // Distinto de armsUpNow (ver RELEASE_MARGIN_FACTOR): solo esto cuenta
    // como "te has soltado de la barra de verdad" para cerrar la serie.
    const armsClearlyReleased = wristVisible
      ? wristMidY > shoulderMidYRaw + RELEASE_MARGIN_FACTOR * shoulderWidth
      : elbowVisible && elbowMidY > shoulderMidYRaw + RELEASE_MARGIN_FACTOR * shoulderWidth;

    if (this.prepping) {
      const waitedSeconds = Math.floor((now - this.prepStartTs) / 1000);
      if ((wristVisible || elbowVisible) && !this.startupVoiceGiven) {
        this.startupVoiceGiven = true;
        this.announceStatus("¡Listo! Cuélgate de la barra con los brazos estirados para empezar.", "startup_ready");
      }

      if (armsUpNow) {
        if (this.hangStableSince === null) this.hangStableSince = now;
        if (now - this.hangStableSince >= HANG_STABLE_MS) {
          this.prepping = false;
          this.calibrating = true;
          this.calibrationStartTs = now;
          this.calibrationSamples = [];
        } else {
          this.setStatus("Te veo colgado… confirmando (no te muevas)");
        }
      } else {
        this.hangStableSince = null;
        this.setStatus(
          waitedSeconds < 8
            ? "Ve a la barra y cuélgate con los brazos estirados…"
            : `Esperando a verte colgado (llevas ${waitedSeconds}s)… comprueba que la cámara vea tus brazos y hombros enteros`
        );
      }
      if (this.debugEl) {
        this.debugEl.textContent = `brazos en alto: ${armsUpNow ? "sí" : "no"} | espera: ${waitedSeconds}s`;
      }
      return;
    }

    if (this.calibrating) {
      if (!armsUpNow) {
        this.prepping = true;
        this.calibrating = false;
        this.hangStableSince = null;
        this.prepStartTs = now;
        this.calibrationSamples = [];
        return;
      }
      const barRefY = wristVisible ? wristMidY : elbowMidY;
      this.calibrationSamples.push({ y, shoulderWidth, barRefY });
      const elapsed = now - this.calibrationStartTs;
      const remaining = Math.max(0, Math.ceil((CALIBRATION_MS - elapsed) / 1000));
      this.setStatus(`Calibrando, quédate colgado y quieto… (${remaining || 1}s)`);
      if (elapsed >= CALIBRATION_MS) {
        const ys = this.calibrationSamples.map((s) => s.y).sort((a, b) => a - b);
        const ws = this.calibrationSamples.map((s) => s.shoulderWidth).sort((a, b) => a - b);
        const wy = this.calibrationSamples.map((s) => s.barRefY).sort((a, b) => a - b);
        this.shoulderWidth = ws[Math.floor(ws.length / 2)];
        this.localBottomY = ys[Math.floor(ys.length / 2)];
        this.localTopY = this.localBottomY;
        this.barY = wy[Math.floor(wy.length / 2)] - BAR_OFFSET_FACTOR * this.shoulderWidth;
        this.calibrating = false;
        this.repStartTime = now;
        this.lastRepTime = now;
        this.restAlerted = false;
        this.updateSetDisplay();
        this.logScissor(`[CALIBRADO] barra_y=${this.barY.toFixed(3)} hombros=${this.shoulderWidth.toFixed(3)}`);
        this.announceStatus(
          "¡Listo! Empieza a hacer dominadas de arquero: al subir, lleva un brazo a 90° y estira el otro, alternando de lado en cada repetición."
        );
      }
      return;
    }

    if (!this.shoulderWidth || this.barY === null) return;

    const scaleChange = Math.abs(shoulderWidth - this.shoulderWidth) / this.shoulderWidth;
    const scaleOk = scaleChange < SCALE_TOLERANCE;

    if (!armsUpNow || !scaleOk) {
      this.logScissor(
        `[frame descartado] brazos_arriba=${armsUpNow} escala_ok=${scaleOk} cambio_escala=${scaleChange.toFixed(2)}(máx ${SCALE_TOLERANCE}) ` +
        `estado=${this.state} reps_serie=${this.currentSetReps}`
      );
      this.localBottomY = null;
      this.localTopY = null;
      this.liftoffTime = null;
      this.archerPeakLeftAngle = null;
      this.archerPeakRightAngle = null;
      this.archerLiveLeftAngle = null;
      this.archerLiveRightAngle = null;

      if (armsClearlyReleased) {
        if (this.armsDownSince === null) this.armsDownSince = now;
        if (now - this.armsDownSince >= ARMS_DOWN_STABLE_MS && this.currentSetReps > 0) {
          const closedReps = this.currentSetReps;
          this.armsDownSince = null;
          // El aviso de descanso obligatorio SÍ tiene que oírse — por eso
          // va antes de silenciar la voz (restVoiceQuiet), no después.
          // setClosedAt lo marca beginPrep() justo debajo (currentSetReps
          // todavía es > 0 en este punto).
          this.announceSetComplete(`Serie de ${closedReps}`, "Cuélgate otra vez para empezar la siguiente.");
          this.restVoiceQuiet = true;
          this.beginPrep();
          return;
        }
      } else {
        // Zona ambigua (aguantando arriba) o solo falló el cambio de
        // escala: no cuenta como que te has soltado de verdad.
        this.armsDownSince = null;
      }

      if (this.debugEl) {
        this.debugEl.textContent = !armsUpNow
          ? "esperando a que agarres la barra (brazos en alto)…"
          : "distancia a la cámara cambió demasiado, recalibra si sigue así";
      }
      return;
    }

    this.armsDownSince = null;

    const moveThresh = MOVE_FACTOR * this.shoulderWidth;
    const barThresh = this.barY + BAR_MARGIN_FACTOR * this.shoulderWidth;

    // Ángulo de codo de cada brazo en ESTE frame (null si no se ven bien
    // codo/muñeca de ese lado — angle() no comprueba visibilidad por su
    // cuenta). Se usan para ir capturando el ángulo del frame con el
    // punto más alto durante la subida, ver más abajo.
    const leftAngle = elbowVisible && wristVisible ? angle(lShoulder, lElbow, lWrist) : null;
    const rightAngle = elbowVisible && wristVisible ? angle(rShoulder, rElbow, rWrist) : null;
    // Para el overlay (ver drawOverlay): el ángulo EN VIVO de este frame,
    // no el capturado en el pico — así el dibujo reacciona al instante
    // mientras te mueves, aunque lo que cuenta para decidir el lado siga
    // siendo solo el del punto más alto.
    this.archerLiveLeftAngle = leftAngle;
    this.archerLiveRightAngle = rightAngle;

    if (this.state === "down") {
      // sigue bajando (o igual) -> este es el nuevo punto de referencia "abajo",
      // y todavia no has "despegado" (reinicia la marca de despegue)
      if (this.localBottomY === null || y > this.localBottomY) {
        this.localBottomY = y;
        this.liftoffTime = null;
      }
      const risenFromBottom = this.localBottomY - y;

      // primer indicio de que te has empezado a mover de verdad
      if (this.liftoffTime === null && risenFromBottom > LIFTOFF_FACTOR * this.shoulderWidth) {
        this.liftoffTime = now;
      }

      const reachedBar = y <= barThresh;
      if (reachedBar && risenFromBottom > moveThresh) {
        this.state = "up";
        this.localTopY = y;
        this.repStartTime = this.liftoffTime ?? now;
        // Empieza a trackear el punto más alto de ESTA subida desde cero.
        this.archerPeakLeftAngle = leftAngle;
        this.archerPeakRightAngle = rightAngle;
      }
    } else {
      // state === "up": sigue subiendo (o igual) -> nuevo punto de referencia "arriba"
      if (this.localTopY === null || y < this.localTopY) {
        this.localTopY = y;
        // Nuevo punto más alto -> los ángulos de este frame son los que
        // se guardan como "postura arriba del todo": se sobrescriben
        // cada vez que subes un poco más, así el valor que queda al
        // final es el del pico real, no el de un frame cualquiera de la
        // subida (que era justo lo que se pidió: comprobar solo arriba
        // del todo).
        this.archerPeakLeftAngle = leftAngle;
        this.archerPeakRightAngle = rightAngle;
      }
      const fallenFromTop = y - this.localTopY;
      if (fallenFromTop > moveThresh) {
        // ha vuelto a bajar lo suficiente -> repetición completa
        const side = this.archerDetectSide(this.archerPeakLeftAngle, this.archerPeakRightAngle);
        this.logScissor(
          `[REP intentada] duración=${((now - this.repStartTime) / 1000).toFixed(2)}s lado=${side ?? "?"} ` +
          `pico_izq=${this.archerPeakLeftAngle === null ? "-" : this.archerPeakLeftAngle.toFixed(0) + "°"} ` +
          `pico_der=${this.archerPeakRightAngle === null ? "-" : this.archerPeakRightAngle.toFixed(0) + "°"}`
        );
        this.countRep((now - this.repStartTime) / 1000, now, "Dominada de arquero");
        if (side !== null) {
          if (this.archerLastSide !== null && this.archerLastSide === side) {
            this.announceStatus(
              `Llevas dos seguidas al lado ${side === "left" ? "izquierdo" : "derecho"} — alterna de lado.`,
              "archer_same_side"
            );
          }
          this.archerLastSide = side;
        }
        this.state = "down";
        this.localBottomY = y;
        this.archerPeakLeftAngle = null;
        this.archerPeakRightAngle = null;
      }
    }

    if (this.debugEl) {
      const fmt = (v) => (v === null ? "-" : `${v.toFixed(0)}°`);
      this.debugEl.textContent =
        `estado: ${this.state} | nariz-barra: ${((y - this.barY) / this.shoulderWidth).toFixed(2)} ` +
        `(umbral ${BAR_MARGIN_FACTOR}) | codo izq: ${fmt(leftAngle)} | codo der: ${fmt(rightAngle)} | último lado: ${this.archerLastSide ?? "-"}`;
    }
    this.logScissor(
      `estado=${this.state} nariz_y=${y.toFixed(3)} barra_y=${this.barY.toFixed(3)} dist_barra=${((y - this.barY) / this.shoulderWidth).toFixed(2)}(umbral ${BAR_MARGIN_FACTOR}) ` +
      `hombros=${this.shoulderWidth.toFixed(3)} abajo_ref=${this.localBottomY === null ? "-" : this.localBottomY.toFixed(3)} arriba_ref=${this.localTopY === null ? "-" : this.localTopY.toFixed(3)} ` +
      `despegue=${this.liftoffTime === null ? "no" : "sí"}`
    );
  }

  /**
   * A partir de los ángulos de codo capturados en el punto más alto de
   * la repetición, decide qué lado se usó (un brazo doblado ~90° y el
   * otro estirado) — o null si no se distingue con claridad (ambos
   * ángulos parecidos, o no se veían bien codo/muñeca de algún lado).
   * Ver ARCHER_BENT_MAX_DEG / ARCHER_STRAIGHT_MIN_DEG.
   */
  archerDetectSide(leftAngle, rightAngle) {
    if (leftAngle === null || rightAngle === null) return null;
    if (leftAngle <= ARCHER_BENT_MAX_DEG && rightAngle >= ARCHER_STRAIGHT_MIN_DEG) return "left";
    if (rightAngle <= ARCHER_BENT_MAX_DEG && leftAngle >= ARCHER_STRAIGHT_MIN_DEG) return "right";
    return null;
  }

  /**
   * Curl de bíceps con mancuernas: cámara DE PERFIL, igual que
   * flexiones/fondos/sentadillas — ver el bloque CURL_* más arriba
   * (SEGUNDA VERSIÓN, con el porqué del cambio desde la primera versión
   * de frente, que no contaba nada en cámara real). Se usa el lado
   * (izq/der) que mejor se vea, exactamente igual que processSquat/
   * processPushup: de perfil solo se ve bien un lado, el otro queda
   * tapado por el propio cuerpo.
   *
   * Se cuenta una repetición cuando el ÁNGULO DEL CODO (hombro-codo-
   * muñeca) completa el ciclo estirado (CURL_EXTENDED_ANGLE_DEG) →
   * doblado (CURL_FLEXED_ANGLE_DEG) → estirado — mismo patrón de dos
   * pasos que flexiones/fondos.
   *
   * Ver el bloque CURL_* más arriba para el porqué de "codo pegado al
   * costado" / "muñeca por debajo de la cara" — los dos falsos positivos
   * concretos que pidió Alex evitar (levantar las manos sin querer,
   * mirar el móvil) — y checkCameraShake para el tercero (el móvil
   * sujeto en la mano en vez de apoyado). Las tres comprobaciones se
   * hacen en TODOS los frames mientras la serie está armada, no solo al
   * principio: si se rompen, el frame se descarta ANTES de mirar el
   * ángulo de codo, así que un gesto suelto nunca puede colarse como
   * repetición aunque el ángulo por sí solo dibuje el ciclo completo.
   *
   * LIMITACIÓN CONOCIDA: MediaPipe Pose da hombro/codo/muñeca, no la
   * forma de la mano — no hay forma de comprobar literalmente si hay
   * algo agarrado (una mancuerna, el móvil, o nada). Lo de arriba es una
   * aproximación por la FORMA del movimiento, no reconocimiento de
   * objetos.
   */
  processDumbbellCurl(lm, now) {
    if (this.state !== null && this.checkWaveGesture(lm, now)) {
      this.closeActiveSet();
      return;
    }

    const nose = lm[NOSE];
    const lShoulder = lm[L_SHOULDER], rShoulder = lm[R_SHOULDER];
    const lElbow = lm[L_ELBOW], rElbow = lm[R_ELBOW];
    const lWrist = lm[L_WRIST], rWrist = lm[R_WRIST];
    const lHip = lm[L_HIP], rHip = lm[R_HIP];

    const leftVis = ((lShoulder.visibility ?? 1) + (lElbow.visibility ?? 1) + (lWrist.visibility ?? 1) + (lHip.visibility ?? 1)) / 4;
    const rightVis = ((rShoulder.visibility ?? 1) + (rElbow.visibility ?? 1) + (rWrist.visibility ?? 1) + (rHip.visibility ?? 1)) / 4;
    const useLeft = leftVis >= rightVis;
    const vis = useLeft ? leftVis : rightVis;

    if (vis < CURL_MIN_VISIBILITY) {
      this.announceStatus(
        "No se te ven bien el hombro, el codo, la muñeca y la cadera. Ponte de perfil a la cámara, de pie, " +
        "con la mancuerna en la mano del lado que mira a la cámara."
      );
      if (this.debugEl) this.debugEl.textContent = "buscando hombro, codo, muñeca y cadera de perfil…";
      this.logScissor(
        `[visibilidad baja] lado_elegido=${useLeft ? "izq" : "der"} vis=${vis.toFixed(2)} (mín ${CURL_MIN_VISIBILITY}) ` +
        `izq: hombro=${(lShoulder.visibility ?? 1).toFixed(2)} codo=${(lElbow.visibility ?? 1).toFixed(2)} muñeca=${(lWrist.visibility ?? 1).toFixed(2)} cadera=${(lHip.visibility ?? 1).toFixed(2)} total=${leftVis.toFixed(2)} | ` +
        `der: hombro=${(rShoulder.visibility ?? 1).toFixed(2)} codo=${(rElbow.visibility ?? 1).toFixed(2)} muñeca=${(rWrist.visibility ?? 1).toFixed(2)} cadera=${(rHip.visibility ?? 1).toFixed(2)} total=${rightVis.toFixed(2)} | ` +
        `estado=${this.state ?? "null"}`
      );
      this.curlSide = null;
      this.groundStableSince = null;
      if (this.state !== null) {
        if (this.offGroundSince === null) this.offGroundSince = now;
        if (now - this.offGroundSince >= CURL_BROKEN_STABLE_MS) {
          this.closeActiveSet();
          return;
        }
      }
      this.noteAbsence(now);
      return;
    }
    this.outOfFrameSince = null;

    const shoulder = useLeft ? lShoulder : rShoulder;
    const elbow = useLeft ? lElbow : rElbow;
    const wrist = useLeft ? lWrist : rWrist;
    const hip = useLeft ? lHip : rHip;

    const elbowAngle = angle(shoulder, elbow, wrist);
    if (elbowAngle === null) return;
    this.curlSide = useLeft ? "left" : "right";
    this.curlElbowAngle = elbowAngle;

    const torsoLength = Math.hypot(shoulder.x - hip.x, shoulder.y - hip.y);
    if (!torsoLength) return;
    // De perfil, el eje x de la imagen es el eje delante-atrás del
    // cuerpo: un codo pegado al costado no se adelanta ni se atrasa
    // respecto a la cadera. Ver el bloque CURL_* más arriba.
    const elbowDrift = Math.abs(elbow.x - hip.x) / torsoLength;
    // BUG REAL (encontrado con el registro de depuración que pegó Alex —
    // el contador nunca llegaba a armarse ni con el ángulo recorriendo
    // el ciclo completo de un curl real): elbowRise se comparaba antes
    // contra un umbral FIJO de codo-por-encima-de-la-cadera, pero
    // anatómicamente el codo YA está muy por encima de la cadera con el
    // brazo colgando en reposo (el codo cuelga a media altura del
    // tronco hombro-cadera, no a la altura de la cadera). En los datos
    // de Alex, con el brazo estirado en reposo (~175-180°), elbowRise
    // salía 0.4-0.6, muy por encima del 0.25 exigido, así que "pegado"
    // nunca daba true y no se podía ni armar. Arreglo: en vez de
    // comparar contra la cadera, se guarda la altura del codo en el
    // momento de armar (curlElbowBaselineY) y se mide cuánto SUBE el
    // codo respecto a ESA referencia — eso sí detecta el tramposeo real
    // (levantar todo el brazo por el hombro en vez de solo doblar el
    // antebrazo), y no se dispara con la postura de reposo normal.
    // Mientras no hay referencia todavía (antes de armar), esta
    // comprobación no bloquea nada.
    const elbowRise = this.curlElbowBaselineY !== null
      ? (this.curlElbowBaselineY - elbow.y) / torsoLength
      : 0;
    const risePinned = this.curlElbowBaselineY === null || elbowRise <= CURL_ELBOW_RISE_MAX_FACTOR;
    const wristDrop = (wrist.y - nose.y) / torsoLength;
    const pinned = elbowDrift <= CURL_ELBOW_DRIFT_MAX_FACTOR && risePinned;
    const belowFace = wristDrop >= CURL_WRIST_FACE_MARGIN_FACTOR;
    const shaking = this.checkCameraShake(shoulder, hip, torsoLength, now);
    const shapeOk = pinned && belowFace && !shaking;

    if (this.state !== null) {
      if (!shapeOk) {
        if (this.offGroundSince === null) this.offGroundSince = now;
        if (now - this.offGroundSince >= CURL_BROKEN_STABLE_MS) {
          this.closeActiveSet();
          return;
        }
        if (this.debugEl) {
          this.debugEl.textContent =
            `fuera de forma (codo pegado: ${pinned ? "sí" : "no"} · muñeca bajo la cara: ${belowFace ? "sí" : "no"} · ` +
            `cámara estable: ${shaking ? "no" : "sí"}) — se descarta este frame`;
        }
        this.logScissor(
          `[forma rota, se descarta frame] ángulo=${elbowAngle.toFixed(0)}° lado=${useLeft ? "izq" : "der"} ` +
          `codo_drift=${elbowDrift.toFixed(2)}(máx ${CURL_ELBOW_DRIFT_MAX_FACTOR}) codo_subido=${elbowRise.toFixed(2)}(máx ${CURL_ELBOW_RISE_MAX_FACTOR}) ` +
          `muñeca_bajo_cara=${wristDrop.toFixed(2)}(mín ${CURL_WRIST_FACE_MARGIN_FACTOR}) pegado=${pinned} bajo_cara=${belowFace} ` +
          `temblando=${shaking} estado=${this.state}`
        );
        return;
      }
      this.offGroundSince = null;
    }

    if (this.state === null) {
      // Referencia siempre fresca: mientras se espera para armar, no
      // hay tramposeo de "codo subido" que juzgar todavía (ver arriba).
      this.curlElbowBaselineY = null;
      const armReady = elbowAngle >= CURL_EXTENDED_ANGLE_DEG;
      if (shapeOk && armReady) {
        if (this.groundStableSince === null) this.groundStableSince = now;
        if (now - this.groundStableSince >= CURL_ARM_STABLE_MS) {
          this.state = "bottom";
          this.groundStableSince = null;
          this.offGroundSince = null;
          this.repStartTime = now;
          this.curlTopHoldSince = null;
          this.curlElbowBaselineY = elbow.y;
          this.logScissor(`[ARMADO] lado=${useLeft ? "izq" : "der"} ángulo=${elbowAngle.toFixed(0)}° codo_y_referencia=${elbow.y.toFixed(3)}`);
          if (!this.startupVoiceGiven) {
            this.startupVoiceGiven = true;
            this.announceStatus(
              "Te veo. ¡Listo! Empieza a hacer curls. Para terminar una serie, sal del encuadre o levanta un brazo y " +
              "agita la mano.",
              "startup_ready"
            );
          } else {
            this.announceStatus("¡Listo! Empieza a hacer curls.", "ready_to_go");
          }
        } else {
          this.setStatus("Postura vista… confirmando (no te muevas).");
        }
      } else {
        this.groundStableSince = null;
        this.setStatus(
          "Ponte de perfil a la cámara, de pie, con la mancuerna colgando, el brazo estirado y el codo pegado " +
          "al cuerpo, para empezar."
        );
      }
      if (this.debugEl) {
        this.debugEl.textContent = `ángulo codo (${useLeft ? "izq" : "der"}): ${elbowAngle.toFixed(0)}° | esperando posición inicial`;
      }
      this.logScissor(
        `[esperando armar] ángulo=${elbowAngle.toFixed(0)}° (mín ${CURL_EXTENDED_ANGLE_DEG} para armar) lado=${useLeft ? "izq" : "der"} ` +
        `forma_ok=${shapeOk} codo_drift=${elbowDrift.toFixed(2)}(máx ${CURL_ELBOW_DRIFT_MAX_FACTOR}) codo_subido=${elbowRise.toFixed(2)}(máx ${CURL_ELBOW_RISE_MAX_FACTOR}) ` +
        `muñeca_bajo_cara=${wristDrop.toFixed(2)}(mín ${CURL_WRIST_FACE_MARGIN_FACTOR}) pegado=${pinned} bajo_cara=${belowFace} temblando=${shaking} ` +
        `armado_desde=${this.groundStableSince === null ? "-" : ((now - this.groundStableSince) / 1000).toFixed(1) + "s"}`
      );
      return;
    }

    if (this.state === "bottom") {
      this.curlTopHoldSince = null;
      if (elbowAngle <= CURL_FLEXED_ANGLE_DEG) {
        this.state = "top";
        this.curlTopHoldSince = now;
        this.curlRestSince = null;
        this.logScissor(`[arriba del curl] ángulo=${elbowAngle.toFixed(0)}° (≤${CURL_FLEXED_ANGLE_DEG} para llegar arriba)`);
      } else if (elbowAngle >= CURL_EXTENDED_ANGLE_DEG) {
        // Brazo estirado del todo y sin doblar: podría ser que has
        // terminado la serie y estás descansando — ver
        // CURL_REST_AUTO_CLOSE_MS más arriba para el porqué.
        if (this.curlRestSince === null) this.curlRestSince = now;
        const restMs = now - this.curlRestSince;
        if (this.currentSetReps > 0 && restMs >= CURL_REST_AUTO_CLOSE_MS) {
          this.logScissor(
            `[serie cerrada por descanso] brazo estirado y quieto ${(restMs / 1000).toFixed(1)}s ` +
            `(≥${(CURL_REST_AUTO_CLOSE_MS / 1000).toFixed(1)}s) reps_serie=${this.currentSetReps}`
          );
          this.curlRestSince = null;
          this.closeActiveSet();
          return;
        }
        if (this.currentSetReps > 0 && restMs >= CURL_REST_WARN_MS) {
          const remaining = ((CURL_REST_AUTO_CLOSE_MS - restMs) / 1000).toFixed(1);
          this.setStatus(`Brazo abajo, quieto… si sigues así se cierra la serie sola en ${remaining}s.`);
        }
      } else {
        // Zona intermedia: se está moviendo (ni estirado del todo ni
        // doblado del todo), así que no cuenta como "quieto en reposo".
        this.curlRestSince = null;
      }
    } else {
      // state === "top": aguantando arriba, o volviendo a bajar.
      if (elbowAngle >= CURL_EXTENDED_ANGLE_DEG) {
        // El brazo ha vuelto a estirarse: repetición completa.
        this.logScissor(`[REP CONTADA] ángulo=${elbowAngle.toFixed(0)}° duración=${((now - this.repStartTime) / 1000).toFixed(2)}s`);
        this.countRep((now - this.repStartTime) / 1000, now, "Curl");
        this.state = "bottom";
        this.repStartTime = now;
        this.curlTopHoldSince = null;
        this.curlRestSince = null;
      } else if (this.curlTopHoldSince !== null && now - this.curlTopHoldSince >= CURL_TOP_HOLD_WARN_MS) {
        // Temporizador pedido por Alex: te has quedado arriba sin bajar
        // — no es un curl, es una sujeción aguantada. Ya NO se cuenta
        // como repetición (el ciclo de arriba solo cuenta al volver a
        // estirar el brazo), pero se avisa en pantalla de cuánto llevas
        // así para que quede claro que no se está contando nada
        // mientras tanto.
        const heldSeconds = ((now - this.curlTopHoldSince) / 1000).toFixed(1);
        this.setStatus(`Aguantando arriba: ${heldSeconds}s (no cuenta como repetición hasta que bajes del todo)`);
      }
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `ángulo codo (${useLeft ? "izq" : "der"}): ${elbowAngle.toFixed(0)}° | estado: ${this.state ?? "esperando"} ` +
        `(estirado ≥${CURL_EXTENDED_ANGLE_DEG}°, doblado ≤${CURL_FLEXED_ANGLE_DEG}°) | ` +
        `codo pegado: ${pinned ? "sí" : "no"} · muñeca bajo la cara: ${belowFace ? "sí" : "no"}`;
    }
  }


  /**
   * Detección de cámara temblando (el móvil sujeto en la mano en vez de
   * apoyado en algún sitio fijo) — ver el bloque CURL_CAMERA_SHAKE_* más
   * arriba. Se mide en el punto medio de los hombros porque no depende
   * de qué brazo está haciendo el curl: si TODO el cuerpo detectado
   * tiembla igual de un frame a otro, el problema es la cámara, no el
   * usuario.
   */
  checkCameraShake(shoulder, hip, torsoLength, now) {
    // BUG REAL (encontrado con los datos de Alex — 0 repeticiones
    // contadas incluso con el móvil totalmente quieto): esto se
    // normalizaba antes contra el ANCHO ENTRE HOMBROS (hombro izq vs.
    // hombro der), que funciona de frente pero se colapsa casi a CERO
    // de perfil (los dos hombros quedan casi superpuestos en la imagen,
    // uno detrás del otro) — al dividir por un número casi cero,
    // cualquier ruido normal de MediaPipe entre frame y frame (que
    // existe siempre, cámara quieta o no) se disparaba muy por encima
    // de CURL_CAMERA_SHAKE_FACTOR, así que "shaking" salía true casi
    // todos los frames y shapeOk nunca llegaba a true — el contador no
    // podía ni armarse. Arreglo: normalizar contra torsoLength (hombro-
    // cadera del MISMO lado, ya calculado en processDumbbellCurl), que
    // no se colapsa de perfil, y trackear el hombro del lado
    // seleccionado en vez del punto medio entre los dos hombros.
    let jitter = 0;
    if (this.curlShoulderMidPrev && torsoLength) {
      jitter = Math.hypot(shoulder.x - this.curlShoulderMidPrev.x, shoulder.y - this.curlShoulderMidPrev.y) / torsoLength;
    }
    this.curlShoulderMidPrev = { x: shoulder.x, y: shoulder.y };
    if (jitter >= CURL_CAMERA_SHAKE_FACTOR) {
      if (this.curlCameraShakeSince === null) this.curlCameraShakeSince = now;
    } else {
      this.curlCameraShakeSince = null;
    }
    return this.curlCameraShakeSince !== null && now - this.curlCameraShakeSince >= CURL_CAMERA_SHAKE_STABLE_MS;
  }

  processResult(result, now) {
    if (!result.landmarks || !result.landmarks.length) {
      if (this.debugEl) this.debugEl.textContent = "sin detección — ¿sales entero en el encuadre?";
      // Sentadillas y los abdominales tumbado no tienen su propio cierre
      // de serie (a diferencia de dominadas y fondos): sin esto, salir
      // del encuadre dejaba la serie abierta en silencio. Aquí también
      // sirve de "siguiente serie" sin moverte del suelo, para quien no
      // quiera levantarse entre series — basta con salir un momento del
      // encuadre y volver a entrar.
      if (GROUND_STYLE_COUNTERS.has(this.counterKey)) this.noteAbsence(now);
      // Plancha / plancha lateral: salir del encuadre también rompe la
      // postura, así que cierra el tramo aguantado por el mismo camino
      // que cualquier otra forma de romperla (ver notePostureBroken).
      if (CAMERA_POSTURE_COUNTERS.has(this.counterKey)) this.notePostureBroken(now, "No se te detecta en el encuadre.");
      return;
    }
    const lm = result.landmarks[0];

    // Cada ejercicio se detecta a su manera. Los fondos y las sentadillas
    // no necesitan calibrar ninguna barra, así que salen antes de todo eso.
    if (this.counterKey === "dip") {
      this.processDip(lm, now);
      return;
    }
    if (this.counterKey === "pushup") {
      this.processPushup(lm, now);
      return;
    }
    if (this.counterKey === "inclinepushup") {
      this.processInclinePushup(lm, now);
      return;
    }
    if (this.counterKey === "squat") {
      this.processSquat(lm, now);
      return;
    }
    if (this.counterKey === "crunch") {
      this.processCrunch(lm, now);
      return;
    }
    if (this.counterKey === "legraise") {
      this.processLegRaise(lm, now);
      return;
    }
    if (this.counterKey === "situp") {
      this.processSitup(lm, now);
      return;
    }
    if (this.counterKey === "scissor") {
      this.processScissor(lm, now);
      return;
    }
    if (this.counterKey === "doublecrunch") {
      this.processDoubleCrunch(lm, now);
      return;
    }
    if (this.counterKey === "archerpullup") {
      this.processArcherPullup(lm, now);
      return;
    }
    if (this.counterKey === "dumbbellcurl") {
      this.processDumbbellCurl(lm, now);
      return;
    }
    if (CAMERA_POSTURE_COUNTERS.has(this.counterKey)) {
      this.processPosture(lm, now);
      return;
    }

    const nose = lm[NOSE];
    const lShoulder = lm[L_SHOULDER];
    const rShoulder = lm[R_SHOULDER];
    const lElbow = lm[L_ELBOW];
    const rElbow = lm[R_ELBOW];
    const lWrist = lm[L_WRIST];
    const rWrist = lm[R_WRIST];
    const shoulderWidth = Math.hypot(lShoulder.x - rShoulder.x, lShoulder.y - rShoulder.y);
    const y = nose.y; // 0 = arriba del todo del encuadre, 1 = abajo del todo
    const wristMidY = (lWrist.y + rWrist.y) / 2;
    const elbowMidY = (lElbow.y + rElbow.y) / 2;
    const wristVisible = ((lWrist.visibility ?? 1) + (rWrist.visibility ?? 1)) / 2 > 0.4;
    const elbowVisible = ((lElbow.visibility ?? 1) + (rElbow.visibility ?? 1)) / 2 > 0.4;

    const shoulderMidYRaw = (lShoulder.y + rShoulder.y) / 2;
    // detección de "brazos en alto" usando la escala del frame actual
    // (para poder usarla ANTES de tener una calibración de referencia).
    // Si la muñeca se ve bien, manda ella sola (si la muñeca está claramente
    // abajo, un codo todavía algo elevado ya no debe contar como "colgado").
    // El codo solo se usa como reserva cuando no se ve bien la muñeca.
    const armsUpNow = wristVisible
      ? wristMidY < shoulderMidYRaw - HANG_MARGIN_FACTOR * shoulderWidth
      : elbowVisible && elbowMidY < shoulderMidYRaw - HANG_MARGIN_FACTOR * shoulderWidth;
    // Distinto de armsUpNow (ver RELEASE_MARGIN_FACTOR): solo esto cuenta
    // como "te has soltado de la barra de verdad" para cerrar la serie.
    const armsClearlyReleased = wristVisible
      ? wristMidY > shoulderMidYRaw + RELEASE_MARGIN_FACTOR * shoulderWidth
      : elbowVisible && elbowMidY > shoulderMidYRaw + RELEASE_MARGIN_FACTOR * shoulderWidth;

    if (this.prepping) {
      const waitedSeconds = Math.floor((now - this.prepStartTs) / 1000);
      // La primera vez en toda la sesión que se te ve lo bastante (muñeca
      // o codo visibles) para intentar detectarte, un aviso de que ya
      // puedes empezar — en las siguientes series no hace falta
      // repetirlo, ya sabes cómo colocarte.
      if ((wristVisible || elbowVisible) && !this.startupVoiceGiven) {
        this.startupVoiceGiven = true;
        this.announceStatus("¡Listo! Cuélgate de la barra con los brazos estirados para empezar.", "startup_ready");
      }

      if (armsUpNow) {
        if (this.hangStableSince === null) this.hangStableSince = now;
        if (now - this.hangStableSince >= HANG_STABLE_MS) {
          // Llevas ya un ratito con los brazos en alto de verdad -> calibra ya,
          // da igual si has tardado 3 segundos o 30 en llegar a la barra.
          this.prepping = false;
          this.calibrating = true;
          this.calibrationStartTs = now;
          this.calibrationSamples = [];
        } else {
          this.setStatus("Te veo colgado… confirmando (no te muevas)");
        }
      } else {
        this.hangStableSince = null;
        this.setStatus(
          waitedSeconds < 8
            ? "Ve a la barra y cuélgate con los brazos estirados…"
            : `Esperando a verte colgado (llevas ${waitedSeconds}s)… comprueba que la cámara vea tus brazos y hombros enteros`
        );
      }
      if (this.debugEl) {
        this.debugEl.textContent = `brazos en alto: ${armsUpNow ? "sí" : "no"} | espera: ${waitedSeconds}s`;
      }
      return;
    }

    if (this.calibrating) {
      // Si en medio de la calibración bajas los brazos (falsa alarma),
      // aborta y vuelve a esperar en vez de calibrar con datos malos.
      if (!armsUpNow) {
        this.prepping = true;
        this.calibrating = false;
        this.hangStableSince = null;
        this.prepStartTs = now;
        this.calibrationSamples = [];
        return;
      }
      // Para calibrar la altura de "la barra" usamos la muñeca si se ve
      // bien; si no, el codo (menos preciso, pero mucho más fiable que los
      // dedos, que MediaPipe no trackea bien cuando están curvados
      // agarrando algo — probado, y hacía que la barra quedara mal puesta).
      const barRefY = wristVisible ? wristMidY : elbowMidY;
      this.calibrationSamples.push({ y, shoulderWidth, barRefY });
      const elapsed = now - this.calibrationStartTs;
      const remaining = Math.max(0, Math.ceil((CALIBRATION_MS - elapsed) / 1000));
      this.setStatus(`Calibrando, quédate colgado y quieto… (${remaining || 1}s)`);
      if (elapsed >= CALIBRATION_MS) {
        const ys = this.calibrationSamples.map((s) => s.y).sort((a, b) => a - b);
        const ws = this.calibrationSamples.map((s) => s.shoulderWidth).sort((a, b) => a - b);
        const wy = this.calibrationSamples.map((s) => s.barRefY).sort((a, b) => a - b);
        this.shoulderWidth = ws[Math.floor(ws.length / 2)];
        this.localBottomY = ys[Math.floor(ys.length / 2)];
        this.localTopY = this.localBottomY;
        // altura de la barra = altura de tu muñeca al colgar, con un
        // empujón extra hacia arriba (BAR_OFFSET_FACTOR) para que la línea
        // cuadre mejor con la barra real (agarras por encima de la muñeca).
        // No hay forma de saber tu escala real en cm sin un objeto de
        // referencia, pero con un ancho de hombros típico (~35-40cm) un
        // factor de 0.05 equivale a ~2cm. Sube/baja el número si hace falta.
        this.barY = wy[Math.floor(wy.length / 2)] - BAR_OFFSET_FACTOR * this.shoulderWidth;
        this.calibrating = false;
        this.repStartTime = now;
        this.lastRepTime = now;
        this.restAlerted = false;
        this.updateSetDisplay();
        this.logScissor(`[CALIBRADO] barra_y=${this.barY.toFixed(3)} hombros=${this.shoulderWidth.toFixed(3)}`);
        this.announceStatus("¡Listo! Empieza a hacer dominadas.");
      }
      return;
    }

    if (!this.shoulderWidth || this.barY === null) return;

    const scaleChange = Math.abs(shoulderWidth - this.shoulderWidth) / this.shoulderWidth;
    const scaleOk = scaleChange < SCALE_TOLERANCE;

    if (!armsUpNow || !scaleOk) {
      // No pareces estar colgado de la barra (o te has acercado/alejado de
      // la cámara) — no cuentes nada de lo que pase ahora mismo, y cuando
      // vuelvas a agarrar la barra, empieza a medir desde cero otra vez.
      this.logScissor(
        `[frame descartado] brazos_arriba=${armsUpNow} escala_ok=${scaleOk} cambio_escala=${scaleChange.toFixed(2)}(máx ${SCALE_TOLERANCE}) ` +
        `estado=${this.state} reps_serie=${this.currentSetReps}`
      );
      this.localBottomY = null;
      this.localTopY = null;
      this.liftoffTime = null;

      if (armsClearlyReleased) {
        // Te has soltado de la barra de verdad (bajaste los brazos, no es
        // solo que te acercaras/alejaras de la cámara ni que estés
        // aguantando arriba a media dominada): esto es el final de la
        // serie en curso. Pero solo lo damos por bueno si se mantiene un
        // ratito seguido — un solo frame ruidoso (oclusión, ángulo raro
        // agarrando la barra) no debe cerrar la serie por error.
        if (this.armsDownSince === null) this.armsDownSince = now;
        if (now - this.armsDownSince >= ARMS_DOWN_STABLE_MS && this.currentSetReps > 0) {
          const closedReps = this.currentSetReps;
          this.armsDownSince = null;
          // El aviso de descanso obligatorio SÍ tiene que oírse — por eso
          // va antes de silenciar la voz (restVoiceQuiet), no después.
          // setClosedAt lo marca beginPrep() justo debajo (currentSetReps
          // todavía es > 0 en este punto).
          this.announceSetComplete(`Serie de ${closedReps}`, "Cuélgate otra vez para empezar la siguiente.");
          this.restVoiceQuiet = true;
          this.beginPrep();
          return;
        }
      } else {
        // Sin señal clara de que te hayas soltado (scaleOk falló con los
        // brazos arriba, o estás en la zona ambigua de "aguantando arriba":
        // ni armsUpNow ni armsClearlyReleased) — no cuenta como fin de
        // serie, reinicia el contador de "brazos abajo".
        this.armsDownSince = null;
      }

      if (this.debugEl) {
        this.debugEl.textContent = !armsUpNow
          ? "esperando a que agarres la barra (brazos en alto)…"
          : "distancia a la cámara cambió demasiado, recalibra si sigue así";
      }
      return;
    }

    this.armsDownSince = null;

    const moveThresh = MOVE_FACTOR * this.shoulderWidth;
    const barThresh = this.barY + BAR_MARGIN_FACTOR * this.shoulderWidth;

    if (this.state === "down") {
      // sigue bajando (o igual) -> este es el nuevo punto de referencia "abajo",
      // y todavia no has "despegado" (reinicia la marca de despegue)
      if (this.localBottomY === null || y > this.localBottomY) {
        this.localBottomY = y;
        this.liftoffTime = null;
      }
      const risenFromBottom = this.localBottomY - y;

      // primer indicio de que te has empezado a mover de verdad
      if (this.liftoffTime === null && risenFromBottom > LIFTOFF_FACTOR * this.shoulderWidth) {
        this.liftoffTime = now;
      }

      const reachedBar = y <= barThresh;
      if (reachedBar && risenFromBottom > moveThresh) {
        this.state = "up";
        this.localTopY = y;
        this.repStartTime = this.liftoffTime ?? now;
      }
    } else {
      // state === "up": sigue subiendo (o igual) -> nuevo punto de referencia "arriba"
      if (this.localTopY === null || y < this.localTopY) {
        this.localTopY = y;
      }
      const fallenFromTop = y - this.localTopY;
      if (fallenFromTop > moveThresh) {
        // ha vuelto a bajar lo suficiente -> repetición completa
        this.logScissor(`[REP intentada] duración=${((now - this.repStartTime) / 1000).toFixed(2)}s`);
        this.countRep((now - this.repStartTime) / 1000, now, "Dominada");
        this.state = "down";
        this.localBottomY = y;
      }
    }

    if (this.debugEl) {
      this.debugEl.textContent =
        `estado: ${this.state} | nariz-barra: ${((y - this.barY) / this.shoulderWidth).toFixed(2)} ` +
        `(umbral ${BAR_MARGIN_FACTOR}) | hombros: ${this.shoulderWidth.toFixed(3)}`;
    }
    this.logScissor(
      `estado=${this.state} nariz_y=${y.toFixed(3)} barra_y=${this.barY.toFixed(3)} dist_barra=${((y - this.barY) / this.shoulderWidth).toFixed(2)}(umbral ${BAR_MARGIN_FACTOR}) ` +
      `hombros=${this.shoulderWidth.toFixed(3)} abajo_ref=${this.localBottomY === null ? "-" : this.localBottomY.toFixed(3)} arriba_ref=${this.localTopY === null ? "-" : this.localTopY.toFixed(3)} ` +
      `despegue=${this.liftoffTime === null ? "no" : "sí"}`
    );
  }

  tickRestTimer() {
    // El cronómetro de sesión y el de descanso tienen que seguir corriendo
    // aunque estés en "prepping" (esperando a colgarte) o calibrando: es
    // justo el rato de descanso entre series, no hay motivo para congelarlos.
    if (!this.running || !this.sessionStart) return;
    const now = performance.now();
    this.timerEl.textContent = this.formatTime((now - this.sessionStart) / 1000);

    if (this.lastRepTime === null) return;
    const restSeconds = (now - this.lastRepTime) / 1000;
    this.restEl.textContent = this.formatTime(restSeconds);

    if (restSeconds >= REST_ALERT_SECONDS && !this.restAlerted) {
      this.restAlerted = true;
      this.restAlertsTriggered += 1;
      // Han pasado los 1:30 de descanso: a partir de aquí la voz ya
      // puede volver a hablar (este mismo aviso incluido).
      this.restVoiceQuiet = false;
      beep();
      this.announceStatus("⏰ ¡Descanso acabado! Volviendo a calibrar para la siguiente serie…");
      this.beginPrep();
    }
  }

  formatTime(totalSeconds) {
    const s = Math.max(0, Math.floor(totalSeconds));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, "0")}`;
  }

  stopCamera() {
    if (!this.running && !this.stream && !this.poseLandmarker) return; // ya estaba parada — nada que hacer
    this.running = false;
    if (this.restIntervalId) clearInterval(this.restIntervalId);
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.poseLandmarker) {
      try {
        this.poseLandmarker.close();
      } catch (e) {
        // Si ya estaba cerrado (llamar close() dos veces según la
        // versión de MediaPipe puede tirar), no es un fallo real — solo
        // asegúrate de no dejarlo a medias silenciosamente.
        console.warn("poseLandmarker.close() en una cámara ya parada:", e);
      }
      this.poseLandmarker = null;
    }
  }

  async finish() {
    const isPosture = CAMERA_POSTURE_COUNTERS.has(this.counterKey);
    if (isPosture) {
      if (this.totalHeldSeconds === 0 && this.currentHoldSeconds === 0 &&
          !confirm("No se ha registrado ningún tiempo aguantado. ¿Guardar la sesión igualmente?")) {
        return;
      }
    } else if (this.reps === 0 && !confirm("No se ha contado ninguna dominada. ¿Guardar la sesión igualmente?")) {
      return;
    }
    this.finishBtn.disabled = true;
    this.finishBtn.textContent = "Guardando…";

    // Cierra la serie que estuviera en curso (si tenía reps) antes de mandar los datos.
    if (this.currentSetReps > 0) {
      this.sets.push({ reps: this.currentSetReps, durations: [...this.currentSetDurations] });
      this.currentSetReps = 0;
      this.currentSetDurations = [];
    }
    // Plancha / plancha lateral: mismo cierre, pero para el tramo
    // aguantado en curso (ver _flushPostureHold).
    if (isPosture) this._flushPostureHold();

    const sessionDuration = this.sessionStart ? (performance.now() - this.sessionStart) / 1000 : 0;
    this.stopCamera();

    const payload = {
      total_reps: this.reps,
      rep_durations: this.repDurations,
      // Plancha / plancha lateral: el tiempo que cuenta es lo REALMENTE
      // aguantado (totalHeldSeconds, suma de cada tramo con la postura
      // correcta), no el reloj de pared de toda la sesión — si has
      // parado la cámara un rato entre tramos, ese hueco no cuenta.
      // achievement_pct (ver WorkoutSession.models) ya sabe comparar esto
      // contra target_seconds*target_sets sin ningún cambio en el backend.
      session_duration_seconds: isPosture ? Math.round(this.totalHeldSeconds) : Math.round(sessionDuration),
      rest_alerts_triggered: this.restAlertsTriggered,
      sets: this.sets,
      total_sets: this.sets.length,
    };

    // Cuando esto se reproduce dentro de la sesión de un plan
    // (plan-session.js), es esa pantalla la que decide qué hacer con el
    // resultado — anotarlo y pasar al siguiente ejercicio, no guardar y
    // salir. Suelto (task_workout.html), sigue el fetch de siempre.
    if (typeof window.__workoutSubmit === "function") {
      try {
        await window.__workoutSubmit(payload);
      } catch (err) {
        // Sin este catch, un fallo aquí dejaba el botón en "Guardando…"
        // para siempre sin ningún error visible — silencioso del todo.
        console.error("Error en __workoutSubmit:", err);
        alert("Algo ha fallado al pasar al siguiente ejercicio. Prueba a recargar la página (lo hecho hasta ahora no se ha guardado todavía).");
        this.finishBtn.disabled = false;
        this.finishBtn.textContent = "Terminar sesión";
      }
      return;
    }

    try {
      const resp = await fetch(this.saveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken"),
        },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (data.ok) {
        window.location.href = data.redirect_url;
      } else {
        alert("No se pudo guardar la sesión: " + (data.error || "error desconocido"));
        this.finishBtn.disabled = false;
        this.finishBtn.textContent = "Terminar sesión";
      }
    } catch (err) {
      console.error(err);
      alert("No se pudo guardar la sesión (sin conexión?). Los datos no se han perdido de la pantalla, prueba de nuevo.");
      this.finishBtn.disabled = false;
      this.finishBtn.textContent = "Terminar sesión";
    }
  }
}

/**
 * Arranca el contador sobre el #workout-root que haya en pantalla.
 * Exportado para que plan-session.js pueda llamarlo por cada ejercicio
 * de cámara de una sesión de plan, en vez de solo al cargar la página.
 */
export function startWorkout() {
  const root = el("workout-root");
  if (!root) return null;
  const session = new WorkoutSession(root);
  session.start();
  return session;
}

// Uso suelto (task_workout.html): arranca solo al cargar la página.
// Cuando lo importa plan-session.js, __LIBRETA_EMBEDDED__ está puesto y
// esto no hace nada — el arranque lo decide esa pantalla, ejercicio a
// ejercicio. Se comprueba document.readyState porque, al ser un script
// de tipo módulo, se ejecuta DESPUÉS de parsear el HTML — a veces antes
// de "DOMContentLoaded", a veces después. Esperar el evento a ciegas es
// una carrera que a veces se pierde y deja la cámara sin encender.
if (!window.__LIBRETA_EMBEDDED__) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startWorkout);
  } else {
    startWorkout();
  }
}
