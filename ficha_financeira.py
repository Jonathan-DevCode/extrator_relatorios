import re
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from login import criar_sessao_autenticada
from sgp_jsf import atualizar_viewstate, extrair_formulario, ler_updates_jsf

BASE_URL = "https://sgp.saovicente.sp.gov.br"
URL = f"{BASE_URL}/relatorio/ficha-financeira/novo/"
COMPONENTE_SERVIDOR = "Formulario:tab-view-geral:contratoFP"
BOTAO_GERAR = "Formulario:tab-view-geral:j_idt81:printer"

MESES = {
    "1": "JANEIRO", "2": "FEVEREIRO", "3": "MARCO",
    "4": "ABRIL", "5": "MAIO", "6": "JUNHO",
    "7": "JULHO", "8": "AGOSTO", "9": "SETEMBRO",
    "10": "OUTUBRO", "11": "NOVEMBRO", "12": "DEZEMBRO",
}


def ler_mes_ano(rotulo):
    while True:
        valor = input(f"{rotulo} (MM/AAAA): ").strip()
        m = re.fullmatch(r"(\d{1,2})/(\d{4})", valor)
        if m and int(m.group(1)) in range(1, 13):
            return MESES[str(int(m.group(1)))], m.group(2)
        print("Formato inválido. Exemplo: 09/2026.")


def buscar_servidor(sessao, dados_base, matricula):
    """Pesquisa a matrícula usando o evento PrimeFaces confirmado na captura."""
    prefixo = COMPONENTE_SERVIDOR
    dados = dict(dados_base)
    dados.update({
        "javax.faces.partial.ajax": "true",
        "javax.faces.source": prefixo,
        "javax.faces.partial.execute": prefixo,
        "javax.faces.partial.render": prefixo,
        prefixo: prefixo,
        f"{prefixo}_query": matricula,
        "Formulario": "Formulario",
        f"{prefixo}_input": matricula,
        f"{prefixo}_hinput": matricula,
        "Formulario:tab-view-geral_activeIndex": "0",
    })

    sessao.headers.update({
        "Origin": BASE_URL,
        "Referer": URL,
        "Accept": "application/xml, text/xml, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Faces-Request": "partial/ajax",
        "X-Requested-With": "XMLHttpRequest",
    })

    resposta = sessao.post(URL, data=dados, timeout=30)
    print("Pesquisa de matrícula:", resposta.status_code)
    resposta.raise_for_status()

    updates = ler_updates_jsf(resposta.text)
    bloco = updates.get(COMPONENTE_SERVIDOR, "")
    if not bloco:
        # Não imprimir a resposta inteira: pode conter informações funcionais.
        raise RuntimeError(
            "A pesquisa não retornou opções do autocomplete. "
            "Confira a matrícula e se o ViewState foi atualizado."
        )

    soup = BeautifulSoup(bloco, "html.parser")
    opcoes = []
    for item in soup.select("li.ui-autocomplete-item"):
        rotulo = item.get("data-item-label") or item.get_text(" ", strip=True)
        identificador = item.get("data-item-value")
        if rotulo and identificador:
            opcoes.append((rotulo.strip(), identificador.strip()))

    if not opcoes:
        raise RuntimeError("A resposta do autocomplete não continha opções válidas.")

    atualizar_viewstate(dados_base, updates)
    return opcoes


def localizar_url_pdf(texto):
    """Extrai a URL do PDF do formulário FormularioRelatorio retornado pelo JSF."""
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError:
        return None

    # A resposta JSF inclui o HTML do relatório em CDATA no update
    # FormularioRelatorio. O BeautifulSoup decodifica &amp; nos atributos HTML.
    for update in raiz.iter("update"):
        if update.attrib.get("id") != "FormularioRelatorio" or not update.text:
            continue
        html_relatorio = BeautifulSoup(update.text, "html.parser")
        objeto = html_relatorio.find("object", attrs={"type": "application/pdf"})
        if not objeto or not objeto.get("data"):
            continue

        candidato = urljoin(URL, objeto["data"])
        partes = urlparse(candidato)
        if (
            partes.scheme == "https"
            and partes.netloc == "sgp.saovicente.sp.gov.br"
            and partes.path == "/faces/javax.faces.resource/dynamiccontent.properties"
            and "pfdrid=" in partes.query
        ):
            # Remove o fragmento de visualização (#zoom=...), que não é enviado.
            return candidato.split("#", 1)[0]
    return None


