"""
Lake Shore Model 218 Temperature Monitor driver (GPIB).

Typical use:

    from lakeshore218_driver import LakeShore218
    from keysight_visa import KeysightVISATransport

    transport = KeysightVISATransport(gpib_address=12)
    with LakeShore218(transport) as ls:
        print(ls.get_idn())
        print(ls.read_all_channels("K"))   # {1: ..., 2: ..., ..., 8: ...}
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum

from base import GPIBTransport

logger = logging.getLogger(__name__)


class TemperatureUnit(Enum):
    KELVIN = 1
    CELSIUS = 2
    SENSOR = 3  # unidades "raw" del sensor (V, Ohm, etc. según tipo)


class SensorType(Enum):
    """INTYPE: tipo de sensor conectado al canal (parámetro 'sensor type')."""
    DISABLED = 0
    DIODE = 1
    PLATINUM_RTD = 2
    NTC_RTD = 3


class InputRange(Enum):
    """
    Rango del canal (parámetro 'input range' de INTYPE).
    El significado depende del sensor_type; ver manual sección INTYPE.
    Para diodo:
        0 = 2.5 V
        1 = 7.5 V
    """
    DIODE_2_5V = 0
    DIODE_7_5V = 1


class AlarmSource(Enum):
    KELVIN = 1
    CELSIUS = 2
    SENSOR_UNITS = 3
    LINEAR_DATA = 4


@dataclass
class InputTypeConfig:
    """Configuración de tipo de entrada devuelta/enviada por INTYPE."""
    sensor_type: int          # 0=Disabled,1=Diode,2=PT RTD,3=NTC RTD
    autorange: bool           # 0/1 (solo aplica a RTD)
    input_range: int          # rango numérico (ver manual, depende de sensor_type)
    compensation: bool        # 0/1 compensación de corriente reversa (solo NTC RTD)
    units: int                # unidades para display: 1=Kelvin, 2=Celsius, 3=Sensor


@dataclass
class FilterConfig:
    """Configuración de filtro de promediado por canal (comando FILTER)."""
    enabled: bool
    points: int    # 2-64 puntos usados para el promedio
    window: int    # 1-10 %, ventana de datos válidos para el filtro


@dataclass
class AlarmConfig:
    """Configuración de alarma por canal (comando ALARM)."""
    enabled: bool
    high_setpoint: float
    low_setpoint: float
    deadband: float
    latch_enable: bool
    audible: bool = False
    visible: bool = False


@dataclass
class AlarmStatus:
    high_state: bool
    low_state: bool


@dataclass
class MinMaxData:
    minimum: float
    maximum: float


@dataclass
class AnalogOutputConfig:
    """Configuración de la salida analógica (comando ANALOG)."""
    channel: int          # canal de entrada asociado (1-8), 0 = ninguno
    units: int            # 1=Kelvin, 2=Celsius, 3=Sensor units, 4=Linear
    high_value: float     # valor de entrada que produce +10V (o 100% de escala)
    low_value: float      # valor de entrada que produce -10V / 0V
    manual_value: float   # valor manual si el modo es manual


@dataclass
class CurveHeader:
    name: str
    serial_number: str
    curve_data_format: int  # 1=mV/K,2=V/K,3=Ohm/K,4=log Ohm/K
    limit_kelvin: float
    coefficient: int        # 1=negative,2=positive


class LakeShore218:
    """Driver for the Lake Shore Model 218 Temperature Monitor (GPIB)."""

    SENSOR_TYPE_MAP = {0: "Disabled", 1: "Diode", 2: "Platinum RTD", 3: "NTC RTD"}
    SENSOR_TYPE_REVERSE_MAP = {v: k for k, v in SENSOR_TYPE_MAP.items()}

    # INTYPE display-unit codes <-> same unit letters as the 350 driver
    # ("S" = sensor units, 218 only).
    UNIT_MAP = {1: "K", 2: "C", 3: "S"}
    UNIT_REVERSE_MAP = {v: k for k, v in UNIT_MAP.items()}

    CHANNELS = tuple(range(1, 9))
    MIN_CHANNEL = CHANNELS[0]
    MAX_CHANNEL = CHANNELS[-1]

    _READ_COMMANDS = {"K": "KRDG?", "C": "CRDG?", "S": "SRDG?", "L": "LRDG?"}

    def __init__(self, transport: GPIBTransport, auto_connect: bool = True):
        self.transport = transport
        self._connected = False
        if auto_connect:
            self.connect()

    # Connection
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        if self._connected:
            return
        logger.info("Connecting to Lake Shore 218")
        self.transport.connect()
        self._connected = True
        try:
            idn = self.get_idn()
        except Exception:
            # The constructor never returns, so __exit__ would not run:
            # close the transport here instead of leaking the socket/VISA session.
            self.disconnect()
            raise
        logger.info("Connection established: %s", idn)

    def disconnect(self):
        if self._connected:
            logger.info("Closing connection with Lake Shore 218")
            self.transport.disconnect()
            self._connected = False

    def is_connected(self):
        """Returns True if the transport is open and the instrument responds to *IDN?."""
        if not self._connected:
            return False
        try:
            self.get_idn()
            return True
        except Exception:  # transport-specific errors are not known here
            return False

    # Low level I/O
    def _write(self, command):
        self.transport.write(command)

    def _read(self):
        return self.transport.read().strip()

    def _query(self, command):
        return self.transport.query(command).strip()

    def get_idn(self):
        """Returns the instrument identification string (*IDN?)."""
        return self._query("*IDN?")

    def reset(self):
        """IEEE-488.2 reset."""
        self._write("*RST")
        time.sleep(0.2)

    # General instrument control (218 only)
    def clear_status(self) -> None:
        """*CLS -- Limpia el registro de estado/eventos."""
        self._write("*CLS")

    def get_event_status(self) -> int:
        """*ESR? -- Lee el Event Status Register."""
        return int(self._query("*ESR?"))

    def set_event_status_enable(self, mask: int) -> None:
        """*ESE <mask> -- Configura la máscara del Event Status Enable Register."""
        self._write(f"*ESE {mask}")

    def get_event_status_enable(self) -> int:
        """*ESE? -- Lee la máscara del Event Status Enable Register."""
        return int(self._query("*ESE?"))

    def operation_complete(self) -> None:
        """*OPC -- Setea el bit OPC cuando terminan las operaciones pendientes."""
        self._write("*OPC")

    def operation_complete_query(self) -> bool:
        """*OPC? -- Devuelve '1' cuando el instrumento terminó operaciones pendientes."""
        return self._query("*OPC?").strip() == "1"

    def self_test(self) -> bool:
        """*TST? -- Ejecuta self-test. Devuelve True si hay error."""
        return bool(int(self._query("*TST?")))

    def set_beeper(self, enabled: bool) -> None:
        """BEEP <0/1> -- Habilita/deshabilita el beeper del equipo."""
        self._write(f"BEEP {self._bool_to_flag(enabled)}")

    def get_beeper(self) -> bool:
        """BEEP? -- Consulta si el beeper está habilitado."""
        return self._query("BEEP?").strip() == "1"

    def set_keypad_lock(self, enabled: bool, code: int = 123) -> None:
        """LOCK <0/1>,<code> -- Bloquea/desbloquea el teclado frontal."""
        self._write(f"LOCK {self._bool_to_flag(enabled)},{code}")

    def get_keypad_lock(self) -> tuple[bool, int]:
        """LOCK? -- Devuelve (locked, code)."""
        response = self._query("LOCK?")
        locked_str, code_str = response.split(",")
        return locked_str.strip() == "1", int(code_str)

    # Temperature readings
    def read_temperature_K(self, channel):
        """Reads temperature in Kelvin from the given channel (1-8)."""
        self._validate_channel(channel)
        return float(self._query(f"KRDG? {channel}"))

    def read_temperature_C(self, channel):
        """Reads temperature in Celsius from the given channel (1-8)."""
        self._validate_channel(channel)
        return float(self._query(f"CRDG? {channel}"))

    def read_sensor_units(self, channel):
        """SRDG? -- raw sensor reading (V, Ohm, ... depending on sensor type). 218 only."""
        self._validate_channel(channel)
        return float(self._query(f"SRDG? {channel}"))

    def read_linear(self, channel):
        """LRDG? -- reading with the linear equation applied (see set_linear_equation). 218 only."""
        self._validate_channel(channel)
        return float(self._query(f"LRDG? {channel}"))

    def read_channel(self, channel, unit="K"):
        """
        Reads one channel in "K", "C", "S" (sensor units) or "L" (linear).
        """
        self._validate_channel(channel)
        return float(self._query(f"{self._reading_command(unit)} {channel}"))

    def read_all_channels(self, unit="K"):
        """
        Returns a dict {channel: reading} for all 8 channels, in the given unit:
        "K", "C", "S" (sensor units) or "L" (linear). Uses one "xRDG? 0"
        query when it returns all 8 readings, otherwise queries each channel.
        """
        cmd = self._reading_command(unit)
        values = self._parse_floats(self._query(f"{cmd} 0"))
        if len(values) != len(self.CHANNELS):
            logger.warning(
                "%s 0 returned %d readings; retrying channels individually",
                cmd,
                len(values),
            )
            return {
                channel: self.read_channel(channel, unit)
                for channel in self.CHANNELS
            }
        return dict(zip(self.CHANNELS, values))

    def sensor_status(self, channel):
        """
        Returns the RDGST? status of the channel. 0 = reading OK (same as the
        350). Non-zero values are a bitmask; see decode_sensor_status().
        """
        self._validate_channel(channel)
        return int(self._query(f"RDGST? {channel}"))

    @staticmethod
    def decode_sensor_status(status):
        """Translates the RDGST? bitmask into readable flags."""
        return {
            "invalid_reading": bool(status & (1 << 0)),
            "old_reading": bool(status & (1 << 1)),
            "temp_underrange": bool(status & (1 << 4)),
            "temp_overrange": bool(status & (1 << 5)),
            "sensor_units_zero": bool(status & (1 << 6)),
            "sensor_units_overrange": bool(status & (1 << 7)),
        }

    # Input configuration - read
    def get_input_config(self, channel):
        """
        Reads the full configuration of an input channel (1-8).

        Returns a dict with the same keys as the 350 driver (sensor_type,
        range, curve, filter, input_name, temperature_limit, preferred_unit)
        plus the 218 extras autorange and compensation. temperature_limit
        is always None: the 218 has no TLIMIT.
        """
        self._validate_channel(channel)

        intype = [int(x) for x in self._query(f"INTYPE? {channel}").split(",")]
        sensor_type_code, autorange, range_code, compensation, unit_code = intype[:5]

        curve = int(self._query(f"INCRV? {channel}"))

        filter_cfg = self.get_filter(channel)

        return {
            "channel": channel,
            "sensor_type": self.SENSOR_TYPE_MAP.get(sensor_type_code, "Unknown"),
            "range": range_code,
            "curve": curve,
            "filter": filter_cfg,
            "input_name": self.get_input_name(channel),
            "temperature_limit": None,
            "preferred_unit": self.UNIT_MAP.get(unit_code, "Unknown"),
            "autorange": bool(autorange),
            "compensation": bool(compensation),
        }

    def get_input_name(self, channel):
        """INNAME? -- name assigned to the channel."""
        self._validate_channel(channel)
        return self._query(f"INNAME? {channel}").strip('"')

    def get_input_curve(self, channel):
        """INCRV? -- curve number assigned to the channel."""
        self._validate_channel(channel)
        return int(self._query(f"INCRV? {channel}"))

    def get_filter(self, channel):
        """FILTER? -- averaging filter as a dict {enabled, points, window}."""
        self._validate_channel(channel)
        enabled, points, window = self._query(f"FILTER? {channel}").split(",")[:3]
        return {
            "enabled": bool(int(enabled)),
            "points": int(points),
            "window": float(window),
        }

    # Input configuration - write
    def set_input_type(self, channel, sensor_type, range_code, unit="K",
                       autorange=False, compensation=False):
        """
        INTYPE. sensor_type: code or name (see SENSOR_TYPE_MAP); unit: "K",
        "C" or "S". autorange / compensation are 218 extras (defaults match
        what the 350 driver sends).
        """
        self._validate_channel(channel)
        sensor_code = self._normalize_sensor_type(sensor_type)
        unit_code = self._normalize_unit(unit)
        self._write(
            f"INTYPE {channel},{sensor_code},{self._bool_to_flag(autorange)},"
            f"{int(range_code)},{self._bool_to_flag(compensation)},{unit_code}"
        )

    def set_input_curve(self, channel, curve):
        """INCRV -- 0 = none, 1-20 = standard curves, 21-28 = user curves."""
        self._validate_channel(channel)
        self._write(f"INCRV {channel},{int(curve)}")

    def set_filter(self, channel, enabled, points, window):
        """FILTER -- averaging filter. points: 2-64, window: 1-10 (%)."""
        self._validate_channel(channel)
        if not 2 <= int(points) <= 64:
            raise ValueError("Filter points must be between 2 and 64")
        if not 1 <= float(window) <= 10:
            raise ValueError("Filter window must be between 1 and 10 (%)")
        self._write(
            f"FILTER {channel},{self._bool_to_flag(enabled)},{int(points)},{int(window)}"
        )

    def set_input_name(self, channel, name):
        """INNAME -- channel name (truncated to 15 characters)."""
        self._validate_channel(channel)
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Input name must be a non-empty string")
        self._write(f'INNAME {channel},"{name.strip()[:15]}"')

    def set_temperature_limit(self, channel, temp_limit):
        """Not available on the 218 (no TLIMIT command)."""
        raise NotImplementedError("The Lake Shore 218 has no temperature limit (TLIMIT) command")

    def set_input_config(
        self,
        channel,
        sensor_type=None,
        range_code=None,
        curve=None,
        filter_enabled=None,
        filter_points=None,
        filter_window=None,
        input_name=None,
        temperature_limit=None,
        preferred_unit=None,
        autorange=None,
        compensation=None,
    ):
        """Sets one or more input channel parameters. Unset parameters are left untouched."""
        self._validate_channel(channel)
        config = self.get_input_config(channel)

        def keep(value, key):
            return config[key] if value is None else value

        self.set_input_type(
            channel,
            keep(sensor_type, "sensor_type"),
            keep(range_code, "range"),
            keep(preferred_unit, "preferred_unit"),
            autorange=keep(autorange, "autorange"),
            compensation=keep(compensation, "compensation"),
        )

        if curve is not None:
            self.set_input_curve(channel, curve)

        if filter_enabled is not None or filter_points is not None or filter_window is not None:
            self.set_filter(
                channel,
                config["filter"]["enabled"] if filter_enabled is None else filter_enabled,
                config["filter"]["points"] if filter_points is None else filter_points,
                config["filter"]["window"] if filter_window is None else filter_window,
            )

        if input_name is not None:
            self.set_input_name(channel, input_name)

        if temperature_limit is not None:
            self.set_temperature_limit(channel, temperature_limit)

        return self.get_input_config(channel)

    def copy_input_config(self, source_channel, target_channel):
        """Copies the full input configuration from one channel to another."""
        self._validate_channel(source_channel)
        self._validate_channel(target_channel)
        if source_channel == target_channel:
            raise ValueError("Source and target channels must be different")

        src = self.get_input_config(source_channel)
        return self.set_input_config(
            target_channel,
            sensor_type=src["sensor_type"],
            range_code=src["range"],
            curve=src["curve"],
            filter_enabled=src["filter"]["enabled"],
            filter_points=src["filter"]["points"],
            filter_window=src["filter"]["window"],
            input_name=src["input_name"],
            temperature_limit=src["temperature_limit"],
            preferred_unit=src["preferred_unit"],
            autorange=src["autorange"],
            compensation=src["compensation"],
        )

    # Display (218 only)
    def set_display_field(self, field: int, channel: int, display_unit: int) -> None:
        """
        DISPFLD <campo>,<canal>,<unidad>
        field: número de campo en pantalla (1-8, depende del modo de display).
        channel: canal de entrada a mostrar en ese campo (1-8).
        display_unit: 1=Kelvin,2=Celsius,3=Sensor units,4=Linear data,
                      5=Min Data,6=Max Data.
        """
        self._write(f"DISPFLD {field},{channel},{display_unit}")

    def get_display_field(self, field: int) -> tuple[int, int]:
        """DISPFLD? <campo> -- Devuelve (canal, unidad) configurados en ese campo."""
        response = self._query(f"DISPFLD? {field}")
        channel_str, unit_str = response.split(",")
        return int(channel_str), int(unit_str)

    def set_display_mode(self, mode: int) -> None:
        """
        DISPLAY <modo> -- Modo de pantalla:
            0 = Input A (grande, 1 canal)
            1 = Input B
            ...
            (según manual, 218 soporta varios layouts; se deja como entero
            crudo para no restringir).
        """
        self._write(f"DISPLAY {mode}")

    def get_display_mode(self) -> int:
        """DISPLAY? -- Modo de pantalla actual."""
        return int(self._query("DISPLAY?"))


    # LINEAR
    def set_linear_equation(
        self, channel: int, equation: int, source: int, slope: float, offset: float
    ) -> None:
        """
        LINEAR <canal>,<equation>,<source>,<m>,<b>
        equation: 1 = mx+b, 2 = m(log10 x)+b (según manual)
        source: 1=Kelvin,2=Celsius,3=Sensor units
        Calcula LRDG usando y = m*x + b (o log) sobre la lectura fuente.
        """
        self._validate_channel(channel)
        self._write(
            f"LINEAR {channel},{equation},{source},{slope},{offset}"
        )

    def get_linear_equation(self, channel: int) -> tuple[int, int, float, float]:
        """LINEAR? <canal> -- Devuelve (equation, source, slope, offset)."""
        self._validate_channel(channel)
        response = self._query(f"LINEAR? {channel}")
        equation, source, slope, offset = response.split(",")
        return int(equation), int(source), float(slope), float(offset)

    # Alarmas
    def set_alarm(self, channel: int, config: AlarmConfig) -> None:
        """
        ALARM <canal>,<on/off>,<high>,<low>,<deadband>,<latch>,<audible>,<visible>
        Configura la alarma de un canal (se dispara si la lectura supera
        `high_setpoint` o baja de `low_setpoint`).
        """
        self._validate_channel(channel)
        self._write(
            f"ALARM {channel},"
            f"{self._bool_to_flag(config.enabled)},"
            f"{config.high_setpoint},"
            f"{config.low_setpoint},"
            f"{config.deadband},"
            f"{self._bool_to_flag(config.latch_enable)},"
            f"{self._bool_to_flag(config.audible)},"
            f"{self._bool_to_flag(config.visible)}"
        )

    def get_alarm(self, channel: int) -> AlarmConfig:
        """ALARM? <canal> -- Configuración actual de la alarma del canal."""
        self._validate_channel(channel)
        response = self._query(f"ALARM? {channel}")
        parts = response.split(",")
        enabled, high, low, deadband, latch = parts[:5]
        audible = parts[5] if len(parts) > 5 else "0"
        visible = parts[6] if len(parts) > 6 else "0"
        return AlarmConfig(
            enabled=enabled.strip() == "1",
            high_setpoint=float(high),
            low_setpoint=float(low),
            deadband=float(deadband),
            latch_enable=latch.strip() == "1",
            audible=audible.strip() == "1",
            visible=visible.strip() == "1",
        )

    def get_alarm_status(self, channel: int) -> AlarmStatus:
        """ALARMST? <canal> -- Estado actual (activo) de la alarma alta/baja."""
        self._validate_channel(channel)
        response = self._query(f"ALARMST? {channel}")
        high_state, low_state = response.split(",")
        return AlarmStatus(
            high_state=high_state.strip() == "1",
            low_state=low_state.strip() == "1",
        )

    def reset_alarm_status(self) -> None:
        """ALMRST -- Reinicia (rearma) todas las alarmas latcheadas."""
        self._write("ALMRST")


    # Min / Max
    def get_min_max(self, channel: int) -> MinMaxData:
        """MDAT? <canal> -- Valores mínimo y máximo registrados en el canal."""
        self._validate_channel(channel)
        response = self._query(f"MDAT? {channel}")
        minimum, maximum = response.split(",")
        return MinMaxData(minimum=float(minimum), maximum=float(maximum))

    def set_min_max_params(self, channel: int, enabled: bool, source: int) -> None:
        """
        MNMX <canal>,<on/off>,<source>
        source: 1=Kelvin,2=Celsius,3=Sensor units,4=Linear data.
        Habilita el registro de min/max en un canal y define qué unidad
        se usa para el cálculo.
        """
        self._validate_channel(channel)
        self._write(
            f"MNMX {channel},{self._bool_to_flag(enabled)},{source}"
        )

    def get_min_max_params(self, channel: int) -> tuple[bool, int]:
        """MNMX? <canal> -- Devuelve (enabled, source)."""
        self._validate_channel(channel)
        response = self._query(f"MNMX? {channel}")
        enabled, source = response.split(",")
        return enabled.strip() == "1", int(source)

    def reset_min_max(self, channel: int = 0) -> None:
        """MNMXRST -- Reinicia los valores min/max de todos los canales."""
        self._write("MNMXRST")

    # Salida analógica
    def set_analog_output(self, config: AnalogOutputConfig) -> None:
        """ANALOG <canal>,<unidad>,<high>,<low>,<manual> -- Configura la salida analógica."""
        self._write(
            f"ANALOG {config.channel},"
            f"{config.units},"
            f"{config.high_value},"
            f"{config.low_value},"
            f"{config.manual_value}"
        )

    def get_analog_output(self) -> AnalogOutputConfig:
        """ANALOG? -- Configuración actual de la salida analógica."""
        response = self._query("ANALOG?")
        channel, units, high, low, manual = response.split(",")
        return AnalogOutputConfig(
            channel=int(channel),
            units=int(units),
            high_value=float(high),
            low_value=float(low),
            manual_value=float(manual),
        )

    def get_analog_output_reading(self) -> float:
        """AOUT? -- Lee el valor actual de la salida analógica (%, -100 a 100)."""
        return float(self._query("AOUT?"))

    # Curvas de calibración de usuario (21-28)
    USER_CURVE_MIN = 21
    USER_CURVE_MAX = 28

    def _check_user_curve(self, curve_number: int) -> None:
        if not (self.USER_CURVE_MIN <= curve_number <= self.USER_CURVE_MAX):
            raise ValueError(
                f"Curva {curve_number} fuera de rango de curvas de usuario "
                f"({self.USER_CURVE_MIN}-{self.USER_CURVE_MAX})"
            )

    def set_curve_header(self, curve_number: int, header: CurveHeader) -> None:
        """
        CRVHDR <curva>,<nombre>,<serie>,<formato>,<límite K>,<coeficiente>
        Define el encabezado de una curva de usuario (21-28).
        """
        self._check_user_curve(curve_number)
        self._write(
            f'CRVHDR {curve_number},"{header.name[:15]}",'
            f'"{header.serial_number[:10]}",'
            f"{header.curve_data_format},"
            f"{header.limit_kelvin},"
            f"{header.coefficient}"
        )

    def get_curve_header(self, curve_number: int) -> CurveHeader:
        """CRVHDR? <curva> -- Encabezado de una curva."""
        response = self._query(f"CRVHDR? {curve_number}")
        name, serial, fmt, limit, coeff = response.split(",")
        return CurveHeader(
            name=name.strip().strip('"'),
            serial_number=serial.strip().strip('"'),
            curve_data_format=int(fmt),
            limit_kelvin=float(limit),
            coefficient=int(coeff),
        )

    def set_curve_point(self, curve_number: int, index: int, units_value: float, kelvin_value: float) -> None:
        """
        CRVPT <curva>,<índice>,<unidades>,<Kelvin>
        Define un punto (índice 1-200) de una curva de usuario.
        """
        self._check_user_curve(curve_number)
        self._write(
            f"CRVPT {curve_number},{index},{units_value},{kelvin_value}"
        )

    def get_curve_point(self, curve_number: int, index: int) -> tuple[float, float]:
        """CRVPT? <curva>,<índice> -- Devuelve (unidades, Kelvin) de un punto de curva."""
        response = self._query(f"CRVPT? {curve_number},{index}")
        units_value, kelvin_value = response.split(",")
        return float(units_value), float(kelvin_value)

    def delete_user_curve(self, curve_number: int) -> None:
        """CRVDEL <curva> -- Borra una curva de usuario."""
        self._check_user_curve(curve_number)
        self._write(f"CRVDEL {curve_number}")


    # Interfaz remota / comunicación
    def set_ieee_address(self, address: int) -> None:
        """IEEE <address> -- Cambia la dirección GPIB del equipo (requiere reinicio)."""
        if not (1 <= address <= 30):
            raise ValueError("Dirección GPIB debe estar entre 1 y 30")
        self._write(f"IEEE {address}")

    def get_ieee_address(self) -> int:
        """IEEE? -- Dirección GPIB actual configurada en el equipo."""
        return int(self._query("IEEE?"))

    def set_terminator(self, terminator: int) -> None:
        """
        TERM <terminator> -- Configura el terminador usado por la interfaz remota.
        0 = <CR><LF>, 1 = <LF><CR>, 2 = <LF>, 3 = ninguno (según manual).
        """
        self._write(f"TERM {terminator}")

    def get_terminator(self) -> int:
        """TERM? -- Terminador configurado actualmente."""
        return int(self._query("TERM?"))


    # Helpers
    @staticmethod
    def _parse_floats(response):
        return [float(v) for v in response.split(",")]

    @staticmethod
    def _bool_to_flag(value):
        return 1 if value else 0

    @classmethod
    def _validate_channel(cls, channel):
        if channel not in cls.CHANNELS or isinstance(channel, bool):
            raise ValueError(f"Invalid channel {channel!r}. Use one of {cls.CHANNELS}.")

    @staticmethod
    def _normalize_code(value, code_map, reverse_map, what):
        if isinstance(value, int):
            if value not in code_map:
                raise ValueError(f"Invalid {what} code")
            return value
        if isinstance(value, str):
            value = value.strip()
            if value.isdigit():
                return LakeShore218._normalize_code(int(value), code_map, reverse_map, what)
            if value not in reverse_map:
                raise ValueError(f"Invalid {what} name")
            return reverse_map[value]
        raise ValueError(f"{what.capitalize()} must be an int or a valid string")

    @classmethod
    def _reading_command(cls, unit):
        if isinstance(unit, TemperatureUnit):
            unit = cls.UNIT_MAP[unit.value]
        cmd = cls._READ_COMMANDS.get(str(unit).strip().upper())
        if cmd is None:
            raise ValueError(
                f"Invalid unit {unit!r}. Use one of {tuple(cls._READ_COMMANDS)}."
            )
        return cmd

    def _normalize_sensor_type(self, sensor_type):
        if isinstance(sensor_type, SensorType):
            return sensor_type.value
        return self._normalize_code(
            sensor_type, self.SENSOR_TYPE_MAP, self.SENSOR_TYPE_REVERSE_MAP, "sensor type"
        )

    def _normalize_unit(self, unit):
        if isinstance(unit, TemperatureUnit):
            return unit.value
        if isinstance(unit, str):
            unit = unit.strip().upper()
        return self._normalize_code(unit, self.UNIT_MAP, self.UNIT_REVERSE_MAP, "unit")


# Backwards-compatible name used by the previous version of this driver.
Lakeshore218 = LakeShore218
