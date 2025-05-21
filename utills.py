import base64

from aiogram.client.session import aiohttp


async def hf_speech_to_text(audio_url: str) -> str:
    HF_API_URL = "https://dushanthae-sinhala-audio-to-text.hf.space/run/predict"

    # 1. Скачиваем аудио и кодируем в base64
    async with aiohttp.ClientSession() as session:
        async with session.get(audio_url) as resp:
            audio_data = await resp.read()
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")

    # 2. Формируем payload для Hugging Face API
    payload = {
        "data": [
            None,  # Пропускаем microphone (None)
            {
                "name": "voice.ogg",
                "data": f"data:audio/ogg;base64,{audio_b64}"
            },
            "transcribe"
        ]
    }

    # 3. Отправляем запрос
    async with aiohttp.ClientSession() as session:
        async with session.post(HF_API_URL, json=payload) as resp:
            result = await resp.json()
            return result["data"][0]  # Возвращаем распознанный текст
