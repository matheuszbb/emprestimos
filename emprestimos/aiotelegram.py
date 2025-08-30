import aiohttp
import asyncio
import uvloop
from dataclasses import dataclass

@dataclass
class TelegramResponse:
    ok: bool
    result: dict
    description: str = None

@dataclass
class MessageInfo:
    message_id: int
    chat_id: int
    text: str

class TelegramBot:
    def __init__(self, token, timeout=3, parse_mode="HTML", disable_web_page_preview=True):
        if not token:
            raise ValueError("O token do bot é obrigatório.")
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.timeout = timeout
        self.parse_mode = parse_mode
        self.disable_web_page_preview = disable_web_page_preview

    async def send_request(self, method, payload):
        url = f"{self.base_url}/{method}"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(url, json=payload) as response:
                    data = await response.json()
                    return TelegramResponse(
                        ok=data.get("ok"),
                        result=data.get("result", {}),
                        description=data.get("description")
                    )
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout, a requisição para a API do Telegram expirou.")
        except Exception as e:
            raise RuntimeError(f"Erro inesperado do tipo '{type(e).__name__}': {str(e)}.\n Resposta esperada: {repr(e)}")

    async def send_message(self, chat_id=None, text=None, parse_mode=None, reply_markup=None, disable_web_page_preview=None,reply_to_message_id=None):
        if not chat_id:
            raise ValueError("O chat_id é obrigatório.")
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode or self.parse_mode,
            "disable_web_page_preview": disable_web_page_preview if disable_web_page_preview is not None else self.disable_web_page_preview
        }
        if reply_markup:
            payload["reply_markup"] = {"inline_keyboard": reply_markup}
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id             
        response = await self.send_request("sendMessage", payload)
        if response.ok:
            message_data = response.result
            return MessageInfo(
                message_id = message_data.get("message_id", 0),
                chat_id = message_data.get("chat", {}).get("id"),
                text = message_data.get("text",""),
            )
        return response

    async def send_photo(self, chat_id=None, photo=None, caption=None, parse_mode=None, reply_markup=None, disable_web_page_preview=None,reply_to_message_id=None):
        if not chat_id:
            raise ValueError("O chat_id é obrigatório.")
        payload = {
            "chat_id": chat_id,
            "photo": photo,
            "caption": caption,
            "parse_mode": parse_mode or self.parse_mode,
            "disable_web_page_preview": disable_web_page_preview if disable_web_page_preview is not None else self.disable_web_page_preview
        }
        if reply_markup:
            payload["reply_markup"] = {"inline_keyboard": reply_markup}
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id             
        response = await self.send_request("sendPhoto", payload)
        if response.ok:
            message_data = response.result
            return MessageInfo(
                message_id = message_data.get("message_id", 0),
                chat_id = message_data.get("chat", {}).get("id"),
                text = message_data.get("text",""),
            )
        return response

    async def send_sticker(self, chat_id=None, sticker=None, reply_markup=None,reply_to_message_id=None):
        if not chat_id:
            raise ValueError("O chat_id é obrigatório.")
        payload = {
            "chat_id": chat_id,
            "sticker": sticker
        }
        if reply_markup:
            payload["reply_markup"] = {"inline_keyboard": reply_markup}
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id             
        response = await self.send_request("sendSticker", payload)
        if response.ok:
            message_data = response.result
            return MessageInfo(
                message_id = message_data.get("message_id", 0),
                chat_id = message_data.get("chat", {}).get("id"),
                text = message_data.get("text",""),
            )
        return response
    
    async def send_animation(self, chat_id=None, animation=None, caption=None, parse_mode=None, reply_markup=None, disable_web_page_preview=None,reply_to_message_id=None):
        if not chat_id:
            raise ValueError("O chat_id é obrigatório.")
        payload = {
            "chat_id": chat_id,
            "animation": animation,
            "caption": caption,
            "parse_mode": parse_mode or self.parse_mode,
            "disable_web_page_preview": disable_web_page_preview if disable_web_page_preview is not None else self.disable_web_page_preview
        }
        if reply_markup:
            payload["reply_markup"] = {"inline_keyboard": reply_markup}
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id             
        response = await self.send_request("sendAnimation", payload)
        if response.ok:
            message_data = response.result
            return MessageInfo(
                message_id = message_data.get("message_id", 0),
                chat_id = message_data.get("chat", {}).get("id"),
                text = message_data.get("text",""),
            )
        return response
    
    async def delete_message(self, chat_id=None, message_id=None):
        if not chat_id:
            raise ValueError("O chat_id é obrigatório.")
        if not message_id:
            raise ValueError("O message_id é obrigatório.")
        payload = {
            "chat_id": chat_id,
            "message_id": message_id
        }
        return await self.send_request("deleteMessage", payload)

    async def InlineKeyboardButton(self, text="", url=""):
        button = {
            "text": text,
            "url": url
        }
        return button
    
    async def InlineKeyboardMarkup(self, buttons):   
        inline_buttons = []
        for button in buttons:
            inline_buttons.append(button)
        return inline_buttons
    
# Exemplo de uso
async def main():
    bot = TelegramBot(token="token")
    chat_id = "chat_id"
    keyboard = []
    button = await bot.InlineKeyboardButton(text="Botão 1", url="https://site1.com")
    keyboard.append([button])
    button = await bot.InlineKeyboardButton(text="Botão 2", url="https://site2.com")
    keyboard.append([button])
    botoes = await bot.InlineKeyboardMarkup(keyboard)
    texto = "Escolha uma opção:<p><br></p><i>teste</i>".replace('<p><br></p>', "\n\n").replace('</p><p>', "\n").replace('<p>', "").replace('</p>', "")
    sticker_id = "CAACAgEAAxkBAAEKy1plXS_OkfIkC7JKYqs7jeVlJyuVBgAC4QIAAm9g-UZesNP5SGZaVjME"
    #mensagem = await bot.send_message(chat_id=chat_id, text=texto, reply_markup=botoes)
    mensagem = await bot.send_sticker(chat_id=chat_id, sticker=sticker_id, reply_markup=botoes)
    print(mensagem.message_id)
    

    # # Deletar mensagem enviada
    # if isinstance(mensagem, MessageInfo):
    #     delete_resposta = await bot.delete_message(chat_id=chat_id, message_id=mensagem.message_id)
    #     print(delete_resposta)

if __name__ == "__main__":
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    asyncio.run(main())  # Inicia o loop de eventos