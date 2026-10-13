"""
Transporte GPIB para el adaptador Prologix GPIB-ETHERNET.

El Prologix no habla VISA: expone un socket TCP (puerto 1234 por
defecto) donde se le mandan comandos de control con prefijo "++"
mezclados con los comandos GPIB normales que van directo al
instrumento.

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
        # instrumento correcto, y pedirle que gestione el "read after write"
        # automáticamente (evita tener que mandar ++read a cada rato).
        self._send_raw("++mode 1")       # Prologix como controlador
        self._send_raw("++auto 1")       # auto-lee tras cada comando
        self._send_raw(f"++addr {self.gpib_address}")
        self._send_raw("++eos 2")        # terminador que agrega el Prologix: \r\n -> LF
        self._send_raw("++eoi 1")        # asertar EOI al final de cada write

    def disconnect(self) -> None:
        if self._sock is not None:
            self._sock.close()

    def _send_raw(self, line: str) -> None:
        self._sock.sendall((line + "\n").encode("ascii"))

    def write(self, command: str) -> None:
        self._send_raw(command)

    def read(self) -> str:
        # Con ++auto 1 el Prologix ya hace polling del instrumento tras
        # el write, así que basta con leer lo que llegue al socket.
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
