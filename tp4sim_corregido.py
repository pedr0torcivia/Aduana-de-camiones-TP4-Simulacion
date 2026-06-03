import streamlit as st
import random
import math
from dataclasses import dataclass
from typing import Optional
import pandas as pd

# Permitir Styler en tablas grandes
pd.set_option("styler.render.max_elements", 2_000_000)

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


def min_a_hhmm(minutos: float) -> str:
    h = int(minutos) // 60
    m = int(minutos) % 60
    return f"{h:02d}:{m:02d}"


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
    add("Columnas auxiliares", "ACU tiempo activo", "aux_acu_tiempo_activo")

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
    N: int,
    seed: Optional[int],
    tipos_clientes: list,
    doc_min: float,
    doc_max: float,
    prob_fisica: float,
    fis_min: float,
    fis_max: float,
    ventana_inicio: float,
    ventana_fin: float,
    cantidad_dias: int,
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

    # Duración fija de la ventana operativa (en minutos)
    duracion_ventana = ventana_fin - ventana_inicio

    # Tiempos de apertura y cierre se programan dinámicamente:
    # - El siguiente día se programa recién cuando el día anterior termina de procesarse.
    # - Si el día anterior se extiende más allá de la apertura programada del siguiente día,
    #   la apertura real se desplaza al momento en que el sistema queda vacío.
    aperturas_reales = []   # tiempos absolutos de apertura ya programados
    cierres_reales = []     # tiempos absolutos de cierre ya programados

    def programar_proximo_dia(reloj_actual: float):
        d = len(aperturas_reales)  # índice del próximo día (base 0)
        if d >= cantidad_dias:
            return
        apertura_calendario = d * 1440 + ventana_inicio
        apertura_efectiva = max(apertura_calendario, reloj_actual)
        aperturas_reales.append(apertura_efectiva)
        cierres_reales.append(apertura_efectiva + duracion_ventana)

    programar_proximo_dia(0.0)  # Programar día 1

    ventana_abierta = False
    current_day_cierre_fired = False   # el cierre del día actual ya se disparó
    ultimo_cierre_fired = False        # fue el cierre del último día
    next_apertura_idx = 0              # índice del próximo evento "Apertura" a disparar
    next_cierre_idx = 0                # índice del próximo evento "Cierre" a disparar
    cierre_actual = None               # tiempo absoluto del cierre del día en curso
    t_apertura_actual = None           # momento en que abrió la ventana del día actual
    final_corte_guardado = False

    acum_espera = {tipo["id"]: 0.0 for tipo in tipos_clientes}
    cont_doc = {tipo["id"]: 0 for tipo in tipos_clientes}
    acum_ocup_fosa = 0.0
    acum_tiempo_activo = 0.0           # denominador de métricas (ventana + overtime)
    camiones_sistema = 0
    max_camiones = 0

    rows = []
    tipos_por_id = {tipo["id"]: tipo for tipo in tipos_clientes}
    orden_prioridad = sorted(tipos_clientes, key=lambda t: (t["prioridad"], t["id"]))

    def sistema_vacio() -> bool:
        return (
            camiones_sistema == 0
            and all(len(q) == 0 for q in colas_doc.values())
            and len(cola_fisica) == 0
            and all(s.estado == "Libre" for s in servidores)
            and all(f.estado == "Libre" for f in fosas)
        )

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
        if next_apertura_idx < len(aperturas_reales):
            candidatos.append((f"Apertura dia {next_apertura_idx + 1}", aperturas_reales[next_apertura_idx]))
        if ventana_abierta and next_cierre_idx < len(cierres_reales):
            candidatos.append((f"Cierre ventana dia {next_cierre_idx + 1}", cierres_reales[next_cierre_idx]))
        if not candidatos:
            return "Fin simulacion"
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
            "aux_acu_tiempo_activo": fmt(acum_tiempo_activo),
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

    def guardar_fila_final_corte(tiempo_corte: Optional[float] = None, evento_final: str = "Fin simulacion"):
        nonlocal reloj, acum_ocup_fosa, final_corte_guardado, acum_tiempo_activo
        if final_corte_guardado:
            return

        if tiempo_corte is None:
            tiempo_corte = reloj
        tiempo_corte = float(tiempo_corte)
        reloj = tiempo_corte

        for fosa in fosas:
            if fosa.estado == "Ocupado" and fosa.inicio_ocupacion is not None:
                acum_ocup_fosa += max(0.0, tiempo_corte - fosa.inicio_ocupacion)

        # Si el corte ocurre en medio de un día activo, sumar el tramo parcial
        if t_apertura_actual is not None:
            acum_tiempo_activo += max(0.0, tiempo_corte - t_apertura_actual)

        guardar_fila(evento_final, mostrar_temporales=False)
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
        # Próxima apertura (sólo si ya fue programada, es decir, el día anterior cerró)
        if next_apertura_idx < len(aperturas_reales):
            candidatos.append((
                f"Apertura dia {next_apertura_idx + 1}",
                aperturas_reales[next_apertura_idx],
                next_apertura_idx,
            ))
        # Próximo cierre (sólo mientras la ventana esté abierta)
        if ventana_abierta and next_cierre_idx < len(cierres_reales):
            candidatos.append((
                f"Cierre ventana dia {next_cierre_idx + 1}",
                cierres_reales[next_cierre_idx],
                next_cierre_idx,
            ))
        return candidatos

    # Fila inicial (sin llegadas — se generan al abrir la primera ventana)
    guardar_fila("Inicio")

    while iteracion < N:
        candidatos = candidatos_evento()
        if not candidatos:
            if not final_corte_guardado:
                guardar_fila_final_corte(reloj, "Fin simulacion")
            break

        evento, tiempo_evento, referencia = min(candidatos, key=lambda x: x[1])
        reloj = tiempo_evento

        # ------------------------------------------------------------------ #
        if evento.startswith("Apertura"):
            day_idx = referencia
            ventana_abierta = True
            current_day_cierre_fired = False
            next_apertura_idx = day_idx + 1
            t_apertura_actual = reloj
            cierre_actual = cierres_reales[day_idx]

            rnd_lleg_dict = {}
            dem_lleg_dict = {}
            for tipo in tipos_clientes:
                tid = tipo["id"]
                rnd = random.random()
                dem = exp_neg(tipo["media"], rnd)
                nueva_llegada = reloj + dem
                prox_llegadas[tid] = nueva_llegada if nueva_llegada <= cierre_actual else None
                rnd_lleg_dict[tid] = rnd
                dem_lleg_dict[tid] = dem

            guardar_fila(evento, rnd_lleg_dict=rnd_lleg_dict, dem_lleg_dict=dem_lleg_dict)

        # ------------------------------------------------------------------ #
        elif evento.startswith("Llegada"):
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
            prox_llegadas[tid] = (
                nueva_llegada
                if ventana_abierta and cierre_actual is not None and nueva_llegada <= cierre_actual
                else None
            )

            rnd_doc_d, dem_doc_d = asignar_documentales()
            guardar_fila(
                f"Llegada {tipo['codigo']}",
                rnd_lleg_dict={tid: rnd_l},
                dem_lleg_dict={tid: dem_l},
                rnd_doc_dict=rnd_doc_d,
                dem_doc_dict=dem_doc_d,
            )

        # ------------------------------------------------------------------ #
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

        # ------------------------------------------------------------------ #
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

        # ------------------------------------------------------------------ #
        elif evento.startswith("Cierre ventana"):
            day_idx = referencia
            ventana_abierta = False
            current_day_cierre_fired = True
            next_cierre_idx = day_idx + 1
            cierre_actual = None
            if day_idx == cantidad_dias - 1:
                ultimo_cierre_fired = True
            for tid in prox_llegadas:
                prox_llegadas[tid] = None
            guardar_fila(evento)

        # ------------------------------------------------------------------ #
        # Verificar fin de día: si el cierre ya ocurrió y el sistema está vacío
        if current_day_cierre_fired and sistema_vacio():
            acum_tiempo_activo += reloj - t_apertura_actual
            t_apertura_actual = None
            current_day_cierre_fired = False

            if ultimo_cierre_fired:
                guardar_fila_final_corte(reloj, "Fin simulacion")
                break
            else:
                # Programar el siguiente día (puede ser a partir de "reloj" si hay desborde)
                programar_proximo_dia(reloj)
                # El loop continúa; la próxima apertura ya está en candidatos

    # Corte por límite de iteraciones
    if rows and not final_corte_guardado:
        guardar_fila_final_corte(reloj, "Corte por limite de iteraciones")

    return (
        rows,
        camiones,
        acum_espera,
        cont_doc,
        acum_ocup_fosa,
        max_camiones,
        acum_tiempo_activo,
    )


