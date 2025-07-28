import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium
import plotly.express as px

# Configuración de la página
st.set_page_config(layout="wide", page_title="Rostock - Visualización Argentina")

# URL base del repositorio en GitHub
BASE_URL = "https://raw.githubusercontent.com/Brunomperetti/Rostock/master/"

# Función para cargar archivos
def cargar_archivo_github(archivo):
    url = f"{BASE_URL}{archivo}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return pd.read_excel(BytesIO(response.content))
        else:
            st.error(f"Error al cargar {archivo}")
            return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None

# Carga de datos
with st.spinner("Cargando datos..."):
    df_clientes = cargar_archivo_github("clientes_activos_geocodificados.xlsx")
    df_potenciales = cargar_archivo_github("Cliente_Campaña_listo_normalizado.xlsx")
    df_base_fria = cargar_archivo_github("base_fria_geocodificado.xlsx")

    if df_clientes is None or df_potenciales is None or df_base_fria is None:
        st.error("Error crítico: No se pudieron cargar los archivos base")
        st.stop()

    # Procesamiento unificado
    df_clientes['Tipo'] = 'Cliente'
    potenciales = pd.concat([df_potenciales, df_base_fria], ignore_index=True)
    potenciales['Tipo'] = 'Potencial'
    datos = pd.concat([df_clientes, potenciales], ignore_index=True)
    
    # Normalización de provincias
    datos['Provincia'] = datos['Provincia'].str.upper().str.strip()
    datos['Provincia'] = datos['Provincia'].replace(
        ['CAPITAL FEDERAL', 'CIUDAD DE BUENOS AIRES', 'CABA'], 'BUENOS AIRES')

    # Manejo seguro de columnas de dirección y teléfono
    datos['Dirección'] = datos['Dirección'].fillna('') if 'Dirección' in datos.columns else datos.get('Direccion', pd.Series('', index=datos.index))
    datos['Telefono'] = datos['Telefono'].fillna('') if 'Telefono' in datos.columns else datos.get('Teléfono', pd.Series('', index=datos.index))

# Filtro por provincia
provincias = ['Todas'] + sorted(datos['Provincia'].dropna().unique())
provincia_seleccionada = st.sidebar.selectbox("Provincia:", provincias)

if provincia_seleccionada != 'Todas':
    datos = datos[datos['Provincia'] == provincia_seleccionada]

# Sidebar para selección de vista
vista = st.sidebar.radio(
    "Vista:",
    ["🗺️ Mapa", "🔥 Mapa de Calor", "📊 Gráficos", "📈 KPIs"],
    index=0
)

# Función para crear popups detallados
def crear_popup(row):
    return f"""
    <div style="font-family: Arial; max-width: 300px;">
        <h4 style="margin-bottom: 5px; color: {'#2ecc71' if row['Tipo'] == 'Cliente' else '#e74c3c'}">
            {'✅ ' if row['Tipo'] == 'Cliente' else '🔴 '}{row['Nombre']}
        </h4>
        <p style="margin: 2px 0;"><b>Tipo:</b> {row['Tipo']}</p>
        <p style="margin: 2px 0;"><b>Provincia:</b> {row.get('Provincia', 'N/A')}</p>
        <p style="margin: 2px 0;"><b>Localidad:</b> {row.get('Localidad', 'N/A')}</p>
        <p style="margin: 2px 0;"><b>Dirección:</b> {row.get('Dirección', 'N/A')}</p>
        <p style="margin: 2px 0;"><b>Teléfono:</b> {row.get('Telefono', 'N/A')}</p>
    </div>
    """

# ========== VISTA DE MAPA ==========
if vista == "🗺️ Mapa":
    st.title("Mapa de Clientes y Potenciales - Argentina")
    
    m = folium.Map(
        location=[-38.4161, -63.6167], 
        zoom_start=5 if provincia_seleccionada == 'Todas' else 7,
        tiles='CartoDB positron'
    )
    
    # Icono personalizado
    icon_url = f"{BASE_URL}icono.jpg"
    rostock_icon = folium.CustomIcon(icon_image=icon_url, icon_size=(30, 30))
    
    # Capas
    cluster_clientes = MarkerCluster(name='Clientes').add_to(m)
    cluster_potenciales = MarkerCluster(name='Potenciales').add_to(m)
    
    # Marcadores clientes
    for _, row in datos[datos['Tipo'] == 'Cliente'].iterrows():
        if pd.notna(row['lat']) and pd.notna(row['lon']):
            folium.Marker(
                [row['lat'], row['lon']],
                popup=folium.Popup(crear_popup(row), max_width=300),
                icon=rostock_icon
            ).add_to(cluster_clientes)
    
    # Marcadores potenciales
    for _, row in datos[datos['Tipo'] == 'Potencial'].iterrows():
        if pd.notna(row['lat']) and pd.notna(row['lon']):
            folium.CircleMarker(
                [row['lat'], row['lon']],
                radius=6,
                popup=folium.Popup(crear_popup(row), max_width=300),
                color='red',
                fill=True,
                fill_color='red'
            ).add_to(cluster_potenciales)
    
    folium.LayerControl().add_to(m)
    st_folium(m, width=1200, height=700)