def main():
    sessao = None
    try:
        # Mantém o comportamento solicitado: login primeiro, antes das operações.
        sessao = criar_sessao_autenticada()

        matricula = input("Matrícula do servidor: ").strip()
        if not matricula:
            raise RuntimeError("A matrícula é obrigatória.")

        mes_ini, ano_ini = ler_mes_ano("Mês inicial")
        mes_fim, ano_fim = ler_mes_ano("Mês final")

        chave_ini = int(ano_ini) * 12 + list(MESES.values()).index(mes_ini)
        chave_fim = int(ano_fim) * 12 + list(MESES.values()).index(mes_fim)
        if chave_fim < chave_ini:
            raise RuntimeError("O mês final não pode ser anterior ao mês inicial.")

        sessao.headers.update({"Origin": BASE_URL, "Referer": URL})

        pagina = sessao.get(URL, timeout=30)
        print("GET ficha:", pagina.status_code, pagina.url)
        pagina.raise_for_status()
        if "/faces/login.xhtml" in pagina.url:
            raise RuntimeError("A sessão foi redirecionada para o login.")

        _, _, dados = extrair_formulario(pagina.text)
        dados.update({
            "Formulario": "Formulario",
            "Formulario:tab-view-geral:mes-inicial": mes_ini,
            "Formulario:tab-view-geral:ano": ano_ini,
            "Formulario:tab-view-geral:mes-final": mes_fim,
            "Formulario:tab-view-geral:anoFinal": ano_fim,
            "Formulario:tab-view-geral:tipo-folha": "NORMAL",
            "Formulario:tab-view-geral_activeIndex": "0",
        })

        opcoes = buscar_servidor(sessao, dados, matricula)
        print("\nServidores encontrados:")
        for i, (rotulo, _) in enumerate(opcoes, start=1):
            print(f"{i}. {rotulo}")

        escolha = input("Selecione o servidor correto pelo número: ").strip()
        if not escolha.isdigit() or not (1 <= int(escolha) <= len(opcoes)):
            raise RuntimeError("Seleção inválida.")

        rotulo, id_servidor = opcoes[int(escolha) - 1]

        # A captura mostra que a geração ocorre em /relatorio/ficha-financeira/novo/
        # e usa estes nomes de campo e o botão printer.
        dados.update({
            "javax.faces.partial.ajax": "true",
            "javax.faces.source": BOTAO_GERAR,
            "javax.faces.partial.execute": "Formulario",
            "javax.faces.partial.render": "Formulario",
            BOTAO_GERAR: BOTAO_GERAR,
            "Formulario": "Formulario",
            "Formulario:tab-view-geral:mes-inicial": mes_ini,
            "Formulario:tab-view-geral:ano": ano_ini,
            "Formulario:tab-view-geral:mes-final": mes_fim,
            "Formulario:tab-view-geral:anoFinal": ano_fim,
            "Formulario:tab-view-geral:tipo-folha": "NORMAL",
            f"{COMPONENTE_SERVIDOR}_input": rotulo,
            f"{COMPONENTE_SERVIDOR}_hinput": id_servidor,
            "Formulario:tab-view-geral_activeIndex": "0",
        })

        sessao.headers.update({
            "Accept": "application/xml, text/xml, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Faces-Request": "partial/ajax",
            "X-Requested-With": "XMLHttpRequest",
        })

        resposta = sessao.post(URL, data=dados, timeout=60)
        print("\nPOST geração:", resposta.status_code)
        print("Content-Type:", resposta.headers.get("Content-Type"))
        resposta.raise_for_status()

        # O endpoint de geração pode devolver XML com o componente de conteúdo
        # dinâmico; a segunda requisição GET é a que entrega o PDF.
        url_pdf = localizar_url_pdf(resposta.text)
        if not url_pdf:
            Path("resposta_geracao_sgp.xml").write_text(
                resposta.text, encoding="utf-8"
            )
            raise RuntimeError(
                "A resposta não revelou a URL dinâmica do PDF. "
                "Salvei resposta_geracao_sgp.xml para diagnóstico local."
            )

        partes = urlparse(url_pdf)
        if partes.scheme != "https" or partes.netloc != "sgp.saovicente.sp.gov.br":
            raise RuntimeError("URL de PDF inesperada; download cancelado.")

        pdf = sessao.get(url_pdf, headers={"Referer": URL}, timeout=60)
        print("GET PDF:", pdf.status_code, "|", pdf.headers.get("Content-Type"))
        pdf.raise_for_status()

        if not pdf.content.startswith(b"%PDF"):
            Path("resposta_download_sgp.bin").write_bytes(pdf.content)
            raise RuntimeError(
                "A resposta não parece ser um PDF. "
                "Conteúdo salvo em resposta_download_sgp.bin."
            )

        nome = (
            f"ficha_financeira_{matricula}_"
            f"{ano_ini}{mes_ini}_{ano_fim}{mes_fim}.pdf"
        )
        Path(nome).write_bytes(pdf.content)
        print("PDF salvo em:", nome)

    except (requests.RequestException, RuntimeError) as erro:
        print("Falha:", erro)
    finally:
        if sessao is not None:
            sessao.close()


if __name__ == "__main__":
    main()
