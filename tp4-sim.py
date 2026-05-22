import streamlit as st
import random
import math
from dataclasses import dataclass
from typing import Optional
import pandas as pd

st.set_page_config(
    page_title="Simulación: Aduana de Camiones",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# DATACLASSES
# ---------------------------------------------------------------------------

@dataclass
class Camion:
    id: int
    tipo: str
    h_llegada: float
    estado: str
    h_inicio_espera_doc: Optional[float] = None
    h_inicio_doc: Optional[float] = None
    h_fin_doc: Optional[float] = None
    h_inicio_fisica: Optional[float] = None
    h_fin_fisica: Optional[float] = None

@dataclass
class Servidor:
    id: int
    estado: str
    id_camion: Optional[int] = None
    fin: Optional[float] = None

@dataclass
class Fosa:
    estado: str
    id_camion: Optional[int] = None
    fin: Optional[float] = None
    inicio_ocupacion: Optional[float] = None

# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def minuto_a_hora(m: float) -> str:
    total = int(round(m))
    hh = 7 + total // 60
    mm = total % 60
    return f"{hh:02d}:{mm:02d}"

def exp_neg(media: float, rnd: float) -> float:
    return -media * math.log(1 - rnd)

def uniforme(minv: float, maxv: float, rnd: float) -> float:
    return minv + rnd * (maxv - minv)

# ---------------------------------------------------------------------------
# DEFINICION MULTIINDEX
# ---------------------------------------------------------------------------

MULTIINDEX_COLS = [
    ("Control", "Evento"),
    ("Control", "Reloj"),
    ("Control", "Prox Evento"),
    ("Llegada de Camión con Carga general", "RND CCG"),
    ("Llegada de Camión con Carga general", "Demora en llegar"),
    ("Llegada de Camión con Carga general", "Proxima Llegada"),
    ("Llegada de Camión con Carga perecedera", "RND CCP"),
    ("Llegada de Camión con Carga perecedera", "Demora en llegar"),
    ("Llegada de Camión con Carga perecedera", "Proxima Llegada"),
    ("Colas Control Documental", "Cola CCG"),
    ("Colas Control Documental", "Cola CCP"),
    ("Puesto de Revision de documentos 1", "Estado"),
    ("Puesto de Revision de documentos 1", "RND"),
    ("Puesto de Revision de documentos 1", "Demora Revision Documental"),
    ("Puesto de Revision de documentos 1", "Fin Revision Documental"),
    ("Puesto de Revision de documentos 2", "Estado"),
    ("Puesto de Revision de documentos 2", "RND"),
    ("Puesto de Revision de documentos 2", "Demora Revision Documental"),
    ("Puesto de Revision de documentos 2", "Fin Revision Documental"),
    ("Puesto de Revision de documentos 3", "Estado"),
    ("Puesto de Revision de documentos 3", "RND"),
    ("Puesto de Revision de documentos 3", "Demora Revision Documental"),
    ("Puesto de Revision de documentos 3", "Fin Revision Documental"),
    ("Revision Fisica", "RND revision"),
    ("Revision Fisica", "Situacion"),
    ("Revision Fisica", "Estado"),
    ("Revision Fisica", "Cola"),
    ("Revision Fisica", "RND tiempo Revision"),
    ("Revision Fisica", "Demora Revision"),
    ("Revision Fisica", "Finaliza Revision"),
    ("Columnas auxiliares", "Hora inicio ocupacion fosa"),
    ("Columnas auxiliares", "Hora fin ocupacion fosa"),
    ("Columnas auxiliares", "ACU tiempo ocupacion fosa"),
    ("Columnas auxiliares", "ACU de espera CCG"),
    ("Columnas auxiliares", "ACU de espera CCP"),
    ("Columnas auxiliares", "Cont CCG cola documental"),
    ("Columnas auxiliares", "cont CCP cola documental"),
    ("Columnas auxiliares", "Cont CP cola documental"),
    ("Columnas auxiliares", "Cont Camiones en sistema"),
    ("Columnas auxiliares", "Max camiones"),
]

INTERNAL_KEYS = [
    "ctrl_evento", "ctrl_reloj", "ctrl_prox_evento",
    "ccg_rnd", "ccg_demora", "ccg_prox",
    "ccp_rnd", "ccp_demora", "ccp_prox",
    "cola_ccg", "cola_ccp",
    "p1_estado", "p1_rnd", "p1_demora", "p1_fin",
    "p2_estado", "p2_rnd", "p2_demora", "p2_fin",
    "p3_estado", "p3_rnd", "p3_demora", "p3_fin",
    "fis_rnd_dec", "fis_situacion", "fos_estado", "fos_cola",
    "fis_rnd_tiempo", "fis_demora", "fis_fin",
    "aux_h_ini_fosa", "aux_h_fin_fosa", "aux_acu_fosa",
    "aux_acu_espera_ccg", "aux_acu_espera_ccp",
    "aux_cont_ccg", "aux_cont_ccp", "aux_cont_cp",
    "aux_cam_sistema", "aux_max_cam",
]

assert len(INTERNAL_KEYS) == len(MULTIINDEX_COLS)

def build_multiindex_df(rows_internal: list) -> pd.DataFrame:
    data = {k: [r.get(k) for r in rows_internal] for k in INTERNAL_KEYS}
    df = pd.DataFrame(data)
    df.columns = pd.MultiIndex.from_tuples(MULTIINDEX_COLS)
    return df

# ---------------------------------------------------------------------------
# SIMULACION PRINCIPAL
# ---------------------------------------------------------------------------

def simular(
    X, N, seed,
    media_CCG, media_CCP,
    doc_min, doc_max,
    prob_fisica, fis_min, fis_max,
    ventana_inicio, ventana_fin,
    puestos_documentales, n_fosas
):
    if seed is not None:
        random.seed(seed)

    reloj = 0.0
    iteracion = 0
    id_counter = 0
    camiones: dict = {}

    cola_ccg: list = []
    cola_ccp: list = []
    cola_fisica: list = []

    servidores = [Servidor(id=i+1, estado="Libre") for i in range(puestos_documentales)]
    fosa = Fosa(estado="Libre")

    acum_espera_CCG = 0.0
    acum_espera_CCP = 0.0
    cont_CCG_doc = 0
    cont_CCP_doc = 0
    cont_total_doc = 0
    acum_ocup_fosa = 0.0
    camiones_sistema = 0
    max_camiones_sistema = 0

    # Primera llegada CCG
    rnd_ccg0 = random.random()
    dem_ccg0 = exp_neg(media_CCG, rnd_ccg0)
    prox_ccg = dem_ccg0 if dem_ccg0 <= ventana_fin else None

    # Primera llegada CCP
    rnd_ccp0 = random.random()
    dem_ccp0 = exp_neg(media_CCP, rnd_ccp0)
    prox_ccp = dem_ccp0 if dem_ccp0 <= ventana_fin else None

    ventana_cerrada = False
    rows: list = []

    # -----------------------------------------------------------------------
    # Nombre del proximo evento (para columna Prox Evento)
    # -----------------------------------------------------------------------
    def nombre_prox_evento():
        cands = []
        if prox_ccg is not None:
            cands.append(("Llegada CCG", prox_ccg))
        if prox_ccp is not None:
            cands.append(("Llegada CCP", prox_ccp))
        for s in servidores:
            if s.fin is not None:
                cands.append((f"Fin Doc P{s.id}", s.fin))
        if fosa.fin is not None:
            cands.append(("Fin Revision Fisica", fosa.fin))
        if not ventana_cerrada:
            cands.append(("Cierre ventana", ventana_fin))
        cands.append(("Fin simulacion", X))
        if not cands:
            return ""
        nombre, _ = min(cands, key=lambda x: x[1])
        return nombre

    # -----------------------------------------------------------------------
    # Guardar fila del vector de estado
    # -----------------------------------------------------------------------
    def guardar_fila(
        evento,
        rnd_ccg_f=None, dem_ccg_f=None,
        rnd_ccp_f=None, dem_ccp_f=None,
        rnd_doc_dict=None, dem_doc_dict=None,
        rnd_dec=None, situacion=None,
        rnd_fis=None, dem_fis=None,
        fin_fosa_liberada=None,
    ):
        nonlocal iteracion
        prox = nombre_prox_evento()
        row = {
            "ctrl_evento": evento,
            "ctrl_reloj": round(reloj, 4),
            "ctrl_prox_evento": prox,
            "ccg_rnd": round(rnd_ccg_f, 6) if rnd_ccg_f is not None else None,
            "ccg_demora": round(dem_ccg_f, 4) if dem_ccg_f is not None else None,
            "ccg_prox": round(prox_ccg, 4) if prox_ccg is not None else None,
            "ccp_rnd": round(rnd_ccp_f, 6) if rnd_ccp_f is not None else None,
            "ccp_demora": round(dem_ccp_f, 4) if dem_ccp_f is not None else None,
            "ccp_prox": round(prox_ccp, 4) if prox_ccp is not None else None,
            "cola_ccg": len(cola_ccg),
            "cola_ccp": len(cola_ccp),
            "p1_estado": servidores[0].estado if len(servidores) > 0 else None,
            "p1_rnd": round((rnd_doc_dict or {}).get(1), 6) if (rnd_doc_dict and 1 in rnd_doc_dict) else None,
            "p1_demora": round((dem_doc_dict or {}).get(1), 4) if (dem_doc_dict and 1 in dem_doc_dict) else None,
            "p1_fin": round(servidores[0].fin, 4) if (len(servidores) > 0 and servidores[0].fin is not None) else None,
            "p2_estado": servidores[1].estado if len(servidores) > 1 else None,
            "p2_rnd": round((rnd_doc_dict or {}).get(2), 6) if (rnd_doc_dict and 2 in rnd_doc_dict) else None,
            "p2_demora": round((dem_doc_dict or {}).get(2), 4) if (dem_doc_dict and 2 in dem_doc_dict) else None,
            "p2_fin": round(servidores[1].fin, 4) if (len(servidores) > 1 and servidores[1].fin is not None) else None,
            "p3_estado": servidores[2].estado if len(servidores) > 2 else None,
            "p3_rnd": round((rnd_doc_dict or {}).get(3), 6) if (rnd_doc_dict and 3 in rnd_doc_dict) else None,
            "p3_demora": round((dem_doc_dict or {}).get(3), 4) if (dem_doc_dict and 3 in dem_doc_dict) else None,
            "p3_fin": round(servidores[2].fin, 4) if (len(servidores) > 2 and servidores[2].fin is not None) else None,
            "fis_rnd_dec": round(rnd_dec, 6) if rnd_dec is not None else None,
            "fis_situacion": situacion,
            "fos_estado": fosa.estado,
            "fos_cola": len(cola_fisica),
            "fis_rnd_tiempo": round(rnd_fis, 6) if rnd_fis is not None else None,
            "fis_demora": round(dem_fis, 4) if dem_fis is not None else None,
            "fis_fin": round(fosa.fin, 4) if fosa.fin is not None else None,
            "aux_h_ini_fosa": round(fosa.inicio_ocupacion, 4) if fosa.inicio_ocupacion is not None else None,
            "aux_h_fin_fosa": round(fin_fosa_liberada, 4) if fin_fosa_liberada is not None else None,
            "aux_acu_fosa": round(acum_ocup_fosa, 4),
            "aux_acu_espera_ccg": round(acum_espera_CCG, 4),
            "aux_acu_espera_ccp": round(acum_espera_CCP, 4),
            "aux_cont_ccg": cont_CCG_doc,
            "aux_cont_ccp": cont_CCP_doc,
            "aux_cont_cp": cont_total_doc,
            "aux_cam_sistema": camiones_sistema,
            "aux_max_cam": max_camiones_sistema,
        }
        rows.append(row)
        iteracion += 1

    # -----------------------------------------------------------------------
    # Guardar fila final de corte en X, incluyendo ocupación parcial de fosa
    # si la fosa queda ocupada al finalizar la simulación.
    # -----------------------------------------------------------------------
    final_corte_guardado = False

    def guardar_fila_final_corte():
        nonlocal reloj, acum_ocup_fosa, final_corte_guardado
        if final_corte_guardado:
            return
        reloj = float(X)
        if fosa.estado == "Ocupado" and fosa.inicio_ocupacion is not None:
            if float(X) > fosa.inicio_ocupacion:
                acum_ocup_fosa += float(X) - fosa.inicio_ocupacion
        guardar_fila("Fin simulacion")
        final_corte_guardado = True

    # -----------------------------------------------------------------------
    # Asignar puestos documentales libres
    # -----------------------------------------------------------------------
    def asignar_documentales():
        nonlocal acum_espera_CCG, acum_espera_CCP, cont_CCG_doc, cont_CCP_doc, cont_total_doc
        rnd_doc_dict = {}
        dem_doc_dict = {}
        for s in servidores:
            if s.estado == "Libre":
                if cola_ccp:
                    cid = cola_ccp.pop(0)
                elif cola_ccg:
                    cid = cola_ccg.pop(0)
                else:
                    break
                c = camiones[cid]
                espera = reloj - c.h_inicio_espera_doc
                if c.tipo == "CCG":
                    acum_espera_CCG += espera
                    cont_CCG_doc += 1
                else:
                    acum_espera_CCP += espera
                    cont_CCP_doc += 1
                cont_total_doc += 1
                rnd_d = random.random()
                dem_d = uniforme(doc_min, doc_max, rnd_d)
                s.estado = "Ocupado"
                s.id_camion = cid
                s.fin = reloj + dem_d
                c.estado = "En revisión documental"
                c.h_inicio_doc = reloj
                c.h_fin_doc = s.fin
                rnd_doc_dict[s.id] = rnd_d
                dem_doc_dict[s.id] = dem_d
        return rnd_doc_dict, dem_doc_dict

    # -----------------------------------------------------------------------
    # Iniciar revision fisica
    # -----------------------------------------------------------------------
    def iniciar_fisica():
        if cola_fisica and fosa.estado == "Libre":
            cid = cola_fisica.pop(0)
            c = camiones[cid]
            rnd_f = random.random()
            dem_f = uniforme(fis_min, fis_max, rnd_f)
            fosa.estado = "Ocupado"
            fosa.id_camion = cid
            fosa.fin = reloj + dem_f
            fosa.inicio_ocupacion = reloj
            c.estado = "En revisión física"
            c.h_inicio_fisica = reloj
            c.h_fin_fisica = fosa.fin
            return rnd_f, dem_f
        return None, None

    # -----------------------------------------------------------------------
    # EVENTO INICIO
    # -----------------------------------------------------------------------
    guardar_fila(
        "Inicio",
        rnd_ccg_f=rnd_ccg0, dem_ccg_f=dem_ccg0,
        rnd_ccp_f=rnd_ccp0, dem_ccp_f=dem_ccp0,
    )

    # -----------------------------------------------------------------------
    # LOOP PRINCIPAL
    # -----------------------------------------------------------------------
    while iteracion < N:
        cands = []
        if prox_ccg is not None:
            cands.append(("Llegada CCG", prox_ccg))
        if prox_ccp is not None:
            cands.append(("Llegada CCP", prox_ccp))
        for s in servidores:
            if s.fin is not None:
                cands.append((f"Fin Doc P{s.id}", s.fin))
        if fosa.fin is not None:
            cands.append(("Fin Revision Fisica", fosa.fin))
        if not ventana_cerrada:
            cands.append(("Cierre ventana", ventana_fin))
        cands.append(("Fin simulacion", X))

        if not cands:
            break

        prox_evento, prox_tiempo = min(cands, key=lambda x: x[1])

        # Si el proximo evento supera X, agregar fila final de corte y salir
        if prox_tiempo > X:
            guardar_fila_final_corte()
            break

        reloj = prox_tiempo

        # ---- LLEGADA CCG ----
        if prox_evento == "Llegada CCG":
            id_counter += 1
            c = Camion(id=id_counter, tipo="CCG", h_llegada=reloj,
                       estado="En cola documental", h_inicio_espera_doc=reloj)
            camiones[c.id] = c
            cola_ccg.append(c.id)
            camiones_sistema += 1
            max_camiones_sistema = max(max_camiones_sistema, camiones_sistema)

            rnd_l = random.random()
            dem_l = exp_neg(media_CCG, rnd_l)
            prox_ccg = reloj + dem_l if (reloj + dem_l <= ventana_fin and not ventana_cerrada) else None

            rnd_doc_d, dem_doc_d = asignar_documentales()
            guardar_fila("Llegada CCG", rnd_ccg_f=rnd_l, dem_ccg_f=dem_l,
                         rnd_doc_dict=rnd_doc_d, dem_doc_dict=dem_doc_d)

        # ---- LLEGADA CCP ----
        elif prox_evento == "Llegada CCP":
            id_counter += 1
            c = Camion(id=id_counter, tipo="CCP", h_llegada=reloj,
                       estado="En cola documental", h_inicio_espera_doc=reloj)
            camiones[c.id] = c
            cola_ccp.append(c.id)
            camiones_sistema += 1
            max_camiones_sistema = max(max_camiones_sistema, camiones_sistema)

            rnd_l = random.random()
            dem_l = exp_neg(media_CCP, rnd_l)
            prox_ccp = reloj + dem_l if (reloj + dem_l <= ventana_fin and not ventana_cerrada) else None

            rnd_doc_d, dem_doc_d = asignar_documentales()
            guardar_fila("Llegada CCP", rnd_ccp_f=rnd_l, dem_ccp_f=dem_l,
                         rnd_doc_dict=rnd_doc_d, dem_doc_dict=dem_doc_d)

        # ---- FIN DOCUMENTAL ----
        elif prox_evento.startswith("Fin Doc P"):
            sid = int(prox_evento[-1])
            s = servidores[sid - 1]
            cid = s.id_camion
            c = camiones[cid]

            s.estado = "Libre"
            s.id_camion = None
            s.fin = None

            rnd_dec = random.random()
            rnd_fis_f, dem_fis_f = None, None
            if rnd_dec < prob_fisica:
                situacion = "Va a Revision"
                c.estado = "En cola física"
                cola_fisica.append(cid)
                rnd_fis_f, dem_fis_f = iniciar_fisica()
            else:
                situacion = "No Va a Revision"
                c.estado = "Destruido"
                camiones_sistema -= 1

            rnd_doc_d, dem_doc_d = asignar_documentales()
            guardar_fila(prox_evento,
                         rnd_dec=rnd_dec, situacion=situacion,
                         rnd_fis=rnd_fis_f, dem_fis=dem_fis_f,
                         rnd_doc_dict=rnd_doc_d, dem_doc_dict=dem_doc_d)

        # ---- FIN REVISION FISICA ----
        elif prox_evento == "Fin Revision Fisica":
            fin_lib = reloj
            acum_ocup_fosa += reloj - fosa.inicio_ocupacion
            cid = fosa.id_camion
            camiones[cid].estado = "Destruido"
            camiones_sistema -= 1

            fosa.estado = "Libre"
            fosa.id_camion = None
            fosa.fin = None
            fosa.inicio_ocupacion = None

            rnd_fis_f, dem_fis_f = iniciar_fisica()
            guardar_fila("Fin Revision Fisica",
                         rnd_fis=rnd_fis_f, dem_fis=dem_fis_f,
                         fin_fosa_liberada=fin_lib)

        # ---- CIERRE VENTANA ----
        elif prox_evento == "Cierre ventana":
            ventana_cerrada = True
            prox_ccg = None
            prox_ccp = None
            guardar_fila("Cierre ventana")

        # ---- FIN SIMULACION ----
        elif prox_evento == "Fin simulacion":
            guardar_fila_final_corte()
            break

    # Garantizar fila final de corte si no existe
    if rows:
        ultima = rows[-1]
        if round(ultima.get("ctrl_reloj", -1), 4) != round(float(X), 4):
            guardar_fila_final_corte()

    return (rows, camiones,
            acum_espera_CCG, acum_espera_CCP,
            cont_CCG_doc, cont_CCP_doc,
            acum_ocup_fosa, max_camiones_sistema)


# ---------------------------------------------------------------------------
# APP STREAMLIT
# ---------------------------------------------------------------------------

st.title("Simulación: Aduana de Camiones")
st.markdown("Simulación de eventos discretos - Control aduanero de camiones.")

# CSS: layout ancho, tablas más grandes y botón Simular rojo
st.markdown("""
<style>
.block-container {
    max-width: 98vw !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    padding-top: 2rem !important;
}
[data-testid="stDataFrame"] {
    width: 100% !important;
}
[data-testid="stSidebar"] {
    min-width: 250px;
    max-width: 290px;
}
div.stButton > button {
    background-color: #c0392b;
    color: white;
    font-size: 1.25rem;
    font-weight: 700;
    padding: 0.9rem 1rem;
    border-radius: 8px;
    width: 100%;
    border: none;
}
div.stButton > button:hover {
    background-color: #a93226;
    color: white;
    border: none;
}
div.stButton > button:focus {
    color: white;
    border: none;
    box-shadow: none;
}
</style>
""", unsafe_allow_html=True)

# ---- SIDEBAR ----
st.sidebar.header("Parametros de simulacion")

X      = st.sidebar.number_input("Tiempo total (min)", min_value=1, max_value=10000, value=720, step=1)
N      = st.sidebar.number_input("Iteraciones maximas (N <= 100000)", min_value=1, max_value=100000, value=1000, step=1)
i_rows = st.sidebar.number_input("Filas a mostrar (i)", min_value=1, max_value=100000, value=50, step=1)
j_min  = st.sidebar.number_input("Minuto inicio visualizacion (j)", min_value=0, max_value=100000, value=0, step=1)
seed_input = st.sidebar.text_input("Semilla (opcional)", value="")

st.sidebar.subheader("Llegadas")
media_CCG = st.sidebar.number_input("Media CCG (min)", value=15.0, min_value=0.1)
media_CCP = st.sidebar.number_input("Media CCP (min)", value=40.0, min_value=0.1)

st.sidebar.subheader("Control documental")
doc_min = st.sidebar.number_input("Doc min (min)", value=10.0, min_value=0.1)
doc_max = st.sidebar.number_input("Doc max (min)", value=15.0, min_value=0.1)

st.sidebar.subheader("Revision fisica")
prob_fisica = st.sidebar.slider("P(revision fisica)", 0.0, 1.0, 0.15, 0.01)
fis_min = st.sidebar.number_input("Fisico min (min)", value=30.0, min_value=0.1)
fis_max = st.sidebar.number_input("Fisico max (min)", value=60.0, min_value=0.1)

st.sidebar.subheader("Ventana operativa")
ventana_inicio = st.sidebar.number_input("Ventana inicio (min)", value=0, min_value=0)
ventana_fin    = st.sidebar.number_input("Ventana fin (min)", value=720, min_value=1)

st.sidebar.subheader("Infraestructura")
puestos_documentales = st.sidebar.number_input("Puestos documentales", value=3, min_value=1, max_value=10)
n_fosas = st.sidebar.number_input("Fosas", value=1, min_value=1, max_value=1)

# ---- VALIDACIONES ----
errores = []
if X <= 0:      errores.append("X debe ser mayor a 0.")
if N <= 0:      errores.append("N debe ser mayor a 0.")
if i_rows <= 0: errores.append("i debe ser mayor a 0.")
if j_min < 0:   errores.append("j debe ser mayor o igual a 0.")
for e in errores:
    st.error(e)

# ---- BOTON SIMULAR ----
if st.button("Simular", use_container_width=True) and not errores:
    seed = int(seed_input) if seed_input.strip().lstrip("-").isdigit() else None

    with st.spinner("Simulando..."):
        (rows, camiones,
         acum_esp_CCG, acum_esp_CCP,
         cnt_CCG, cnt_CCP,
         acum_fosa, max_cam) = simular(
            X=float(X), N=int(N), seed=seed,
            media_CCG=float(media_CCG), media_CCP=float(media_CCP),
            doc_min=float(doc_min), doc_max=float(doc_max),
            prob_fisica=float(prob_fisica), fis_min=float(fis_min), fis_max=float(fis_max),
            ventana_inicio=float(ventana_inicio), ventana_fin=float(ventana_fin),
            puestos_documentales=int(puestos_documentales), n_fosas=int(n_fosas),
        )

    df_full = build_multiindex_df(rows)

    # ---- METRICAS ----
    st.subheader("Metricas finales")
    col1, col2, col3, col4 = st.columns(4)
    esp_ccg   = acum_esp_CCG / cnt_CCG if cnt_CCG > 0 else 0.0
    esp_ccp   = acum_esp_CCP / cnt_CCP if cnt_CCP > 0 else 0.0
    util_fosa = acum_fosa / float(X) * 100

    col1.metric("Espera prom. CCG (doc)", f"{esp_ccg:.2f} min")
    col2.metric("Espera prom. CCP (doc)", f"{esp_ccp:.2f} min")
    col3.metric("Utilizacion fosa", f"{util_fosa:.2f} %")
    col4.metric("Max. camiones simultaneos", str(max_cam))

    with st.expander("Formulas utilizadas"):
        st.markdown(f"""
- **Espera promedio CCG** = ACU de espera CCG / Cont CCG cola documental = {acum_esp_CCG:.4f} / {cnt_CCG} = **{esp_ccg:.4f} min**
- **Espera promedio CCP** = ACU de espera CCP / cont CCP cola documental = {acum_esp_CCP:.4f} / {cnt_CCP} = **{esp_ccp:.4f} min**
- **Utilizacion fosa** = ACU tiempo ocupacion fosa / Tiempo total simulado x 100 = {acum_fosa:.4f} / {X} x 100 = **{util_fosa:.4f} %**
- **Maximo camiones simultaneos** = max(Cont Camiones en sistema) = **{max_cam}**
        """)

    # ---- VECTOR FILTRADO ----
    st.subheader("Vector de estado")

    reloj_col = ("Control", "Reloj")

    # Filtrar por j, tomar i filas y agregar siempre la ultima fila real
    df_filtrado = df_full[df_full[reloj_col] >= j_min].head(int(i_rows))
    df_ultima = df_full.tail(1)
    if not df_ultima.empty:
        if df_ultima.index[0] not in df_filtrado.index:
            df_filtrado = pd.concat([df_filtrado, df_ultima])
    df_filtrado = df_filtrado.loc[~df_filtrado.index.duplicated(keep="first")]

    st.caption("Vector solicitado: primeras i filas desde j, con la ultima fila de simulacion agregada si no estaba incluida.")
    st.dataframe(df_filtrado, use_container_width=True, height=650)

    # ---- ULTIMA FILA SEPARADA ----
    st.subheader("Ultima fila de simulacion")
    st.caption("Fila final de corte del sistema. Se muestra aparte para verificar rapidamente el estado final.")
    st.dataframe(df_ultima, use_container_width=True, height=170)


    # ---- CAMIONES ACTIVOS ----
    st.subheader("Camiones activos")
    activos = [c for c in camiones.values() if c.estado != "Destruido"]
    if activos:
        df_activos = pd.DataFrame([{
            "id": c.id,
            "tipo": c.tipo,
            "estado": c.estado,
            "h_llegada": round(c.h_llegada, 4),
            "h_inicio_espera_doc": round(c.h_inicio_espera_doc, 4) if c.h_inicio_espera_doc is not None else None,
            "h_inicio_doc": round(c.h_inicio_doc, 4) if c.h_inicio_doc is not None else None,
            "h_fin_doc": round(c.h_fin_doc, 4) if c.h_fin_doc is not None else None,
            "h_inicio_fisica": round(c.h_inicio_fisica, 4) if c.h_inicio_fisica is not None else None,
            "h_fin_fisica": round(c.h_fin_fisica, 4) if c.h_fin_fisica is not None else None,
        } for c in sorted(activos, key=lambda x: x.id)])
        st.dataframe(df_activos, use_container_width=True, height=300)
    else:
        st.info("No hay camiones activos al finalizar la simulacion.")

    # ---- DESCARGA CSV ----
    st.subheader("Descargar vector completo")
    df_csv = df_full.copy()
    df_csv.columns = [f"{g} | {c}" for g, c in df_csv.columns]
    csv_bytes = df_csv.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Descargar CSV",
        data=csv_bytes,
        file_name="vector_aduana.csv",
        mime="text/csv",
    )