import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap
from fuzzywuzzy import process
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px

sns.set(style="whitegrid")
st.set_page_config(layout="wide")
st.title("📊 Dashboard Clientes Rostock")
st.markdown("Visualización y análisis de clientes actuales 🟢 y potenciales 🔴.")

# ====== CARGA DE DATOS CON SPINNER ======
with st.spinner("Cargando datos..."):
    clientes_actuales = pd.read_excel('clientes_activos_geocodificados.xlsx')
    camiones = pd.read_excel('lista_pesada.xlsx')
    clientes_campañas = pd.read_excel('Cliente_Campaña_listo_normalizado.xlsx')
    base_fria = pd.read_excel('base_fria_geocodificado.xlsx')

    potenciales = pd.concat([camiones, clientes_campañas, base_fria], ignore_index=True)

    clientes_actuales['Tipo'] = 'Cliente'
    potenciales['Tipo'] = 'Potencial'

    for col in ['Provincia', 'Localidad']:
        clientes_actuales[col] = clientes_actuales[col].str.upper().str.strip()
        potenciales[col] = potenciales[col].str.upper().str.strip()

    bases_unidas = pd.concat([clientes_actuales, potenciales], ignore_index=True)

    # === Fuzzy solo una vez ===
    def normalizar_columna_fuzzy(columna, umbral=90):
        unicos = columna.dropna().unique()
        unificados = {}
        for val in unicos:
            match, score = process.extractOne(val, unificados.keys()) if unificados else (None, 0)
            if score >= umbral:
                unificados[val] = match
            else:
                unificados[val] = val
        return columna.map(unificados)

    if 'Provincia_norm' not in st.session_state:
        with st.spinner("Normalizando provincias y localidades..."):
            bases_unidas['Provincia'] = normalizar_columna_fuzzy(bases_unidas['Provincia'])
            bases_unidas['Localidad'] = normalizar_columna_fuzzy(bases_unidas['Localidad'])
            st.session_state['Provincia_norm'] = bases_unidas['Provincia']
            st.session_state['Localidad_norm'] = bases_unidas['Localidad']
    else:
        bases_unidas['Provincia'] = st.session_state['Provincia_norm']
        bases_unidas['Localidad'] = st.session_state['Localidad_norm']

    clientes_actuales = bases_unidas[bases_unidas['Tipo'] == 'Cliente']
    potenciales = bases_unidas[bases_unidas['Tipo'] == 'Potencial']

# ====== UI ======
opciones = ["Mapa", "Mapa de calor", "Gráficos comparativos", "KPIs resumen"]
seleccion = st.sidebar.radio("Seleccioná la vista", opciones)

# ====== MAPA ======
if seleccion == "Mapa":
    with st.spinner("Cargando mapa..."):
        st.subheader("🗺️ Mapa de Clientes y Potenciales")
        m = folium.Map(location=[-38.4161, -63.6167], zoom_start=5, tiles='CartoDB positron')
        rostock_icon = folium.CustomIcon(icon_image='icono.jpg', icon_size=(30, 30))
        cluster_clientes = MarkerCluster(name='🟢 Clientes').add_to(m)
        cluster_potenciales = MarkerCluster(name='🔴 Potenciales').add_to(m)

        for _, row in clientes_actuales.iterrows():
            if pd.notna(row['lat']) and pd.notna(row['lon']):
                popup_info = f"✅ Cliente: {row.get('Nombre fantasía', 'Sin nombre')}<br>{row['Localidad']}, {row['Provincia']}"
                folium.Marker(location=[row['lat'], row['lon']], popup=popup_info, icon=rostock_icon).add_to(cluster_clientes)

        for _, row in potenciales.iterrows():
            if pd.notna(row['lat']) and pd.notna(row['lon']):
                nombre = row.get('Nombre fantasía') or row.get('Nombre') or 'Sin nombre'
                telefono = row.get('Telefono') or 'Sin teléfono'
                popup_info = f"🔴 Potencial: {nombre}<br>{row['Localidad']}, {row['Provincia']}<br>📞 {telefono}"
                folium.CircleMarker(location=[row['lat'], row['lon']], radius=6, popup=popup_info,
                                    color='red', fill=True, fill_color='red').add_to(cluster_potenciales)

        st_folium(m, width=800, height=600)

