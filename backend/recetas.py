"""
El catálogo de lo que se puede hacer desde el asistente.

Cada receta es un formulario chico y un pedido armado para el agente. La persona
elige y completa; el texto que le llega a Claude lo escribe esta tabla, no ella.

Para sumar una acción nueva alcanza con agregar un dict a `RECETAS`:

- `campos`: lo que se le pide a la persona. Tipos: `curso`, `comision`, `tarea`
  (se llenan con las comisiones del tutor), `archivo`, `archivos`, `texto`,
  `parrafo`, `opcion`. El campus NO es un campo: se elige arriba, en la barra, y las
  materias/comisiones que se ofrecen son las del campus activo.
- `pedido`: el texto que recibe el agente. `{campo}` se reemplaza por lo que se
  cargó; si quedó vacío se usa su `vacio`, si lo tiene. Un bloque `[[ ... {campo} ... ]]`
  se omite entero si algún campo de adentro quedó vacío.
"""

from __future__ import annotations

import re

SKILLS = [
    {
        "id": "propias",
        "skill": None,  # no es una skill de Claude Code: siempre disponible
        "titulo": "Mis acciones",
        "bajada": "Tus propias tareas, armadas a tu gusto: quedan guardadas como un botón.",
    },
    {
        "id": "campus",
        "skill": "tup-campus-navigator",
        "titulo": "Campus y comisiones",
        "bajada": "Correcciones pendientes, alumnos que se alejan, mensajes, notas e informes del campus Moodle.",
    },
    {
        "id": "rubricas",
        "skill": "rubrica-builder",
        "titulo": "Rúbricas para Active-IA",
        "bajada": "Revisar una consigna, armar los criterios de corrección y probarlos antes de subirlos.",
    },
    {
        "id": "apuntes",
        "skill": "apunte-interactivo",
        "titulo": "Apuntes interactivos",
        "bajada": "Convertir un PDF, fotos o apuntes en una página para estudiar con ejercicios y examen.",
    },
    {
        "id": "videos",
        "skill": "tutorial-video-agente",
        "titulo": "Videos tutoriales",
        "bajada": "Grabar, narrar y publicar tutoriales donde el agente resuelve un proyecto.",
        # Los mismos programas que exige plataforma.py de la skill. En Windows graba con
        # gdigrab y tipea con SendInput (librería estándar): alcanza con ffmpeg.
        "requiere": {
            "todos": ["ffmpeg", "ffprobe"],
            "linux": ["xdotool", "wmctrl"],
            "como_instalar": "Windows: winget install Gyan.FFmpeg · Linux: sudo apt install ffmpeg xdotool wmctrl",
        },
    },
]

_CURSO = {"id": "curso", "tipo": "curso", "etiqueta": "Materia"}
_CURSO_OPC = {**_CURSO, "opcional": True, "vacio": "todas mis materias", "ayuda": "Si lo dejás vacío, revisa todas tus materias."}
_COMISION_OPC = {
    "id": "comision",
    "tipo": "comision",
    "etiqueta": "Comisión",
    "opcional": True,
    "ayuda": "Vacío = todas tus comisiones de esa materia.",
}

