import json
import math
import requests
import numpy as np
import pandas as pd
import streamlit as st
import geopandas as gpd
import plotly.express as px
import pyarrow
# import plotly.graph_objects as gov
import plotly.subplots as sp
from datetime import date

# -------------------- CONFIGURAÇÕES ----------------------
titulo_pagina = 'Mapa de Eventos Climáticos :world_map:'
# titulo_pagina = 'Mapa de Eventos Climáticos'
layout = 'wide'
# st.set_page_config(layout=layout)
st.set_page_config(page_title='Mapa de Eventos Climáticos', layout=layout)
st.title(titulo_pagina)
# ---------------------------------------------------------

@st.cache_resource
def single():
    pd.set_option('compute.use_numexpr', False)

single()


# FUNÇÕES
def number_to_human(num):
    if num >= 1000000000:
        return f'R$ {num/1000000000:.2f} Bi'
    elif num > 1000000:
        return f'R$ {num/1000000:.2f} Mi'
    elif num > 1000:
        return f'R$ {num/1000:.2f} Mil'
    else:
        return f'R$ {num:.2f}'

@st.cache_data
def carrega_geojson(caminho):
    with open(caminho, 'r') as f:
        geoj = json.load(f)
    return geoj

# @st.cache_data
def filtra_geojson(geojson, iso, prop='codarea'):
    gdf = gpd.GeoDataFrame.from_features(geojson)
    return json.loads(gdf[gdf[prop] == iso].to_json())

@st.cache_data
def carrega_dados(caminho_arquivo):
    df = pd.read_csv(caminho_arquivo, engine='pyarrow', dtype_backend='pyarrow')
    return df

@st.cache_data
def carrega_parquet(caminho_arquivo):
    df = pd.read_parquet(caminho_arquivo, engine='pyarrow', dtype_backend='pyarrow')
    return df

@st.cache_data
def carrega_malha(tipo='estados', uf='MG', intrarregiao='municipio', qualidade='minima'):
    url = f'https://servicodados.ibge.gov.br/api/v3/malhas/{tipo}/{uf}?formato=application/vnd.geo+json&intrarregiao={intrarregiao}&qualidade={qualidade}'
    return requests.get(url).json()

def filtra_estado(df, uf):
    return df[(df.uf.eq(uf))]

def filtra_grupo_desastre(df, grupo_desastre):
    return df[df.grupo_de_desastre == grupo_desastre]

def filtra_ano(df, inicio, fim):
    return df[(df.data.ge(f'{inicio}-01-01')) & (df.data.le(f'{fim}-12-30'))]

def calcula_ocorrencias(df, cols_selecionadas, cols_agrupadas):
    return df.groupby(cols_agrupadas, as_index=False)[cols_selecionadas].count().rename(columns={'protocolo': 'ocorrencias'})

def classifica_risco(df, col_ocorrencias):
    # df = dataframe.copy()
    quartis = df[col_ocorrencias].quantile([0.2, 0.4, 0.6, 0.8]).values
    risco = []
    for valor in df[col_ocorrencias]:
        if valor > quartis[3]:
            risco.append('Muito Alto')
        elif valor > quartis[2]:
            risco.append('Alto')
        elif valor > quartis[1]:
            risco.append('Moderado')
        elif valor > quartis[0]:
            risco.append('Baixo')
        else:
            risco.append('Muito Baixo')
    df['risco'] = risco
    return df

def classifica_segurado(df, munis, munis_segurados, munis_sinistrados):
    # df = dataframe.copy()
    tudo = set(munis)
    tenho = set(munis_segurados)
    especifico = set(munis_sinistrados)

    nao_segurado = list(tudo - tenho)
    nao_sinistrado = list(tenho - especifico)

    df['seg'] = np.where(df.code_muni.isin(nao_segurado), 'Não Segurada', 'Mais Sinistros que a Média')
    # df['seg'] = np.where(df.code_muni.isin(nao_segurado), 'Não Segurada', 'Apresenta Sinistro')
    df.loc[df[df.code_muni.isin(nao_sinistrado)].index, 'seg'] = 'Menos Sinistros que a Média'
    # df.loc[df[df.code_muni.isin(nao_sinistrado)].index, 'seg'] = 'Não Apresenta Sinistro'
    # df.seg = np.where(df.ibge.isin(nao_sinistrado), 'Não Apresenta Sinistro', 'Apresenta Sinistro')
    
    # nenhum = set(base.query("descricao_tipologia == '-'").ibge)
    # algum = set(base.query("descricao_tipologia != '-'").ibge)
    # resultado = list(nenhum - algum)
    # df['seg'] = np.where(df.ibge == '-', 'Não Segurada', 'Apresenta Sinistro')
    # df.seg = df.seg.mask(df.code_muni.isin(resultado), 'Não Apresenta Sinistro')
    return df

# @st.cache_data
def classifica_lossratio(df):
    # df = dados.copy()
    df['classe_sinistralidade'] = pd.cut(df.loss_ratio, [0.0, 20, 40, 60, 80, 100, 1000], labels=['Abaixo de 20%', 'De 20% a 40%', 'De 40% e 60%', 'De 60% e 80%', 'De 80% e 100%', 'Acima de 100%'])
    return df

def cria_mapa(df, malha, locais='ibge', cor='ocorrencias', tons=None, tons_midpoint=None, nome_hover=None, dados_hover=None, lista_cores=None, lat=-14, lon=-53, zoom=3, titulo_legenda='Risco', featureid='properties.codarea', min_max=None):
    ordem = {cor: list(lista_cores.keys())} if lista_cores else None
    fig = px.choropleth_mapbox(
        df, geojson=malha, color=cor,
        color_continuous_scale=tons,
        range_color=min_max,
        color_continuous_midpoint=tons_midpoint,
        color_discrete_map=lista_cores,
        category_orders=ordem,
        labels={'risco': 'Risco', 'ocorrencias': 'Ocorrências', 'code_muni': 'Código Municipal', 'sinistros': 'Sinistros',
                'code_state': 'Código', 'desastre_mais_comum': 'Desastre mais comum', 'evento_mais_comum': 'Evento mais comum',
                'seg': 'Tipo de Área Segurada', 'classe_sinistralidade': 'Classificação', 'loss_ratio': 'Índice de Sinistralidade'},
        locations=locais, featureidkey=featureid,
        center={'lat': lat, 'lon': lon}, zoom=zoom, 
        mapbox_style='carto-positron', height=500,
        hover_name=nome_hover, hover_data=dados_hover,
        opacity=0.95
    )

    fig.update_layout(
        margin={"r":0,"t":0,"l":0,"b":0},
        mapbox_bounds={"west": -150, "east": -20, "south": -60, "north": 60},
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor='rgb(250, 250, 250)',
            font=dict(size=14),
            title=dict(
                font=dict(size=16),
                text=titulo_legenda
            ),
            traceorder="normal"
        )
    )
    
    return fig



# VARIAVEIS
dados_atlas = carrega_parquet('desastres_latam2.parquet')
dados_merge = carrega_parquet('area2.parquet')
coord_uf = carrega_parquet('coord_uf.parquet')
coord_muni = carrega_parquet('coord_muni.parquet')
pop_pib = carrega_parquet('pop_pib_muni.parquet')
# pop_pib_uf = carrega_parquet('pop_pib_latam.parquet')
# malha_america = carrega_geojson('malha_latam.json')
# malha_brasil = carrega_geojson('malha_brasileira.json')

# dados_susep = carrega_parquet('susep_agro.parquet')
# psr = carrega_parquet('PSR_COMPLETO.parquet')
# psr.seguradora = psr.seguradora.map(seg)
# psr.pe_taxa = psr.pe_taxa * 100

print(dados_atlas.info())


estados = {
    'Acre': 'AC',
    'Alagoas': 'AL',
    'Amazonas': 'AM',
    'Amapá': 'AP',
    'Bahia': 'BA',
    'Ceará': 'CE',
    'Distrito Federal': 'DF',
    'Espírito Santo': 'ES',
    'Goiás': 'GO',
    'Maranhão': 'MA',
    'Minas Gerais': 'MG',
    'Mato Grosso do Sul': 'MS',
    'Mato Grosso': 'MT',
    'Pará': 'PA',
    'Paraíba': 'PB',
    'Pernambuco': 'PE',
    'Piauí': 'PI',
    'Paraná': 'PR',
    'Rio de Janeiro': 'RJ',
    'Rio Grande do Norte': 'RN',
    'Rondônia': 'RO',
    'Roraima': 'RR',
    'Rio Grande do Sul': 'RS',
    'Santa Catarina': 'SC',
    'Sergipe': 'SE',
    'São Paulo': 'SP',
    'Tocantins': 'TO'
}


