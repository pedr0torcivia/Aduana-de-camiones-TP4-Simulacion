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
# OBJETOS DEL SISTEMA
# ---------------------------------------------------------------------------

@dataclass
class Camion:
    id: int
    tipo: str
    h_llegada: float
    estado: str
    h_inicio_doc: Optional[float] = None


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
    inicio_ocupacion: Optional[float] = None
    fin: Optional[float] = None


# ---------------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------------------------------

def exp_neg(media: float, rnd: float) -> float:
    return -media * math.log(1 - rnd)


def uniforme(minv: float, maxv: float, rnd: float) -> float:
    return minv + rnd * (maxv - minv)


def minuto_a_hora(minuto: float) -> str:
    total = int(round(minuto))
    h = 7 + total // 60
    m = total % 60
    return f"{h:02d}:{m:02d}"


def fmt(x):
    if x is None:
        return None
    if isinstance(x, float):
        return round(x, 4)
    return x


# ---------------------------------------------------------------------------
# COLUMNAS DEL VECTOR DE ESTADO
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
    "aux_cont_ccg", "aux_cont_ccp",
    "aux_cam_sistema", "aux_max_cam",
]

CAMION_ATTRS_VECTOR = [
    ("Tipo", "tipo"),
    ("Hora Llegada", "h_llegada"),
    ("Hora Inicio Atención Documental", "h_inicio_doc"),
    ("Estado", "estado"),
]


def build_multiindex_df(rows_internal: list) -> pd.DataFrame:
    cols = list(MULTIINDEX_COLS)
    keys = list(INTERNAL_KEYS)

    camion_ids = set()
    for row in rows_internal:
        for key in row:
            if key.startswith("camion_"):
                parts = key.split("_")
                if len(parts) >= 3 and parts[1].isdigit():
                    camion_ids.add(int(parts[1]))

    for cid in sorted(camion_ids):
        for nombre_columna, clave_attr in CAMION_ATTRS_VECTOR:
            cols.append((f"Camion {cid}", nombre_columna))
            keys.append(f"camion_{cid}_{clave_attr}")

    data = {key: [row.get(key) for row in rows_internal] for key in keys}
    df = pd.DataFrame(data)
    df.columns = pd.MultiIndex.from_tuples(cols)
    return df


# ---------------------------------------------------------------------------
# SIMULACION
# ---------------------------------------------------------------------------

