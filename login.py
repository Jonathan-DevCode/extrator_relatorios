import getpass
import requests
from urllib.parse import urlparse

BASE_URL = "https://sgp.saovicente.sp.gov.br"
LOGIN_PAGE = f"{BASE_URL}/faces/login.xhtml"
LOGIN_ENDPOINT = f"{BASE_URL}/j_spring_security_check"


def criar_sessao_autenticada(usuario=None, senha=None):
    """Autentica no SGP e devolve a mesma requests.Session para consultas."""
    if usuario is None:
        usuario = input("Usuário do SGP: ")
    if senha is None:
        senha = getpass.getpass("Senha do SGP: ")

    sessao = requests.Session()
    sessao.headers.update({
        "User-Agent": "Mozilla/5.0",
    })

    resposta_login = sessao.get(LOGIN_PAGE, timeout=30)
    resposta_login.raise_for_status()

    resposta = sessao.post(
        LOGIN_ENDPOINT,
        data={
            "j_username": usuario,
            "j_password": senha,
        },
        headers={
            "Origin": BASE_URL,
            "Referer": LOGIN_PAGE,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        allow_redirects=False,
        timeout=30,
    )

    print("Resposta do login:", resposta.status_code)
    destino = resposta.headers.get("Location", "")
    print("Redirecionamento:", destino or "(nenhum)")

    if resposta.status_code not in (301, 302, 303, 307, 308):
        sessao.close()
        raise RuntimeError(
            "O SGP não retornou o redirecionamento esperado após o login."
        )

    # O SGP pode informar http:// no Location. Não seguimos esse endereço:
    # testamos a página equivalente em HTTPS, preservando a sessão.
    destino_parseado = urlparse(destino)
    if destino_parseado.path == "/faces/login.xhtml":
        sessao.close()
        raise RuntimeError("O SGP redirecionou de volta para a tela de login.")

    pagina_home = sessao.get(f"{BASE_URL}/home", timeout=30, allow_redirects=False)
    print("Teste da página inicial por HTTPS:", pagina_home.status_code)

    if pagina_home.status_code in (301, 302, 303, 307, 308):
        prox = pagina_home.headers.get("Location", "")
        if "/faces/login.xhtml" in prox:
            sessao.close()
            raise RuntimeError("A sessão não foi autenticada; houve retorno ao login.")

    # A página inicial pode variar por configuração; a ficha financeira fará
    # uma segunda verificação de acesso e do formulário.
    return sessao


if __name__ == "__main__":
    try:
        sessao = criar_sessao_autenticada()
        print("Sessão criada. Cookies mantidos em memória; não os compartilhe.")
        sessao.close()
    except (requests.RequestException, RuntimeError) as erro:
        print("Falha na autenticação:", erro)
