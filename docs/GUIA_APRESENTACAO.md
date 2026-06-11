# Guia de estudo e apresentação do ROTA

Este documento explica o projeto para quem ainda não conhece Docker,
paralelismo, APIs, bancos de dados ou ferramentas de monitoramento.

## 1. O projeto em uma frase

O ROTA baixa dados de acidentes da PRF, trata os arquivos, salva as
informações em um banco de dados e apresenta gráficos em uma aplicação web.

A principal demonstração da disciplina é:

> Dividir a carga dos dados entre vários workers reduz o tempo de
> processamento.

## 2. Visão geral

```text
Portal da PRF
      |
      v
   Scraper
      |
      v
Arquivos CSV
      |
      v
Coordenador do loader
  /       |       \
 v        v        v
Worker 1 Worker 2 Worker 3
  \       |       /
          v
      PostgreSQL
          |
          v
        FastAPI
        /     \
       v       v
  Frontend   Streamlit

Aplicação -> Prometheus -> Grafana
```

Cada componente possui uma responsabilidade específica.

## 3. O problema

A Polícia Rodoviária Federal disponibiliza arquivos CSV com centenas de
milhares de registros.

CSV é um arquivo parecido com uma planilha:

```text
id;data;uf;causa;mortos
1;2025-01-01;TO;Excesso de velocidade;0
2;2025-01-02;GO;Ingestão de álcool;1
```

O projeto trabalha com três tipos de arquivo:

- acidentes;
- pessoas envolvidas;
- causas dos acidentes.

No benchmark foram processados:

- nove arquivos;
- dados de 2024, 2025 e 2026;
- aproximadamente 717 MiB;
- 2.007.544 linhas.

Consultar diretamente os arquivos sempre que alguém abre a página seria
ineficiente. Por isso, eles são tratados e armazenados no PostgreSQL.

## 4. Docker

Docker permite executar programas em ambientes isolados chamados
**contêineres**.

Um contêiner pode ser entendido como uma caixa que contém:

- o programa;
- as bibliotecas;
- as configurações;
- tudo que o programa precisa para funcionar.

O projeto possui contêineres para:

- frontend;
- API;
- banco de dados;
- dashboard;
- Prometheus;
- Grafana;
- cAdvisor;
- PostgreSQL Exporter.

Tudo pode ser iniciado com:

```bash
docker compose up -d
```

## 5. Docker Compose

Docker Compose organiza todos os contêineres.

O arquivo `docker-compose.yml` informa:

- quais serviços existem;
- quais portas são utilizadas;
- quais serviços dependem de outros;
- quais diretórios são compartilhados;
- quais variáveis de ambiente são necessárias.

Exemplos de dependência:

```text
Frontend depende da API.
API depende do banco.
Grafana depende do Prometheus.
```

O Compose também cria uma rede interna. Nessa rede, os serviços são
localizados por nomes como `api`, `db` e `prometheus`.

## 6. Scraper

O scraper é o programa que coleta os dados.

Ele:

1. acessa a página da PRF;
2. encontra os links;
3. baixa os arquivos ZIP;
4. verifica se os ZIPs são válidos;
5. extrai os CSVs;
6. organiza os arquivos por ano.

Resultado:

```text
data/
├── 2024/
├── 2025/
└── 2026/
```

O scraper apenas baixa e organiza. Ele não trata os dados.

## 7. Loader e ETL

O loader trata os arquivos e envia os resultados ao banco.

Esse processo é chamado de **ETL**:

- **Extract:** extrair ou ler os CSVs;
- **Transform:** limpar e converter os valores;
- **Load:** carregar os dados no banco.

Exemplos:

```text
"10,5"       -> número 10.5
"2025-01-01" -> data
"N/A"        -> valor nulo
"25"         -> número inteiro 25
```

Os arquivos são lidos em blocos de 25 mil linhas para evitar que centenas de
megabytes sejam carregadas na memória ao mesmo tempo.

## 8. Paralelismo e workers

