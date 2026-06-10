CREATE TABLE IF NOT EXISTS ocorrencias (
    ano_fonte SMALLINT NOT NULL,
    id BIGINT NOT NULL,
    data_inversa DATE,
    dia_semana TEXT,
    horario TIME,
    uf CHAR(2),
    br NUMERIC,
    km NUMERIC,
    municipio TEXT,
    causa_acidente TEXT,
    tipo_acidente TEXT,
    classificacao_acidente TEXT,
    fase_dia TEXT,
    sentido_via TEXT,
    condicao_metereologica TEXT,
    tipo_pista TEXT,
    tracado_via TEXT,
    uso_solo TEXT,
    pessoas INTEGER,
    mortos INTEGER,
    feridos_leves INTEGER,
    feridos_graves INTEGER,
    ilesos INTEGER,
    ignorados INTEGER,
    feridos INTEGER,
    veiculos INTEGER,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    regional TEXT,
    delegacia TEXT,
    uop TEXT,
    PRIMARY KEY (ano_fonte, id)
);

CREATE TABLE IF NOT EXISTS pessoas (
    ano_fonte SMALLINT NOT NULL,
    id BIGINT NOT NULL,
    pesid BIGINT,
    id_veiculo BIGINT,
    data_inversa DATE,
    uf CHAR(2),
    municipio TEXT,
    tipo_veiculo TEXT,
    ano_fabricacao_veiculo INTEGER,
    tipo_envolvido TEXT,
    estado_fisico TEXT,
    idade INTEGER,
    sexo TEXT
);

CREATE TABLE IF NOT EXISTS causas (
    ano_fonte SMALLINT NOT NULL,
    id BIGINT NOT NULL,
    pesid BIGINT,
    id_veiculo BIGINT,
    causa_principal TEXT,
    causa_acidente TEXT,
    ordem_tipo_acidente INTEGER,
    tipo_acidente TEXT
);

CREATE TABLE IF NOT EXISTS cargas (
    id BIGSERIAL PRIMARY KEY,
    ano_fonte SMALLINT NOT NULL,
    arquivo TEXT NOT NULL,
    tabela_destino TEXT NOT NULL,
    linhas BIGINT NOT NULL,
    bytes BIGINT NOT NULL,
    duracao_segundos DOUBLE PRECISION NOT NULL,
    carregado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ocorrencias_data ON ocorrencias (data_inversa);
CREATE INDEX IF NOT EXISTS idx_ocorrencias_uf ON ocorrencias (uf);
CREATE INDEX IF NOT EXISTS idx_ocorrencias_causa ON ocorrencias (causa_acidente);
CREATE INDEX IF NOT EXISTS idx_pessoas_id ON pessoas (ano_fonte, id);
CREATE INDEX IF NOT EXISTS idx_pessoas_perfil ON pessoas (idade, sexo, estado_fisico);
CREATE INDEX IF NOT EXISTS idx_causas_id ON causas (ano_fonte, id);
CREATE INDEX IF NOT EXISTS idx_causas_causa ON causas (causa_acidente);