# estados = ['AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO']
anos = np.arange(1991, 2023)
anos_latam = np.arange(2000, 2024)
anos_psr = np.arange(2006, 2022)
mapa_de_cores = {
    'Estiagem e Seca': '#EECA3B',
    'Incêndio Florestal': '#E45756',
    'Onda de Frio': '#72B7B2',
    'Onda de Calor e Baixa Umidade': '#F58518',
    'Enxurradas': '#B279A2',
    'Inundações': '#0099C6',
    'Alagamentos': '#72B7B2',
    'Movimento de Massa': '#9D755D',
    'Chuvas Intensas': '#4C78A8',
    'Vendavais e Ciclones': '#54A24B',
    'Granizo': 'rgb(102, 102, 102)',
    'Tornado': '#4C78A8',
    'Onda de Frio': '#72B7B2',
    'Doenças infecciosas': '#54A24B',
    'Erosão': '#9D755D',
    'Outros': '#FF9DA6',
    'Rompimento/Colapso de barragens': 'rgb(102, 102, 102)',
    'Sem Dados': '#BAB0AC'
}
meses = {
    '1': 'JAN',
    '2': 'FEV',
    '3': 'MAR',
    '4': 'ABR',
    '5': 'MAI',
    '6': 'JUN',
    '7': 'JUL',
    '8': 'AGO',
    '9': 'SET',
    '10': 'OUT',
    '11': 'NOV',
    '12': 'DEZ'
}
cores_risco = {
    'Muito Alto': '#E45756',
    'Alto': '#F58518',
    'Moderado': '#EECA3B',
    'Baixo': '#72B7B2',
    'Muito Baixo': '#4C78A8'
}
cores_segurado = {
    'Não Segurada': '#EECA3B',
    'Menos Sinistros que a Média': '#54A24B',
    'Mais Sinistros que a Média': '#E45756'
}
# cores_segurado = {
#     'Não Segurada': '#EECA3B',
#     'Não Apresenta Sinistro': '#54A24B',
#     'Apresenta Sinistro': '#E45756'
# }
cores_sinistralidade = {
    'Acima de 100%': '#ff0000',
    'De 80% e 100%': '#ff5232',
    'De 60% e 80%': '#ff7b5a',
    'De 40% e 60%': '#ff9e81',
    'De 20% a 40%': '#ffbfaa',
    'Abaixo de 20%': '#ffdfd4'
}
desastres = {
    'Hidrológico': ['Alagamentos', 'Chuvas Intensas', 'Enxurradas', 'Inundações', 'Movimento de Massa'],
    'Climatológico': ['Estiagem e Seca', 'Incêndio Florestal', 'Onda de Calor e Baixa Umidade', 'Onda de Frio'],
    'Meteorológico': ['Granizo', 'Onda de Frio', 'Tornado', 'Vendavais e Ciclones'],
    'Outros': ['Doenças infecciosas', 'Erosão', 'Onda de Calor e Baixa Umidade', 'Outros', 'Rompimento/Colapso de barragens']
}
idx_select = {
    'Climatológico': 0,
    'Hidrológico': 2,
    'Meteorológico': 3,
    'Outros': 1
}

idx_select_br = {
    'Climatológico': 0,
    'Hidrológico': 3,
    'Meteorológico': 3,
    'Outros': 1
}
seg = {
    'BRASILSEG COMPANHIA DE SEGUROS': 'Brasilseg', 
    'Mapfre Seguros Gerais S.A.': 'MAPFRE Seguros',
    'Essor Seguros S.A.': 'Essor Seguros',
    'Swiss Re Corporate Solutions Brasil S.A.': 'Swiss Re',
    'Nobre Seguradora do Brasil S.A': 'Nobre Seguradora',
    'Allianz Seguros S.A': 'Allianz Seguros',
    'Sancor Seguros do Brasil S.A.': 'Sancor Seguros',
    'FairFax Brasil Seguros Corporativos S/A': 'Fairfax Seguros',
    'Newe Seguros S.A': 'Newe Seguros',
    'Tokio Marine Seguradora S.A.': 'Tokio Marine Seguradora',
    'Porto Seguro Companhia de Seguros Gerais': 'Porto Seguro',
    'Too Seguros S.A.': 'Too Seguros',
    'Aliança do Brasil Seguros S/A.': 'Aliança do Brasil Seguros',
    'Sompo Seguros S/A': 'Sompo Seguros',
    'Companhia Excelsior de Seguros': 'Seguros Excelsior',
    'EZZE Seguros S.A.': 'EZZE Seguros',
    'Itaú XL Seguros Corporativos S.A': 'Itaú XL Seguros',
}

# COLUNAS
tabs = st.tabs(['UF do Brasil', 'Agro', 'América Latina', 'Créditos'])

