import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import folium
from folium.plugins import MarkerCluster, HeatMap
from streamlit_folium import st_folium
from fuzzywuzzy import process
import plotly.express as px

# URL base del repositorio en GitHub
BASE_URL = "https://raw.githubusercontent.com/Brunomperetti/Rostock/master/"

# Función para cargar archivos Excel desde GitHub
def cargar_archivo_github(archivo):
    url = f"{BASE_URL}{archivo}"
    try:
        # Realiza la solicitud GET para descargar el archivo
        response = requests.get(url)
        
        # Verifica si la solicitud fue exitosa
        if response.status_code == 200:
            # Usamos BytesIO para manejar el contenido binario de la respuesta
            return pd.read_excel(BytesIO(response.content))
        else:
            st.error(f"Error al cargar el archivo: {archivo}, código de estado: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error al descargar el archivo {archivo}: {e}")
        return None

# Configuración inicial de la página
st.set_page_config(layout="wide")

# ====== CARGA DE DATOS CON SPINNER ======
with st.spinner("Cargando datos..."):
    # Consultar los datos desde GitHub
    df_repmotor_geodificado = cargar_archivo_github("rep_motor_geodificado_normalizado.xlsx")
    df_clientes_activos = cargar_archivo_github("clientes_activos_geocodificados.xlsx")
    df_cliente_campaña = cargar_archivo_github("Cliente_Campaña_listo_normalizado.xlsx")
    df_base_fria = cargar_archivo_github("base_fria_geocodificado.xlsx")

    # Verificar si los archivos fueron cargados correctamente
    if df_repmotor_geodificado is None or df_clientes_activos is None or df_cliente_campaña is None or df_base_fria is None:
        st.error("No se pudieron cargar los archivos correctamente.")
        st.stop()  # Detener la ejecución si no hay datos
    else:
        # Unificación de potenciales
        potenciales = pd.concat([df_cliente_campaña, df_base_fria], ignore_index=True)

        df_clientes_activos['Tipo'] = 'Cliente'
        potenciales['Tipo'] = 'Potencial'

        # Normalización de provincias y localidades
        for col in ['Provincia', 'Localidad']:
            if col in df_clientes_activos.columns:
                df_clientes_activos[col] = df_clientes_activos[col].astype(str).str.upper().str.strip()
            if col in potenciales.columns:
                potenciales[col] = potenciales[col].astype(str).str.upper().str.strip()

        bases_unidas = pd.concat([df_clientes_activos, potenciales], ignore_index=True)

        # === Fuzzy matching ===
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
                if 'Provincia' in bases_unidas.columns:
                    bases_unidas['Provincia'] = normalizar_columna_fuzzy(bases_unidas['Provincia'])
                if 'Localidad' in bases_unidas.columns:
                    bases_unidas['Localidad'] = normalizar_columna_fuzzy(bases_unidas['Localidad'])
                
                st.session_state['Provincia_norm'] = bases_unidas['Provincia']
                st.session_state['Localidad_norm'] = bases_unidas['Localidad']

                # Normalizar 'Capital Federal' a 'Buenos Aires'
                bases_unidas['Provincia'] = bases_unidas['Provincia'].replace(
                    ['CAPITAL FEDERAL', 'CIUDAD DE BUENOS AIRES', 'CABA'], 'BUENOS AIRES')
        else:
            bases_unidas['Provincia'] = st.session_state['Provincia_norm']
            bases_unidas['Localidad'] = st.session_state['Localidad_norm']

        df_clientes_activos = bases_unidas[bases_unidas['Tipo'] == 'Cliente']
        potenciales = bases_unidas[bases_unidas['Tipo'] == 'Potencial']

# ====== UI ======
opciones = ["Mapa", "Mapa de calor", "Gráficos comparativos", "KPIs resumen"]
seleccion = st.sidebar.radio("Seleccioná la vista", opciones)

