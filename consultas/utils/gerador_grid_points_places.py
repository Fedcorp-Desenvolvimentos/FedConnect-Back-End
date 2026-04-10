# consultas/utils/gerador_grid_points_places.py
from itertools import product
import math
import logging
logger = logging.getLogger(__name__)

def generate_grid_points(bounds, grid_spacing_meters=500):
    """
    Gera grade de pontos otimizada
    
    Para bairros com grid_spacing=500m, deve gerar ~9-16 pontos no máximo
    """
    if not bounds or 'northeast' not in bounds or 'southwest' not in bounds:
        raise ValueError("Bounds inválidos para geração de grade")
    
    # Calcula tamanho da área
    lat_span = abs(bounds['northeast']['lat'] - bounds['southwest']['lat'])
    lng_span = abs(bounds['northeast']['lng'] - bounds['southwest']['lng'])
    
    # Converte para km aproximado
    lat_km = lat_span * 111
    avg_lat = (bounds['northeast']['lat'] + bounds['southwest']['lat']) / 2
    lng_km = lng_span * 111 * math.cos(math.radians(avg_lat))
    
    logger.info(f"Área de busca: {lat_km:.2f}km x {lng_km:.2f}km")
    
    # Ajusta grid_spacing se necessário
    grid_spacing_km = grid_spacing_meters / 1000.0
    
    # Calcula número de pontos
    lat_points_count = max(1, int(lat_km / grid_spacing_km) + 1)
    lng_points_count = max(1, int(lng_km / grid_spacing_km) + 1)
    
    # Limita o número máximo de pontos
    MAX_POINTS = 36  # 6x6 no máximo
    if lat_points_count * lng_points_count > MAX_POINTS:
        # Reduz proporcionalmente
        ratio = math.sqrt(MAX_POINTS / (lat_points_count * lng_points_count))
        lat_points_count = max(1, int(lat_points_count * ratio))
        lng_points_count = max(1, int(lng_points_count * ratio))
        logger.warning(f"Pontos excederam limite. Reduzido para {lat_points_count}x{lng_points_count}={lat_points_count * lng_points_count}")
    
    # Gera pontos igualmente espaçados
    lat_step = lat_span / (lat_points_count - 1) if lat_points_count > 1 else 0
    lng_step = lng_span / (lng_points_count - 1) if lng_points_count > 1 else 0
    
    lat_points = [bounds['southwest']['lat'] + i * lat_step for i in range(lat_points_count)]
    lng_points = [bounds['southwest']['lng'] + i * lng_step for i in range(lng_points_count)]
    
    grid = list(product(lat_points, lng_points))
    
    logger.info(f"Grade gerada: {lat_points_count} latitudes x {lng_points_count} longitudes = {len(grid)} pontos")
    
    return grid


def estimate_grid_cost(bounds, grid_spacing_meters=500):
    """
    Estima o custo em requisições da API Places para uma grade
    """
    grid_points = generate_grid_points(bounds, grid_spacing_meters)
    num_points = len(grid_points)
    
    # Cada ponto pode gerar até 2 páginas (40 resultados) com nosso limite
    max_requests = num_points * 2
    estimated_cost = max_requests * 0.032  # $0.032 por requisição Nearby Search
    
    return {
        'total_grid_points': num_points,
        'max_api_requests': max_requests,
        'estimated_cost_usd': round(estimated_cost, 2),
        'grid_spacing_meters': grid_spacing_meters
    }

