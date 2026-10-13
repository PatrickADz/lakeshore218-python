"""
Transporte GPIB para el adaptador Prologix GPIB-ETHERNET.

Referencia: "Prologix GPIB-ETHERNET Controller User Manual".
"""

import socket

from base import GPIBTransport


class PrologixEthernetTransport(GPIBTransport):
    def __init__(
        self,
        ip_address: str,
        gpib_address: int,
        port: int = 1234,
        timeout_s: float = 5.0,
    ):
        """
        ip_address:   IP del adaptador Prologix en la red.
        gpib_address: dirección GPIB del Lakeshore 218 (ej. 12).
        """
        self.ip_address = ip_address
        self.port = port
        self.gpib_address = gpib_address
        self.timeout_s = timeout_s
        self._sock = None

    def connect(self) -> None:
        self._sock = socket.create_connection(
            (self.ip_address, self.port), timeout=self.timeout_s
        )
        self._sock.settimeout(self.timeout_s)

        # Configuración del adaptador: modo controlador, apuntar al
        # instrumento correcto. IMPORTANTE: se usa modo MANUAL (++auto 0)
        # en vez de ++auto 1. 
        # Con auto=1 el Prologix intenta leer una
        # respuesta después de CADA comando -- incluidos los de escritura
        # pura (*RST, ALARM, FILTER, INNAME, etc.) que el 218 no responde,
        # lo que genera timeouts internos intermitentes y riesgo de leer
        # datos desincronizados en la siguiente consulta real. 
        # En modo manual, se puede decidir explícitamente cuándo pedir lectura
        self._send_raw("++mode 1")       # Prologix como controlador
        self._send_raw("++auto 0")       # modo manual
        self._send_raw(f"++addr {self.gpib_address}")
        self._send_raw("++eos 2")        # terminador que agrega el Prologix
        self._send_raw("++eoi 1")        # asertar EOI al final de cada write
        self._send_raw(f"++read_tmo_ms {int(self.timeout_s * 1000)}")

    def disconnect(self) -> None:
        if self._sock is not None:
            self._sock.close()

    def _send_raw(self, line: str) -> None:
        self._sock.sendall((line + "\n").encode("ascii"))

    def write(self, command: str) -> None:
        """Envía un comando sin pedir lectura (para comandos que no responden)."""
        self._send_raw(command)

    def read(self) -> str:
        """
        Pide explícitamente al Prologix que lea la respuesta pendiente del
        instrumento (++read eoi) y devuelve lo que llegue por el socket.
        Solo debe llamarse cuando el comando previo espera una respuesta.
        """
        self._send_raw("++read eoi")
        chunks = []
        try:
            while True:
                data = self._sock.recv(4096)
                if not data:
                    break
                chunks.append(data)
                if data.endswith(b"\n"):
                    break
        except socket.timeout:
            pass
        return b"".join(chunks).decode("ascii", errors="replace").strip()

    def query(self, command: str) -> str:
        self.write(command)
        return self.read()
