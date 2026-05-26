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
    tipo_id: int
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
    id: int
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


def fmt(x):
    if x is None:
        return None
    if isinstance(x, float):
        return round(x, 4)
    return x


def nombre_grupo_llegada(tipo: dict) -> str:
    codigo = tipo["codigo"]
    if codigo == "CCG":
        return "Llegada de Camión con Carga general"
    if codigo == "CCP":
        return "Llegada de Camión con Carga perecedera"
    return f"Llegada de {tipo['nombre']}"


# ---------------------------------------------------------------------------
# COLUMNAS DINÁMICAS DEL VECTOR DE ESTADO
# ---------------------------------------------------------------------------

CAMION_ATTRS_VECTOR = [
    ("Tipo", "tipo"),
    ("Hora Llegada", "h_llegada"),
    ("Hora Inicio Atención Documental", "h_inicio_doc"),
    ("Estado", "estado"),
]


def construir_columnas(tipos_clientes: list, puestos_documentales: int, cantidad_fosas: int):
    cols = []
    keys = []

    def add(grupo, col, key):
        cols.append((grupo, col))
        keys.append(key)

    add("Control", "Evento", "ctrl_evento")
    add("Control", "Reloj", "ctrl_reloj")
    add("Control", "Prox Evento", "ctrl_prox_evento")

    for tipo in tipos_clientes:
        tid = tipo["id"]
        grupo = nombre_grupo_llegada(tipo)
        add(grupo, f"RND {tipo['codigo']}", f"lleg_{tid}_rnd")
        add(grupo, "Demora en llegar", f"lleg_{tid}_demora")
        add(grupo, "Proxima Llegada", f"lleg_{tid}_prox")

    for tipo in tipos_clientes:
        add("Colas Control Documental", f"Cola {tipo['codigo']}", f"cola_doc_{tipo['id']}")

    for i in range(1, puestos_documentales + 1):
        grupo = f"Puesto de Revision de documentos {i}"
        add(grupo, "Estado", f"p{i}_estado")
        add(grupo, "RND", f"p{i}_rnd")
        add(grupo, "Demora Revision Documental", f"p{i}_demora")
        add(grupo, "Fin Revision Documental", f"p{i}_fin")

    if cantidad_fosas == 1:
        add("Revision Fisica", "RND revision", "fis_rnd_dec")
        add("Revision Fisica", "Situacion", "fis_situacion")
        add("Revision Fisica", "Estado", "fos_1_estado")
        add("Revision Fisica", "Cola", "fos_cola")
        add("Revision Fisica", "RND tiempo Revision", "fos_1_rnd_tiempo")
        add("Revision Fisica", "Demora Revision", "fos_1_demora")
        add("Revision Fisica", "Finaliza Revision", "fos_1_fin")
    else:
        add("Revision Fisica", "RND revision", "fis_rnd_dec")
        add("Revision Fisica", "Situacion", "fis_situacion")
        add("Revision Fisica", "Cola", "fos_cola")
        for i in range(1, cantidad_fosas + 1):
            grupo = f"Fosa de Revision Fisica {i}"
            add(grupo, "Estado", f"fos_{i}_estado")
            add(grupo, "RND tiempo Revision", f"fos_{i}_rnd_tiempo")
            add(grupo, "Demora Revision", f"fos_{i}_demora")
            add(grupo, "Finaliza Revision", f"fos_{i}_fin")

    if cantidad_fosas == 1:
        add("Columnas auxiliares", "Hora inicio ocupacion fosa", "aux_h_ini_fosa_1")
        add("Columnas auxiliares", "Hora fin ocupacion fosa", "aux_h_fin_fosa_1")
    else:
        for i in range(1, cantidad_fosas + 1):
            add("Columnas auxiliares", f"Hora inicio ocupacion fosa {i}", f"aux_h_ini_fosa_{i}")
            add("Columnas auxiliares", f"Hora fin ocupacion fosa {i}", f"aux_h_fin_fosa_{i}")

    add("Columnas auxiliares", "ACU tiempo ocupacion fosa", "aux_acu_fosa")

    for tipo in tipos_clientes:
        add("Columnas auxiliares", f"ACU de espera {tipo['codigo']}", f"aux_acu_espera_{tipo['id']}")

    for tipo in tipos_clientes:
        add("Columnas auxiliares", f"Cont {tipo['codigo']} cola documental", f"aux_cont_doc_{tipo['id']}")

    add("Columnas auxiliares", "Cont Camiones en sistema", "aux_cam_sistema")
    add("Columnas auxiliares", "Max camiones", "aux_max_cam")

    return cols, keys


