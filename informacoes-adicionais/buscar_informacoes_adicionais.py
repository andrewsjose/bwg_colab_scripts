# -*- coding: utf-8 -*-
"""
Coleta "Informações Adicionais" por conceito no endpoint da LG
e grava os resultados no Google Sheets.

Pode ser chamado com:
    run(url_base, cookies, cliente)
"""

import json
import time
import logging
from typing import Dict, List, Any
import requests
import gspread
from google.oauth2.service_account import Credentials

# ==============================
# VARIÁVEIS GLOBAIS
# ==============================
ENDPOINT_PATH = "/Gente/Produtos/FolhaDePagamento/InformacaoAdicional/ObtenhaListaDeInformacoesAdicionais"
IDENTIFICADOR_DA_ABA = "5039b8f1-6081-456d-8ef7-371b4fa3cdde"

SPREADSHEET_ID = "1ijwb6D59j_3KQQaUnMifN88L79qvtuIEJ2Cq-yZv82E"
WORKSHEET_TITLE = "informacoes-adicionais"

# Credencial do Sheets
url = "https://drive.google.com/uc?export=download&id=15Pzgk8O1bgbIH3cfdiBz6qwrzEbdfQtF"
r = requests.get(url)
open("credencial_sheets.json", "wb").write(r.content)
SERVICE_ACCOUNT_FILE = "credencial_sheets.json"

REQUEST_TIMEOUT = 30
REQUEST_PAUSE = 0.5
RETRIES = 3

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

# ==============================
# FUNÇÕES AUXILIARES
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


def fetch_informacoes(session, url, identificador_da_aba, conceito, retries=3, timeout=30):
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
        ws = sh.add_worksheet(title=worksheet_title, rows=2000, cols=60)
    return ws


def normalize_value(v: Any) -> Any:
    """Converte dicts e listas para JSON string."""
    if isinstance(v, (dict, list)):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    return v


def parse_rows(data, cliente, codigo_conceito, descricao_conceito):
    rows = []
    for item in data:
        grupo = item.get("DtoGrupoDeInformacoesAdicionais", {}) or {}
        entidade = grupo.get("DtoEntidadeInformacaoAdicional", {}) or {}
        codigo_inf = grupo.get("Codigo")
        desc_inf = grupo.get("Descricao")
        modulo = entidade.get("Modulo")

        flat = {k: normalize_value(v) for k, v in item.items()}

        prefixo = [
            cliente,
            descricao_conceito,
            modulo,
            codigo_conceito,
            codigo_inf,
            desc_inf,
        ]
        resto = [flat.get(k) for k in sorted(flat.keys())]
        rows.append(prefixo + resto)
    return rows

# ==============================
# EXECUÇÃO PRINCIPAL
# ==============================
def run(url_base: str, cookies: str, cliente: str):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    ws = open_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, WORKSHEET_TITLE)
    ws.clear()

    session = build_session(cookies, url_base)
    endpoint = url_base.rstrip("/") + ENDPOINT_PATH

    # Gera cabeçalho dinâmico
    header_prefix = [
        "cliente",
        "descricao_conceito",
        "modulo",
        "codigo_conceito",
        "codigo_informacao_adicional",
        "descricao_informacao_adicional",
    ]

    exemplo = None
    for c in CONCEITOS:
        exemplo = fetch_informacoes(session, endpoint, IDENTIFICADOR_DA_ABA, c)
        if exemplo:
            break

    if exemplo:
        all_keys = sorted(exemplo[0].keys())
    else:
        all_keys = [
            "Id", "TipoEntidade", "Codigo", "Descricao", "Status",
            "Observacao", "Obrigatorio", "DescricaoDoTipo", "Mascara",
            "FormaDeApresentacaoSelUnica", "FormaDeApresentacaoSelMultipla",
            "ValorPadrao", "Ordem"
        ]

    header = header_prefix + all_keys
    ws.update("A1", [header])

    total = 0
    buffer = []

    for codigo_conceito, descricao_conceito in CONCEITOS.items():
        logging.info(f"Consultando {descricao_conceito} ({codigo_conceito})")
        data = fetch_informacoes(session, endpoint, IDENTIFICADOR_DA_ABA, codigo_conceito)
        rows = parse_rows(data, cliente, codigo_conceito, descricao_conceito)
        buffer.extend(rows)
        total += len(rows)

        if len(buffer) >= 1000:
            ws.append_rows(buffer, value_input_option="RAW")
            buffer.clear()

        time.sleep(REQUEST_PAUSE)

    if buffer:
        ws.append_rows(buffer, value_input_option="RAW")

    logging.info(f"✅ Concluído! {total} linhas gravadas na aba '{WORKSHEET_TITLE}'.")
