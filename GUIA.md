# Cómo usar el Asistente TUP

Paso a paso para usar el asistente sin tocar la consola. Si en algún momento algo no
coincide con lo que ves, fijate en [Problemas frecuentes](#problemas-frecuentes), al final.

---

## Antes de empezar (una sola vez)

Necesitás tres cosas instaladas en tu computadora:

1. **Claude Code**, con la sesión iniciada. Si nunca lo abriste, abrilo una vez e iniciá
   sesión con tu cuenta. El asistente usa esa misma sesión, así que no te pide ninguna clave.
2. **Python** (versión 3.10 o más nueva). En Windows, al instalarlo marcá la casilla
   **«Add python.exe to PATH»**.
3. **La skill del campus** (`tup-campus-navigator`) configurada. Si ya la usabas desde la
   terminal, ya está. Si trabajás con otro campus además de TUP, lo sumás desde el propio
   asistente (ver «Trabajar con más de un campus», más abajo).

### Bajar e instalar el asistente

1. Entrá a **https://github.com/CinRigoniG/asistente-tup**.
2. Tocá el botón verde **Code** y después **Download ZIP**.
3. Descomprimí el ZIP en una carpeta que vayas a recordar, por ejemplo en *Documentos*.
4. Instalalo:
   - **Windows:** doble clic en **`Instalar.bat`**. Se abre una ventana negra que trabaja
     un par de minutos. Cuando diga *«Listo»*, cerrala.
   - **Mac y Linux:** no hace falta un paso aparte. La primera vez que lo abras (paso 1)
     se instala solo y tarda un par de minutos más.

Esto se hace una sola vez.

---

## 1. Abrir el asistente

- **Windows:** doble clic en **`Abrir asistente.bat`**.
- **Mac:** doble clic en **`Abrir asistente.command`**. La primera vez, Mac puede pedirte
  permiso: clic derecho sobre el archivo → **Abrir** → **Abrir**.
- **Linux:** `./abrir.sh`.

Se abre el navegador con el asistente. Si ya estaba abierto, sólo te muestra la pestaña.

> **Tip:** creá un acceso directo de `Abrir asistente` en el escritorio (clic derecho →
> *Enviar a* → *Escritorio*) para no tener que buscar la carpeta cada vez.

## 2. Elegir qué querés hacer

La pantalla de inicio agrupa todo por tema: **Mis acciones** (las que armás vos),
**Campus y comisiones**, **Rúbricas**, **Apuntes interactivos** y **Videos tutoriales**.
Cada renglón es una acción, con una línea que explica qué hace. Hacé clic en la que
necesites.

Arriba, junto a *Ayuda*, el botón **Campus** dice con qué campus estás trabajando. Ahí
mismo lo cambiás, agregás otro o elegís tus comisiones.

![Pantalla de inicio](docs/capturas/1-inicio.jpg)

Si una sección aparece gris, es porque a tu computadora le falta algo para usarla. El
aviso de arriba de la sección dice qué es.

## 3. Completar lo que te pide

Cada acción te pide sólo lo necesario. Arriba, en el recuadro **«Qué vas a obtener»**,
dice qué resultado vas a tener y si va a cambiar algo en el campus o no.

![Formulario de una acción](docs/capturas/2-formulario.jpg)

- **Materia, comisión y tarea** se eligen de una lista con *tus* materias y comisiones
  **del campus activo**. Primero elegí la materia; ahí se llenan las comisiones y tareas
  de esa materia. Si cambiás de campus, las listas cambian con él.
- Los campos que dicen **(opcional)** se pueden dejar vacíos. Por ejemplo, si no elegís
  comisión, revisa todas las tuyas.
- **Archivos** (una consigna, un apunte, una entrega): tocá **Elegir archivo** o
  arrastralo al recuadro. Esperá a que aparezca el ✓ con el nombre antes de seguir.

Cuando esté todo, tocá **Empezar**.

## 4. Mientras Claude trabaja

Vas a ver la lista de pasos que va haciendo, en castellano: *«Buscando entregas sin
corregir…»*, *«Armando el informe en PDF…»*. El paso que está en curso tiene un circulito
que gira y, si tarda, un contador de segundos.

- Algunas acciones tardan: el **panorama de todas las comisiones** puede llevar uno o dos
  minutos. Mientras el contador avance, está trabajando.
- **No cierres la pestaña** mientras trabaja: se corta lo que esté haciendo. Si igual
  querés salir, el asistente te avisa antes.
- Si querés ver exactamente qué se le pidió a Claude, abrí **«Lo que le pedí a Claude»**,
  debajo del título.

## 5. Cuando Claude necesita que decidas

A veces Claude necesita una decisión tuya. Por ejemplo, al revisar una consigna le puede
preguntar qué hacer con un requisito que la corrección con IA no puede evaluar. En ese
caso aparece una tarjeta con las opciones como botones:

![Claude pregunta con opciones](docs/capturas/3-pregunta.jpg)

1. Tocá la opción que prefieras. Cada una explica debajo qué implica.
2. Si ninguna te sirve, escribí la tuya en **«Otra respuesta»**.
3. Tocá **Responder**.

Si no querés contestar, tocá **Prefiero no contestar** y Claude sigue sin esa información.

## 6. Antes de escribir en el campus

**El asistente nunca escribe en el campus sin tu OK.** Cargar una nota, responder un
mensaje o publicar en un foro siempre se frena en una tarjeta roja como esta:

![Confirmación antes de cargar una nota](docs/capturas/4-confirmar.jpg)

- Revisá lo que va a escribir. **Podés corregirlo ahí mismo**: cambiar la nota, editar la
  devolución o el texto del mensaje.
- **Confirmar y escribir en el campus** lo carga tal como quedó en la tarjeta.
- **No, cancelar** no escribe nada. Claude se entera de que cancelaste y sigue desde ahí;
  si querés otra cosa, pedíselo en el cuadro de abajo cuando termine.

Una vez confirmado, no se puede deshacer desde el asistente. Si te equivocaste, hay que
corregirlo en el campus.

El rojo aparece **sólo** en estas tarjetas. Si ves rojo, es porque algo va a quedar
escrito en el campus.

## 7. El resultado y los archivos

Al terminar, Claude escribe un resumen de lo que hizo y lo que encontró. Si generó
archivos (un PDF, una rúbrica, un apunte), aparecen abajo con dos botones:

![Resultado con el archivo generado](docs/capturas/5-resultado.jpg)

- **Abrir:** abre el archivo con el programa que corresponda (el PDF en tu lector, el
  apunte en el navegador).
- **Mostrar en la carpeta:** abre la carpeta donde quedó el archivo.

Después de eso tenés tres caminos:

- **Seguir con la misma tarea:** escribí en el cuadro de abajo, por ejemplo *«ahora
  mostrame sólo los de la comisión 5»* o *«escribile un mensaje a los tres primeros»*.
  Claude se acuerda de lo que acaba de hacer.
- **Hacer lo mismo con otros datos:** vuelve al formulario de esa acción, vacío.
- **Terminar y volver al inicio.**

## 8. ¿Está todo listo?

Arriba a la derecha hay un indicador: **● Todo listo** (verde) o **Falta configurar
algo** (amarillo). Tocalo para ver qué revisa y qué hacer con lo que falta.

![Pantalla de estado](docs/capturas/6-estado.jpg)

Ahí también se eligen dos carpetas:

- **Carpeta de trabajo:** donde quedan los archivos que subís y lo que Claude produce
  (rúbricas en `TPs_rubrica`, apuntes en `Apuntes`…). Por omisión, *Documentos/Asistente TUP*.
- **Carpeta de informes:** los PDF del campus se copian acá al terminar cada tarea.

## 9. Cerrar el asistente

Tocá **Cerrar asistente** arriba a la derecha y después cerrá la pestaña. Si sólo cerrás
la pestaña, el asistente sigue abierto de fondo y la próxima vez abre más rápido. No
molesta, pero consume un poco de memoria.

---

## Qué hace cada acción

**Campus y comisiones**

| Acción | Qué obtenés | ¿Escribe en el campus? |
|---|---|---|
| ¿Qué me falta corregir? | Entregas sin nota por comisión y tarea, la más vieja primero | No |
| Alumnos que dejaron de entrar | Quién no abre la materia hace días | No |
| Mensajes y foros sin responder | Las consultas que siguen esperando | Sólo si pedís contestar, y con tu OK |
| Informe de seguimiento en PDF | Un PDF de tus comisiones | No |
| Panorama del curso | Todas las comisiones en una tabla (vista de profesor) | No |
| Corregir una entrega y cargar la nota | Ver la entrega, nota y devolución propuestas | Sí, con tu OK |
| Revisar cómo está armada el aula | Lo que falta o está roto en el aula | No |
| Otra consulta sobre el campus | Lo que escribas con tus palabras | Sólo con tu OK |

**Rúbricas para Active-IA:** revisar si una consigna se puede corregir con IA, armar una
rúbrica nueva, revisar una que ya existe y probarla con una entrega. Todo queda en
`TPs_rubrica/<nombre del trabajo>/`. La prueba es un ensayo: la nota simulada puede variar
2 o 3 puntos entre corridas.

**Apuntes interactivos:** subís un PDF, fotos o apuntes y obtenés una página para estudiar,
con ejercicios que se autocorrigen y un examen final. Queda en `Apuntes/`.

**Videos tutoriales:** grabar un tutorial donde el agente resuelve un proyecto y cambiar
la voz de videos ya editados. Necesita **ffmpeg** instalado (en Windows:
`winget install Gyan.FFmpeg`).

---

## Trabajar con más de un campus

Si tenés materias en más de un Moodle (por ejemplo TUP y otra sede), el asistente los
maneja por separado: cada campus tiene su dirección, sus credenciales y sus propias
materias y comisiones. **TUP viene por omisión.** Todo lo que hacés (las acciones, las
listas de materias y comisiones) se refiere al **campus activo**, que ves arriba en el
botón **Campus**. No hace falta elegirlo en cada acción.

Tocá **Campus** para:

- **Cambiar de campus:** «Usar este» en el que quieras. Rige desde la próxima tarea. No se
  puede cambiar mientras hay una tarea trabajando.
- **Agregar un campus,** en dos pasos:
  1. Completá el **nombre**, la **dirección** (la URL de ese Moodle), tu **usuario y
     contraseña** de ese campus y, si en Active-IA usás otro usuario para él, esos
     datos también (son opcionales). Tocá **Probar conexión**: se comprueba el ingreso
     antes de guardar nada.
  2. Elegí **cuáles son tus materias y comisiones** (ver abajo) y tocá **Guardar campus**.
     Queda como campus activo.
- **Definir tus comisiones:** **Mis materias y comisiones** en cualquiera de los campus.

### Tus materias y comisiones

Las acciones sólo van a mostrar las comisiones que vos elijas, así no ves las de otros
tutores. El asistente intenta reconocer las tuyas solo (las de los grupos de los que
sos miembro). Si no puede (por ejemplo, si sos docente con acceso a todo el curso y no
figurás en ninguna comisión), no marca nada y **lo elegís vos**: tildá las comisiones de
cada materia; con **Marcar todas** o **Ninguna** vas más rápido. Hace falta elegir al
menos una.

Lo que elegís se guarda **por campus**. Por ejemplo: en TUP, Programación II con las
comisiones 3 y 4; en otro campus, Programación 1 con la 3 y la 4, y Programación II con
la 5. Podés cambiarlo cuando quieras con **Mis materias y comisiones**; antes de
guardar, el asistente deja una copia del archivo anterior (`mis_datos.json.bak`).

Los datos de cada campus que agregás viven en tu carpeta de usuario
(`.asistente-tup/campus/`), sólo en tu computadora.

---

## Mis acciones: tus propios botones

Si hacés seguido una tarea que no está entre las acciones de fábrica, la podés dejar
como un botón propio. Aparece en la sección **Mis acciones**, con la etiqueta *Mía*, y
funciona igual que las demás: se abre el formulario, lo completás y Claude trabaja.

**Hay dos formas de crearla:**

1. **Crear mi propia acción** (arriba en *Mis acciones*). Contás en una frase qué querés
   y Claude te entrevista con opciones: qué tarea es, qué datos cambian cada vez
   (materia, comisión, un texto, un archivo, una opción de una lista) y qué tiene que
   entregar. Si se puede sin escribir en el campus, la prueba con vos una vez.
2. **Guardar como acción,** al pie de cualquier tarea que ya hiciste (por ejemplo, una
   *Otra consulta sobre el campus* que te gustó). Claude arma la acción a partir de lo
   que hicieron en la conversación y te pregunta lo que falte.

Antes de guardar, la pantalla te muestra cómo quedó: **nombre**, **descripción**, los
**datos que te va a pedir** y la **instrucción para Claude**. Podés corregir el nombre,
la descripción y la instrucción, y confirmar o cancelar.

**Después:** en cada acción propia tenés **Renombrar** (nombre y descripción) y
**Eliminar**. Las acciones quedan guardadas para tus próximas sesiones y valen en
cualquier campus. Están en tu carpeta de usuario (`.asistente-tup/acciones.json`).

> **Tip:** cuanto más concreta sea tu descripción, mejor queda el botón. Si al usarlo
> algo no sale como esperabas, hacé la tarea de nuevo con **Guardar como acción** o
> pedile a Claude que la ajuste y creá otra con un nombre distinto.

---

## Problemas frecuentes

**«No pude hablar con el asistente»**
El asistente se cerró. Volvé a abrirlo con *Abrir asistente*.

**«Claude Code no tiene la sesión iniciada» o «No encontré Claude Code»**
Abrí Claude Code una vez, iniciá sesión y volvé a intentar.

**No aparecen mis materias en la lista**
Fijate primero en el botón **Campus** (arriba): las listas son las del campus activo.
Si es el correcto, entrá a **Campus → Mis materias y comisiones** y tildá las tuyas. Si el
campus es TUP y nunca mapeaste tus comisiones, usá **Otra consulta sobre el campus** y
escribí *«mapeá mis comisiones»*.

**«Probar conexión» falla al agregar un campus**
Revisá la dirección (tiene que empezar con `https://`) y el usuario: en Moodle no siempre
es el DNI. No se guarda nada hasta que el ingreso funciona.

**Mi acción propia no aparece**
Aparece en **Mis acciones** cuando terminó la tarea en la que la guardaste. Si no la ves,
volvé al inicio; si cancelaste la tarjeta de confirmación, no se guardó.

**Una sección aparece gris**
Le falta algo a tu computadora. El aviso gris dice qué es. La pantalla *¿Está todo
listo?* tiene el detalle.

**El paso lleva mucho tiempo**
Si el contador de segundos sigue avanzando, está trabajando. Si pasan varios minutos
sin cambios, tocá *Terminar y volver al inicio* y probá de nuevo.

**Hay una versión nueva del asistente**
Volvé a bajar el ZIP y reemplazá los archivos de la carpeta. Tu configuración no se
pierde: vive en otra carpeta de tu usuario (`.asistente-tup`).

**Algo salió mal y quiero avisar**
Pasale a quien te ayuda el archivo `asistente.log`, que está en la carpeta
`.asistente-tup` de tu usuario.

---

## Lo que conviene saber

- **Corre en tu computadora.** Nadie más puede entrar a tu asistente: sólo responde a tu
  propio navegador.
- **Usa tu cuenta de Claude y tus credenciales del campus**, igual que si trabajaras
  desde la terminal.
- **Nada se escribe en el campus sin tu confirmación**, y lo que confirmás es exactamente
  lo que ves en la tarjeta roja.

---

## Novedades

**Trabajo con varios campus**
- Botón **Campus** en la barra: muestra el campus activo, permite cambiarlo y agregar otros.
- Alta de un campus nuevo con prueba de conexión: dirección, usuario y contraseña del
  Moodle y, opcionalmente, el usuario de Active-IA de ese campus.
- Cada campus guarda sus propias credenciales, materias, comisiones e informes, sólo en
  tu computadora. TUP sigue siendo el campus por omisión y no cambia nada para quien
  sólo usa TUP.
- La acción ya no pregunta el campus: se elige una vez arriba y todo se ajusta a él.

**Tus materias y comisiones, a medida**
- Al agregar un campus (y cuando quieras, con **Mis materias y comisiones**) elegís cuáles
  son tus comisiones; las acciones sólo muestran esas.
- Se reconocen solas las comisiones de los grupos de los que sos miembro; si no se puede,
  las elegís vos. Se reconocen nombres como `1pro3` o `Comision_6` además de los de TUP.
- Lo elegido se guarda por campus, con copia de seguridad del archivo anterior.

**Mis acciones**
- Creá tus propios botones: con **Crear mi propia acción** o con **Guardar como acción**
  al terminar cualquier tarea.
- Nombre, descripción y los datos que se piden cada vez, a tu gusto; Claude te hace las
  preguntas necesarias y vos confirmás antes de guardar.
- **Renombrar** y **Eliminar** desde el inicio; quedan guardadas para tus próximas sesiones.
