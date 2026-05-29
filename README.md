# Mobilidade ETL com Containers

Projeto acadêmico em Python para processar dados de mobilidade urbana usando Docker, MySQL e paralelismo simples.

A solução simula um pipeline ETL inspirado no processamento de dados públicos de trânsito e transporte. O arquivo CSV bruto é lido, tratado, processado de forma sequencial e paralela, e os resultados são gravados em arquivos CSV e no banco MySQL.

## Objetivo

Organizar dados brutos de transporte público ou trânsito, removendo inconsistências e gerando estatísticas básicas para apoiar análises de mobilidade urbana.

## Arquitetura

```text
data/input/*.csv
       |
       v
Container Python
ETL sequencial e paralelo
       |
       v
data/output/*.csv
       |
       v
Container MySQL
dados tratados e estatísticas
```

## Tecnologias

- Python 3.12
- Pandas
- MySQL
- Docker
- Docker Compose

## Estrutura

```text
mobilidade-etl-containers/
├── app/
│   ├── config.py
│   ├── db.py
│   ├── etl.py
│   └── main.py
├── data/
│   ├── input/
│   │   └── viagens_exemplo.csv
│   └── output/
├── db/
│   └── init.sql
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

## Como Executar com Docker

```bash
docker compose up --build
```

O serviço `app` aguarda o MySQL iniciar, processa os dados e grava os resultados.

## Como Executar Localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main --input data/input/viagens_exemplo.csv
```

Para salvar no MySQL local, configure as variáveis de ambiente:

```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_NAME=mobilidade
export DB_USER=mobilidade_user
export DB_PASSWORD=mobilidade_pass
python -m app.main --input data/input/viagens_exemplo.csv
```

## Colunas Esperadas no CSV

O pipeline espera um CSV com as seguintes colunas:

- `linha`
- `data`
- `horario_previsto`
- `horario_realizado`
- `passageiros`
- `status`

## Estatísticas Geradas

- total de viagens por linha;
- total de passageiros por linha;
- média de atraso por linha;
- percentual de viagens atrasadas;
- comparação de tempo entre processamento sequencial e paralelo.

## Paralelismo

O processamento paralelo divide o DataFrame em blocos e processa cada bloco usando `ProcessPoolExecutor`.

Isso permite comparar:

- processamento sequencial: arquivo inteiro em uma única etapa;
- processamento paralelo: arquivo dividido em partes processadas simultaneamente.

## Próximas Evoluções

- integrar coleta real via API ou scraping do portal de Acesso à Informação de Palmas;
- adicionar interface web em Laravel ou outro frontend;
- incluir gráficos e filtros por linha, data e status;
- adicionar testes automatizados.