def build_multiindex_df(rows_internal: list, tipos_clientes: list, puestos_documentales: int, cantidad_fosas: int) -> pd.DataFrame:
    cols, keys = construir_columnas(tipos_clientes, puestos_documentales, cantidad_fosas)

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
# SIMULACIÓN
# ---------------------------------------------------------------------------

def simular(
    X: float,
    N: int,
    seed: Optional[int],
    tipos_clientes: list,
    doc_min: float,
    doc_max: float,
    prob_fisica: float,
    fis_min: float,
    fis_max: float,
    ventana_fin: float,
    puestos_documentales: int,
    cantidad_fosas: int,
):
    if seed is not None:
        random.seed(seed)

    reloj = 0.0
    iteracion = 0
    id_counter = 0

    camiones = {}
    colas_doc = {tipo["id"]: [] for tipo in tipos_clientes}
    cola_fisica = []

    servidores = [Servidor(id=i + 1, estado="Libre") for i in range(puestos_documentales)]
    fosas = [Fosa(id=i + 1, estado="Libre") for i in range(cantidad_fosas)]

    prox_llegadas = {tipo["id"]: None for tipo in tipos_clientes}
    ventana_cerrada = False
    final_corte_guardado = False

    acum_espera = {tipo["id"]: 0.0 for tipo in tipos_clientes}
    cont_doc = {tipo["id"]: 0 for tipo in tipos_clientes}
    acum_ocup_fosa = 0.0
    camiones_sistema = 0
    max_camiones = 0

    rows = []
    tipos_por_id = {tipo["id"]: tipo for tipo in tipos_clientes}
    orden_prioridad = sorted(tipos_clientes, key=lambda t: (t["prioridad"], t["id"]))

    def nombre_tipo(tid: int) -> str:
        return tipos_por_id[tid]["codigo"]

    def nombre_prox_evento():
        candidatos = []
        for tipo in tipos_clientes:
            tid = tipo["id"]
            if prox_llegadas[tid] is not None:
                candidatos.append((f"Llegada {tipo['codigo']}", prox_llegadas[tid]))
        for serv in servidores:
            if serv.fin is not None:
                candidatos.append((f"Fin Doc P{serv.id}", serv.fin))
        for fosa in fosas:
            if fosa.fin is not None:
                candidatos.append((f"Fin Revision Fisica F{fosa.id}", fosa.fin))
        if not ventana_cerrada:
            candidatos.append(("Cierre ventana", ventana_fin))
        candidatos.append(("Fin simulacion", X))
        if not candidatos:
            return None
        return min(candidatos, key=lambda x: x[1])[0]

    def guardar_fila(
        evento,
        rnd_lleg_dict=None,
        dem_lleg_dict=None,
        rnd_doc_dict=None,
        dem_doc_dict=None,
        rnd_dec=None,
        situacion=None,
        rnd_fis_dict=None,
        dem_fis_dict=None,
        fin_fosa_liberada_dict=None,
        mostrar_temporales=True,
    ):
        nonlocal iteracion

        rnd_lleg_dict = rnd_lleg_dict or {}
        dem_lleg_dict = dem_lleg_dict or {}
        rnd_doc_dict = rnd_doc_dict or {}
        dem_doc_dict = dem_doc_dict or {}
        rnd_fis_dict = rnd_fis_dict or {}
        dem_fis_dict = dem_fis_dict or {}
        fin_fosa_liberada_dict = fin_fosa_liberada_dict or {}

        row = {
            "ctrl_evento": evento,
            "ctrl_reloj": fmt(reloj),
            "ctrl_prox_evento": nombre_prox_evento(),
            "fis_rnd_dec": round(rnd_dec, 6) if rnd_dec is not None else None,
            "fis_situacion": situacion,
            "fos_cola": len(cola_fisica),
            "aux_acu_fosa": fmt(acum_ocup_fosa),
            "aux_cam_sistema": camiones_sistema,
            "aux_max_cam": max_camiones,
        }

        for tipo in tipos_clientes:
            tid = tipo["id"]
            row[f"lleg_{tid}_rnd"] = round(rnd_lleg_dict[tid], 6) if tid in rnd_lleg_dict else None
            row[f"lleg_{tid}_demora"] = fmt(dem_lleg_dict.get(tid))
            row[f"lleg_{tid}_prox"] = fmt(prox_llegadas.get(tid))
            row[f"cola_doc_{tid}"] = len(colas_doc[tid])
            row[f"aux_acu_espera_{tid}"] = fmt(acum_espera[tid])
            row[f"aux_cont_doc_{tid}"] = cont_doc[tid]

        for serv in servidores:
            row[f"p{serv.id}_estado"] = serv.estado
            row[f"p{serv.id}_rnd"] = round(rnd_doc_dict[serv.id], 6) if serv.id in rnd_doc_dict else None
            row[f"p{serv.id}_demora"] = fmt(dem_doc_dict.get(serv.id))
            row[f"p{serv.id}_fin"] = fmt(serv.fin)

        for fosa in fosas:
            row[f"fos_{fosa.id}_estado"] = fosa.estado
            row[f"fos_{fosa.id}_rnd_tiempo"] = round(rnd_fis_dict[fosa.id], 6) if fosa.id in rnd_fis_dict else None
            row[f"fos_{fosa.id}_demora"] = fmt(dem_fis_dict.get(fosa.id))
            row[f"fos_{fosa.id}_fin"] = fmt(fosa.fin)
            row[f"aux_h_ini_fosa_{fosa.id}"] = fmt(fosa.inicio_ocupacion)
            row[f"aux_h_fin_fosa_{fosa.id}"] = fmt(fin_fosa_liberada_dict.get(fosa.id))

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
        for fosa in fosas:
            if fosa.estado == "Ocupado" and fosa.inicio_ocupacion is not None:
                if float(X) > fosa.inicio_ocupacion:
                    acum_ocup_fosa += float(X) - fosa.inicio_ocupacion

        guardar_fila("Fin simulacion", mostrar_temporales=False)
        final_corte_guardado = True

    def asignar_documentales():
        nonlocal acum_espera, cont_doc

        rnd_doc_dict = {}
        dem_doc_dict = {}

        for serv in servidores:
            if serv.estado != "Libre":
                continue

            cid = None
            for tipo in orden_prioridad:
                tid = tipo["id"]
                if colas_doc[tid]:
                    cid = colas_doc[tid].pop(0)
                    break

            if cid is None:
                break

            camion = camiones[cid]
            espera = reloj - camion.h_llegada
            acum_espera[camion.tipo_id] += espera
            cont_doc[camion.tipo_id] += 1

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
        rnd_fis_dict = {}
        dem_fis_dict = {}

        for fosa in fosas:
            if not cola_fisica:
                break
            if fosa.estado != "Libre":
                continue

            cid = cola_fisica.pop(0)
            camion = camiones[cid]

            rnd_f = random.random()
            dem_f = uniforme(fis_min, fis_max, rnd_f)

            fosa.estado = "Ocupado"
            fosa.id_camion = cid
            fosa.inicio_ocupacion = reloj
            fosa.fin = reloj + dem_f

            camion.estado = "En revisión física"

            rnd_fis_dict[fosa.id] = rnd_f
            dem_fis_dict[fosa.id] = dem_f

        return rnd_fis_dict, dem_fis_dict

    def candidatos_evento():
        candidatos = []
        for tipo in tipos_clientes:
            tid = tipo["id"]
            if prox_llegadas[tid] is not None:
                candidatos.append((f"Llegada {tipo['codigo']}", prox_llegadas[tid], tid))
        for serv in servidores:
            if serv.fin is not None:
                candidatos.append((f"Fin Doc P{serv.id}", serv.fin, serv.id))
        for fosa in fosas:
            if fosa.fin is not None:
                candidatos.append((f"Fin Revision Fisica F{fosa.id}", fosa.fin, fosa.id))
        if not ventana_cerrada:
            candidatos.append(("Cierre ventana", ventana_fin, None))
        candidatos.append(("Fin simulacion", X, None))
        return candidatos

    # Inicializar próximas llegadas
    rnd_lleg_inicial = {}
    dem_lleg_inicial = {}
    for tipo in tipos_clientes:
        tid = tipo["id"]
        rnd = random.random()
        demora = exp_neg(tipo["media"], rnd)
        prox_llegadas[tid] = demora if demora <= ventana_fin else None
        rnd_lleg_inicial[tid] = rnd
        dem_lleg_inicial[tid] = demora

    guardar_fila("Inicio", rnd_lleg_dict=rnd_lleg_inicial, dem_lleg_dict=dem_lleg_inicial)

    while iteracion < N:
        candidatos = candidatos_evento()
        if not candidatos:
            break

        evento, tiempo_evento, referencia = min(candidatos, key=lambda x: x[1])

        if tiempo_evento > X:
            guardar_fila_final_corte()
            break

        reloj = tiempo_evento

        if evento.startswith("Llegada"):
            tid = referencia
            tipo = tipos_por_id[tid]

            id_counter += 1
            camion = Camion(
                id=id_counter,
                tipo_id=tid,
                tipo=tipo["codigo"],
                h_llegada=reloj,
                estado="En cola documental",
            )
            camiones[camion.id] = camion
            colas_doc[tid].append(camion.id)

            camiones_sistema += 1
            max_camiones = max(max_camiones, camiones_sistema)

            rnd_l = random.random()
            dem_l = exp_neg(tipo["media"], rnd_l)
            nueva_llegada = reloj + dem_l
            prox_llegadas[tid] = nueva_llegada if nueva_llegada <= ventana_fin and not ventana_cerrada else None

            rnd_doc_d, dem_doc_d = asignar_documentales()
            guardar_fila(
                f"Llegada {tipo['codigo']}",
                rnd_lleg_dict={tid: rnd_l},
                dem_lleg_dict={tid: dem_l},
                rnd_doc_dict=rnd_doc_d,
                dem_doc_dict=dem_doc_d,
            )

        elif evento.startswith("Fin Doc P"):
            sid = referencia
            serv = servidores[sid - 1]
            cid = serv.id_camion
            camion = camiones[cid]

            serv.estado = "Libre"
            serv.id_camion = None
            serv.fin = None

            rnd_dec = random.random()
            rnd_fis_dict = {}
            dem_fis_dict = {}

            if rnd_dec < prob_fisica:
                situacion = "Va a Revision"
                camion.estado = "En cola física"
                cola_fisica.append(cid)
                rnd_fis_dict, dem_fis_dict = iniciar_fisica()
            else:
                situacion = "No Va a Revision"
                camion.estado = "Destruido"
                camiones_sistema -= 1

            rnd_doc_d, dem_doc_d = asignar_documentales()
            guardar_fila(
                evento,
                rnd_dec=rnd_dec,
                situacion=situacion,
                rnd_fis_dict=rnd_fis_dict,
                dem_fis_dict=dem_fis_dict,
                rnd_doc_dict=rnd_doc_d,
                dem_doc_dict=dem_doc_d,
            )

        elif evento.startswith("Fin Revision Fisica"):
            fosa_id = referencia
            fosa = fosas[fosa_id - 1]
            fin_fosa = reloj
            acum_ocup_fosa += reloj - fosa.inicio_ocupacion

            cid = fosa.id_camion
            camiones[cid].estado = "Destruido"
            camiones_sistema -= 1

            fosa.estado = "Libre"
            fosa.id_camion = None
            fosa.inicio_ocupacion = None
            fosa.fin = None

            rnd_fis_dict, dem_fis_dict = iniciar_fisica()
            guardar_fila(
                evento,
                rnd_fis_dict=rnd_fis_dict,
                dem_fis_dict=dem_fis_dict,
                fin_fosa_liberada_dict={fosa_id: fin_fosa},
            )

        elif evento == "Cierre ventana":
            ventana_cerrada = True
            for tid in prox_llegadas:
                prox_llegadas[tid] = None
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
        acum_espera,
        cont_doc,
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
    min-width: 260px;
    max-width: 320px;
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

