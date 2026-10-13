"""
Driver Lakeshore Model 218 Temperature Monitor.
"""

from base import GPIBTransport


class Lakeshore218:
    def __init__(self, transport: GPIBTransport):
        self.transport = transport

    def __enter__(self):
        self.transport.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.transport.disconnect()

    # --- Comunicación básica ---

    def idn(self) -> str:
        """Consulta *IDN? para verificar que el equipo responde."""
        return self.transport.query("*IDN?")

    def get_temperature_kelvin(self, channel: int) -> float:
        """
        Lee la temperatura en Kelvin de un canal (1-8).
        Comando SCPI del 218: KRDG? <canal>
        """
        response = self.transport.query(f"KRDG? {channel}")
        return float(response)

    def get_all_temperatures_kelvin(self) -> list[float]:
        """Lee los 8 canales de una vez (KRDG? 0 devuelve todos separados por coma)."""
        response = self.transport.query("KRDG? 0")
        return [float(v) for v in response.split(",")]

    def get_sensor_reading(self, channel: int) -> float:
        """Lectura cruda del sensor (unidades del sensor). Comando: SRDG? <canal>"""
        response = self.transport.query(f"SRDG? {channel}")
        return float(response)
