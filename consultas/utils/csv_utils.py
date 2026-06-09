import csv
import io
import json
from typing import List, Dict, Any
from datetime import date, datetime
from decimal import Decimal

def convert_to_csv(data: List[Dict[str, Any]], delimiter: str = ';', encoding: str = 'utf-8') -> str:
    """
    Converte uma lista de dicionários para CSV
    
    Args:
        data: Lista de dicionários com os dados
        delimiter: Delimitador do CSV (padrão: ';')
        encoding: Encoding do arquivo (padrão: 'utf-8')
    
    Returns:
        String com o conteúdo CSV
    """
    if not data:
        return ""
    
    # Obtém todas as chaves únicas dos dicionários
    fieldnames = set()
    for row in data:
        fieldnames.update(row.keys())
    
    fieldnames = sorted(list(fieldnames))  # Ordena para consistência
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter, extrasaction='ignore')
    
    # Escreve cabeçalho
    writer.writeheader()
    
    # Escreve os dados
    for row in data:
        # Converte valores para string de forma segura
        processed_row = {}
        for key, value in row.items():
            processed_row[key] = _serialize_value(value)
        writer.writerow(processed_row)
    
    return output.getvalue()

def _serialize_value(value: Any) -> str:
    """Serializa valores para CSV"""
    if value is None:
        return ""
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return str(value).replace('.', ',')
    elif isinstance(value, (int, float)):
        return str(value).replace('.', ',')
    elif isinstance(value, bool):
        return "Sim" if value else "Não"
    elif isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    else:
        return str(value)