st.sidebar.subheader("Tipos de clientes")
cantidad_tipos = st.sidebar.number_input("Cantidad de tipos de clientes", min_value=1, max_value=6, value=2, step=1)

tipos_clientes = []
for idx in range(1, int(cantidad_tipos) + 1):
    if idx == 1:
        codigo_default = "CCG"
        nombre_default = "Camión con Carga general"
        media_default = 15.0
        prioridad_default = 2
    elif idx == 2:
        codigo_default = "CCP"
        nombre_default = "Camión con Carga perecedera"
        media_default = 40.0
        prioridad_default = 1
    else:
        codigo_default = f"C{idx}"
        nombre_default = f"Cliente {idx}"
        media_default = 30.0
        prioridad_default = idx

    with st.sidebar.expander(f"Cliente tipo {idx}", expanded=(idx <= 2)):
        codigo = st.text_input(f"Código tipo {idx}", value=codigo_default, key=f"cod_{idx}").strip()
        nombre = st.text_input(f"Nombre tipo {idx}", value=nombre_default, key=f"nom_{idx}").strip()
        media = st.number_input(f"Media llegada tipo {idx}", value=media_default, min_value=0.1, key=f"media_{idx}")
        prioridad = st.number_input(
            f"Prioridad documental tipo {idx} (1 = mayor prioridad)",
            value=prioridad_default,
            min_value=1,
            max_value=99,
            step=1,
            key=f"prio_{idx}",
        )

    tipos_clientes.append({
        "id": idx,
        "codigo": codigo if codigo else f"C{idx}",
        "nombre": nombre if nombre else f"Cliente {idx}",
        "media": float(media),
        "prioridad": int(prioridad),
    })

