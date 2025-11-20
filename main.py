import streamlit as st
import pandas as pd
import pygsheets
import json
from collections import Counter

# --- Credenciais via secrets ---
service_account_info = dict(st.secrets["gcp_service_account"])
service_account_json = json.dumps(service_account_info)
crendenciais = pygsheets.authorize(service_account_json=service_account_json)

# --- Ler planilha ---
filePath = "https://docs.google.com/spreadsheets/d/1dP5615dw8FXX6QDHOYZr6hYTw6qmU90GwJAnpeOGU_I/"
file = crendenciais.open_by_url(filePath)
sheet = file.worksheet_by_title("2025")
data = sheet.get_all_values()

header = data[0]
rows = data[1:]

# --- Normalizar cabeçalho (tirar vazios e duplicados) ---
counter = Counter()
new_header = []

for name in header:
    name = name.strip()

    # se estiver vazio, dá um nome genérico
    if name == "":
        name = "Coluna_vazia"

    # garantir unicidade
    counter[name] += 1
    if counter[name] > 1:
        name = f"{name}_{counter[name]}"

    new_header.append(name)

df = pd.DataFrame(rows, columns=new_header)

# Opcional: remover colunas completamente vazias
df = df.loc[:, (df != "").any(axis=0)]

# --- App ---
st.title("Controle de Luvas")
st.write("Sistema para controle de estoque de luvas.")
st.dataframe(df)
