import os
import asyncio
import json
import soundfile as sf
import numpy as np
import websockets

WS_URL = "ws://127.0.0.1:8000"
WAV_PATH = "./fixtures/test.wav"  # replace with your WAV file

async def transcribe():
    # Load WAV
    data, samplerate = sf.read(WAV_PATH, dtype='int16')
    print(f"Original samplerate: {samplerate} Hz")
    
    # Resample to 16 kHz if needed
    target_rate = 16000
    if samplerate != target_rate:
        duration = data.shape[0] / samplerate
        num_samples = int(duration * target_rate)
        data = np.interp(
            np.linspace(0, len(data), num=num_samples, endpoint=False),
            np.arange(len(data)),
            data
        ).astype('int16')
        print(f"Resampled to {target_rate} Hz")

    raw_bytes = data.tobytes()
    uri = f"{WS_URL}/mic?userId=demo&clientId=demo&sessionId=demo"

    print(f"Connecting to {uri}")
    async with websockets.connect(uri) as ws:
        print("Connected. Streaming audio…")
        chunk_size = target_rate * 2 // 10  # 0.1 s of samples

        async def reader():
            try:
                async for message in ws:
                    payload = json.loads(message)
                    if payload.get("type") == "mic_transcription":
                        print("Transcription:", payload["content"])
            except websockets.exceptions.ConnectionClosed:
                print("WebSocket closed.")

        read_task = asyncio.create_task(reader())

        # Stream in 0.1 s chunks
        for i in range(0, len(raw_bytes), chunk_size):
            await ws.send(raw_bytes[i:i+chunk_size])
            await asyncio.sleep(0.05)

        # Give the server a moment to finish
        await asyncio.sleep(1)
        await ws.close()
        await read_task

if __name__ == "__main__":
    asyncio.run(transcribe())