with tabs[0]:
    secao1_uf = st.container()
    col_mapa1, col_dados1 = secao1_uf.columns([1, 1], gap='large')
    col_dados1.header('Parâmetros de Análise')
    # col_mapa, col_dados = st.columns([1, 1], gap='large')
    select1, select2 = col_dados1.columns([1, 1])



    # SELECTBOX
    uf_selectbox = select1.selectbox('Selecione o estado', list(estados.keys()), index=17)
    uf_selecionado = estados[uf_selectbox]
    grupo_desastre_selecionado = select2.selectbox('Selecione o grupo de desastre', ['Todos os Grupos de Desastre'] + list(desastres.keys()), index=0)
    # grupo_desastre_selecionado = select2.selectbox('Selecione o grupo de desastre', list(desastres.keys()), index=0)
    # ano_inicial, ano_final = col_dados.date_input('Selecione o Período a ser analisado', (date(1991, 1, 7), date(2022, 12, 30)), date(1991, 1, 7), date(2022, 12, 30), format="DD/MM/YYYY")
    ano_inicial, ano_final = col_dados1.select_slider('Selecione o Intervalo de Anos', anos, value=(anos[0], anos[-1]))



    # BUBBLE PLOT
    atlas_yearQ = dados_atlas.query("uf == @uf_selecionado & ano >= @ano_inicial & ano <= @ano_final")
    if grupo_desastre_selecionado != 'Todos os Grupos de Desastre':
        atlas_yearQ = atlas_yearQ.query("grupo_de_desastre == @grupo_desastre_selecionado")
    atlas_year = atlas_yearQ.groupby(['ano', 'descricao_tipologia'], as_index=False).size().rename(columns={'size': 'ocorrencias'})
    # atlas_year = dados_atlas.query("grupo_de_desastre == @grupo_desastre_selecionado & uf == @uf_selecionado & ano >= @ano_inicial & ano <= @ano_final").groupby(['ano', 'descricao_tipologia'], as_index=False).size().rename(columns={'size': 'ocorrencias'})



    fig_grupo_desastre = px.scatter(atlas_year, x="ano", y='descricao_tipologia', size='ocorrencias', 
        color='descricao_tipologia', size_max=50, color_discrete_map=mapa_de_cores,
        labels={
            "ano": "Ano", 
            "descricao_tipologia": "Desastre"
        }
    )
    fig_grupo_desastre.update_layout(showlegend=False, legend_orientation='h', margin={"r":0,"t":0,"l":0,"b":0})
    fig_grupo_desastre.update_xaxes(showgrid=True)
    # col_dados.caption('Quanto maior o círculo, maior o número de ocorrências do desastre')
    col_dados1.plotly_chart(fig_grupo_desastre)
    # col_dados.title(" ")


    secao2_uf = st.container()
    col_mapa2, col_dados2 = secao2_uf.columns([1, 1], gap='large')

    col_dados2.header('Refinar Parâmetros de Análise')

    # selecionando estado
    desastre_col, mun_col = col_dados2.columns([1, 1])

    disasters = desastres[grupo_desastre_selecionado] if grupo_desastre_selecionado != 'Todos os Grupos de Desastre' else dados_atlas.descricao_tipologia.unique().tolist()

    tipol_name = 'Todos os Desasastres' if grupo_desastre_selecionado == 'Todos os Grupos de Desastre' else f'Todos os Desastres ({grupo_desastre_selecionado})'
    tipologia_selecionada = desastre_col.selectbox('Selecione a tipologia do desastre', [tipol_name] + disasters, index=0, key='tipol')
    # tipologia_selecionada = desastre_col.selectbox('Selecione a tipologia do desastre', desastres[grupo_desastre_selecionado], index=idx_select[grupo_desastre_selecionado], key='tipol')
    coord_municipio = mun_col.selectbox('Encontrar município (zoom)',['-'] + dados_merge.iloc[:-45].query("abbrev_state == @uf_selecionado").name_muni.unique().tolist(), index=0)



    # MALHA
    malha_mun_estados = carrega_malha(uf=uf_selecionado)
    zoom_uf = 5
    if coord_municipio == '-':
        lat, lon = coord_uf.query("abbrev_state == @uf_selecionado")[['lat', 'lon']].values[0]
    else:
        cod_muni = dados_merge.loc[dados_merge.name_muni == coord_municipio, 'code_muni'].values[0]
        lat, lon = coord_muni.query("codarea == @cod_muni")[['lat', 'lon']].values[0]
        zoom_uf = 10



    # MAPA DE DESASTRES COMUNS
    tipol_com_muni = dados_atlas.query("uf == @uf_selecionado & ano >= @ano_inicial & ano <= @ano_final")
    if grupo_desastre_selecionado != 'Todos os Grupos de Desastre':
        tipol_com_muni = tipol_com_muni.query("grupo_de_desastre == @grupo_desastre_selecionado")

    tipologias_mais_comuns_por_muni = tipol_com_muni.groupby(['ibge', 'descricao_tipologia'], as_index=False).size().sort_values('size', ascending=False).drop_duplicates(subset='ibge', keep='first').rename(columns={'size': 'ocorrencias', 'descricao_tipologia': 'desastre_mais_comum'})
    # tipologias_mais_comuns_por_muni = dados_atlas.query("grupo_de_desastre == @grupo_desastre_selecionado & uf == @uf_selecionado & ano >= @ano_inicial & ano <= @ano_final").groupby(['ibge', 'descricao_tipologia'], as_index=False).size().sort_values('size', ascending=False).drop_duplicates(subset='ibge', keep='first').rename(columns={'size': 'ocorrencias', 'descricao_tipologia': 'desastre_mais_comum'})

    merge_muni_2 = dados_merge.query("abbrev_state == @uf_selecionado").groupby(['code_muni', 'name_muni'], as_index=False).size().drop('size', axis=1)
    tipol_merge = merge_muni_2.merge(tipologias_mais_comuns_por_muni, how='left', left_on='code_muni', right_on='ibge').drop('ibge', axis=1)
    tipol_merge.loc[np.isnan(tipol_merge["ocorrencias"]), 'ocorrencias'] = 0
    tipol_merge.desastre_mais_comum = tipol_merge.desastre_mais_comum.fillna('Sem Dados')
    col_mapa1.header(f'Desastre mais comum por Município')
    # col_mapa1.header(f'Desastre mais comum por Município ({ano_inicial} - {ano_final})')
    col_mapa1.plotly_chart(cria_mapa(tipol_merge, malha_mun_estados, locais='code_muni', cor='desastre_mais_comum', lista_cores=mapa_de_cores, nome_hover='name_muni', dados_hover=['desastre_mais_comum', 'ocorrencias'], zoom=zoom_uf, lat=lat, lon=lon, titulo_legenda='Desastre mais comum'), use_container_width=True)






    # QUERY
    dados_atlas_query = dados_atlas.query("uf == @uf_selecionado & ano >= @ano_inicial & ano <= @ano_final")
    # dados_atlas_query = dados_atlas.query("descricao_tipologia == @tipologia_selecionada & uf == @uf_selecionado & ano >= @ano_inicial & ano <= @ano_final")
    if grupo_desastre_selecionado != 'Todos os Grupos de Desastre':
        dados_atlas_query = dados_atlas_query.query("grupo_de_desastre == @grupo_desastre_selecionado")

    if tipologia_selecionada != tipol_name:
        dados_atlas_query = dados_atlas_query.query("descricao_tipologia == @tipologia_selecionada")

    # dados_atlas_query = dados_atlas.query("grupo_de_desastre == @grupo_desastre_selecionado & descricao_tipologia == @tipologia_selecionada & uf == @uf_selecionado & ano >= @ano_inicial & ano <= @ano_final")


    # MAPA RISCO
    ocorrencias = dados_atlas_query.groupby(['ibge', 'municipio'], as_index=False).size().rename(columns={'size': 'ocorrencias'}).sort_values('ocorrencias', ascending=False).drop_duplicates(subset='ibge', keep='first')
    merge_muni = dados_merge.query("abbrev_state == @uf_selecionado").groupby(['code_muni', 'name_muni', 'AREA_KM2'], as_index=False).size().drop('size', axis=1).drop_duplicates(subset='code_muni', keep='first')
    ocorrencias_merge = merge_muni.merge(ocorrencias, how='left', left_on='code_muni', right_on='ibge')
    ocorrencias_merge.loc[np.isnan(ocorrencias_merge["ocorrencias"]), 'ocorrencias'] = 0

    classificacao_ocorrencias = classifica_risco(ocorrencias_merge, 'ocorrencias')  # mudadr classficador
    fig_mapa = cria_mapa(classificacao_ocorrencias, malha_mun_estados, locais='code_muni', cor='risco', lista_cores=cores_risco, dados_hover='ocorrencias', nome_hover='name_muni', lat=lat, lon=lon, zoom=zoom_uf, titulo_legenda=f'Risco de {tipologia_selecionada}')
    # fig_mapa = cria_mapa(classificacao_ocorrencias, malha_mun_estados, locais='code_muni', cor='ocorrencias', tons=list(cores_risco.values()), dados_hover='ocorrencias', nome_hover='name_muni', lat=lat, lon=lon, zoom=5, titulo_legenda=f'Risco de {tipologia_selecionada}')
    # col_mapa.divider()
    # col_mapa.title(" ")
    # col_mapa.title(" ")
    col_mapa2.header(f'Risco de {tipologia_selecionada} ({ano_inicial} - {ano_final})')
    col_mapa2.plotly_chart(fig_mapa, use_container_width=True)



    # MÉTRICAS
    met1, met2 = col_dados2.columns([1, 1])
    met3, met4 = col_dados2.columns([1, 1])

    met1.metric('Total de Ocorrências', len(dados_atlas_query))
    med_anual = dados_atlas_query.groupby('ano').size().mean().astype(int) if dados_atlas_query.groupby('ano').size().any() else 0
    met2.metric('Média de Ocorrências por Ano', med_anual)
    muni_ocorr = math.ceil(len(classificacao_ocorrencias.query("ocorrencias > 0")) / len(classificacao_ocorrencias) * 100)
    met3.metric('% dos Municípios com no *mínimo* Uma Ocorrência', f'{muni_ocorr}%')
    area_risco = math.ceil(classificacao_ocorrencias.loc[classificacao_ocorrencias.query("risco == 'Muito Alto' | risco == 'Alto'").index, "AREA_KM2"].sum() / classificacao_ocorrencias.AREA_KM2.sum() * 100)
    met4.metric('% de Área Classificada como Risco *Alto* e *Muito Alto*', f'{area_risco}%')



    # DATAFRAME E DOWNLOAD
    tabela = ocorrencias.copy().reset_index(drop=True).sort_values('ocorrencias', ascending=False).rename(columns={'ibge': 'codigo_municipal'})
    tabela['ocorrencias_por_ano'] = tabela.ocorrencias / (ano_final - ano_inicial + 1)
    tabela_merge = tabela.merge(pop_pib, how='left', left_on='codigo_municipal', right_on='code_muni').drop('code_muni', axis=1)

    expander = col_dados2.expander(f'Municípios com o maior risco de *{tipologia_selecionada}* em {uf_selecionado}', expanded=True)
    expander.dataframe(tabela_merge.head(), hide_index=True,
                       column_config={
                            'codigo_municipal': None,
                            'municipio': st.column_config.TextColumn('Município'),
                            'ocorrencias': st.column_config.TextColumn('Total ocorrências'),
                            'pib_per_capita': st.column_config.NumberColumn(
                                'PIB per Capita',
                                format="R$ %.2f",
                            ),
                            'populacao': st.column_config.NumberColumn('Pop.', format='%d'),
                            'ocorrencias_por_ano': st.column_config.NumberColumn('Média ocorrências/ano', format='%.1f')
                        })
    
    col_dados2.download_button('Baixar tabela', tabela_merge.to_csv(sep=';', index=False), file_name=f'ocorrencias_{uf_selecionado}.csv', mime='text/csv', use_container_width=True)



    # LINEPLOT
    line_query = dados_atlas.iloc[:62273].query("uf == @uf_selecionado")
    if tipologia_selecionada != tipol_name:
        line_query = line_query.query("descricao_tipologia == @tipologia_selecionada")

    cols_danos = ['agricultura', 'pecuaria', 'industria']  # 'total_danos_materiais'
    soma_danos = line_query.groupby(['ano'], as_index=False)[cols_danos].sum()
    st.header(f'Danos causados por *{tipologia_selecionada}* em *{uf_selecionado} de 1991 a 2022*')

    fig_line = px.line(
        soma_danos, 'ano', cols_danos, markers=True, 
        labels={'value': 'Valor', 'variable': 'Setor', 'ano': 'Ano'}, 
        # line_shape='spline'
    )
    print(soma_danos.max())
    fig_line.update_layout(
    legend=dict(orientation="v",
        font=dict(size=16))
    )
    st.plotly_chart(fig_line, use_container_width=True)      



    # HEATMAPS
    # aba_hm1, aba_hm2 = st.tabs(['Ocorrências por Grupo de Desastre', 'Ocorrências por Estado'])
    cls_scales = {
        'Climatológico': 'OrRd',
        'Hidrológico': 'PuBu',
        'Meteorológico': 'Tempo',
        'Outros': 'Brwnyl'
    }

    # arrumar depois
    cor_hm = cls_scales[grupo_desastre_selecionado] if grupo_desastre_selecionado != 'Todos os Grupos de Desastre' else 'Greys'

    
    # with aba_hm1:
    #     heatmap_query2 = dados_atlas.iloc[:62273].query("grupo_de_desastre == @grupo_desastre_selecionado & uf == @uf_selecionado")
    #     pivot_hm2 = heatmap_query2.pivot_table(index='ano', columns='descricao_tipologia', aggfunc='size', fill_value=0)
    #     pivot_hm2 = pivot_hm2.reindex(index=anos, fill_value=0).transpose()
    #     fig_hm2 = px.imshow(
    #         pivot_hm2,
    #         labels=dict(x="Ano", y="Desastre", color="Total ocorrências"),
    #         x=pivot_hm2.columns,
    #         y=pivot_hm2.index,
    #         color_continuous_scale=cls_scales[grupo_desastre_selecionado],
    #     )
    #     fig_hm2.update_layout(
    #         yaxis_nticks=len(pivot_hm2),
    #     )
    #     st.subheader(f'Ocorrências do grupo de desastre *{grupo_desastre_selecionado} em {uf_selecionado}* de 1991 a 2022')
    #     st.plotly_chart(fig_hm2, use_container_width=True)

    # with aba_hm2:
    #     heatmap_query = dados_atlas.iloc[:62273].query("grupo_de_desastre == @grupo_desastre_selecionado & descricao_tipologia == @tipologia_selecionada")
    #     pivot_hm = heatmap_query.pivot_table(index='ano', columns='uf', aggfunc='size', fill_value=0)
    #     pivot_hm = pivot_hm.reindex(columns=dados_atlas.uf.unique()[:-1], fill_value=0)
    #     pivot_hm = pivot_hm.reindex(index=anos, fill_value=0).transpose()
    #     fig_hm = px.imshow(
    #         pivot_hm,
    #         labels=dict(x="Ano", y="Estado (UF)", color="Total ocorrências"),
    #         x=pivot_hm.columns,
    #         y=pivot_hm.index,
    #         color_continuous_scale=cor_hm,
    #     )
    #     fig_hm.update_layout(
    #         yaxis_nticks=len(pivot_hm),
    #         height=700
    #     )
    #     st.subheader(f'Ocorrências de *{tipologia_selecionada}* por estado de 1991 a 2022')
    #     st.plotly_chart(fig_hm, use_container_width=True)

    heatmap_query = dados_atlas.iloc[:62273]
    # heatmap_query = dados_atlas.iloc[:62273].query("descricao_tipologia == @tipologia_selecionada")
    if grupo_desastre_selecionado != 'Todos os Grupos de Desastre':
        heatmap_query = heatmap_query.query("grupo_de_desastre == @grupo_desastre_selecionado")

    if tipologia_selecionada != tipol_name:
        heatmap_query = heatmap_query.query("descricao_tipologia == @tipologia_selecionada")

    # heatmap_query = dados_atlas.iloc[:62273].query("grupo_de_desastre == @grupo_desastre_selecionado & descricao_tipologia == @tipologia_selecionada")
    pivot_hm = heatmap_query.pivot_table(index='ano', columns='uf', aggfunc='size', fill_value=0)
    pivot_hm = pivot_hm.reindex(columns=dados_atlas.uf.unique()[:-1], fill_value=0)
    pivot_hm = pivot_hm.reindex(index=anos, fill_value=0).transpose()
    fig_hm = px.imshow(
        pivot_hm,
        labels=dict(x="Ano", y="Estado (UF)", color="Total ocorrências"),
        x=pivot_hm.columns,
        y=pivot_hm.index,
        color_continuous_scale=cor_hm,
    )
    fig_hm.update_layout(
        yaxis_nticks=len(pivot_hm),
        height=700
    )
    st.header(f'Ocorrências de *{tipologia_selecionada}* por estado de 1991 a 2022')
    st.plotly_chart(fig_hm, use_container_width=True)



