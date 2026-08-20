import json
import os
from urllib.parse import quote

from groq import Groq


# ============================================================
# CONFIGURACIÓN
# ============================================================

PREFERRED_MODELS = [
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
]

MAX_TUTORIALS = 10
MAX_RETRIES = 2


# ============================================================
# OBTENER MODELO DISPONIBLE
# ============================================================

def get_active_model(client):
    """
    Obtiene los modelos disponibles en Groq y selecciona
    uno de los modelos preferidos.
    """

    try:
        models_response = client.models.list()

        available_models = {
            model.id
            for model in models_response.data
        }

        print(
            f"[AI INFO] Se encontraron "
            f"{len(available_models)} modelos disponibles."
        )

        # ----------------------------------------------------
        # MODELOS PREFERIDOS
        # ----------------------------------------------------

        for model_name in PREFERRED_MODELS:

            if model_name in available_models:

                print(
                    f"[AI INFO] Modelo seleccionado: "
                    f"{model_name}"
                )

                return model_name

        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        excluded_keywords = (
            "whisper",
            "guard",
            "safety",
            "audio",
            "tts",
            "speech",
            "transcribe",
        )

        possible_models = []

        for model_id in available_models:

            model_lower = model_id.lower()

            if any(
                keyword in model_lower
                for keyword in excluded_keywords
            ):
                continue

            possible_models.append(model_id)

        if not possible_models:

            print(
                "[AI ERROR] No se encontró ningún "
                "modelo compatible."
            )

            return None

        possible_models.sort()

        selected = possible_models[0]

        print(
            "[AI WARNING] Ningún modelo preferido "
            "está disponible."
        )

        print(
            f"[AI INFO] Usando modelo alternativo: "
            f"{selected}"
        )

        return selected

    except Exception as e:

        print(
            f"[AI ERROR] Error obteniendo modelos "
            f"de Groq: {e}"
        )

        return None


# ============================================================
# URL YOUTUBE
# ============================================================

def create_youtube_search_url(component, action):
    """
    Genera una búsqueda de YouTube.
    La IA nunca genera directamente la URL.
    """

    query = (
        f"mantenimiento "
        f"{component} "
        f"{action}"
    )

    return (
        "https://www.youtube.com/results?search_query="
        + quote(query)
    )


# ============================================================
# LIMPIAR JSON
# ============================================================

def clean_json_response(content):
    """
    Limpia posibles bloques Markdown o texto adicional.
    """

    if not content:
        raise ValueError(
            "La respuesta del modelo está vacía."
        )

    content = content.strip()

    if content.startswith("```"):

        lines = content.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        content = "\n".join(lines).strip()

    if not content.startswith("{"):

        start = content.find("{")

        if start != -1:

            end = content.rfind("}")

            if end != -1:

                content = content[
                    start:end + 1
                ]

    return content.strip()


# ============================================================
# EXTRAER TUTORIALES
# ============================================================

def extract_tutorials(data):

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    tutorials = data.get("tutorials")

    if isinstance(tutorials, list):
        return tutorials

    for key in (
        "results",
        "data",
        "recommendations",
    ):

        value = data.get(key)

        if isinstance(value, list):
            return value

    if "component" in data:
        return [data]

    return []


# ============================================================
# VALIDAR TUTORIALES
# ============================================================