Um **worker** é um processo responsável por executar uma parte do trabalho.

Na versão sequencial:

```text
Worker 1: 2024 -> 2025 -> 2026
```

Na versão paralela:

```text
Worker 1 -> 2024
Worker 2 -> 2025
Worker 3 -> 2026
```

Os três anos são processados ao mesmo tempo.

O coordenador distribui os anos usando o `ProcessPoolExecutor` do Python.

### Por que dividir por ano?

Os dados são independentes:

```text
Worker 1 altera somente 2024.
Worker 2 altera somente 2025.
Worker 3 altera somente 2026.
```

Cada worker possui sua própria conexão e transação com o banco.

## 9. PostgreSQL

PostgreSQL é o banco de dados.

Ele armazena as informações em tabelas:

| Tabela | Conteúdo |
| --- | --- |
| `ocorrencias` | Acidentes |
| `pessoas` | Pessoas envolvidas |
| `causas` | Causas dos acidentes |
| `cargas` | Histórico das importações |

Uma consulta SQL pode perguntar quantos acidentes existem por estado:

```sql
SELECT uf, COUNT(*)
FROM ocorrencias
GROUP BY uf;
```

O loader utiliza o comando `COPY`, que é uma forma eficiente de inserir
milhares de registros.

## 10. Transações e rollback

Uma transação protege a consistência dos dados.

```text
Apagar dados antigos do ano
          |
Inserir os novos registros
          |
Registrar informações da carga
          |
Confirmar tudo
```

Se ocorrer um erro, o PostgreSQL faz um **rollback**, que desfaz aquela
operação. Assim, o banco não fica com apenas parte do arquivo carregada.

## 11. FastAPI e API

FastAPI é a tecnologia usada para construir a API.

O fluxo é:

```text
Frontend -> API -> PostgreSQL
```

O frontend não acessa diretamente o banco.

Exemplo de requisição:

```http
GET /api/resumo
```

Exemplo de resposta:

```json
{
  "acidentes": 169160,
  "pessoas": 455060,
  "mortos": 12345
}
```

Outros endpoints:

```text
/api/por-uf
/api/top-causas
/api/serie-mensal
/api/perfil-vitimas
```

## 12. HTTP

HTTP é o protocolo usado para a comunicação web.

```text
Frontend envia uma requisição HTTP.
API recebe a requisição.
API consulta o banco.
API devolve uma resposta HTTP.
```

O método `GET` solicita informações sem alterá-las.

## 13. Frontend e Nginx

Frontend é a página vista pelo usuário.

Ela utiliza:

- HTML para a estrutura;
- CSS para a aparência;
- JavaScript para buscar dados e gerar gráficos;
- Nginx como servidor web.

Endereço:

```text
http://localhost:3001
```

O Nginx também atua como proxy reverso:

```text
Navegador: http://localhost:3001/api/resumo
                         |
                         v
API interna: http://api:8000/api/resumo
```

## 14. Streamlit

Streamlit é um dashboard complementar construído com Python.

Endereço:

```text
http://localhost:8501
```

Ele utiliza Plotly para apresentar gráficos e também consulta a FastAPI:

```text
Streamlit -> FastAPI -> PostgreSQL
```

## 15. Prometheus

Prometheus é uma ferramenta que coleta e armazena métricas.

Métricas são números sobre o funcionamento do sistema:

- requisições por segundo;
- tempo de resposta;
- uso de CPU;
- uso de memória;
- conexões do banco;
- transações.

O Prometheus consulta os serviços periodicamente:

```text
API -----------\
PostgreSQL -----> Prometheus
Contêineres ---/
```

## 16. Grafana

Grafana transforma as métricas do Prometheus em gráficos e painéis.

```text
Aplicação -> Prometheus -> Grafana
```

Resumo:

- Prometheus coleta e armazena;
- Grafana exibe.

O dashboard mostra:

- requisições por segundo;
- latência da API;
- CPU por contêiner;
- memória por contêiner;
- conexões PostgreSQL;
- transações do banco.

