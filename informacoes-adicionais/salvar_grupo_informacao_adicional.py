# -*- coding: utf-8 -*-
"""
Lê dados da aba "grupo-informacoes-adicionais" do Google Sheets
e cadastra cada linha no endpoint /GrupoDeInformacaoAdicional/Salvar da LG.
Grava o resultado (mensagem) em uma coluna chamada 'resultado'.

Pode ser chamado com:
    run(url_base, cookies, cliente)
"""

import json
import time
import logging
import requests
import gspread
from google.oauth2.service_account import Credentials

# ==============================
# CONFIGURAÇÕES FIXAS
# ==============================
ENDPOINT_PATH = "/Gente/Produtos/FolhaDePagamento/GrupoDeInformacaoAdicional/Salvar"
IDENTIFICADOR_DA_ABA = "e3eaa866-3fab-4931-bc56-802923127f09"

SPREADSHEET_ID = "1ijwb6D59j_3KQQaUnMifN88L79qvtuIEJ2Cq-yZv82E"
WORKSHEET_TITLE = "grupo-informacoes-adicionais"
COLUNA_RESULTADO = "resultado"

REQUEST_TIMEOUT = 30
REQUEST_PAUSE = 0.8

# Credencial pública do Google Sheets
url = "https://drive.google.com/uc?export=download&id=15Pzgk8O1bgbIH3cfdiBz6qwrzEbdfQtF"
r = requests.get(url)
open("credencial_sheets.json", "wb").write(r.content)
SERVICE_ACCOUNT_FILE = "credencial_sheets.json"

# ==============================
# FUNÇÕES AUXILIARES
# ==============================
def build_session(cookie_str: str, base_url: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Accept": "*/*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Connection": "keep-alive",
        "Origin": base_url,
        "Referer": f"{base_url}/Gente/Produtos/Infraestrutura/InicioPorParametros/Index",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Cookie": cookie_str.strip(),
    })
    return s


def open_sheet(creds_path: str, sheet_id: str, worksheet_title: str):
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(worksheet_title)
    return ws


def enviar_registro(session: requests.Session, url: str, form_data: dict):
    """Envia um POST e retorna a mensagem da resposta."""
    try:
        resp = session.post(url, data=form_data, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return f"Erro HTTP {resp.status_code}"

        try:
            result = resp.json()
        except json.JSONDecodeError:
            return "Resposta inválida (não-JSON)"

        return result.get("mensagem", "(sem mensagem)")

    except Exception as e:
        return f"Erro: {e}"


def garantir_coluna_resultado(ws):
    """Cria a coluna 'resultado' caso não exista e retorna seu índice."""
    cabecalho = ws.row_values(1)
    if COLUNA_RESULTADO in cabecalho:
        return cabecalho.index(COLUNA_RESULTADO) + 1

    nova_coluna = len(cabecalho) + 1
    ws.add_cols(1)
    ws.update_cell(1, nova_coluna, COLUNA_RESULTADO)
    return nova_coluna


# ==============================
# EXECUÇÃO PRINCIPAL
# ==============================
def run(url_base: str, cookies: str, cliente: str):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.info(f"🔹 Iniciando cadastro de grupos de informação adicional para o cliente: {cliente}")

    endpoint = url_base.rstrip("/") + ENDPOINT_PATH
    session = build_session(cookies, url_base)
    ws = open_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, WORKSHEET_TITLE)
    col_resultado = garantir_coluna_resultado(ws)

    registros = ws.get_all_records()
    total = len(registros)
    logging.info(f"📄 {total} registros lidos da planilha.")

    for idx, row in enumerate(registros, start=2):
        codigo = row.get("codigo")
        descricao = row.get("descricao")
        conceito = row.get("codigo_conceito")
        modulo = row.get("modulo")

        form_data = {
            "chaveParaExcluirItem": "Codigo",
            "chaveParaConsultarItem": "Codigo",
            "Cadastro_InserindoNovoRegistro": "true",
            "_TxtCodigo": codigo,
            "Codigo": codigo,
            "cboModulo": modulo,
            "cboConceito": conceito,
            "Descricao": descricao,
            "X-Requested-With": "XMLHttpRequest",
            "identificadorDaAba": IDENTIFICADOR_DA_ABA,
        }

        mensagem = enviar_registro(session, endpoint, form_data)
        logging.info(f"[{idx - 1}/{total}] {codigo} → {mensagem}")

        try:
            ws.update_cell(idx, col_resultado, mensagem)
        except Exception as e:
            logging.warning(f"⚠️ Falha ao atualizar linha {idx}: {e}")

        time.sleep(REQUEST_PAUSE)

    logging.info("✅ Processo concluído com sucesso!")
