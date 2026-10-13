"""
Transporte GPIB para el adaptador Keysight USB-GPIB (82357B y similares).

Usa PyVISA, que se apoya en las Keysight IO Libraries (VISA) instaladas
en el sistema. Requiere que el adaptador ya aparezca en Keysight
Connection Expert / NI MAX con su GPIB address.
"""

from base import GPIBTransport


import pyvisa


class KeysightVISATransport(GPIBTransport):
    def __init__(self, gpib_address: int, board_index: int = 0, timeout_ms: int = 5000):
        """
        gpib_address: dirección GPIB del Lakeshore 218 (la que configuraste
                       en el instrumento, ej. 12).
        board_index:  número de la tarjeta/adaptador GPIB (normalmente 0).
        """
        self.resource_string = f"GPIB{board_index}::{gpib_address}::INSTR"
        self.timeout_ms = timeout_ms
        self._rm = None
        self._inst = None

    def connect(self) -> None:
        self._rm = pyvisa.ResourceManager()
        self._inst = self._rm.open_resource(self.resource_string)
        self._inst.timeout = self.timeout_ms
        self._inst.read_termination = "\r\n"
        self._inst.write_termination = "\n"

    def disconnect(self) -> None:
        if self._inst is not None:
            self._inst.close()
        if self._rm is not None:
            self._rm.close()

    def write(self, command: str) -> None:
        self._inst.write(command)

    def read(self) -> str:
        return self._inst.read()

    def query(self, command: str) -> str:
        return self._inst.query(command)
