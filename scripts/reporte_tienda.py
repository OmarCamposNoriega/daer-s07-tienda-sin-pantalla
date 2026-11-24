"""Parte 2 — Script de reporte que consume la CLI headless (`tiendactl`) vía `--json`.

Ejecución desde la raíz del proyecto (con `myvenv` activado):
    python scripts/reporte_tienda.py
    python scripts/reporte_tienda.py --umbral 5 --minimo 2 --pedido 1
"""

import argparse
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MANAGE_PY = BASE_DIR / 'manage.py'


def ejecutar_tiendactl(*args):
    """Ejecuta `python manage.py tiendactl <args>` en modo headless y retorna (returncode, stdout, stderr)."""
    entorno = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    proceso = subprocess.run(
        [sys.executable, str(MANAGE_PY), 'tiendactl', *args],
        cwd=BASE_DIR,
        env=entorno,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )
    return proceso.returncode, proceso.stdout.strip(), proceso.stderr.strip()


def consultar_json(*args):
    """Llama a `tiendactl ... --json`, exige código de salida 0 y parsea el JSON resultante."""
    codigo, salida, error = ejecutar_tiendactl(*args, '--json')
    if codigo != 0:
        raise RuntimeError(f'tiendactl {" ".join(args)} falló con código {codigo}: {error or salida}')
    return json.loads(salida)


def generar_reporte(umbral: int, minimo: int, pedido_id: int, categoria: str, busqueda: str) -> int:
    """Genera un reporte consolidado de la tienda y verifica el contrato de códigos de salida."""
    version_activa = os.environ.get('TIENDA_VERSION', 'alumno')
    print('=' * 68)
    print(f'REPORTE AUTOMÁTICO DE LA TIENDA (tiendactl --json | versión: {version_activa})')
    print('=' * 68)

    # 1. Ventas pagadas por categoría (importes exactos como Decimal)
    ventas = consultar_json('ventas')
    total_ventas = sum((Decimal(item['total']) for item in ventas), Decimal('0.00'))
    print('\n[1] Ventas pagadas por categoría:')
    for fila in ventas:
        print(f"  - {fila['categoria']:<12} : S/ {Decimal(fila['total']):>6.2f}")
    print(f"  Total general pagado : S/ {total_ventas:>6.2f}")

    # 2. Alerta de stock bajo
    bajo_stock = consultar_json('stock', '--umbral', str(umbral))
    print(f'\n[2] Productos con stock <= {umbral}:')
    for fila in bajo_stock:
        marca = ' [AGOTADO]' if fila['stock'] == 0 else ''
        print(f"  - {fila['nombre']:<18} : {fila['stock']} u.{marca}")

    # 3. Clientes frecuentes
    frecuentes = consultar_json('clientes', '--minimo', str(minimo))
    print(f'\n[3] Clientes con al menos {minimo} pedidos pagados:')
    for fila in frecuentes:
        print(f"  - {fila['nombre']:<18} : {fila['pedidos_pagados']} pedidos pagados")

    # 4. Catálogo por categoría y búsqueda
    productos_cat = consultar_json('categoria', categoria)
    coincidencias = consultar_json('buscar', busqueda)
    print(f"\n[4] Categoría '{categoria}' ({len(productos_cat)} productos):")
    for fila in productos_cat:
        print(f"  - {fila['nombre']:<18} S/ {Decimal(fila['precio']):>5.2f} (stock {fila['stock']})")
    print(f"    Búsqueda '{busqueda}': {', '.join(coincidencias) if coincidencias else '(sin coincidencias)'}")

    # 5. Detalle de pedido
    detalle = consultar_json('pedido', str(pedido_id))
    print(f"\n[5] Detalle del pedido #{detalle['pedido']} — {detalle['cliente']} ({detalle['estado']}):")
    for linea in detalle['lineas']:
        print(
            f"  - {linea['cantidad']} × {linea['producto']} "
            f"@ S/ {Decimal(linea['precio_unitario']):.2f} = S/ {Decimal(linea['subtotal']):.2f}"
        )
    print(f"  Total del pedido: S/ {Decimal(detalle['total']):.2f}")

    # 6. Comprobación del contrato headless (códigos 0, 2 y 3)
    print('\n[6] Verificación del contrato de códigos de salida:')
    c_vacio, out_vacio, _ = ejecutar_tiendactl('categoria', 'Helados', '--json')
    c_invalido, _, err_invalido = ejecutar_tiendactl('stock', '--umbral', '-1', '--json')
    c_inexistente, _, err_inexistente = ejecutar_tiendactl('pedido', '999', '--json')

    print(f'  - Categoría vacía ("Helados"): código={c_vacio}, salida={out_vacio}')
    print(f'  - Umbral negativo (--umbral -1): código={c_invalido}, error={err_invalido}')
    print(f'  - Pedido inexistente (999): código={c_inexistente}, error={err_inexistente}')

    if (c_vacio, c_invalido, c_inexistente) != (0, 2, 3):
        print('\nERROR: el contrato de códigos de salida no devolvió (0, 2, 3).', file=sys.stderr)
        return 1

    print('\nReporte completado sin errores (contrato headless verificado: 0, 2, 3).')
    return 0


def main():
    parser = argparse.ArgumentParser(description='Genera un reporte consumiendo tiendactl --json.')
    parser.add_argument('--umbral', type=int, default=5, help='Umbral de stock bajo (por defecto: 5)')
    parser.add_argument('--minimo', type=int, default=2, help='Mínimo de pedidos pagados (por defecto: 2)')
    parser.add_argument('--pedido', type=int, default=1, help='ID de pedido a detallar (por defecto: 1)')
    parser.add_argument('--categoria', default='Gaseosas', help='Categoría a consultar (por defecto: Gaseosas)')
    parser.add_argument('--buscar', default='chocolate', help='Texto a buscar en productos (por defecto: chocolate)')
    args = parser.parse_args()

    try:
        sys.exit(generar_reporte(args.umbral, args.minimo, args.pedido, args.categoria, args.buscar))
    except RuntimeError as exc:
        print(f'Error ejecutando el reporte: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
