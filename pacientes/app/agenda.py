"""App mínima del laboratorio: usa fechautil sin fijar su versión (a propósito)."""
from datetime import date

import fechautil


def dias_para(fecha_texto: str, hoy: date) -> int:
    """Cuántos días faltan para una fecha (negativo si ya pasó)."""
    objetivo = fechautil.parse(fecha_texto)
    return (hoy - objetivo).days


def describir(fecha_texto: str) -> str:
    """La fecha en formato largo, por ejemplo '5 de octubre de 2026'."""
    return fechautil.formato_largo(fechautil.parse(fecha_texto))
