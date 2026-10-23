#!/usr/bin/env python3
"""
CLI para el Lakeshore 218. Soporta dos transportes intercambiables:
Keysight USB-GPIB (VISA) y Prologix GPIB-Ethernet.

Ejemplos (Keysight):
    python examples/cli.py --transport keysight --addr 12 idn
    python examples/cli.py --transport keysight --addr 12 read-all --unit C
    python examples/cli.py --transport keysight --addr 12 monitor --interval 1

Ejemplos (Prologix):
    python examples/cli.py --transport prologix --addr 12 --ip 192.168.1.50 idn
    python examples/cli.py --transport prologix --addr 12 --ip 192.168.1.50 read-all

Argumentos de conexión según transporte:
    --transport keysight: --addr (obligatorio), --board (default 0),
                           --timeout (ms, default 5000)
    --transport prologix: --addr (obligatorio), --ip (obligatorio),
                           --port (default 1234), --timeout (ms, default 5000)

IMPORTANTE -- imports diferidos a propósito: `pyvisa` (necesario para
Keysight) solo se importa si se elige --transport keysight, y el socket
de Prologix no tiene dependencias externas. Esto permite compartir este
mismo ejemplo con alguien que solo tiene uno de los dos adaptadores, sin
que le falle por no tener instalada una dependencia que no va a usar
(ver README.md, sección "Windows vs Linux / dependencias por transporte").
"""

from __future__ import annotations

import argparse
import sys
import time

from lakeshore218_driver import (
    LakeShore218,
    TemperatureUnit,
    AlarmConfig,
)


UNIT_MAP = {
    "K": TemperatureUnit.KELVIN,
    "C": TemperatureUnit.CELSIUS,
    "S": TemperatureUnit.SENSOR,
}


def build_transport(args: argparse.Namespace):
    """
    Construye el transporte según --transport. Los imports de cada
    implementación se hacen acá adentro (no arriba del archivo) para
    que este cli.py pueda compartirse sin forzar la instalación de
    dependencias del transporte que no se va a usar.
    """
    if args.transport == "keysight":
        try:
            from keysight_visa import KeysightVISATransport
        except ImportError as exc:
            raise SystemExit(
                "No se pudo importar keysight_visa / pyvisa. "
                "Instala el extra `pip install -e \".[keysight]\"` y el runtime VISA "
                "correspondiente a tu sistema operativo. "
                "Ver README.md."
            ) from exc
        return KeysightVISATransport(
            gpib_address=args.addr,
            board_index=args.board,
            timeout_ms=args.timeout,
        )

    if args.transport == "prologix":
        if not args.ip:
            raise SystemExit("--transport prologix requiere --ip <dirección del adaptador>")
        try:
            from prologix_ethernet import PrologixEthernetTransport
        except ImportError as exc:
            raise SystemExit(
                "No se pudo importar prologix_ethernet.py. "
                "Instala el proyecto con `pip install -e .` y vuelve a intentarlo."
            ) from exc
        return PrologixEthernetTransport(
            ip_address=args.ip,
            gpib_address=args.addr,
            port=args.port,
            timeout_s=args.timeout / 1000,
        )

    raise SystemExit(f"Transporte desconocido: {args.transport}")


# --------------------------------------------------------------------
# Handlers de cada subcomando
# --------------------------------------------------------------------

def cmd_idn(ls: LakeShore218, args: argparse.Namespace) -> None:
    print(ls.get_idn())


def cmd_read(ls: LakeShore218, args: argparse.Namespace) -> None:
    unit = UNIT_MAP[args.unit]
    value = ls.read_channel(args.channel, unit)
    print(f"Canal {args.channel}: {value:.4f} {args.unit}")


def cmd_read_all(ls: LakeShore218, args: argparse.Namespace) -> None:
    unit = UNIT_MAP[args.unit]
    readings = ls.read_all_channels(unit)
    for ch, value in readings.items():
        print(f"Canal {ch}: {value:.4f} {args.unit}")


