import os
import re
import uvloop
import asyncio
import logging
import httpx
import datetime
import aiosqlite
from aiotelegram import TelegramBot
from aiodiscord import DiscordBot
from datetime import date, timedelta

class DB():
    def __init__(self,):
        self.dbpath = "db.sqlite3"
        self.conexao = None

    async def connect(self):
        self.conexao = await aiosqlite.connect(self.dbpath)
        self.conexao.row_factory = aiosqlite.Row
        await self.conexao.execute("PRAGMA foreign_keys = ON")

    async def get_cliente(self, cliente_id):
        async with self.conexao.cursor() as cursor:
            await cursor.execute("SELECT * FROM core_cliente WHERE id = ?", (cliente_id,))
            row = await cursor.fetchone()
            return dict(row) if row else {}

    async def get_emprestimo(self, emprestimo_id):
        async with self.conexao.cursor() as cursor:
            await cursor.execute("SELECT * FROM core_emprestimo WHERE id = ?", (emprestimo_id,))
            row = await cursor.fetchone()
            return dict(row) if row else {}

    async def get_parcelas_a_vencer(self, dias):
        """
        Busca parcelas com vencimento em X dias.
        
        Args:
            dias (int): Dias até o vencimento
                - dias > 0: Parcelas que vencem em X dias
                - dias = 0: Parcelas que vencem hoje
                - dias < 0: Parcelas vencidas (usa valor absoluto como referência)
                
        Returns:
            list: Lista de parcelas encontradas
        """
        if dias < 0:
            # Parcelas vencidas: data_fim < hoje
            data_ref = date.today().isoformat()
            condition = "date(p.data_fim) < ?"
        else:
            # Parcelas que vencem em X dias
            data_ref = (date.today() + timedelta(days=dias)).isoformat()
            condition = "date(p.data_fim) = ?"
        
        query = f'''
            SELECT p.*, u.username as responsavel_username
            FROM core_parcela p
            LEFT JOIN core_emprestimo e ON p.emprestimo_id = e.id
            LEFT JOIN auth_user u ON e.responsavel_id = u.id
            WHERE p.status = 0 AND {condition}
        '''
        async with self.conexao.cursor() as cursor:
            await cursor.execute(query, (data_ref,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows] if rows else []

    async def get_notificacoes(self, user_id=None):
        query = '''
            SELECT n.*, 
                    t.token as bot_token, t.nome as bot_nome, t.plataforma as bot_plataforma, t.dono_id as bot_dono_id,
                    c.chat_id as chat_id_val, c.nome as chat_nome, c.plataforma as chat_plataforma, c.dono_id as chat_dono_id,
                    u.username as dono_username, u.email as dono_email
            FROM core_notificacao n
            LEFT JOIN core_bottoken t ON n.token_id = t.id
            LEFT JOIN core_chatid c ON n.chat_id_id = c.id
            LEFT JOIN auth_user u ON n.dono_id = u.id
        '''
        params = ()
        if user_id is not None:
            query += " WHERE n.dono_id = ?"
            params = (user_id,)
        async with self.conexao.cursor() as cursor:
            await cursor.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows] if rows else []

