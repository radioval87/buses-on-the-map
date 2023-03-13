import itertools
import json
import os
import random
from sys import stderr

import trio
from trio_websocket import open_websocket_url

NUMBER_OF_BUSES_PER_ROUTE = 34


def generate_bus_id(route_id, bus_index):
    return f"{route_id}-{bus_index}"


def load_routes(directory_path='routes'):
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, 'r', encoding='utf8') as file:
                yield json.load(file)


async def send_updates(server_address, receive_channel):
    async for value in receive_channel:
        async with open_websocket_url(server_address) as ws:
            await ws.send_message(value)
            
        await trio.sleep(0.1)        


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


async def main():
    memory_channels = []
    active_receive_channels = []
    for _ in range(0, 100):
        send_channel, receive_channel = trio.open_memory_channel(0)
        memory_channels.append((send_channel, receive_channel))
    
    async with trio.open_nursery() as nursery:
        for route in load_routes():
            for b in range(0, NUMBER_OF_BUSES_PER_ROUTE):
                send_channel, receive_channel = random.choice(memory_channels)
                
                nursery.start_soon(run_bus, generate_bus_id(route['name'], b), route, send_channel)

                if receive_channel not in active_receive_channels:
                    active_receive_channels.append(receive_channel)
                    nursery.start_soon(send_updates, 'ws://127.0.0.1:8080', receive_channel)
trio.run(main)
