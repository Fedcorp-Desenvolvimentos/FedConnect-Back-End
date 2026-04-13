# src/utils/buscar_cidades.py
import logging
import unicodedata
import httpx
from typing import Dict, Optional
import re
from difflib import get_close_matches

# Cache em memória
_CACHE = {}
_CACHE_INICIALIZADO = False
_CODIGOS_IBGE_CACHE = {}

logger = logging.getLogger(__name__)


def _remover_acentos(texto: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

def _normalizar_nome_cidade(nome: str) -> dict:
    if not nome:
        return {"original": "", "normalizado": "", "sem_espaco": ""}

    nome = nome.upper().strip()

    # remove acentos
    nome = _remover_acentos(nome)

    # remove caracteres especiais
    nome = re.sub(r'[^A-Z\s]', '', nome)

    # remove múltiplos espaços
    nome = re.sub(r'\s+', ' ', nome).strip()

    # remove sufixos comuns
    sufixos_remover = [
        'MUNICIPIO DE ', 'CIDADE DE ', ' MUNICIPIO', ' MUNICIPIO',
        ' MUN', ' MUN.', ' PREFEITURA DE '
    ]
    for s in sufixos_remover:
        nome = nome.replace(s, '')

    nome = nome.strip()

    return {
        "original": nome,
        "normalizado": nome,
        "sem_espaco": nome.replace(" ", "")
    }

def _normalizar_uf(uf: str) -> str:
    """Normaliza a UF"""
    if not uf:
        return ""
    
    uf = uf.upper().strip()
    
    # Mapeamentos comuns de erros
    mapeamento_uf = {
        'RIO DE JANEIRO': 'RJ',
        'SAO PAULO': 'SP',
        'MINAS GERAIS': 'MG',
        'PERNAMBUCO': 'PE',
        'RIO GRANDE DO NORTE': 'RN',
        'R J': 'RJ',
        'S P': 'SP',
        'M G': 'MG',
        'P E': 'PE',
        'R N': 'RN'
    }
    
    return mapeamento_uf.get(uf, uf)

async def _carregar_cidades_ibge():
    """Carrega cidades da API IBGE com índice por código"""
    global _CACHE, _CACHE_INICIALIZADO, _CODIGOS_IBGE_CACHE
    
    if _CACHE_INICIALIZADO:
        return
    
    logger.info("🔄 Carregando cidades do IBGE...")
    
    estados = [("33", "RJ")]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for cod_ibge, sigla in estados:
            try:
                url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{cod_ibge}/municipios"
                response = await client.get(url)
                
                if response.status_code == 200:
                    cidades = response.json()
                    for cidade in cidades:
                        nome = cidade['nome'].upper().strip()
                        codigo_ibge = str(cidade["id"])
                        
                        # Chave primária: nome_normalizado + UF
                        nome_norm = _normalizar_nome_cidade(nome)
                        chave = f"{nome_norm['normalizado']}_{sigla}"
                        
                        _CACHE[chave] = {
                            "codigo": codigo_ibge,
                            "descricao": cidade["nome"],
                            "estado": sigla,
                            "nome_normalizado": nome_norm
                        }
                        
                        # Indexa pelo código IBGE também
                        _CODIGOS_IBGE_CACHE[codigo_ibge] = _CACHE[chave]
                    
                    logger.info(f"✅ {len(cidades)} cidades de {sigla} carregadas")
                    
            except Exception as e:
                logger.error(f"⚠️ Erro ao carregar {sigla}: {e}")
    
    if _CACHE:
        _CACHE_INICIALIZADO = True
        logger.info(f"📊 Total em cache: {len(_CACHE)} cidades, {len(_CODIGOS_IBGE_CACHE)} códigos IBGE")
    else:
        logger.error("❌ IBGE indisponível - cache NÃO carregado")
    logger.info(f"📊 Total em cache: {len(_CACHE)} cidades, {len(_CODIGOS_IBGE_CACHE)} códigos IBGE")
 
async def _consultar_cep_completo(cep: str) -> Optional[Dict]:
    """Consulta serviços de CEP para obter dados completos com código IBGE"""
    cep_limpo = ''.join(filter(str.isdigit, cep))
    if len(cep_limpo) != 8:
        return None
    
    dados_cep = None
    
    # Tenta OpenCEP primeiro (tem código IBGE)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"https://opencep.com/v1/{cep_limpo}")
            if response.status_code == 200:
                dados = response.json()
                if not dados.get("erro"):
                    ibge = dados.get("ibge", "")
                    if ibge:
                        dados_cep = {
                            "cidade": dados.get("localidade", "").upper().strip(),
                            "uf": dados.get("uf", "").upper().strip(),
                            "ibge": str(ibge),
                            "origem": "OpenCEP"
                        }
                        logger.info(f"✅ OpenCEP retornou: {dados_cep}")
    except Exception as e:
        logger.debug(f"OpenCEP falhou para CEP {cep_limpo}: {e}")
    
    # Se OpenCEP não retornou código IBGE, tenta ViaCEP
    if not dados_cep or not dados_cep.get("ibge"):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"https://viacep.com.br/ws/{cep_limpo}/json/")
                if response.status_code == 200:
                    dados = response.json()
                    if not dados.get("erro"):
                        ibge = dados.get("ibge", "")
                        dados_cep = {
                            "cidade": dados.get("localidade", "").upper().strip(),
                            "uf": dados.get("uf", "").upper().strip(),
                            "ibge": str(ibge) if ibge else "",
                            "origem": "ViaCEP"
                        }
                        logger.info(f"✅ ViaCEP retornou: {dados_cep}")
        except Exception as e:
            logger.debug(f"ViaCEP falhou para CEP {cep_limpo}: {e}")
    
    return dados_cep