Endereço:

```text
http://localhost:3000
```

Credenciais:

```text
usuário: admin
senha: admin
```

## 17. cAdvisor e PostgreSQL Exporter

O **cAdvisor** mede os recursos usados pelos contêineres:

```text
Contêineres -> cAdvisor -> Prometheus -> Grafana
```

Ele observa CPU, memória e rede.

O **PostgreSQL Exporter** traduz as métricas do banco para o formato esperado
pelo Prometheus:

```text
PostgreSQL -> PostgreSQL Exporter -> Prometheus
```

## 18. Observabilidade

Observabilidade é a capacidade de entender o que acontece dentro do sistema.

O projeto utiliza:

```text
logs + métricas + health checks
```

Logs são mensagens:

```text
25.000 linhas carregadas
arquivo concluído em 2,5 segundos
```

Métricas são números históricos:

```text
CPU: 40%
latência: 0,08 segundo
20 requisições por segundo
```

Health check verifica se o serviço está funcionando:

```http
GET /health
```

Resposta:

```json
{"status":"ok","database":1}
```

## 19. Benchmark

Benchmark é um teste controlado de desempenho.

Foram comparados:

- um worker;
- dois workers;
- três workers.

Cada configuração foi executada três vezes. A ordem foi alternada:

```text
Repetição 1: 1, 2, 3
Repetição 2: 2, 3, 1
Repetição 3: 3, 1, 2
```

Isso reduz o efeito de cache e aquecimento do armazenamento.

## 20. Resultados

| Workers | Tempo médio | Linhas/s | Speedup | Eficiência |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 24,135 s | 83.482 | 1,000 | 100,00% |
| 2 | 17,274 s | 116.697 | 1,397 | 69,86% |
| 3 | 12,886 s | 156.229 | 1,873 | 62,43% |

Com três workers:

- o tempo caiu de 24,135 para 12,886 segundos;
- houve redução aproximada de 46,6%;
- a execução ficou aproximadamente 1,87 vez mais rápida;
- o throughput chegou a aproximadamente 156 mil linhas por segundo.

## 21. Speedup

Speedup indica quantas vezes a execução paralela foi mais rápida.

```text
Speedup = tempo sequencial / tempo paralelo
```

Para três workers:

```text
Speedup = 24,135 / 12,886
Speedup = 1,873
```

Portanto, três workers foram aproximadamente 1,87 vez mais rápidos.

## 22. Eficiência

Eficiência indica quanto da capacidade teórica dos workers foi aproveitada.

```text
Eficiência = speedup / quantidade de workers
```

Para três workers:

```text
Eficiência = 1,873 / 3
Eficiência = 62,43%
```

O resultado não é linear porque os workers compartilham:

- processador;
- disco;
- memória;
- PostgreSQL;
- índices do banco.

Além disso, 2026 possui menos dados. Seu worker termina antes dos outros,
causando desbalanceamento.

## 23. Por que o speedup não foi três?

Com três workers, o valor ideal seria três. Na prática, existem custos:

1. Todos leem arquivos do mesmo disco.
2. Todos escrevem no mesmo banco.
3. O banco atualiza os mesmos índices.
4. Criar processos e conexões possui custo.
5. Os anos têm tamanhos diferentes.
6. Algumas partes continuam sequenciais.

Explicar isso demonstra compreensão do paralelismo.

## 24. Testes automatizados

Foram implementados seis testes:

- conversão dos dados;
- tratamento de valores nulos;
- identificação das pastas anuais;
- cálculo de speedup e eficiência;
- descoberta dos arquivos da PRF;
- validação dos arquivos ZIP.

Comando:

```bash
docker compose --profile load run --rm loader \
  python -m unittest discover -v
```

Resultado esperado:

```text
Ran 6 tests
OK
```

## 25. Roteiro de fala

> Nosso projeto se chama ROTA e analisa dados abertos de acidentes da Polícia
> Rodoviária Federal. O problema é que os dados são publicados em arquivos CSV
> grandes, que precisam ser baixados, tratados e armazenados antes de serem
> consultados eficientemente.

