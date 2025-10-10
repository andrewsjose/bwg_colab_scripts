# -*- coding: utf-8 -*-
"""
Lê dados da aba "informacoes-adicionais" e cadastra um por um
no endpoint /InformacaoAdicional/Salvar da LG.
Grava o resultado (mensagem) em uma nova coluna chamada 'resultado'.

Pode ser chamada com:
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
ENDPOINT_PATH = "/Gente/Produtos/FolhaDePagamento/InformacaoAdicional/Salvar"
IDENTIFICADOR_DA_ABA = "1357cb4d-919b-4f17-ac76-800cd42ecc71"

SPREADSHEET_ID = "1ijwb6D59j_3KQQaUnMifN88L79qvtuIEJ2Cq-yZv82E"
WORKSHEET_TITLE = "informacoes-adicionais"
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


def get_rows_as_text(ws):
    """Lê todas as linhas preservando o formato textual"""
    data = ws.get_all_values()
    headers = data[0]
    return [dict(zip(headers, row)) for row in data[1:]]


def garantir_coluna_resultado(ws):
    """Cria a coluna 'resultado' caso não exista e retorna o índice"""
    cabecalho = ws.row_values(1)
    if COLUNA_RESULTADO in cabecalho:
        return cabecalho.index(COLUNA_RESULTADO) + 1
    nova_coluna = len(cabecalho) + 1
    ws.add_cols(1)
    ws.update_cell(1, nova_coluna, COLUNA_RESULTADO)
    return nova_coluna


def enviar_registro(session: requests.Session, url: str, form_data: dict):
    """Envia o POST e retorna mensagem"""
    try:
        resp = session.post(url, data=form_data, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return f"Erro HTTP {resp.status_code}"
        try:
            result = resp.json()
            return result.get("mensagem", "(sem mensagem)")
        except json.JSONDecodeError:
            return "Resposta inválida"
    except Exception as e:
        return str(e)


def safe_str(value):
    """Mantém formato textual (para máscara, etc.)"""
    if value is None:
        return ""
    value = str(value).replace(".", ",")
    if "," in value:
        partes = value.split(",")
        if len(partes) == 2 and len(partes[1]) == 1:
            value = partes[0] + "," + partes[1] + "0"
    return value.strip()


def montar_payload(row: dict, identificador_da_aba: str):
    tipo = int(row.get("Tipo", 0) or 0)

    base = {
        "chaveParaExcluirItem": "Codigo",
        "chaveParaConsultarItem": "Codigo",
        "Status": "ATIVO",
        "Cadastro_InserindoNovoRegistro": "True",
        "cboModulo": row.get("modulo", ""),
        "cboConceito": row.get("codigo_conceito", ""),
        "Ordem": row.get("Ordem", ""),
        "DtoGrupoDeInformacoesAdicionais.Codigo": row.get("codigo_informacao_adicional", ""),
        "Codigo": row.get("Codigo", ""),
        "_TxtCodigo": row.get("Codigo", ""),
        "Descricao": row.get("Descricao", ""),
        "Observacao": row.get("Observacao", ""),
        "Tipo": tipo,
        "Obrigatorio": str(row.get("Obrigatorio", "False")).capitalize(),
        "InserirValorPadraoEmRegistrosAtivos": str(row.get("InserirValorPadraoEmRegistrosAtivos", "false")).lower(),
        "APartirDe": row.get("APartirDe", ""),
        "identificadorDaAba": identificador_da_aba,
        "X-Requested-With": "XMLHttpRequest"
    }

    # Campos adicionais por tipo
    if tipo == 0:
        base.update({
            "Comprimento": row.get("Comprimento", ""),
            "NumeroDeLinhasVisiveis": row.get("NumeroDeLinhasVisiveis", ""),
            "Mascara": safe_str(row.get("Mascara", "")),
            "ValorPadrao": row.get("ValorPadrao", "")
        })
    elif tipo == 1:
        base.update({"ValorPadrao": row.get("ValorPadrao", "")})
    elif tipo == 2:
        base.update({
            "Mascara": safe_str(row.get("Mascara", "")),
            "PreenchimentoExclusivo": str(row.get("PreenchimentoExclusivo", "False")).capitalize(),
            "ValorPadrao": row.get("ValorPadrao", "")
        })
    elif tipo == 3:
        base.update({
            "Comprimento": row.get("Comprimento", ""),
            "QuantidadeCasasDecimais": row.get("QuantidadeCasasDecimais", "")
        })
    elif tipo == 4:
        base.update({"MascaraDeData.Codigo": row.get("MascaraDeData", "")})
    elif tipo == 5:
        base.update({
            "OpcoesSelecaoUnica": row.get("Opcoes", "[]"),
            "OpcoesSelecaoUnicaRemovidos": "[]",
            "FormaDeApresentacaoSelUnica": row.get("FormaDeApresentacaoSelUnica", 0),
            "NumeroDeLinhasVisiveis": row.get("NumeroDeLinhasVisiveis", 1)
        })

    return base


# ==============================
# EXECUÇÃO PRINCIPAL
# ==============================
def run(url_base: str, cookies: str, cliente: str):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.info(f"🔹 Iniciando envio de informações adicionais para {cliente}")

    endpoint = url_base.rstrip("/") + ENDPOINT_PATH
    session = build_session(cookies, url_base)
    ws = open_sheet(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, WORKSHEET_TITLE)
    col_resultado = garantir_coluna_resultado(ws)

    rows = get_rows_as_text(ws)
    logging.info(f"📄 {len(rows)} registros lidos da planilha.")

    for idx, row in enumerate(rows, start=2):
        payload = montar_payload(row, IDENTIFICADOR_DA_ABA)
        mensagem = enviar_registro(session, endpoint, payload)
        logging.info(f"[{idx - 1}] Código={row.get('Codigo')} Tipo={row.get('Tipo')} → {mensagem}")

        try:
            ws.update_cell(idx, col_resultado, mensagem)
        except Exception as e:
            logging.warning(f"⚠️ Falha ao atualizar linha {idx}: {e}")

        time.sleep(REQUEST_PAUSE)

    logging.info("✅ Processo concluído com sucesso!")
