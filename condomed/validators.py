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


def normalizar_cnpj(valor):
    """Deixa apenas os dígitos do CNPJ."""
    return re.sub(r"\D", "", valor or "")


def cnpj_valido(cnpj):
    """Valida os dígitos verificadores do CNPJ (certificado cita o condomínio com CNPJ)."""
    cnpj = normalizar_cnpj(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6] + pesos_1
    for tamanho, pesos in ((12, pesos_1), (13, pesos_2)):
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(tamanho))
        digito = 11 - (soma % 11)
        digito = 0 if digito >= 10 else digito
        if digito != int(cnpj[tamanho]):
            return False
    return True