with tabs[1]:
    dados_susep = carrega_parquet('susep_agro2.parquet')
    psr = carrega_parquet('PSR_COMPLETO.parquet')
    psr.seguradora = psr.seguradora.map(seg)
    psr.pe_taxa = psr.pe_taxa * 100

    tipologias_psr = sorted(psr.descricao_tipologia.unique()[1:].tolist())

    secao1_agro = st.container()

    # COLUNAS
    col_mapa_agro1, col_metrics1 = secao1_agro.columns([1, 1], gap='large')
    col_metrics1.header('Parâmetros de Análise')
    form_agro = col_metrics1.form('form_agro', border=False, clear_on_submit=False)
    col_config1, col_config2, col_config3 = form_agro.columns([1, 1, 1])
    
    estado_psr = col_config1.selectbox('Estado', estados.keys(), index=17, key='uf_psr')
    uf_psr = estados[estado_psr]
    psrQ1 = psr.query("uf == @uf_psr")
    dt_inicial_psr, dt_final_psr = col_config2.date_input('Data das Apólices', (date(2021, 1, 1), date(2021, 12, 31)), date(2006, 1, 7), date(2021, 12, 31), format="DD/MM/YYYY")
    # ano_psr = col_config2.selectbox('Ano de Subscrição', sorted(psrQ1.ano.unique().tolist(), reverse=True), index=0, key='ano_psr')
    psrQ1 = psrQ1.query("data_apolice >= @dt_inicial_psr & data_apolice < @dt_final_psr")
    # psrQ1 = psrQ1.query("ano == @ano_psr")

    cultura_psr = col_config1.multiselect('Cultura Global', psrQ1.cultura.value_counts().index.tolist(), default=None, placeholder='Selecionar culturas', key='cultura_psr')
    # cultura_psr = col_config3.selectbox('Cultura Global', ['Todas as Culturas'] + sorted(psrQ1.cultura.unique().tolist()), index=0, key='cultura_psr')

    enviar_form_agro = form_agro.form_submit_button('Aplicar Parâmetros')
    
    # if cultura_psr != 'Todas as Culturas':
    if len(cultura_psr) > 0:
        psrQ3 = psrQ1.query("cultura.isin(@cultura_psr)")
        # print(f'CULTURA: {cultura_psr}')
    else:
        psrQ3 = psrQ1



    # METRICAS1
    lr = psrQ3.groupby(['uf'], as_index=False)[['valor_premio', 'valor_subvencao', 'valor_indenizacao']].sum()
    lr['loss_ratio'] = lr.valor_indenizacao / (lr.valor_premio + lr.valor_subvencao)

    # metrica_psr_uf1, metrica_psr_uf2 = col_metrics.columns([1, 1])
    col_config3.metric('Total de Apólices', psrQ3.num_apolice.nunique())
    # print(f'LEN APOL: {len(psrQ3.num_apolice)}')
    # col_config3.metric('Total de Apólices', len(psrQ3.num_apolice))
    # print(psrQ3.num_apolice.nunique())
    lr_metric = f'{lr.loss_ratio.multiply(100).astype(int).values[0]}%' if not psrQ3.empty else '0%'
    col_config3.metric(f'Índice de Sinistralidade', lr_metric)

    coord_psr = col_config2.selectbox('Encontrar município (zoom)',['-'] + dados_merge.iloc[:-45].query("abbrev_state == @uf_psr").name_muni.unique().tolist(), index=0, key='coord_psr')



    zoom_uf_psr = 6
    if coord_psr == '-':
        lat_psr, lon_psr = coord_uf.query("abbrev_state == @uf_psr")[['lat', 'lon']].values[0]
    else:
        cod_muni_psr = dados_merge.loc[dados_merge.name_muni == coord_psr, 'code_muni'].values[0]
        # print(cod_muni_psr)
        lat_psr, lon_psr = coord_muni.query("codarea == @cod_muni_psr")[['lat', 'lon']].values[0]
        # print(coord_muni.head())
        zoom_uf_psr = 10



    malha_psr = carrega_malha(uf=uf_psr)
    merge_muni_psr = dados_merge.iloc[:-45].query("abbrev_state == @uf_psr")

    # MAPA SINISTRALIDADE
    sin_muni = psrQ3.groupby(['ibge'], as_index=False)[['valor_premio', 'valor_subvencao', 'valor_indenizacao']].sum().copy()
    sin_muni['loss_ratio'] = (sin_muni.valor_indenizacao / (sin_muni.valor_premio + sin_muni.valor_subvencao)) * 100

    sin_muni_merge = merge_muni_psr.merge(sin_muni, how='left', left_on='code_muni', right_on='ibge')
    sin_muni_merge.loss_ratio = sin_muni_merge.loss_ratio.fillna(0)
    # sin_muni_merge.loss_ratio = sin_muni_merge.loss_ratio.fillna(1e-6)
    sin_muni_merge.ibge = sin_muni_merge.ibge.fillna('-')
    # sin_muni_lr = classifica_lossratio(sin_muni_merge)

    fig_sinistralidade_muni = cria_mapa(sin_muni_merge, malha_psr, locais='code_muni', cor='loss_ratio', tons='Reds', min_max=[0, 120], dados_hover='loss_ratio', nome_hover='name_muni', lat=lat_psr, lon=lon_psr, zoom=zoom_uf_psr, titulo_legenda=f'Índice de Sinistralidade (%)')
    # fig_sinistralidade_muni = cria_mapa(sin_muni_lr, malha_psr, locais='code_muni', cor='classe_sinistralidade', lista_cores=cores_sinistralidade, dados_hover='loss_ratio', nome_hover='name_muni', lat=lat_psr, lon=lon_psr, zoom=zoom_uf_psr, titulo_legenda=f'Índice de Sinistralidade')

    fig_sinistralidade_muni.update_coloraxes(colorbar=dict(title='Índice de Sinistralidade (%)', tickvals=[0, 20, 40, 60, 80, 100], ticktext=['0', '20', '40', '60', '80', '100+'], orientation='h', yanchor='top', y=0.0))

    col_mapa_agro1.header(f'Índice de Sinistralidade por Município')
    col_mapa_agro1.plotly_chart(fig_sinistralidade_muni, use_container_width=True)



    fig_bar = sp.make_subplots(specs=[[{"secondary_y": True}]])

    bar_data = psrQ3.groupby(['ano', psrQ1.data_apolice.dt.month]).num_apolice.nunique()
    bar_data = bar_data.reset_index(level=['data_apolice', 'ano'])
    bar_data.data_apolice = bar_data.data_apolice.astype(str).map(meses)
    bar_data.ano = bar_data.ano.astype(str)
    bar_data['Mês'] = bar_data[['data_apolice', 'ano']].agg('-'.join, axis=1)
    bar_data = bar_data.drop(['ano', 'data_apolice'], axis=1)

    # bar_data = psrQ3.groupby(psrQ3.data_apolice.dt.month, as_index=False).num_apolice.nunique().rename(columns={'num_apolice': 'Apólices'})
    # print(bar_data.head())
    # bar_data = bar_data.set_index(['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'])
    fig_bar.add_trace(
        px.bar(bar_data, x='Mês', y='num_apolice', labels={'num_apolice': 'Apólices'}).data[0],
        secondary_y=False,
    )
    # fig_bar.add_trace(
    #     px.bar(bar_data, x=bar_data.index, y='Apólices', labels={'index': 'Mês', 'Apólices': 'Apólices'}).data[0],
    #     secondary_y=False,
    # )

    line_data = psrQ3.groupby(['ano', psrQ1.data_apolice.dt.month])[['valor_premio', 'valor_subvencao', 'valor_indenizacao']].sum().copy()
    line_data = line_data.reset_index(level=['data_apolice', 'ano'])
    line_data.data_apolice = line_data.data_apolice.astype(str).map(meses)
    line_data.ano = line_data.ano.astype(str)
    line_data['Mês'] = line_data[['data_apolice', 'ano']].agg('-'.join, axis=1)
    line_data = line_data.drop(['ano', 'data_apolice'], axis=1)
    # line_data = psrQ3.groupby(psrQ3.data_apolice.dt.month, as_index=False)[['valor_premio', 'valor_subvencao', 'valor_indenizacao']].sum().copy()
    line_data['loss_ratio'] = (line_data.valor_indenizacao / (line_data.valor_premio + line_data.valor_subvencao)) * 100
    fig_bar.add_trace(
        # go.Line(x=[2, 3, 4], y=[4, 5, 6], name="yaxis2 data"),
        px.line(line_data, x='Mês', y='loss_ratio', labels={'loss_ratio': 'Índice de Sinistralidade (%)'}, color_discrete_sequence=['#ff0000'], markers=True).data[0],
        secondary_y=True
    )
    # fig_bar.add_trace(
    #     # go.Line(x=[2, 3, 4], y=[4, 5, 6], name="yaxis2 data"),
    #     px.line(line_data, x=line_data.index, y='loss_ratio', labels={'index': 'Mês', 'loss_ratio': 'Índice de Sinistralidade (%)'}, color_discrete_sequence=['#ff0000'], markers=True).data[0],
    #     secondary_y=True
    # )

    fig_bar.update_layout(
        title_text="Número de Apólices Contratas e Índice de Sinistralidade por Mês",
        # xaxis = dict(
        #     tickmode = 'array',
        #     tickvals = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        #     ticktext = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
        # )
    )

    # Set x-axis title
    fig_bar.update_xaxes(title_text="Mês")

    # Set y-axes titles
    fig_bar.update_yaxes(title_text="Número de Apólices", secondary_y=False)
    fig_bar.update_yaxes(title_text="Índice de Sinistralidade (%)", secondary_y=True, minor=dict(dtick=1))

    col_metrics1.plotly_chart(fig_bar)
    col_metrics1.caption("Os meses que não aparecem no gráfico acima não possuem apólices subscritas ou sinistros reportados.")



    # # BUBBLE PLOT
    # psr_year = psr.query("uf == @uf_psr")
    # psr_year_grouped = psr_year.drop(psr_year.query("descricao_tipologia == '-'").index).groupby(['ano', 'descricao_tipologia'], as_index=False).size().rename(columns={'size': 'ocorrencias'})
    # # print(psr_year_grouped.head())



    # fig_psr_year = px.scatter(psr_year_grouped, x="ano", y='descricao_tipologia', size='ocorrencias', 
    #     color='descricao_tipologia', size_max=50, color_discrete_map=mapa_de_cores,
    #     labels={
    #         "ano": "Ano de Subscrição", 
    #         "descricao_tipologia": "Evento Climático"
    #     }
    # )
    # fig_psr_year.update_layout(showlegend=False, legend_orientation='h', margin={"r":0,"t":0,"l":0,"b":0})
    # fig_psr_year.update_xaxes(showgrid=True)
    # # col_metrics.caption('Sinistros por evento climático ao longo dos anos.')
    # col_metrics.plotly_chart(fig_psr_year)
    # col_metrics.text(" ")
    # col_metrics.text(" ")

    susepQ = dados_susep.query("uf == @uf_psr & data >= @dt_inicial_psr & data < @dt_final_psr")
    top_seguradoras = susepQ.groupby(['seguradora'], as_index=False)['premio_dir'].sum().sort_values('premio_dir', ascending=False).seguradora.tolist()
    


    secao2_agro = st.container()
    col_mapa_agro2, col_metrics2 = secao2_agro.columns([1, 1], gap='large')

    col_metrics2.header(f'Sinistros e Reportes de Desastres em {meses[str(dt_inicial_psr.month)]} {dt_inicial_psr.year} - {meses[str(dt_final_psr.month)]} {dt_final_psr.year}')
    # col_metrics2.header(f'Sinistros e Reportes de Desastres em {ano_psr}')
    tipologia_selecionada_psr = col_metrics2.selectbox('Evento Climático', ['Todos os Eventos'] + tipologias_psr, index=0, key='tipol_psr')



    # QUERIES
    psrQ2 = psrQ1.query("descricao_tipologia != '-'")
    if tipologia_selecionada_psr != 'Todos os Eventos':
        psrQ2 = psrQ1.query("descricao_tipologia == @tipologia_selecionada_psr")

    if len(cultura_psr) > 0:
        psrQ2_2 = psrQ2.query("cultura.isin(@cultura_psr)")
    else:
        psrQ2_2 = psrQ2

    # else:
    #     psrQ2 = psrQ1.query("descricao_tipologia != '-'")



    # AREA SEGURADA
    sin = psrQ2_2.groupby(['ibge'], as_index=False).size()
    sin_merge = merge_muni_psr.merge(sin, how='left', left_on='code_muni', right_on='ibge').rename(columns={'size': 'sinistros'})
    sin_merge.sinistros = sin_merge.sinistros.fillna(0)
    sin_merge.ibge = sin_merge.ibge.fillna('-')
    sin_quant = int(sin_merge['sinistros'].mean()) if len(sin) > 0 else 0
    munis_sinistrados = sin_merge.query("sinistros > @sin_quant").ibge
    # print(sin_quant)
    sin_segurado = classifica_segurado(sin_merge, merge_muni_psr.code_muni, psrQ1.ibge, munis_sinistrados)
    # sin_segurado = classifica_segurado(sin_merge, merge_muni_psr.code_muni, psrQ1.ibge, psrQ2.ibge)

    sin_fig = cria_mapa(sin_segurado, malha_psr, locais='code_muni', cor='seg', lista_cores=cores_segurado, dados_hover='sinistros', nome_hover='name_muni', lat=lat_psr, lon=lon_psr, zoom=zoom_uf_psr, titulo_legenda=f'Classificação da Área')

    col_mapa_agro2.header(f'Mapa de Áreas Seguradas ({tipologia_selecionada_psr})')
    col_mapa_agro2.plotly_chart(sin_fig, use_container_width=True)



    # # SINISTRO COMUM
    # psrQ1_2 = psrQ1.drop(psrQ1.query("descricao_tipologia == '-'").index)
    # sin_comum = psrQ1_2.groupby(['ibge', 'descricao_tipologia'], as_index=False).size().sort_values('size', ascending=False).drop_duplicates(subset='ibge', keep='first').rename(columns={'size': 'ocorrencias', 'descricao_tipologia': 'evento_mais_comum'})
    # sin_comum_merge = merge_muni_psr.merge(sin_comum, how='left', left_on='code_muni', right_on='ibge')
    # sin_comum_merge.loc[np.isnan(sin_comum_merge["ocorrencias"]), 'ocorrencias'] = 0
    # sin_comum_merge.evento_mais_comum = sin_comum_merge.evento_mais_comum.fillna('Sem Dados')

    # # col_mapa.subheader(f'Desastre mais comum por Município ({ano_inicial} - {ano_final})')
    # col_mapa_agro.subheader(f'Evento com mais Chamadas de Sinistro por Município ({uf_psr} - {ano_psr})')
    # col_mapa_agro.plotly_chart(cria_mapa(sin_comum_merge, malha_psr, locais='code_muni', cor='evento_mais_comum', lista_cores=mapa_de_cores, nome_hover='name_muni', dados_hover=['evento_mais_comum', 'ocorrencias'], zoom=zoom_uf_psr, lat=lat_psr, lon=lon_psr, titulo_legenda='Evento mais comum'), use_container_width=True)



    atlas_psr = dados_atlas.query("uf == @uf_psr & data >= @dt_inicial_psr & data < @dt_final_psr")
    # atlas_psr = dados_atlas.query("uf == @uf_psr & ano == @ano_psr")
    if tipologia_selecionada_psr != 'Todos os Eventos':
        atlas_psr = atlas_psr.query("descricao_tipologia == @tipologia_selecionada_psr")

    # METRICAS2
    col_metrics_col1, col_metrics_col2 = col_metrics2.columns([1, 1])
    col_metrics_col1.metric(f'Ocorrências Reportadas de {tipologia_selecionada_psr}', len(atlas_psr))
    col_metrics_col2.metric(f'Sinistros de {tipologia_selecionada_psr}', len(psrQ2_2))



    # PIE CHART
    col_metrics2.write(f'**Representatividade dos Eventos Climáticos no Total Indenizado ({uf_psr} - {meses[str(dt_inicial_psr.month)]} {dt_inicial_psr.year} a {meses[str(dt_final_psr.month)]} {dt_final_psr.year})**')
    # col_metrics2.write(f'**Representatividade dos Eventos Climáticos no Total Indenizado ({uf_psr} - {ano_psr})**')
    psrPie = psrQ3.drop(psrQ3.query("descricao_tipologia == '-'").index).groupby('descricao_tipologia')['valor_indenizacao'].sum()
    figpie = px.pie(
        psrPie,
        values='valor_indenizacao',
        names=psrPie.index,
        #title=f'Representatividade dos Eventos Climáticos no Total Indenizado ({uf_psr} - {ano_psr})'
    )
    figpie.update_layout(
        legend=dict(font=dict(size=16)),
        legend_title=dict(font=dict(size=14), text='Evento Climático')
    )
    col_metrics2.plotly_chart(figpie, use_container_width=True)



    # secao_susep = st.container()
    # col_susep1, col_susep2 = secao_susep.columns([1, 1])

    # col_susep1.header('Análise Gráfica dos Valores Financeiros')
    # col_susep2.header('Métricas Financeiras')

    # col_susep1.caption('Dados da Superintendência de Seguros Privados (SUSEP).')

    # form_susep = col_susep2.form('form_susep', border=False, clear_on_submit=False)
    # form_susep.caption('As seguradoras estão listadas abaixo por ordem decrescente de prêmios diretos. Se nenhuma seguradora for selecionada, todas serão consideradas.')

    # susep_seg = form_susep.multiselect('Seguradoras', top_seguradoras, default=None, placeholder='Selecionar seguradoras', key='seguradora_psr')
    # enviar_form_susep = form_susep.form_submit_button('Selecionar Seguradoras')

    # if len(susep_seg) > 0:
    #     susepQ2 = susepQ.query("seguradora.isin(@susep_seg)")
    # else:
    #     susepQ2 = susepQ



    # susep_met_1, susep_met_2 = col_susep2.columns([1, 1])
    # susep_met_1.metric('Prêmios Diretos', number_to_human(susepQ2.premio_dir.sum()))
    # susep_met_2.metric('Sinistro Diretos', number_to_human(susepQ2.sin_dir.sum()))
    # susep_met_1.metric('Prêmios Retidos', number_to_human(susepQ2.premio_ret.sum()))
    # susep_met_2.metric('Prêmios Retidos (Líquido)', number_to_human(susepQ2.prem_ret_liq.sum()))
    # susep_met_1.metric('Salvados de Sinistros', number_to_human(susepQ2.salvados.sum()))
    # susep_met_2.metric('Recuperações', number_to_human(susepQ2.recuperacao.sum()))

    # susep_tab1, susep_tab2 = col_susep1.tabs(['Prêmios e Sinsitros', 'Ramos do Seguro Rural'])

    # bar_susep = susepQ2.groupby([susepQ2.data.dt.year, susepQ2.data.dt.month], as_index=True)[['premio_dir', 'sin_dir']].sum()
    # bar_susep = bar_susep.reset_index(level=0).rename(columns={'data': 'Ano'})
    # bar_susep = bar_susep.reset_index(level=0).rename(columns={'data': 'Mês'})
    # bar_susep.Mês = bar_susep.Mês.astype(str).map(meses)
    # bar_susep.Ano = bar_susep.Ano.astype(str)
    # bar_susep['Período'] = bar_susep[['Mês', 'Ano']].agg('-'.join, axis=1)
    # bar_susep = bar_susep.drop(['Mês', 'Ano'], axis=1)
    # bar_susep = bar_susep.rename(columns={'premio_dir': 'Prêmios Diretos', 'sin_dir': 'Sinistros Diretos'})
    # susepBar = px.bar(bar_susep, x='Período', y=['Prêmios Diretos', 'Sinistros Diretos'], barmode='group', labels={'value': 'Valor', 'variable': 'Tipo', 'Período': 'Período'})

    # susep_tab1.write(f'**Prêmios e Sinistros diretos ({meses[str(dt_inicial_psr.month)]} {dt_inicial_psr.year} a {meses[str(dt_final_psr.month)]} {dt_final_psr.year})**')
    # susep_tab1.plotly_chart(susepBar, use_container_width=True)
    

    # susep_cols = {
    #     'premio_dir': 'Prêmios Diretos',
    #     'premio_ret': 'Prêmios Retidos',
    #     'prem_ret_liq': 'Prêmios Retidos (Líquido)',
    #     'sin_dir': 'Sinistros Diretos',
    #     'salvados': 'Salvados',
    #     'recuperacao': 'Recuperações'
    # }
    # inv_susep_cols = {v: k for k, v in susep_cols.items()}
    # met_selecionada = susep_tab2.selectbox('Métrica', list(susep_cols.values()))

    # susep_tab2.write(f'**Representatividade dos Tipos de Seguro no valor dos {met_selecionada} ({meses[str(dt_inicial_psr.month)]} {dt_inicial_psr.year} a {meses[str(dt_final_psr.month)]} {dt_final_psr.year})**')

    # susepPie = susepQ2.groupby(['ramo'])[inv_susep_cols[met_selecionada]].sum()
    # susepPie = px.pie(
    #     susepPie,
    #     values=inv_susep_cols[met_selecionada],
    #     names=susepPie.index
    # )
    # susepPie.update_layout(
    #     legend=dict(font=dict(size=16)),
    #     legend_title=dict(font=dict(size=14), text='Tipo de Seguro')
    # )
    # susep_tab2.plotly_chart(susepPie, use_container_width=True)

   

    # DATAFRAME
    if len(psrQ2_2) > 0:

        # print(f'psrQ2_2:\n{psrQ2_2.head()}')
        psrG_muni = psrQ2_2.groupby('municipio').agg({
            'descricao_tipologia': 'count',
            # 'NM_CULTURA_GLOBAL': lambda x: x.mode().iloc[0],
            'pe_taxa': 'mean',
            'prod_segurada': 'mean',
            'seguradora': lambda x: x.mode().iloc[0],
        }).reset_index()
        # print(f'psrG_muni:\n{psrG_muni.head()}')

        psrApol_muni = psrQ2_2.groupby(['municipio'], as_index=False).size().merge(psrQ1.groupby(['municipio'], as_index=False)['num_apolice'].nunique(), how='left', on='municipio')
        psrG_muni['apolices'] = psrApol_muni['num_apolice']
        psrG_muni['sin/apol'] = (psrApol_muni['size'] / psrApol_muni['num_apolice'])

        psrG_muni = psrQ2_2.groupby(['municipio', 'cultura'], as_index=False)['area_total'].sum().sort_values('area_total', ascending=False).drop_duplicates('municipio', keep='first').merge(psrG_muni, how='right', on='municipio').drop('area_total', axis=1)

        col_order = ['municipio', 'cultura', 'apolices', 'descricao_tipologia', 'sin/apol', 'pe_taxa', 'prod_segurada', 'seguradora']
        tabela_cols = {
            'Média Taxa de Prêmio': 'pe_taxa',
            'Total Sinistros': 'descricao_tipologia',
            'Total Apólices': 'apolices',
            'Média de Sinistros por Apólice': 'sin/apol',
            'Média Prod. Segurada': 'prod_segurada'
        }

        # st.divider()
        tit_tabela, tabela_ordem = st.columns([4, 1])
        ordem_tabela1 = tabela_ordem.selectbox('Ordenar por', ['Média Taxa de Prêmio', 'Total Sinistros', 'Total Apólices', 'Média de Sinistros por Apólice', 'Média Prod. Segurada'], index=0, key='ordem_psr')
        ordem_tabela2 = tabela_cols[ordem_tabela1]
        tit_tabela.header(f'Dados dos Municípios com Sinistros de {tipologia_selecionada_psr} ({meses[str(dt_inicial_psr.month)]} {dt_inicial_psr.year} - {meses[str(dt_final_psr.month)]} {dt_final_psr.year})')
        # tit_tabela.header(f'Dados dos Municípios com Sinistros de {tipologia_selecionada_psr} ({ano_psr})')
        st.dataframe(
            psrG_muni[col_order].sort_values(ordem_tabela2, ascending=False),
            hide_index=True, 
            column_config={
                'municipio': st.column_config.TextColumn('Município'),
                'descricao_tipologia': st.column_config.TextColumn('Total Sinistros'),
                'apolices': st.column_config.TextColumn('Total Apólices'),
                'cultura': st.column_config.TextColumn('Cultura mais Comum'),
                'seguradora': st.column_config.TextColumn('Seguradora mais Comum'),
                'prod_segurada': st.column_config.NumberColumn(
                    'Média Prod. Segurada (kg/ha)',
                    format="%.2f",
                ),
                'pe_taxa': st.column_config.NumberColumn(
                    'Média Taxa de Prêmio',
                    format="%.2f%%",
                ),
                'sin/apol': st.column_config.NumberColumn(
                    'Média de Sinistros por Apólice',
                    format="%.2f",
                )
            },
            height=400,
            use_container_width=True
        )
        st.download_button('Baixar tabela', psrG_muni.to_csv(sep=',', index=False), file_name=f'psr_{uf_psr}_{meses[str(dt_inicial_psr.month)]}{dt_inicial_psr.year}-{meses[str(dt_final_psr.month)]}{dt_final_psr.year}.csv', use_container_width=True)
        # st.download_button('Baixar tabela', psrG_muni.to_csv(sep=',', index=False), file_name=f'psr_{uf_psr}_{ano_psr}.csv', use_container_width=True)



    # HEATMAP
    st.title(" ")
    st.title(" ")

    tabs_psr = st.tabs(['Sinistros por Evento Climático', 'Sinistros por Estado'])
    hm_query_psr = psr.drop(psr.query("descricao_tipologia == '-'").index)
    if tipologia_selecionada_psr != 'Todos os Eventos':
        hm_query_psr = psr.query("descricao_tipologia == @tipologia_selecionada_psr")

    with tabs_psr[0]:
        hm_query_psr_1 = psr.drop(psr.query("descricao_tipologia == '-'").index).query("uf == @uf_selecionado")
        pivot_hm1_psr = hm_query_psr_1.pivot_table(index='ano', columns='descricao_tipologia', aggfunc='size', fill_value=0)
        pivot_hm1_psr = pivot_hm1_psr.reindex(index=anos_psr, fill_value=0).transpose()
        fig_hm1_psr = px.imshow(
            pivot_hm1_psr,
            labels=dict(x="Ano", y="Evento Climático", color="Sinistros"),
            x=pivot_hm1_psr.columns,
            y=pivot_hm1_psr.index,
            color_continuous_scale='Greys',
        )
        fig_hm1_psr.update_layout(
            yaxis_nticks=len(pivot_hm1_psr),
        )
        st.header(f'Número de Sinistros por Evento Climático de 2006 a 2021')
        st.plotly_chart(fig_hm1_psr, use_container_width=True)


    with tabs_psr[1]:
        pivot_hm_psr = hm_query_psr.pivot_table(index='ano', columns='uf', aggfunc='size', fill_value=0)
        # pivot_hm_psr = pivot_hm_psr.reindex(columns=psr.uf.unique(), fill_value=0)
        pivot_hm_psr = pivot_hm_psr.reindex(index=anos_psr, fill_value=0).transpose()
        fig_hm_psr = px.imshow(
            pivot_hm_psr,
            labels=dict(x="Ano", y="Estado (UF)", color="Total de Sinistro"),
            x=pivot_hm_psr.columns,
            y=pivot_hm_psr.index,
            color_continuous_scale='Greys',
        )
        fig_hm_psr.update_layout(
            yaxis_nticks=len(pivot_hm_psr),
            height=700
        )
        st.header(f'Sinistros de *{tipologia_selecionada_psr}* por estado de 2006 a 2021')
        st.caption('Apenas os estados com pelo menos um sinistro serão exibidos')
        st.plotly_chart(fig_hm_psr, use_container_width=True)



    secao_susep = st.container()
    col_susep1, col_susep2 = secao_susep.columns([1, 1])

    col_susep1.header('Análise Gráfica dos Valores Financeiros')
    col_susep2.header('Métricas Financeiras')

    col_susep1.caption('Dados da Superintendência de Seguros Privados (SUSEP).')

    form_susep = col_susep2.form('form_susep', border=False, clear_on_submit=False)
    form_susep.caption('As seguradoras estão listadas abaixo por ordem decrescente de prêmios diretos. Se nenhuma seguradora for selecionada, todas serão consideradas.')

    susep_seg = form_susep.multiselect('Seguradoras', top_seguradoras, default=None, placeholder='Selecionar seguradoras', key='seguradora_psr')
    enviar_form_susep = form_susep.form_submit_button('Selecionar Seguradoras')

    if len(susep_seg) > 0:
        susepQ2 = susepQ.query("seguradora.isin(@susep_seg)")
    else:
        susepQ2 = susepQ



    susep_met_1, susep_met_2 = col_susep2.columns([1, 1])
    susep_met_1.metric('Prêmios Diretos', number_to_human(susepQ2.premio_dir.sum()))
    susep_met_2.metric('Sinistro Diretos', number_to_human(susepQ2.sin_dir.sum()))
    susep_met_1.metric('Prêmios Retidos', number_to_human(susepQ2.premio_ret.sum()))
    susep_met_2.metric('Prêmios Retidos (Líquido)', number_to_human(susepQ2.prem_ret_liq.sum()))
    susep_met_1.metric('Salvados de Sinistros', number_to_human(susepQ2.salvados.sum()))
    susep_met_2.metric('Recuperações', number_to_human(susepQ2.recuperacao.sum()))

    susep_tab1, susep_tab2 = col_susep1.tabs(['Prêmios e Sinsitros', 'Ramos do Seguro Rural'])

    bar_susep = susepQ2.groupby([susepQ2.data.dt.year, susepQ2.data.dt.month], as_index=True)[['premio_dir', 'sin_dir']].sum()
    bar_susep = bar_susep.reset_index(level=0).rename(columns={'data': 'Ano'})
    bar_susep = bar_susep.reset_index(level=0).rename(columns={'data': 'Mês'})
    bar_susep.Mês = bar_susep.Mês.astype(str).map(meses)
    bar_susep.Ano = bar_susep.Ano.astype(str)
    bar_susep['Período'] = bar_susep[['Mês', 'Ano']].agg('-'.join, axis=1)
    bar_susep = bar_susep.drop(['Mês', 'Ano'], axis=1)
    bar_susep = bar_susep.rename(columns={'premio_dir': 'Prêmios Diretos', 'sin_dir': 'Sinistros Diretos'})
    susepBar = px.bar(bar_susep, x='Período', y=['Prêmios Diretos', 'Sinistros Diretos'], barmode='group', labels={'value': 'Valor', 'variable': 'Tipo', 'Período': 'Período'})

    susep_tab1.write(f'**Prêmios e Sinistros diretos ({meses[str(dt_inicial_psr.month)]} {dt_inicial_psr.year} a {meses[str(dt_final_psr.month)]} {dt_final_psr.year})**')
    susep_tab1.plotly_chart(susepBar, use_container_width=True)
    

    susep_cols = {
        'premio_dir': 'Prêmios Diretos',
        'premio_ret': 'Prêmios Retidos',
        'prem_ret_liq': 'Prêmios Retidos (Líquido)',
        'sin_dir': 'Sinistros Diretos',
        'salvados': 'Salvados',
        'recuperacao': 'Recuperações'
    }
    inv_susep_cols = {v: k for k, v in susep_cols.items()}
    met_selecionada = susep_tab2.selectbox('Métrica', list(susep_cols.values()))

    susep_tab2.write(f'**Representatividade dos Tipos de Seguro no valor dos {met_selecionada} ({meses[str(dt_inicial_psr.month)]} {dt_inicial_psr.year} a {meses[str(dt_final_psr.month)]} {dt_final_psr.year})**')

    susepPie = susepQ2.groupby(['ramo'])[inv_susep_cols[met_selecionada]].sum()
    susepPie = px.pie(
        susepPie,
        values=inv_susep_cols[met_selecionada],
        names=susepPie.index
    )
    susepPie.update_layout(
        legend=dict(font=dict(size=16)),
        legend_title=dict(font=dict(size=14), text='Tipo de Seguro')
    )
    susep_tab2.plotly_chart(susepPie, use_container_width=True)



