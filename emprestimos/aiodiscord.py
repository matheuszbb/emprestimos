import aiohttp
import asyncio
from dataclasses import dataclass

@dataclass
class DiscordResponse:
    success: bool
    result: dict
    error_message: str = None

@dataclass
class MessageInfo:
    message_id: int
    chat_id: int
    text: str

class DiscordBot:
    def __init__(self, token, timeout=3):
        if not token:
            raise ValueError("O token do bot é obrigatório.")
        self.token = token
        self.base_url = "https://discord.com/api/v10"
        self.timeout = timeout

    async def send_request(self, endpoint, payload):
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json"
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    data = await response.json()
                    return DiscordResponse(
                        success=response.status == 200,
                        result=data if response.status == 200 else {},
                        error_message=data.get("message") if response.status != 200 else None
                    )
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout, a requisição para a API do Discord expirou.")
        except Exception as e:
            raise RuntimeError(f"Erro inesperado do tipo '{type(e).__name__}': {str(e)}.\n Resposta esperada: {repr(e)}")

    async def send_message(self, chat_id, text, reply_markup=None, reply_to_message_id=None):
        if reply_markup:
            payload = {
                "content": text
            }
            if reply_markup:
                payload["components"] = reply_markup
            if reply_to_message_id:
                payload["message_reference"] = {"message_id": reply_to_message_id}
            response = await self.send_request(f"channels/{chat_id}/messages", payload)
            if response.success:
                message_data = response.result
                return MessageInfo(
                    message_id=message_data.get("id", 0),
                    chat_id=message_data.get("channel_id", 0),
                    text=message_data.get("content", "")
                )
            return response
        else:
            payload = {"content": text}
            if reply_to_message_id:
                payload["message_reference"] = {"message_id": reply_to_message_id}
            response = await self.send_request(f"channels/{chat_id}/messages", payload)
            if response.success:
                message_data = response.result
                return MessageInfo(
                    message_id=message_data.get("id", 0),
                    chat_id=message_data.get("channel_id", 0),
                    text=message_data.get("content", "")
                )
            return response

    async def send_animation(self, chat_id=None, animation=None, caption=None, reply_markup=None, reply_to_message_id=None):
        return await self.send_photo(chat_id=chat_id, photo=animation, caption=caption, reply_markup=reply_markup, reply_to_message_id=reply_to_message_id)

    async def send_photo(self, chat_id, photo, caption="", reply_markup=None, reply_to_message_id=None):
        if reply_markup:
            payload = {
                "embeds": [{
                    "image": {"url": photo},
                    "description": caption
                }],
                "components": reply_markup
            }
            if reply_to_message_id:
                payload["message_reference"] = {"message_id": reply_to_message_id}
            response = await self.send_request(f"channels/{chat_id}/messages", payload)
            if response.success:
                message_data = response.result
                return MessageInfo(
                    message_id=message_data.get("id", 0),
                    chat_id=message_data.get("channel_id", 0),
                    text=message_data.get("content", "")
                )
            return response
        else:
            payload = {
                "embeds": [{
                    "image": {"url": photo},
                    "description": caption
                }]
            }
            if reply_to_message_id:
                payload["message_reference"] = {"message_id": reply_to_message_id}
            response = await self.send_request(f"channels/{chat_id}/messages", payload)
            if response.success:
                message_data = response.result
                return MessageInfo(
                    message_id=message_data.get("id", 0),
                    chat_id=message_data.get("channel_id", 0),
                    text=message_data.get("content", "")
                )
            return response

    async def send_sticker(self, chat_id, sticker, reply_markup=None, reply_to_message_id=None):
        if reply_markup:
            payload = {
                "sticker_ids": [sticker],
                "components": reply_markup
            }
            if reply_to_message_id:
                payload["message_reference"] = {"message_id": reply_to_message_id}
            response = await self.send_request(f"channels/{chat_id}/messages", payload)
            if response.success:
                message_data = response.result
                return MessageInfo(
                    message_id=message_data.get("id", 0),
                    chat_id=message_data.get("channel_id", 0),
                    text=message_data.get("content", "")
                )
            return response
        else:
            payload = {"sticker_ids": [sticker]}
            if reply_to_message_id:
                payload["message_reference"] = {"message_id": reply_to_message_id}
            response = await self.send_request(f"channels/{chat_id}/messages", payload)
            if response.success:
                message_data = response.result
                return MessageInfo(
                    message_id=message_data.get("id", 0),
                    chat_id=message_data.get("channel_id", 0),
                    text=message_data.get("content", "")
                )
            return response
    
    async def delete_message(self, chat_id, message_id):
        url = f"{self.base_url}/channels/{chat_id}/messages/{message_id}"
        headers = {"Authorization": f"Bot {self.token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as response:
                    if response.status == 204:
                        return {"ok": True, "description": "Mensagem deletada com sucesso."}
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout, a requisição para a API do Discord expirou.")
        except Exception as e:
            raise RuntimeError(f"Erro inesperado do tipo '{type(e).__name__}': {str(e)}.\n Resposta esperada: {repr(e)}")

    async def InlineKeyboardButton(self, text="", url=None):
        # Apenas botões de link (style=5)
        return {
            "type": 2,
            "label": text,
            "style": 5,
            "url": url
        }

    async def InlineKeyboardMarkup(self, buttons):
        # buttons: lista de listas de botões (igual ao Telegram)
        return [{"type": 1, "components": row} for row in buttons]

# Exemplo de uso
async def main():
    bot = DiscordBot(token="")
    chat_id = ""
    # Criando botões de link
    botao1 = await bot.InlineKeyboardButton(text="Site 1", url="https://site1.com")
    botao2 = await bot.InlineKeyboardButton(text="Site 2", url="https://site2.com")
    keyboard = [[botao1, botao2]]
    markup = await bot.InlineKeyboardMarkup(keyboard)
    #mensagem_botoes = await bot.send_message(chat_id, "Veja os sites:", reply_markup=[])
    
    # Imagem simples
    # mensagem_botoes = await bot.send_photo(chat_id, "https://i.gifer.com/origin/25/25dcee6c68fdb7ac42019def1083b2ef_w200.gif", caption="Legenda")

    # # Imagem com botões
    # mensagem_botoes = await bot.send_photo(chat_id, "https://i.gifer.com/origin/25/25dcee6c68fdb7ac42019def1083b2ef_w200.gif", caption="Legenda", reply_markup=markup)

    # Sticker simples
    mensagem_botoes = await bot.send_sticker(chat_id, "796140656941989888")

    # Sticker com botões
    mensagem_botoes = await bot.send_sticker(chat_id, "796140656941989888", reply_markup=markup)

    print(f"Mensagem com botões enviada com ID: {mensagem_botoes.message_id}")

if __name__ == "__main__":
    asyncio.run(main())