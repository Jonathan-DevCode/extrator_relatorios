import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup


__all__ = ["extrair_formulario", "ler_updates_jsf", "atualizar_viewstate"]


def extrair_formulario(html_texto, form_id="Formulario"):
    soup = BeautifulSoup(html_texto, "html.parser")
    form = soup.find("form", id=form_id)
    if not form:
        raise RuntimeError(
            f"Formulário '{form_id}' não encontrado. "
            "Confira se a sessão está autenticada e se o endereço está correto."
        )

    dados = {}
    for campo in form.select("input[name], select[name], textarea[name]"):
        nome = campo.get("name")
        if not nome:
            continue

        if campo.name == "input":
            tipo = campo.get("type", "").lower()
            if tipo == "hidden":
                dados[nome] = campo.get("value", "")
            elif tipo in ("text", "search"):
                dados[nome] = campo.get("value", "")
        elif campo.name == "select":
            selecionado = campo.select_one("option[selected]")
            if selecionado is None:
                selecionado = campo.select_one("option")
            dados[nome] = selecionado.get("value", "") if selecionado else ""
        elif campo.name == "textarea":
            dados[nome] = campo.get_text()

    if not dados.get("javax.faces.ViewState"):
        raise RuntimeError("ViewState não encontrado no formulário.")
    return soup, form, dados


def ler_updates_jsf(texto):
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError:
        return {}
    updates = {}
    for elemento in raiz.iter():
        if elemento.tag.endswith("update"):
            updates[elemento.attrib.get("id", "")] = elemento.text or ""
    return updates


def atualizar_viewstate(dados, updates):
    novo_estado = updates.get("javax.faces.ViewState")
    if novo_estado:
        dados["javax.faces.ViewState"] = novo_estado
