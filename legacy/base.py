"""
Interfaz común que debe implementar cualquier transporte GPIB.
"""

from abc import ABC, abstractmethod


class GPIBTransport(ABC):
    """Contrato mínimo para comunicarse con un instrumento GPIB."""

    @abstractmethod
    def connect(self) -> None:
        """Abre la conexión física (socket, puerto VISA, etc.)."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Cierra la conexión."""
        raise NotImplementedError

    @abstractmethod
    def write(self, command: str) -> None:
        """Envía un comando SCPI/GPIB sin esperar respuesta."""
        raise NotImplementedError

    @abstractmethod
    def read(self) -> str:
        """Lee una respuesta pendiente del instrumento."""
        raise NotImplementedError

    def query(self, command: str) -> str:
        """Envía un comando y lee la respuesta. Por defecto: write + read."""
        self.write(command)
        return self.read()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
