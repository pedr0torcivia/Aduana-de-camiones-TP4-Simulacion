import streamlit as st
import random
import math
from dataclasses import dataclass
from typing import Optional
import pandas as pd

st.set_page_config(page_title="Aduana de Camiones", layout="wide")

# ─────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────
HORA_APERTURA = 7 * 60
HORA_CIERRE   = 19 * 60
MAX_ITER      = 100_000

def min2hhmm(m):
    if m is None: return "-"
    return f"{int(m)//60:02d}:{int(m)%60:02d}"

# ─────────────────────────────────────────────
#  GENERADORES
# ─────────────────────────────────────────────
def exp_neg(media):
    r = random.random()
    while r == 0: r = random.random()
    return -media * math.log(r), round(r, 4)

def uniforme(a, b):
    r = random.random()
    return a + (b - a) * r, round(r, 4)

# ─────────────────────────────────────────────
#  ESTRUCTURAS
# ─────────────────────────────────────────────
@dataclass
class Camion:
    id: int
    tipo: str
    t_llegada: float
    t_ini_doc: Optional[float] = None
    t_fin_doc: Optional[float] = None
    t_ini_fis: Optional[float] = None
    t_fin_fis: Optional[float] = None
    en_sistema: bool = True

@dataclass
class PuestoDoc:
    id: int
    libre: bool = True
    camion_id: Optional[int] = None
    t_fin: Optional[float] = None

@dataclass
class PuestoFis:
    libre: bool = True
    camion_id: Optional[int] = None
    t_fin: Optional[float] = None

