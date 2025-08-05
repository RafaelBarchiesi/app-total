import streamlit as st
import pandas as pd
import re
import subprocess
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# --- Lanzar Chrome debug solo si se usa el modo Notificaciones ---
def lanzar_chrome_debug():
    import psutil
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if "chrome.exe" in proc.info['name'].lower():
            if "--remote-debugging-port=9223" in ' '.join(proc.info['cmdline']):
                return
    subprocess.Popen("abrir_chrome_debug.bat", shell=True)

# --- Configuración inicial ---
st.set_page_config(page_title="Notificaciones UED", layout="wide")
st.title("📢 Gestión de Notificaciones - Electrodependientes")

# ---------------------- PESTAÑAS ----------------------
tab_notif, tab_consulta, tab_gestion, tab_graficos = st.tabs(
    ["🚀 Notificaciones", "🔎 Consultas", "🛠️ Gestión de seguimiento", "📈 Gráficos"]
)

# ======================================================
# TAB 1: NOTIFICACIONES
# ======================================================
with tab_notif:
    st.markdown("### Subir padrón")
    archivo_excel = st.file_uploader(
        "Seleccionar archivo Excel", type=["xlsx"], key="archivo_excel"
    )
    lanzar_chrome_debug()

    if archivo_excel:
        archivo_path = "Padrón Electrodependientes Nacionales - MENDOZA.xlsx"
        with open(archivo_path, "wb") as f:
            f.write(archivo_excel.read())

        df = pd.read_excel(archivo_path, sheet_name="Padrón")
        df["Contacto"] = df["Contacto"].fillna("")

        # --- Función para extraer número válido ---
        def extraer_primer_numero(celda_contactos):
            numeros = re.findall(r"\d{6,}", str(celda_contactos))
            for num in numeros:
                num = re.sub(r"[^\d]", "", num)
                if len(num) >= 9:
                    if num.startswith("54"):
                        return "549" + num[2:]
                    elif not num.startswith("549"):
                        return "549" + num[-10:]
            return None

        df["telefono_wsp"] = df["Contacto"].apply(extraer_primer_numero)

        # Filtrar vencidas
        df = df[df["VIGENCIA"].astype(str).str.upper().str.contains("VENCIDA", na=False)].copy()

        # Asegurar columnas para seguimiento de envío
        for col in ["Fecha Notificación", "Estado Notificación", "Observaciones", "Tipo Notificación"]:
            if col not in df.columns:
                df[col] = ""

        st.success("📄 Padrón cargado correctamente")
        st.subheader("👥 Usuarios con disposición vencida")
        st.dataframe(df[["Nº SUMINISTRO", "NOMBRE ELECTRODEPENDIENTE", "telefono_wsp", "VIGENCIA"]])

        st.markdown("---")
        st.subheader("🚀 Enviar notificaciones automáticamente")

        if st.button("Iniciar envío automático"):
            st.info("⏳ Enviando mensajes por WhatsApp... No cerrar Chrome.")
            try:
                resultado = subprocess.run(["python", "notificar_ued.py"], capture_output=True, text=True)
                st.text_area("Resultado del proceso", value=resultado.stdout, height=300)
            except Exception as e:
                st.error(f"❌ Error al ejecutar el envío: {e}")

        st.markdown("---")
        st.subheader("📋 Seguimiento actual")
        if os.path.exists("Seguimiento_Notificaciones.xlsx"):
            df_seguimiento = pd.read_excel("Seguimiento_Notificaciones.xlsx")
            st.dataframe(df_seguimiento)
            st.download_button("⬇ Descargar seguimiento",
                               data=df_seguimiento.to_csv(index=False).encode("utf-8"),
                               file_name="Seguimiento_Notificaciones.csv",
                               mime="text/csv")
        else:
            st.info("No hay 'Seguimiento_Notificaciones.xlsx' todavía.")

# ======================================================
# Carga del historial para las otras pestañas
# ======================================================
df_hist = None
if os.path.exists("Historial_Notificaciones.xlsx"):
    df_hist = pd.read_excel("Historial_Notificaciones.xlsx")

    # columnas mínimas
    base_cols = ["Tipo Notificación", "Visto", "Respondió", "Respuesta", "Estado Caso",
                 "Fecha Notificación", "Estado Notificación", "Distribuidora", "Departamento",
                 "telefonos", "Contacto", "NOMBRE ELECTRODEPENDIENTE", "Nº SUMINISTRO"]
    for c in base_cols:
        if c not in df_hist.columns:
            df_hist[c] = ""

    # fecha a datetime
    if not pd.api.types.is_datetime64_any_dtype(df_hist["Fecha Notificación"]):
        df_hist["Fecha Notificación"] = pd.to_datetime(df_hist["Fecha Notificación"], errors="coerce")