# ====== HEATMAP ======
elif seleccion == "Mapa de calor":
    with st.spinner("Generando mapa de calor..."):
        st.subheader("🔥 Mapa de Calor de Clientes y Potenciales")
        m_heat = folium.Map(location=[-38.4161, -63.6167], zoom_start=5, tiles='CartoDB positron')
        HeatMap(clientes_actuales[['lat', 'lon']].dropna().values.tolist(),
                name='🟢 Clientes', radius=10,
                gradient={0.4: 'lime', 0.65: 'green', 1: 'darkgreen'}).add_to(m_heat)
        HeatMap(potenciales[['lat', 'lon']].dropna().values.tolist(),
                name='🔴 Potenciales', radius=10,
                gradient={0.4: 'orange', 0.65: 'red', 1: 'darkred'}).add_to(m_heat)
        folium.LayerControl().add_to(m_heat)
        st_folium(m_heat, width=800, height=600)

# ====== GRÁFICOS COMPARATIVOS ======
elif seleccion == "Gráficos comparativos":
    with st.expander("📈 Ver gráficos comparativos", expanded=True):
        st.markdown("### Clientes vs Potenciales por Provincia")
        prov_counts = bases_unidas.groupby(['Provincia', 'Tipo']).size().reset_index(name='Cantidad')
        fig = px.bar(prov_counts, x='Cantidad', y='Provincia', color='Tipo', orientation='h', barmode='group',
                     color_discrete_map={'Cliente': '#2ecc71', 'Potencial': '#e74c3c'}, height=600)
        fig.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Top 10 Localidades con más Clientes y Potenciales")
        loc_counts = bases_unidas.groupby(['Localidad', 'Tipo']).size().reset_index(name='Cantidad')
        top_localidades = loc_counts.groupby('Localidad')['Cantidad'].sum().nlargest(10).index
        loc_counts_top = loc_counts[loc_counts['Localidad'].isin(top_localidades)]
        fig2 = px.bar(loc_counts_top, x='Cantidad', y='Localidad', color='Tipo', orientation='h', barmode='group',
                      color_discrete_map={'Cliente': '#2ecc71', 'Potencial': '#e74c3c'}, height=600)
        fig2.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("### Proporción Global de Clientes y Potenciales")
        tipo_counts = bases_unidas['Tipo'].value_counts().reset_index()
        tipo_counts.columns = ['Tipo', 'Cantidad']
        fig3 = px.pie(tipo_counts, names='Tipo', values='Cantidad',
                      color='Tipo',
                      color_discrete_map={'Cliente': '#2ecc71', 'Potencial': '#e74c3c'},
                      hole=0.4)
        fig3.update_traces(textinfo='percent+label')
        st.plotly_chart(fig3, use_container_width=True)

# ====== KPIs RESUMEN ======
elif seleccion == "KPIs resumen":
    with st.expander("📋 Ver KPIs resumen", expanded=True):
        total_clientes = clientes_actuales.shape[0]
        total_potenciales = potenciales.shape[0]
        total_general = bases_unidas.shape[0]
        porcentaje_clientes = (total_clientes / total_general) * 100 if total_general > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🟢 Clientes Actuales", total_clientes)
        col2.metric("🔴 Potenciales", total_potenciales)
        col3.metric("📊 Total General", total_general)
        col4.metric("✅ % Clientes", f"{porcentaje_clientes:.2f}%")

        st.markdown("### Clientes y Potenciales por Provincia (Tabla con semáforo)")
        resumen_prov = bases_unidas.groupby(['Provincia', 'Tipo']).size().unstack(fill_value=0)
        resumen_prov['Total'] = resumen_prov.sum(axis=1)
        resumen_prov['% Clientes'] = (resumen_prov['Cliente'] / resumen_prov['Total'] * 100).round(2)

        def color_fila(valor):
            if valor >= 70:
                return 'background-color: #b6fcb6'
            elif valor >= 40:
                return 'background-color: #fff3b0'
            else:
                return 'background-color: #fcb6b6'

        styled_table = resumen_prov.style.applymap(color_fila, subset=['% Clientes'])
        st.dataframe(styled_table, use_container_width=True)