def validate_tutorials(data):

    tutorials = extract_tutorials(data)

    if not tutorials:

        print(
            "[AI WARNING] No se encontraron "
            "tutoriales válidos."
        )

        return []

    validated = []

    for item in tutorials:

        if not isinstance(item, dict):
            continue

        component = str(
            item.get(
                "component",
                "Alerta general"
            )
        ).strip()

        action = str(
            item.get(
                "action",
                "Realizar mantenimiento"
            )
        ).strip()

        # ----------------------------------------------------
        # PASOS
        # ----------------------------------------------------

        steps = item.get(
            "steps",
            []
        )

        if isinstance(steps, str):
            steps = [steps]

        if not isinstance(steps, list):
            steps = []

        cleaned_steps = []

        for step in steps:

            if step is None:
                continue

            step = str(step).strip()

            if step:
                cleaned_steps.append(step)

        # ----------------------------------------------------
        # INSUMOS
        # ----------------------------------------------------

        supplies = item.get(
            "supplies",
            []
        )

        if isinstance(supplies, str):
            supplies = [supplies]

        if not isinstance(supplies, list):
            supplies = []

        cleaned_supplies = []

        for supply in supplies:

            if supply is None:
                continue

            supply = str(supply).strip()

            if supply:
                cleaned_supplies.append(supply)

        # ----------------------------------------------------
        # RESULTADO
        # ----------------------------------------------------

        validated.append({

            "component": component,

            "action": action,

            "steps": cleaned_steps,

            "supplies": cleaned_supplies,

            "link": create_youtube_search_url(
                component,
                action
            )
        })

    return validated[:MAX_TUTORIALS]


# ============================================================
# SANITIZAR TELEMETRÍA
# ============================================================

def build_system_payload(
    telemetry_data,
    disk_data
):
    """
    Construye todos los datos disponibles para la IA.

    Es importante enviar la mayor cantidad de telemetría
    posible para que la IA pueda determinar si el sistema
    está realmente sano.
    """

    if not isinstance(
        telemetry_data,
        dict
    ):
        telemetry_data = {}

    if not isinstance(
        disk_data,
        list
    ):
        disk_data = []

    hardware = {

        "model": telemetry_data.get(
            "board_info",
            "Desconocido"
        ),

        "chassis": telemetry_data.get(
            "chassis_label",
            "Desconocido"
        ),

        "is_laptop": bool(
            telemetry_data.get(
                "is_laptop",
                False
            )
        ),

        "cpu": telemetry_data.get(
            "cpu_name",
            "Desconocido"
        ),

        "gpu": telemetry_data.get(
            "gpu_name",
            "Desconocido"
        ),
    }

    metrics = {

        "cpu_usage_percent": telemetry_data.get(
            "cpu_usage"
        ),

        "cpu_temperature_c": telemetry_data.get(
            "cpu_temp"
        ),

        "gpu_usage_percent": telemetry_data.get(
            "gpu_usage"
        ),

        "gpu_temperature_c": telemetry_data.get(
            "gpu_temp"
        ),

        "ram_usage_percent": telemetry_data.get(
            "ram_usage"
        ),

        "ram_used_gb": telemetry_data.get(
            "ram_used_gb"
        ),

        "ram_total_gb": telemetry_data.get(
            "ram_total_gb"
        ),
    }

    firmware = {

        "bios": telemetry_data.get(
            "bios_info",
            "Desconocido"
        )
    }

    payload = {

        "hardware": hardware,

        "metrics": metrics,

        "firmware": firmware,

        "disks": disk_data,
    }

    return payload


# ============================================================
# CREAR PROMPT
# ============================================================

