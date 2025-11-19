import streamlit as st
import pandas as pd
import pygsheets
import json

# Lê o bloco [gcp_service_account] do secrets.toml
service_account_info = st.secrets["gcp_service_account"]

# Converte o dict em JSON string
service_account_json = json.dumps(dict(service_account_info))

# Autoriza o pygsheets usando o JSON em memória
crendenciais = pygsheets.authorize(service_account_json=service_account_json)

filePath = "https://docs.google.com/spreadsheets/d/1dP5615dw8FXX6QDHOYZr6hYTw6qmU90GwJAnpeOGU_I/"

file = crendenciais.open_by_url(filePath)
sheet = file.worksheet_by_title("2025")
data = sheet.get_all_values()

# Se a primeira linha é cabeçalho, isso aqui já melhora o DF:
df = pd.DataFrame(data[1:], columns=data[0])

st.title("Controle de Luvas")
st.write("Sistema para controle de estoque de luvas.")
st.write(df)
