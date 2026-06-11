# Relatório técnico

## ROTA: processamento paralelo e análise containerizada de acidentes da PRF

**Disciplina:** Sistemas Paralelos e Distribuídos  
**Tema:** Tema 7 - Aplicação com Computação em Nuvem ou Contêineres  
**Integrantes:** Nicole França e Davi Teixeira
**Data:** 11 de junho de 2026

## 1. Descrição do problema

A Polícia Rodoviária Federal publica grandes arquivos CSV com ocorrências,
pessoas envolvidas e causas de acidentes. A consulta direta desses arquivos é
demorada, exige tratamento de tipos e dificulta a criação de indicadores.

O ROTA resolve esse problema por meio de uma aplicação distribuída que coleta,
normaliza, armazena, consulta e apresenta os dados. A carga pode ser executada
sequencialmente ou distribuída entre múltiplos workers.

## 2. Relevância

Os dados de acidentes ajudam a identificar estados, períodos e causas com maior
quantidade de ocorrências, feridos e mortes. Uma aplicação consultável facilita
a exploração dessas informações e demonstra um uso concreto de sistemas
paralelos e distribuídos.

## 3. Dados de entrada

Foram utilizados dados abertos da PRF referentes a 2024, 2025 e 2026:

| Arquivo | Conteúdo |
| --- | --- |
| `ocorrencias.csv` | Uma linha por acidente |
| `pessoas.csv` | Pessoas e veículos envolvidos |
| `pessoas_todas_causas.csv` | Causas e tipos associados |

Cada execução completa processa:

- 2.007.544 linhas;
- 751.752.064 bytes, aproximadamente 717 MiB;
- nove arquivos CSV, três para cada ano.

Os arquivos usam separador `;` e codificação `ISO-8859-1`. Como os dados reais
são grandes e não ficam no Git, o projeto também contém
`scripts/generate_sample_data.py` para gerar entradas compatíveis.

## 4. Solução centralizada

Na versão centralizada, um único processo percorre os anos em ordem. Para cada
arquivo, o Pandas lê blocos de 25 mil linhas, normaliza os valores e envia os
dados ao PostgreSQL por meio do comando `COPY`.

Essa solução é funcional, mas deixa CPU, leitura de arquivos e preparação dos
blocos concentradas em um único fluxo de execução.

## 5. Justificativa do paralelismo

Os anos são independentes: os registros de 2024, 2025 e 2026 possuem conjuntos
distintos identificados por `ano_fonte`. Isso permite processá-los
simultaneamente.

O paralelismo reduz o tempo total porque um worker pode ler e transformar um
ano enquanto outros fazem o mesmo com anos diferentes. O ganho não é
perfeitamente linear, pois todos compartilham CPU, disco, índices e PostgreSQL.

## 6. Arquitetura

```text
Portal PRF
    |
 Scraper
    |
 CSVs anuais
    |
 Coordenador do loader
   /       |       \
worker 1 worker 2 worker 3
   \       |       /
       PostgreSQL
           |
        FastAPI
        /     \
    Nginx   Streamlit

API + PostgreSQL + containers
           |
       Prometheus
           |
         Grafana
```

A arquitetura combina mestre-trabalhador, cliente-servidor, microsserviços e
pipeline de dados.

## 7. Componentes e comunicação

| Componente | Responsabilidade | Comunicação |
| --- | --- | --- |
| Scraper | Descoberta e download | HTTPS |
| Loader coordenador | Distribuição dos anos | Processos locais |
| Workers | Limpeza e carga | PostgreSQL/TCP |
| PostgreSQL | Persistência compartilhada | SQL |
| FastAPI | Consultas e métricas | HTTP |
| Nginx/frontend | Interface e proxy | HTTP |
| Streamlit | Dashboard analítico | HTTP com a API |
| Prometheus | Coleta de métricas | HTTP |
| Grafana | Visualização das métricas | PromQL/HTTP |
| cAdvisor | CPU e memória dos contêineres | Métricas |

O Docker Compose fornece rede interna e resolução DNS pelos nomes dos serviços.

## 8. Tecnologias e justificativas

- **Docker Compose:** execução reproduzível de múltiplos serviços.
- **Python 3.12 e Pandas:** leitura em blocos e normalização dos CSVs.
- **ProcessPoolExecutor:** processos independentes e quantidade configurável de
  workers.
- **PostgreSQL 17:** transações, índices e carga eficiente com `COPY`.
- **FastAPI:** API tipada, documentação automática e integração com métricas.
- **Nginx:** frontend estático e proxy reverso.
- **Streamlit e Plotly:** exploração complementar dos dados.
- **Prometheus, Grafana e cAdvisor:** latência, throughput, CPU e memória.

## 9. Implementação do paralelismo

O processo coordenador descobre os diretórios anuais e limita a quantidade
efetiva de workers ao número de anos. Com um worker, a carga é sequencial. Com
mais workers, cada ano é enviado a um processo do `ProcessPoolExecutor`.

