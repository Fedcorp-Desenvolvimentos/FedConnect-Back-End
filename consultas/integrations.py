import requests
import json
import os
from django.conf import settings


class ConsultaCEP:
    @staticmethod
    def consultar(cep):
        if not cep or not cep.isdigit() or len(cep) != 8:
            raise ValueError("CEP inválido. Deve conter 8 dígitos numéricos.")

        url = settings.CEP_URL + cep
        response = requests.get(url, timeout=30)
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
        
        
        
        url = "http://"+settings.ALT_CEP_URL+"/"+estado+"/"+cidade+"/"+logradouro+"/json"
        print(url)

        try:
            response = requests.get(url, timeout=30)
            
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
            response = requests.post(url, json=payload, headers=headers, timeout=30) # Adicionado timeout
            response.raise_for_status()
            return response.json()
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
            response = requests.post(url, json=payload, headers=headers, timeout=30) # Adicionado timeout
            response.raise_for_status()
            data = response.json()

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
            response = requests.post(url, json=payload, headers=headers, timeout=30) # Adicionado timeout
            response.raise_for_status() # Levanta um HTTPError para erros 4xx/5xx
            return response.json() # Retorna o JSON completo da resposta da BigDataCorp
        except requests.exceptions.HTTPError as e:
            # Captura erros HTTP específicos da API externa
            error_detail = e.response.json() if e.response.content else e.response.text
            raise ValueError(f"Erro na API da BigDataCorp (CPF alternativas): {e.response.status_code} - {error_detail}")
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Erro de conexão ao consultar CPF por chaves alternativas na BigDataCorp: {e}")
        except ValueError as e:
            raise ValueError(f"Erro ao processar resposta da BigDataCorp (CPF alternativas): {e}")


class ConsultaCNPJ:
    @staticmethod
    def consultar(cnpj):
        """
        Realiza uma consulta de CNPJ padrão utilizando a URL configurada em settings.CNPJ_URL.
        """
        if not cnpj:
            raise ValueError("CNPJ não pode ser vazio para consulta padrão.")

        url = settings.CNPJ_URL + cnpj
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status() # Lança um erro para status de resposta HTTP ruins (4xx ou 5xx)
            return response.json()
        except requests.exceptions.RequestException as e:
            status_code_info = f"Status: {e.response.status_code}" if e.response else "Sem status"
            error_text = e.response.text if e.response else str(e)
            print(f"Erro de comunicação com a API de consulta padrão de CNPJ ({status_code_info}): {error_text}")
            raise requests.exceptions.RequestException(
                f"Erro de comunicação com a API de consulta padrão de CNPJ ({status_code_info}): {error_text}"
            )
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON da API de consulta padrão de CNPJ: {e}. Resposta recebida: {response.text if 'response' in locals() else 'N/A'}")
            raise ValueError(f"Resposta inválida da API de consulta padrão de CNPJ: Não foi possível decodificar JSON. Detalhes: {e}")
        except Exception as e:
            print(f"Erro inesperado na consulta padrão de CNPJ: {e}")
            raise Exception(f"Erro interno ao processar consulta padrão de CNPJ: {e}")


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
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            print("Resposta bruta da BigDataCorp:", response.text)
            
            data = response.json()

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
        except json.JSONDecodeError as e:
            print(f"Erro ao decodificar JSON da BigDataCorp: {e}. Resposta recebida: {response.text if 'response' in locals() else 'N/A'}")
            raise ValueError(f"Resposta inválida da API externa: Não foi possível decodificar JSON. Detalhes: {e}")
        except ValueError as e:
            print(f"Erro de validação interna da resposta da BigDataCorp: {e}")
            raise e
        except Exception as e:
            print(f"Erro inesperado na consulta BigDataCorp: {e}")
            raise Exception(f"Erro interno ao processar consulta BigDataCorp: {e}")
