
import json
import os
from sys import stderr

import trio
from trio_websocket import open_websocket_url


def load_routes(directory_path='routes'):
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, 'r', encoding='utf8') as file:
                yield json.load(file)


async def run_bus(url, bus_id, route):
    try:
        async with open_websocket_url(url) as ws:

            for coord in route['coordinates']:
                mes = {
                    "busId": bus_id,
                    "lat": coord[0],
                    "lng": coord[1],
                    "route": route['name']
                }
                await ws.send_message(json.dumps(mes, ensure_ascii=False))
                await trio.sleep(1)
    except OSError as ose:
        print('Connection attempt failed: %s' % ose, file=stderr)


async def main():
    async with trio.open_nursery() as nursery:
        for route in load_routes():
            nursery.start_soon(run_bus, 'ws://127.0.0.1:8080', route['name'], route)

trio.run(main)