class Notificador():
    def __init__(self):
        """Inicializa o notificador com cache de bots."""
        self.db = None
        self._telegram_bots = {}  # Cache: token -> TelegramBot
        self._discord_bots = {}   # Cache: token -> DiscordBot
        self._pending_tasks = []  # Lista para rastrear tasks pendentes
        self._semaphoro = asyncio.Semaphore(20)  # Limita a 20 processos paralelos
        self._contador_mensagens = 0  # Contador de mensagens enviadas

    async def buscar_vencimentos(self):
        """
        Busca parcelas em diferentes períodos de vencimento e agrupa mensagens por usuário.
        Envia sequencialmente para cada usuário com delay de 3s entre mensagens.
        """
        periodos = [3, 2, 1, 0, -1]
        
        # Agrupar mensagens por (token, chat_id, plataforma)
        mensagens_agrupadas = {}
        
        for dias in periodos:
            parcelas = await self.db.get_parcelas_a_vencer(dias)
            for parcela in parcelas:
                # Prepara dados de mensagem sem enviar
                dados_mensagens = await self.preparar_dados_mensagem(parcela, dias_restantes=dias)
                for token, chat_id, plataforma, mensagem_texto in dados_mensagens:
                    chave = (token, chat_id, plataforma)
                    if chave not in mensagens_agrupadas:
                        mensagens_agrupadas[chave] = []
                    mensagens_agrupadas[chave].append(mensagem_texto)
        
        # Criar tasks para enviar mensagens agrupadas por usuário
        for (token, chat_id, plataforma), textos_mensagens in mensagens_agrupadas.items():
            task = asyncio.create_task(
                self._enviar_com_fila(token, chat_id, plataforma, textos_mensagens)
            )
            self._pending_tasks.append(task)

    async def escape_markdown_v2(self, text):
        escape_chars = r'_\*\[\]\(\)~`>#+\-=|{}.!'
        return re.sub(f'([{escape_chars}])', r'\\\1', text)

    async def preparar_dados_mensagem(self, parcela, dias_restantes=None):
        """
        Prepara dados de mensagens a serem enviadas para uma parcela.
        
        Returns:
            list: Lista de tuplas (token, chat_id, plataforma, mensagem_texto)
        """
        if not parcela:
            return []
        
        notificacoes = await self.db.get_notificacoes(parcela['responsavel_id'])
        dados_mensagens = []
        
        for notificacao in notificacoes:
            chat_id = notificacao['chat_id_val']
            plataforma = notificacao['chat_plataforma']
            token = notificacao['bot_token']
            
            cliente = await self.db.get_cliente(parcela['cliente_id'])
            emprestimo = await self.db.get_emprestimo(parcela['emprestimo_id'])

            total_parcelas = emprestimo['parcelas'] if emprestimo else '?'
            porcentagem = f"{emprestimo['porcentagem']}%" if emprestimo else '%'
            admin_url = f"{os.getenv('SITE_URL')}emprestimosadmindjango/core/emprestimo/{emprestimo['id']}/change/" if emprestimo else '#'

            data_fim = parcela['data_fim'][:10]
            try:
                data_fim_fmt = datetime.datetime.strptime(data_fim, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                data_fim_fmt = data_fim

            try:
                data_inicio_fmt = datetime.datetime.strptime(parcela['data_inicio'][:10], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                data_inicio_fmt = parcela['data_inicio'][:10] if 'data_inicio' in parcela else ''

            # Define o título baseado em dias_restantes
            if dias_restantes is None:
                hoje = date.today().isoformat()
                data_vencimento = parcela['data_fim'][:10]
                dias = (datetime.datetime.strptime(data_vencimento, "%Y-%m-%d").date() - date.today()).days
                dias_restantes = dias
            
            if dias_restantes < 0:
                titulo = f"🚨 **Parcela {parcela['numero_parcela']} VENCIDA\\!**"
            elif dias_restantes == 0:
                titulo = f"⚠️ **Parcela {parcela['numero_parcela']} vence HOJE\\!**"
            elif dias_restantes == 1:
                titulo = f"🔔 **Parcela {parcela['numero_parcela']} vence AMANHÃ\\!**"
            elif dias_restantes == 2:
                titulo = f"📅 **Parcela {parcela['numero_parcela']} vence em 2 DIAS\\!**"
            elif dias_restantes == 3:
                titulo = f"📆 **Parcela {parcela['numero_parcela']} vence em 3 DIAS\\!**"
            else:
                titulo = f"📢 **Aviso de Parcela {parcela['numero_parcela']}**"

            valor_formatado_parcela = await self.escape_markdown_v2(f"{parcela['valor']:,.2f}")
            valor_formatado_emprestimo = await self.escape_markdown_v2(f"{emprestimo['valor']:,.2f}") if emprestimo else '0,00'
            responsavel_formatado = await self.escape_markdown_v2(parcela.get('responsavel_username', ''))
            motivo = await self.escape_markdown_v2(emprestimo.get('motivo', ''))

            mensagem = (
                f"{titulo}\n\n"
                f"👤 Cliente: {cliente['nome_completo'] if cliente else ''}\n"
                f"💳 Parcela: {parcela['numero_parcela']} de {total_parcelas}\n"
                f"💰 Valor Empréstimo: R$ {valor_formatado_emprestimo}\n"
                f"💰 Valor Parcela: R$ {valor_formatado_parcela}\n"
                f"📆 Início: {data_inicio_fmt}\n"
                f"📅 Vencimento: {data_fim_fmt}\n"
                f"📈 Porcentagem: {porcentagem}\n"
                f"🔗 Status: {'Pendente' if not parcela['status'] else 'Paga'}\n"
                f"👨‍💼 Responsável: {responsavel_formatado}\n"
                f"📝 Motivo: {motivo}\n"
                f"\n🔗 [Ver Empréstimo no Admin]({admin_url})"
            )
            
            dados_mensagens.append((token, chat_id, plataforma, mensagem))
        
        return dados_mensagens

    def _get_telegram_bot(self, token):
        """
        Obtém ou cria uma instância de TelegramBot cacheada.
        Reutiliza a mesma sessão para múltiplas mensagens do mesmo token.
        """
        if token not in self._telegram_bots:
            self._telegram_bots[token] = TelegramBot(token=token)
        return self._telegram_bots[token]

    def _get_discord_bot(self, token):
        """
        Obtém ou cria uma instância de DiscordBot cacheada.
        Reutiliza a mesma sessão para múltiplas mensagens do mesmo token.
        """
        if token not in self._discord_bots:
            self._discord_bots[token] = DiscordBot(token=token)
        return self._discord_bots[token]

    async def _cleanup_bots(self):
        """
        Fecha todas as sessões abertas dos bots.
        Deve ser chamado ao final de cada ciclo ou ao encerrar.
        """
        for bot in self._telegram_bots.values():
            try:
                await bot.reset_session()
            except Exception as e:
                logging.warning(f"Erro ao fechar sessão Telegram: {e}")
        
        for bot in self._discord_bots.values():
            try:
                await bot.reset_session()
            except Exception as e:
                logging.warning(f"Erro ao fechar sessão Discord: {e}")
        
        self._telegram_bots.clear()
        self._discord_bots.clear()

    async def _wait_for_pending_tasks(self):
        """
        Aguarda a conclusão de todas as tasks pendentes.
        """
        if self._pending_tasks:
            try:
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                logging.warning(f"Todas as {self._contador_mensagens} mensagens foram processadas.")
            except Exception as e:
                logging.error(f"Erro ao aguardar tasks: {e}")
            finally:
                self._pending_tasks.clear()
                self._contador_mensagens = 0  # Reseta contador para próximo ciclo

    async def enviar_mensagens_usuario_sequencial(self, token, chat_id, plataforma, textos_mensagens):
        """
        Envia múltiplas mensagens para o mesmo usuário de forma sequencial.
        Aguarda 3 segundos entre cada mensagem para evitar rate limit do Telegram.
        
        Args:
            token: Token do bot
            chat_id: ID do chat/usuário
            plataforma: 'telegram' ou 'discord'
            textos_mensagens: Lista de textos das mensagens
        """
        # Obtém bot do cache
        if plataforma == 'telegram':
            bot = self._get_telegram_bot(token)
        else:
            bot = self._get_discord_bot(token)
        
        for i, texto in enumerate(textos_mensagens):
            # Aguarda 3 segundos entre mensagens do mesmo usuário
            if i > 0:
                await asyncio.sleep(3)
            
            try:
                await self.enviar_mensagem(bot, chat_id, texto, plataforma)
            except Exception as e:
                logging.error(f"Erro ao enviar mensagem para {chat_id}: {e}")

    async def _enviar_com_fila(self, token, chat_id, plataforma, textos_mensagens):
        """
        Wrapper que controla concorrência usando semáforo (fila com limite de 20 processos).
        Garante que no máximo 20 usuarios recebem mensagens em paralelo.
        """
        async with self._semaphoro:
            await self.enviar_mensagens_usuario_sequencial(token, chat_id, plataforma, textos_mensagens)

    async def enviar_mensagem(self, bot, chat_id, texto, plataforma):
        delays = [10, 20, 60, 120, 300]  # segundos
        for tentativa, delay in enumerate([0] + delays):
            try:
                if plataforma == 'telegram':
                    msg = await bot.send_message(chat_id=chat_id, text=texto, parse_mode="MarkdownV2")
                else:
                    msg = await bot.send_message(chat_id=chat_id, text=texto)
                self._contador_mensagens += 1  # Incrementa contador de mensagens
                logging.warning(f"Mensagem enviada para {chat_id} após {tentativa} tentativa(s).")
                break
            except Exception as execao:
                if tentativa < len(delays):
                    logging.warning(f"Tentativa {tentativa+1} falhou para {chat_id}. Erro: {execao}. Retentando em {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logging.critical(f"Mensagem NÃO enviada para o {chat_id} após {tentativa+1} tentativas. Erro final: {execao}")

    async def health_check(self):
        while True:
            try:
                health_url = f"{os.getenv('SITE_URL')}health/"
                logging.warning(f"Verificando saúde do serviço em {health_url}...")
                async with httpx.AsyncClient() as client:
                    resp = await client.get(health_url)
                    if resp.status_code == 200:
                        logging.warning("Serviço está saudável.")
                        break
                    else:
                        logging.warning(f"Serviço retornou status {resp.status_code}.")
            except Exception as e:
                logging.error(f"Erro ao verificar saúde do serviço: {e}")
            await asyncio.sleep(1)

    async def main(self):
        await self.health_check()

        db = DB()
        await db.connect()
        self.db = db

        while True:
            await self.buscar_vencimentos()
            
            # Aguarda que TODAS as mensagens sejam enviadas antes de fechar as sessões
            await self._wait_for_pending_tasks()
            
            # Fecha todas as sessões de bots para evitar "Unclosed client session"
            await self._cleanup_bots()
            
            logging.critical("Notificações enviadas. Aguardando até a próxima meia-noite...")

            # Calcula segundos até a próxima meia-noite
            agora = datetime.datetime.now()
            amanha = agora + datetime.timedelta(days=1)
            proxima_meia_noite = amanha.replace(hour=0, minute=0, second=0, microsecond=0)
            segundos_ate_meia_noite = (proxima_meia_noite - agora).total_seconds()

            await asyncio.sleep(segundos_ate_meia_noite)

if __name__ == "__main__":
    logging.basicConfig(
        format='%(asctime)s %(lineno)d >> %(message)s',
        datefmt='%d/%m/%Y %H:%M:%S',
        level=logging.WARNING,  # Nível de log que você deseja (CRITICAL, DEBUG, INFO, etc.)
        handlers=[
        #logging.FileHandler('log.log', encoding='utf-8'),  # Log em arquivo
        logging.StreamHandler()  # Log no console
        ]
    )    
    notificador = Notificador()
    asyncio.run(notificador.main(), loop_factory=uvloop.new_event_loop)