else:
    with tab_consulta:
        st.warning("⚠️ No hay historial cargado todavía (falta 'Historial_Notificaciones.xlsx').")
    with tab_gestion:
        st.warning("⚠️ No hay historial cargado todavía (falta 'Historial_Notificaciones.xlsx').")
    with tab_graficos:
        st.warning("⚠️ No hay historial cargado todavía (falta 'Historial_Notificaciones.xlsx').")

# ======================================================
# TAB 2: CONSULTAS
# ======================================================
if df_hist is not None:
    with tab_consulta:
        st.subheader("🗂️ Módulo de Consulta")
        resultados = df_hist.copy()

        # --- Filtros principales ---
        hoy = datetime.today().date()
        una_semana_atras = hoy - timedelta(days=7)
        fecha_rango = st.date_input("📆 Rango de fechas (Fecha Notificación)",
                                    value=(una_semana_atras, hoy))
        if isinstance(fecha_rango, tuple) and len(fecha_rango) == 2:
            fi, ff = fecha_rango
            resultados = resultados[
                (resultados["Fecha Notificación"].dt.date >= fi) &
                (resultados["Fecha Notificación"].dt.date <= ff)
            ]

        # Tipo de notificación
        tipos = ["Todos"] + sorted([t for t in resultados["Tipo Notificación"].dropna().unique().tolist() if str(t).strip() != ""])
        tipo_sel = st.selectbox("📌 Tipo de notificación", tipos)
        if tipo_sel != "Todos":
            resultados = resultados[resultados["Tipo Notificación"] == tipo_sel]

        # Filtros avanzados
        col1, col2, col3 = st.columns(3)
        with col1:
            if "Distribuidora" in resultados.columns:
                distros = sorted(resultados["Distribuidora"].dropna().unique().tolist())
                dist_sel = st.multiselect("🏢 Distribuidora", options=distros)
                if dist_sel:
                    resultados = resultados[resultados["Distribuidora"].isin(dist_sel)]
        with col2:
            if "Departamento" in resultados.columns:
                deptos = sorted(resultados["Departamento"].dropna().unique().tolist())
                depto_sel = st.multiselect("📍 Departamento", options=deptos)
                if depto_sel:
                    resultados = resultados[resultados["Departamento"].isin(depto_sel)]
        with col3:
            if "Estado Caso" in resultados.columns:
                estados = sorted(resultados["Estado Caso"].dropna().unique().tolist())
                estado_sel = st.multiselect("📌 Estado del caso", options=estados)
                if estado_sel:
                    resultados = resultados[resultados["Estado Caso"].isin(estado_sel)]

        # Filtro de texto
        consulta_txt = st.text_input("🔎 Buscar por NIC, nombre o teléfono").strip().lower()
        if consulta_txt:
            resultados = resultados[resultados.apply(
                lambda row: (
                    consulta_txt in str(row.get("telefonos", "")).lower() or
                    consulta_txt in str(row.get("Contacto", "")).lower() or
                    consulta_txt in str(row.get("NOMBRE ELECTRODEPENDIENTE", "")).lower() or
                    consulta_txt in str(row.get("Nº SUMINISTRO", "")).lower()
                ), axis=1
            )]

        if resultados.empty:
            st.warning("No se encontraron coincidencias.")
        else:
            st.markdown("### 📋 Historial filtrado")
            st.dataframe(resultados[[
                "Nº SUMINISTRO", "NOMBRE ELECTRODEPENDIENTE", "telefonos",
                "Fecha Notificación", "Tipo Notificación", "Estado Notificación",
                "Estado Caso", "Distribuidora", "Departamento", "Respuesta"
            ]])
            st.download_button(
                "⬇ Descargar vista filtrada",
                data=resultados.to_csv(index=False).encode("utf-8"),
                file_name="Seguimiento_filtrado.csv",
                mime="text/csv"
            )

