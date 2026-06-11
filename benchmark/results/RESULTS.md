# Resultado do benchmark

- Gerado em: `2026-06-11T11:33:51+00:00`
- Anos processados: `2024,2025,2026`
- Linhas processadas por execucao: `2007544`
- Volume lido por execucao: `751752064` bytes
- Repeticoes por configuracao: `3`
- Ordem rotativa entre repeticoes para reduzir o efeito de cache

| Workers | Tempo medio (s) | Desvio (s) | Linhas/s | Speedup | Eficiencia |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 24.135 | 1.800 | 83482.37 | 1.000 | 100.00% |
| 2 | 17.274 | 1.330 | 116697.37 | 1.397 | 69.86% |
| 3 | 12.886 | 0.828 | 156228.57 | 1.873 | 62.43% |

## Analise

A melhor media foi obtida com **3 worker(s)**, com speedup de **1.873** em relacao a 1 worker.

A eficiencia abaixo de 100% e esperada porque os workers disputam CPU, leitura de disco, escrita nos indices e recursos do PostgreSQL. Por isso, aumentar workers pode deixar de produzir ganho linear.

Os arquivos `runs.csv` e `summary.csv` preservam os dados brutos e as medias usadas nesta tabela.
