import streamlit as st
import pandas as pd
import pygsheets

crendenciais = pygsheets.authorize(service_file='./controle-luvas.json')

filePath = "https://docs.google.com/spreadsheets/d/1dP5615dw8FXX6QDHOYZr6hYTw6qmU90GwJAnpeOGU_I/"

file = crendenciais.open_by_url(filePath)
sheet = file.worksheet_by_title("2025")
data = sheet.get_all_values()
df = pd.DataFrame(data)

st.title("Controle de Luvas")
st.write("Sistema para controle de estoque de luvas.")
st.write(df)