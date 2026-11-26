# App Score Finanças (`app_scorefinancas`)

Serviço externo (sem interface visual) responsável por calcular o **Score de Saúde Financeira** de um utilizador da **Finances4You**.

## Fluxo de Interoperabilidade
1. Recebe `POST /api/v1/avaliar` da **Finances4You** (com `id_utilizador`, `data_inicio`, `data_fim` e header `X-API-Key`).
2. Faz `GET http://127.0.0.1:5000/api/v1/transacoes` (com `X-API-Key`) para recolher as carteiras e transações em **JSON**.
3. Calcula o **Score Global (0–100, Rating A–E)** nos 4 pilares (*Taxa de Poupança*, *Equilíbrio Essencial vs. Lazer*, *Liquidez das Carteiras* e *Controlo de Pendentes*) e gera recomendações automáticas.
4. Constrói e valida o documento **XML** contra `schemas/avaliacao_financeira.xsd` e devolve-o à **Finances4You**, que o valida novamente e o transforma em **HTML** via **XSLT**.

## Como executar (porta 5001)
```powershell
flask --app app run --port 5001 --debug
```