RECETAS = [
    # ------------------------------------------------------------ mis acciones
    {
        "id": "crear_accion",
        "skill": "propias",
        "titulo": "Crear mi propia acción",
        "bajada": "Contale a Claude qué tarea repetís y la deja guardada como un botón más, a tu gusto.",
        "resultado": "Una acción nueva en «Mis acciones». Antes de guardarla vas a ver cómo quedó y la confirmás.",
        "campos": [
            {"id": "idea", "tipo": "parrafo", "etiqueta": "¿Qué querés automatizar?", "opcional": True,
             "ayuda": "Una frase alcanza; Claude te va a hacer las preguntas que falten."},
        ],
        "pedido": (
            "Ayudame a crear una acción propia para este asistente: un botón nuevo que repite una tarea que hago seguido. "
            "[[La idea inicial es: {idea}. ]]\n\n"
            "Cómo hacerlo:\n"
            "1. Entrevistame con AskUserQuestion (opciones concretas, una o dos preguntas por vez) hasta entender: qué tarea es y "
            "con qué skill o herramienta se resuelve (campus Moodle, rúbricas, apuntes, etc.); qué datos cambian cada vez "
            "(materia, comisión, tarea, un texto, un archivo, una opción de una lista); qué tiene que entregar (una lista, un "
            "informe, un archivo, un mensaje) y si escribe algo en el campus (en ese caso siempre se confirma en pantalla).\n"
            "2. Si se puede sin escribir en el campus, probá la tarea conmigo una vez para comprobar que la instrucción funciona "
            "y ajustala con lo que aprendas.\n"
            "3. Proponeme un nombre corto y una descripción de una frase.\n"
            "4. Guardala con la herramienta guardar_accion. Reglas: `pedido` es la instrucción completa y autosuficiente, escrita "
            "para vos en segunda persona («Decime…», «Armá…»), con la skill a usar si corresponde («Usá la skill …») y con "
            "{id} en el lugar de cada dato que se pide; para un dato opcional usá un bloque [[ … {id} … ]], que se omite entero "
            "si el dato queda vacío. Tipos de dato: curso, comision y tarea (estos dos van después de un curso), texto, parrafo, "
            "archivo, archivos y opcion (con `opciones`). Cada dato lleva id (minúsculas, sin espacios), tipo, etiqueta y, si "
            "hace falta, opcional y ayuda. Lo que llega de curso, comision y tarea tiene la forma «Nombre (course_id 81)», "
            "«Nombre (group_id 12)» o «Nombre (assign_id 5)»: la instrucción puede pedirte usar esos números.\n"
            "5. La persona ve lo que proponés y lo confirma antes de que se guarde. Si pide cambios, ajustá y volvé a llamar."
        ),
    },
    # ------------------------------------------------------------------ campus
    {
        "id": "pendientes",
        "skill": "campus",
        "titulo": "¿Qué me falta corregir?",
        "bajada": "Las entregas esperando nota, por comisión y tarea, empezando por la que más espera.",
        "resultado": "Una lista ordenada de lo pendiente. No cambia nada en el campus.",
        "campos": [_CURSO_OPC],
        "pedido": (
            "Decime qué me falta corregir en {curso}. "
            "Agrupalo por comisión y tarea, y marcá cuántos días lleva esperando la entrega más vieja."
        ),
    },
    {
        "id": "inactivos",
        "skill": "campus",
        "titulo": "Alumnos que dejaron de entrar",
        "bajada": "Quién hace días que no abre la materia, para escribirle antes de que abandone.",
        "resultado": "Una lista de alumnos con los días sin entrar a la materia. No cambia nada en el campus.",
        "campos": [_CURSO, _COMISION_OPC],
        "pedido": (
            "Decime qué alumnos dejaron de entrar a la materia {curso}[[, comisión {comision}]]. "
            "Usá los días sin abrir ESTA materia (no el último acceso al campus en general) y separá "
            "los que nunca la abrieron de los que no se pudieron leer. Ordená del que más días lleva al que menos."
        ),
    },
    {
        "id": "mensajes",
        "skill": "campus",
        "titulo": "Mensajes y foros sin responder",
        "bajada": "Las consultas de alumnos que siguen esperando respuesta.",
        "resultado": "Un resumen de cada consulta pendiente. Si pedís contestar alguna, te muestro el texto antes de enviarlo.",
        "campos": [],
        "pedido": (
            "Revisá mis mensajes privados y los foros: ¿qué consultas de alumnos siguen sin respuesta? "
            "Para los mensajes usá un límite amplio (250) y mirá también las que el filtro descartó como cortesía, "
            "por si alguna es una consulta real. Resumí cada una en una línea y decime cuáles son urgentes."
        ),
    },
    {
        "id": "informe",
        "skill": "campus",
        "titulo": "Informe de seguimiento en PDF",
        "bajada": "Un PDF con el estado de tus comisiones, listo para mandar.",
        "resultado": "Un archivo PDF que vas a poder abrir desde acá mismo.",
        "campos": [_CURSO, _COMISION_OPC],
        "pedido": (
            "Armá el informe de seguimiento en PDF de la materia {curso}[[, comisión {comision}]]. "
            "Al terminar, decime dónde quedó el archivo."
        ),
    },
    {
        "id": "panorama",
        "skill": "campus",
        "titulo": "Panorama del curso (todas las comisiones)",
        "bajada": "La vista de profesor/coordinación: cómo viene cada comisión y quién tiene correcciones atrasadas.",
        "resultado": "Una tabla por comisión y, si querés, el PDF para coordinación. No cambia nada en el campus.",
        "campos": [_CURSO],
        "pedido": (
            "Dame el panorama de todas las comisiones de la materia {curso}: por comisión, qué falta corregir, "
            "hace cuántos días espera la entrega más vieja y qué consultas de foro nadie contestó. "
            "Hechos por comisión, sin rankings de tutores."
        ),
    },
    {
        "id": "corregir",
        "skill": "campus",
        "titulo": "Corregir una entrega y cargar la nota",
        "bajada": "Veo lo que entregó el alumno, te propongo nota y devolución, y la cargo sólo si aprobás.",
        "resultado": "Antes de escribir en el campus vas a ver la nota y la devolución, y podés corregirlas.",
        "campos": [
            _CURSO,
            {"id": "tarea", "tipo": "tarea", "etiqueta": "Tarea"},
            {"id": "alumno", "tipo": "texto", "etiqueta": "Alumno", "ayuda": "Nombre, apellido o DNI."},
            {
                "id": "criterio",
                "tipo": "parrafo",
                "etiqueta": "Qué querés que mire (opcional)",
                "opcional": True,
            },
        ],
        "pedido": (
            "En la materia {curso}, abrí la entrega de {alumno} para la tarea «{tarea}». Mostrame qué entregó, "
            "proponeme una nota y una devolución[[ teniendo en cuenta esto: {criterio}]], y cargala sólo si la confirmo."
        ),
    },
    {
        "id": "auditar_aula",
        "skill": "campus",
        "titulo": "Revisar cómo está armada el aula",
        "bajada": "Controla que no falten actividades, que los links funcionen y que todo sea consistente.",
        "resultado": "Un informe de lo que hay que arreglar. No cambia nada en el campus.",
        "campos": [_CURSO],
        "pedido": (
            "Auditá el aula virtual de la materia {curso} y decime qué hay que arreglar, ordenado por importancia."
        ),
    },
    {
        "id": "campus_libre",
        "skill": "campus",
        "titulo": "Otra consulta sobre el campus",
        "bajada": "Escribí con tus palabras lo que necesitás.",
        "resultado": "Si hace falta escribir algo en el campus, te lo muestro antes.",
        "campos": [{"id": "texto", "tipo": "parrafo", "etiqueta": "¿Qué necesitás?"}],
        "pedido": "{texto}",
    },
    # ---------------------------------------------------------------- rúbricas
    {
        "id": "curar",
        "skill": "rubricas",
        "titulo": "Revisar si una consigna se puede corregir con IA",
        "bajada": "Detecta lo que la IA no puede corregir (links, videos, capturas…) y propone cómo adaptarlo.",
        "resultado": "La consigna revisada, con cada cambio explicado. Las decisiones las tomás vos.",
        "campos": [
            {"id": "consigna", "tipo": "archivo", "etiqueta": "Consigna", "ayuda": "PDF, Word o texto.", "acepta": ".pdf,.docx,.doc,.md,.txt"},
            {"id": "nombre", "tipo": "texto", "etiqueta": "Nombre del trabajo", "ayuda": "Por ejemplo: TP 3 Prog 2."},
        ],
        "pedido": (
            "Modo CURAR. Revisá la consigna del archivo {consigna} ({nombre}) y detectá los requisitos que rompen "
            "la corrección con IA. Para cada uno, preguntame qué hacer con opciones. Guardá la consigna curada en "
            "la carpeta TPs_rubrica/{nombre}/."
        ),
    },
    {
        "id": "crear_rubrica",
        "skill": "rubricas",
        "titulo": "Armar una rúbrica nueva",
        "bajada": "A partir de la consigna, genera los criterios listos para el botón «Cargar criterios».",
        "resultado": "Un archivo JSON con los criterios, que suman 100.",
        "campos": [
            {"id": "consigna", "tipo": "archivo", "etiqueta": "Consigna", "acepta": ".pdf,.docx,.doc,.md,.txt"},
            {"id": "nombre", "tipo": "texto", "etiqueta": "Nombre del trabajo"},
            {"id": "notas", "tipo": "parrafo", "etiqueta": "Algo a tener en cuenta (opcional)", "opcional": True},
        ],
        "pedido": (
            "Modo CREAR. Armá la rúbrica para la consigna del archivo {consigna} ({nombre})[[. Tené en cuenta: {notas}]]. "
            "Guardá el JSON en TPs_rubrica/{nombre}/."
        ),
    },
    {
        "id": "auditar_rubrica",
        "skill": "rubricas",
        "titulo": "Revisar una rúbrica que ya existe",
        "bajada": "Busca contradicciones, requisitos que faltan o que se inventaron, y reajusta los pesos.",
        "resultado": "La rúbrica corregida y la lista de cambios con su porqué.",
        "campos": [
            {"id": "consigna", "tipo": "archivo", "etiqueta": "Consigna", "acepta": ".pdf,.docx,.doc,.md,.txt"},
            {"id": "rubrica", "tipo": "archivo", "etiqueta": "Rúbrica actual", "acepta": ".json,.txt,.md"},
            {"id": "nombre", "tipo": "texto", "etiqueta": "Nombre del trabajo"},
        ],
        "pedido": (
            "Modo AUDITAR. Consigna: {consigna}. Rúbrica actual: {rubrica}. ({nombre}). Corregila y explicame cada "
            "cambio. Guardá la versión corregida en TPs_rubrica/{nombre}/."
        ),
    },
    {
        "id": "probar_rubrica",
        "skill": "rubricas",
        "titulo": "Probar una rúbrica con una entrega",
        "bajada": "Simula la corrección real para ver qué nota y qué devolución daría, antes de subirla.",
        "resultado": "La nota simulada y el desglose por criterio. Es un ensayo: la nota puede variar 2 o 3 puntos.",
        "campos": [
            {"id": "rubrica", "tipo": "archivo", "etiqueta": "Rúbrica", "acepta": ".json,.txt,.md"},
            {"id": "entrega", "tipo": "archivo", "etiqueta": "Entrega de ejemplo", "ayuda": "ZIP, PDF o código."},
            {"id": "nombre", "tipo": "texto", "etiqueta": "Nombre del trabajo"},
        ],
        "pedido": (
            "Modo TEST. Probá la rúbrica {rubrica} con la entrega {entrega} ({nombre}) y mostrame la nota y el "
            "desglose por criterio. Guardá el resultado en TPs_rubrica/{nombre}/."
        ),
    },
    # ----------------------------------------------------------------- apuntes
    {
        "id": "apunte",
        "skill": "apuntes",
        "titulo": "Convertir un apunte en página de estudio",
        "bajada": "Resumen completo, simuladores, ejercicios que se autocorrigen y examen final.",
        "resultado": "Una página HTML que se abre en el navegador y se puede compartir.",
        "campos": [
            {"id": "material", "tipo": "archivos", "etiqueta": "Material", "ayuda": "PDF, fotos o documentos. Podés elegir varios.", "acepta": ".pdf,.png,.jpg,.jpeg,.docx,.md,.txt"},
            {"id": "tema", "tipo": "texto", "etiqueta": "Tema o materia (opcional)", "opcional": True},
            {"id": "enfasis", "tipo": "parrafo", "etiqueta": "¿Algo en especial? (opcional)", "opcional": True, "ayuda": "Por ejemplo: «para preparar el parcial», «más ejercicios de la unidad 3»."},
        ],
        "pedido": (
            "Convertí este material en un apunte interactivo: {material}.[[ Tema: {tema}.]][[ Tené en cuenta: {enfasis}.]] "
            "Guardá la página en la carpeta Apuntes/."
        ),
    },
    # ------------------------------------------------------------------ videos
    {
        "id": "grabar",
        "skill": "videos",
        "titulo": "Grabar un tutorial",
        "bajada": "El agente resuelve un proyecto en la terminal mientras se graba la pantalla.",
        "resultado": "Los videos editados por capítulo.",
        "campos": [{"id": "proyecto", "tipo": "parrafo", "etiqueta": "¿Qué proyecto tiene que resolver?"}],
        "pedido": "Grabá un tutorial donde el agente resuelve: {proyecto}",
    },
    {
        "id": "voz",
        "skill": "videos",
        "titulo": "Cambiar la voz de videos ya editados",
        "bajada": "Rehace la narración sin volver a grabar.",
        "resultado": "Los mismos videos con la voz nueva.",
        "campos": [
            {"id": "carpeta", "tipo": "texto", "etiqueta": "Carpeta de los videos"},
            {"id": "voz", "tipo": "opcion", "etiqueta": "Voz", "opciones": ["Piper (local, gratis)", "ElevenLabs", "Fish Audio"]},
        ],
        "pedido": "Cambiá la voz de los videos de {carpeta} usando {voz}.",
    },
]

_BLOQUE = re.compile(r"\[\[(.*?)\]\]", re.S)
_CAMPO = re.compile(r"\{(\w+)\}")


def armar_pedido(receta: dict, valores: dict[str, str]) -> str:
    vacios = {c["id"]: c["vacio"] for c in receta["campos"] if "vacio" in c}
    valores = {k: (v or "").strip() for k, v in valores.items()}

    def bloque(m: re.Match) -> str:
        dentro = m.group(1)
        if all(valores.get(n) for n in _CAMPO.findall(dentro)):
            return dentro
        return ""

    texto = _BLOQUE.sub(bloque, receta["pedido"])
    return _CAMPO.sub(lambda c: valores.get(c.group(1)) or vacios.get(c.group(1), ""), texto)


def faltantes(receta: dict, valores: dict[str, str]) -> list[str]:
    return [c["etiqueta"] for c in receta["campos"] if not c.get("opcional") and not (valores.get(c["id"]) or "").strip()]


def por_id(rid: str) -> dict | None:
    return next((r for r in RECETAS if r["id"] == rid), None)
