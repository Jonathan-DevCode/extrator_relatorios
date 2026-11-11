# -*- coding: utf-8 -*-
"""Baixa o PDF de concessões de férias/licença-prêmio do SGP."""

import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from login import criar_sessao_autenticada
from sgp_jsf import extrair_formulario


BASE_URL = "https://sgp.saovicente.sp.gov.br"
CONSULTA_URL = f"{BASE_URL}/concessao-ferias-licenca-premio/listar/"
FORM = "concessaoFeriasLicenca:FormularioPesquisa"
CAMPO_TIPO = f"{FORM}:j_idt434"
CAMPO_OPERADOR = f"{FORM}:j_idt437"
CAMPO_MATRICULA = f"{FORM}:j_idt441:j_idt442"


def localizar_botao_pesquisa(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["button", "input"]):
        identificador = tag.get("id", "") or tag.get("name", "")
        onclick = tag.get("onclick", "")
        texto = tag.get_text(" ", strip=True).lower() if tag.name == "button" else ""
        if (
            "pesquisar" in identificador.lower()
            or "pesquisar" in onclick.lower()
            or texto in {"pesquisar", "consultar", "buscar"}
        ):
            return tag.get("name") or tag.get("id")

    return f"{FORM}:j_idt87"


def baixar_pdf(sessao, matricula):
    pagina = sessao.get(CONSULTA_URL, timeout=30)
    pagina.raise_for_status()
    if "/faces/login.xhtml" in pagina.url:
        raise RuntimeError("A sessão foi redirecionada para o login.")

    _, _, dados = extrair_formulario(pagina.text, form_id=FORM)
    botao = localizar_botao_pesquisa(pagina.text)
    dados.update({
        "javax.faces.source": botao,
        botao: botao,
        FORM: FORM,
        CAMPO_TIPO: "174511206928360",
        CAMPO_OPERADOR: "IGUAL",
        CAMPO_MATRICULA: matricula,
    })

    resposta = sessao.post(
        CONSULTA_URL,
        data=dados,
        headers={
            "Accept": "application/pdf, application/octet-stream, */*",
            "Origin": BASE_URL,
            "Referer": CONSULTA_URL,
        },
        timeout=60,
    )
    print("Consulta SGP:", resposta.status_code, resposta.headers.get("Content-Type", ""))
    resposta.raise_for_status()

    if "/faces/login.xhtml" in resposta.url:
        raise RuntimeError("A sessão foi redirecionada para o login.")
    if not resposta.content.startswith(b"%PDF-"):
        raise RuntimeError(
            "A consulta não retornou um PDF. "
            f"Content-Type recebido: {resposta.headers.get('Content-Type', 'não informado')}."
        )

    pasta = Path("resultado_concessao_ferias")
    pasta.mkdir(exist_ok=True)
    matricula_arquivo = re.sub(r"[^A-Za-z0-9_-]", "_", matricula)
    data_hora = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta / f"concessao_ferias_matricula_{matricula_arquivo}_{data_hora}.pdf"
    caminho.write_bytes(resposta.content)
    return caminho


def main():
    sessao = None
    try:
        sessao = criar_sessao_autenticada()
        matricula = input("Matrícula do servidor: ").strip()
        if not matricula:
            raise RuntimeError("A matrícula é obrigatória.")

        print("Consultando concessões no SGP...")
        arquivo = baixar_pdf(sessao, matricula)
        print("PDF salvo em:", arquivo.resolve())
    except (requests.RequestException, RuntimeError) as erro:
        print("Falha:", erro)
        raise SystemExit(1) from erro
    finally:
        if sessao is not None:
            sessao.close()


if __name__ == "__main__":
    main()
