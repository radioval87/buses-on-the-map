import json
from functools import partial

import trio
from trio_websocket import ConnectionClosed, serve_websocket

buses = {}


async def handle_incoming_data(request):
    ws = await request.accept()
    while True:
        try:
            message = await ws.get_message()
            if message:
                try:
                    message = json.loads(message)
                    buses[message['busId']] = message
                except json.JSONDecodeError:
                    print(message)
        except ConnectionClosed:
            break


async def talk_to_browser(request):
    ws = await request.accept()
    while True:
        message = {
            "msgType": "Buses",
            "buses": [bus for bus in buses.values()]
        }
    
        await ws.send_message(json.dumps(message))
        await trio.sleep(0.1)


async def main():
    serve1 = partial(serve_websocket, handle_incoming_data, '127.0.0.1', 8080, ssl_context=None)
    serve2 = partial(serve_websocket, talk_to_browser, '127.0.0.1', 8000, ssl_context=None)
    async with trio.open_nursery() as nursery:
        nursery.start_soon(serve1)
        nursery.start_soon(serve2)

trio.run(main)
