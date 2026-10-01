import logging
import requests
import json
import os
from django.conf import settings

logger = logging.getLogger(__name__)


# `timeout=30` num `requests` é 30 s para CONECTAR **mais** 30 s para ler: um
# destino que engole os pacotes, em vez de recusar a conexão, segura a
# requisição por até 60 s. Esse é justamente o limite do balanceador da
# DigitalOcean, que então devolve 504 — erro genérico, sem mensagem e sem log
# útil. Com a tupla, o pior caso são 20 s e o operador recebe um 503 explicado.
TEMPO_LIMITE = (5, 15)  # (conectar, ler), em segundos


class RecusaBigDataCorp(Exception):
    """A BigDataCorp recusou a consulta, mas respondeu com HTTP 200.

    Ela sinaliza falha no corpo, em `Status`, e não no código HTTP: token
    inválido, saldo esgotado ou origem bloqueada chegam como 200. Quem só
    olhava `raise_for_status()` tratava a recusa como sucesso — o resultado
    era gravado no histórico e a tela ficava vazia, sem erro nenhum.
    """


def verificar_recusa_bigdatacorp(dados):
    """Devolve `dados` ou levanta `RecusaBigDataCorp` com o que a base disse.

    `Status` é um dicionário de grupo (`login`, `api`, `basic_data`, ...) para
    uma lista de ocorrências `{Code, Message}`. Só código **negativo** é
    recusa: 0 é sucesso e os positivos são avisos, como "nada encontrado",
    que precisam continuar chegando à tela como consulta vazia.

    Um grupo que traz o 0 junto com um negativo entregou os dados: o negativo
    é aviso. O dataset `addresses` responde `OK` + "-205 DEPRECATED DATASET"
    (visto em 01/10/2026) e não pode derrubar a consulta.
    """
    status = (dados or {}).get("Status")
    if not isinstance(status, dict):
        return dados

    recusas = []
    for grupo, ocorrencias in status.items():
        if not isinstance(ocorrencias, list):
            continue
        if any(isinstance(o, dict) and o.get("Code") == 0 for o in ocorrencias):
            continue
        for ocorrencia in ocorrencias:
            if not isinstance(ocorrencia, dict):
                continue
            codigo = ocorrencia.get("Code")
            if isinstance(codigo, int) and codigo < 0:
                mensagem = ocorrencia.get("Message") or "sem mensagem"
                recusas.append(f"{grupo}: {mensagem} (código {codigo})")

    if recusas:
        raise RecusaBigDataCorp(
            "A base de consulta recusou a requisição — " + "; ".join(recusas)
        )
    return dados


class ConsultaCEP:
    @staticmethod
    def consultar(cep):
        if not cep or not cep.isdigit() or len(cep) != 8:
            raise ValueError("CEP inválido. Deve conter 8 dígitos numéricos.")

        url = settings.CEP_URL + cep
        response = requests.get(url, timeout=TEMPO_LIMITE)
        response.raise_for_status()
        data = response.json()

        if "erro" in data:
            raise ValueError("CEP não encontrado.")

        return data

    @staticmethod
    def consultar_por_rua_e_cidade(params):
        """
        Consulta CEP utilizando uma URL de API ViaCEP já pré-formatada.
        :param params: Dicionário contendo a 'url_completa_viacep'.
        """
        estado = params["estado"].replace(" ","%20")
        cidade = params["cidade"].replace(" ","%20")
        logradouro = params["logradouro"].replace(" ","%20")
        
        
        
        url = settings.ALT_CEP_URL+"/"+estado+"/"+cidade+"/"+logradouro+"/json"
        print(url)

        try:
            response = requests.get(url, timeout=TEMPO_LIMITE)
            
            print(f"DEBUG: Resposta bruta da ViaCEP (status {response.status_code}): {response.text}")

            response.raise_for_status() # Lança HTTPError para status 4xx/5xx
            
            data = response.json()

            if isinstance(data, list) and data: # ViaCEP retorna lista de dicionários
                return {"resultados_viacep": data}
            elif isinstance(data, dict) and data.get('erro'):
                # O ViaCEP retorna {'erro': true} se não encontrar
                raise ValueError(f"Nenhum CEP encontrado para o endereço fornecido na URL: {url}.")
            else:
                # Caso a resposta não seja nem lista nem erro (algo inesperado)
                raise ValueError(f"Resposta inesperada da ViaCEP para a URL {url}: {json.dumps(data, ensure_ascii=False)}")

        except requests.exceptions.HTTPError as e:
            error_content = ""
            try:
                error_content = e.response.json() if e.response.content else e.response.text
            except json.JSONDecodeError:
                error_content = e.response.text # Fallback se o conteúdo do erro não for JSON

            raise ValueError(f"Erro na API ViaCEP (Status {e.response.status_code}): {error_content}")
        
        except json.JSONDecodeError as e:
            raise ValueError(f"Erro ao decodificar JSON da ViaCEP. Conteúdo da resposta inválida: '{response.text}'. Detalhes: {e}")
        
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(
                f"Erro de comunicação ao consultar CEP por endereço na ViaCEP: {e}"
            )
        except ValueError as e:
            raise e # Re-lança os ValueErrors da sua própria lógica
        except Exception as e:
            raise Exception(f"Erro inesperado na consulta de CEP por endereço: {e}")




