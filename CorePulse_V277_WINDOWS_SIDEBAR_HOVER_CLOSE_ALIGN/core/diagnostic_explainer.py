"""Convierte hallazgos técnicos del diagnóstico en explicaciones comprensibles para el usuario."""
from __future__ import annotations
# Código refactorizado: nombres estables y documentación en español.
import copy

def _ev(alert):
    return [str(x) for x in alert.get('evidence') or [] if x is not None]

class DiagnosticExplainer:

    def explain_alert(self, alert):
        key = alert.get('key', '')
        out = {'key': key, 'component': alert.get('component', 'SYSTEM'), 'level': alert.get('level', 'INFO'), 'context': alert.get('context', 'UNKNOWN'), 'title': alert.get('title', ''), 'summary': alert.get('detail', ''), 'evidence': _ev(alert), 'why': '', 'checks': [], 'notes': []}
        if key == 'cpu_tjmax_critical':
            out['why'] = 'La CPU estuvo extremadamente cerca de TjMax durante una proporción alta de muestras y el TjMax inferido se mantuvo consistente entre lecturas.'
            out['checks'] = ['Revisar entradas y salidas de aire.', 'Comprobar respuesta de ventiladores bajo carga.', 'Revisar perfil de energía/rendimiento.', 'Si persiste, evaluar mantenimiento térmico.']
            out['notes'] = ['CRITICAL requiere proximidad extrema a TjMax, no solo 95 °C.', 'CorePulse valida consistencia del sensor antes de elevar a CRITICAL.']
        elif key == 'cpu_tjmax_warning':
            out['why'] = 'La CPU se mantuvo cerca de TjMax durante una parte importante de la ventana. Es una condición térmica alta que merece revisión, pero no implica por sí sola peligro inmediato.'
            out['checks'] = ['Comprobar ventilación y flujo de aire.', 'Observar ventiladores durante carga.', 'Comparar escritorio frente a juego.', 'Revisar perfil de energía si la condición es sostenida.']
            out['notes'] = ['Una lectura alrededor de 95 °C puede ser alta sin justificar CRITICAL por sí sola.']
        elif key == 'cpu_tjmax_sensor_uncertain':
            out['why'] = 'Las lecturas de temperatura y distancia a TjMax no producen un TjMax inferido suficientemente estable para elevar una alerta crítica.'
            out['checks'] = ['Repetir la observación durante una carga estable.', 'Comprobar que LibreHardwareMonitor esté entregando los mismos sensores.']
            out['notes'] = ['CorePulse evita clasificar CRITICAL cuando la referencia térmica es inconsistente.']
        elif key == 'ram_pressure':
            out['why'] = 'La RAM se mantuvo en 95% o más durante la mayoría de las muestras recientes.'
            out['checks'] = ['Revisar procesos con mayor consumo de memoria.', 'Cerrar aplicaciones no necesarias.', 'Comprobar archivo de paginación.', 'Si es habitual, considerar ampliar RAM.']
            out['notes'] = ['La alerta exige persistencia; no se activa por una sola muestra.']
        elif key == 'ssd_warning':
            out['why'] = 'La unidad superó repetidamente el warning térmico reportado por ella misma.'
            out['checks'] = ['Revisar flujo de aire alrededor de la unidad.', 'Comprobar si la temperatura baja al reducir carga.']
            out['notes'] = ['El umbral proviene del dispositivo.']
        elif key == 'ssd_critical':
            out['why'] = 'La unidad alcanzó repetidamente su umbral crítico reportado.'
            out['checks'] = ['Reducir cargas intensivas sobre la unidad.', 'Revisar ventilación/disipación.', 'Respaldar datos importantes si persiste.', 'Revisar SMART/reliability.']
        elif key == 'gpu_hotspot_attention':
            out['why'] = 'El hotspot de la GPU se mantuvo alto durante una proporción importante de muestras.'
            out['checks'] = ['Comprobar respuesta de ventiladores.', 'Revisar flujo de aire y temperatura ambiente.', 'Comparar hotspot y temperatura core.', 'Observar si baja al reducir carga gráfica.']
            out['notes'] = ['El umbral de hotspot es una heurística conservadora de CorePulse, no un límite oficial.']
        elif key == 'gpu_hotspot_delta':
            out['why'] = 'La diferencia hotspot-core se mantuvo elevada durante varias muestras.'
            out['checks'] = ['Seguir observando la diferencia hotspot-core.', 'Comparar el delta en diferentes cargas.']
            out['notes'] = ['Es una señal informativa; por sí sola no demuestra un fallo.']
        elif key == 'gpu_high_load_info':
            out['why'] = 'La GPU está siendo utilizada intensamente por una aplicación 3D.'
            out['checks'] = ['No requiere acción si temperaturas y frametime son normales.']
            out['notes'] = ['Una GPU al 90–100% jugando puede ser normal.']
        elif key == 'game_frametime_high':
            out['why'] = 'El frametime se mantuvo alto mientras el juego estaba en primer plano.'
            out['checks'] = ['Reducir primero ajustes gráficos pesados.', 'Comprobar RAM/VRAM simultáneamente.', 'Revisar procesos en segundo plano.', 'Comparar otra escena o juego.']
            out['notes'] = ['CorePulse no juzga FPS/frametime en GAME_BACKGROUND.']
        else:
            out['why'] = 'CorePulse detectó esta condición mediante el motor de alertas y conserva la evidencia que la activó.'
            out['checks'] = ['Revisar la evidencia y observar si la condición persiste.']
        return out

    def explain_state(self, state):
        active = (state.get('alerts') or {}).get('active') or []
        explanations = [self.explain_alert(alert) for alert in active]
        instant = copy.deepcopy(state.get('instant') or {}) if isinstance(state, dict) else {}
        return {'overall': state.get('overall', 'UNKNOWN'), 'context': state.get('context', 'UNKNOWN'), 'active_count': len(explanations), 'explanations': copy.deepcopy(explanations), 'instant': instant}
