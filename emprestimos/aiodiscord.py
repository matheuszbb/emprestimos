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
    def __init__(self, token, timeout=10):
        if not token:
            raise ValueError("O token do bot é obrigatório.")
        self.token = token
        self.base_url = "https://discord.com/api/v10"
        self.timeout = timeout
        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

    async def get_session(self) -> aiohttp.ClientSession:
        async with self._session_lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(
                        connect=2,
                        sock_read=3,
                    ),
                    connector=aiohttp.TCPConnector(
                        keepalive_timeout=60,
                        limit_per_host=10,
                        ttl_dns_cache=300,
                        use_dns_cache=True,
                    ),
                    headers={
                        "Authorization": f"Bot {self.token}",
                        "Content-Type": "application/json"
                    }
                )
        return self._session

    async def reset_session(self):
        async with self._session_lock:
            if self._session and not self._session.closed:
                await self._session.connector.close()
                await self._session.close()
            self._session = None

    async def send_request(self, endpoint, payload):
        url = f"{self.base_url}/{endpoint}"
        try:
            session = await self.get_session()
            async with session.post(url, json=payload) as response:
                if response.status == 429:
                    raise RuntimeError("Rate limit atingido")
                data = await response.json()
                return DiscordResponse(
                    success=response.status in (200, 204),
                    result=data if response.status in (200, 204) else {},
                    error_message=data.get("message") if response.status not in (200, 204) else None
                )
        except aiohttp.ClientConnectionError:
            await self.reset_session()
            raise RuntimeError("Conexão perdida com o Discord")
        except asyncio.TimeoutError:
            raise TimeoutError("Timeout na requisição para o Discord expirou.")
        except Exception as e:
            raise RuntimeError(f"Erro inesperado do tipo '{type(e).__name__}': {str(e)}")

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

        for tentativa in range(1, 4):  # 3 tentativas
            try:
                session = await self.get_session()
                async with session.delete(url) as response:
                    if response.status == 204:
                        return {"ok": True, "description": "Mensagem deletada com sucesso."}
            except aiohttp.ClientConnectionError:
                await self.reset_session()
                if tentativa == 3:
                    raise RuntimeError("Conexão perdida com o Discord")
            except asyncio.TimeoutError:
                if tentativa == 3:
                    raise TimeoutError("Timeout na requisição para o Discord expirou.")
            
            await asyncio.sleep(tentativa)  # 1s, 2s entre tentativas

    def InlineKeyboardButton(self, text="", url=None):
        # Apenas botões de link (style=5)
        return {
            "type": 2,
            "label": text,
            "style": 5,
            "url": url
        }

    def InlineKeyboardMarkup(self, buttons):
        # buttons: lista de listas de botões (igual ao Telegram)
        return [{"type": 1, "components": row} for row in buttons]

# Exemplo de uso
async def main():
    bot = DiscordBot(token="your_discord_token_here")
    chat_id = "your_channel_id_here"
    # Criando botões de link
    botao1 = bot.InlineKeyboardButton(text="Site 1", url="https://site1.com")
    botao2 = bot.InlineKeyboardButton(text="Site 2", url="https://site2.com")
    keyboard = [[botao1, botao2]]
    markup = bot.InlineKeyboardMarkup(keyboard)
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