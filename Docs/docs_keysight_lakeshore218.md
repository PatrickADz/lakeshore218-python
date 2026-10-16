# Uso del Lakeshore 218 con Keysight USB-GPIB (82357B)

## 1. Requisitos previos

- **Keysight IO Libraries Suite** instalado (incluye Keysight Connection Expert
  y el runtime VISA). Sin esto, `pyvisa` no encuentra ningún backend.
- Driver del adaptador 82357B instalado (viene con IO Libraries Suite).
- Python: `pip install pyvisa`

## 2. Configurar la dirección GPIB en el Lakeshore 218

En el panel frontal del 218:

1. Presionar el botón **`IEEE ADDR`** (o entrar al menú de configuración,
   depende de la versión de firmware — en algunos es `SETUP` → `IEEE ADDR`).
2. Anotar / setear la dirección (rango válido: 1-30). Por defecto suele
   venir en `12`.
3. Confirmar que el equipo tiene habilitada la interfaz **IEEE-488 (GPIB)**
   y no está en modo local-lock.

Esta dirección es el `gpib_address` que se le entrega a `KeysightVISATransport`.

## 3. Verificar el adaptador con Keysight Connection Expert

1. Conectar el 82357B por USB a la PC.
2. Abrir **Keysight Connection Expert**.
3. Debe aparecer el adaptador como `GPIB0` (o similar). Si no aparece,
   reinstalar el driver del 82357B.
4. Conectar el cable GPIB del 82357B al Lakeshore 218.
5. En Connection Expert, hacer clic derecho sobre `GPIB0` → **Scan for
   Instruments**. Debería detectar el instrumento en la dirección
   configurada (ej. `GPIB0::12::INSTR`).
6. Botón derecho sobre el instrumento detectado → **Send Commands to
   this Instrument** probar `*IDN?` manualmente. Si responde algo como:

   ```
   LSCI,MODEL218,XXXXXX,X.X
   ```

   el hardware y el driver VISA están correctamente configurados, y
   cualquier problema posterior es de software/Python, no de conexión física.

Este paso es clave: si `*IDN?` no funciona desde Connection Expert,
tampoco va a funcionar desde `pyvisa`, así que conviene descartar
el hardware primero.

## 4. Resource string VISA

El formato que usa `KeysightVISATransport` es:

```
GPIB{board_index}::{gpib_address}::INSTR
```

Ejemplo:

```python
transport = KeysightVISATransport(gpib_address=12, board_index=0)
```

## 5. Parámetros de comunicación (termination / timeout)

El 218 se comunica por defecto con terminador `<CR><LF>` en las
respuestas. Esto ya está seteado en `KeysightVISATransport`:

```python
self._inst.read_termination = "\r\n"
self._inst.write_termination = "\n"
```

Si en algún momento las lecturas devuelven timeout o strings vacíos,
lo primero a revisar es:

1. **Terminador incorrecto**: si se configuró el 218 con `TERM` distinto
   a `<CR><LF>` (comando `TERM` del driver, sección "Interfaz remota"),
   hay que ajustar `read_termination`/`write_termination` para que
   coincidan.
2. **Timeout corto**: `timeout_ms` por defecto es `5000` (5s). Lecturas
   de los 8 canales (`KRDG? 0`) no deberían tardar tanto, pero si hay
   cable largo/ruido puede convenir subirlo.

## 6. Comandos verificados como correctos para el 218

Estos son los comandos SCPI reales que usa `lakeshore218.py`, tal como
están documentados en el manual del Model 218, quedan acá como
referencia rápida al momento de debuggear con Connection Expert o un
terminal serie/VISA manual:

| Método Python | Comando SCPI | Formato de respuesta |
|---|---|---|
| `idn()` | `*IDN?` | `LSCI,MODEL218,<serie>,<firmware>` |
| `reset()` | `*RST` | (sin respuesta) |
| `get_temperature_kelvin(ch)` | `KRDG? <ch>` | `+273.15` (float, K) |
| `get_all_temperatures_kelvin()` | `KRDG? 0` | `v1,v2,...,v8` |
| `get_temperature_celsius(ch)` | `CRDG? <ch>` | float, °C |
| `get_sensor_reading(ch)` | `SRDG? <ch>` | float, unidades del sensor (V/Ω) |
| `get_reading_status(ch)` | `RDGST? <ch>` | entero (bitmask) |
| `set_input_name/get_input_name` | `INNAME <ch>,"nombre"` / `INNAME? <ch>` | string entre comillas |
| `set_input_type/get_input_type` | `INTYPE <ch>,...` / `INTYPE? <ch>` | 5 campos separados por "," |
| `set_filter/get_filter` | `FILTER <ch>,...` / `FILTER? <ch>` | 3 campos |
| `set_alarm/get_alarm` | `ALARM <ch>,...` / `ALARM? <ch>` | hasta 7 campos |
| `get_alarm_status(ch)` | `ALARMST? <ch>` | `high,low` (0/1) |
| `get_min_max(ch)` | `MDAT? <ch>` | `min,max` |
| `reset_min_max()` | `MNMXRST` | (sin respuesta) |

**Importante**: todos los comandos `?` de consulta deben mandarse con
`query()` (write + read), y todos los de escritura pura (`*RST`,
`MNMXRST`, `ALMRST`, `INNAME`, `FILTER`, `ALARM`, etc.) con `write()`
solamente el 218 no responde nada a esos, y si se emite `query()` sobre
ellos el `read()` se va a quedar esperando hasta el timeout.

## 7. Checklist de prueba rápida

```python
from lakeshore218 import Lakeshore218
from keysight_visa import KeysightVISATransport

transport = KeysightVISATransport(gpib_address=12)  # ajustar dirección real

with Lakeshore218(transport) as ls:
    print("IDN:", ls.idn())
    print("Kelvin:", ls.get_all_temperatures_kelvin())
    print("Status canal 1:", ls.decode_reading_status(ls.get_reading_status(1)))
```
