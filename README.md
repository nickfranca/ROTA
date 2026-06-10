# Dados de acidentes da PRF

Este projeto baixa os dados anuais de acidentes disponibilizados no portal de
dados abertos da Polícia Rodoviária Federal (PRF).
Site: [text](https://www.gov.br/prf/pt-br/acesso-a-informacao/dados-abertos/dados-abertos-da-prf)

Para cada ano solicitado, o script baixa e extrai três arquivos:

- acidentes agrupados por ocorrência;
- acidentes agrupados por pessoa;
- acidentes agrupados por pessoa, incluindo todas as causas e tipos de
  acidentes.

Os arquivos ZIP são temporários. Depois da extração, somente os CSVs são
mantidos.

## Criar o ambiente virtual

Na raiz do projeto, crie o `.venv`:

```bash
python3 -m venv .venv
```

Ative o ambiente:

```bash
source .venv/bin/activate
```

No Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Atualize o `pip` e instale as dependências:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

O ambiente precisa ser criado somente uma vez. Nas execuções seguintes, basta
ativá-lo antes de rodar o script.

## Baixar os dados

Baixar um ano:

```bash
python prf_scraper.py 2025
```

Baixar vários anos:

```bash
python prf_scraper.py 2024 2025 2026
```

Se um CSV já existir, ele será substituído somente após o novo arquivo ser
baixado e extraído corretamente.

## Organização dos arquivos

Por padrão, cada ano é armazenado em uma pasta própria:

```text
data/
├── 2024/
│   ├── ocorrencias.csv
│   ├── pessoas.csv
│   └── pessoas_todas_causas.csv
├── 2025/
│   ├── ocorrencias.csv
│   ├── pessoas.csv
│   └── pessoas_todas_causas.csv
└── 2026/
    ├── ocorrencias.csv
    ├── pessoas.csv
    └── pessoas_todas_causas.csv
```

Os CSVs usam `;` como separador e são publicados pela PRF com codificação
ISO-8859-1.

### `ocorrencias.csv`

Possui uma linha por acidente. Contém informações gerais como:

- data e horário;
- UF, município, BR e quilômetro;
- causa e tipo principal do acidente;
- condição meteorológica e tipo de pista;
- totais de pessoas, veículos, feridos e mortos;
- latitude e longitude.

O campo `id` identifica o acidente e não se repete neste arquivo.

### `pessoas.csv`

Possui os dados das pessoas e dos veículos envolvidos:

- `pesid`: identificação da pessoa;
- `id_veiculo`: identificação do veículo;
- idade, sexo e tipo de envolvido;
- estado físico;
- tipo, marca e ano do veículo;
- causa principal e tipo principal do acidente.

Um mesmo `id` aparece várias vezes porque um acidente pode envolver diversas
pessoas e veículos.

Algumas linhas representam somente veículos. Nelas, `pesid` pode ser igual a
`0` e os campos da pessoa ficam como `NA`.

### `pessoas_todas_causas.csv`

É uma versão expandida de `pessoas.csv`. Cada pessoa ou veículo é repetido para
todas as combinações de causas e tipos registradas no acidente.

Os campos adicionais mais importantes são:

- `causa_principal`: informa se aquela causa é a principal;
- `causa_acidente`: causa registrada;
- `ordem_tipo_acidente`: posição do tipo na sequência do acidente;
- `tipo_acidente`: tipo ou evento ocorrido.

O conteúdo de `pessoas.csv` corresponde ao recorte de
`pessoas_todas_causas.csv` em que:

```text
causa_principal = "Sim"
ordem_tipo_acidente = 1
```

## Sugestão de conexão de dados

### Ocorrências com pessoas

A conexão principal é feita pelo campo `id`:

```sql
SELECT *
FROM ocorrencias AS o
JOIN pessoas AS p
    ON o.id = p.id;
```

Essa relação é de um para muitos: uma ocorrência pode possuir várias pessoas e
veículos.

### Ocorrências com todas as causas

Também é possível conectar diretamente pelo `id`:

```sql
SELECT *
FROM ocorrencias AS o
JOIN pessoas_todas_causas AS ptc
    ON o.id = ptc.id;
```

Use esse formato para estudar causas secundárias ou a sequência de tipos do
acidente.

### Pessoas com todas as causas

Para pessoas identificadas, use `id` e `pesid`:

```sql
SELECT *
FROM pessoas AS p
JOIN pessoas_todas_causas AS ptc
    ON p.id = ptc.id
   AND p.pesid = ptc.pesid
WHERE p.pesid <> 0;
```

Para linhas que representam apenas veículos, use `id` e `id_veiculo`:

```sql
SELECT *
FROM pessoas AS p
JOIN pessoas_todas_causas AS ptc
    ON p.id = ptc.id
   AND p.id_veiculo = ptc.id_veiculo
WHERE p.pesid = 0;
```

Na maioria das análises, não é necessário conectar `pessoas.csv` com
`pessoas_todas_causas.csv`. Escolha um deles:

- use `pessoas.csv` para análises gerais com a causa e o tipo principais;
- use `pessoas_todas_causas.csv` quando causas secundárias ou múltiplos tipos
  forem necessários.

## Evitar contagens duplicadas

Após um `JOIN`, os valores gerais da ocorrência serão repetidos para cada
pessoa, causa e tipo. Por isso, não use `COUNT(*)` para contar acidentes.

Para contar acidentes:

```sql
COUNT(DISTINCT id)
```

Para contar pessoas identificadas:

```sql
COUNT(DISTINCT CONCAT(id, '-', pesid))
```

Para contar veículos:

```sql
COUNT(DISTINCT CONCAT(id, '-', id_veiculo))
```

Totais consolidados, como mortos e feridos por ocorrência, devem ser somados
diretamente a partir de `ocorrencias.csv` ou depois de reduzir o resultado do
`JOIN` para uma linha por `id`.

## Modelo recomendado

```text
ocorrencias.id
    ├── pessoas.id
    └── pessoas_todas_causas.id
```

Use `ocorrencias.csv` como tabela principal de acidentes e escolha
`pessoas.csv` ou `pessoas_todas_causas.csv` como tabela detalhada, conforme a
pergunta que será respondida.
