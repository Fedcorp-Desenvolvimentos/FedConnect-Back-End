# condomed/validators.py
import re


def normalizar_cpf(valor):
    """Deixa apenas os dígitos do CPF."""
    return re.sub(r"\D", "", valor or "")


def cpf_valido(cpf):
    """Valida os dígitos verificadores do CPF (RF-CIP-003)."""
    cpf = normalizar_cpf(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11
        digito = 0 if digito == 10 else digito
        if digito != int(cpf[tamanho]):
            return False
    return True
