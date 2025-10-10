# -*- coding: utf-8 -*-
"""
Coleta "Grupo de Informação Adicional" por conceito no endpoint da LG
e grava os resultados no Google Sheets.

Pode ser chamado com:
    run(url_base, cookies, cliente)
"""

import json
import time
import logging
from typing import Dict, List
import requests
import gspread
from google.oauth2.service_account import Credentials

# ==============================
# VARIÁVEIS GLOBAIS
# ==============================
ENDPOINT_PATH = "/Gente/Produtos/FolhaDePagamento/GrupoDeInformacaoAdicional/ObtenhaListaDeGrupoDeInformacoesAdicionais"
IDENTIFICADOR_DA_ABA = "5039b8f1-6081-456d-8ef7-371b4fa3cdde"

# Google Sheets
SPREADSHEET_ID = "1ijwb6D59j_3KQQaUnMifN88L79qvtuIEJ2Cq-yZv82E"
WORKSHEET_TITLE = "grupo-informacoes-adicionais"

# Credencial do Sheets (via link público)
url = "https://drive.google.com/uc?export=download&id=15Pzgk8O1bgbIH3cfdiBz6qwrzEbdfQtF"
r = requests.get(url)
open("credencial_sheets.json", "wb").write(r.content)
SERVICE_ACCOUNT_FILE = "credencial_sheets.json"

# Conceitos a consultar
CONCEITOS: Dict[int, str] = {
    1000: "Centro de Custos",
    1002: "Órgão Responsável",
    1016: "Cargo",
    1019: "Dependente",
    1020: "Pensionista",
    1028: "Sindicato",
    1029: "Pessoa",
    1031: "Unidade Organizacional",
    1032: "Estabelecimento",
    1034: "Colaborador",
    1077: "Evento",
    1183: "Fornecedor",
    1194: "Autônomo",
}

SHEET_HEADER = [
    "cliente",
    "codigo_conceito",
    "descricao_conceito",
    "modulo",
    "codigo",
    "descricao",
    "ordem",
]

# ==============================
# Funções auxiliares
# ==============================
def build_session(cookie_str: str, base_url: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
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


def fetch_grupos_por_conceito(session, url, identificador_da_aba, conceito, retries=3, timeout=30):
    payload = {"identificadorDaAba": identificador_da_aba, "conceito": str(conceito)}
    for attempt in range(1, retries + 1):
        try:
            resp = session.post(url, data=payload, timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logging.warning(f"Tentativa {attempt}/{retries} falhou para conceito {conceito}: {e}")
            time.sleep(attempt)
    return []


def open_sheet(creds_path, sheet_id, worksheet_title):
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
    gc = gspread.authorize(credentials)
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(worksheet_title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_title, rows=1000, cols=len(SHEET_HEADER))
    return ws


def parse_rows(raw_list, cliente, codigo_conceito, descricao_conceito):
    rows = []
    for item in raw_list:
        dto = item.get("DtoEntidadeInformacaoAdicional", {}) or {}
        rows.append([
            cliente,
            codigo_conceito,
            descricao_conceito,
            dto.get("Modulo"),
            item.get("Codigo"),
            item.get("Descricao"),
            item.get("Ordem"),
        ])
    return rows

# ==============================
# Execução principal
# ==============================
def run(url_base: str, cookies: str, cliente: str):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ws = open_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, WORKSHEET_TITLE)
    ws.clear()
    ws.update(values=[SHEET_HEADER], range_name="A1")

    session = build_session(cookies, url_base)
    endpoint = url_base.rstrip("/") + ENDPOINT_PATH
    total = 0
    buffer = []

    for codigo_conceito, descricao_conceito in CONCEITOS.items():
        logging.info(f"Consultando {descricao_conceito} ({codigo_conceito})")
        data = fetch_grupos_por_conceito(session, endpoint, IDENTIFICADOR_DA_ABA, codigo_conceito)
        rows = parse_rows(data, cliente, codigo_conceito, descricao_conceito)
        buffer.extend(rows)
        total += len(rows)
        time.sleep(0.5)

    if buffer:
        ws.append_rows(buffer, value_input_option="RAW")

    logging.info(f"✅ Concluído! {total} linhas gravadas no Google Sheets.")