# ========== VISTA DE MAPA DE CALOR ==========
elif vista == "🔥 Mapa de Calor":
    st.title("Mapa de Calor - Argentina")
    
    m_heat = folium.Map(
        location=[-38.4161, -63.6167],
        zoom_start=5 if provincia_seleccionada == 'Todas' else 7,
        tiles='CartoDB positron'
    )
    
    # Heatmap clientes
    if not datos[datos['Tipo'] == 'Cliente'][['lat', 'lon']].empty:
        HeatMap(
            datos[datos['Tipo'] == 'Cliente'][['lat', 'lon']].dropna().values,
            name='Clientes',
            radius=15,
            gradient={0.4: 'lime', 0.6: 'green', 1: 'darkgreen'}
        ).add_to(m_heat)
    
    # Heatmap potenciales
    if not datos[datos['Tipo'] == 'Potencial'][['lat', 'lon']].empty:
        HeatMap(
            datos[datos['Tipo'] == 'Potencial'][['lat', 'lon']].dropna().values,
            name='Potenciales',
            radius=15,
            gradient={0.4: 'orange', 0.6: 'red', 1: 'darkred'}
        ).add_to(m_heat)
    
    folium.LayerControl().add_to(m_heat)
    st_folium(m_heat, width=1200, height=700)

# ========== VISTA DE GRÁFICOS ==========
elif vista == "📊 Gráficos":
    st.title("Análisis Comparativo - Argentina")
    
    # Gráfico por provincia
    st.subheader("Distribución por Provincia")
    try:
        fig_prov = px.bar(
            datos.groupby(['Provincia', 'Tipo']).size().reset_index(name='Cantidad'),
            x='Provincia',
            y='Cantidad',
            color='Tipo',
            barmode='group',
            color_discrete_map={'Cliente': '#2ecc71', 'Potencial': '#e74c3c'}
        )
        st.plotly_chart(fig_prov, use_container_width=True)
    except Exception as e:
        st.error(f"No se pudo generar el gráfico: {str(e)}")
    
    # Gráfico de torta
    st.subheader("Proporción Total")
    try:
        fig_torta = px.pie(
            datos['Tipo'].value_counts().reset_index(),
            names='Tipo',
            values='count',
            color='Tipo',
            color_discrete_map={'Cliente': '#2ecc71', 'Potencial': '#e74c3c'}
        )
        st.plotly_chart(fig_torta, use_container_width=True)
    except Exception as e:
        st.error(f"No se pudo generar el gráfico: {str(e)}")

# ========== VISTA DE KPIs ==========
elif vista == "📈 KPIs":
    st.title("Indicadores Clave - Argentina")
    
    # Métricas básicas
    try:
        total_clientes = datos[datos['Tipo'] == 'Cliente'].shape[0]
        total_potenciales = datos[datos['Tipo'] == 'Potencial'].shape[0]
        
        cols = st.columns(3)
        cols[0].metric("Clientes", total_clientes)
        cols[1].metric("Potenciales", total_potenciales)
        cols[2].metric("Ratio", 
                      f"{total_clientes/(total_clientes+total_potenciales)*100:.1f}%" 
                      if (total_clientes+total_potenciales) > 0 else "0%")
    except Exception as e:
        st.error(f"Error calculando métricas: {str(e)}")
    
    # Resumen por provincia
    st.subheader("Resumen por Provincia")
    try:
        resumen = datos.pivot_table(index='Provincia', columns='Tipo', aggfunc='size', fill_value=0)
        resumen['Total'] = resumen.sum(axis=1)
        if 'Cliente' in resumen.columns:
            resumen['% Clientes'] = (resumen['Cliente'] / resumen['Total'] * 100).round(1)
        st.dataframe(resumen.sort_values('Total', ascending=False))
    except Exception as e:
        st.error(f"No se pudo generar el resumen: {str(e)}")
    
    # Tabla completa con todos los datos
    st.subheader("Datos Completos")
    try:
        columnas_a_mostrar = ['Nombre', 'Provincia', 'Localidad', 'Dirección', 'Telefono', 'Tipo']
        columnas_disponibles = [col for col in columnas_a_mostrar if col in datos.columns]
        st.dataframe(datos[columnas_disponibles].sort_values('Provincia'))
    except Exception as e:
        st.error(f"No se pudo mostrar la tabla completa: {str(e)}")