# ---------------------------------------------------------------------------
# ESTILOS / COLORES
# ---------------------------------------------------------------------------

# Paleta de fondos para tipos de camiones (bg_llegada, bg_camion)
_PALETA_TIPOS = [
    ("#dbeafe", "#bfdbfe"),  # azul
    ("#fef3c7", "#fde68a"),  # ámbar
    ("#dcfce7", "#bbf7d0"),  # verde
    ("#fce7f3", "#fbcfe8"),  # rosa
    ("#ede9fe", "#ddd6fe"),  # violeta
    ("#ffedd5", "#fed7aa"),  # naranja
]

_COLOR_APERTURA    = "#f0fdf4"   # green-50
_COLOR_CIERRE      = "#fefce8"   # yellow-50
_COLOR_FIN_DOC     = "#f5f3ff"   # violet-50
_COLOR_FIN_FIS     = "#fdf2f8"   # pink-50
_COLOR_FIN_SIM     = "#f1f5f9"   # slate-100
_COLOR_CORTE_N     = "#fff7ed"   # orange-50
_COLOR_INICIO      = "#f8fafc"   # slate-50


def _colores_tipo(tipos_clientes: list) -> dict:
    """Devuelve {codigo: (bg_llegada, bg_camion)} para cada tipo."""
    return {
        t["codigo"]: _PALETA_TIPOS[i % len(_PALETA_TIPOS)]
        for i, t in enumerate(tipos_clientes)
    }


