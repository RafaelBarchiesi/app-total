import pandas as pd
import re
import time
from datetime import datetime
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os

# --- CONFIGURACIONES ---
ARCHIVO_PADRON = "Padrón Electrodependientes Nacionales - MENDOZA.xlsx"
NOMBRE_HOJA = "Padrón"  # Cambiar si la hoja tiene otro nombre
COLUMNA_CONTACTOS = "Contacto"  # o 'contactos'
COLUMNA_VIGENCIA = "VIGENCIA"

# --- ABRIR CHROME EN MODO DEPURACIÓN ---
chrome_options = Options()
chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9223")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

# --- FUNCIONES ---

def extraer_numeros(celda_contactos):
    numeros = re.findall(r"\d{6,}", str(celda_contactos))
    telefonos = []
    for num in numeros:
        num = re.sub(r"[^\d]", "", num)
        if len(num) >= 9:
            if num.startswith("54"):
                num = "549" + num[2:]
            elif not num.startswith("549"):
                num = "549" + num[-10:]
            telefonos.append(num)
    return telefonos if telefonos else [None]

def enviar_mensaje(numero, mensaje):
    try:
        print(f"Enviando mensaje a: {numero}")
        driver.get(f"https://web.whatsapp.com/send?phone={numero}")
        time.sleep(6)

        input_box = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//footer//div[@contenteditable='true']"))
        )
        input_box.click()
        time.sleep(2)

        for linea in mensaje.split("\n"):
            input_box.send_keys(linea)
            input_box.send_keys(Keys.SHIFT, Keys.ENTER)

        time.sleep(1)
        input_box.send_keys(Keys.ENTER)
        time.sleep(3)

        print("Mensaje enviado.")
        return "Enviado", ""

    except Exception as e:
        # Si llegó a cargar el input y escribir, pero falló el ENTER o algo menor
        page_source = driver.page_source
        if "contenteditable" in page_source:
            print(f"[Advertencia] Posible error menor tras enviar a {numero}")
            return "No se pudo enviar WhatsApp", str(e)
        else:
            print(f"[Fallo real] No se pudo abrir o escribir en el chat con {numero}")
            return "No se pudo enviar WhatsApp", str(e)

# --- CARGAR Y PROCESAR PADRÓN ---
df_original = pd.read_excel(ARCHIVO_PADRON, sheet_name=NOMBRE_HOJA)
df_original[COLUMNA_CONTACTOS] = df_original[COLUMNA_CONTACTOS].fillna("")

df_vencidos = df_original[df_original[COLUMNA_VIGENCIA].str.upper().str.contains("VENCIDA", na=False)].copy()
df_vencidos["telefonos"] = df_vencidos[COLUMNA_CONTACTOS].apply(extraer_numeros)
df_explotado = df_vencidos.explode("telefonos").dropna(subset=["telefonos"])

df_explotado["Tipo Notificación"] = "Renovación - DI Vencida"
df_explotado["Fecha Notificación"] = ""
df_explotado["Estado Notificación"] = ""
df_explotado["Observaciones"] = ""

# --- ENVIAR MENSAJES ---
for idx, row in df_explotado.iterrows():
    numero = row["telefonos"]
    nombre = str(row.get("NOMBRE ELECTRODEPENDIENTE", "Usuario"))
    suministro = str(row.get("Nº SUMINISTRO", "S/D"))
    
    mensaje = f"""Buenas tardes, *Señor/a {nombre}*, usuario del *suministro N° {suministro}*:

Nos comunicamos desde el *EPRE Mendoza* para informarle que, tras NO haber recibido en los últimos 6 meses documentación a nivel provincial para el beneficio de *Electrodependencia por Cuestiones de Salud*, hemos advertido la falta de documentación actualizada.

Por lo expuesto, le informamos que deberá *realizar el trámite en el sistema TAD como una RENOVACIÓN*, incluyendo *toda la documentación necesaria* y asegurándose de iniciarlo correctamente. Una vez realizado, deberá enviarnos la *carátula del trámite*, así como también la documentación que haya subido al sistema TAD.

En caso de ya haber realizado el trámite en el sistema TAD, le solicitamos que nos envíe la carátula del mismo junto con la documentación que cargó oportunamente en el sistema TAD.

Ante cualquier duda, puede comunicarse por este medio o acercarse a nuestras oficinas:

  *- San Martín 285, Ciudad de Mendoza*  
  *- Bombal 283, San Rafael*

Es importante que complete este proceso para continuar recibiendo el beneficio. Para ello, dispone de un plazo de *60 días*. En caso de necesitar una extensión por alguna razón particular, por favor háganoslo saber.

*¡Muchas gracias!*"""

    estado, obs = enviar_mensaje(numero, mensaje)
    df_explotado.at[idx, "Fecha Notificación"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    df_explotado.at[idx, "Estado Notificación"] = estado
    df_explotado.at[idx, "Observaciones"] = obs

    
# --- GUARDAR RESULTADOS EN UN ARCHIVO HISTÓRICO ---
historial_file = "Historial_Notificaciones.xlsx"

# Agregamos timestamp de ejecución (por si querés analizar por tanda)
df_explotado["Timestamp de Ejecución"] = datetime.now().strftime("%Y-%m-%d %H:%M")

if os.path.exists(historial_file):
    df_historial = pd.read_excel(historial_file)
    df_total = pd.concat([df_historial, df_explotado], ignore_index=True)

    # Evitar duplicados exactos (mismo número, mismo suministro, misma fecha de notificación)
    df_total.drop_duplicates(subset=["Nº SUMINISTRO", "telefonos", "Fecha Notificación"], inplace=True)
else:
    df_total = df_explotado

df_total.to_excel(historial_file, index=False)
print(f"Historial actualizado en '{historial_file}'")