st.sidebar.subheader("Control documental")
puestos_documentales = st.sidebar.number_input("Cantidad de servidores documentales", value=3, min_value=1, max_value=10, step=1)
doc_min = st.sidebar.number_input("Revision documental minima", value=10.0, min_value=0.1)
doc_max = st.sidebar.number_input("Revision documental maxima", value=15.0, min_value=0.1)

st.sidebar.subheader("Revision fisica")
cantidad_fosas = st.sidebar.number_input("Cantidad de servidores de fosa", value=1, min_value=1, max_value=10, step=1)
prob_fisica = st.sidebar.slider("Probabilidad revision fisica", 0.0, 1.0, 0.15, 0.01)
fis_min = st.sidebar.number_input("Revision fisica minima", value=30.0, min_value=0.1)
fis_max = st.sidebar.number_input("Revision fisica maxima", value=60.0, min_value=0.1)

st.sidebar.subheader("Ventana operativa")
ventana_fin = st.sidebar.number_input("Cierre de ventana operativa", value=720, min_value=1)

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
if len(set(t["codigo"] for t in tipos_clientes)) != len(tipos_clientes):
    errores.append("Los códigos de tipos de clientes no deben repetirse.")

for error in errores:
    st.error(error)

if st.button("Simular", use_container_width=True) and not errores:
    seed = int(seed_input) if seed_input.strip().lstrip("-").isdigit() else None

    with st.spinner("Simulando..."):
        (
            rows,
            camiones,
            acum_espera,
            cont_doc,
            acum_fosa,
            max_cam,
        ) = simular(
            X=float(X),
            N=int(N),
            seed=seed,
            tipos_clientes=tipos_clientes,
            doc_min=float(doc_min),
            doc_max=float(doc_max),
            prob_fisica=float(prob_fisica),
            fis_min=float(fis_min),
            fis_max=float(fis_max),
            ventana_fin=float(ventana_fin),
            puestos_documentales=int(puestos_documentales),
            cantidad_fosas=int(cantidad_fosas),
        )

    df_full = build_multiindex_df(rows, tipos_clientes, int(puestos_documentales), int(cantidad_fosas))

    st.subheader("Metricas finales")

    metric_cols = st.columns(min(4, len(tipos_clientes) + 2))
    col_idx = 0
    esperas = {}
    for tipo in tipos_clientes:
        tid = tipo["id"]
        espera_prom = acum_espera[tid] / cont_doc[tid] if cont_doc[tid] > 0 else 0.0
        esperas[tid] = espera_prom
        metric_cols[col_idx % len(metric_cols)].metric(
            f"Espera prom. {tipo['codigo']}",
            f"{espera_prom:.2f} min",
        )
        col_idx += 1

    util_fosa = acum_fosa / float(X) * 100
    metric_cols[col_idx % len(metric_cols)].metric("Utilizacion fosa", f"{util_fosa:.2f} %")
    col_idx += 1
    metric_cols[col_idx % len(metric_cols)].metric("Max. camiones", str(max_cam))

    with st.expander("Formulas utilizadas"):
        lineas = []
        for tipo in tipos_clientes:
            tid = tipo["id"]
            lineas.append(
                f"- Espera promedio {tipo['codigo']} = ACU de espera {tipo['codigo']} / "
                f"Cont {tipo['codigo']} cola documental = {acum_espera[tid]:.4f} / "
                f"{cont_doc[tid]} = {esperas[tid]:.4f} min"
            )
        lineas.append(
            f"- Utilizacion fosa = ACU tiempo ocupacion fosa / Tiempo total simulado x 100 = "
            f"{acum_fosa:.4f} / {float(X):.4f} x 100 = {util_fosa:.4f} %"
        )
        lineas.append(f"- Maximo camiones simultaneos = max(Cont Camiones en sistema) = {max_cam}")
        st.markdown("\n".join(lineas))

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
