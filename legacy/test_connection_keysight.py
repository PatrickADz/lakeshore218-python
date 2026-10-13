"""
Prueba básica de comunicación con el Lakeshore 218 vía Keysight USB-GPIB.
"""

from lakeshore218 import Lakeshore218
from keysight_visa import KeysightVISATransport

GPIB_ADDRESS = 12

transport = KeysightVISATransport(gpib_address=GPIB_ADDRESS)

with Lakeshore218(transport) as ls:
    print("IDN:", ls.idn())
    print("Temperaturas (K):", ls.get_all_temperatures_kelvin())