class ConsultaCPF:
    @staticmethod
    def consultar(cpf):
        # Esta é a sua função existente para CPF individual
        url = settings.CPF_URL

        access_token = os.environ.get("BIGDATA_ACCESS_TOKEN")
        token_id = os.environ.get("BIGDATA_TOKEN_ID")

        if not access_token or not token_id:
            raise ValueError(
                "As credenciais da BigDataCorp (BIGDATA_ACCESS_TOKEN e BIGDATA_TOKEN_ID) não estão configuradas nas variáveis de ambiente."
            )

        payload = {"q": f"doc{{{cpf}}}", "Datasets": "basic_data", "Limit": 1}
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "AccessToken": access_token,
            "TokenId": token_id,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TEMPO_LIMITE)
            response.raise_for_status()
            return verificar_recusa_bigdatacorp(response.json())
        except RecusaBigDataCorp:
            raise
        except requests.exceptions.RequestException as e:
            # Captura erros de requisição (conexão, timeout, etc.)
            raise requests.exceptions.RequestException(
                f"Erro ao consultar CPF na BigDataCorp: {e}"
            )
        except ValueError as e:
            # Captura erros ao parsear JSON
            raise ValueError(f"Erro ao processar resposta da BigDataCorp: {e}")

    @staticmethod
    def consultar_por_nome_e_data_nascimento(nome_completo, data_nascimento_str):
        # Esta função (e a correspondente view e serializer) serão removidas,
        # mas a deixei aqui para referência por enquanto.
        """
        Consulta CPF utilizando nome completo e data de nascimento através da BigDataCorp.
        data_nascimento_str deve estar no formato 'YYYY-MM-DD'.
        """
        url = settings.CPF_URL 

        access_token = os.environ.get("BIGDATA_ACCESS_TOKEN")
        token_id = os.environ.get("BIGDATA_TOKEN_ID")

        if not access_token or not token_id:
            raise ValueError(
                "As credenciais da BigDataCorp (BIGDATA_ACCESS_TOKEN e BIGDATA_TOKEN_ID) não estão configuradas nas variáveis de ambiente."
            )

        # Adapte o payload para a consulta por nome e data de nascimento na BigDataCorp
        payload = {
            "q": f"name{{{nome_completo}}} birthdate{{{data_nascimento_str}}}",
            "Datasets": "basic_data",
            "Limit": 1,
            "Mode": "fuzzy"
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "AccessToken": access_token,
            "TokenId": token_id,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TEMPO_LIMITE)
            response.raise_for_status()
            data = verificar_recusa_bigdatacorp(response.json())

            if data and data.get('data') and len(data['data']) > 0:
                return data['data'][0]
            else:
                raise ValueError(f"CPF não encontrado para o nome '{nome_completo}' e data de nascimento '{data_nascimento_str}'.")

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(
                f"Erro ao consultar CPF por nome/data na BigDataCorp: {e}"
            )
        except ValueError as e:
            raise ValueError(f"Erro ao processar resposta da BigDataCorp: {e}")

    @staticmethod
    def consultar_cpf_alternativa(params_json: dict):
        """
        Consulta CPF utilizando chaves alternativas (nome, data de nascimento, nome da mãe/pai)
        através da API da BigDataCorp.

        :param params_json: Dicionário já parseado do JSON do frontend, contendo
                            'Datasets', 'q' (com name{}, birthdate{}, etc.), e 'Limit'.
        """
        url = settings.CPF_URL # A BigDataCorp usa a mesma URL para diferentes consultas via payload

        access_token = os.environ.get("BIGDATA_ACCESS_TOKEN")
        token_id = os.environ.get("BIGDATA_TOKEN_ID")

        if not access_token or not token_id:
            raise ValueError(
                "As credenciais da BigDataCorp (BIGDATA_ACCESS_TOKEN e BIGDATA_TOKEN_ID) não estão configuradas nas variáveis de ambiente."
            )

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "AccessToken": access_token,
            "TokenId": token_id,
        }

        payload = params_json 
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TEMPO_LIMITE)
            response.raise_for_status() # Levanta um HTTPError para erros 4xx/5xx
            # Retorna o JSON completo da resposta, depois de conferir se ela não é uma recusa.
            return verificar_recusa_bigdatacorp(response.json())
        except RecusaBigDataCorp:
            raise
        except requests.exceptions.HTTPError as e:
            # Captura erros HTTP específicos da API externa
            error_detail = e.response.json() if e.response.content else e.response.text
            raise ValueError(f"Erro na API da BigDataCorp (CPF alternativas): {e.response.status_code} - {error_detail}")
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Erro de conexão ao consultar CPF por chaves alternativas na BigDataCorp: {e}")
        except ValueError as e:
            raise ValueError(f"Erro ao processar resposta da BigDataCorp (CPF alternativas): {e}")