# ====== MAPA ======
if seleccion == "Mapa":
    with st.spinner("Cargando mapa..."):
        st.subheader("🗺️ Mapa de Clientes y Potenciales")
        m = folium.Map(location=[-38.4161, -63.6167], zoom_start=5, tiles='CartoDB positron')
        
        # URL del icono personalizado desde GitHub
        icon_url = "https://raw.githubusercontent.com/Brunomperetti/Rostock/master/icono.jpg"
        rostock_icon = folium.CustomIcon(icon_image=icon_url, icon_size=(30, 30))
        
        cluster_clientes = MarkerCluster(name='🟢 Clientes').add_to(m)
        cluster_potenciales = MarkerCluster(name='🔴 Potenciales').add_to(m)

        for _, row in df_clientes_activos.iterrows():
            if pd.notna(row['lat']) and pd.notna(row['lon']):
                nombre = row.get('Nombre fantasía', row.get('Nombre', 'Sin nombre'))
                popup_info = f"✅ Cliente: {nombre}<br>{row.get('Localidad', '')}, {row.get('Provincia', '')}"
                folium.Marker(
                    location=[row['lat'], row['lon']], 
                    popup=popup_info,
                    icon=rostock_icon  # Icono personalizado para clientes
                ).add_to(cluster_clientes)

        if 'lat' in potenciales.columns and 'lon' in potenciales.columns:
            for _, row in potenciales.iterrows():
                if pd.notna(row['lat']) and pd.notna(row['lon']):
                    nombre = row.get('Nombre fantasía', row.get('Nombre', 'Sin nombre'))
                    telefono = row.get('Telefono', row.get('Teléfono', 'Sin teléfono'))
                    popup_info = f"🔴 Potencial: {nombre}<br>{row.get('Localidad', '')}, {row.get('Provincia', '')}<br>📞 {telefono}"
                    folium.CircleMarker(
                        location=[row['lat'], row['lon']], 
                        radius=6, 
                        popup=popup_info,
                        color='red', 
                        fill=True, 
                        fill_color='red'
                    ).add_to(cluster_potenciales)

        folium.LayerControl().add_to(m)
        st_folium(m, width=800, height=600)

# ====== HEATMAP ======
elif seleccion == "Mapa de calor":
    with st.spinner("Generando mapa de calor..."):
        st.subheader("🔥 Mapa de Calor de Clientes y Potenciales")
        m_heat = folium.Map(location=[-38.4161, -63.6167], zoom_start=5, tiles='CartoDB positron')
        
        if 'lat' in df_clientes_activos.columns and 'lon' in df_clientes_activos.columns:
            HeatMap(
                df_clientes_activos[['lat', 'lon']].dropna().values.tolist(),
                name='🟢 Clientes', 
                radius=10,
                gradient={0.4: 'lime', 0.65: 'green', 1: 'darkgreen'}
            ).add_to(m_heat)
        
        if 'lat' in potenciales.columns and 'lon' in potenciales.columns:
            HeatMap(
                potenciales[['lat', 'lon']].dropna().values.tolist(),
                name='🔴 Potenciales', 
                radius=10,
                gradient={0.4: 'orange', 0.65: 'red', 1: 'darkred'}
            ).add_to(m_heat)
        
        folium.LayerControl().add_to(m_heat)
        st_folium(m_heat, width=800, height=600)

