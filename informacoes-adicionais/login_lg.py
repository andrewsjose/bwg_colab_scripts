# -*- coding: utf-8 -*-
"""
login_lg.py — Versão Playwright com 2FA via Gmail
Compatível com Google Colab / Jupyter.
"""

import os
import re
import time
import json
import base64
import logging
import nest_asyncio
nest_asyncio.apply()

import asyncio
from urllib.parse import urlparse

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from playwright.async_api import async_playwright


# ============================================================
# CONFIGURAÇÕES
# ============================================================
WORK_DIR = "/content"

credentials_path = os.path.join(WORK_DIR, "credentials.json")
token_path       = os.path.join(WORK_DIR, "token.json")

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

LOGIN_EMAIL = "avieira@bwg.com.br"
LOGIN_SENHA = "Kalisba987"

log = print


# ============================================================
# AUTENTICAÇÃO NO GMAIL (para buscar código 2FA)
# ============================================================
def autenticar_gmail():
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise Exception("Arquivo credentials.json não encontrado. Envie para o Colab.")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def extrair_codigo_email(msg):
    try:
        payload = msg['payload']

        def decode_part(part):
            data = part.get("body", {}).get("data")
            if not data:
                return None
            text = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            m = re.search(r"\b\d{6}\b", text)
            return m.group(0) if m else None

        if "parts" in payload:
            for p in payload["parts"]:
                codigo = decode_part(p)
                if codigo:
                    return codigo
        else:
            return decode_part(payload)

    except Exception:
        return None

    return None


def buscar_codigo_2fa(gmail_service):
    try:
        results = gmail_service.users().messages().list(
            userId="me",
            q="from:cloud@lg.com.br is:unread"
        ).execute()

        msgs = results.get("messages", [])
        if not msgs:
            return None

        msg = gmail_service.users().messages().get(
            userId="me", id=msgs[0]["id"], format="full"
        ).execute()

        return extrair_codigo_email(msg)

    except Exception as e:
        log(f"⚠️ Erro lendo Gmail: {e}")
        return None


# ============================================================
# LOGIN COM PLAYWRIGHT
# ============================================================
async def login_lg(cliente="bwg_template", modo_autenticacao="PADRAO"):
    """
    Executa login no LG e retorna cookies + url_base.
    """
    url_login = f"https://login.lg.com.br/login/gente/{cliente}"
    log(f"\n🌐 Iniciando login Playwright → {url_login}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        page = await browser.new_page()

        # 1. Abre página inicial
        await page.goto(url_login)
        log("📄 Página de login aberta.")

        # 2. Preenche usuário
        await page.fill("#Login", LOGIN_EMAIL)
        await page.keyboard.press("Enter")
        log("📧 Usuário informado.")

        # 3. Preenche senha
        await page.wait_for_selector("#Senha")
        await page.fill("#Senha", LOGIN_SENHA)
        await page.keyboard.press("Enter")
        log("🔑 Senha enviada.")

        # 4. Se tiver 2FA → buscar código no Gmail
        if modo_autenticacao.upper() == "2FA":
            log("📲 Aguardando tela de código 2FA...")
            await page.wait_for_selector("#Codigo", timeout=25000)

            gmail = autenticar_gmail()

            codigo = None
            for tent in range(12):
                codigo = buscar_codigo_2fa(gmail)
                if codigo:
                    log(f"✅ Código 2FA recebido: {codigo}")
                    break
                log(f"Tentativa {tent+1}/12 — aguardando e-mail...")
                time.sleep(4)

            if not codigo:
                raise Exception("Não foi possível obter o código 2FA do Gmail.")

            await page.fill("#Codigo", codigo)
            await page.keyboard.press("Enter")
            log("📨 Código 2FA enviado.")

        # 5. Aguarda redirecionamento final
        await page.wait_for_timeout(6000)

        final_url = page.url
        log(f"🏁 URL final após login: {final_url}")

        parsed = urlparse(final_url)
        url_base = f"{parsed.scheme}://{parsed.netloc}"

        # Extrai cookies
        cookies_list = await page.context.cookies()
        cookies_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])

        await browser.close()

        log("🍪 Cookies capturados com sucesso.\n")
        return {
            "url": url_base,
            "cookies": cookies_str
        }


# ============================================================
# EXECUÇÃO DIRETA NO COLAB
# ============================================================
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()

    print("Executando login de teste...")
    res = asyncio.run(login_lg("bwg_template", modo_autenticacao="PADRAO"))
    print(json.dumps(res, indent=2, ensure_ascii=False))

