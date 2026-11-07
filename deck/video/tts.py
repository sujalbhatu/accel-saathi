"""Makes the AI voice-over, one file per line and voice (needs: pip install edge-tts; internet).

    python tts.py [script file] [out folder] [rate]      e.g.  python tts.py script_v2.json voice2 +10%

Writes deck/video/<out folder>/<voice>/<line id>.mp3, plus <line id>.json with each word's start and end in seconds,
so the captions can follow the voice word by word."""
import asyncio
import json
import os
import sys

import edge_tts

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = sys.argv[1] if len(sys.argv) > 1 else "script.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "voice"
RATE = sys.argv[3] if len(sys.argv) > 3 else "+4%"
# first voice that exists wins: the Expressive Neerja sounds more like a person telling a story
VOICES = {"neerja": ["en-IN-NeerjaExpressiveNeural", "en-IN-NeerjaNeural"], "prabhat": ["en-IN-PrabhatNeural"]}


async def speak(text, voice, mp3):
    try:
        com = edge_tts.Communicate(text, voice, rate=RATE, boundary="WordBoundary")
    except TypeError:  # edge-tts 6.x: word boundaries are the default and there is no boundary option
        com = edge_tts.Communicate(text, voice, rate=RATE)
    words, audio = [], bytearray()
    async for chunk in com.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
        elif chunk["type"] == "WordBoundary":
            start = chunk["offset"] / 1e7
            words.append([round(start, 3), round(start + chunk["duration"] / 1e7, 3), chunk["text"]])
    if not audio:
        raise RuntimeError("no audio")
    open(mp3, "wb").write(audio)
    json.dump(words, open(mp3[:-4] + ".json", "w", encoding="utf-8"), ensure_ascii=False)


async def main():
    lines = json.load(open(os.path.join(HERE, SCRIPT), encoding="utf-8"))
    names = {v["ShortName"] for v in await edge_tts.list_voices()}
    for short, choices in VOICES.items():
        voice = next((v for v in choices if v in names), choices[-1])
        out = os.path.join(HERE, OUT, short)
        os.makedirs(out, exist_ok=True)
        for s in lines:
            await speak(s["text"], voice, os.path.join(out, s["id"] + ".mp3"))
            print(short, voice, s["id"])


asyncio.run(main())