def simular(
    X: float,
    N: int,
    seed: Optional[int],
    media_CCG: float,
    media_CCP: float,
    doc_min: float,
    doc_max: float,
    prob_fisica: float,
    fis_min: float,
    fis_max: float,
    ventana_fin: float,
    puestos_documentales: int,
):
    if seed is not None:
        random.seed(seed)

    reloj = 0.0
    iteracion = 0
    id_counter = 0

    camiones = {}
    cola_ccg = []
    cola_ccp = []
    cola_fisica = []

    servidores = [Servidor(id=i + 1, estado="Libre") for i in range(puestos_documentales)]
    fosa = Fosa(estado="Libre")

    prox_ccg = None
    prox_ccp = None
    ventana_cerrada = False
    final_corte_guardado = False

    acum_espera_ccg = 0.0
    acum_espera_ccp = 0.0
    cont_ccg_doc = 0
    cont_ccp_doc = 0
    acum_ocup_fosa = 0.0
    camiones_sistema = 0
    max_camiones = 0

    rows = []

    # -----------------------------------------------------------------------
    # Funciones internas
    # -----------------------------------------------------------------------

    def nombre_prox_evento():
        candidatos = []
        if prox_ccg is not None:
            candidatos.append(("Llegada CCG", prox_ccg))
        if prox_ccp is not None:
            candidatos.append(("Llegada CCP", prox_ccp))
        for serv in servidores:
            if serv.fin is not None:
                candidatos.append((f"Fin Doc P{serv.id}", serv.fin))
        if fosa.fin is not None:
            candidatos.append(("Fin Revision Fisica", fosa.fin))
        if not ventana_cerrada:
            candidatos.append(("Cierre ventana", ventana_fin))
        candidatos.append(("Fin simulacion", X))

        if not candidatos:
            return None
        return min(candidatos, key=lambda x: x[1])[0]

    def guardar_fila(
        evento,
        rnd_ccg_f=None,
        dem_ccg_f=None,
        rnd_ccp_f=None,
        dem_ccp_f=None,
        rnd_doc_dict=None,
        dem_doc_dict=None,
        rnd_dec=None,
        situacion=None,
        rnd_fis=None,
        dem_fis=None,
        fin_fosa_liberada=None,
        mostrar_temporales=True,
    ):
        nonlocal iteracion

        rnd_doc_dict = rnd_doc_dict or {}
        dem_doc_dict = dem_doc_dict or {}

        row = {
            "ctrl_evento": evento,
            "ctrl_reloj": fmt(reloj),
            "ctrl_prox_evento": nombre_prox_evento(),

            "ccg_rnd": round(rnd_ccg_f, 6) if rnd_ccg_f is not None else None,
            "ccg_demora": fmt(dem_ccg_f),
            "ccg_prox": fmt(prox_ccg),

            "ccp_rnd": round(rnd_ccp_f, 6) if rnd_ccp_f is not None else None,
            "ccp_demora": fmt(dem_ccp_f),
            "ccp_prox": fmt(prox_ccp),

            "cola_ccg": len(cola_ccg),
            "cola_ccp": len(cola_ccp),

            "p1_estado": servidores[0].estado if len(servidores) > 0 else None,
            "p1_rnd": round(rnd_doc_dict.get(1), 6) if 1 in rnd_doc_dict else None,
            "p1_demora": fmt(dem_doc_dict.get(1)),
            "p1_fin": fmt(servidores[0].fin) if len(servidores) > 0 else None,

            "p2_estado": servidores[1].estado if len(servidores) > 1 else None,
            "p2_rnd": round(rnd_doc_dict.get(2), 6) if 2 in rnd_doc_dict else None,
            "p2_demora": fmt(dem_doc_dict.get(2)),
            "p2_fin": fmt(servidores[1].fin) if len(servidores) > 1 else None,

            "p3_estado": servidores[2].estado if len(servidores) > 2 else None,
            "p3_rnd": round(rnd_doc_dict.get(3), 6) if 3 in rnd_doc_dict else None,
            "p3_demora": fmt(dem_doc_dict.get(3)),
            "p3_fin": fmt(servidores[2].fin) if len(servidores) > 2 else None,

            "fis_rnd_dec": round(rnd_dec, 6) if rnd_dec is not None else None,
            "fis_situacion": situacion,
            "fos_estado": fosa.estado,
            "fos_cola": len(cola_fisica),
            "fis_rnd_tiempo": round(rnd_fis, 6) if rnd_fis is not None else None,
            "fis_demora": fmt(dem_fis),
            "fis_fin": fmt(fosa.fin),

            "aux_h_ini_fosa": fmt(fosa.inicio_ocupacion),
            "aux_h_fin_fosa": fmt(fin_fosa_liberada),
            "aux_acu_fosa": fmt(acum_ocup_fosa),
            "aux_acu_espera_ccg": fmt(acum_espera_ccg),
            "aux_acu_espera_ccp": fmt(acum_espera_ccp),
            "aux_cont_ccg": cont_ccg_doc,
            "aux_cont_ccp": cont_ccp_doc,
            "aux_cam_sistema": camiones_sistema,
            "aux_max_cam": max_camiones,
        }

        if mostrar_temporales:
            for cid, camion in sorted(camiones.items()):
                if camion.estado != "Destruido":
                    pref = f"camion_{cid}_"
                    row[pref + "tipo"] = camion.tipo
                    row[pref + "h_llegada"] = fmt(camion.h_llegada)
                    row[pref + "h_inicio_doc"] = fmt(camion.h_inicio_doc)
                    row[pref + "estado"] = camion.estado

        rows.append(row)
        iteracion += 1

    def guardar_fila_final_corte():
        nonlocal reloj, acum_ocup_fosa, final_corte_guardado
        if final_corte_guardado:
            return

        reloj = float(X)

        if fosa.estado == "Ocupado" and fosa.inicio_ocupacion is not None:
            if float(X) > fosa.inicio_ocupacion:
                acum_ocup_fosa += float(X) - fosa.inicio_ocupacion

        guardar_fila("Fin simulacion", mostrar_temporales=False)
        final_corte_guardado = True

    def asignar_documentales():
        nonlocal acum_espera_ccg, acum_espera_ccp
        nonlocal cont_ccg_doc, cont_ccp_doc

        rnd_doc_dict = {}
        dem_doc_dict = {}

        for serv in servidores:
            if serv.estado != "Libre":
                continue

            if cola_ccp:
                cid = cola_ccp.pop(0)
            elif cola_ccg:
                cid = cola_ccg.pop(0)
            else:
                break

            camion = camiones[cid]
            espera = reloj - camion.h_llegada

            if camion.tipo == "CCG":
                acum_espera_ccg += espera
                cont_ccg_doc += 1
            else:
                acum_espera_ccp += espera
                cont_ccp_doc += 1

            rnd_d = random.random()
            dem_d = uniforme(doc_min, doc_max, rnd_d)

            serv.estado = "Ocupado"
            serv.id_camion = cid
            serv.fin = reloj + dem_d

            camion.estado = "En revisión documental"
            camion.h_inicio_doc = reloj

            rnd_doc_dict[serv.id] = rnd_d
            dem_doc_dict[serv.id] = dem_d

        return rnd_doc_dict, dem_doc_dict

    def iniciar_fisica():
        if cola_fisica and fosa.estado == "Libre":
            cid = cola_fisica.pop(0)
            camion = camiones[cid]

            rnd_f = random.random()
            dem_f = uniforme(fis_min, fis_max, rnd_f)

            fosa.estado = "Ocupado"
            fosa.id_camion = cid
            fosa.inicio_ocupacion = reloj
            fosa.fin = reloj + dem_f

            camion.estado = "En revisión física"

            return rnd_f, dem_f

        return None, None

    def candidatos_evento():
        candidatos = []
        if prox_ccg is not None:
            candidatos.append(("Llegada CCG", prox_ccg))
        if prox_ccp is not None:
            candidatos.append(("Llegada CCP", prox_ccp))
        for serv in servidores:
            if serv.fin is not None:
                candidatos.append((f"Fin Doc P{serv.id}", serv.fin))
        if fosa.fin is not None:
            candidatos.append(("Fin Revision Fisica", fosa.fin))
        if not ventana_cerrada:
            candidatos.append(("Cierre ventana", ventana_fin))
        candidatos.append(("Fin simulacion", X))
        return candidatos

    # -----------------------------------------------------------------------
    # Inicialización de próximas llegadas
    # -----------------------------------------------------------------------

    rnd_ccg0 = random.random()
    dem_ccg0 = exp_neg(media_CCG, rnd_ccg0)
    prox_ccg = dem_ccg0 if dem_ccg0 <= ventana_fin else None

    rnd_ccp0 = random.random()
    dem_ccp0 = exp_neg(media_CCP, rnd_ccp0)
    prox_ccp = dem_ccp0 if dem_ccp0 <= ventana_fin else None

    guardar_fila(
        "Inicio",
        rnd_ccg_f=rnd_ccg0,
        dem_ccg_f=dem_ccg0,
        rnd_ccp_f=rnd_ccp0,
        dem_ccp_f=dem_ccp0,
    )

    # -----------------------------------------------------------------------
    # Loop principal
    # -----------------------------------------------------------------------

    while iteracion < N:
        candidatos = candidatos_evento()
        if not candidatos:
            break

        evento, tiempo_evento = min(candidatos, key=lambda x: x[1])

        if tiempo_evento > X:
            guardar_fila_final_corte()
            break

        reloj = tiempo_evento

        if evento == "Llegada CCG":
            id_counter += 1
            camion = Camion(
                id=id_counter,
                tipo="CCG",
                h_llegada=reloj,
                estado="En cola documental",
            )
            camiones[camion.id] = camion
            cola_ccg.append(camion.id)
            camiones_sistema += 1
            max_camiones = max(max_camiones, camiones_sistema)

            rnd_l = random.random()
            dem_l = exp_neg(media_CCG, rnd_l)
            nueva_llegada = reloj + dem_l
            prox_ccg = nueva_llegada if nueva_llegada <= ventana_fin and not ventana_cerrada else None

            rnd_doc_d, dem_doc_d = asignar_documentales()
            guardar_fila(
                "Llegada CCG",
                rnd_ccg_f=rnd_l,
                dem_ccg_f=dem_l,
                rnd_doc_dict=rnd_doc_d,
                dem_doc_dict=dem_doc_d,
            )

        elif evento == "Llegada CCP":
            id_counter += 1
            camion = Camion(
                id=id_counter,
                tipo="CCP",
                h_llegada=reloj,
                estado="En cola documental",
            )
            camiones[camion.id] = camion
            cola_ccp.append(camion.id)
            camiones_sistema += 1
            max_camiones = max(max_camiones, camiones_sistema)

            rnd_l = random.random()
            dem_l = exp_neg(media_CCP, rnd_l)
            nueva_llegada = reloj + dem_l
            prox_ccp = nueva_llegada if nueva_llegada <= ventana_fin and not ventana_cerrada else None

            rnd_doc_d, dem_doc_d = asignar_documentales()
            guardar_fila(
                "Llegada CCP",
                rnd_ccp_f=rnd_l,
                dem_ccp_f=dem_l,
                rnd_doc_dict=rnd_doc_d,
                dem_doc_dict=dem_doc_d,
            )

        elif evento.startswith("Fin Doc P"):
            sid = int(evento[-1])
            serv = servidores[sid - 1]
            cid = serv.id_camion
            camion = camiones[cid]

            serv.estado = "Libre"
            serv.id_camion = None
            serv.fin = None

            rnd_dec = random.random()
            rnd_fis = None
            dem_fis = None

            if rnd_dec < prob_fisica:
                situacion = "Va a Revision"
                camion.estado = "En cola física"
                cola_fisica.append(cid)
                rnd_fis, dem_fis = iniciar_fisica()
            else:
                situacion = "No Va a Revision"
                camion.estado = "Destruido"
                camiones_sistema -= 1

            rnd_doc_d, dem_doc_d = asignar_documentales()
            guardar_fila(
                evento,
                rnd_dec=rnd_dec,
                situacion=situacion,
                rnd_fis=rnd_fis,
                dem_fis=dem_fis,
                rnd_doc_dict=rnd_doc_d,
                dem_doc_dict=dem_doc_d,
            )

        elif evento == "Fin Revision Fisica":
            fin_fosa = reloj
            acum_ocup_fosa += reloj - fosa.inicio_ocupacion

            cid = fosa.id_camion
            camiones[cid].estado = "Destruido"
            camiones_sistema -= 1

            fosa.estado = "Libre"
            fosa.id_camion = None
            fosa.inicio_ocupacion = None
            fosa.fin = None

            rnd_fis, dem_fis = iniciar_fisica()
            guardar_fila(
                "Fin Revision Fisica",
                rnd_fis=rnd_fis,
                dem_fis=dem_fis,
                fin_fosa_liberada=fin_fosa,
            )

        elif evento == "Cierre ventana":
            ventana_cerrada = True
            prox_ccg = None
            prox_ccp = None
            guardar_fila("Cierre ventana")

        elif evento == "Fin simulacion":
            guardar_fila_final_corte()
            break

    if rows:
        if round(rows[-1].get("ctrl_reloj", -1), 4) != round(float(X), 4):
            guardar_fila_final_corte()

    return (
        rows,
        camiones,
        acum_espera_ccg,
        acum_espera_ccp,
        cont_ccg_doc,
        cont_ccp_doc,
        acum_ocup_fosa,
        max_camiones,
    )


