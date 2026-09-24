"""Módulo integrado de audio. Toda operación nativa sucede fuera del hilo Tk."""
import queue
import threading
import customtkinter as ctk
from core.audio_test import AudioTest, evidence_rows
from core.theme_manager import color


class AudioTestPanel(ctk.CTkFrame):
    def __init__(self, master, service=None):
        super().__init__(master, fg_color=color('#0d1828'))
        self.service = service or AudioTest()
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self._poll_id = None
        self.bind('<Destroy>', self._destroyed, add='+')
        body = ctk.CTkFrame(self, fg_color=color('#0d1828'))
        body.pack(fill='both', expand=True, padx=12, pady=12)
        self.body = body
        self.label('TEST DE AUDIO', 20)
        self.label('Prueba manual local · Ajusta antes un volumen cómodo.', 12)
        self.label('El micrófono sólo graba al pulsar «Grabar 5 s». No se guarda ni envía la voz.', 12)
        self.output = self.label('SALIDA · Consultando…', 14)
        buttons = ctk.CTkFrame(body, fg_color='transparent')
        buttons.pack(fill='x', pady=8)
        self.actions = []
        for text, key in (('Izquierdo', 'left'), ('Derecho', 'right'), ('Ambos', 'both')):
            button = ctk.CTkButton(buttons, text=text, width=115,
                                  command=lambda k=key: self.run(lambda: self.service.play(k), k))
            button.pack(side='left', expand=True, fill='x', padx=3)
            self.actions.append(button)
        self.stereo = self.label('', 12)
        self.input = self.label('MICRÓFONO · Consultando…', 14)
        self.record_button = ctk.CTkButton(body, text='Grabar 5 s', command=self.record)
        self.record_button.pack(anchor='w', pady=8)
        self.actions.append(self.record_button)
        self.level = ctk.CTkProgressBar(body)
        self.level.pack(fill='x', pady=4)
        self.level.set(0)
        self.level_text = self.label('Nivel de entrada: N/A', 12)
        self.replay = ctk.CTkButton(body, text='Reproducir grabación',
                                   command=lambda: self.run(lambda: self.service.play('microphone'), 'microphone'))
        self.replay.pack(anchor='w', pady=8)
        self.actions.append(self.replay)
        self.status = self.label('Preparando dispositivos…', 13)
        self.question = self.label('', 13)
        answers = ctk.CTkFrame(body, fg_color='transparent')
        answers.pack(fill='x', pady=8)
        self.answers = []
        for answer in ('Sí', 'No', 'No estoy seguro'):
            button = ctk.CTkButton(answers, text=answer, width=100, state='disabled',
                                  command=lambda a=answer: self.run(lambda: self.service.confirm(a), 'confirm'))
            button.pack(side='left', fill='x', expand=True, padx=3)
            self.answers.append(button)
        self.summary = self.label('RESUMEN · NO EVALUADO', 13)
        self.refresh_button = ctk.CTkButton(body, text='Actualizar dispositivos',
                                          command=lambda: self.run(self.service.refresh, 'refresh'))
        self.refresh_button.pack(anchor='w', pady=8)
        self.actions.append(self.refresh_button)
        ctk.CTkButton(body, text='Detener', command=self.service.cancel.set).pack(anchor='w', pady=4)
        self._poll_id = self.after(50, self.poll)
        self.run(self.service.refresh, 'refresh')

    def label(self, text, size):
        label = ctk.CTkLabel(self.body, text=text, font=('Segoe UI', size),
                            anchor='w', justify='left', wraplength=405)
        label.pack(fill='x', pady=5)
        return label

    def record(self):
        self.level.set(0)
        self.run(lambda: self.service.record(lambda value: self.events.put(('level', value))), 'record')

    def run(self, fn, key):
        if self.busy or self.closed:
            return
        self.busy = True
        self.service.cancel.clear()  # Sólo una nueva acción explícita reinicia la cancelación.
        self.question.configure(text='')
        for widget in self.actions + self.answers:
            widget.configure(state='disabled')
        text = '● GRABANDO · 5 segundos' if key == 'record' else 'Reproduciendo…' if key in ('left', 'right', 'both', 'microphone') else 'Consultando…'
        self.status.configure(text=text)
        def worker():
            try:
                fn()
                self.events.put(('done', key))
            except Exception as exc:
                self.events.put(('error', str(exc)))
        threading.Thread(target=worker, daemon=True, name='CorePulse-AudioTest').start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'level':
                    self.level.set(min(1., value))
                    self.level_text.configure(text=f'Amplitud real: {value:.4f} (0–1)')
                    continue
                self.busy = False
                self.status.configure(text=('Error · ' + value) if kind == 'error' else
                                      'Grabación lista · pulsa Reproducir grabación.' if value == 'record' else
                                      'Operación terminada; confirma lo que escuchaste.' if self.service.pending else 'Listo')
                self.update_state()
        except queue.Empty:
            pass
        self._poll_id = self.after(50, self.poll)

    def update_state(self):
        devices = self.service.result.get('devices', {})
        output, source = devices.get('output', {}), devices.get('input', {})
        self.output.configure(text='SALIDA · ' + (output.get('name') or 'N/A') +
                              ('\n' + output.get('error', 'No disponible') if not output.get('available') else ''))
        self.input.configure(text='MICRÓFONO · ' + (source.get('name') or 'N/A') +
                             ('\n' + source.get('error', 'No disponible') if not source.get('available') else ''))
        self.stereo.configure(text='Canales L/R disponibles según Windows.' if output.get('stereo') else 'Prueba estéreo no disponible · N/A')
        for widget in self.actions:
            widget.configure(state='normal')
        for button in self.actions[:2]:
            button.configure(state='normal' if output.get('available') and output.get('stereo') else 'disabled')
        self.actions[2].configure(state='normal' if output.get('available') else 'disabled')
        self.record_button.configure(state='normal' if source.get('available') else 'disabled')
        self.replay.configure(state='normal' if self.service.recording and output.get('available') else 'disabled')
        pending = self.service.pending
        self.question.configure(text=('¿La grabación se escucha correctamente?' if pending == 'microphone' else
                                      '¿Escuchaste correctamente este canal?') if pending else '')
        for button in self.answers:
            button.configure(state='normal' if pending else 'disabled')
        from core.audio_test import summary
        rows = '\n'.join(f'{key}: {value}' for key, value in evidence_rows(self.service.result))
        self.summary.configure(text='RESUMEN · ' + summary(self.service.result) + '\n' + rows)

    def _destroyed(self, event):
        if event.widget is self:
            self.closed = True
            self.service.close()

    def destroy(self):
        if not self.closed:
            self.closed = True
            self.service.close()
            if self._poll_id is not None:
                self.after_cancel(self._poll_id)
        super().destroy()


def open_audio_test(app):
    return app.open_health_center(tab='audio')
