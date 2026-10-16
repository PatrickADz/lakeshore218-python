# Lakeshore 218 — Driver Python

Librería para controlar el **Lakeshore Model 218 Temperature Monitor**
desde Python, independiente del adaptador GPIB usado (Keysight USB-GPIB
o Prologix GPIB-Ethernet).

Dependencias:

```bash
pip install pyvisa            # solo si usás Keysight / VISA
```

Prologix (ethernet): no requiere librerías externas (usa `socket` de la stdlib).
Keysight 82357B (USBB): requiere **Keysight IO Libraries Suite** instalado.

## Uso rápido

### Con Keysight USB-GPIB

```python
from lakeshore218 import Lakeshore218
from keysight_visa import KeysightVISATransport

transport = KeysightVISATransport(gpib_address=12)

with Lakeshore218(transport) as ls:
    print(ls.idn())
    print(ls.get_all_temperatures_kelvin())
```

### Con Prologix GPIB-Ethernet

```python
from lakeshore218 import Lakeshore218
from prologix_ethernet import PrologixEthernetTransport

transport = PrologixEthernetTransport(ip_address="192.168.1.50", gpib_address=12)

with Lakeshore218(transport) as ls:
    print(ls.idn())
    print(ls.get_all_temperatures_kelvin())
```

### Desde la terminal (CLI)

```bash
# Keysight USB-GPIB
python cli.py --transport keysight --addr 12 idn
python cli.py --transport keysight --addr 12 read-all --unit C
python cli.py --transport keysight --addr 12 monitor --interval 1

# Prologix GPIB-Ethernet
python cli.py --transport prologix --addr 12 --ip 192.168.1.50 idn
python cli.py --transport prologix --addr 12 --ip 192.168.1.50 read-all

# Shell interactivo de comandos SCPI crudos (cualquiera de los dos transportes)
python cli.py --transport keysight --addr 12 shell
```

Ver `python cli.py --help` y `python cli.py <subcomando> --help` para
todas las opciones.

## Windows vs Linux / dependencias por transporte

Los dos transportes **no tienen los mismos requisitos de sistema
operativo**, porque uno depende de un runtime de terceros y el otro no.

### Keysight (VISA / 82357B)

- **Windows**: requiere **Keysight IO Libraries Suite**
  (incluye el runtime VISA y el driver del 82357B). Sin esto, `pyvisa`
  no encuentra ningún backend y falla al conectar.
- **Linux**: **NI-VISA para Linux**, **`linux-gpib`**
-  
- **pyvisa** (`pip install pyvisa-py`)

### Prologix (Ethernet)

- `prologix_ethernet.py` usa la librería estándar de Python. 
- No depende de ningún runtime VISA ni driver de fabricante. Requiere conectividad de red

## Archivos del proyecto

| Archivo | Descripción |
|---|---|
| `base.py` | Interfaz abstracta `GPIBTransport` |
| `keysight_visa.py` | GPIB vía Keysight/VISA |
| `prologix_ethernet.py` | GPIB vía Prologix GPIB-Ethernet |
| `lakeshore218.py` | Driver |
| `cli.py` | Herramienta de terminal |
| `test_connection_keysight.py` | Script de prueba |
| `test_connection_prologix.py` | Script de prueba  |