with tabs[2]:
    pop_pib_uf = carrega_parquet('pop_pib_latam.parquet')
    malha_america = carrega_geojson('malha_latam.json')
    malha_brasil = carrega_geojson('malha_brasileira.json')
    coord_latam = carrega_parquet('coord_latam3.parquet')

    secao1_latam = st.container()
    col_mapa_br1, col_dados_br1 = secao1_latam.columns([1, 1], gap='large')
    col_dados_br1.header('Parâmetros de Análise')

    # SELECTBOX
    grupo_desastre_selecionado_br = col_dados_br1.selectbox('Selecione o grupo de desastre', list(desastres.keys()), index=0, key='gp_desastre_br')
    ano_inicial_br, ano_final_br = col_dados_br1.select_slider('Selecione o Intervalo de Anos', anos_latam, value=(anos_latam[0], anos_latam[-1]), key='periodo_br')



    # QUERY
    dados_atlas_query_br_1 = dados_atlas.query("grupo_de_desastre == @grupo_desastre_selecionado_br & ano >= @ano_inicial_br & ano <= @ano_final_br")
    


    # BUBBLE PLOT
    atlas_year_br = dados_atlas_query_br_1.groupby(['ano', 'descricao_tipologia'], as_index=False).size().rename(columns={'size': 'ocorrencias'})



    fig_grupo_desastre_br = px.scatter(atlas_year_br, x="ano", y='descricao_tipologia', size='ocorrencias', 
        color='descricao_tipologia', size_max=50, color_discrete_map=mapa_de_cores,
        labels={
            "ano": "Ano", 
            "descricao_tipologia": "Desastre"
        }
    )
    fig_grupo_desastre_br.update_layout(showlegend=False, legend_orientation='h', margin={"r":0,"t":0,"l":0,"b":0})
    fig_grupo_desastre_br.update_xaxes(showgrid=True)
    # col_dados_br.caption('Quanto maior o círculo, maior o número de ocorrências do desastre')
    col_dados_br1.plotly_chart(fig_grupo_desastre_br)



    secao2_latam = st.container()
    col_mapa_br2, col_dados_br2 = secao2_latam.columns([1, 1], gap='large')
    col_dados_br2.header('Refinar Parâmetros')



    # selecionando estado
    col_pais, col_desastre = col_dados_br2.columns([1, 1])

    pais_selecionado = col_pais.selectbox('Selecione o país', sorted(dados_merge.iloc[-45:].name_state.unique()), index=7, key='pais_br')
    iso = dados_merge.loc[dados_merge.name_state == pais_selecionado, 'code_state'].values[0]
    malha_pais_selecionado = malha_brasil if iso == 'BRA' else filtra_geojson(malha_america, iso)
    
    tipologia_selecionada_br = col_desastre.selectbox('Selecione a tipologia do desastre', desastres[grupo_desastre_selecionado_br], index=idx_select_br[grupo_desastre_selecionado_br], key='tipol_br')



    # MAPA DE DESASTRES COMUNS
    tipologias_mais_comuns_por_estado = dados_atlas_query_br_1.groupby(['pais', 'descricao_tipologia'], as_index=False).size().sort_values('size', ascending=False).drop_duplicates(subset='pais', keep='first').rename(columns={'size': 'ocorrencias', 'descricao_tipologia': 'desastre_mais_comum'})
    tipol_br = dados_merge.groupby(['code_state', 'name_state'], as_index=False).size().drop('size', axis=1)
    tipol_merge_br = tipol_br.merge(tipologias_mais_comuns_por_estado, how='left', left_on='name_state', right_on='pais').drop('pais', axis=1)
    tipol_merge_br.loc[np.isnan(tipol_merge_br['ocorrencias']), 'ocorrencias'] = 0
    tipol_merge_br.desastre_mais_comum = tipol_merge_br.desastre_mais_comum.fillna('Sem Dados')
    col_mapa_br1.header(f'Desastre mais comum por País')
    # col_mapa_br1.header(f'Desastres mais comuns por País ({ano_inicial_br} - {ano_final_br})')
    col_mapa_br1.plotly_chart(cria_mapa(tipol_merge_br, malha_america, locais='code_state', cor='desastre_mais_comum', lista_cores=mapa_de_cores, nome_hover='name_state', dados_hover=['desastre_mais_comum', 'ocorrencias'], zoom=1, titulo_legenda='Desastre mais comum'), use_container_width=True)



    # QUERY
    dados_atlas_query_br_2 = dados_atlas_query_br_1.query("descricao_tipologia == @tipologia_selecionada_br")



    # MAPA RISCO
    # col_mapa_br.divider()  
    col_mapa_br2.header(f'{pais_selecionado}: Risco de {tipologia_selecionada_br} ({ano_inicial_br} - {ano_final_br})')

    ocorrencias_br = dados_atlas_query_br_2.groupby(['cod_uf', 'pais'], as_index=False).size().rename(columns={'size': 'ocorrencias'})

    merge_ufs = dados_merge.iloc[:-45].groupby(['code_state', 'name_state'], as_index=False).size().drop('size', axis=1)
    merge_paises = dados_merge.iloc[-45:].drop(['code_muni', 'name_muni'], axis=1)
    merge_escolhido = merge_ufs if iso == 'BRA' else merge_paises
    ocorrencias_merge_br = merge_escolhido.merge(ocorrencias_br, how='left', left_on='code_state', right_on='cod_uf')
    ocorrencias_merge_br.loc[np.isnan(ocorrencias_merge_br["ocorrencias"]), 'ocorrencias'] = 0
    classificacao_ocorrencias_br = classifica_risco(ocorrencias_merge_br, 'ocorrencias')

    fig_mapa_br = cria_mapa(classificacao_ocorrencias_br, malha_pais_selecionado, locais='code_state', cor='risco', lista_cores=cores_risco, dados_hover='ocorrencias', nome_hover='name_state', titulo_legenda=f'Risco de {tipologia_selecionada_br}', zoom=1, featureid='properties.codarea')

    coord_pais = coord_latam.query("cod_uf == @iso & ano >= @ano_inicial_br & ano <= @ano_final_br & descricao_tipologia == @tipologia_selecionada_br")

    # if iso != 'BRA':
    #     fig_mapa_br.add_trace(
    #         px.scatter_mapbox(
    #             lat=coord_pais['latitude'],
    #             lon=coord_pais['longitude'],
    #             hover_name=coord_pais['local']
    #         ).data[0]
    #     )
    #     fig_mapa_br.update_traces(marker=dict(size=12, color='#222A2A'), selector=dict(mode='markers'))

    col_mapa_br2.plotly_chart(fig_mapa_br, use_container_width=True)



    # DADOS
    dados_tabela = dados_atlas_query_br_1.query("descricao_tipologia == @tipologia_selecionada_br").groupby(['pais'], as_index=False).size().rename(columns={'size': 'ocorrencias'})
    tabela_br = dados_tabela.copy().reset_index(drop=True).sort_values('ocorrencias', ascending=False)
    tabela_br['ocorrencias_por_ano'] = round(tabela_br.ocorrencias.div(ano_final_br - ano_inicial_br + 1), 1)
  
    tabela_merge_br = tabela_br.merge(pop_pib_uf, how='right', left_on='pais', right_on='pais')
    tabela_merge_br.loc[np.isnan(tabela_merge_br["ocorrencias"]), 'ocorrencias'] = 0
    tabela_merge_br.loc[np.isnan(tabela_merge_br["ocorrencias_por_ano"]), 'ocorrencias_por_ano'] = 0.0
    tabela_merge_br = tabela_merge_br.sort_values('ocorrencias', ascending=False)
    tabela_merge_br.loc[tabela_merge_br.query("cod_uf == 'VEN'").index, 'pais'] = 'Venezuela'



    # MÉTRICAS
    met1_br, met2_br = col_dados_br2.columns([1, 1])
    met1_br.metric('Total de ocorrências', tabela_merge_br.query("pais == @pais_selecionado")['ocorrencias'])
    met2_br.metric('Média de ocorrências por ano', tabela_merge_br.query("pais == @pais_selecionado")['ocorrencias_por_ano'])

    

    # DATAFRAME E DOWNLOAD
    expander_br = col_dados_br2.expander(f'Países com o maior risco de *{tipologia_selecionada_br}* na América Latina', expanded=True)
    expander_br.dataframe(tabela_merge_br.drop('cod_uf', axis=1).head(), hide_index=True, 
                          column_config={
                            'pais': st.column_config.TextColumn('País'),
                            'ocorrencias': st.column_config.TextColumn('Total ocorrências'),
                            'pib_per_capita': st.column_config.NumberColumn(
                                'PIB per Capita',
                                format="R$ %.2f",
                            ),
                            'populacao': st.column_config.NumberColumn('Pop.', format='%d'),
                            'ocorrencias_por_ano': st.column_config.NumberColumn('Média ocorrências/ano', format='%.1f')
                        })

    col_dados_br2.download_button('Baixar tabela', tabela_merge_br.to_csv(sep=';', index=False), file_name=f'{tipologia_selecionada_br.replace(" ", "_").lower()}_americalatina.csv', mime='text/csv', use_container_width=True)



    
    heatmap_query_br = dados_atlas.iloc[62273:].query("descricao_tipologia == @tipologia_selecionada_br & ano >= 2000")
    pivot_hm_br = heatmap_query_br.pivot_table(index='ano', columns='pais', aggfunc='size', fill_value=0)
    # pivot_hm_br = pivot_hm_br.reindex(columns=dados_atlas.pais.unique(), fill_value=0)
    pivot_hm_br = pivot_hm_br.reindex(index=anos_latam, fill_value=0).transpose()
    # print(pivot_hm_br.head())
    fig_hm_br = px.imshow(
        pivot_hm_br,
        labels=dict(x="Ano", y="País", color="Total ocorrências"),
        x=pivot_hm_br.columns,
        y=pivot_hm_br.index,
        color_continuous_scale=cls_scales[grupo_desastre_selecionado_br],
    )
    fig_hm_br.update_layout(
        yaxis_nticks=len(pivot_hm_br),
        height=700
    )
    st.header(f'Ocorrências de *{tipologia_selecionada_br}* por País de 2000 a 2023')
    st.caption('Países sem ocorrências não aparecem no gráfico')
    st.plotly_chart(fig_hm_br, use_container_width=True)

    # aba_hm1_br, aba_hm2_br = st.tabs(['Ocorrências por Grupo de Desastre', 'Ocorrências por País'])
    # with aba_hm2_br:
    #     heatmap_query_br = dados_atlas.iloc[62273:].query("descricao_tipologia == @tipologia_selecionada & ano >= 2000")
    #     pivot_hm_br = heatmap_query_br.pivot_table(index='ano', columns='pais', aggfunc='size', fill_value=0)
    #     # pivot_hm_br = pivot_hm_br.reindex(columns=dados_atlas.pais.unique(), fill_value=0)
    #     pivot_hm_br = pivot_hm_br.reindex(index=anos_latam, fill_value=0).transpose()
    #     fig_hm_br = px.imshow(
    #         pivot_hm_br,
    #         labels=dict(x="Ano", y="País", color="Total ocorrências"),
    #         x=pivot_hm_br.columns,
    #         y=pivot_hm_br.index,
    #         color_continuous_scale=cls_scales[grupo_desastre_selecionado_br],
    #     )
    #     fig_hm_br.update_layout(
    #         yaxis_nticks=len(pivot_hm_br),
    #         height=700
    #     )
    #     st.subheader(f'Ocorrências de *{tipologia_selecionada_br}* por País de 2000 a 2023')
    #     st.caption('Países sem ocorrências não aparecem no gráfico')
    #     st.plotly_chart(fig_hm_br, use_container_width=True)
    # with aba_hm1_br:
 
    #     heatmap_query2_br = dados_atlas.query("grupo_de_desastre == @grupo_desastre_selecionado & pais == @pais_selecionado & ano >= 2000")
    #     pivot_hm2_br = heatmap_query2_br.pivot_table(index='ano', columns='descricao_tipologia', aggfunc='size', fill_value=0)
    #     pivot_hm2_br = pivot_hm2_br.reindex(index=anos_latam, fill_value=0).transpose()
    #     fig_hm2_br = px.imshow(
    #         pivot_hm2_br,
    #         labels=dict(x="Ano", y="Desastre", color="Total ocorrências"),
    #         x=pivot_hm2_br.columns,
    #         y=pivot_hm2_br.index,
    #         color_continuous_scale=cls_scales[grupo_desastre_selecionado_br],
    #     )
    #     fig_hm2_br.update_layout(
    #         yaxis_nticks=len(pivot_hm2_br),
    #     )
    #     st.subheader(f'{pais_selecionado}: Ocorrências do grupo de desastre *{grupo_desastre_selecionado_br}* de 2000 a 2023')
    #     st.plotly_chart(fig_hm2_br, use_container_width=True)