def cmd_status(ls: LakeShore218, args: argparse.Namespace) -> None:
    raw = ls.sensor_status(args.channel)
    flags = ls.decode_sensor_status(raw)
    print(f"Canal {args.channel} -- status crudo: {raw}")
    for flag_name, value in flags.items():
        marca = "X" if value else " "
        print(f"  [{marca}] {flag_name}")


def cmd_name(ls: LakeShore218, args: argparse.Namespace) -> None:
    if args.set is not None:
        ls.set_input_name(args.channel, args.set)
        print(f"Canal {args.channel} renombrado a '{args.set}'")
    else:
        print(f"Canal {args.channel}: '{ls.get_input_name(args.channel)}'")


def cmd_filter(ls: LakeShore218, args: argparse.Namespace) -> None:
    if args.set:
        ls.set_filter(args.channel, args.on, args.points, args.window)
        config = ls.get_filter(args.channel)
        print(f"Filtro canal {args.channel} configurado: {config}")
    else:
        config = ls.get_filter(args.channel)
        print(f"Filtro canal {args.channel}: {config}")


def cmd_alarm(ls: LakeShore218, args: argparse.Namespace) -> None:
    if args.set:
        config = AlarmConfig(
            enabled=args.on,
            high_setpoint=args.high,
            low_setpoint=args.low,
            deadband=args.deadband,
            latch_enable=args.latch,
        )
        ls.set_alarm(args.channel, config)
        print(f"Alarma canal {args.channel} configurada: {config}")
    else:
        config = ls.get_alarm(args.channel)
        status = ls.get_alarm_status(args.channel)
        print(f"Alarma canal {args.channel}: {config}")
        print(f"Estado actual: high={status.high_state} low={status.low_state}")


def cmd_minmax(ls: LakeShore218, args: argparse.Namespace) -> None:
    if args.reset:
        ls.reset_min_max()
        print("Min/Max reiniciados en todos los canales")
        return
    data = ls.get_min_max(args.channel)
    print(f"Canal {args.channel}: min={data.minimum:.4f} max={data.maximum:.4f}")


def cmd_monitor(ls: LakeShore218, args: argparse.Namespace) -> None:
    unit = UNIT_MAP[args.unit]
    channels = args.channels if args.channels else list(range(1, 9))
    print(f"Monitoreando canales {channels} cada {args.interval}s "
          f"(Ctrl+C para salir)")
    try:
        while True:
            timestamp = time.strftime("%H:%M:%S")
            valores = [
                f"CH{ch}={ls.read_channel(ch, unit):.3f}{args.unit}"
                for ch in channels
            ]
            print(f"[{timestamp}] " + "  ".join(valores))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitoreo detenido.")


