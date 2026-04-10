# consultas/services/google_geocoding.py
import requests
import logging
import math
from django.conf import settings

logger = logging.getLogger(__name__)

class GoogleGeocodingService:
    BASE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    @classmethod
    def get_location_data(cls, uf, municipio, bairro=None):
        city_result = cls._geocode_city(municipio, uf)

        if not city_result:
            raise ValueError(f"Não foi possível geocodificar a cidade: {municipio}")

        logger.info(f"Cidade encontrada: {city_result['formatted_address']}")

        if bairro:
            bairro_result = cls._geocode_bairro_with_bias(
                bairro, municipio, city_result['lat'], city_result['lng']
            )

            if bairro_result:
                logger.info(f"Bairro validado dentro da cidade: {bairro}")
                result = bairro_result
                # Para BAIRRO, área MUITO menor (1km total)
                viewport = cls._build_viewport_realistic(
                    result['lat'], result['lng'], is_bairro=True
                )
            else:
                logger.warning(f"Bairro '{bairro}' não encontrado. Usando cidade.")
                result = city_result
                viewport = cls._build_viewport_realistic(
                    result['lat'], result['lng'], is_bairro=False
                )
        else:
            result = city_result
            viewport = cls._build_viewport_realistic(
                result['lat'], result['lng'], is_bairro=False
            )

        return {
            'lat': result['lat'],
            'lng': result['lng'],
            'viewport': viewport,
            'formatted_address': result['formatted_address'],
            'place_id': result['place_id']
        }

    @classmethod
    def _geocode_city(cls, municipio, uf):
        params = {
            'address': f"{municipio}, {uf}, Brasil",
            'key': settings.GOOGLE_MAPS_API_KEY,
            'components': f'country:BR|administrative_area:{uf}'
        }

        response = requests.get(cls.BASE_URL, params=params, timeout=10).json()

        if response.get('status') != 'OK':
            return None

        r = response['results'][0]

        return {
            'lat': r['geometry']['location']['lat'],
            'lng': r['geometry']['location']['lng'],
            'formatted_address': r['formatted_address'],
            'place_id': r['place_id']
        }

    @classmethod
    def _geocode_bairro_with_bias(cls, bairro, municipio, lat, lng):
        params = {
            'address': f"{bairro}, {municipio}",
            'key': settings.GOOGLE_MAPS_API_KEY,
            'components': f'country:BR|locality:{municipio}'
        }

        response = requests.get(cls.BASE_URL, params=params, timeout=10).json()

        if response.get('status') != 'OK':
            return None

        results = response.get('results', [])
        
        for r in results:
            if cls._is_in_city(r, municipio):
                return {
                    'lat': r['geometry']['location']['lat'],
                    'lng': r['geometry']['location']['lng'],
                    'formatted_address': r['formatted_address'],
                    'place_id': r['place_id']
                }

        return None

    @staticmethod
    def _is_in_city(result, municipio):
        components = result.get('address_components', [])

        for comp in components:
            if 'administrative_area_level_2' in comp['types']:
                found = comp['long_name']
                return found.lower() == municipio.lower()

        return False

    @staticmethod
    def _build_viewport_realistic(lat, lng, is_bairro=False):
        """
        Viewport REALISTA para evitar grids enormes
        """
        if is_bairro:
            # Bairro: apenas 800m de raio (área de 1.6km x 1.6km)
            delta_km = 0.8  # 800 metros
        else:
            # Cidade: 2km de raio (área de 4km x 4km) - ainda grande, mas melhor
            delta_km = 2.0

        lat_delta = delta_km / 111.0
        lng_delta = delta_km / (111.0 * math.cos(math.radians(lat)))

        return {
            'northeast': {
                'lat': lat + lat_delta,
                'lng': lng + lng_delta
            },
            'southwest': {
                'lat': lat - lat_delta,
                'lng': lng - lng_delta
            }
        }