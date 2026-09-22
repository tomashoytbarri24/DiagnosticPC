"""Módulo integrado de audio. Toda operación nativa sucede fuera del hilo Tk."""
import queue
import threading
import customtkinter as ctk
from core.audio_test import AudioTest, evidence_rows
from core.theme_manager import color, role_color


FONT = 'Segoe UI'


class AudioTestPanel(ctk.CTkFrame):
    """Prueba guiada de audio con una composición visual compacta y simétrica."""

    CARD_HEIGHT = 220

    def __init__(self, master, service=None):
        super().__init__(master, fg_color=color('#06111f'))
        self.service = service or AudioTest()
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self._poll_id = None
        self.bind('<Destroy>', self._destroyed, add='+')

        self.body = ctk.CTkFrame(self, fg_color='transparent')
        self.body.pack(fill='both', expand=True, padx=8, pady=8)

        # Introducción breve: el encabezado superior del Centro de salud ya
        # contiene el título, por lo que evitamos repetir "TEST DE AUDIO".
        intro = ctk.CTkFrame(self.body, fg_color='transparent')
        intro.pack(fill='x', padx=4, pady=(1, 8))
        ctk.CTkLabel(
            intro,
            text='Prueba guiada local',
            font=(FONT, 11, 'bold'),
            text_color=role_color('accent'),
            anchor='w',
        ).pack(anchor='w')
        ctk.CTkLabel(
            intro,
            text='Comprueba salida estéreo y micrófono. La voz permanece sólo en memoria y nunca se guarda ni se envía.',
            font=(FONT, 10),
            text_color=role_color('text_2'),
            anchor='w', justify='left', wraplength=1180,
        ).pack(fill='x', pady=(2, 0))

        grid = ctk.CTkFrame(self.body, fg_color='transparent')
        grid.pack(fill='x', padx=0, pady=0)
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform='audio_cards_cols')
        for row in range(2):
            grid.grid_rowconfigure(row, minsize=self.CARD_HEIGHT + 10, uniform='audio_cards_rows')

        self.actions = []
        self.channel_buttons = {}
        self.answers = []

        # 1) Salida
        output_card, output_content = self._make_card(
            grid, 0, 0, 'SALIDA DE AUDIO', 'Altavoces y canales', '01', role_color('accent')
        )
        self.output = self._text(
            output_content, 'Consultando dispositivo…', 11, bold=True,
            color_value=role_color('text'), pady=(0, 4)
        )
        self.stereo = self._text(
            output_content, '', 9, color_value=role_color('muted'), pady=(0, 8)
        )
        channels = ctk.CTkFrame(output_content, fg_color='transparent')
        channels.pack(fill='x', side='bottom', pady=(4, 0))
        for text, key in (('Izquierdo', 'left'), ('Ambos', 'both'), ('Derecho', 'right')):
            button = self._button(
                channels, text,
                command=lambda k=key: self.run(lambda: self.service.play(k), k),
                primary=True,
            )
            button.pack(side='left', expand=True, fill='x', padx=3)
            self.channel_buttons[key] = button
            self.actions.append(button)

        # 2) Micrófono
        input_card, input_content = self._make_card(
            grid, 0, 1, 'MICRÓFONO', 'Captura y reproducción local', '02', role_color('accent')
        )
        self.input = self._text(
            input_content, 'Consultando dispositivo…', 11, bold=True,
            color_value=role_color('text'), pady=(0, 6)
        )
        self.level_text = self._text(
            input_content, 'Nivel de entrada: N/A', 9,
            color_value=role_color('muted'), pady=(0, 5)
        )
        self.level = ctk.CTkProgressBar(
            input_content,
            height=8,
            corner_radius=4,
            progress_color=role_color('accent'),
            fg_color=role_color('surface_2'),
        )
        self.level.pack(fill='x', pady=(0, 10))
        self.level.set(0)
        mic_actions = ctk.CTkFrame(input_content, fg_color='transparent')
        mic_actions.pack(fill='x', side='bottom', pady=(4, 0))
        self.record_button = self._button(mic_actions, '●  Grabar 5 s', command=self.record, primary=True)
        self.record_button.pack(side='left', fill='x', expand=True, padx=(0, 4))
        self.actions.append(self.record_button)
        self.replay = self._button(
            mic_actions, '▶  Reproducir',
            command=lambda: self.run(lambda: self.service.play('microphone'), 'microphone'),
        )
        self.replay.pack(side='left', fill='x', expand=True, padx=(4, 0))
        self.actions.append(self.replay)

        # 3) Confirmación manual
        confirm_card, confirm_content = self._make_card(
            grid, 1, 0, 'CONFIRMACIÓN', 'Validación manual de lo que escuchas', '03', role_color('accent')
        )
        self.status = self._text(
            confirm_content, 'Preparando dispositivos…', 11, bold=True,
            color_value=role_color('text'), pady=(0, 7)
        )
        self.question = self._text(
            confirm_content, 'Cuando termine una reproducción podrás confirmar el resultado.', 10,
            color_value=role_color('text_2'), pady=(0, 8)
        )
        answers = ctk.CTkFrame(confirm_content, fg_color='transparent')
        answers.pack(fill='x', side='bottom', pady=(4, 0))
        for answer in ('Sí', 'No', 'No estoy seguro'):
            button = self._button(
                answers, answer, state='disabled',
                command=lambda a=answer: self.run(lambda: self.service.confirm(a), 'confirm'),
            )
            button.pack(side='left', fill='x', expand=True, padx=3)
            self.answers.append(button)

        # 4) Resultado / evidencia
        summary_card, summary_content = self._make_card(
            grid, 1, 1, 'RESULTADO', 'Estado y evidencia de la prueba actual', '04', role_color('accent')
        )
        self.summary_state = self._status_badge(summary_content, 'NO EVALUADO', role_color('muted'))
        self.summary = ctk.CTkLabel(
            summary_content,
            text='Aún no hay resultados confirmados.',
            font=(FONT, 9),
            text_color=role_color('text_2'),
            anchor='nw', justify='left', wraplength=570,
        )
        self.summary.pack(fill='both', expand=True, pady=(8, 0))

        footer = ctk.CTkFrame(self.body, fg_color='transparent')
        footer.pack(fill='x', padx=4, pady=(8, 2))
        self.refresh_button = self._button(
            footer, '↻  Actualizar dispositivos',
            command=lambda: self.run(self.service.refresh, 'refresh'),
        )
        self.refresh_button.pack(side='left')
        self.actions.append(self.refresh_button)
        self.stop_button = self._button(
            footer, 'Detener prueba', command=self.service.cancel.set,
        )
        self.stop_button.pack(side='right')

        self._poll_id = self.after(50, self.poll)
        self.run(self.service.refresh, 'refresh')

    def _make_card(self, parent, row, column, eyebrow, subtitle, number, accent):
        card = ctk.CTkFrame(
            parent,
            height=self.CARD_HEIGHT,
            fg_color=role_color('surface'),
            border_width=1,
            border_color=role_color('border'),
            corner_radius=10,
        )
        card.grid(row=row, column=column, sticky='nsew', padx=5, pady=5)
        card.grid_propagate(False)
        content = ctk.CTkFrame(card, fg_color='transparent')
        content.pack(fill='both', expand=True, padx=14, pady=12)

        head = ctk.CTkFrame(content, fg_color='transparent')
        head.pack(fill='x', pady=(0, 7))
        number_badge = ctk.CTkLabel(
            head, text=number, width=28, height=28, corner_radius=7,
            fg_color=role_color('accent_soft'), text_color=accent,
            font=(FONT, 9, 'bold')
        )
        number_badge.pack(side='left', padx=(0, 9))
        titles = ctk.CTkFrame(head, fg_color='transparent')
        titles.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(
            titles, text=eyebrow, font=(FONT, 10, 'bold'), text_color=accent,
            anchor='w'
        ).pack(fill='x')
        ctk.CTkLabel(
            titles, text=subtitle, font=(FONT, 9), text_color=role_color('muted'),
            anchor='w'
        ).pack(fill='x', pady=(1, 0))
        return card, content

    def _status_badge(self, parent, text, text_color):
        badge = ctk.CTkLabel(
            parent, text=text, height=27, corner_radius=7,
            fg_color=role_color('surface_2'),
            text_color=text_color,
            font=(FONT, 9, 'bold'),
            anchor='w', padx=10,
        )
        badge.pack(fill='x')
        return badge

    def _text(self, parent, text, size, *, bold=False, color_value=None, pady=0):
        label = ctk.CTkLabel(
            parent, text=text, font=(FONT, size, 'bold' if bold else 'normal'),
            text_color=color_value or role_color('text_2'),
            anchor='w', justify='left', wraplength=570,
        )
        label.pack(fill='x', pady=pady)
        return label

    def _button(self, parent, text, command, *, primary=False, state='normal'):
        if primary:
            fg = role_color('accent_2')
            hover = role_color('accent')
            text_color = role_color('text_on_accent')
            border = role_color('accent_edge')
        else:
            fg = role_color('surface_2')
            hover = role_color('accent_soft')
            text_color = role_color('text_2')
            border = role_color('border')
        return ctk.CTkButton(
            parent, text=text, height=32, corner_radius=7,
            fg_color=fg, hover_color=hover, text_color=text_color,
            border_width=1, border_color=border,
            font=(FONT, 10, 'bold'), state=state, command=command,
        )

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
        text = (
            '● Grabando durante 5 segundos…' if key == 'record' else
            '▶ Reproduciendo prueba…' if key in ('left', 'right', 'both', 'microphone') else
            'Actualizando dispositivos…'
        )
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
                    self.level_text.configure(text=f'Nivel capturado: {value:.4f} / 1.0000')
                    continue
                self.busy = False
                self.status.configure(
                    text=('Error · ' + value) if kind == 'error' else
                    'Grabación lista · ahora puedes reproducirla.' if value == 'record' else
                    'Reproducción terminada · confirma lo que escuchaste.' if self.service.pending else
                    'Dispositivos listos.'
                )
                self.update_state()
        except queue.Empty:
            pass
        self._poll_id = self.after(50, self.poll)

    def update_state(self):
        devices = self.service.result.get('devices', {})
        output, source = devices.get('output', {}), devices.get('input', {})
        self.output.configure(
            text=(output.get('name') or 'Salida no disponible') +
                 (' · ' + output.get('error', 'N/A') if not output.get('available') else '')
        )
        self.input.configure(
            text=(source.get('name') or 'Micrófono no disponible') +
                 (' · ' + source.get('error', 'N/A') if not source.get('available') else '')
        )
        self.stereo.configure(
            text='Canales izquierdo y derecho disponibles.' if output.get('stereo')
            else 'Prueba estéreo no disponible · N/A'
        )

        for widget in self.actions:
            widget.configure(state='normal')
        for key in ('left', 'right'):
            self.channel_buttons[key].configure(
                state='normal' if output.get('available') and output.get('stereo') else 'disabled'
            )
        self.channel_buttons['both'].configure(state='normal' if output.get('available') else 'disabled')
        self.record_button.configure(state='normal' if source.get('available') else 'disabled')
        self.replay.configure(state='normal' if self.service.recording and output.get('available') else 'disabled')

        pending = self.service.pending
        self.question.configure(
            text=('¿La grabación se escucha correctamente?' if pending == 'microphone'
                  else '¿Escuchaste correctamente este canal?') if pending
            else 'Cuando termine una reproducción podrás confirmar el resultado.'
        )
        for button in self.answers:
            button.configure(state='normal' if pending else 'disabled')

        from core.audio_test import summary
        result_state = summary(self.service.result)
        tone = (
            role_color('ok_text') if result_state == 'AUDIO VERIFICADO' else
            role_color('bad_text') if result_state == 'PROBLEMA REPORTADO' else
            role_color('warn_text') if result_state == 'VERIFICACIÓN PARCIAL' else
            role_color('muted')
        )
        self.summary_state.configure(text=result_state, text_color=tone)
        rows = evidence_rows(self.service.result)
        compact_rows = []
        for key, value in rows:
            compact_rows.append(f'{key}:  {value}')
        self.summary.configure(text='\n'.join(compact_rows))

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
