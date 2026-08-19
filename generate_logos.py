import os
from PIL import Image, ImageDraw, ImageFont

# Crear carpeta de assets si no existe
assets_dir = r"C:\DiagnosticPC\assets"
os.makedirs(assets_dir, exist_ok=True)

def create_neon_pulse_logo():
    """ Opción 1: Rayo + CPU en Cyan y Verde """
    size = (512, 512)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fondo redondeado oscuro
    draw.rounded_rectangle([20, 20, 492, 492], radius=80, fill="#151c2c", outline="#232f48", width=8)

    # Marco de CPU (Chipset)
    draw.rectangle([120, 120, 392, 392], outline="#38bdf8", width=12)

    # Pines del procesador
    for i in range(160, 360, 40):
        # Arriba / Abajo
        draw.line([(i, 90), (i, 120)], fill="#38bdf8", width=8)
        draw.line([(i, 392), (i, 422)], fill="#38bdf8", width=8)
        # Izquierda / Derecha
        draw.line([(90, i), (120, i)], fill="#38bdf8", width=8)
        draw.line([(392, i), (422, i)], fill="#38bdf8", width=8)

    # Rayo Neón Central
    lightning_points = [(280, 150), (200, 270), (270, 270), (230, 370), (330, 240), (260, 240)]
    draw.polygon(lightning_points, fill="#10b981")

    # Guardar en formato PNG e ICO
    img.save(os.path.join(assets_dir, "logo_neon_pulse.png"))
    img.save(os.path.join(assets_dir, "app_icon.ico"), format="ICO", sizes=[(64, 64), (128, 128), (256, 256)])

def create_shield_health_logo():
    """ Opción 2: Escudo Diagnóstico """
    size = (512, 512)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Escudo
    shield_points = [(256, 60), (430, 120), (400, 360), (256, 460), (112, 360), (82, 120)]
    draw.polygon(shield_points, fill="#151c2c", outline="#a855f7", width=10)

    # Pulso / Electrocardiograma
    pulse_points = [(130, 256), (190, 256), (220, 180), (260, 330), (290, 210), (320, 256), (380, 256)]
    draw.line(pulse_points, fill="#38bdf8", width=14, joint="curved")

    img.save(os.path.join(assets_dir, "logo_shield_health.png"))

create_neon_pulse_logo()
create_shield_health_logo()
print("¡Logos e íconos generados exitosamente en C:\\DiagnosticPC\\assets!")
