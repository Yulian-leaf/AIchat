import asyncio
import json

import websockets


async def main() -> None:
    uri = "ws://127.0.0.1:8765/ws"
    async with websockets.connect(uri) as ws:
        first = await ws.recv()
        print("first:", first)
        session_id = json.loads(first).get("session_id")

        await ws.send(
            json.dumps(
                {
                    "type": "user_message",
                    "content": "你好，介绍一下你自己",
                    "session_id": session_id,
                    "stream": True,
                },
                ensure_ascii=False,
            )
        )

        full = ""
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("type") == "assistant_delta":
                full += data.get("content", "")
            if data.get("type") == "assistant_message":
                print("final:", data.get("content"))
                break

        print("accumulated:", full)


if __name__ == "__main__":
    asyncio.run(main())