def _texto(valor):
    """Texto sem espaços sobrando, ou None — a BigDataCorp usa " " para vazio."""
    limpo = " ".join(str(valor or "").split())
    return limpo or None


def _data(valor):
    """"1966-08-01T00:00:00Z" (BigDataCorp) → "1966-08-01" (formato da BrasilAPI)."""
    texto = _texto(valor)
    return texto[:10] if texto else None


def _inteiro(valor):
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def bigdatacorp_para_brasilapi(dados, cnpj_consultado):
    """Converte a resposta da BigDataCorp (`basic_data` + `addresses`) no formato da BrasilAPI.

    O frontend e o histórico só conhecem o formato da BrasilAPI (snake_case,
    endereço solto na raiz), então o fallback precisa devolver o mesmo
    contrato. O que a BigDataCorp não tem nesses datasets (telefones, e-mail,
    QSA) vai vazio. `fonte` diz de onde o dado veio.

    Devolve None quando não há empresa no resultado.
    """
    resultado = (dados or {}).get("Result") or []
    primeiro = resultado[0] if resultado and isinstance(resultado[0], dict) else {}
    basico = primeiro.get("BasicData") or {}
    if not _texto(basico.get("OfficialName")):
        return None

    # O endereço da Receita vem como "OFFICIAL REGISTRATION"; os demais foram
    # achados em outras fontes. Sem ele, fica o de maior prioridade.
    enderecos = [e for e in (primeiro.get("Addresses") or []) if isinstance(e, dict)]
    endereco = next(
        (e for e in enderecos if str(e.get("Type") or "").upper() == "OFFICIAL REGISTRATION"),
        None,
    ) or min(enderecos, key=lambda e: e.get("Priority") or 99, default={})

    atividades = [a for a in (basico.get("Activities") or []) if isinstance(a, dict)]
    principal = next((a for a in atividades if a.get("IsMain")), {})
    natureza = basico.get("LegalNature") or {}
    adicionais = basico.get("AdditionalOutputData") or {}
    regimes = basico.get("TaxRegimes") or {}
    matriz = basico.get("IsHeadquarter")

    try:
        capital_social = float(adicionais.get("CapitalRS"))
    except (TypeError, ValueError):
        capital_social = None

    return {
        "cnpj": "".join(filter(str.isdigit, str(basico.get("TaxIdNumber") or ""))) or cnpj_consultado,
        "razao_social": _texto(basico.get("OfficialName")),
        "nome_fantasia": _texto(basico.get("TradeName")),
        "descricao_situacao_cadastral": _texto(basico.get("TaxIdStatus")),
        "data_situacao_cadastral": _data(basico.get("TaxIdStatusDate")),
        "descricao_motivo_situacao_cadastral": _texto(basico.get("TaxIdStatusReason")),
        "data_inicio_atividade": _data(basico.get("FoundedDate")),
        "cnae_fiscal": _inteiro(principal.get("Code")),
        "cnae_fiscal_descricao": _texto(principal.get("Activity")),
        "cnaes_secundarios": [
            {"codigo": _inteiro(a.get("Code")), "descricao": _texto(a.get("Activity"))}
            for a in atividades
            if not a.get("IsMain")
        ],
        "codigo_natureza_juridica": _inteiro(natureza.get("Code")),
        "natureza_juridica": _texto(natureza.get("Activity")),
        "porte": _texto(basico.get("CompanyType_ReceitaFederal")),
        "capital_social": capital_social,
        "identificador_matriz_filial": None if matriz is None else (1 if matriz else 2),
        "descricao_identificador_matriz_filial": None if matriz is None else ("MATRIZ" if matriz else "FILIAL"),
        "opcao_pelo_simples": regimes.get("Simples"),
        "descricao_tipo_de_logradouro": _texto(endereco.get("Typology")),
        "logradouro": _texto(endereco.get("AddressMain")),
        "numero": _texto(endereco.get("Number")),
        "complemento": _texto(endereco.get("Complement")),
        "bairro": _texto(endereco.get("Neighborhood")),
        "municipio": _texto(endereco.get("City")),
        "uf": _texto(endereco.get("State")) or _texto(basico.get("HeadquarterState")),
        "cep": "".join(filter(str.isdigit, str(endereco.get("ZipCode") or ""))) or None,
        "ddd_telefone_1": None,
        "ddd_telefone_2": None,
        "email": None,
        "qsa": [],
        "fonte": "bigdatacorp",
    }


