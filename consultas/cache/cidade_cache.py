# consultas/services/cidade_cache.py
import json
import logging
from pathlib import Path
from typing import List, Dict
from difflib import get_close_matches

logger = logging.getLogger(__name__)

# Cache em arquivo
_CACHE_FILE = Path(__file__).parent / "cidades_rj_cache.json"
_CIDADES_CACHE = None

def _carregar_ou_criar_cache() -> List[Dict]:
    """Carrega cidades do arquivo cache ou cria se não existir"""
    global _CIDADES_CACHE
    
    if _CIDADES_CACHE is not None:
        return _CIDADES_CACHE
    
    # Tenta carregar do arquivo
    if _CACHE_FILE.exists():
        try:
            with open(_CACHE_FILE, 'r', encoding='utf-8') as f:
                _CIDADES_CACHE = json.load(f)
                logger.info(f"✅ Cache carregado do arquivo: {len(_CIDADES_CACHE)} cidades")
                return _CIDADES_CACHE
        except Exception as e:
            logger.warning(f"⚠️ Erro ao ler cache: {e}")
    
    # Se não existe, carrega do IBGE (apenas uma vez na vida)
    logger.info("🔄 Cache não encontrado, carregando do IBGE...")
    _CIDADES_CACHE = _carregar_do_ibge()
    
    # Salva em arquivo para sempre
    try:
        with open(_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_CIDADES_CACHE, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Cache salvo em: {_CACHE_FILE}")
    except Exception as e:
        logger.error(f"❌ Erro ao salvar cache: {e}")
    
    return _CIDADES_CACHE

def _carregar_do_ibge() -> List[Dict]:
    """Carrega cidades do IBGE (operação pesada, feita apenas uma vez)"""
    import asyncio
    from consultas.services.buscar_cidades import _carregar_cidades_ibge, _CACHE
    
    # Executa o carregamento assíncrono
    asyncio.run(_carregar_cidades_ibge())
    
    # Converte para lista serializável
    cidades = []
    for chave, cidade in _CACHE.items():
        cidades.append({
            "codigo": cidade["codigo"],
            "descricao": cidade["descricao"],
            "estado": cidade["estado"],
            "nome_normalizado": cidade["nome_normalizado"]["normalizado"]
        })
    
    logger.info(f"📊 {len(cidades)} cidades carregadas do IBGE")
    return cidades

def buscar_cidades_autocomplete_sync(termo: str, uf: str = "RJ", limite: int = 20) -> List[Dict]:
    """
    Busca cidades para autocomplete - VERSÃO SÍNCRONA E SUPER RÁPIDA
    Não depende de banco de dados, apenas do arquivo cache
    """
    # Carrega cache (já em memória após primeira chamada)
    todas_cidades = _carregar_ou_criar_cache()
    
    # Filtra por UF
    cidades_filtradas = [c for c in todas_cidades if c["estado"] == uf]
    
    # Se não tem termo, retorna primeiras
    if not termo or len(termo) < 2:
        return cidades_filtradas[:limite]
    
    termo_lower = termo.lower().strip()
    resultados = []
    
    for cidade in cidades_filtradas:
        nome_norm = cidade["nome_normalizado"].lower()
        score = 0
        
        if termo_lower == nome_norm:
            score = 100
        elif nome_norm.startswith(termo_lower):
            score = 80
        elif termo_lower in nome_norm:
            score = 60
        elif get_close_matches(termo_lower, [nome_norm], n=1, cutoff=0.7):
            score = 40
        
        if score > 0:
            resultados.append({
                "codigo": cidade["codigo"],
                "descricao": cidade["descricao"],
                "estado": cidade["estado"],
                "score": score
            })
    
    # Ordena por relevância e limita
    resultados.sort(key=lambda x: x["score"], reverse=True)
    return resultados[:limite]