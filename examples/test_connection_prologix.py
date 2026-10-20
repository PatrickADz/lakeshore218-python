"""
Prueba básica de comunicación con el Lakeshore 218 vía Prologix GPIB-Ethernet.
"""

from lakeshore218_driver import LakeShore218
from prologix_ethernet import PrologixEthernetTransport

PROLOGIX_IP = "192.168.1.50"
GPIB_ADDRESS = 12           

transport = PrologixEthernetTransport(ip_address=PROLOGIX_IP, gpib_address=GPIB_ADDRESS)

with LakeShore218(transport) as ls:
    print("IDN:", ls.get_idn())
    print("Temperaturas (K):", ls.read_all_channels("K"))