class ConsultaCNPJ:
    @staticmethod
    def consultar(cnpj):
        """
        Consulta o CNPJ na BrasilAPI (settings.CNPJ_URL) e, se ela falhar, na BigDataCorp.

        A BrasilAPI é gratuita mas instável (504 em produção, 01/10/2026). Fora
        do ar, por timeout, 5xx, 429, 404 ou JSON inválido, a consulta segue
        para a BigDataCorp, convertida para o mesmo formato. Só o 400 (CNPJ
        inválido) não cai no fallback: a BigDataCorp diria o mesmo, cobrando.

        Pior caso: dois `TEMPO_LIMITE` em série (40 s), abaixo dos 60 s do
        balanceador da DigitalOcean.
        """
        if not cnpj:
            raise ValueError("CNPJ não pode ser vazio para consulta padrão.")

        try:
            return ConsultaCNPJ.consultar_brasilapi(cnpj)
        except ValueError:
            raise
        except Exception as e:
            falha_brasilapi = str(e)
            logger.warning(f"BrasilAPI falhou para o CNPJ {cnpj}, consultando a BigDataCorp: {falha_brasilapi}")

        try:
            return ConsultaCNPJ.consultar_bigdatacorp(cnpj)
        except RecusaBigDataCorp as e:
            raise RecusaBigDataCorp(f"BrasilAPI indisponível ({falha_brasilapi}) e {e}")
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(
                f"BrasilAPI e BigDataCorp indisponíveis — BrasilAPI: {falha_brasilapi} | BigDataCorp: {e}"
            )

    @staticmethod
    def consultar_brasilapi(cnpj):
        """Consulta na BrasilAPI. ValueError só para CNPJ inválido (HTTP 400)."""
        url = settings.CNPJ_URL + cnpj
        response = requests.get(url, timeout=TEMPO_LIMITE)
        if response.status_code == 400:
            raise ValueError(f"CNPJ inválido: {response.text}")
        if response.status_code != 200:
            raise requests.exceptions.RequestException(f"HTTP {response.status_code}: {response.text[:200]}")
        try:
            return response.json()
        except ValueError as e:  # JSONDecodeError herda de ValueError, mas aqui é falha da base
            raise requests.exceptions.RequestException(f"resposta não é JSON: {e}")

    @staticmethod
    def consultar_bigdatacorp(cnpj):
        """Consulta o CNPJ na BigDataCorp (`doc{cnpj}`) e devolve no formato da BrasilAPI."""
        access_token = os.environ.get("BIGDATA_ACCESS_TOKEN")
        token_id = os.environ.get("BIGDATA_TOKEN_ID")
        if not access_token or not token_id:
            raise requests.exceptions.RequestException(
                "credenciais da BigDataCorp (BIGDATA_ACCESS_TOKEN e BIGDATA_TOKEN_ID) não configuradas"
            )

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "AccessToken": access_token,
            "TokenId": token_id,
        }
        payload = {"q": f"doc{{{cnpj}}}", "Datasets": "basic_data,addresses", "Limit": 1}

        response = requests.post(settings.ALT_CNPJ_URL, json=payload, headers=headers, timeout=TEMPO_LIMITE)
        if response.status_code != 200:
            raise requests.exceptions.RequestException(f"HTTP {response.status_code}: {response.text[:200]}")
        try:
            dados = response.json()
        except ValueError as e:
            raise requests.exceptions.RequestException(f"resposta não é JSON: {e}")

        convertido = bigdatacorp_para_brasilapi(verificar_recusa_bigdatacorp(dados), cnpj)
        if convertido is None:
            raise ValueError(f"CNPJ {cnpj} não encontrado nas bases de consulta.")
        return convertido


    @staticmethod
    def consultar_por_razao_social_bigdatacorp(big_data_corp_payload_dict):
        """
        Realiza uma consulta de CNPJ por razão social via BigDataCorp,
        extrai o CNPJ do resultado e, em seguida, realiza uma consulta padrão de CNPJ.
        O retorno final é o da consulta padrão.
        """
        url = settings.ALT_CNPJ_URL

        if not isinstance(big_data_corp_payload_dict, dict):
            raise ValueError("Payload de BigDataCorp inválido: Não é um dicionário.")
        if 'q' not in big_data_corp_payload_dict or not big_data_corp_payload_dict['q'].strip():
            raise ValueError("Payload de BigDataCorp inválido: Campo 'q' ausente ou vazio.")
        if 'Datasets' not in big_data_corp_payload_dict:
            raise ValueError("Payload de BigDataCorp inválido: Campo 'Datasets' ausente.")
        
        payload = big_data_corp_payload_dict 

        print("Payload final enviado para BigDataCorp:", json.dumps(payload, indent=2)) # Para depuração

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "AccessToken": os.environ.get("BIGDATA_ACCESS_TOKEN"),
            "TokenId": os.environ.get("BIGDATA_TOKEN_ID"),
        }

        access_token = os.environ.get("BIGDATA_ACCESS_TOKEN")
        token_id = os.environ.get("BIGDATA_TOKEN_ID")

        if not access_token or not token_id:
            raise ValueError(
                "As credenciais da BigDataCorp (BIGDATA_ACCESS_TOKEN e BIGDATA_TOKEN_ID) não estão configuradas nas variáveis de ambiente."
            )

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=TEMPO_LIMITE)
            response.raise_for_status()
            
            # print("Resposta bruta da BigDataCorp:", response.text)
            
            data = verificar_recusa_bigdatacorp(response.json())

            if data and data.get('Result') and isinstance(data['Result'], list) and len(data['Result']) > 0:
                print("Resultados encontrados da BigDataCorp.")
                # --- Extrai o CNPJ do primeiro resultado da BigDataCorp ---
                cnpj_encontrado = data['Result'][0].get('BasicData', {}).get('TaxIdNumber')
                
                if cnpj_encontrado:
                    print(f"CNPJ encontrado pela BigDataCorp: {cnpj_encontrado}. Realizando consulta padrão...")
                    # --- Chama a consulta padrão com o CNPJ encontrado ---
                    return ConsultaCNPJ.consultar(cnpj_encontrado)
                else:
                    print(f"CNPJ não encontrado na resposta 'BasicData' da BigDataCorp. Resposta completa: {json.dumps(data, indent=2)}")
                    raise ValueError(f"Nenhum CNPJ válido encontrado nos resultados da BigDataCorp para a razão social fornecida: {payload.get('q', 'N/A')}")
            else:
                print(f"Nenhum resultado na chave 'Result' ou 'Result' está vazia. Resposta completa: {json.dumps(data, indent=2)}")
                raise ValueError(f"Nenhum CNPJ encontrado para os parâmetros fornecidos: {payload.get('q', 'N/A')}")

        except requests.exceptions.RequestException as e:
            status_code_info = f"Status: {e.response.status_code}" if e.response else "Sem status"
            error_text = e.response.text if e.response else str(e)
            print(f"Erro de conexão/API com BigDataCorp ({status_code_info}): {error_text}")
            raise requests.exceptions.RequestException(
                f"Erro de comunicação com a API externa (BigDataCorp - {status_code_info}): {error_text}"
            )
        except RecusaBigDataCorp:
            raise
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON da BigDataCorp: {e}. Resposta recebida: {response.text if 'response' in locals() else 'N/A'}")
            raise ValueError(f"Resposta inválida da API externa: Não foi possível decodificar JSON. Detalhes: {e}")
        except ValueError as e:
            print(f"Erro de validação interna da resposta da BigDataCorp: {e}")
            raise e
        except Exception as e:
            print(f"Erro inesperado na consulta BigDataCorp: {e}")
            raise Exception(f"Erro interno ao processar consulta BigDataCorp: {e}")