# ─────────────────────────────────────────────
#  MOTOR DE SIMULACIÓN
# ─────────────────────────────────────────────
def simular(t_sim_min, media_gen, media_per, prob_fis,
            tdoc_min, tdoc_max, tfis_min, tfis_max):

    t_max = HORA_APERTURA + t_sim_min
    reloj = float(HORA_APERTURA)
    camiones: dict[int, Camion] = {}
    cola_doc: list[int] = []
    puestos_doc = [PuestoDoc(i) for i in range(1, 4)]
    puesto_fis  = PuestoFis()
    cola_fis: list[int] = []

    dt, rnd_prox_gen = exp_neg(media_gen)
    t_prox_gen = HORA_APERTURA + dt
    dt, rnd_prox_per = exp_neg(media_per)
    t_prox_per = HORA_APERTURA + dt

    id_counter = 0
    iteracion  = 0
    cierre     = False

    esp_gen = esp_per = 0.0
    cnt_gen = cnt_per = 0
    t_fis_ocup = 0.0
    max_recinto = 0

    filas = []

    def en_recinto():
        return sum(1 for c in camiones.values() if c.en_sistema)

    def ocupar_doc(cid, t):
        for p in puestos_doc:
            if p.libre:
                dur, rd = uniforme(tdoc_min, tdoc_max)
                p.libre = False; p.camion_id = cid; p.t_fin = t + dur
                camiones[cid].t_ini_doc = t
                camiones[cid].t_fin_doc = p.t_fin
                return rd
        return None

    def ocupar_fis(cid, t):
        dur, rf = uniforme(tfis_min, tfis_max)
        puesto_fis.libre = False; puesto_fis.camion_id = cid; puesto_fis.t_fin = t + dur
        camiones[cid].t_ini_fis = t
        camiones[cid].t_fin_fis = puesto_fis.t_fin
        return rf

    def proximos():
        evts = []
        if not cierre:
            evts += [("Lleg.Gen", t_prox_gen), ("Lleg.Per", t_prox_per)]
        for p in puestos_doc:
            if not p.libre: evts.append((f"FinDoc P{p.id}", p.t_fin))
        if not puesto_fis.libre: evts.append(("FinFís", puesto_fis.t_fin))
        return "; ".join(f"{n}@{min2hhmm(t)}" for n,t in sorted(evts, key=lambda x:x[1])[:5])

    def snap(evento, rnd_lg=None, rnd_lp=None, rnd_doc=None, rnd_der=None, rnd_dur=None):
        cola_d = ", ".join(
            f"C{c}({'P' if camiones[c].tipo=='Perecedera' else 'G'})" for c in cola_doc
        ) or "-"
        cola_f = ", ".join(f"C{c}" for c in cola_fis) or "-"
        return {
            "Iter":          iteracion,
            "Hora":          min2hhmm(reloj),
            "Evento":        evento,
            "Próximos":      proximos(),
            # Puestos doc
            "PD1":           "Libre" if puestos_doc[0].libre else f"C{puestos_doc[0].camion_id}",
            "PD1 Fin":       min2hhmm(puestos_doc[0].t_fin),
            "PD2":           "Libre" if puestos_doc[1].libre else f"C{puestos_doc[1].camion_id}",
            "PD2 Fin":       min2hhmm(puestos_doc[1].t_fin),
            "PD3":           "Libre" if puestos_doc[2].libre else f"C{puestos_doc[2].camion_id}",
            "PD3 Fin":       min2hhmm(puestos_doc[2].t_fin),
            "Cola Doc":      cola_d,
            "Lon CD":        len(cola_doc),
            # Puesto físico
            "PF Estado":     "Libre" if puesto_fis.libre else f"C{puesto_fis.camion_id}",
            "PF Fin":        min2hhmm(puesto_fis.t_fin),
            "Cola Fís":      cola_f,
            # Auxiliares
            "En Recinto":    en_recinto(),
            "Máx Recinto":   max_recinto,
            "Acum Esp Gen":  round(esp_gen, 2),
            "Acum Esp Per":  round(esp_per, 2),
            # RNDs
            "RND Lleg Gen":  rnd_lg  if rnd_lg  is not None else "",
            "RND Lleg Per":  rnd_lp  if rnd_lp  is not None else "",
            "RND Doc":       rnd_doc if rnd_doc is not None else "",
            "RND Deriva Fís":rnd_der if rnd_der is not None else "",
            "RND Dur Fís":   rnd_dur if rnd_dur is not None else "",
        }

    while iteracion < MAX_ITER:
        cands = []
        if not cierre:
            cands += [("llegada_gen", t_prox_gen), ("llegada_per", t_prox_per)]
        for p in puestos_doc:
            if not p.libre: cands.append((f"fin_doc_{p.id}", p.t_fin))
        if not puesto_fis.libre: cands.append(("fin_fis", puesto_fis.t_fin))
        if not cands: break

        tipo_evt, reloj = min(cands, key=lambda x: x[1])
        if reloj >= HORA_CIERRE and not cierre: cierre = True
        if reloj > t_max: break
        iteracion += 1

        rnd_lg = rnd_lp = rnd_doc = rnd_der = rnd_dur = None

        if tipo_evt == "llegada_gen":
            if not cierre:
                id_counter += 1
                camiones[id_counter] = Camion(id_counter, "General", reloj)
                cnt_gen += 1
                rnd_lg = rnd_prox_gen
                dt, rnd_prox_gen = exp_neg(media_gen)
                t_prox_gen = reloj + dt
                if any(p.libre for p in puestos_doc) and not cola_doc:
                    rnd_doc = ocupar_doc(id_counter, reloj)
                else:
                    cola_doc.append(id_counter)
                max_recinto = max(max_recinto, en_recinto())

        elif tipo_evt == "llegada_per":
            if not cierre:
                id_counter += 1
                camiones[id_counter] = Camion(id_counter, "Perecedera", reloj)
                cnt_per += 1
                rnd_lp = rnd_prox_per
                dt, rnd_prox_per = exp_neg(media_per)
                t_prox_per = reloj + dt
                if any(p.libre for p in puestos_doc) and not cola_doc:
                    rnd_doc = ocupar_doc(id_counter, reloj)
                else:
                    cola_doc.insert(0, id_counter)
                max_recinto = max(max_recinto, en_recinto())

        elif tipo_evt.startswith("fin_doc_"):
            pid = int(tipo_evt.split("_")[-1])
            p   = puestos_doc[pid - 1]
            cid = p.camion_id
            cam = camiones[cid]
            espera = cam.t_ini_doc - cam.t_llegada
            if cam.tipo == "General": esp_gen += espera
            else:                     esp_per += espera
            p.libre = True; p.camion_id = None; p.t_fin = None
            rnd_der = round(random.random(), 4)
            if rnd_der < prob_fis:
                if puesto_fis.libre: rnd_dur = ocupar_fis(cid, reloj)
                else:                cola_fis.append(cid)
            else:
                cam.en_sistema = False
            if cola_doc:
                idx = next((i for i,c in enumerate(cola_doc)
                            if camiones[c].tipo=="Perecedera"), 0)
                rnd_doc = ocupar_doc(cola_doc.pop(idx), reloj)

        elif tipo_evt == "fin_fis":
            cid = puesto_fis.camion_id
            t_fis_ocup += puesto_fis.t_fin - (camiones[cid].t_ini_fis or reloj)
            puesto_fis.libre = True; puesto_fis.camion_id = None; puesto_fis.t_fin = None
            camiones[cid].en_sistema = False
            if cola_fis:
                rnd_dur = ocupar_fis(cola_fis.pop(0), reloj)

        filas.append(snap(tipo_evt.replace("_"," ").title(),
                          rnd_lg, rnd_lp, rnd_doc, rnd_der, rnd_dur))

    t_total = max(reloj - HORA_APERTURA, 1)
    stats = {
        "Iteraciones totales": iteracion,
        "Tiempo simulado":     min2hhmm(reloj),
        "Camiones General":    cnt_gen,
        "Camiones Perecedera": cnt_per,
        "Esp. prom. General (min)":    round(esp_gen / cnt_gen, 2) if cnt_gen else 0,
        "Esp. prom. Perecedera (min)": round(esp_per / cnt_per, 2) if cnt_per else 0,
        "Utiliz. Física (%)":  round((t_fis_ocup / t_total) * 100, 2),
        "Máx. en recinto":     max_recinto,
    }
    return filas, stats