> Criamos uma aplicação distribuída com Docker Compose. Ela possui scraper,
> loader, PostgreSQL, API FastAPI, frontend Nginx, dashboard Streamlit e
> ferramentas de observabilidade.

> O scraper baixa os arquivos da PRF. O loader realiza o ETL, convertendo
> datas, números e valores nulos. Depois, os dados são inseridos no PostgreSQL
> usando o comando COPY.

> O paralelismo está no loader. Na versão sequencial, um worker processa 2024,
> depois 2025 e depois 2026. Na versão paralela, três processos trabalham
> simultaneamente, cada um responsável por um ano.

> A API consulta o PostgreSQL e entrega os resultados por HTTP. O frontend e o
> Streamlit consomem essa API e exibem indicadores e gráficos.

> Para observar a aplicação, utilizamos Prometheus para coletar métricas e
> Grafana para exibi-las. O cAdvisor coleta CPU e memória dos contêineres,
> enquanto o PostgreSQL Exporter coleta métricas do banco.

> No benchmark, processamos 2.007.544 linhas. Com um worker, o tempo médio foi
> 24,135 segundos. Com três workers, caiu para 12,886 segundos. Isso representa
> speedup de 1,873 e redução de aproximadamente 46,6%.

> O ganho não foi linear porque os processos compartilham disco, CPU e o mesmo
> banco de dados. Também existe desbalanceamento, pois 2026 possui menos dados.

> Concluímos que a distribuição por workers melhorou o throughput e reduziu o
> tempo total, demonstrando na prática conceitos de sistemas paralelos e
> distribuídos.

## 26. Perguntas prováveis

### Onde está o paralelismo?

No loader. Processos diferentes carregam anos diferentes simultaneamente
usando `ProcessPoolExecutor`.

### Onde está a distribuição?

Nos serviços Docker independentes que se comunicam pela rede: frontend, API,
banco, dashboard e monitoramento.

### Qual a diferença entre paralelismo e distribuição?

Paralelismo é executar tarefas simultaneamente. Distribuição é separar
responsabilidades entre componentes independentes que se comunicam.

### Por que processos em vez de threads?

Os processos são independentes, podem usar múltiplos núcleos e cada worker
mantém sua própria conexão com o banco.

### Por que PostgreSQL?

Porque oferece SQL, índices, transações e carga eficiente com `COPY`.

### Prometheus e Grafana são a mesma coisa?

Não. Prometheus coleta e armazena métricas. Grafana consulta essas métricas e
cria os painéis.

### Por que três workers?

Porque existem três partições naturais dos dados: 2024, 2025 e 2026.

### O que acontece se um worker falhar?

A transação daquele arquivo é desfeita e o erro é propagado ao coordenador.

### Qual foi o ganho?

Redução de 46,6% no tempo médio e speedup de 1,873 com três workers.

### Por que a eficiência diminuiu?

Porque os workers disputam recursos compartilhados e processam quantidades
diferentes de dados.

## 27. Endereços da demonstração

| Recurso | Endereço |
| --- | --- |
| Aplicação principal | http://localhost:3001 |
| Dashboard Streamlit | http://localhost:8501 |
| Documentação da API | http://localhost:8000/docs |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| cAdvisor | http://localhost:8080 |

## 28. Comandos importantes

Iniciar:

```bash
docker compose up -d
```

Verificar os serviços:

```bash
docker compose ps
```

Executar carga com três workers:

```bash
docker compose --profile load run --rm loader \
  python -m app.loader --workers 3 2024 2025 2026
```

Executar benchmark:

```bash
docker compose --profile benchmark run --rm benchmark
```

Executar testes:

```bash
docker compose --profile load run --rm loader \
  python -m unittest discover -v
```

Parar:

```bash
docker compose down
```

Não use `docker compose down -v` antes da apresentação, pois `-v` apaga o
volume do banco.
