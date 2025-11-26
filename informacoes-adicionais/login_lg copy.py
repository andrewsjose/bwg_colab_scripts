# -*- coding: utf-8 -*-
"""
login_lg.py — versão final compatível com Google Colab
Executa login no portal LG (modo headless) e retorna cookies + URL base.
"""

import os
import time
import json
import base64
import re
import logging
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================
log = print
WORK_DIR = "/content"
credentials_path = os.path.join(WORK_DIR, "credentials.json")
token_path = os.path.join(WORK_DIR, "token.json")

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
usuario_portal = "avieira@bwg.com.br"
senha_portal = "Kalisba987"


# ============================================================
# INICIALIZA O CHROME DRIVER (Colab)
# ============================================================
def iniciar_driver_colab():
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium-browser"

    # Configurações obrigatórias do Colab
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--no-zygote")
    chrome_options.add_argument("--log-level=3")

    # ESTE é o chromedriver correto
    service = Service("/usr/bin/chromedriver")

    driver = webdriver.Chrome(
        service=service,
        options=chrome_options
    )

    return driver




# ============================================================
# GMAIL - AUTENTICAÇÃO E BUSCA DO CÓDIGO 2FA
# ============================================================
def autenticar_gmail():
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def buscar_codigo_2fa(service):
    try:
        results = service.users().messages().list(
            userId='me', q='from:cloud@lg.com.br is:unread'
        ).execute()
        msgs = results.get('messages', [])
        if not msgs:
            return None

        msg = service.users().messages().get(userId='me', id=msgs[0]['id'], format='full').execute()
        body = msg['payload']

        def extrair_texto(part):
            data = part.get('body', {}).get('data')
            if data:
                texto = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                match = re.search(r"\b\d{6}\b", texto)
                if match:
                    return match.group(0)
            return None

        if 'parts' in body:
            for part in body['parts']:
                codigo = extrair_texto(part)
                if codigo:
                    return codigo
        else:
            return extrair_texto(body)
        return None
    except Exception as e:
        log(f"⚠️ Erro ao buscar código 2FA: {e}")
        return None


# ============================================================
# LOGIN PRINCIPAL
# ============================================================
def executar_login(url_login="https://login.lg.com.br/login/gente/bwg_braza", modo_autenticacao="PADRAO"):
    log(f"🌐 Iniciando login para: {url_login}")

    driver = None
    try:
        driver = iniciar_driver_colab()
        wait = WebDriverWait(driver, 25)

        driver.get(url_login)
        log("✅ Página de login acessada.")

        # Campo de login
        try:
            input_login = wait.until(EC.presence_of_element_located((By.ID, "Login")))
            input_login.send_keys(usuario_portal)
            input_login.send_keys(Keys.RETURN)
            log("📧 Usuário informado.")
        except TimeoutException:
            raise Exception("Campo de login não encontrado.")

        # Campo de senha
        try:
            input_senha = wait.until(EC.presence_of_element_located((By.ID, "Senha")))
            input_senha.send_keys(senha_portal)
            input_senha.send_keys(Keys.RETURN)
            log("🔑 Senha informada.")
        except TimeoutException:
            raise Exception("Campo de senha não encontrado.")

        # Validação 2FA, se necessário
        if modo_autenticacao.upper() == "2FA":
            log("📲 Aguardando validação 2FA...")
            wait.until(EC.url_contains("ValideCodigo"))
            input_codigo = wait.until(EC.presence_of_element_located((By.ID, "Codigo")))
            gmail_service = autenticar_gmail()

            codigo = None
            for tentativa in range(12):
                codigo = buscar_codigo_2fa(gmail_service)
                if codigo:
                    log(f"✅ Código 2FA obtido: {codigo}")
                    break
                log(f"Tentativa {tentativa+1}/12: código ainda não recebido...")
                time.sleep(5)

            if not codigo:
                raise Exception("Não foi possível obter o código 2FA.")
            input_codigo.send_keys(codigo)
            input_codigo.send_keys(Keys.RETURN)
            log("📨 Código enviado com sucesso.")

        # Espera carregamento e coleta cookies
        time.sleep(5)
        log("🍪 Tentando capturar cookies...")

        cookies_capturados = {c['name']: c['value'] for c in driver.get_cookies()}
        cookies_str = "; ".join(f"{k}={v}" for k, v in cookies_capturados.items())
        url_base = urlparse(driver.current_url)._replace(path="", query="", fragment="").geturl()

        resultado = {"cookies": cookies_str, "url": url_base}

        #print(json.dumps(resultado, indent=2, ensure_ascii=False))
        log("✅ Login concluído com sucesso.")
        return resultado

    except Exception as e:
        log(f"❌ Erro durante o login: {e}")
        return {"erro": str(e)}

    finally:
        if driver:
            driver.quit()
            log("🧹 Driver encerrado.")
