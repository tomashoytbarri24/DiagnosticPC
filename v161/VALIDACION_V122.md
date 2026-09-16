# Validación CorePulse V122

- Autoridad SMART NVMe directa sobre valores 0 ambiguos de proveedor: PASS
- `Percentage Used=6` => 94% restante: PASS
- `Percentage Used=0` => 100% restante cuando proviene del SMART NVMe directo: PASS
- `Wear=0` de Windows sin SMART directo => porcentaje N/A, estado cualitativo conservado: PASS
- Temperatura 0 °C => N/A: PASS
- Centro de Salud no penaliza N/A como 0%: PASS
- Runtime canónico preservado: verificar hashes contra V121 antes de empaquetar.
