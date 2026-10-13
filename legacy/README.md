# lakeshore_lib

Librería para controlar un **Lakeshore Model 218 Temperature Monitor**
por GPIB.

- **Keysight USB-GPIB** (82357B u otro) vía PyVISA / Keysight IO Libraries.
- **Prologix GPIB-ETHERNET** vía socket TCP directo (protocolo Prologix).

## Estructura

```
lakeshore_lib/
├── transports/
│   ├── 

```

##Windows:
Requiere la instalación de Keysight IO Libraries Suite. 

## Instalación

```bash
pip install -r requirements.txt
```

Para el camino Keysight se necesita además tener instaladas las
**Keysight IO Libraries Suite** (o NI-VISA), que es lo que provee el
backend VISA que usa PyVISA.

Para el camino Prologix no se necesita nada adicional: es un socket TCP
plano. Solo necesitas la IP del adaptador en tu red.

## Uso rápido

```python
from lakeshore_lib import Lakeshore218, KeysightVISATransport

transport = KeysightVISATransport(gpib_address=12)

with Lakeshore218(transport) as ls:
    print(ls.idn())
    print(ls.get_all_temperatures_kelvin())
```

O con Prologix:

```python
from lakeshore_lib import Lakeshore218, PrologixEthernetTransport

transport = PrologixEthernetTransport(ip_address="192.168.1.50", gpib_address=12)

with Lakeshore218(transport) as ls:
    print(ls.idn())
```

## Averiguar la dirección GPIB del 218

En el panel frontal del Lakeshore 218: botón **CONFIG** hasta llegar a
`IEEE ADDR`, ahí se ve/edita la dirección (por defecto suele venir en 12).