# ---------------------------------------------------------------------------
# INTERFAZ STREAMLIT
# ---------------------------------------------------------------------------

st.title("Simulación: Aduana de Camiones")
st.markdown("Simulación de eventos discretos - Control aduanero de camiones.")

st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

st.sidebar.header("Parametros de simulacion")

X = st.sidebar.number_input("Tiempo total X (min)", min_value=1, max_value=10000, value=720, step=1)
N = st.sidebar.number_input("Iteraciones maximas N", min_value=1, max_value=100000, value=1000, step=1)
i_rows = st.sidebar.number_input("Filas a mostrar i", min_value=1, max_value=100000, value=50, step=1)
j_min = st.sidebar.number_input("Minuto inicio visualizacion j", min_value=0, max_value=100000, value=0, step=1)
seed_input = st.sidebar.text_input("Semilla opcional", value="")

st.sidebar.subheader("Llegadas")
media_CCG = st.sidebar.number_input("Media llegada CCG", value=15.0, min_value=0.1)
media_CCP = st.sidebar.number_input("Media llegada CCP", value=40.0, min_value=0.1)

st.sidebar.subheader("Control documental")
doc_min = st.sidebar.number_input("Revision documental minima", value=10.0, min_value=0.1)
doc_max = st.sidebar.number_input("Revision documental maxima", value=15.0, min_value=0.1)