def _bg_evento(evento: str, colores: dict) -> str:
    if not evento:
        return ""
    if evento == "Inicio":
        return _COLOR_INICIO
    if evento.startswith("Apertura"):
        return _COLOR_APERTURA
    if evento.startswith("Cierre ventana"):
        return _COLOR_CIERRE
    if evento.startswith("Fin Doc"):
        return _COLOR_FIN_DOC
    if evento.startswith("Fin Revision Fisica"):
        return _COLOR_FIN_FIS
    if evento in ("Fin simulacion",):
        return _COLOR_FIN_SIM
    if evento == "Corte por limite de iteraciones":
        return _COLOR_CORTE_N
    for cod, (bg, _) in colores.items():
        if evento == f"Llegada {cod}":
            return bg
    return ""


def aplicar_estilos_vector(df, tipos_clientes: list):
    """Colorea cada fila del vector de estado según el tipo de evento."""
    colores = _colores_tipo(tipos_clientes)
    evento_col = ("Control", "Evento")

    def color_fila(row):
        evento = str(row.get(evento_col, "") or "")
        bg = _bg_evento(evento, colores)
        estilo = f"background-color: {bg}; color: #1e293b" if bg else ""
        return [estilo] * len(row)

    return df.style.apply(color_fila, axis=1)


def aplicar_estilos_activos(df, tipos_clientes: list):
    """Colorea la tabla de camiones activos por tipo."""
    colores = _colores_tipo(tipos_clientes)

    def color_fila(row):
        tipo = str(row.get("Tipo", "") or "")
        bg = colores.get(tipo, (None, None))[1]
        estilo = f"background-color: {bg}; color: #1e293b" if bg else ""
        return [estilo] * len(row)

    return df.style.apply(color_fila, axis=1)