Cada worker:

1. abre uma conexão própria;
2. inicia uma transação por arquivo;
3. remove os registros anteriores daquele ano;
4. lê e normaliza os blocos;
5. executa `COPY`;
6. registra linhas, bytes e duração;
7. confirma a transação.

Uma falha provoca rollback apenas da transação afetada e é propagada ao
coordenador.

## 10. Tratamento de erros

- health checks para API, frontend e banco;
- timeout e validação dos downloads;
- rejeição de ZIP inválido ou com quantidade incorreta de CSVs;
- SQL parametrizado na API;
- transações para evitar cargas parciais;
- validação de quantidade de workers e de diretórios anuais;
- logs de progresso e identificação do worker que falhou.

## 11. Metodologia dos testes de desempenho

Foram comparados 1, 2 e 3 workers usando exatamente os mesmos nove arquivos.
Cada configuração foi executada três vezes.

Para reduzir viés de cache, a ordem foi rotacionada:

| Repetição | Ordem |
| --- | --- |
| 1 | 1, 2 e 3 workers |
| 2 | 2, 3 e 1 workers |
| 3 | 3, 1 e 2 workers |

Métricas:

```text
throughput = linhas processadas / tempo
speedup = tempo médio com 1 worker / tempo médio paralelo
eficiência = speedup / quantidade de workers
```

O script `app/benchmark.py` gera automaticamente os arquivos de resultados.

## 12. Resultados

| Workers | Tempo médio (s) | Desvio (s) | Linhas/s | Speedup | Eficiência |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 24,135 | 1,800 | 83.482 | 1,000 | 100,00% |
| 2 | 17,274 | 1,330 | 116.697 | 1,397 | 69,86% |
| 3 | 12,886 | 0,828 | 156.229 | 1,873 | 62,43% |

Com três workers:

- o tempo médio caiu 11,249 segundos;
- a redução de tempo foi de aproximadamente 46,6%;
- o throughput aumentou aproximadamente 87,1%;
- o speedup foi 1,873.

Os dados completos estão em `benchmark/results/runs.csv` e os cálculos em
`benchmark/results/summary.csv`.

## 13. Análise

Os resultados confirmam que a divisão por ano melhora o desempenho. Três
workers tiveram o menor tempo e o maior throughput.

O speedup ficou abaixo de três porque a parte paralelizável compartilha
recursos. As principais limitações são:

- concorrência de leitura no mesmo disco;
- escrita simultânea no mesmo PostgreSQL;
- atualização dos mesmos índices;
- checkpoints e sincronização do banco;
- tamanhos diferentes entre os anos;
- custos de criação dos processos e conexões.

O ano de 2026 possui menos registros. Portanto, esse worker termina antes dos
workers de 2024 e 2025, causando desbalanceamento. Uma futura divisão por
arquivos ou partições menores poderia distribuir melhor o trabalho.

## 14. Testes funcionais

Foram implementados seis testes automatizados:

- normalização de inteiros, decimais, datas e nulos;
- descoberta e ordenação das pastas anuais;
- cálculo de média, speedup e eficiência;
- descoberta dos três tipos de dataset na página da PRF;
- extração de ZIP com um CSV;
- rejeição de ZIP com múltiplos CSVs.

Também foram validados:

- sintaxe Python;
- sintaxe JavaScript;
- configuração do Docker Compose;
- integridade do diff;
- resposta do endpoint `/health`;
- contagens finais das três tabelas por ano.

## 15. Dificuldades encontradas

- formatos e codificação dos arquivos públicos;
- volume total superior a 700 MiB;
- necessidade de evitar duplicação ao recarregar anos;
- concorrência no banco e nos índices;
- efeito de cache nas medições;
- diferença de tamanho entre as partições anuais;
- limitações do cAdvisor no Docker Desktop com WSL2.

## 16. Possíveis melhorias

- particionar tabelas por ano no PostgreSQL;
- dividir arquivos grandes em mais tarefas que a quantidade de anos;
- usar RabbitMQ ou Redis para uma fila dinâmica de trabalhos;
- separar workers em máquinas diferentes;
- testar múltiplas réplicas da API com balanceamento;
- incluir testes de carga HTTP com Locust;
- adicionar autenticação e configuração segura de credenciais;
- executar testes automaticamente em integração contínua.

## 17. Conclusão

O ROTA atende ao Tema 7 porque implementa uma aplicação distribuída com
múltiplos serviços conteinerizados e um mecanismo real de paralelismo.

A comparação controlada mostrou que três workers reduziram o tempo médio da
carga em aproximadamente 46,6% e produziram speedup de 1,873. O projeto também
demonstra por que o ganho não é linear, relacionando os resultados à
concorrência de recursos, ao banco compartilhado e ao desbalanceamento das
tarefas.