st.sidebar.subheader("Revision fisica")
prob_fisica = st.sidebar.slider("Probabilidad revision fisica", 0.0, 1.0, 0.15, 0.01)
fis_min = st.sidebar.number_input("Revision fisica minima", value=30.0, min_value=0.1)
fis_max = st.sidebar.number_input("Revision fisica maxima", value=60.0, min_value=0.1)

st.sidebar.subheader("Ventana operativa")
ventana_fin = st.sidebar.number_input("Cierre de ventana operativa", value=720, min_value=1)

st.sidebar.subheader("Infraestructura")
puestos_documentales = st.sidebar.number_input("Puestos documentales", value=3, min_value=1, max_value=3)

errores = []
if X <= 0:
    errores.append("X debe ser mayor a 0.")
if N <= 0:
    errores.append("N debe ser mayor a 0.")
if i_rows <= 0:
    errores.append("i debe ser mayor a 0.")
if j_min < 0:
    errores.append("j debe ser mayor o igual a 0.")
if doc_max < doc_min:
    errores.append("La revision documental maxima debe ser mayor o igual a la minima.")
if fis_max < fis_min:
    errores.append("La revision fisica maxima debe ser mayor o igual a la minima.")
if ventana_fin <= 0:
    errores.append("El cierre de ventana debe ser mayor a 0.")