# ─────────────────────────────────────────────
#  INTERFAZ STREAMLIT
# ─────────────────────────────────────────────
st.title("🚛 Simulación Aduana de Camiones")

# ── Sidebar: parámetros ───────────────────────
with st.sidebar:
    st.header("⚙️ Parámetros")
    st.subheader("Tiempo")
    t_sim   = st.number_input("Tiempo a simular (min)", 60, 1440, 720, 60)
    j_iter  = st.number_input("Mostrar desde iteración j", 1, MAX_ITER, 1, 1)
    i_iter  = st.number_input("Cantidad de iteraciones i", 1, 500, 30, 10)

    st.subheader("Llegadas")
    media_gen = st.number_input("Media Carga General (min)", 1.0, 120.0, 15.0, 1.0)
    media_per = st.number_input("Media Carga Perecedera (min)", 1.0, 120.0, 40.0, 1.0)

    st.subheader("Control Documental")
    tdoc_min = st.number_input("Tiempo Doc. Mín (min)", 1.0, 60.0, 10.0, 1.0)
    tdoc_max = st.number_input("Tiempo Doc. Máx (min)", 1.0, 60.0, 15.0, 1.0)

    st.subheader("Revisión Física")
    prob_fis = st.slider("% Derivación a Física", 0, 100, 15) / 100
    tfis_min = st.number_input("Tiempo Fís. Mín (min)", 1.0, 120.0, 30.0, 1.0)
    tfis_max = st.number_input("Tiempo Fís. Máx (min)", 1.0, 120.0, 60.0, 1.0)

    simular_btn = st.button("▶ Simular", type="primary", use_container_width=True)

# ── Ejecución ────────────────────────────────
if simular_btn:
    with st.spinner("Simulando..."):
        filas, stats = simular(t_sim, media_gen, media_per, prob_fis,
                               tdoc_min, tdoc_max, tfis_min, tfis_max)

    # ── Métricas ─────────────────────────────
    st.subheader("📊 Resultados")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Esp. prom. General",    f"{stats['Esp. prom. General (min)']} min")
    c2.metric("Esp. prom. Perecedera", f"{stats['Esp. prom. Perecedera (min)']} min")
    c3.metric("Utilización Física",    f"{stats['Utiliz. Física (%)']}%")
    c4.metric("Máx. en recinto",       stats['Máx. en recinto'])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Iteraciones",      stats['Iteraciones totales'])
    c6.metric("Tiempo simulado",  stats['Tiempo simulado'])
    c7.metric("Cam. General",     stats['Camiones General'])
    c8.metric("Cam. Perecedera",  stats['Camiones Perecedera'])

    # ── Fila final ───────────────────────────
    st.subheader("🏁 Fila final del vector de estado")
    fila_final = filas[-1].copy()
    for k in ["RND Lleg Gen","RND Lleg Per","RND Doc","RND Deriva Fís","RND Dur Fís"]:
        fila_final[k] = "-"
    st.dataframe(pd.DataFrame([fila_final]), use_container_width=True, hide_index=True)

    # ── Vector de estado filtrado ─────────────
    st.subheader(f"📋 Vector de estado — iteraciones {j_iter} a {j_iter + i_iter - 1}")

    inicio = max(0, j_iter - 1)
    df = pd.DataFrame(filas[inicio: inicio + i_iter])

    # Columnas RND resaltadas con colores usando styler
    def colorear(df):
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for col in ["RND Lleg Gen", "RND Lleg Per"]:
            if col in df.columns:
                styles[col] = df[col].apply(
                    lambda v: "background-color:#3a2e00; color:#f9e2af" if v != "" else "")
        if "RND Doc" in df.columns:
            styles["RND Doc"] = df["RND Doc"].apply(
                lambda v: "background-color:#003a1e; color:#a6e3a1" if v != "" else "")
        for col in ["RND Deriva Fís", "RND Dur Fís"]:
            if col in df.columns:
                styles[col] = df[col].apply(
                    lambda v: "background-color:#3a1000; color:#f38ba8" if v != "" else "")
        return styles

    styled = df.style.apply(colorear, axis=None)
    st.dataframe(styled, use_container_width=True, hide_index=True, height=600)

    # ── Leyenda ──────────────────────────────
    st.caption(
        "🟡 RND Llegadas &nbsp;&nbsp; "
        "🟢 RND Atención Documental &nbsp;&nbsp; "
        "🔴 RND Revisión Física"
    )

    # ── Exportar CSV ─────────────────────────
    st.subheader("💾 Exportar")
    csv_data = pd.DataFrame(filas).to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Descargar vector completo (CSV)",
        data=csv_data,
        file_name="aduana_simulacion.csv",
        mime="text/csv",
        use_container_width=True,
    )