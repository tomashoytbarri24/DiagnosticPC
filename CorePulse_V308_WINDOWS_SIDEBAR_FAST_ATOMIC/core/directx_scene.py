"""Escenas deterministas del benchmark gráfico DirectX de CorePulse.

Este módulo NO mide rendimiento. Sólo define geometría, complejidad y trayectoria
para que el backend Direct3D pueda ejecutar exactamente el mismo workload entre
máquinas. Todos los conteos publicados se derivan de estas estructuras.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class SceneLevel:
    key: str
    label: str
    terrain_resolution: int
    tree_instances: int
    rock_instances: int
    jet_instances: int
    cloud_instances: int
    shader_iterations: int
    texture_samples: int
    warmup_seconds: float
    settle_seconds: float
    measure_seconds: float
    boat_instances: int = 0
    smoke_instances: int = 0
    fire_instances: int = 0


WATER_RESOLUTION = 192

SCENE_LEVELS: tuple[SceneLevel, ...] = (
    SceneLevel('valley', 'Escena 1 · Valle abierto', 96, 220, 90, 1, 30, 10, 5, 5.0, 0.75, 10.0, 1, 0, 0),
    SceneLevel('forest', 'Escena 2 · Corredor de bosque', 144, 980, 300, 1, 52, 20, 9, 0.0, 1.00, 12.0, 1, 0, 0),
    SceneLevel('lake', 'Escena 3 · Lago y costa', 192, 2300, 720, 1, 78, 38, 16, 0.0, 1.00, 12.0, 1, 0, 0),
    SceneLevel('extreme', 'Escena 4 · Valle completo / Extreme', 256, 4600, 1500, 1, 118, 64, 24, 0.0, 1.25, 15.0, 1, 3, 2),
)


def profile_levels(profile: str = 'standard') -> tuple[SceneLevel, ...]:
    """Devuelve los niveles con tiempos del perfil, sin alterar su complejidad."""
    key = str(profile or 'standard').strip().lower()
    if key == 'quick':
        return tuple(SceneLevel(**{**s.__dict__, 'warmup_seconds': (2.0 if i == 0 else 0.0), 'settle_seconds': 0.75, 'measure_seconds': 5.0}) for i, s in enumerate(SCENE_LEVELS[:3]))
    if key == 'extended':
        return tuple(SceneLevel(**{**s.__dict__, 'warmup_seconds': (6.0 if i == 0 else 0.0), 'settle_seconds': 1.25, 'measure_seconds': 20.0}) for i, s in enumerate(SCENE_LEVELS))
    return SCENE_LEVELS


def terrain_height(x: float, z: float) -> float:
    """Función determinista de altura usada para el archipiélago."""
    # Cuatro islas suaves; el agua queda alrededor de y=0.
    islands = (
        (-105.0, -25.0, 92.0, 37.0),
        (70.0, 50.0, 80.0, 30.0),
        (10.0, -110.0, 58.0, 22.0),
        (145.0, -72.0, 52.0, 18.0),
    )
    h = -4.5
    for cx, cz, radius, amp in islands:
        dx = (x - cx) / radius
        dz = (z - cz) / radius
        r2 = dx * dx + dz * dz
        if r2 < 1.65:
            dome = max(0.0, 1.0 - r2)
            detail = (
                math.sin(x * 0.075 + cz * 0.01) * 0.9
                + math.cos(z * 0.064 - cx * 0.01) * 0.8
                + math.sin((x + z) * 0.031) * 0.7
            )
            h += dome * dome * amp + dome * detail * 2.3
    return h


def _normal_for_height(x: float, z: float, eps: float = 0.7) -> tuple[float, float, float]:
    hl = terrain_height(x - eps, z)
    hr = terrain_height(x + eps, z)
    hd = terrain_height(x, z - eps)
    hu = terrain_height(x, z + eps)
    nx, ny, nz = hl - hr, 2.0 * eps, hd - hu
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / length, ny / length, nz / length


def build_terrain(resolution: int, span: float = 420.0):
    """Malla de terreno: vértice = pos3, normal3, uv2."""
    n = max(8, int(resolution))
    vertices: list[tuple[float, ...]] = []
    indices: list[int] = []
    for j in range(n):
        v = j / (n - 1)
        z = (v - 0.5) * span
        for i in range(n):
            u = i / (n - 1)
            x = (u - 0.5) * span
            y = terrain_height(x, z)
            nx, ny, nz = _normal_for_height(x, z)
            vertices.append((x, y, z, nx, ny, nz, u * 8.0, v * 8.0))
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            b = a + 1
            c = a + n
            d = c + 1
            indices.extend((a, c, b, b, c, d))
    return vertices, indices


def build_water(resolution: int = WATER_RESOLUTION, span: float = 760.0):
    n = max(8, int(resolution))
    vertices: list[tuple[float, ...]] = []
    indices: list[int] = []
    for j in range(n):
        v = j / (n - 1)
        z = (v - 0.5) * span
        for i in range(n):
            u = i / (n - 1)
            x = (u - 0.5) * span
            vertices.append((x, 0.0, z, 0.0, 1.0, 0.0, u * 17.0, v * 17.0))
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i; b = a + 1; c = a + n; d = c + 1
            indices.extend((a, c, b, b, c, d))
    return vertices, indices


def build_jet(radial_segments: int = 24):
    """Jet original CorePulse V11, con silueta 3D estable y reconocible.

    El modelo sigue el eje X (nariz +X), pero incorpora fuselaje elíptico,
    ala delta con borde de fuga, estabilizadores, quilla y canopy marcado
    mediante UV.y > 1.5. No usa assets externos ni geometría aleatoria.
    """
    seg = max(12, int(radial_segments))
    verts: list[tuple[float, ...]] = []
    idx: list[int] = []
    rings = [
        (-6.3, 0.10, 0.10), (-5.6, 0.48, 0.38), (-4.1, 0.70, 0.52),
        (-1.7, 0.88, 0.64), (1.0, 0.92, 0.66), (3.4, 0.70, 0.50),
        (5.0, 0.40, 0.30), (6.5, 0.055, 0.055),
    ]
    for ri, (x, ry, rz) in enumerate(rings):
        for k in range(seg):
            a = 2.0 * math.pi * k / seg
            y = math.cos(a) * ry
            z = math.sin(a) * rz
            # Normal radial aproximada. Es suficiente para el shading del benchmark.
            nx, ny, nz = 0.0, math.cos(a), math.sin(a)
            verts.append((x, y, z, nx, ny, nz, ri / (len(rings)-1), k / seg))
    for r in range(len(rings) - 1):
        for k in range(seg):
            a = r * seg + k
            b = r * seg + (k + 1) % seg
            c = (r + 1) * seg + k
            d = (r + 1) * seg + (k + 1) % seg
            idx.extend((a, c, b, b, c, d))

    def add_tri(p0, p1, p2, normal, uv=((0,0),(1,0),(0.5,1))):
        base = len(verts)
        for pnt, tex in zip((p0, p1, p2), uv):
            verts.append((*pnt, *normal, *tex))
        idx.extend((base, base+1, base+2))

    def add_quad(p0, p1, p2, p3, normal, uv_y=0.4):
        # Dos triángulos; culling está desactivado para mantener el mismo mesh en
        # hardware con distinta convención de winding.
        add_tri(p0, p1, p2, normal, ((0,uv_y),(1,uv_y),(1,uv_y+0.35)))
        add_tri(p0, p2, p3, normal, ((0,uv_y),(1,uv_y+0.35),(0,uv_y+0.35)))

    # Ala principal: mayor cuerda y flecha para que la silueta se lea a distancia.
    add_quad((-2.55, 0.00, -0.40), (2.35, 0.00, -0.32), (0.82, 0.03, -6.35), (-1.35, 0.03, -4.35), (0.0, 1.0, 0.0))
    add_quad((-2.55, 0.00,  0.40), (-1.35, 0.03,  4.35), (0.82, 0.03,  6.35), (2.35, 0.00,  0.32), (0.0, 1.0, 0.0))
    # LERX / prolongaciones de ala junto al fuselaje.
    add_quad((-2.20, 0.09, -0.26), (-0.22, 0.18, -0.22), (-0.90, 0.28, -1.78), (-2.08, 0.20, -1.10), (0.0, 1.0, 0.0), 0.52)
    add_quad((-2.20, 0.09,  0.26), (-2.08, 0.20,  1.10), (-0.90, 0.28,  1.78), (-0.22, 0.18,  0.22), (0.0, 1.0, 0.0), 0.52)
    # Estabilizadores horizontales.
    add_quad((2.45, 0.10, -0.22), (5.05, 0.10, -0.16), (3.85, 0.12, -2.95), (2.95, 0.12, -2.05), (0.0, 1.0, 0.0))
    add_quad((2.45, 0.10,  0.22), (2.95, 0.12,  2.05), (3.85, 0.12,  2.95), (5.05, 0.10,  0.16), (0.0, 1.0, 0.0))
    # Quilla vertical.
    add_tri((2.35, 0.28, 0.0), (4.95, 0.18, 0.0), (3.70, 2.55, 0.0), (0.0, 0.0, 1.0))
    add_tri((2.35, 0.28, 0.0), (3.70, 2.55, 0.0), (4.95, 0.18, 0.0), (0.0, 0.0, -1.0))
    # V13: nariz +X; desplaza estabilizadores y quilla hacia la cola -X.
    # Estas piezas se añadieron después de las alas principales (12 vértices).
    tail_start = len(rings) * seg + 12
    for vi in range(tail_start, len(verts)):
        x,y,z,nx,ny,nz,u,v = verts[vi]
        verts[vi] = (-x,y,z,-nx,ny,nz,u,v)
    # Canopy: UV.y=2 identifica material de cristal en el pixel shader.
    canopy_uv=((0.10,2.0),(0.90,2.0),(0.72,2.0))
    add_tri((0.8,0.68,-0.32),(3.2,0.50,-0.28),(1.65,1.14,-0.05),(0.0,0.72,-0.68),canopy_uv)
    add_tri((0.8,0.68, 0.32),(1.65,1.14, 0.05),(3.2,0.50, 0.28),(0.0,0.72, 0.68),canopy_uv)

    # V15: detalles de silueta. Se conserva un único mesh/draw call; las alas y
    # derivas ganan lectura transversal sin aumentar el número de instancias.
    # Tomas de aire laterales bajo el ala.
    add_quad((-0.65,-0.24,-0.54),(1.72,-0.18,-0.46),(1.24,-0.62,-0.77),(-0.92,-0.66,-0.84),(0.0,-0.45,-0.89),0.65)
    add_quad((-0.65,-0.24, 0.54),(-0.92,-0.66, 0.84),(1.24,-0.62, 0.77),(1.72,-0.18, 0.46),(0.0,-0.45, 0.89),0.65)
    # Gondolas/raíces de motor sutiles para engrosar la silueta en pasadas lejanas.
    add_quad((-1.05,-0.08,-0.52),(1.65,-0.05,-0.44),(1.20,-0.34,-0.95),(-1.12,-0.38,-0.98),(0.0,-0.32,-0.95),0.58)
    add_quad((-1.05,-0.08, 0.52),(-1.12,-0.38, 0.98),(1.20,-0.34, 0.95),(1.65,-0.05, 0.44),(0.0,-0.32, 0.95),0.58)
    # Dos derivas pequeñas complementan la quilla principal sin convertir el
    # modelo en un asset pesado.
    add_tri((-3.10,0.38,-0.32),(-4.85,0.26,-0.26),(-4.08,1.54,-0.26),(0.0,0.18,-0.98),((0.1,0.7),(0.9,0.7),(0.55,1.0)))
    add_tri((-3.10,0.38, 0.32),(-4.08,1.54, 0.26),(-4.85,0.26, 0.26),(0.0,0.18, 0.98),((0.1,0.7),(0.55,1.0),(0.9,0.7)))
    # Aletas ventrales discretas para darle lectura inferior en escenas con agua.
    add_tri((0.55,-0.22,-0.16),(-1.35,-0.28,-0.10),(-0.18,-0.86,-0.12),(0.0,-0.92,-0.38),((0.1,0.7),(0.9,0.7),(0.55,1.0)))
    add_tri((0.55,-0.22, 0.16),(-0.18,-0.86, 0.12),(-1.35,-0.28, 0.10),(0.0,-0.92, 0.38),((0.1,0.7),(0.55,1.0),(0.9,0.7)))
    # V19: dos toberas oscuras en la cola. El marcador UV.y 1.12 permite
    # material propio en el PS sin crear otro draw call ni una textura externa.
    add_quad((-5.88,-0.28,-0.72),(-5.88,0.28,-0.72),(-5.88,0.28,-0.18),(-5.88,-0.28,-0.18),(-1.0,0.0,0.0),1.12)
    add_quad((-5.88,-0.28, 0.18),(-5.88,0.28, 0.18),(-5.88,0.28, 0.72),(-5.88,-0.28, 0.72),(-1.0,0.0,0.0),1.12)
    return verts, idx


def build_boat():
    """Barco estilizado y más limpio visualmente para lectura a distancia."""
    verts: list[tuple[float, ...]] = []
    idx: list[int] = []

    def add_tri(p0, p1, p2, normal, uv=((0.0, 0.0), (1.0, 0.0), (0.5, 1.0))):
        base = len(verts)
        for pnt, tex in zip((p0, p1, p2), uv):
            verts.append((*pnt, *normal, *tex))
        idx.extend((base, base + 1, base + 2))

    def add_quad(p0, p1, p2, p3, normal, uv=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))):
        add_tri(p0, p1, p2, normal, (uv[0], uv[1], uv[2]))
        add_tri(p0, p2, p3, normal, (uv[0], uv[2], uv[3]))

    # Casco principal.
    front_top = (5.5, 0.10, 0.0)
    front_bottom = (4.2, -0.70, 0.0)
    add_quad((-4.7, 0.18, -1.25), (3.9, 0.18, -0.98), (2.9, -0.96, -0.56), (-3.8, -1.02, -0.82), (0.0, 0.0, -1.0))
    add_quad((-4.7, 0.18, 1.25), (-3.8, -1.02, 0.82), (2.9, -0.96, 0.56), (3.9, 0.18, 0.98), (0.0, 0.0, 1.0))
    add_quad((-4.7, 0.18, -1.25), (-4.7, 0.18, 1.25), (-3.8, -1.02, 0.82), (-3.8, -1.02, -0.82), (-1.0, 0.0, 0.0))
    add_tri((3.9, 0.18, -0.98), front_top, (3.9, 0.18, 0.98), (0.88, 0.15, 0.0))
    add_tri((2.9, -0.96, -0.56), (2.9, -0.96, 0.56), front_bottom, (0.88, -0.10, 0.0))
    add_quad((3.9, 0.18, -0.98), (2.9, -0.96, -0.56), front_bottom, front_top, (0.82, 0.0, -0.25))
    add_quad(front_top, front_bottom, (2.9, -0.96, 0.56), (3.9, 0.18, 0.98), (0.82, 0.0, 0.25))
    add_quad((-3.8, -1.02, -0.82), (-3.8, -1.02, 0.82), (2.9, -0.96, 0.56), (2.9, -0.96, -0.56), (0.0, -1.0, 0.0))

    # Cubierta.
    add_tri((-4.2, 0.26, -1.00), (3.5, 0.26, -0.78), (4.2, 0.12, 0.0), (0.0, 1.0, 0.0))
    add_tri((-4.2, 0.26, 1.00), (4.2, 0.12, 0.0), (3.5, 0.26, 0.78), (0.0, 1.0, 0.0))

    # Cabina y techo.
    add_quad((-1.2, 0.34, -0.82), (1.8, 0.34, -0.66), (1.55, 1.34, -0.52), (-0.9, 1.34, -0.62), (0.0, 0.0, -1.0))
    add_quad((-1.2, 0.34, 0.82), (-0.9, 1.34, 0.62), (1.55, 1.34, 0.52), (1.8, 0.34, 0.66), (0.0, 0.0, 1.0))
    add_quad((-1.2, 0.34, -0.82), (-1.2, 0.34, 0.82), (-0.9, 1.34, 0.62), (-0.9, 1.34, -0.62), (-1.0, 0.0, 0.0))
    add_quad((1.8, 0.34, -0.66), (1.55, 1.34, -0.52), (1.55, 1.34, 0.52), (1.8, 0.34, 0.66), (1.0, 0.0, 0.0))
    add_quad((-0.9, 1.34, -0.62), (1.55, 1.34, -0.52), (1.55, 1.34, 0.52), (-0.9, 1.34, 0.62), (0.0, 1.0, 0.0))
    # Parabrisas frontal.
    add_quad((1.0, 1.18, -0.55), (1.75, 0.62, -0.48), (1.75, 0.62, 0.48), (1.0, 1.18, 0.55), (0.95, 0.18, 0.0))

    # Quilla corta.
    add_quad((-2.1, -1.08, -0.18), (1.5, -1.08, -0.14), (1.5, -1.08, 0.14), (-2.1, -1.08, 0.18), (0.0, -1.0, 0.0))
    return verts, idx



def _append_tapered_cylinder(dst_v, dst_i, p0, p1, r0, r1, sides=8, material_marker=0.0):
    """Añade un cilindro cónico orientado entre dos puntos.

    Se usa para tronco y ramas del árbol. ``material_marker`` se guarda en UV.y
    para que el pixel shader diferencie corteza y follaje sin draw calls extra.
    """
    x0,y0,z0=p0; x1,y1,z1=p1
    dx,dy,dz=x1-x0,y1-y0,z1-z0
    ln=math.sqrt(dx*dx+dy*dy+dz*dz) or 1.0
    ax,ay,az=dx/ln,dy/ln,dz/ln
    # Construye una base ortonormal estable alrededor del eje.
    helper=(0.0,1.0,0.0) if abs(ay)<0.92 else (1.0,0.0,0.0)
    ux=ay*helper[2]-az*helper[1]; uy=az*helper[0]-ax*helper[2]; uz=ax*helper[1]-ay*helper[0]
    ul=math.sqrt(ux*ux+uy*uy+uz*uz) or 1.0; ux,uy,uz=ux/ul,uy/ul,uz/ul
    vx=ay*uz-az*uy; vy=az*ux-ax*uz; vz=ax*uy-ay*ux
    base=len(dst_v); sides=max(5,int(sides))
    for ring,(px,py,pz,rr) in enumerate(((x0,y0,z0,r0),(x1,y1,z1,r1))):
        for k in range(sides):
            a=2.0*math.pi*k/sides; ca,sa=math.cos(a),math.sin(a)
            nx,ny,nz=ux*ca+vx*sa,uy*ca+vy*sa,uz*ca+vz*sa
            dst_v.append((px+nx*rr,py+ny*rr,pz+nz*rr,nx,ny,nz,k/sides,float(material_marker)))
    for k in range(sides):
        a=base+k; b=base+(k+1)%sides; c=base+sides+k; d=base+sides+(k+1)%sides
        dst_i.extend((a,c,b,b,c,d))


def _append_leaf_card(dst_v, dst_i, center, half_w, half_h, yaw, tilt=0.0):
    """Añade una tarjeta de follaje con UV.y desplazado +2 como marcador.

    El pixel shader recorta el borde proceduralmente (alpha test) para evitar
    copas esféricas. Tres tarjetas cruzadas por cluster producen volumen visual
    sin multiplicar draw calls porque todo el árbol sigue siendo un único mesh.
    """
    cx, cy, cz = center
    sy, cyaw = math.sin(yaw), math.cos(yaw)
    st, ct = math.sin(tilt), math.cos(tilt)
    # Eje horizontal de la tarjeta y eje vertical ligeramente inclinado.
    rx, ry, rz = cyaw, 0.0, -sy
    ux, uy, uz = sy * st, ct, cyaw * st
    # Normal mirando perpendicular a la tarjeta.
    nx, ny, nz = sy * ct, -st, cyaw * ct
    base = len(dst_v)
    corners = ((-1,-1,0.0,0.0),(1,-1,1.0,0.0),(1,1,1.0,1.0),(-1,1,0.0,1.0))
    for sx, syy, u, v in corners:
        px = cx + rx * (sx * half_w) + ux * (syy * half_h)
        py = cy + ry * (sx * half_w) + uy * (syy * half_h)
        pz = cz + rz * (sx * half_w) + uz * (syy * half_h)
        dst_v.append((px, py, pz, nx, ny, nz, u, 2.0 + v * 0.99))
    dst_i.extend((base,base+1,base+2, base,base+2,base+3))


def build_tree():
    """Árbol V11: tronco ramificado + canopy multicapa con hojas recortadas.

    Sigue siendo un único mesh instanciado (un draw call), pero la copa utiliza
    más clusters pequeños y alturas irregulares para eliminar el aspecto de
    "bola verde". Las variaciones de color/escala siguen siendo deterministas.
    """
    verts: list[tuple[float, ...]]=[]; idx: list[int]=[]
    _append_tapered_cylinder(verts,idx,(0,0,0),(0,6.25,0),0.37,0.11,12,0.0)
    branches=(
        ((0,1.95,0),(1.40,3.10,0.46),0.17,0.045),
        ((0,2.25,0),(-1.32,3.36,-0.42),0.16,0.043),
        ((0,2.62,0),(0.62,3.82,-1.42),0.15,0.040),
        ((0,2.90,0),(-0.70,4.04,1.34),0.14,0.038),
        ((0,3.22,0),(1.20,4.44,-0.70),0.125,0.035),
        ((0,3.48,0),(-1.10,4.60,0.72),0.12,0.034),
        ((0,3.82,0),(0.55,4.92,1.05),0.105,0.031),
        ((0,4.04,0),(-0.46,5.12,-1.00),0.10,0.030),
        ((0,4.34,0),(0.82,5.30,-0.44),0.088,0.027),
        ((0,4.48,0),(-0.78,5.38,0.48),0.084,0.026),
    )
    for p0,p1,r0,r1 in branches:
        _append_tapered_cylinder(verts,idx,p0,p1,r0,r1,8,0.0)

    # Canopy asimétrico: clusters pequeños y superpuestos en lugar de grandes
    # tarjetas repetidas. Tres tarjetas cruzadas por cluster mantienen volumen.
    clusters=(
        (-1.18,3.10,-0.22,0.86,0.66),(1.08,3.18,0.34,0.92,0.70),
        (-0.48,3.40,1.05,0.88,0.68),(0.48,3.46,-1.12,0.86,0.66),
        (-1.30,3.72,0.48,0.96,0.73),(1.32,3.78,-0.52,0.98,0.75),
        (-0.72,3.96,-1.00,0.94,0.72),(0.82,4.02,1.03,0.92,0.70),
        (0.02,4.10,0.02,1.04,0.80),(-1.08,4.28,-0.34,0.88,0.68),
        (1.10,4.32,0.28,0.90,0.70),(-0.55,4.48,0.92,0.86,0.66),
        (0.58,4.51,-0.94,0.86,0.66),(0.05,4.65,0.08,0.98,0.75),
        (-0.82,4.82,-0.48,0.80,0.62),(0.88,4.84,0.44,0.82,0.64),
        (-0.34,5.02,0.72,0.78,0.60),(0.40,5.06,-0.76,0.78,0.60),
        (0.00,5.18,0.02,0.88,0.68),(-0.55,5.36,-0.18,0.72,0.56),
        (0.58,5.40,0.22,0.72,0.56),(-0.18,5.58,0.46,0.68,0.53),
        (0.22,5.62,-0.48,0.68,0.53),(0.00,5.88,0.00,0.62,0.50),
    )
    for ci,(x,y,z,hw,hh) in enumerate(clusters):
        phase=(ci*0.61803398875)%1.0 * math.tau
        tilt=math.sin(ci*1.73)*0.13
        yaw_offsets = (0.0, 0.93, 2.06)
        scale_x = (0.79, 0.73, 0.76)
        scale_y = (0.86, 0.80, 0.83)
        for k in range(3):
            # V16: mismas 3 tarjetas / 2 triángulos por tarjeta. Son más
            # estrechas y no equidistantes para reducir la pared verde cercana.
            local_tilt = tilt + (-0.11, 0.07, 0.15)[k]
            _append_leaf_card(
                verts, idx, (x,y,z), hw*scale_x[k], hh*scale_y[k],
                phase+yaw_offsets[k], local_tilt,
            )
    return verts,idx

def build_rock(lat_segments: int = 6, lon_segments: int = 9):
    verts=[]; idx=[]
    lat=max(4,lat_segments); lon=max(6,lon_segments)
    for y in range(lat+1):
        v=y/lat; phi=math.pi*v
        for x in range(lon):
            u=x/lon; th=2*math.pi*u
            wobble=1.0+0.12*math.sin(th*3.0)+0.08*math.cos(phi*5.0)
            px=math.sin(phi)*math.cos(th)*wobble
            py=math.cos(phi)*0.75*wobble
            pz=math.sin(phi)*math.sin(th)*wobble
            l=math.sqrt(px*px+py*py+pz*pz) or 1
            verts.append((px,py,pz,px/l,py/l,pz/l,u,v))
    for y in range(lat):
        for x in range(lon):
            a=y*lon+x; b=y*lon+(x+1)%lon; c=(y+1)*lon+x; d=(y+1)*lon+(x+1)%lon
            idx.extend((a,c,b,b,c,d))
    return verts,idx

def _append_scaled_mesh(dst_v, dst_i, src_v, src_i, offset, scale, uv_marker=None):
    base=len(dst_v)
    ox,oy,oz=offset
    sx,sy,sz=scale
    for v in src_v:
        px,py,pz,nx,ny,nz,u,w=v
        # La transformación sólo escala/traslada; normal aproximada renormalizada.
        nnx=nx/max(abs(sx),1e-6); nny=ny/max(abs(sy),1e-6); nnz=nz/max(abs(sz),1e-6)
        ln=math.sqrt(nnx*nnx+nny*nny+nnz*nnz) or 1.0
        vv=float(uv_marker) if uv_marker is not None else w
        dst_v.append((px*sx+ox,py*sy+oy,pz*sz+oz,nnx/ln,nny/ln,nnz/ln,u,vv))
    dst_i.extend(base+i for i in src_i)


def _append_cloud_card(dst_v, dst_i, center, half_w, half_h, yaw, pitch=0.0):
    """Tarjeta suave para nubes V11; UV 0..1 se usa para alpha radial."""
    cx,cy,cz=center
    sy,cyaw=math.sin(yaw),math.cos(yaw)
    sp,cp=math.sin(pitch),math.cos(pitch)
    rx,ry,rz=cyaw,0.0,-sy
    ux,uy,uz=sy*sp,cp,cyaw*sp
    nx,ny,nz=sy*cp,-sp,cyaw*cp
    base=len(dst_v)
    for sx,syy,u,v in ((-1,-1,0,0),(1,-1,1,0),(1,1,1,1),(-1,1,0,1)):
        px=cx+rx*(sx*half_w)+ux*(syy*half_h)
        py=cy+ry*(sx*half_w)+uy*(syy*half_h)
        pz=cz+rz*(sx*half_w)+uz*(syy*half_h)
        dst_v.append((px,py,pz,nx,ny,nz,float(u),float(v)))
    dst_i.extend((base,base+1,base+2,base,base+2,base+3))


def build_cloud(lat_segments: int = 0, lon_segments: int = 0):
    """Nube V11 tipo *soft volume* hecha con tarjetas cruzadas.

    Sustituye los lóbulos de roca de V10. Cada nube contiene puffs de distintas
    escalas y alturas; el PS aplica borde suave, ruido y blending. No usa assets
    externos y sigue siendo determinista/repetible.
    """
    del lat_segments, lon_segments  # compatibilidad de firma histórica
    verts: list[tuple[float,...]]=[]; idx: list[int]=[]
    puffs=(
        (0.00,0.00,0.00,1.70,0.82),
        (1.18,0.02,0.12,1.15,0.68),(-1.20,0.00,0.06,1.20,0.70),
        (0.42,0.48,-0.10,1.02,0.72),(-0.48,0.44,0.10,0.98,0.70),
        (1.78,-0.08,0.02,0.86,0.54),(-1.76,-0.06,-0.04,0.90,0.56),
        (0.02,0.70,0.04,0.88,0.62),(0.72,0.64,0.18,0.72,0.54),
        (-0.74,0.62,-0.16,0.74,0.54),
    )
    for pi,(x,y,z,hw,hh) in enumerate(puffs):
        phase=(pi*0.754877666)%1.0*math.tau
        # Dos verticales cruzadas + una ligeramente inclinada por puff.
        _append_cloud_card(verts,idx,(x,y,z),hw,hh,phase,0.0)
        _append_cloud_card(verts,idx,(x,y,z),hw*0.96,hh*0.96,phase+math.pi/2.0,0.0)
        _append_cloud_card(verts,idx,(x,y+0.08,z),hw*0.88,hh*0.82,phase+math.pi/4.0,0.20 if pi%2==0 else -0.20)
    return verts,idx

def build_smoke_plume():
    """Pluma de humo más suave y legible basada en tarjetas apiladas."""
    verts: list[tuple[float,...]]=[]; idx: list[int]=[]
    layers=(
        (0.00,0.15,0.00,0.55,0.85,0.0),
        (0.08,1.35,0.06,0.82,1.10,0.7),
        (-0.10,2.85,-0.04,1.05,1.34,1.5),
        (0.18,4.65,0.08,1.26,1.56,2.2),
        (-0.16,6.90,0.02,1.46,1.82,2.9),
        (0.10,9.35,-0.08,1.64,2.02,3.6),
    )
    for li,(x,y,z,hw,hh,phase) in enumerate(layers):
        _append_cloud_card(verts,idx,(x,y,z),hw,hh,phase,0.0)
        _append_cloud_card(verts,idx,(x,y,z),hw*0.94,hh*0.94,phase+math.pi/2.0,0.0)
        if li >= 2:
            _append_cloud_card(verts,idx,(x,y+0.12,z),hw*0.84,hh*0.80,phase+math.pi/4.0,0.12 if li%2==0 else -0.12)
    return verts,idx


def build_fire_billboard():
    """Llama compacta hecha con tarjetas cruzadas para una fogata visible."""
    verts: list[tuple[float,...]]=[]; idx: list[int]=[]
    flames=(
        (0.00,0.52,0.00,0.34,0.78,0.0),
        (0.08,0.76,0.04,0.28,0.66,1.1),
        (-0.06,0.68,-0.03,0.30,0.70,2.0),
    )
    for x,y,z,hw,hh,phase in flames:
        _append_cloud_card(verts,idx,(x,y,z),hw,hh,phase,0.0)
        _append_cloud_card(verts,idx,(x,y,z),hw*0.92,hh*0.92,phase+math.pi/2.0,0.0)
    return verts,idx


def build_sky(lat_segments: int = 22, lon_segments: int = 44):
    """Esfera UV limpia para el cielo.

    A diferencia de ``build_rock`` no introduce *wobble*. El VS la centra en la
    cámara, evitando que el movimiento orbital atraviese facetas del sky dome.
    """
    lat=max(8,int(lat_segments)); lon=max(16,int(lon_segments))
    verts=[]; idx=[]
    for y in range(lat+1):
        v=y/lat; phi=math.pi*v
        sp=math.sin(phi); cp=math.cos(phi)
        for x in range(lon+1):
            u=x/lon; th=2.0*math.pi*u
            px=sp*math.cos(th); py=cp; pz=sp*math.sin(th)
            verts.append((px,py,pz,px,py,pz,u,v))
    row=lon+1
    for y in range(lat):
        for x in range(lon):
            a=y*row+x; b=a+1; c=(y+1)*row+x; d=c+1
            idx.extend((a,c,b,b,c,d))
    return verts,idx

def mesh_triangles(indices: Sequence[int]) -> int:
    return len(indices) // 3


def level_workload(level: SceneLevel) -> dict:
    terrain_tri = 2 * (level.terrain_resolution - 1) ** 2
    # Los conteos de los meshes instanciados se determinan con los builders.
    jet_tri = mesh_triangles(build_jet()[1])
    tree_tri = mesh_triangles(build_tree()[1])
    rock_tri = mesh_triangles(build_rock()[1])
    cloud_tri = mesh_triangles(build_cloud()[1])
    boat_tri = mesh_triangles(build_boat()[1])
    smoke_tri = mesh_triangles(build_smoke_plume()[1])
    fire_tri = mesh_triangles(build_fire_billboard()[1])
    water_tri = 2 * (WATER_RESOLUTION - 1) ** 2
    total = (
        terrain_tri + water_tri
        + jet_tri * level.jet_instances
        + tree_tri * level.tree_instances
        + rock_tri * level.rock_instances
        + cloud_tri * level.cloud_instances
        + boat_tri * int(getattr(level, 'boat_instances', 0) or 0)
        + smoke_tri * int(getattr(level, 'smoke_instances', 0) or 0)
        + fire_tri * int(getattr(level, 'fire_instances', 0) or 0)
    )
    return {
        'terrain_resolution': level.terrain_resolution,
        'terrain_triangles': terrain_tri,
        'water_triangles': water_tri,
        'jet_instances': level.jet_instances,
        'tree_instances': level.tree_instances,
        'rock_instances': level.rock_instances,
        'cloud_instances': level.cloud_instances,
        'boat_instances': int(getattr(level, 'boat_instances', 0) or 0),
        'smoke_instances': int(getattr(level, 'smoke_instances', 0) or 0),
        'fire_instances': int(getattr(level, 'fire_instances', 0) or 0),
        'shader_iterations': level.shader_iterations,
        'texture_samples': level.texture_samples,
        'approx_triangles_per_frame': total,
        'object_instances': level.jet_instances + level.tree_instances + level.rock_instances + level.cloud_instances + int(getattr(level, 'boat_instances', 0) or 0) + int(getattr(level, 'smoke_instances', 0) or 0) + int(getattr(level, 'fire_instances', 0) or 0) + 3,
        'draw_calls_per_frame': 8 + (1 if int(getattr(level, 'smoke_instances', 0) or 0) > 0 else 0) + (1 if int(getattr(level, 'fire_instances', 0) or 0) > 0 else 0),
        'warmup_seconds': level.warmup_seconds,
        'settle_seconds': level.settle_seconds,
        'measure_seconds': level.measure_seconds,
    }


def all_workloads(profile: str = 'standard') -> list[dict]:
    return [{'key': s.key, 'label': s.label, **level_workload(s)} for s in profile_levels(profile)]
