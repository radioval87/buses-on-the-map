import argparse
import itertools
import json
import logging
import os
import random

from contextlib import suppress
from functools import wraps
from sys import stderr


import trio
from trio_websocket import open_websocket_url, HandshakeError


logger = logging.getLogger('server')

open_websockets = []


def relaunch_on_disconnect(async_ws_connection_func):
    @wraps(async_ws_connection_func)
    async def apply_retrying(*args, **kwargs):
        connected = False
        while not connected:
            try:
                result = await async_ws_connection_func(*args, **kwargs)
                connected = True
                return result
            except HandshakeError:
                logger.info('Unable to connect to server. Retrying')
                await trio.sleep(1)
    return apply_retrying


def generate_bus_id(emulator_id, route_id, bus_index):
    return f'{emulator_id + "-" if emulator_id else ""}{route_id}-{bus_index}'


def load_routes(directory_path='routes'):
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, 'r', encoding='utf8') as file:
                yield json.load(file)


@relaunch_on_disconnect
async def send_updates(server_address, receive_channel, websockets_number,
                       open_websockets, refresh_timeout):
    async for value in receive_channel:
        while len(open_websockets) >= websockets_number:
            for ws in open_websockets:
                if ws.closed:
                    open_websockets.remove(ws)

        async with open_websocket_url(server_address) as ws:
            open_websockets.append(ws)
            await ws.send_message(value)
        await trio.sleep(refresh_timeout)


async def run_bus(bus_id, route, send_channel):
    coordinates = itertools.cycle(route['coordinates'])
    coordinates = itertools.islice(
        coordinates,
        random.randint(0, len(route['coordinates']) - 1),
        None
    )
    try:
        async with send_channel:
            for coord in coordinates:
                mes = {
                    "busId": bus_id,
                    "lat": coord[0],
                    "lng": coord[1],
                    "route": route['name']
                }
                await send_channel.send(json.dumps(mes, ensure_ascii=False))
                await trio.sleep(0.1)
    except OSError as ose:
        print('Connection attempt failed: %s' % ose, file=stderr)


async def main(server_address, routes_number, buses_per_route,
               websockets_number, emulator_id, refresh_timeout):
    memory_channels = []
    active_receive_channels = []
    for _ in range(0, 100):
        send_channel, receive_channel = trio.open_memory_channel(0)
        memory_channels.append((send_channel, receive_channel))
    
    routes_counter = 0
    async with trio.open_nursery() as nursery:
        for route in load_routes():
            if routes_counter == routes_number:
                break
            for b in range(buses_per_route):
                send_channel, receive_channel = random.choice(memory_channels)
                
                nursery.start_soon(
                    run_bus,
                    generate_bus_id(emulator_id, route['name'], b),
                    route,
                    send_channel,
                )

                if receive_channel not in active_receive_channels:
                    active_receive_channels.append(receive_channel)
                    nursery.start_soon(
                        send_updates,
                        server_address,
                        receive_channel,
                        websockets_number,
                        open_websockets,
                        refresh_timeout,
                    )

            routes_counter += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--server', type=str, default='ws://127.0.0.1:8080',
        help='Server Address'
    )
    parser.add_argument(
        '--routes_number', type=int, default=1,
        help='Number of bus routes'
    )
    parser.add_argument(
        '--buses_per_route', type=int, default=1,
        help='Number of buses per route'
    )
    parser.add_argument(
        '--websockets_number', type=int, default=1,
        help='Number of open websockets'
    )
    parser.add_argument(
        '--emulator_id', type=str, default='',
        help='Prefix for emulator instance busId'
    )
    parser.add_argument(
        '--refresh_timeout', type=float, default=0.1,
        help='Seconds to wait to refresh coordinates'
    )
    parser.add_argument(
        '--v', type=bool, default=True,
        help='Turn on logging'
    )
    args = parser.parse_args()

    if not args.v:
        logger.disabled = True
    else:
        logging.basicConfig(
            format=(
                '%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s] '
                '%(message)s'
            ),
            level=logging.DEBUG
        )
    with suppress(KeyboardInterrupt):
        trio.run(
            main,
            args.server,
            args.routes_number,
            args.buses_per_route,
            args.websockets_number,
            args.emulator_id,
            args.refresh_timeout
        )
