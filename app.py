import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

# Configuración de la página
st.set_page_config(layout="wide", page_title="Mapa de Clientes - Rostock Argentina")

# URL base del repositorio en GitHub
BASE_URL = "https://raw.githubusercontent.com/Brunomperetti/Rostock/master/"

# Función para cargar archivos Excel desde GitHub
def cargar_archivo_github(archivo):
    url = f"{BASE_URL}{archivo}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return pd.read_excel(BytesIO(response.content))
        else:
            st.error(f"Error al cargar {archivo}: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error al descargar {archivo}: {e}")
        return None

# Carga de datos
with st.spinner("Cargando datos..."):
    df_clientes = cargar_archivo_github("clientes_activos_geocodificados.xlsx")
    df_potenciales = cargar_archivo_github("Cliente_Campaña_listo_normalizado.xlsx")
    df_base_fria = cargar_archivo_github("base_fria_geocodificado.xlsx")

    if df_clientes is None or df_potenciales is None or df_base_fria is None:
        st.error("Error al cargar los datos necesarios")
        st.stop()

    # Combinar potenciales
    potenciales = pd.concat([df_potenciales, df_base_fria], ignore_index=True)
    
    # Asignar tipos
    df_clientes['Tipo'] = 'Cliente'
    potenciales['Tipo'] = 'Potencial'
    
    # Unificar datos
    datos = pd.concat([df_clientes, potenciales], ignore_index=True)
    
    # Limpieza básica de provincias
    datos['Provincia'] = datos['Provincia'].str.upper().str.strip()
    datos['Provincia'] = datos['Provincia'].replace(
        ['CAPITAL FEDERAL', 'CIUDAD DE BUENOS AIRES', 'CABA'], 'BUENOS AIRES')

# Filtro por provincia
provincias = sorted(datos['Provincia'].dropna().unique())
provincia_seleccionada = st.sidebar.selectbox(
    "Seleccionar Provincia:", 
    ['Todas'] + provincias,
    index=0
)

if provincia_seleccionada != 'Todas':
    datos = datos[datos['Provincia'] == provincia_seleccionada]

# Crear mapa centrado en Argentina
m = folium.Map(
    location=[-38.4161, -63.6167],  # Coordenadas de Argentina
    zoom_start=5 if provincia_seleccionada == 'Todas' else 8,
    tiles='CartoDB positron',
    control_scale=True
)

# Capa de clientes
icon_url = "https://raw.githubusercontent.com/Brunomperetti/Rostock/master/icono.jpg"
rostock_icon = folium.CustomIcon(icon_image=icon_url, icon_size=(30, 30))

clientes_layer = MarkerCluster(name='🟢 Clientes').add_to(m)
for _, row in datos[datos['Tipo'] == 'Cliente'].iterrows():
    if pd.notna(row['lat']) and pd.notna(row['lon']):
        popup = f"""
        <b>✅ Cliente:</b> {row.get('Nombre fantasía', row.get('Nombre', 'N/A'))}<br>
        <b>Localidad:</b> {row.get('Localidad', 'N/A')}<br>
        <b>Provincia:</b> {row.get('Provincia', 'N/A')}
        """
        folium.Marker(
            [row['lat'], row['lon']],
            popup=popup,
            icon=rostock_icon
        ).add_to(clientes_layer)

# Capa de potenciales
potenciales_layer = MarkerCluster(name='🔴 Potenciales').add_to(m)
for _, row in datos[datos['Tipo'] == 'Potencial'].iterrows():
    if pd.notna(row['lat']) and pd.notna(row['lon']):
        popup = f"""
        <b>🔴 Potencial:</b> {row.get('Nombre fantasía', row.get('Nombre', 'N/A'))}<br>
        <b>Localidad:</b> {row.get('Localidad', 'N/A')}<br>
        <b>Provincia:</b> {row.get('Provincia', 'N/A')}<br>
        <b>Teléfono:</b> {row.get('Telefono', row.get('Teléfono', 'N/A'))}
        """
        folium.CircleMarker(
            [row['lat'], row['lon']],
            radius=6,
            popup=popup,
            color='red',
            fill=True,
            fill_color='red'
        ).add_to(potenciales_layer)

# Control de capas
folium.LayerControl().add_to(m)

# Mostrar el mapa
st.title("🌍 Mapa de Clientes y Potenciales - Argentina")
st.markdown(f"### {'Provincia: ' + provincia_seleccionada if provincia_seleccionada != 'Todas' else 'Todas las provincias'}")

# Estadísticas rápidas
col1, col2 = st.columns(2)
col1.metric("Clientes Activos", datos[datos['Tipo'] == 'Cliente'].shape[0])
col2.metric("Potenciales", datos[datos['Tipo'] == 'Potencial'].shape[0])

# Mostrar mapa
st_folium(m, width=1200, height=700)

# Mostrar datos debajo del mapa
with st.expander("📊 Ver datos detallados"):
    st.dataframe(datos[['Nombre fantasía', 'Nombre', 'Localidad', 'Provincia', 'Tipo']])


