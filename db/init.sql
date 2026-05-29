CREATE TABLE IF NOT EXISTS viagens_tratadas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    linha VARCHAR(50) NOT NULL,
    data_viagem DATE NOT NULL,
    horario_previsto TIME NOT NULL,
    horario_realizado TIME NOT NULL,
    passageiros INT NOT NULL,
    status_viagem VARCHAR(30) NOT NULL,
    atraso_minutos INT NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS estatisticas_linha (
    id INT AUTO_INCREMENT PRIMARY KEY,
    linha VARCHAR(50) NOT NULL,
    total_viagens INT NOT NULL,
    total_passageiros INT NOT NULL,
    media_atraso_minutos DECIMAL(10,2) NOT NULL,
    percentual_atrasadas DECIMAL(10,2) NOT NULL,
    modo_processamento VARCHAR(30) NOT NULL,
    tempo_execucao_segundos DECIMAL(10,4) NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
