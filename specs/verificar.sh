#!/usr/bin/env bash
# Verificação de integridade das specs (formato novo — CONVENCOES.md).
# Rode de qualquer lugar: bash specs/verificar.sh
# Saída: violações por regra. Código 1 se houver qualquer uma.
#
# Adaptação do verificador canônico do pacote SDD (DesenhoPortalNovo/verificar.sh)
# para specs de feature deste backend. Specs legadas (sem matriz.csv) saem como
# nota e não são verificadas — ver STATUS.md.

set -uo pipefail
cd "$(dirname "$0")"

FALHAS_FILE=$(mktemp)
trap 'rm -f "$FALHAS_FILE"' EXIT

Q=00-registro-de-questoes.md

reporta() {  # reporta <id> <descrição> ; consome stdin
  local id="$1" desc="$2" out
  out=$(cat)
  if [ -n "$out" ]; then
    echo "FALHA $id — $desc"
    echo "$out" | sed 's/^/    /'
    echo "$id" >> "$FALHAS_FILE"
  else
    echo "ok    $id — $desc"
  fi
}

campos() { awk -F';' -v c="$1" 'NR>1{n=split($c,a,"|");for(i=1;i<=n;i++) if(a[i]!="") print a[i]}' "$2" | sort -u; }

# Pastas de feature no formato novo = têm matriz.csv
NOVAS=$(find . -maxdepth 2 -name matriz.csv | xargs -r -n1 dirname | sort)
LEGADAS=$(find . -maxdepth 1 -type d ! -name '.' ! -name '_templates' ! -name 'adr' \
  | while read -r d; do [ -f "$d/matriz.csv" ] || echo "$d"; done)
[ -n "$LEGADAS" ] && echo "nota: specs legadas (não verificadas): $(echo "$LEGADAS" | tr '\n' ' ')"

echo "== Matriz de rastreabilidade =="

for d in $NOVAS; do
  M="$d/matriz.csv"

  n=$(head -1 "$M" | awk -F';' '{print NF}')
  awk -F';' -v n="$n" -v f="$M" 'NF!=n{print f":"NR" tem "NF" colunas, esperado "n}' "$M" \
    | reporta R0 "[$d] contagem de colunas uniforme na matriz"

  awk -F';' 'NR>1 && $2==""{print $1}' "$M" \
    | reporta R1 "[$d] todo requisito da matriz tem origem"

  comm -3 <(grep -ohE '^### (RF|RNF)-[A-Z]{3}-[0-9]{3}' "$d/requirements.md" | grep -oE '(RF|RNF)-[A-Z]{3}-[0-9]{3}' | sort -u) \
          <(awk -F';' 'NR>1{print $1}' "$M" | sort -u) \
    | reporta R2 "[$d] requirements.md e matriz declaram os mesmos requisitos"

  awk -F';' 'NR>1 && $6==""{print $1}' "$M" \
    | reporta R3 "[$d] todo requisito tem caso de teste"

  awk -F';' 'NR>1{print $1}' "$M" | sort | uniq -d \
    | reporta R8 "[$d] nenhum requisito duplicado na matriz"

  comm -23 <(campos 6 "$M") <(grep -rhoE 'CT-[A-Z]{3}-[0-9]{3}' "$d"/*.md | sort -u) \
    | reporta R9 "[$d] todo caso de teste da matriz existe nos documentos"

  if [ -f "$d/tasks.md" ]; then
    comm -23 <(campos 5 "$M") <(grep -ohE 'T-[A-Z]{3}-[0-9]+\.[0-9]+' "$d/tasks.md" | sort -u) \
      | reporta R10 "[$d] toda tarefa da matriz existe no tasks.md"
  fi

  grep -hE '\*\*Status:\*\*' "$d"/*.md \
    | grep -voE '(esboço|rascunho|em revisão|aprovado|descartado)' \
    | reporta R12 "[$d] status do cabeçalho pertence ao vocabulário"
done

echo "== Procedência =="

EXCL=(--exclude=CONVENCOES.md --exclude=README.md --exclude-dir=_templates)

grep -rnE '\[D\]' --include='*.md' "${EXCL[@]}" . | grep -vE '(ADR-[0-9]{4}|PA-[0-9]{3})' \
  | cut -c1-140 | reporta R4 "todo [D] cita um ADR (ou PA fechada)"

grep -rnE '\[P\]' --include='*.md' "${EXCL[@]}" . | grep -vE 'PA-[0-9]{3}' \
  | cut -c1-140 | reporta R5 "todo [P] cita uma questão"

comm -23 <(grep -rhoE 'PA-[0-9]{3}' --include='*.md' --include='*.csv' --exclude-dir=_templates . | sort -u) \
         <(grep -oE '^## PA-[0-9]{3}' "$Q" | grep -oE 'PA-[0-9]{3}' | sort -u) \
  | reporta R6 "toda questão citada existe no registro"

comm -23 <(grep -rhoE 'ADR-[0-9]{4}' --include='*.md' --include='*.csv' --exclude-dir=_templates . | sort -u) \
         <(ls adr/ 2>/dev/null | grep -oE '^[0-9]{4}' | sed 's/^/ADR-/' | sort -u) \
  | reporta R7 "todo ADR citado existe em specs/adr/"

echo "== Higiene =="

while IFS= read -r f; do
  d=$(dirname "$f")
  grep -oE '\]\(\.\.?[^)#]*\.(md|csv|yaml|yml|mmd|sh|py)\)' "$f" 2>/dev/null \
    | sed 's/^](//;s/)$//' | while read -r l; do
        [ -e "$d/$l" ] || echo "$f -> $l"
      done
done < <(find . -name '*.md' -not -path './_templates/*') | reporta R11 "nenhum link relativo quebrado"

find . -name '*.md' | while read -r f; do
  n=$(grep -c '^# ' "$f"); [ "$n" -le 1 ] || echo "$f tem $n títulos de primeiro nível"
done | reporta R13 "um único título de primeiro nível por arquivo"

grep -rnE '[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}' --include='*.md' --include='*.csv' . \
  | grep -vE '000\.000\.000-00|XXX\.XXX' | cut -c1-140 \
  | reporta R14 "nenhum CPF real nas specs"

grep -rniE '(client_secret|api_key|password|senha)[^=:]{0,10}[=:] *["'"'"'][A-Za-z0-9+/]{16,}' \
  --include='*.md' --include='*.csv' . | cut -c1-140 \
  | reporta R15 "nenhuma credencial literal nas specs"

echo
FALHAS=$(wc -l < "$FALHAS_FILE" | tr -d " ")
if [ "$FALHAS" -eq 0 ]; then
  echo "Sem violações."
else
  echo "$FALHAS regra(s) com violação: $(tr '\n' ' ' < "$FALHAS_FILE")"
  exit 1
fi