def renderizar_leyenda(tipos_clientes: list):
    colores = _colores_tipo(tipos_clientes)
    items = []

    def chip(bg, texto):
        return (
            f'<span style="display:inline-block;padding:2px 10px;margin:2px 4px;'
            f'border-radius:4px;background:{bg};color:#1e293b;font-size:0.82rem;">{texto}</span>'
        )

    for tipo in tipos_clientes:
        cod = tipo["codigo"]
        bg, _ = colores[cod]
        items.append(chip(bg, f"Llegada {cod}"))

    items.append(chip(_COLOR_FIN_DOC,  "Fin Documental"))
    items.append(chip(_COLOR_FIN_FIS,  "Fin Revisión Física"))
    items.append(chip(_COLOR_APERTURA, "Apertura"))
    items.append(chip(_COLOR_CIERRE,   "Cierre ventana"))
    items.append(chip(_COLOR_FIN_SIM,  "Fin simulación"))
    items.append(chip(_COLOR_CORTE_N,  "Corte por N"))

    st.markdown(
        "<div style='margin-bottom:6px'><b>Leyenda:</b> " + " ".join(items) + "</div>",
        unsafe_allow_html=True,
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

N = st.sidebar.number_input("Iteraciones maximas N", min_value=1, value=10000, step=1)
mostrar_todas = st.sidebar.checkbox("Mostrar todas las filas", value=False)
i_rows = None if mostrar_todas else st.sidebar.number_input("Filas a mostrar i", min_value=1, value=50, step=1)
j_min = st.sidebar.number_input("Minuto inicio visualizacion j", min_value=0, value=0, step=1)
seed_input = st.sidebar.text_input("Semilla opcional", value="")

st.sidebar.subheader("Tipos de clientes")
cantidad_tipos = st.sidebar.number_input("Cantidad de tipos de clientes", min_value=1, value=2, step=1)

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
        media = st.number_input(f"Media llegada tipo {idx}", value=media_default, min_value=0.0001, key=f"media_{idx}")
        prioridad = st.number_input(
            f"Prioridad documental tipo {idx} (1 = mayor prioridad)",
            value=prioridad_default,
            min_value=1,
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
puestos_documentales = st.sidebar.number_input("Cantidad de servidores documentales", value=3, min_value=1, step=1)
doc_min = st.sidebar.number_input("Revision documental minima", value=10.0, min_value=0.0)
doc_max = st.sidebar.number_input("Revision documental maxima", value=15.0, min_value=0.0)

st.sidebar.subheader("Revision fisica")
cantidad_fosas = st.sidebar.number_input("Cantidad de servidores de fosa", value=1, min_value=1, step=1)
prob_fisica = st.sidebar.slider("Probabilidad revision fisica", 0.0, 1.0, 0.15, 0.01)
fis_min = st.sidebar.number_input("Revision fisica minima", value=30.0, min_value=0.0)
fis_max = st.sidebar.number_input("Revision fisica maxima", value=60.0, min_value=0.0)

st.sidebar.subheader("Ventana operativa")
cantidad_dias = st.sidebar.number_input("Cantidad de dias a simular", min_value=1, value=1, step=1)
ventana_inicio = st.sidebar.number_input(
    "Inicio ventana (min del día, 0-1440)",
    min_value=0,
    max_value=1439,
    value=420,
    step=1,
)
ventana_fin = st.sidebar.number_input(
    "Fin ventana (min del día, 0-1440)",
    min_value=1,
    max_value=1440,
    value=1140,
    step=1,
)

# Mostrar horarios equivalentes
if ventana_inicio < ventana_fin:
    st.sidebar.caption(
        f"Ventana: {min_a_hhmm(ventana_inicio)} – {min_a_hhmm(ventana_fin)} "
        f"({int(ventana_fin - ventana_inicio)} min/día)"
    )

errores = []
if N <= 0:
    errores.append("N debe ser mayor a 0.")
if i_rows is not None and i_rows <= 0:
    errores.append("i debe ser mayor a 0.")
if j_min < 0:
    errores.append("j debe ser mayor o igual a 0.")
if doc_max < doc_min:
    errores.append("La revision documental maxima debe ser mayor o igual a la minima.")
if fis_max < fis_min:
    errores.append("La revision fisica maxima debe ser mayor o igual a la minima.")
if ventana_inicio >= ventana_fin:
    errores.append("El inicio de ventana debe ser menor al fin de ventana.")
if ventana_fin > 1440:
    errores.append("El fin de ventana no puede superar 1440 min (24 hs).")
for tipo in tipos_clientes:
    if tipo["media"] <= 0:
        errores.append(f"La media de llegada de {tipo['codigo']} debe ser mayor a 0.")

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
            acum_tiempo_activo,
        ) = simular(
            N=int(N),
            seed=seed,
            tipos_clientes=tipos_clientes,
            doc_min=float(doc_min),
            doc_max=float(doc_max),
            prob_fisica=float(prob_fisica),
            fis_min=float(fis_min),
            fis_max=float(fis_max),
            ventana_inicio=float(ventana_inicio),
            ventana_fin=float(ventana_fin),
            cantidad_dias=int(cantidad_dias),
            puestos_documentales=int(puestos_documentales),
            cantidad_fosas=int(cantidad_fosas),
        )

    df_full = build_multiindex_df(rows, tipos_clientes, int(puestos_documentales), int(cantidad_fosas))

    ultimo_evento = rows[-1]["ctrl_evento"] if rows else ""
    corte_por_n = ultimo_evento == "Corte por limite de iteraciones"

    if corte_por_n:
        tiempo_corte = float(rows[-1]["ctrl_reloj"]) if rows else 0.0
        st.warning(
            f"La simulación se cortó en el minuto {tiempo_corte:.4f} por límite de iteraciones N={N}. "
            "Las métricas son parciales y el denominador se calcula hasta ese instante."
        )

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

    util_fosa = (acum_fosa / acum_tiempo_activo * 100) if acum_tiempo_activo > 0 else 0.0

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
            f"- Utilizacion fosa = ACU tiempo ocupacion fosa / ACU tiempo activo x 100 = "
            f"{acum_fosa:.4f} / {acum_tiempo_activo:.4f} x 100 = {util_fosa:.4f} %"
        )
        lineas.append(
            f"  (ACU tiempo activo = suma de ventanas operativas + overtime de cada día)"
        )
        lineas.append(f"- Maximo camiones simultaneos = max(Cont Camiones en sistema) = {max_cam}")
        st.markdown("\n".join(lineas))

    reloj_col = ("Control", "Reloj")
    df_desde_j = df_full[df_full[reloj_col] >= float(j_min)]
    df_filtrado = df_desde_j if mostrar_todas else df_desde_j.head(int(i_rows))
    df_ultima = df_full.tail(1)

    if not df_ultima.empty and df_ultima.index[0] not in df_filtrado.index:
        df_filtrado = pd.concat([df_filtrado, df_ultima])

    df_filtrado = df_filtrado.loc[~df_filtrado.index.duplicated(keep="first")]

    st.subheader("Vector de estado")
    if mostrar_todas:
        st.caption("Se muestran todas las filas desde j. La última fila siempre se incluye.")
    else:
        st.caption("Se muestran las primeras i filas desde j y siempre se agrega la ultima fila de simulacion si no estaba incluida.")
    renderizar_leyenda(tipos_clientes)
    st.dataframe(aplicar_estilos_vector(df_filtrado, tipos_clientes), use_container_width=True, height=650)

    st.subheader("Ultima fila de simulacion")
    st.dataframe(aplicar_estilos_vector(df_ultima, tipos_clientes), use_container_width=True, height=170)