def build_prompt(system_payload):

    telemetry_json = json.dumps(
        system_payload,
        indent=2,
        ensure_ascii=False
    )

    return f"""
Eres el motor de diagnóstico de hardware de CorePulse.

Tu trabajo NO es generar una lista genérica de mantenimiento.

Debes analizar la telemetría REAL del computador y determinar
si existe algún problema que justifique una recomendación.

DATOS REALES DEL EQUIPO:

{telemetry_json}


============================================================
REGLA PRINCIPAL
============================================================

NO inventes problemas.

Si los datos indican que el computador está funcionando
correctamente, debes devolver una lista VACÍA:

{{
  "tutorials": []
}}

Esto es MUY IMPORTANTE.

Por ejemplo, si:

- CPU tiene temperatura normal.
- GPU tiene temperatura normal.
- RAM tiene un uso razonable.
- Los discos tienen buena salud.
- Los discos tienen suficiente espacio libre.
- No existen indicadores anormales.

Entonces NO debes recomendar limpieza, cambio de pasta térmica,
ampliación de RAM, limpieza de SSD, cambio de disco ni otras
acciones innecesarias.

En ese caso:

{{
  "tutorials": []
}}


============================================================
CRITERIOS ORIENTATIVOS
============================================================

Utiliza criterio técnico, no valores rígidos ciegamente.

CPU:

- Temperaturas sostenidas normales no requieren mantenimiento.
- Una temperatura elevada de forma consistente puede justificar
  revisar refrigeración.
- No diagnostiques un problema únicamente por un pico aislado.

GPU:

- Temperaturas normales no requieren mantenimiento.
- Temperaturas persistentemente elevadas pueden justificar
  revisar refrigeración.

RAM:

- Un uso normal de RAM no requiere ampliación.
- Un uso persistentemente muy elevado puede justificar revisar
  procesos o capacidad.

ALMACENAMIENTO:

- Buena salud S.M.A.R.T. significa que no debes recomendar
  reemplazar la unidad.
- Espacio libre suficiente significa que no debes recomendar
  liberar espacio.
- Una unidad con salud claramente deteriorada sí puede requerir
  copia de seguridad y reemplazo.
- Un disco casi lleno puede justificar liberar espacio.

IMPORTANTE:

No conviertas una recomendación preventiva genérica en una
"alerta".

Si todo está correcto, el resultado debe ser vacío.


============================================================
OBJETIVO DEL PDF
============================================================

CorePulse utilizará tu respuesta para generar un informe.

Si el análisis es satisfactorio, el PDF mostrará:

"ANÁLISIS SUPERADO"

y un mensaje de felicitaciones.

Por lo tanto, NO generes un tutorial artificial solamente para
evitar una lista vacía.


============================================================
SI EXISTE UN PROBLEMA REAL
============================================================

Solo entonces genera tutoriales.

Cada tutorial debe:

- Corresponder directamente a un dato anormal.
- Explicar qué debe hacerse.
- Tener pasos concretos.
- Tener únicamente los insumos realmente necesarios.
- Ser seguro para un usuario normal.
- Adaptarse a portátil o escritorio.
- No recomendar desmontajes innecesarios.
- No inventar componentes.
- No inventar temperaturas.
- No inventar problemas.


============================================================
FORMATO OBLIGATORIO
============================================================

Devuelve EXCLUSIVAMENTE JSON válido.

Formato:

{{
  "tutorials": [
    {{
      "component": "CPU",
      "action": "Revisar sistema de refrigeración",
      "steps": [
        "Apagar completamente el equipo.",
        "Desconectar la alimentación.",
        "Comprobar que las rejillas y ventiladores estén libres de polvo."
      ],
      "supplies": [
        "Aire comprimido",
        "Paño de microfibra"
      ]
    }}
  ]
}}

Si no existen problemas:

{{
  "tutorials": []
}}


============================================================
REGLAS DEL JSON
============================================================

- "tutorials" siempre debe existir.
- "tutorials" siempre debe ser una lista.
- Cada tutorial debe tener:
  "component",
  "action",
  "steps",
  "supplies".
- "steps" siempre es una lista.
- "supplies" siempre es una lista.
- No incluyas URLs.
- No incluyas Markdown.
- No incluyas explicaciones fuera del JSON.
- No incluyas razonamiento.
- No inventes información.
- Máximo {MAX_TUTORIALS} tutoriales.
"""


# ============================================================
# PETICIÓN A GROQ
# ============================================================

