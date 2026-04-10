# consultas/services/google_places_grid.py
import requests
import time
import logging
from django.conf import settings
from consultas.utils.gerador_grid_points_places import generate_grid_points
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class GooglePlacesGridService:
    """Serviço para buscar estabelecimentos usando estratégia de grade"""
    
    BASE_URL = "https://places.googleapis.com/v1/places:searchNearby"
    
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.GOOGLE_MAPS_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.displayName,"
                "places.formattedAddress,"
                "places.nationalPhoneNumber,"
                "places.websiteUri,"
                "places.businessStatus,"
                "places.id,"
                "places.location"
            )
        }
    
    def search_all_businesses(self, bounds, business_types=None, keyword=None, 
                            radius=500, grid_spacing=500, max_results_per_point=60):
        """
        Busca todos os estabelecimentos em uma área usando grade
        """
        grid_points = generate_grid_points(bounds, grid_spacing)
        logger.info(f"Grade gerada com {len(grid_points)} pontos")
        
        # Se tiver muitos pontos, avisa e reduz
        if len(grid_points) > 25:
            logger.warning(f"Muitos pontos ({len(grid_points)}). Reduzindo para 25 máximo")
            # Pega apenas pontos estratégicos (pula alguns)
            step = max(1, len(grid_points) // 25)
            grid_points = grid_points[::step][:25]
            logger.info(f"Grade reduzida para {len(grid_points)} pontos")
        
        all_places = {}
        stats = {
            'total_grid_points': len(grid_points),
            'successful_queries': 0,
            'failed_queries': 0,
            'total_api_calls': 0,
            'duplicates_removed': 0
        }
        
        for idx, (lat, lng) in enumerate(grid_points, 1):
            logger.info(f"Processando ponto {idx}/{len(grid_points)}: ({lat:.6f}, {lng:.6f})")
            
            try:
                places = self._search_single_point_with_retry(
                    lat, lng, radius, business_types, keyword, max_results_per_point
                )
                
                stats['successful_queries'] += 1
                
                new_places = 0
                for place in places:
                    place_id = place.get('id')
                    if place_id and place_id not in all_places:
                        all_places[place_id] = place
                        new_places += 1
                    else:
                        stats['duplicates_removed'] += 1
                
                logger.info(f"Ponto {idx}: {len(places)} encontrados, {new_places} novos")
                
                # Delay menor entre pontos
                time.sleep(0.3)
                    
            except Exception as e:
                logger.error(f"Erro no ponto {idx}: {str(e)}")
                stats['failed_queries'] += 1
                continue
        
        stats['total_unique_places'] = len(all_places)
        
        logger.info(f"✅ Busca finalizada: {len(all_places)} lugares únicos em {stats['successful_queries']} consultas bem-sucedidas")
        
        return {
            'places': list(all_places.values()),
            'stats': stats
        }
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError))
    )
    def _search_single_point_with_retry(self, lat, lng, radius, business_types, keyword, max_results):
        """Versão com retry automático"""
        return self._search_single_point(lat, lng, radius, business_types, keyword, max_results)
    
    def _search_single_point(self, lat, lng, radius, business_types, keyword, max_results):
        """Busca em um único ponto com paginação"""
        all_places = []
        page_token = None
        pages_processed = 0
        MAX_PAGES = 2  # Limita a 2 páginas por ponto (40 resultados)
        
        payload = {
            "maxResultCount": 20,  # Máximo por página
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": lat,
                        "longitude": lng
                    },
                    "radius": float(radius)
                }
            }
        }
        
        if business_types:
            payload["includedTypes"] = business_types
        
        while len(all_places) < max_results and pages_processed < MAX_PAGES:
            if page_token:
                payload["pageToken"] = page_token
            
            try:
                # Timeout aumentado para 15 segundos
                response = requests.post(
                    self.BASE_URL, 
                    json=payload, 
                    headers=self.headers, 
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()
                
                places = data.get('places', [])
                
                operational_places = [
                    p for p in places 
                    if p.get('businessStatus') == 'OPERATIONAL'
                ]
                
                if keyword:
                    keyword_lower = keyword.lower()
                    operational_places = [
                        p for p in operational_places
                        if keyword_lower in p.get('displayName', {}).get('text', '').lower()
                    ]
                
                all_places.extend(operational_places)
                
                page_token = data.get('nextPageToken')
                if not page_token:
                    break
                
                pages_processed += 1
                
                if page_token:
                    time.sleep(1.5)  # Espera para o token ficar válido
                
            except requests.exceptions.Timeout as e:
                logger.warning(f"Timeout no ponto ({lat}, {lng}) - página {pages_processed + 1}")
                raise  # Re-levanta para o retry
            except Exception as e:
                logger.error(f"Erro na paginação: {str(e)}")
                break
        
        return all_places[:max_results]