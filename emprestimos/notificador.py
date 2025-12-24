import os
import re
import uvloop
import asyncio
import logging
import aiohttp
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

    async def get_parcelas_a_vencer_amanha(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        query = '''
            SELECT p.*, u.username as responsavel_username
            FROM core_parcela p
            LEFT JOIN core_emprestimo e ON p.emprestimo_id = e.id
            LEFT JOIN auth_user u ON e.responsavel_id = u.id
            WHERE p.status = 0 AND date(p.data_fim) = ?
        '''
        async with self.conexao.cursor() as cursor:
            await cursor.execute(query, (amanha,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows] if rows else []


    async def get_parcelas_a_vencer_hoje(self):
        hoje = date.today().isoformat()
        query = '''
            SELECT p.*, u.username as responsavel_username
            FROM core_parcela p
            LEFT JOIN core_emprestimo e ON p.emprestimo_id = e.id
            LEFT JOIN auth_user u ON e.responsavel_id = u.id
            WHERE p.status = 0 AND date(p.data_fim) = ?
        '''
        async with self.conexao.cursor() as cursor:
            await cursor.execute(query, (hoje,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows] if rows else []


    async def get_parcelas_vencidas(self):
        hoje = date.today().isoformat()
        query = '''
            SELECT p.*, u.username as responsavel_username
            FROM core_parcela p
            LEFT JOIN core_emprestimo e ON p.emprestimo_id = e.id
            LEFT JOIN auth_user u ON e.responsavel_id = u.id
            WHERE p.status = 0 AND date(p.data_fim) < ?
        '''
        async with self.conexao.cursor() as cursor:
            await cursor.execute(query, (hoje,))
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
    async def buscar_vencimentos(self):
        parcelas_amanha = await self.db.get_parcelas_a_vencer_amanha()
        parcelas_hoje = await self.db.get_parcelas_a_vencer_hoje()
        parcelas_vencidas = await self.db.get_parcelas_vencidas()

        for parcela in parcelas_amanha:
            await self.notificar_vencimentos(parcela)
        for parcela in parcelas_hoje:
            await self.notificar_vencimentos(parcela)
        for parcela in parcelas_vencidas:
            await self.notificar_vencimentos(parcela)

    async def escape_markdown_v2(self, text):
        escape_chars = r'_\*\[\]\(\)~`>#+\-=|{}.!'
        return re.sub(f'([{escape_chars}])', r'\\\1', text)

    async def notificar_vencimentos(self, parcela):
        if parcela:
            notificacoes = await self.db.get_notificacoes(parcela['responsavel_id'])
            for notificacao in notificacoes:
                chat_id = notificacao['chat_id_val']
                plataforma = notificacao['chat_plataforma']
                token = notificacao['bot_token']
                if plataforma == 'telegram':
                    bot = TelegramBot(token=token)
                else:
                    bot = DiscordBot(token=token)
                cliente = await self.db.get_cliente(parcela['cliente_id'])
                emprestimo = await self.db.get_emprestimo(parcela['emprestimo_id'])

                total_parcelas = emprestimo['parcelas'] if emprestimo else '?'
                porcentagem = f"{emprestimo['porcentagem']}%" if emprestimo else '%'
                admin_url = f"{os.getenv('SITE_URL')}admin/core/emprestimo/{emprestimo['id']}/change/" if emprestimo else '#'

                data_fim = parcela['data_fim'][:10]
                try:
                    data_fim_fmt = datetime.datetime.strptime(data_fim, "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    data_fim_fmt = data_fim

                try:
                    data_inicio_fmt = datetime.datetime.strptime(parcela['data_inicio'][:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    data_inicio_fmt = parcela['data_inicio'][:10] if 'data_inicio' in parcela else ''

                hoje = date.today().isoformat()
                amanha = (date.today() + timedelta(days=1)).isoformat()
                if data_fim < hoje:
                    titulo = f"🚨 **Parcela {parcela['numero_parcela']} VENCIDA\\!**"
                elif data_fim == hoje:
                    titulo = f"⚠️ **Parcela {parcela['numero_parcela']} vence HOJE\\!**"
                elif data_fim == amanha:
                    titulo = f"🔔 **Parcela {parcela['numero_parcela']} vence AMANHÃ\\!**"
                else:
                    titulo = f"📢 **Aviso de Parcela**"

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
                
                asyncio.create_task(self.enviar_mensagem(bot, chat_id, mensagem, plataforma))

    async def enviar_mensagem(self, bot, chat_id, texto, plataforma):
        delays = [10, 20, 60, 120, 300]  # segundos
        for tentativa, delay in enumerate([0] + delays):
            try:
                if plataforma == 'telegram':
                    msg = await bot.send_message(chat_id=chat_id, text=texto, parse_mode="MarkdownV2")
                else:
                    msg = await bot.send_message(chat_id=chat_id, text=texto)
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
                health_url = f"{os.getenv('SITE_URL')}health"
                logging.warning(f"Verificando saúde do serviço em {health_url}...")
                async with aiohttp.ClientSession() as session:
                    async with session.get(health_url) as resp:
                        if resp.status == 200:
                            logging.warning("Serviço está saudável.")
                            break
                        else:
                            logging.warning(f"Serviço retornou status {resp.status}.")
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
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    notificador = Notificador()
    asyncio.run(notificador.main())