def _buscar_no_cache(cidade_nome: str, uf: str) -> Optional[Dict]:
    """Busca cidade no cache local"""
    cidade_norm = _normalizar_nome_cidade(cidade_nome)
    uf_norm = _normalizar_uf(uf)
    
    # Tenta busca direta
    chave = f"{cidade_norm['normalizado']}_{uf_norm}"
    if chave in _CACHE:
        return _CACHE[chave]
    
    # Se não encontrou, tenta busca parcial no nome
    for chave_cache, cidade_info in _CACHE.items():
        cidade_input_norm = _normalizar_nome_cidade(cidade_nome)
        cidade_cache_norm = _normalizar_nome_cidade(cidade_info["descricao"])

        if (
            cidade_input_norm["normalizado"] == cidade_cache_norm["normalizado"]
            or cidade_input_norm["sem_espaco"] == cidade_cache_norm["sem_espaco"]
        ):
            logging.info(f"Dados inteiros >>> {cidade_info}")
            return cidade_info
    
    return None

def _buscar_por_codigo_ibge(codigo_ibge: str) -> Optional[Dict]:
    """Busca cidade pelo código IBGE"""
    return _CODIGOS_IBGE_CACHE.get(codigo_ibge)

async def buscar_cidade(nome_cidade: str, uf: str = "", cep: str = "") -> Dict:
    """
    Busca cidade com validação robusta de múltiplas fontes
    
    Ordem de prioridade:
    1. Cidade + UF no cache IBGE
    2. CEP → código IBGE → cache IBGE
    3. CEP → cidade/UF → cache IBGE
    4. Fallbacks com validação cruzada
    """
    
    # 1. Carrega cache IBGE se necessário
    if not _CACHE_INICIALIZADO:
        await _carregar_cidades_ibge()
    
    # Normaliza entradas
    cidade_input = nome_cidade or ""
    uf_input = uf or ""
    cep_input = cep or ""
    
    # logger.info(f"🔍 Buscando: Cidade='{cidade_input}', UF='{uf_input}', CEP='{cep_input}'")
    
    # ETAPA 1: Tentativa com dados de entrada (cidade + UF)
    if cidade_input and uf_input:
        cidade_info = _buscar_no_cache(cidade_input, uf_input)
        if cidade_info:
            # logger.info(f"✅ Encontrado pelo nome/UF: {cidade_info['descricao']}/{cidade_info['estado']}")
            return cidade_info
        
    dados_cep = None
    
    # ETAPA 2: Usar CEP como fonte confiável
    if cep_input:
        dados_cep = await _consultar_cep_completo(cep_input)
        
        if dados_cep:
            # 2A: Tem código IBGE → busca direta no cache
            codigo_ibge = dados_cep.get("ibge", "")
            if codigo_ibge:
                cidade_info = _buscar_por_codigo_ibge(codigo_ibge)
                if cidade_info:
                    logger.info(f"✅ Encontrado pelo CEP (via código IBGE {codigo_ibge}): {cidade_info['descricao']}/{cidade_info['estado']}")
                    return cidade_info
            
            # 2B: Tem cidade/UF → busca no cache
            cidade_cep = dados_cep.get("cidade", "")
            uf_cep = dados_cep.get("uf", "")
            
            if cidade_cep and uf_cep:
                cidade_info = _buscar_no_cache(cidade_cep, uf_cep)
                if cidade_info:
                    logger.info(f"✅ Encontrado pelo CEP (via cidade/UF): {cidade_info['descricao']}/{cidade_info['estado']}")
                    return cidade_info
                
                # 2C: Se encontrou pelo CEP mas não no cache, pode ser cidade de outro estado
                logger.warning(f"⚠️ CEP {cep_input} retornou {cidade_cep}/{uf_cep} mas não está no cache IBGE")
                
                return {
                    "codigo": codigo_ibge or "",
                    "descricao": cidade_cep,
                    "estado": uf_cep,
                    "nome_normalizado": _normalizar_nome_cidade(cidade_cep)
                }
    
    # ETAPA 3: Validação cruzada - se temos dados conflitantes
    if cidade_input and uf_input and cep_input and dados_cep:
        cidade_cep = dados_cep.get("cidade", "")
        uf_cep = dados_cep.get("uf", "")
        
        # Se CEP retornou dados diferentes dos inputados
        if cidade_cep and uf_cep:
            cidade_norm_input = _normalizar_nome_cidade(cidade_input)
            cidade_norm_cep = _normalizar_nome_cidade(cidade_cep)
            uf_norm_input = _normalizar_uf(uf_input)
            uf_norm_cep = _normalizar_uf(uf_cep)
            
            if (cidade_norm_input != cidade_norm_cep) or (uf_norm_input != uf_norm_cep):
                logger.warning(f"⚠️ Conflito detectado: Input={cidade_input}/{uf_input}, CEP={cidade_cep}/{uf_cep}")
                
                # Priorizar dados do CEP (mais confiável)
                cidade_info = _buscar_no_cache(cidade_cep, uf_cep)
                if cidade_info:
                    logger.info(f"✅ Usando dados do CEP (conflito resolvido): {cidade_info['descricao']}/{cidade_info['estado']}")
                    return cidade_info
    
    # ETAPA 4: Fallbacks menos confiáveis
    if cidade_input:
        # Tenta buscar só pela cidade (qualquer UF)
        cidade_norm = _normalizar_nome_cidade(cidade_input)
        for chave_cache, cidade_info in _CACHE.items():
            if cidade_norm in chave_cache:
                logger.warning(f"⚠️ Fallback: encontrado {cidade_info['descricao']}/{cidade_info['estado']} (sem validação de UF)")
                return cidade_info
        
        # Tenta buscar nomes similares
        for chave_cache, cidade_info in _CACHE.items():
            cidade_cache_norm = cidade_info['nome_normalizado']
            # Verifica se os nomes são similares (ex: "SAO PAULO" vs "S PAULO")
            if (cidade_norm in cidade_cache_norm or 
                cidade_cache_norm in cidade_norm or
                cidade_norm.replace(" ", "") == cidade_cache_norm.replace(" ", "")):
                logger.warning(f"⚠️ Fallback por nome similar: {cidade_input} → {cidade_info['descricao']}/{cidade_info['estado']}")
                return cidade_info
    
    # ETAPA 5: Cidade genérica para erro
    logger.error(f"❌ Cidade não encontrada: Cidade='{cidade_input}', UF='{uf_input}', CEP='{cep_input}'")
    
    # Retorna cidade genérica do estado se soubermos o estado
    if uf_input:
        uf_norm = _normalizar_uf(uf_input)
        cidades_estado = [c for c in _CACHE.values() if c["estado"] == uf_norm]
        if cidades_estado:
            # Retorna a capital ou primeira cidade do estado
            for cidade in cidades_estado:
                if "RIO DE JANEIRO" in cidade["descricao"].upper() and uf_norm == "RJ":
                    return cidade
                elif "SAO PAULO" in cidade["descricao"].upper() and uf_norm == "SP":
                    return cidade
            
            logger.warning(f"⚠️ Retornando cidade genérica do estado {uf_norm}")
            return cidades_estado[0]
    
    # Último fallback: erro
    raise ValueError(f"Cidade '{nome_cidade}' não encontrada após todas as tentativas")

