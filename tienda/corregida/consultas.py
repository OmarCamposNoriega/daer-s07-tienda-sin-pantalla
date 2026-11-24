"""Copia corregida de tienda/ia/consultas.py (Parte 4).

Corrige los 4 fallos detectados por `python manage.py duelo ia --detalle` sin modificar tienda/ia/ ni tienda/tests/.
"""

from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum

from tienda.models import Cliente, LineaPedido, Pedido, Producto


def productos_por_categoria(nombre):
    # Fallo 1 corregido: usar __iexact para ignorar mayúsculas/minúsculas.
    productos = Producto.objects.filter(categoria__nombre__iexact=nombre).order_by('nombre')
    return [{'nombre': p.nombre, 'precio': p.precio, 'stock': p.stock, 'descripcion': p.descripcion}
            for p in productos]


def buscar_productos(texto):
    # Fallo 2 corregido: usar Q(...) | Q(...) para buscar en nombre O descripción (no AND).
    productos = Producto.objects.filter(Q(nombre__icontains=texto) | Q(descripcion__icontains=texto))
    return [p.nombre for p in productos.order_by('nombre')]


def stock_bajo(umbral=5):
    productos = Producto.objects.filter(stock__lte=umbral).order_by('stock', 'nombre')
    return [{'nombre': p.nombre, 'stock': p.stock} for p in productos]


def ventas_por_categoria():
    importe = ExpressionWrapper(F('cantidad') * F('precio_unitario'),
                                output_field=DecimalField(max_digits=10, decimal_places=2))
    # Fallo 3 corregido: filtrar solo pedidos PAGADOS (excluye pendientes y anulados).
    filas = (LineaPedido.objects
             .filter(pedido__estado=Pedido.PAGADO)
             .values('producto__categoria__nombre')
             .annotate(total=Sum(importe))
             .order_by('-total', 'producto__categoria__nombre'))
    return [{'categoria': f['producto__categoria__nombre'], 'total': f['total']} for f in filas]


def clientes_frecuentes(minimo=2):
    clientes = (Cliente.objects
                .annotate(pedidos_pagados=Count('pedidos', filter=Q(pedidos__estado=Pedido.PAGADO)))
                .filter(pedidos_pagados__gte=minimo)
                .order_by('-pedidos_pagados', 'nombre'))
    return [{'nombre': c.nombre, 'pedidos_pagados': c.pedidos_pagados} for c in clientes]


def detalle_pedido(pedido_id):
    # Fallo 4 corregido: select_related('cliente') y select_related('producto') para resolver en 2 consultas.
    pedido = Pedido.objects.select_related('cliente').filter(pk=pedido_id).first()
    if pedido is None:
        return None
    lineas = [{'producto': linea.producto.nombre, 'cantidad': linea.cantidad,
               'precio_unitario': linea.precio_unitario,
               'subtotal': linea.cantidad * linea.precio_unitario}
              for linea in pedido.lineas.select_related('producto')]
    return {'pedido': pedido.pk, 'cliente': pedido.cliente.nombre, 'estado': pedido.estado,
            'lineas': lineas, 'total': sum((linea['subtotal'] for linea in lineas), Decimal('0.00'))}
