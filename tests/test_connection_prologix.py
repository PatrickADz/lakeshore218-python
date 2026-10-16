"""
Prueba básica de comunicación con el Lakeshore 218 vía Prologix GPIB-Ethernet.
"""

from lakeshore218 import Lakeshore218
from prologix_ethernet import PrologixEthernetTransport

PROLOGIX_IP = "192.168.1.50"
GPIB_ADDRESS = 12           

transport = PrologixEthernetTransport(ip_address=PROLOGIX_IP, gpib_address=GPIB_ADDRESS)

with Lakeshore218(transport) as ls:
    print("IDN:", ls.idn())
    print("Temperaturas (K):", ls.get_all_temperatures_kelvin())