async def buscar_cidades_autocomplete(termo: str, uf: str = "RJ", limite: int = 20) -> list:
    """
    Busca cidades para autocomplete com matching fuzzy
    """
    # Garantir cache carregado
    if not _CACHE_INICIALIZADO:
        await _carregar_cidades_ibge()
    
    termo_norm = _normalizar_nome_cidade(termo)
    termo_lower = termo_norm["normalizado"].lower()
    
    resultados = []
    
    # Busca no cache
    for chave, cidade_info in _CACHE.items():
        # Filtrar por UF
        if cidade_info["estado"] != uf:
            continue
        
        nome_cidade = cidade_info["descricao"].upper()
        nome_norm = cidade_info["nome_normalizado"]["normalizado"]
        
        # Critérios de matching (prioridade)
        score = 0
        
        # 1. Match exato (maior prioridade)
        if termo_lower == nome_norm.lower():
            score = 100
        # 2. Começa com o termo
        elif nome_norm.lower().startswith(termo_lower):
            score = 80
        # 3. Termo está contido no nome
        elif termo_lower in nome_norm.lower():
            score = 60
        # 4. Similaridade fuzzy (último recurso)
        else:
            similaridade = get_close_matches(
                termo_lower, 
                [nome_norm.lower()], 
                n=1, 
                cutoff=0.7
            )
            if similaridade:
                score = 40
        
        if score > 0:
            resultados.append({
                "codigo": cidade_info["codigo"],
                "descricao": cidade_info["descricao"],
                "estado": cidade_info["estado"],
                "score": score,
                "nome_normalizado": nome_norm
            })
    
    # Ordenar por score (maior primeiro) e limitar
    resultados.sort(key=lambda x: x["score"], reverse=True)
    
    # Opcional: Adicionar "Todas as cidades" como primeira opção se termo vazio
    if not termo and len(resultados) > 0:
        return resultados[:limite]
    
    return resultados[:limite]