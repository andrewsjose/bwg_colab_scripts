# -*- coding: utf-8 -*-
"""
login_lg.py — versão Playwright FINAL (SEM 2FA)
Compatível com Google Colab + login direto no portal LG.
"""

import json
import os
from playwright.async_api import async_playwright


# ============================================================
# 🔐 Ler credenciais locais
# ============================================================
def carregar_credenciais():
    with open("/content/login_cred.json", "r") as f:
        return json.load(f)


# ============================================================
# 🚀 LOGIN PRINCIPAL (SEM 2FA)
# ============================================================
async def login_lg(cliente):

    cred = carregar_credenciais()
    usuario = cred["usuario"]
    senha = cred["senha"]

    url_login = f"https://login.lg.com.br/login/gente/{cliente}"
    print(f"🌐 Iniciando login Playwright → {url_login}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )
        page = await browser.new_page()

        # Abrir página
        await page.goto(url_login, timeout=60000)
        print("📄 Página de login aberta.")

        # Informar usuário
        await page.fill("#Login", usuario)
        await page.keyboard.press("Enter")
        print("📧 Usuário informado.")

        # Informar senha
        await page.fill("#Senha", senha)
        await page.keyboard.press("Enter")
        print("🔑 Senha enviada.")

        # Aguardar navegação final
        print("⏳ Aguardando portal carregar...")
        await page.wait_for_load_state("networkidle", timeout=60000)

        # Capturar cookies
        cookies_list = await page.context.cookies()
        cookies = "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])

        # Base da URL do portal
        base_url = page.url.split("/Gente")[0]

        await browser.close()

        print("✅ Login concluído!")
        return {
            "url": base_url,
            "cookies": cookies
        }