for error in errores:
    st.error(error)

if st.button("Simular", use_container_width=True) and not errores:
    seed = int(seed_input) if seed_input.strip().lstrip("-").isdigit() else None

    with st.spinner("Simulando..."):
        (
            rows,
            camiones,
            acum_esp_ccg,
            acum_esp_ccp,
            cnt_ccg,
            cnt_ccp,
            acum_fosa,
            max_cam,
        ) = simular(
            X=float(X),
            N=int(N),
            seed=seed,
            media_CCG=float(media_CCG),
            media_CCP=float(media_CCP),
            doc_min=float(doc_min),
            doc_max=float(doc_max),
            prob_fisica=float(prob_fisica),
            fis_min=float(fis_min),
            fis_max=float(fis_max),
            ventana_fin=float(ventana_fin),
            puestos_documentales=int(puestos_documentales),
        )

    df_full = build_multiindex_df(rows)

    st.subheader("Metricas finales")
    esp_ccg = acum_esp_ccg / cnt_ccg if cnt_ccg > 0 else 0.0
    esp_ccp = acum_esp_ccp / cnt_ccp if cnt_ccp > 0 else 0.0
    util_fosa = acum_fosa / float(X) * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Espera prom. CCG", f"{esp_ccg:.2f} min")
    c2.metric("Espera prom. CCP", f"{esp_ccp:.2f} min")
    c3.metric("Utilizacion fosa", f"{util_fosa:.2f} %")
    c4.metric("Max. camiones", str(max_cam))

    with st.expander("Formulas utilizadas"):
        st.markdown(
            f"""
- Espera promedio CCG = ACU de espera CCG / Cont CCG cola documental = {acum_esp_ccg:.4f} / {cnt_ccg} = {esp_ccg:.4f} min
- Espera promedio CCP = ACU de espera CCP / cont CCP cola documental = {acum_esp_ccp:.4f} / {cnt_ccp} = {esp_ccp:.4f} min
- Utilizacion fosa = ACU tiempo ocupacion fosa / Tiempo total simulado x 100 = {acum_fosa:.4f} / {float(X):.4f} x 100 = {util_fosa:.4f} %
- Maximo camiones simultaneos = max(Cont Camiones en sistema) = {max_cam}
"""
        )

    reloj_col = ("Control", "Reloj")

    df_filtrado = df_full[df_full[reloj_col] >= float(j_min)].head(int(i_rows))
    df_ultima = df_full.tail(1)

    if not df_ultima.empty and df_ultima.index[0] not in df_filtrado.index:
        df_filtrado = pd.concat([df_filtrado, df_ultima])

    df_filtrado = df_filtrado.loc[~df_filtrado.index.duplicated(keep="first")]

    st.subheader("Vector de estado")
    st.caption("Se muestran las primeras i filas desde j y siempre se agrega la ultima fila de simulacion si no estaba incluida.")
    st.dataframe(df_filtrado, use_container_width=True, height=650)

    st.subheader("Ultima fila de simulacion")
    st.dataframe(df_ultima, use_container_width=True, height=170)

    st.subheader("Camiones activos")
    activos = [camion for camion in camiones.values() if camion.estado != "Destruido"]

    if activos:
        df_activos = pd.DataFrame([
            {
                "Camion": camion.id,
                "Tipo": camion.tipo,
                "Hora Llegada": fmt(camion.h_llegada),
                "Hora Inicio Atención Documental": fmt(camion.h_inicio_doc),
                "Estado": camion.estado,
            }
            for camion in sorted(activos, key=lambda x: x.id)
        ])
        st.dataframe(df_activos, use_container_width=True, height=300)
    else:
        st.info("No hay camiones activos al finalizar la simulacion.")

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