# ====== GRÁFICOS COMPARATIVOS ======
elif seleccion == "Gráficos comparativos":
    with st.expander("📈 Ver gráficos comparativos", expanded=True):
        st.markdown("### Clientes vs Potenciales por Provincia")
        
        if 'Provincia' in bases_unidas.columns and 'Tipo' in bases_unidas.columns:
            prov_counts = bases_unidas.groupby(['Provincia', 'Tipo']).size().reset_index(name='Cantidad')
            fig = px.bar(
                prov_counts, 
                x='Cantidad', 
                y='Provincia', 
                color='Tipo', 
                orientation='h', 
                barmode='group',
                color_discrete_map={'Cliente': '#2ecc71', 'Potencial': '#e74c3c'}, 
                height=600
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No se encontraron las columnas necesarias para generar el gráfico por provincia.")

        st.markdown("### Top 10 Localidades con más Clientes y Potenciales")
        if 'Localidad' in bases_unidas.columns and 'Tipo' in bases_unidas.columns:
            loc_counts = bases_unidas.groupby(['Localidad', 'Tipo']).size().reset_index(name='Cantidad')
            top_localidades = loc_counts.groupby('Localidad')['Cantidad'].sum().nlargest(10).index
            loc_counts_top = loc_counts[loc_counts['Localidad'].isin(top_localidades)]
            fig2 = px.bar(
                loc_counts_top, 
                x='Cantidad', 
                y='Localidad', 
                color='Tipo', 
                orientation='h', 
                barmode='group',
                color_discrete_map={'Cliente': '#2ecc71', 'Potencial': '#e74c3c'}, 
                height=600
            )
            fig2.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("No se encontraron las columnas necesarias para generar el gráfico por localidad.")

        st.markdown("### Proporción Global de Clientes y Potenciales")
        if 'Tipo' in bases_unidas.columns:
            tipo_counts = bases_unidas['Tipo'].value_counts().reset_index()
            tipo_counts.columns = ['Tipo', 'Cantidad']
            fig3 = px.pie(
                tipo_counts, 
                names='Tipo', 
                values='Cantidad',
                color='Tipo',
                color_discrete_map={'Cliente': '#2ecc71', 'Potencial': '#e74c3c'},
                hole=0.4
            )
            fig3.update_traces(textinfo='percent+label')
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.warning("No se encontró la columna 'Tipo' para generar el gráfico de proporción.")

# ====== KPIs RESUMEN ======
elif seleccion == "KPIs resumen":
    with st.expander("📋 Ver KPIs resumen", expanded=True):
        total_clientes = df_clientes_activos.shape[0]
        total_potenciales = potenciales.shape[0]
        total_general = bases_unidas.shape[0]
        porcentaje_clientes = (total_clientes / total_general) * 100 if total_general > 0 else 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🟢 Clientes Actuales", total_clientes)
        col2.metric("🔴 Potenciales", total_potenciales)
        col3.metric("📊 Total General", total_general)
        col4.metric("✅ % Clientes", f"{porcentaje_clientes:.2f}%")

        st.markdown("### Clientes y Potenciales por Provincia (Tabla con semáforo)")
        if 'Provincia' in bases_unidas.columns and 'Tipo' in bases_unidas.columns:
            resumen_prov = bases_unidas.groupby(['Provincia', 'Tipo']).size().unstack(fill_value=0)
            resumen_prov['Total'] = resumen_prov.sum(axis=1)
            resumen_prov['% Clientes'] = (resumen_prov.get('Cliente', 0) / resumen_prov['Total'] * 100).round(2)

            # Reemplazar nombres de provincias
            resumen_prov.index = resumen_prov.index.str.replace('CAPITAL FEDERAL', 'BUENOS AIRES')
            resumen_prov.index = resumen_prov.index.str.replace('CIUDAD DE BUENOS AIRES', 'BUENOS AIRES')
            resumen_prov.index = resumen_prov.index.str.replace('CABA', 'BUENOS AIRES')

            # Función para colorear las filas
            def color_fila(val):
                color = ''
                if isinstance(val, (int, float)):
                    if val >= 70:
                        color = 'background-color: #b6fcb6'  # Verde claro
                    elif val >= 40:
                        color = 'background-color: #fff3b0'  # Amarillo
                    else:
                        color = 'background-color: #fcb6b6'  # Rojo claro
                return color

            styled_table = resumen_prov.style.applymap(color_fila, subset=['% Clientes'])
            st.dataframe(styled_table, use_container_width=True)
        else:
            st.warning("No se encontraron las columnas necesarias para generar la tabla de provincias.")


