"""
Driver Lakeshore Model 218 Temperature Monitor.

Uso típico:

    from lakeshore218 import Lakeshore218
    from keysight_visa import KeysightVISATransport

    transport = KeysightVISATransport(gpib_address=12)
    with Lakeshore218(transport) as ls:
        print(ls.idn())
        print(ls.get_all_temperatures_kelvin())
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from base import GPIBTransport


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
    Para RTD (platino / NTC) hay varios rangos (0-8 aprox, depende de escala).
    Se deja como int crudo para no perder flexibilidad; estos son solo
    ejemplos comunes.
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
class FilterConfig:
    """Configuración de filtro de promediado por canal (comando FILTER)."""
    enabled: bool
    points: int    # 2-64 puntos usados para el promedio
    window: int    # 1-10 %, ventana de datos válidos para el filtro


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


# --------------------------------------------------------------------------
# Driver principal
# --------------------------------------------------------------------------

class Lakeshore218:
    """
    Driver de alto nivel para el Lakeshore 218.

    Todos los métodos asumen que `transport` ya implementa GPIBTransport
    (conexión, write, read, query). El objeto puede usarse como context
    manager para abrir/cerrar la conexión automáticamente.
    """

    MIN_CHANNEL = 1
    MAX_CHANNEL = 8

    def __init__(self, transport: GPIBTransport):
        self.transport = transport

    def __enter__(self):
        self.transport.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.transport.disconnect()

    # ----------------------------------------------------------------
    # Utilidades internas
    # ----------------------------------------------------------------

    def _check_channel(self, channel: int, allow_zero: bool = False) -> None:
        lo = 0 if allow_zero else self.MIN_CHANNEL
        if not (lo <= channel <= self.MAX_CHANNEL):
            raise ValueError(
                f"Canal {channel} fuera de rango "
                f"({lo}-{self.MAX_CHANNEL})"
            )

    @staticmethod
    def _parse_floats(response: str) -> list[float]:
        return [float(v) for v in response.split(",")]

    @staticmethod
    def _bool_to_flag(value: bool) -> int:
        return 1 if value else 0

    # ----------------------------------------------------------------
    # Identificación / control general del instrumento
    # ----------------------------------------------------------------

    def idn(self) -> str:
        """*IDN? -- Identifica el equipo (fabricante, modelo, serie, firmware)."""
        return self.transport.query("*IDN?")

    def reset(self) -> None:
        """*RST -- Regresa el instrumento a su configuración por defecto."""
        self.transport.write("*RST")

    def clear_status(self) -> None:
        """*CLS -- Limpia el registro de estado/eventos."""
        self.transport.write("*CLS")

    def get_event_status(self) -> int:
        """*ESR? -- Lee el Event Status Register."""
        return int(self.transport.query("*ESR?"))

    def set_event_status_enable(self, mask: int) -> None:
        """*ESE <mask> -- Configura la máscara del Event Status Enable Register."""
        self.transport.write(f"*ESE {mask}")

    def get_event_status_enable(self) -> int:
        """*ESE? -- Lee la máscara del Event Status Enable Register."""
        return int(self.transport.query("*ESE?"))

    def operation_complete(self) -> None:
        """*OPC -- Setea el bit OPC cuando terminan las operaciones pendientes."""
        self.transport.write("*OPC")

    def operation_complete_query(self) -> bool:
        """*OPC? -- Devuelve '1' cuando el instrumento terminó operaciones pendientes."""
        return self.transport.query("*OPC?").strip() == "1"

    def self_test(self) -> bool:
        """*TST? -- Ejecuta self-test. Devuelve True si hay error."""
        return bool(int(self.transport.query("*TST?")))

    def set_beeper(self, enabled: bool) -> None:
        """BEEP <0/1> -- Habilita/deshabilita el beeper del equipo."""
        self.transport.write(f"BEEP {self._bool_to_flag(enabled)}")

    def get_beeper(self) -> bool:
        """BEEP? -- Consulta si el beeper está habilitado."""
        return self.transport.query("BEEP?").strip() == "1"

    def set_keypad_lock(self, enabled: bool, code: int = 123) -> None:
        """LOCK <0/1>,<code> -- Bloquea/desbloquea el teclado frontal."""
        self.transport.write(f"LOCK {self._bool_to_flag(enabled)},{code}")

    def get_keypad_lock(self) -> tuple[bool, int]:
        """LOCK? -- Devuelve (locked, code)."""
        response = self.transport.query("LOCK?")
        locked_str, code_str = response.split(",")
        return locked_str.strip() == "1", int(code_str)

    # ----------------------------------------------------------------
    # Lecturas de temperatura / sensor
    # ----------------------------------------------------------------

    def get_temperature_kelvin(self, channel: int) -> float:
        """KRDG? <canal> -- Temperatura en Kelvin de un canal (1-8)."""
        self._check_channel(channel)
        response = self.transport.query(f"KRDG? {channel}")
        return float(response)

    def get_all_temperatures_kelvin(self) -> list[float]:
        """KRDG? 0 -- Temperatura en Kelvin de los 8 canales."""
        response = self.transport.query("KRDG? 0")
        return self._parse_floats(response)

    def get_temperature_celsius(self, channel: int) -> float:
        """CRDG? <canal> -- Temperatura en Celsius de un canal (1-8)."""
        self._check_channel(channel)
        response = self.transport.query(f"CRDG? {channel}")
        return float(response)

    def get_all_temperatures_celsius(self) -> list[float]:
        """CRDG? 0 -- Temperatura en Celsius de los 8 canales."""
        response = self.transport.query("CRDG? 0")
        return self._parse_floats(response)

    def get_sensor_reading(self, channel: int) -> float:
        """SRDG? <canal> -- Lectura cruda del sensor (V, Ohm, etc. según tipo)."""
        self._check_channel(channel)
        response = self.transport.query(f"SRDG? {channel}")
        return float(response)

    def get_all_sensor_readings(self) -> list[float]:
        """SRDG? 0 -- Lectura cruda de los 8 canales."""
        response = self.transport.query("SRDG? 0")
        return self._parse_floats(response)

    def get_linear_reading(self, channel: int) -> float:
        """LRDG? <canal> -- Lectura con ecuación lineal aplicada (ver LINEAR)."""
        self._check_channel(channel)
        response = self.transport.query(f"LRDG? {channel}")
        return float(response)

    def get_all_linear_readings(self) -> list[float]:
        """LRDG? 0 -- Lectura lineal de los 8 canales."""
        response = self.transport.query("LRDG? 0")
        return self._parse_floats(response)

    def get_reading(self, channel: int, unit: TemperatureUnit) -> float:
        """Atajo genérico: lee un canal en la unidad indicada."""
        if unit is TemperatureUnit.KELVIN:
            return self.get_temperature_kelvin(channel)
        if unit is TemperatureUnit.CELSIUS:
            return self.get_temperature_celsius(channel)
        return self.get_sensor_reading(channel)

    def get_all_readings(self, unit: TemperatureUnit) -> list[float]:
        """Atajo genérico: lee los 8 canales en la unidad indicada."""
        if unit is TemperatureUnit.KELVIN:
            return self.get_all_temperatures_kelvin()
        if unit is TemperatureUnit.CELSIUS:
            return self.get_all_temperatures_celsius()
        return self.get_all_sensor_readings()

    def get_reading_status(self, channel: int) -> int:
        """
        RDGST? <canal> -- Bitmask de estado de la lectura del canal:
            bit 0: reading overflow (128 en bitmask real, ver manual, se
                   devuelve el entero crudo para que el usuario decodifique)
            bit 4: over range
            bit 5: under range
            bit 6: sensor open (T.OVER)
            bit 7: sensor short (T.UNDER)
        Se deja como entero crudo; usar `decode_reading_status` para
        una interpretación legible.
        """
        self._check_channel(channel)
        return int(self.transport.query(f"RDGST? {channel}"))

    @staticmethod
    def decode_reading_status(status: int) -> dict[str, bool]:
        """Traduce el bitmask de RDGST? a flags legibles."""
        return {
            "invalid_reading": bool(status & (1 << 0)),
            "old_reading": bool(status & (1 << 1)),
            "temp_underrange": bool(status & (1 << 4)),
            "temp_overrange": bool(status & (1 << 5)),
            "sensor_units_zero": bool(status & (1 << 6)),
            "sensor_units_overrange": bool(status & (1 << 7)),
        }

    # ----------------------------------------------------------------
    # Configuración de entradas (canales)
    # ----------------------------------------------------------------

    def set_input_name(self, channel: int, name: str) -> None:
        """INNAME <canal>,<nombre> -- Asigna un nombre (hasta 15 chars) al canal."""
        self._check_channel(channel)
        self.transport.write(f'INNAME {channel},"{name[:15]}"')

    def get_input_name(self, channel: int) -> str:
        """INNAME? <canal> -- Nombre asignado al canal."""
        self._check_channel(channel)
        return self.transport.query(f"INNAME? {channel}").strip().strip('"')

    def set_input_type(self, channel: int, config: InputTypeConfig) -> None:
        """
        INTYPE <canal>,<sensor_type>,<autorange>,<range>,<compensation>,<units>
        Configura el tipo de sensor conectado a un canal.
        """
        self._check_channel(channel)
        self.transport.write(
            f"INTYPE {channel},"
            f"{config.sensor_type},"
            f"{self._bool_to_flag(config.autorange)},"
            f"{config.input_range},"
            f"{self._bool_to_flag(config.compensation)},"
            f"{config.units}"
        )

    def get_input_type(self, channel: int) -> InputTypeConfig:
        """INTYPE? <canal> -- Configuración actual del tipo de sensor."""
        self._check_channel(channel)
        response = self.transport.query(f"INTYPE? {channel}")
        sensor_type, autorange, in_range, compensation, units = response.split(",")
        return InputTypeConfig(
            sensor_type=int(sensor_type),
            autorange=autorange.strip() == "1",
            input_range=int(in_range),
            compensation=compensation.strip() == "1",
            units=int(units),
        )

    def set_input_curve(self, channel: int, curve_number: int) -> None:
        """
        INCRV <canal>,<curva> -- Asigna la curva de calibración a un canal.
        curve_number: 0 = ninguna, 1-20 = curvas estándar, 21-28 = curvas de usuario.
        """
        self._check_channel(channel)
        self.transport.write(f"INCRV {channel},{curve_number}")

    def get_input_curve(self, channel: int) -> int:
        """INCRV? <canal> -- Número de curva asignada al canal."""
        self._check_channel(channel)
        return int(self.transport.query(f"INCRV? {channel}"))

    # ----------------------------------------------------------------
    # Unidades de display
    # ----------------------------------------------------------------

    def set_display_field_units(self, channel: int, unit: TemperatureUnit) -> None:
        """
        DISPFLD <campo>,<canal>,<unidad> simplificado: usa TUNITS para setear
        la unidad de temperatura preferida de un canal cuando se lo consulta
        vía KRDG/CRDG (esto es más un helper conceptual: el 218 realmente
        expone la unidad de display vía DISPFLD, ver `set_display_field`).
        """
        raise NotImplementedError(
            "Usa set_display_field() para configurar unidades por campo "
            "de pantalla, o simplemente llama get_temperature_kelvin / "
            "get_temperature_celsius / get_sensor_reading según necesites."
        )

    def set_display_field(self, field: int, channel: int, display_unit: int) -> None:
        """
        DISPFLD <campo>,<canal>,<unidad>
        field: número de campo en pantalla (1-8, depende del modo de display).
        channel: canal de entrada a mostrar en ese campo (1-8).
        display_unit: 1=Kelvin,2=Celsius,3=Sensor units,4=Linear data,
                      5=Min Data,6=Max Data.
        """
        self.transport.write(f"DISPFLD {field},{channel},{display_unit}")

    def get_display_field(self, field: int) -> tuple[int, int]:
        """DISPFLD? <campo> -- Devuelve (canal, unidad) configurados en ese campo."""
        response = self.transport.query(f"DISPFLD? {field}")
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
        self.transport.write(f"DISPLAY {mode}")

    def get_display_mode(self) -> int:
        """DISPLAY? -- Modo de pantalla actual."""
        return int(self.transport.query("DISPLAY?"))

    # ----------------------------------------------------------------
    # Filtro de promediado
    # ----------------------------------------------------------------

    def set_filter(self, channel: int, config: FilterConfig) -> None:
        """FILTER <canal>,<on/off>,<points>,<window> -- Configura filtro de promediado."""
        self._check_channel(channel)
        self.transport.write(
            f"FILTER {channel},"
            f"{self._bool_to_flag(config.enabled)},"
            f"{config.points},"
            f"{config.window}"
        )

    def get_filter(self, channel: int) -> FilterConfig:
        """FILTER? <canal> -- Configuración de filtro del canal."""
        self._check_channel(channel)
        response = self.transport.query(f"FILTER? {channel}")
        enabled, points, window = response.split(",")
        return FilterConfig(
            enabled=enabled.strip() == "1",
            points=int(points),
            window=int(window),
        )

    # ----------------------------------------------------------------
    # Ecuación lineal (LINEAR)
    # ----------------------------------------------------------------

    def set_linear_equation(
        self, channel: int, equation: int, source: int, slope: float, offset: float
    ) -> None:
        """
        LINEAR <canal>,<equation>,<source>,<m>,<b>
        equation: 1 = mx+b, 2 = m(log10 x)+b (según manual)
        source: 1=Kelvin,2=Celsius,3=Sensor units
        Calcula LRDG usando y = m*x + b (o log) sobre la lectura fuente.
        """
        self._check_channel(channel)
        self.transport.write(
            f"LINEAR {channel},{equation},{source},{slope},{offset}"
        )

    def get_linear_equation(self, channel: int) -> tuple[int, int, float, float]:
        """LINEAR? <canal> -- Devuelve (equation, source, slope, offset)."""
        self._check_channel(channel)
        response = self.transport.query(f"LINEAR? {channel}")
        equation, source, slope, offset = response.split(",")
        return int(equation), int(source), float(slope), float(offset)

    # ----------------------------------------------------------------
    # Alarmas
    # ----------------------------------------------------------------

    def set_alarm(self, channel: int, config: AlarmConfig) -> None:
        """
        ALARM <canal>,<on/off>,<high>,<low>,<deadband>,<latch>,<audible>,<visible>
        Configura la alarma de un canal (se dispara si la lectura supera
        `high_setpoint` o baja de `low_setpoint`).
        """
        self._check_channel(channel)
        self.transport.write(
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
        self._check_channel(channel)
        response = self.transport.query(f"ALARM? {channel}")
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
        self._check_channel(channel)
        response = self.transport.query(f"ALARMST? {channel}")
        high_state, low_state = response.split(",")
        return AlarmStatus(
            high_state=high_state.strip() == "1",
            low_state=low_state.strip() == "1",
        )

    def reset_alarm_status(self) -> None:
        """ALMRST -- Reinicia (rearma) todas las alarmas latcheadas."""
        self.transport.write("ALMRST")

    # ----------------------------------------------------------------
    # Min / Max
    # ----------------------------------------------------------------

    def get_min_max(self, channel: int) -> MinMaxData:
        """MDAT? <canal> -- Valores mínimo y máximo registrados en el canal."""
        self._check_channel(channel)
        response = self.transport.query(f"MDAT? {channel}")
        minimum, maximum = response.split(",")
        return MinMaxData(minimum=float(minimum), maximum=float(maximum))

    def set_min_max_params(self, channel: int, enabled: bool, source: int) -> None:
        """
        MNMX <canal>,<on/off>,<source>
        source: 1=Kelvin,2=Celsius,3=Sensor units,4=Linear data.
        Habilita el registro de min/max en un canal y define qué unidad
        se usa para el cálculo.
        """
        self._check_channel(channel)
        self.transport.write(
            f"MNMX {channel},{self._bool_to_flag(enabled)},{source}"
        )

    def get_min_max_params(self, channel: int) -> tuple[bool, int]:
        """MNMX? <canal> -- Devuelve (enabled, source)."""
        self._check_channel(channel)
        response = self.transport.query(f"MNMX? {channel}")
        enabled, source = response.split(",")
        return enabled.strip() == "1", int(source)

    def reset_min_max(self, channel: int = 0) -> None:
        """MNMXRST -- Reinicia los valores min/max de todos los canales."""
        self.transport.write("MNMXRST")

    # ----------------------------------------------------------------
    # Salida analógica
    # ----------------------------------------------------------------

    def set_analog_output(self, config: AnalogOutputConfig) -> None:
        """ANALOG <canal>,<unidad>,<high>,<low>,<manual> -- Configura la salida analógica."""
        self.transport.write(
            f"ANALOG {config.channel},"
            f"{config.units},"
            f"{config.high_value},"
            f"{config.low_value},"
            f"{config.manual_value}"
        )

    def get_analog_output(self) -> AnalogOutputConfig:
        """ANALOG? -- Configuración actual de la salida analógica."""
        response = self.transport.query("ANALOG?")
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
        return float(self.transport.query("AOUT?"))

    # ----------------------------------------------------------------
    # Curvas de calibración de usuario (21-28)
    # ----------------------------------------------------------------

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
        self.transport.write(
            f'CRVHDR {curve_number},"{header.name[:15]}",'
            f'"{header.serial_number[:10]}",'
            f"{header.curve_data_format},"
            f"{header.limit_kelvin},"
            f"{header.coefficient}"
        )

    def get_curve_header(self, curve_number: int) -> CurveHeader:
        """CRVHDR? <curva> -- Encabezado de una curva."""
        response = self.transport.query(f"CRVHDR? {curve_number}")
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
        self.transport.write(
            f"CRVPT {curve_number},{index},{units_value},{kelvin_value}"
        )

    def get_curve_point(self, curve_number: int, index: int) -> tuple[float, float]:
        """CRVPT? <curva>,<índice> -- Devuelve (unidades, Kelvin) de un punto de curva."""
        response = self.transport.query(f"CRVPT? {curve_number},{index}")
        units_value, kelvin_value = response.split(",")
        return float(units_value), float(kelvin_value)

    def delete_user_curve(self, curve_number: int) -> None:
        """CRVDEL <curva> -- Borra una curva de usuario."""
        self._check_user_curve(curve_number)
        self.transport.write(f"CRVDEL {curve_number}")

    # ----------------------------------------------------------------
    # Interfaz remota / comunicación
    # ----------------------------------------------------------------

    def set_ieee_address(self, address: int) -> None:
        """IEEE <address> -- Cambia la dirección GPIB del equipo (requiere reinicio)."""
        if not (1 <= address <= 30):
            raise ValueError("Dirección GPIB debe estar entre 1 y 30")
        self.transport.write(f"IEEE {address}")

    def get_ieee_address(self) -> int:
        """IEEE? -- Dirección GPIB actual configurada en el equipo."""
        return int(self.transport.query("IEEE?"))

    def set_terminator(self, terminator: int) -> None:
        """
        TERM <terminator> -- Configura el terminador usado por la interfaz remota.
        0 = <CR><LF>, 1 = <LF><CR>, 2 = <LF>, 3 = ninguno (según manual).
        """
        self.transport.write(f"TERM {terminator}")

    def get_terminator(self) -> int:
        """TERM? -- Terminador configurado actualmente."""
        return int(self.transport.query("TERM?"))

    # ----------------------------------------------------------------
    # Snapshot de alto nivel: útil para logging / dataframes
    # ----------------------------------------------------------------

    def get_snapshot(self, unit: TemperatureUnit = TemperatureUnit.KELVIN) -> dict[int, float]:
        """
        Devuelve un dict {canal: lectura} para los 8 canales, en la unidad
        indicada. Pensado para loguear datos periódicamente.
        """
        readings = self.get_all_readings(unit)
        return {ch: val for ch, val in zip(range(1, self.MAX_CHANNEL + 1), readings)}
