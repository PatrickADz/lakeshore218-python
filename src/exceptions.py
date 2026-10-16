"""Excepciones públicas del driver Lakeshore 218."""


class Lakeshore218Error(Exception):
    """Error base del driver Lakeshore 218."""


class Lakeshore218ValidationError(Lakeshore218Error, ValueError):
    """Error de validación de un parámetro del instrumento."""