def request_json(
    client,
    model,
    prompt
):

    response = client.chat.completions.create(

        model=model,

        messages=[

            {
                "role": "system",
                "content": (
                    "Eres un sistema de diagnóstico "
                    "de hardware. "
                    "Responde exclusivamente con "
                    "un objeto JSON válido."
                )
            },

            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.15,

        reasoning_format="hidden",

        reasoning_effort="none",

        response_format={
            "type": "json_object"
        }
    )

    if not response.choices:

        raise ValueError(
            "Groq no devolvió choices."
        )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:

        raise ValueError(
            "Groq devolvió contenido vacío."
        )

    return clean_json_response(
        content
    )


# ============================================================
# GENERAR TUTORIAL CON IA
# ============================================================

def generate_ai_tutorial(
    telemetry_data,
    disk_data
):
    """
    Analiza la telemetría mediante Groq.

    IMPORTANTE:
    Una lista vacía es un resultado válido.
    Significa que la IA determinó que no existen problemas
    que requieran una acción.
    """

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:

        print(
            "[AI ERROR] No existe GROQ_API_KEY."
        )

        return []

    try:

        client = Groq(
            api_key=api_key
        )

        active_model = get_active_model(
            client
        )

        if not active_model:

            print(
                "[AI ERROR] No hay un modelo disponible."
            )

            return []

        system_payload = build_system_payload(
            telemetry_data,
            disk_data
        )

        prompt = build_prompt(
            system_payload
        )

        print(
            f"[AI INFO] Analizando telemetría "
            f"con {active_model}..."
        )

        last_error = None

        for attempt in range(
            1,
            MAX_RETRIES + 2
        ):

            try:

                print(
                    f"[AI INFO] Intento "
                    f"{attempt}/"
                    f"{MAX_RETRIES + 1}"
                )

                content = request_json(
                    client,
                    active_model,
                    prompt
                )

                try:

                    parsed_data = json.loads(
                        content
                    )

                except json.JSONDecodeError as e:

                    last_error = e

                    print(
                        "[AI WARNING] JSON inválido."
                    )

                    continue

                tutorials = validate_tutorials(
                    parsed_data
                )

                print(
                    f"[AI INFO] Diagnóstico IA: "
                    f"{len(tutorials)} "
                    f"recomendaciones."
                )

                return tutorials

            except Exception as e:

                last_error = e

                print(
                    f"[AI WARNING] Intento "
                    f"{attempt} falló: {e}"
                )

                if attempt <= MAX_RETRIES:

                    prompt += """

RECUERDA:

Devuelve exclusivamente JSON válido.

Si el equipo está en buenas condiciones,
devuelve:

{"tutorials":[]}

No inventes problemas.
"""

        print(
            "[AI ERROR] No fue posible obtener "
            "un diagnóstico válido."
        )

        if last_error:

            print(
                f"[AI ERROR] Último error: "
                f"{last_error}"
            )

        return []

    except Exception as e:

        print(
            f"[AI ERROR] Fallo crítico: {e}"
        )

        return []


# ============================================================
# PRUEBA DIRECTA
# ============================================================

if __name__ == "__main__":

    telemetry_example = {

        "board_info":
            "ASUS TUF Gaming",

        "chassis_label":
            "Notebook",

        "cpu_name":
            "AMD Ryzen",

        "gpu_name":
            "NVIDIA GeForce",

        "is_laptop":
            True,

        "cpu_temp":
            55,

        "cpu_usage":
            35,

        "gpu_temp":
            50,

        "gpu_usage":
            20,

        "ram_usage":
            45,

        "ram_used_gb":
            7.2,

        "ram_total_gb":
            16,

        "bios_info":
            "1.0"
    }

    disk_example = [

        {
            "index": 0,
            "model": "SSD NVMe",
            "mount_points": "C:",
            "health": 100,
            "used_gb": 300,
            "total_gb": 1000,
            "used_percent": 30
        }
    ]

    result = generate_ai_tutorial(
        telemetry_example,
        disk_example
    )

    print()
    print("=" * 60)
    print("RESULTADO")
    print("=" * 60)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )
