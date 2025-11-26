# -*- coding: utf-8 -*-
import requests
from urllib.parse import urljoin

LOGIN_URL_TEMPLATE = "https://login.lg.com.br/login/gente/{cliente}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "keep-alive",
}

def executar_login(url_inicial, tema="PADRAO"):
    """
    Login completo no ambiente LG via requests, seguindo exatamente o fluxo real,
    incluindo SAAA, EscolhaDoPortal, home.aspx e Suite/Index.
    Retorna:
        {
            "cookies": "cookie=a; cookie2=b; ...",
            "url": "https://prd-ng2.lg.com.br/Gente/Produtos/Infraestrutura/InicioPorParametros/Index"
        }
    """

    sess = requests.Session()
    sess.headers.update(HEADERS)

    print("🌐 [1] GET login inicial:", url_inicial)
    r = sess.get(url_inicial, allow_redirects=True)

    # --- Procura o token do formulário
    token = None
    if "__RequestVerificationToken" in r.text:
        import re
        m = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', r.text)
        if m:
            token = m.group(1)

    # Carrega credenciais
    import json, os
    cred_path = "/content/scripts/login_cred.json"
    if not os.path.exists(cred_path):
        raise Exception("Arquivo login_cred.json não encontrado")

    cred = json.load(open(cred_path, "r"))
    usuario = cred["usuario"]
    senha = cred["senha"]

    payload = {
        "Login": usuario,
        "Senha": senha,
        "Tema": tema,
    }

    if token:
        payload["__RequestVerificationToken"] = token

    print("🔐 [2] POST credenciais…")
    r = sess.post(url_inicial, data=payload, allow_redirects=True)

    print("➡️ [3] Seguindo redirects…")
    url_atual = r.url

    for i in range(10):
        print("   - Redirect step", i, "→", url_atual)
        r = sess.get(url_atual, allow_redirects=True)
        if r.url == url_atual:
            break
        url_atual = r.url

    # --- Fluxo SAAA e Portal
    def try_get(path):
        full = path if path.startswith("http") else urljoin("https://prd-ng2.lg.com.br", path)
        print("📄 GET", full)
        return sess.get(full, allow_redirects=True)

    try_get("/gente/Produtos/SAAA/InicieLoginServicos.aspx")
    try_get("/gente/Produtos/SAAA/LoginServicos.aspx")
    try_get("/Gente/EscolhaDoPortal.aspx")
    try_get("/Gente/home.aspx")
    final = try_get("/Gente/Produtos/Infraestrutura/Suite/Index")

    # --- URL final
    final_url = final.url
    print("🏁 URL Final:", final_url)

    # --- Monta cookie string estilo navegador
    cookie_str = "; ".join([f"{k}={v}" for k, v in sess.cookies.get_dict().items()])

    print("\n🍪 Cookies coletados:")
    for k, v in sess.cookies.get_dict().items():
        print("  -", k)

    return {
        "cookies": cookie_str,
        "url": final_url
    }
