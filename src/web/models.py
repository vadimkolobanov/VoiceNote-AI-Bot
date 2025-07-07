# src/web/models.py
from pydantic import BaseModel


class AliceRequest(BaseModel):
    """
    Упрощенная модель для входящего запроса от Яндекс.Алисы.
    Мы определяем только те поля, которые нам действительно нужны.
    """
    class Session(BaseModel):
        new: bool
        class User(BaseModel):
            user_id: str
        user: User

    class Request(BaseModel):
        original_utterance: str
        type: str

    request: Request
    session: Session
    version: str


class AliceResponse(BaseModel):
    """
    Модель для ответа Яндекс.Алисе.
    """
    class Response(BaseModel):
        text: str
        end_session: bool = True

    response: Response
    version: str = "1.0"