# ======================================================
# TAB 3: GESTIÓN DE SEGUIMIENTO
# ======================================================
if df_hist is not None:
    with tab_gestion:
        st.subheader("🛠️ Gestión de seguimiento")
        resultados = df_hist.copy()

        # (Opcional) filtro rápido por tipo para editar menos filas
        tipos_ed = ["Todos"] + sorted([t for t in resultados["Tipo Notificación"].dropna().unique().tolist() if str(t).strip() != ""])
        tipo_sel_ed = st.selectbox("📌 Filtrar para editar – Tipo de notificación", tipos_ed, key="tipo_ed")
        if tipo_sel_ed != "Todos":
            resultados = resultados[resultados["Tipo Notificación"] == tipo_sel_ed]

        if resultados.empty:
            st.info("No hay filas para editar con el filtro aplicado.")
        else:
            for idx, row in resultados.iterrows():
                st.markdown(f"**🔹 {row['NOMBRE ELECTRODEPENDIENTE']}** – Suministro: `{row['Nº SUMINISTRO']}` – Tel: `{row['telefonos']}`")

                df_hist.at[row.name, "Visto"] = st.checkbox("👁️ Visto", value=bool(row["Visto"]), key=f"visto_{idx}")
                df_hist.at[row.name, "Respondió"] = st.checkbox("💬 Respondió", value=bool(row["Respondió"]), key=f"respondio_{idx}")
                df_hist.at[row.name, "Respuesta"] = st.text_area("📝 Respuesta del usuario", value=row["Respuesta"] or "", key=f"respuesta_{idx}")
                opciones_estado = ["", "Sin contacto", "En seguimiento", "Documentación recibida", "Caso cerrado"]
                current_idx = 0 if pd.isna(row["Estado Caso"]) or row["Estado Caso"] not in opciones_estado else opciones_estado.index(row["Estado Caso"])
                df_hist.at[row.name, "Estado Caso"] = st.selectbox(
                    "📌 Estado del caso", options=opciones_estado, index=current_idx, key=f"estado_{idx}"
                )
                st.markdown("---")

            if st.button("💾 Guardar cambios en seguimiento"):
                df_hist.to_excel("Historial_Notificaciones.xlsx", index=False)
                df_hist.to_excel("Seguimiento_Usuarios.xlsx", index=False)
                st.success("✅ Cambios guardados correctamente.")

# ======================================================
# TAB 4: GRÁFICOS (por Tipo de Notificación)
# ======================================================
if df_hist is not None:
    with tab_graficos:
        st.subheader("📈 Gráficos por Tipo de Notificación")

        dfg = df_hist.copy()

        # Normalizar criterio de "notificado"
        # Consideramos notificado si tiene fecha o un estado en el set de enviados
        estados_enviados = {"ENVIADO", "ENTREGADO", "OK"}
        dfg["notificado"] = (
            dfg["Fecha Notificación"].notna() |
            dfg["Estado Notificación"].astype(str).str.upper().isin(estados_enviados)
        )

        # Selector de tipo
        tipos_g = sorted([t for t in dfg["Tipo Notificación"].dropna().unique().tolist() if str(t).strip() != ""])
        if not tipos_g:
            st.info("No hay valores en 'Tipo Notificación' para graficar.")
        else:
            tipo_g_sel = st.selectbox("📌 Elegí un tipo de notificación", tipos_g)

            # Total de notificados para el tipo seleccionado
            total_tipo = int(dfg[(dfg["Tipo Notificación"] == tipo_g_sel) & (dfg["notificado"])].shape[0])
            st.metric(label=f"Total notificados – {tipo_g_sel}", value=total_tipo)

            # Barras: total notificados por tipo (visión general)
            totales_por_tipo = (
            dfg[dfg["notificado"]]
            .groupby("Tipo Notificación")
            .size()
            .sort_values(ascending=False)
        )

        fig, ax = plt.subplots(figsize=(6, 4))  # más chico
        totales_por_tipo.plot(kind="bar", ax=ax)
        ax.set_title("Total de notificados por Tipo de Notificación")
        ax.set_xlabel("Tipo de Notificación")
        ax.set_ylabel("Total notificados")
        ax.set_xticklabels(ax.get_xticklabels(), rotation=0)  # etiquetas horizontales
        st.pyplot(fig)

        # --- Distribución de Estado de Notificación ---
        df_tipo = dfg[dfg["Tipo Notificación"] == tipo_g_sel]
        if not df_tipo.empty:
            estado_counts = df_tipo["Estado Notificación"].value_counts()

            fig2, ax2 = plt.subplots(figsize=(6, 4))  # más chico
            estado_counts.plot(kind="pie", autopct="%1.1f%%", ax=ax2)
            ax2.set_ylabel("")
            ax2.set_title(f"Distribución de Estado de Notificación – {tipo_g_sel}")
            st.pyplot(fig2)