def cmd_shell(ls: LakeShore218, args: argparse.Namespace) -> None:
    """Modo interactivo: manda comandos SCPI crudos directo al instrumento."""
    print("Shell interactivo Lakeshore 218. Comandos SCPI crudos.")
    print("'exit' o Ctrl+D para salir.\n")
    while True:
        try:
            raw = input("218> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue
        if raw.lower() in ("exit", "quit"):
            break
        try:
            if "?" in raw:
                print(ls.transport.query(raw))
            else:
                ls.transport.write(raw)
        except Exception as exc:  # noqa: BLE001 - shell de debug, se quiere ver cualquier error
            print(f"Error: {exc}")


# --------------------------------------------------------------------
# Definición de argparse
# --------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lakeshore218-cli",
        description="CLI para controlar el Lakeshore 218 (Keysight USB-GPIB o Prologix Ethernet).",
    )
    parser.add_argument(
        "--transport", choices=["keysight", "prologix"], required=True,
        help="Adaptador GPIB a usar",
    )
    parser.add_argument("--addr", type=int, required=True, help="Dirección GPIB del 218 (1-30)")
    parser.add_argument("--timeout", type=int, default=5000, help="Timeout en ms (default 5000)")

    # Específicos de --transport keysight
    parser.add_argument("--board", type=int, default=0, help="[keysight] Índice de tarjeta GPIB (default 0)")

    # Específicos de --transport prologix
    parser.add_argument("--ip", type=str, default=None, help="[prologix] IP del adaptador Prologix")
    parser.add_argument("--port", type=int, default=1234, help="[prologix] Puerto TCP (default 1234)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("idn", help="Consulta *IDN?").set_defaults(func=cmd_idn)

    p_read = subparsers.add_parser("read", help="Lee un canal")
    p_read.add_argument("channel", type=int)
    p_read.add_argument("--unit", choices=["K", "C", "S"], default="K")
    p_read.set_defaults(func=cmd_read)

    p_read_all = subparsers.add_parser("read-all", help="Lee los 8 canales")
    p_read_all.add_argument("--unit", choices=["K", "C", "S"], default="K")
    p_read_all.set_defaults(func=cmd_read_all)

    p_status = subparsers.add_parser("status", help="Estado de lectura de un canal (RDGST?)")
    p_status.add_argument("channel", type=int)
    p_status.set_defaults(func=cmd_status)

    p_name = subparsers.add_parser("name", help="Lee/asigna el nombre de un canal")
    p_name.add_argument("channel", type=int)
    p_name.add_argument("--set", type=str, default=None, help="Nuevo nombre (si se omite, solo consulta)")
    p_name.set_defaults(func=cmd_name)

    p_filter = subparsers.add_parser("filter", help="Lee/configura el filtro de promediado")
    p_filter.add_argument("channel", type=int)
    p_filter.add_argument("--set", action="store_true", help="Escribir configuración en vez de solo leer")
    p_filter.add_argument("--on", action="store_true", help="Habilitar filtro (usar con --set)")
    p_filter.add_argument("--points", type=int, default=8, help="Puntos del promedio (2-64)")
    p_filter.add_argument("--window", type=int, default=1, help="Ventana %% (1-10)")
    p_filter.set_defaults(func=cmd_filter)

    p_alarm = subparsers.add_parser("alarm", help="Lee/configura alarma de un canal")
    p_alarm.add_argument("channel", type=int)
    p_alarm.add_argument("--set", action="store_true", help="Escribir configuración en vez de solo leer")
    p_alarm.add_argument("--on", action="store_true", help="Habilitar alarma (usar con --set)")
    p_alarm.add_argument("--high", type=float, default=0.0, help="Setpoint alto")
    p_alarm.add_argument("--low", type=float, default=0.0, help="Setpoint bajo")
    p_alarm.add_argument("--deadband", type=float, default=0.0, help="Deadband")
    p_alarm.add_argument("--latch", action="store_true", help="Habilitar latch")
    p_alarm.set_defaults(func=cmd_alarm)

    p_minmax = subparsers.add_parser("minmax", help="Lee o reinicia min/max")
    p_minmax.add_argument("channel", type=int, nargs="?", default=1)
    p_minmax.add_argument("--reset", action="store_true", help="Reinicia min/max de todos los canales")
    p_minmax.set_defaults(func=cmd_minmax)

    p_monitor = subparsers.add_parser("monitor", help="Monitoreo continuo en consola")
    p_monitor.add_argument("--unit", choices=["K", "C", "S"], default="K")
    p_monitor.add_argument("--interval", type=float, default=1.0, help="Segundos entre lecturas")
    p_monitor.add_argument("--channels", type=int, nargs="+", default=None,
                            help="Canales a monitorear (default: todos, 1-8)")
    p_monitor.set_defaults(func=cmd_monitor)

    subparsers.add_parser("shell", help="Shell interactivo de comandos SCPI crudos").set_defaults(func=cmd_shell)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    transport = build_transport(args)
    try:
        with LakeShore218(transport) as ls:
            args.func(ls, args)
    except Exception as exc:  # noqa: BLE001 - se quiere reportar cualquier falla de conexión/comando
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
