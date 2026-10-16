# Changelog

## v1.3.1 - Reorganización del proyecto

### Cambiado
- Movidos el driver y los transportes a `src/`, y las herramientas
  ejecutables a `examples/`.
- Añadido `pyproject.toml` para instalar el proyecto y declarar la
  dependencia opcional de Keysight.
- Añadido el módulo `lakeshore218_driver` y se conserva `lakeshore218`
  como importación de compatibilidad.
- Las validaciones de parámetros del driver ahora usan
  `Lakeshore218ValidationError`, que sigue siendo subclase de `ValueError`.

## v1.3 - Transporte Prologix GPIB-Ethernet

### Agregado
- `prologix_ethernet.py`: `PrologixEthernetTransport`, implementa
  `GPIBTransport` sobre socket TCP.
- `test_connection_prologix.py`: script mínimo de prueba de conexión.

### Corregido
- Cambiado `++auto 1` por `++auto 0` (modo manual) en
  `PrologixEthernetTransport.connect()`. Con `++auto 1`, el adaptador
  intenta leer una respuesta después de *cada* comando enviado,
  incluidos los de escritura pura que el 218 no responde (`*RST`,
  `ALARM`, `FILTER`, `INNAME`, etc.), generando timeouts internos
  intermitentes y riesgo de leer datos desincronizados en la siguiente
  consulta real. `read()` ahora manda `++read eoi` explícitamente solo
  cuando se espera respuesta.
- Agregado `++read_tmo_ms` en `connect()`, sincronizado con el
  `timeout_s` del constructor (antes el timeout interno del Prologix
  no tenía relación con el timeout configurado en Python).

## v1.2 - CLI de terminal
- `cli.py`: herramienta de línea de comandos basada en `argparse`, con
  subcomandos: `idn`, `read`, `read-all`, `status`, `name`, `filter`,
  `alarm`, `minmax`, `monitor`, `shell`.
- Modo `monitor`: lectura continua en consola con timestamp, canales e
  intervalo configurables.
- Modo `shell`: REPL interactivo para mandar comandos SCPI crudos
  directo al instrumento (útil para debugging y comandos sin wrapper
  todavía).

## v1.1
- `lakeshore218.py` reescrito con cobertura completa del set de
  comandos del 218:
  - Lecturas: Kelvin, Celsius, sensor units, linear data, snapshot
    multi-canal, status de lectura decodificado.
  - Configuración de canal: nombre, tipo de sensor, curva asignada.
  - Display: campo y modo de pantalla.
  - Filtro de promediado.
  - Ecuación lineal.
  - Alarmas: configuración, estado, reset de latch.
  - Min/Max: lectura, configuración de fuente, reset.
  - Salida analógica: configuración y lectura.
  - Curvas de usuario (21-28): header y puntos.
  - Sistema: reset, self-test, beeper, lock de teclado, dirección
    IEEE, terminador de interfaz remota.
- Dataclasses de configuración: `InputTypeConfig`, `AlarmConfig`,
  `FilterConfig`, `MinMaxData`, `AnalogOutputConfig`, `CurveHeader`,
  `AlarmStatus`.


## v1.0
- `base.py`: interfaz abstracta `GPIBTransport`.
- `keysight_visa.py`: `KeysightVISATransport`, validado contra
  hardware real (Keysight 82357B + Lakeshore 218).
- `lakeshore218.py`: versión inicial con métodos básicos (`idn`,
  lectura de temperatura Kelvin, todos los canales, lectura de sensor).
- `test_connection_keysight.py`: script de prueba de conexión.