# with tabs[3]:
#     secao1_clima = st.container()
#     secao1_clima.header('Em desenvolvimento...')
#     # secao1_clima.image("sant'ana.jpeg", use_column_width=True)


with tabs[-1]:
    col_creditos1, col_creditos2 = st.columns([1, 1], gap='large')

    col_creditos1.subheader('Founded by [IRB(Re)](https://www.irbre.com/)')
    col_creditos1.caption('A leading figure in the Brazilian reinsurance market, with over 80 years of experience and a complete portfolio of solutions for the market.')
    col_creditos1.image('irb.jpg', use_column_width=True)

    col_creditos2.subheader('Developed by Instituto de Riscos Climáticos')
    col_creditos2.markdown('''
    **Supervisors:** Carlos Teixeira, Reinaldo Marques & Roberto Westenberger

    **Researchers:** Luiz Otávio & Karoline Branco

    **Data Scientists:**  Lucas Lima & Paulo Cesar
                        
    **Risk Scientists:** Ana Victoria & Beatriz Pimenta
                        
    #### Source
    - **Atlas Digital de Desastres no Brasil** - [www.atlasdigital.mdr.gov.br/](http://atlasdigital.mdr.gov.br/).
    - **EM-DAT, CRED / UCLouvain, 2024, Brussels, Belgium** – [www.emdat.be](https://www.emdat.be/).
    - **SES - Sistema de Estatística da SUSEP** - [https://www2.susep.gov.br/menuestatistica/SES/principal.aspx](https://www2.susep.gov.br/menuestatistica/SES/principal.aspx)
    - **Sistema de Subvenção Econômica ao Prêmio do Seguro Rural** - SISSER - Portal de Dados Abertos do Ministério da Agricultura e Pecuária - [dados.agricultura.gov.br/dataset/sisser3](https://dados.agricultura.gov.br/dataset/sisser3).
    ''')