from aiohttp import web, ClientSession
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
import json
from os import environ

PUBLIC_KEY = VerifyKey(bytes.fromhex(environ["PUBLIC_KEY"]))
CLIENT_ID = environ["CLIENT_ID"]
TOKEN = environ["TOKEN"]
GUILD_ID = environ["GUILD_ID"]


async def ping_command(data):
    # just send a response message
    return web.json_response({
        "type": 3,  # send a response without showing the command message
        "data": {
            "content": "Pong!",
            "flags": 1 << 6  # Make the respond message only visible to the user than ran the command
        }
    })


async def echo_command(data):
    command = data["data"]
    text_option = command["options"][0]  # We know the command always has one option, so it's safe to do this
    return web.json_response({
        "type": 4,  # send a response and show the command message
        "data": {
            "content": text_option["value"],
        }
    })


async def command_entry(request):
    # Read the request body as text (str)
    raw_data = await request.text()

    # Get our header values
    signature = request.headers.get("x-signature-ed25519")
    timestamp = request.headers.get("x-signature-timestamp")
    if signature is None or timestamp is None:
        # We can't verify the request without the signature and timestamp
        return web.HTTPUnauthorized()

    try:
        # Verify the signature with our public key
        PUBLIC_KEY.verify(f"{timestamp}{raw_data}".encode(), bytes.fromhex(signature))
    except BadSignatureError:
        # The signature is wrong
        return web.HTTPUnauthorized()

    # Parse the request body as json
    data = json.loads(raw_data)

    # Check which interaction type this request is
    if data["type"] == 1:
        # It's a PING request -> respond with PONG (type 1)
        return web.json_response({"type": 1})

    elif data["type"] == 2:
        # It's a command request -> run the correct command
        command = data["data"]
        if command["name"] == "ping":
            return await ping_command(data)

        if command["name"] == "echo":
            return await echo_command(data)

        else:
            # We don't know this command
            return web.HTTPNotFound()

    else:
        # We don't know what to do with this
        return web.HTTPBadRequest()


async def create_commands(app):
    # The json structure for our commands
    commands = [
        {
            "name": "ping",
            "description": "Ping? Pong!",
            "options": []  # The command doesn't need any arguments
        },
        {
            "name": "echo",
            "description": "Let the bot repeat the given text",
            "options": [
                {
                    "type": 3,  # It's a text argument,
                    "name": "text",
                    "description": "The text to repeat",
                    "required": True,
                }
            ]
        }
    ]

    # We need a session to make http requests
    session = ClientSession()

    # Register all the commands at discord
    async with session.put(
            f"https://discord.com/api/v8/applications/{CLIENT_ID}/guilds/{GUILD_ID}/commands",
            headers={"Authorization": f"Bot {TOKEN}"},
            json=commands
    ) as resp:
        resp.raise_for_status()

    # We don't need the session anymore -> close it
    await session.close()


if __name__ == "__main__":
    app = web.Application()
    app.add_routes([web.post("/entry", command_entry)])
    app.on_startup.append(create_commands)
    web.run_app(app, host="127.0.0.1", port=8080)
