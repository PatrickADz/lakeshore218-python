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
        socket_margin_s: float = 2.0,
        read_until: str = "eoi",
    ):
        """
        ip_address:      IP del adaptador Prologix en la red.
        gpib_address:    dirección GPIB del Lakeshore 218 (ej. 12).
        timeout_s:       tiempo que el Prologix espera la respuesta del
                         instrumento (++read_tmo_ms).
        socket_margin_s: margen extra del socket sobre timeout_s. Debe ser
                         > 0: si ambos timeouts son iguales, el socket se rinde
                         justo antes de que el Prologix entregue la respuesta,
                         read() devolvía vacío y esa respuesta se leía como la
                         de la consulta siguiente (desfase de una respuesta).
        read_until:      argumento de ++read: "eoi" (por defecto) o "10" para
                         leer hasta LF si el instrumento no asierta EOI.
        """
        self.ip_address = ip_address
        self.port = port
        self.gpib_address = gpib_address
        self.timeout_s = timeout_s
        self.read_until = str(read_until)
        self._socket_timeout_s = timeout_s + socket_margin_s
        self._sock = None

    def connect(self) -> None:
        self._sock = socket.create_connection(
            (self.ip_address, self.port), timeout=self.timeout_s
        )
        self._sock.settimeout(self._socket_timeout_s)

        # Configuración del adaptador: modo controlador, apuntar al
        # instrumento correcto. IMPORTANTE: se usó modo MANUAL (++auto 0)
        # en vez de ++auto 1. 
        # Con auto=1 el Prologix intenta leer unarespuesta después de CADA comando
        # incluidos los de escritura
        # pura (*RST, ALARM, FILTER, INNAME, etc.) que el 218 no responde,
        # lo que genera timeouts internos intermitentes y riesgo de leer
        # datos desincronizados en la siguiente consulta real.

        self._send_raw("++mode 1")       # Prologix como controlador
        self._send_raw("++auto 0")       # modo manual
        self._send_raw(f"++addr {self.gpib_address}")
        self._send_raw("++eos 0")        # terminador CR+LF que requiere el 218
        self._send_raw("++eoi 1")        # asertar EOI al final de cada write
        self._send_raw(f"++read_tmo_ms {int(self.timeout_s * 1000)}")
        self._drain()

    def disconnect(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def _send_raw(self, line: str) -> None:
        self._sock.sendall((line + "\n").encode("ascii"))

    def write(self, command: str) -> None:
        """Envía un comando sin pedir lectura (para comandos que no responden)."""
        self._send_raw(command)

    def _drain(self) -> None:
        """Descarta bytes viejos del socket para no confundirlos con la próxima respuesta."""
        self._sock.settimeout(0.05)
        try:
            while self._sock.recv(4096):
                pass
        except (socket.timeout, BlockingIOError):
            pass
        finally:
            self._sock.settimeout(self._socket_timeout_s)

    def read(self) -> str:
        """
        Pide la respuesta pendiente del instrumento (++read eoi) y la devuelve.
        Lanza TimeoutError si no llega una respuesta completa: devolver vacío
        en silencio deja la respuesta atrasada en el buffer y la siguiente
        consulta lee los datos de la anterior.
        """
        self._send_raw(f"++read {self.read_until}")
        chunks = []
        try:
            while True:
                data = self._sock.recv(4096)
                if not data:
                    raise ConnectionError("El Prologix cerró la conexión")
                chunks.append(data)
                if data.endswith(b"\n"):
                    break
        except socket.timeout:
            partial = b"".join(chunks).decode("ascii", errors="replace").strip()
            raise TimeoutError(
                f"Sin respuesta completa del instrumento (GPIB {self.gpib_address}) "
                f"en {self._socket_timeout_s:.1f} s"
                + (f"; datos parciales: {partial!r}" if partial else "")
            ) from None
        return b"".join(chunks).decode("ascii", errors="replace").strip()

    def query(self, command: str) -> str:
        self._drain()
        self.write(command)
        return self.read()
