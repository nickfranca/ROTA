from __future__ import annotations

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

from app.config import API_URL


st.set_page_config(
    page_title="Acidentes PRF",
    page_icon="",
    layout="wide",
)


@st.cache_data(ttl=60)
def api_get(path: str, params: dict | None = None):
    response = requests.get(f"{API_URL}{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


st.title("Painel de acidentes em rodovias federais")
st.caption("Dados abertos da Policia Rodoviaria Federal")

anos = api_get("/api/por-ano")
opcoes_ano = ["Todos"] + [item["ano"] for item in anos]
ano_selecionado = st.sidebar.selectbox("Ano", opcoes_ano)
ano = None if ano_selecionado == "Todos" else int(ano_selecionado)
params = {"ano": ano} if ano else {}

resumo = api_get("/api/resumo", params)
colunas = st.columns(4)
colunas[0].metric("Acidentes", f"{resumo['acidentes']:,}".replace(",", "."))
colunas[1].metric("Pessoas envolvidas", f"{resumo['pessoas']:,}".replace(",", "."))
colunas[2].metric("Feridos", f"{resumo['feridos']:,}".replace(",", "."))
colunas[3].metric("Mortos", f"{resumo['mortos']:,}".replace(",", "."))

serie = pd.DataFrame(api_get("/api/serie-mensal", params))
ufs = pd.DataFrame(api_get("/api/por-uf", params))
causas = pd.DataFrame(api_get("/api/top-causas", params))

esquerda, direita = st.columns(2)
with esquerda:
    st.plotly_chart(
        px.line(
            serie,
            x="mes",
            y="acidentes",
            markers=True,
            title="Evolucao mensal dos acidentes",
        ),
        use_container_width=True,
    )
with direita:
    st.plotly_chart(
        px.bar(
            ufs,
            x="uf",
            y="acidentes",
            color="mortos",
            title="Acidentes e mortes por UF",
        ),
        use_container_width=True,
    )

esquerda, direita = st.columns(2)
with esquerda:
    st.plotly_chart(
        px.bar(
            causas.sort_values("acidentes"),
            x="acidentes",
            y="causa",
            orientation="h",
            title="Principais causas",
        ),
        use_container_width=True,
    )
with direita:
    condicoes = pd.DataFrame(api_get("/api/condicoes", params))
    st.plotly_chart(
        px.scatter(
            condicoes,
            x="acidentes",
            y="mortos",
            size="acidentes",
            hover_name="condicao",
            title="Condicao meteorologica: acidentes x mortes",
        ),
        use_container_width=True,
    )

st.subheader("Perfil das pessoas envolvidas")
perfil = pd.DataFrame(api_get("/api/perfil-vitimas", params))
if not perfil.empty:
    agrupado = perfil.groupby(
        ["faixa_etaria", "estado_fisico"], as_index=False
    )["pessoas"].sum()
    st.plotly_chart(
        px.bar(
            agrupado,
            x="faixa_etaria",
            y="pessoas",
            color="estado_fisico",
            barmode="stack",
        ),
        use_container_width=True,
    )

with st.expander("Desempenho das cargas"):
    st.dataframe(pd.DataFrame(api_get("/api/cargas")), use_container_width=True)
    st.markdown(
        "Metricas de CPU, memoria, rede e tempo de resposta estao no Grafana."
    )
