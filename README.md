# Lakeshore 218 — Driver Python

Driver para controlar el **Lakeshore Model 218 Temperature Monitor** mediante
GPIB, con transportes intercambiables para Keysight USB-GPIB y Prologix
GPIB-Ethernet.

## Instalación

Desde la raíz del repositorio:

```bash
pip install -e .
```

Para usar el adaptador Keysight, instala además la dependencia opcional:

```bash
pip install -e ".[keysight]"
```

Keysight también requiere las Keysight IO Libraries en Windows o un backend
VISA compatible en Linux. El transporte Prologix solo usa la biblioteca
estándar de Python.

## Uso como librería

```python
from lakeshore218_driver import Lakeshore218
from prologix_ethernet import PrologixEthernetTransport

transport = PrologixEthernetTransport(
    ip_address="192.168.1.50",
    gpib_address=12,
)

with Lakeshore218(transport) as instrument:
    print(instrument.idn())
    print(instrument.get_all_temperatures_kelvin())
```

El nombre de importación `lakeshore218` sigue disponible por compatibilidad:

```python
from lakeshore218 import Lakeshore218
```

## CLI y ejemplos

Los ejemplos requieren que el proyecto esté instalado. Ejemplos de uso:

```bash
python examples/cli.py --transport keysight --addr 12 idn
python examples/cli.py --transport keysight --addr 12 read-all --unit C
python examples/cli.py --transport keysight --addr 12 monitor --interval 1
python examples/cli.py --transport prologix --addr 12 --ip 192.168.1.50 idn
python examples/cli.py --transport prologix --addr 12 --ip 192.168.1.50 read-all
python examples/cli.py --help
```

## Estructura

```text
src/
├── lakeshore218_driver.py
├── exceptions.py
├── base.py
├── keysight_visa.py
├── lakeshore218.py          # compatibilidad con imports antiguos
└── prologix_ethernet.py
examples/
├── cli.py
└── test_connection_prologix.py
pyproject.toml
CHANGELOG.md
```

El driver no importa `pyvisa` ni `socket`: los transportes implementan la
interfaz común `GPIBTransport`, y el CLI selecciona cuál usar.
