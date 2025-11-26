# -*- coding: utf-8 -*-
"""
login_lg_sem_selenium.py — Login 100% sem navegador
Retorna cookies + URL base do portal LG.
Compatível com Google Colab, Docker, Airflow, etc.
"""

import time
import re
import base64
import requests
from urllib.parse import urlparse
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os

# ===============================
# CONFIGURAÇÕES
# ===============================
usuario_portal = "avieira@bwg.com.br"
senha_portal   = "Kalisba987"

WORK_DIR = "/content"
credentials_path = os.path.join(WORK_DIR, "credentials.json")
token_path = os.path.join(WORK_DIR, "token.json")
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


# ===============================
# LOGIN 2FA – GMAIL
# ===============================
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

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def buscar_codigo_2fa(gmail_service):
    """
    Busca email da LG com código 2FA
    """
    try:
        results = gmail_service.users().messages().list(
            userId="me",
            q="from:cloud@lg.com.br is:unread"
        ).execute()

        msgs = results.get("messages", [])
        if not msgs:
            return None

        msg = gmail_service.users().messages().get(
            userId='me',
            id=msgs[0]["id"],
            format="full"
        ).execute()

        payload = msg["payload"]

        def extrair_texto(part):
            data = part.get("body", {}).get("data")
            if data:
                texto = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                m = re.search(r"\b\d{6}\b", texto)
                if m:
                    return m.group(0)
            return None

        if "parts" in payload:
            for p in payload["parts"]:
                c = extrair_texto(p)
                if c:
                    return c
        else:
            return extrair_texto(payload)

    except Exception as e:
        print("Erro ao buscar código 2FA:", e)

    return None


# ===============================
# LOGIN PADRÃO (SEM SELENIUM)
# ===============================
def executar_login(url_login, modo_autenticacao="PADRAO"):
    print("🌐 Iniciando login sem Selenium:", url_login)

    s = requests.Session()

    # 1) GET inicial → capturar cookies
    r1 = s.get(url_login, allow_redirects=True)
    if r1.status_code != 200 and r1.status_code != 302:
        return {"erro": f"Falha ao acessar login ({r1.status_code})"}

    # 2) Página de login: extrair hidden fields (se houver)
    # (informa a LG que é login legítimo)
    csrf = None
    m = re.search(r'name="__RequestVerificationToken" value="([^"]+)"', r1.text)
    if m:
        csrf = m.group(1)

    payload = {
        "Login": usuario_portal,
        "Senha": senha_portal
    }

    if csrf:
        payload["__RequestVerificationToken"] = csrf

    # 3) POST credenciais
    r2 = s.post(url_login, data=payload, allow_redirects=True)

    # Se for redirecionado para 2FA
    if "ValideCodigo" in r2.url:
        if modo_autenticacao.upper() != "2FA":
            return {"erro": "Conta exige 2FA mas modo_autenticacao!='2FA'"}

        print("📲 Autenticando via 2FA...")

        gmail_service = autenticar_gmail()
        codigo = None

        for i in range(12):
            codigo = buscar_codigo_2fa(gmail_service)
            if codigo:
                print("🔐 Código:", codigo)
                break
            time.sleep(5)

        if not codigo:
            return {"erro": "Código 2FA não recebido."}

        # Enviar o código
        post_2fa = {
            "Codigo": codigo
        }

        r3 = s.post(r2.url, data=post_2fa, allow_redirects=True)
        final = r3
    else:
        final = r2

    # Determinar URL base
    url_final = urlparse(final.url)
    url_base = f"{url_final.scheme}://{url_final.netloc}"

    # Formatar cookies
    cookie_str = "; ".join(f"{c.name}={c.value}" for c in s.cookies)

    print("✅ Login concluído sem Selenium.")
    return {"url": url_base, "cookies": cookie_str}
