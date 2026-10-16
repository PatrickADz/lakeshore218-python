# Arquitectura

## Diagrama de dependencias

```
                    ┌─────────────────────┐
                    │   base.py            │
                    │   GPIBTransport (ABC)│
                    │   - connect()         │
                    │   - disconnect()      │
                    │   - write(cmd)         │
                    │   - read() -> str      │
                    │   - query(cmd) -> str  │  (default: write+read)
                    └──────────┬───────────┘
                               │ implementa
             ┌─────────────────┴─────────────────┐
             │                                     │
  ┌──────────▼───────────┐            ┌───────────▼────────────┐
  │ keysight_visa.py       │            │ prologix_ethernet.py    │
  │ KeysightVISATransport  │            │ PrologixEthernetTransport│
  │ (usa pyvisa)            │            │ (usa socket TCP)         │
  └──────────┬───────────┘            └───────────┬────────────┘
             │                                     │
             └──────────────────┬──────────────────┘
                                 │ se inyecta como `transport`
                     ┌───────────▼────────────┐
                     │   lakeshore218.py        │
                     │   Lakeshore218            │
                     │   (driver del instrumento)│
                     └───────────┬────────────┘
                                 │ usado por
                     ┌───────────▼────────────┐
                     │   cli.py                  │
                     │   (herramienta de terminal)│
                     └────────────────────────┘
```

**Regla de oro:** las flechas solo van hacia abajo. `lakeshore218.py`
nunca importa `pyvisa` ni `socket`. `cli.py` es el único que decide
*qué* transporte instanciar.

## `base.py` — el contrato

```python
class GPIBTransport(ABC):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def write(self, command: str) -> None: ...
    def read(self) -> str: ...
    def query(self, command: str) -> str: ...  # default: write + read
```

Cualquier adaptador nuevo (ej. un futuro NI-GPIB, otro Ethernet, etc.)
solo necesita subclasear esto e implementar los 4 métodos abstractos.
`Lakeshore218` no requiere ningún cambio.

## `lakeshore218.py` — mapa de métodos por categoría

Para navegar rápido sin tener que leer el archivo completo. Los nombres
coinciden con los comandos SCPI reales entre paréntesis.

### Identificación / sistema
- `idn()` (`*IDN?`)
- `reset()` (`*RST`)
- `clear_status()` (`*CLS`)
- `get_event_status()` / `set_event_status_enable()` / `get_event_status_enable()` (`*ESR?`, `*ESE`)
- `operation_complete()` / `operation_complete_query()` (`*OPC`)
- `self_test()` (`*TST?`)
- `set_beeper()` / `get_beeper()` (`BEEP`)
- `set_keypad_lock()` / `get_keypad_lock()` (`LOCK`)

### Lecturas de temperatura / sensor
- `get_temperature_kelvin(ch)` / `get_all_temperatures_kelvin()` (`KRDG?`)
- `get_temperature_celsius(ch)` / `get_all_temperatures_celsius()` (`CRDG?`)
- `get_sensor_reading(ch)` / `get_all_sensor_readings()` (`SRDG?`)
- `get_linear_reading(ch)` / `get_all_linear_readings()` (`LRDG?`)
- `get_reading(ch, unit)` / `get_all_readings(unit)` → atajos genéricos por `TemperatureUnit`
- `get_reading_status(ch)` + `decode_reading_status(status)` (`RDGST?`)
- `get_snapshot(unit)` → dict `{canal: valor}` para logging

### Configuración de canales
- `set_input_name()` / `get_input_name()` (`INNAME`)
- `set_input_type()` / `get_input_type()` (`INTYPE`) — usa `InputTypeConfig`
- `set_input_curve()` / `get_input_curve()` (`INCRV`)

### Display
- `set_display_field()` / `get_display_field()` (`DISPFLD`)
- `set_display_mode()` / `get_display_mode()` (`DISPLAY`)

### Filtro de promediado
- `set_filter()` / `get_filter()` (`FILTER`) — usa `FilterConfig`

### Ecuación lineal
- `set_linear_equation()` / `get_linear_equation()` (`LINEAR`)

### Alarmas
- `set_alarm()` / `get_alarm()` (`ALARM`) — usa `AlarmConfig`
- `get_alarm_status()` (`ALARMST?`) → `AlarmStatus`
- `reset_alarm_status()` (`ALMRST`)

### Min / Max
- `get_min_max()` (`MDAT?`) → `MinMaxData`
- `set_min_max_params()` / `get_min_max_params()` (`MNMX`)
- `reset_min_max()` (`MNMXRST`)

### Salida analógica
- `set_analog_output()` / `get_analog_output()` (`ANALOG`) — usa `AnalogOutputConfig`
- `get_analog_output_reading()` (`AOUT?`)

### Curvas de usuario (21-28)
- `set_curve_header()` / `get_curve_header()` (`CRVHDR`) — usa `CurveHeader`
- `set_curve_point()` / `get_curve_point()` (`CRVPT`)
- `delete_user_curve()` (`CRVDEL`)

### Interfaz remota
- `set_ieee_address()` / `get_ieee_address()` (`IEEE`)
- `set_terminator()` / `get_terminator()` (`TERM`)

## Convención write vs query

Todo comando `?` (consulta) se manda con `transport.query()`. Todo
comando de escritura pura (`*RST`, `MNMXRST`, `ALMRST`, `INNAME`,
`FILTER`, `ALARM`, `INTYPE`, etc.) se manda con `transport.write()`
solamente, porque el 218 no responde nada a esos — si se manda con
`query()` el `read()` posterior queda esperando hasta el timeout.
Esto ya está resuelto correctamente método por método en
`lakeshore218.py`; es lo primero a revisar si agregás un comando nuevo
a mano y ves timeouts inesperados.

## Detalles específicos de cada transporte

### `KeysightVISATransport`
- Resource string: `GPIB{board_index}::{gpib_address}::INSTR`
- Terminadores fijos: `read_termination="\r\n"`, `write_termination="\n"`
- `query()` sobreescrito para usar el `.query()` nativo de `pyvisa`
  (más eficiente que el `write+read` genérico de la clase base)

### `PrologixEthernetTransport`
- Socket TCP directo, puerto por defecto `1234`
- Modo **manual** (`++auto 0`) — decisión de diseño importante: con
  `++auto 1` el adaptador intenta leer respuesta después de cada
  comando, incluidos los de escritura pura que el 218 no responde,
  generando timeouts intermitentes y riesgo de leer datos
  desincronizados. En modo manual, `read()` pide explícitamente
  `++read eoi` solo cuando se espera respuesta real.
- `++eos 2` (LF) como terminador hacia el instrumento
- `++read_tmo_ms` configurado según el `timeout_s` del constructor

## `cli.py` — cómo está armado

Usa `argparse` con subcomandos (patrón tipo `git <subcomando>`). Cada
subcomando tiene un handler `cmd_<nombre>(ls, args)` que recibe una
instancia ya conectada de `Lakeshore218`. Para agregar un subcomando
nuevo:

1. Escribir `cmd_nuevo(ls: Lakeshore218, args) -> None`
2. Registrar el subparser en `build_parser()` con sus argumentos
3. `set_defaults(func=cmd_nuevo)`

El transporte se arma una sola vez en `build_transport()` — hoy
hardcodeado a `KeysightVISATransport`. Cuando se agregue soporte
Prologix al CLI, este es el único lugar que cambia.
