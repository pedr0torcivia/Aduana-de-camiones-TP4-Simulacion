import streamlit as st
import random
import math
from dataclasses import dataclass
from typing import Optional
import pandas as pd

st.set_page_config(page_title="Aduana de Camiones", layout="wide")

HORA_APERTURA = 7 * 60   # 420 min
HORA_CIERRE   = 19 * 60  # 1140 min
MAX_ITER      = 100_000

def min2hhmm(m):
    if m is None: return "-"
    return f"{int(m)//60:02d}:{int(m)%60:02d}"

def hhmm2min(s):
    """'07:30' -> 450"""
    h, m = s.split(":")
    return int(h) * 60 + int(m)

def exp_neg(media):
    r = random.random()
    while r == 0: r = random.random()
    return -media * math.log(r), round(r, 4)

def uniforme(a, b):
    r = random.random()
    return a + (b - a) * r, round(r, 4)

@dataclass
class Camion:
    id: int
    tipo: str           # "General" | "Perecedera"
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
    t_ini: Optional[float] = None   # para acumular aunque corte ocupado

# ─────────────────────────────────────────────
#  MOTOR
# ─────────────────────────────────────────────
def simular(t_sim_min, n_iter_max,
            media_gen, media_per, prob_fis,
            tdoc_min, tdoc_max, tfis_min, tfis_max):

    t_max = HORA_APERTURA + t_sim_min

    reloj = float(HORA_APERTURA)
    camiones: dict[int, Camion] = {}
    # Cola doc: lista de (orden_llegada, cam_id, tipo)
    # Perecederas tienen prioridad; dentro de cada tipo, FIFO por orden_llegada
    cola_doc: list[tuple[int,int,str]] = []   # (seq, id, tipo)
    puestos_doc = [PuestoDoc(i) for i in range(1, 4)]
    puesto_fis  = PuestoFis()
    cola_fis: list[int] = []

    dt, rnd_prox_gen = exp_neg(media_gen)
    t_prox_gen = HORA_APERTURA + dt
    dt, rnd_prox_per = exp_neg(media_per)
    t_prox_per = HORA_APERTURA + dt

    id_counter  = 0
    seq_cola    = 0     # orden de llegada a la cola
    iteracion   = 0
    cierre      = False

    esp_gen_acum = esp_per_acum = 0.0
    cnt_doc_gen  = cnt_doc_per  = 0   # camiones que TERMINARON doc (para espera correcta)
    cnt_gen      = cnt_per      = 0
    t_fis_ocup   = 0.0
    max_recinto  = 0

    filas: list[dict] = []

    def en_recinto():
        return sum(1 for c in camiones.values() if c.en_sistema)

    def siguiente_cola_doc():
        """FIFO con prioridad: primero perecederas (por seq), luego generales (por seq)."""
        pec = [(s,cid) for s,cid,t in cola_doc if t == "Perecedera"]
        gen = [(s,cid) for s,cid,t in cola_doc if t == "General"]
        if pec:
            _, cid = min(pec)
        elif gen:
            _, cid = min(gen)
        else:
            return None
        cola_doc[:] = [(s,c,t) for s,c,t in cola_doc if c != cid]
        return cid

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
        puesto_fis.libre = False
        puesto_fis.camion_id = cid
        puesto_fis.t_fin  = t + dur
        puesto_fis.t_ini  = t
        camiones[cid].t_ini_fis = t
        camiones[cid].t_fin_fis = puesto_fis.t_fin
        return rf

    def proximos_str():
        evts = []
        if not cierre:
            evts += [("Lleg.Gen", t_prox_gen), ("Lleg.Per", t_prox_per)]
        for p in puestos_doc:
            if not p.libre: evts.append((f"FinDoc P{p.id}", p.t_fin))
        if not puesto_fis.libre: evts.append(("FinFís", puesto_fis.t_fin))
        return "; ".join(f"{n}@{min2hhmm(t)}" for n,t in sorted(evts, key=lambda x:x[1])[:5])

    def snap(evento, rnd_lg=None, rnd_lp=None,
             rnd_doc=None, rnd_der=None, rnd_dur=None):
        # Mostrar en orden de prioridad: perecederas primero (por seq), luego generales (por seq)
        pec_vis = [(s,cid,tp) for s,cid,tp in cola_doc if tp == "Perecedera"]
        gen_vis = [(s,cid,tp) for s,cid,tp in cola_doc if tp == "General"]
        cola_d = ", ".join(
            f"C{cid}({'P' if tp=='Perecedera' else 'G'})"
            for _,cid,tp in sorted(pec_vis) + sorted(gen_vis)
        ) or "-"
        cola_f = ", ".join(f"C{c}" for c in cola_fis) or "-"
        er = en_recinto()
        return {
            "Iter":           iteracion,
            "Hora":           min2hhmm(reloj),
            "Evento":         evento,
            "Próximos":       proximos_str(),
            "PD1":            "Libre" if puestos_doc[0].libre else f"C{puestos_doc[0].camion_id}",
            "PD1 Fin":        min2hhmm(puestos_doc[0].t_fin),
            "PD2":            "Libre" if puestos_doc[1].libre else f"C{puestos_doc[1].camion_id}",
            "PD2 Fin":        min2hhmm(puestos_doc[1].t_fin),
            "PD3":            "Libre" if puestos_doc[2].libre else f"C{puestos_doc[2].camion_id}",
            "PD3 Fin":        min2hhmm(puestos_doc[2].t_fin),
            "Cola Doc":       cola_d,
            "Lon CD":         len(cola_doc),
            "PF Estado":      "Libre" if puesto_fis.libre else f"C{puesto_fis.camion_id}",
            "PF Fin":         min2hhmm(puesto_fis.t_fin),
            "Cola Fís":       cola_f,
            # RNDs que GENERARON este evento (llegada anterior)
            "RND Lleg Gen":   rnd_lg  if rnd_lg  is not None else "",
            "RND Lleg Per":   rnd_lp  if rnd_lp  is not None else "",
            # Estado del sistema resultante
            "En Recinto":     er,
            "Máx Recinto":    max_recinto,
            "Acum Esp Gen":   round(esp_gen_acum, 2),
            "Acum Esp Per":   round(esp_per_acum, 2),
            # RNDs que se usan DURANTE este evento
            "RND Doc":        rnd_doc if rnd_doc is not None else "",
            "RND Deriva Fís": rnd_der if rnd_der is not None else "",
            "RND Dur Fís":    rnd_dur if rnd_dur is not None else "",
        }

    # ── LOOP ────────────────────────────────────────────────
    while iteracion < min(n_iter_max, MAX_ITER):
        cands = []
        if not cierre:
            cands += [("llegada_gen", t_prox_gen), ("llegada_per", t_prox_per)]
        for p in puestos_doc:
            if not p.libre: cands.append((f"fin_doc_{p.id}", p.t_fin))
        if not puesto_fis.libre: cands.append(("fin_fis", puesto_fis.t_fin))
        if not cands: break

        tipo_evt, t_evt = min(cands, key=lambda x: x[1])

        # Cierre: rechazar llegadas >= 19:00, pero procesar todo lo que ya está
        if t_evt >= HORA_CIERRE and not cierre:
            cierre = True
        # Cortar solo si superamos t_max Y el evento NO es un fin de servicio
        # (para no dejar camiones colgados dentro del recinto al instante X)
        if t_evt > t_max and tipo_evt in ("llegada_gen", "llegada_per") and not cierre:
            break

        reloj = t_evt
        iteracion += 1
        rnd_lg = rnd_lp = rnd_doc = rnd_der = rnd_dur = None

        if tipo_evt == "llegada_gen":
            if not cierre:
                id_counter += 1; seq_cola += 1
                camiones[id_counter] = Camion(id_counter, "General", reloj)
                cnt_gen += 1
                rnd_lg = rnd_prox_gen
                dt, rnd_prox_gen = exp_neg(media_gen)
                t_prox_gen = reloj + dt
                if any(p.libre for p in puestos_doc) and not cola_doc:
                    rnd_doc = ocupar_doc(id_counter, reloj)
                else:
                    cola_doc.append((seq_cola, id_counter, "General"))
                max_recinto = max(max_recinto, en_recinto())

        elif tipo_evt == "llegada_per":
            if not cierre:
                id_counter += 1; seq_cola += 1
                camiones[id_counter] = Camion(id_counter, "Perecedera", reloj)
                cnt_per += 1
                rnd_lp = rnd_prox_per
                dt, rnd_prox_per = exp_neg(media_per)
                t_prox_per = reloj + dt
                if any(p.libre for p in puestos_doc) and not cola_doc:
                    rnd_doc = ocupar_doc(id_counter, reloj)
                else:
                    cola_doc.append((seq_cola, id_counter, "Perecedera"))
                max_recinto = max(max_recinto, en_recinto())

        elif tipo_evt.startswith("fin_doc_"):
            pid = int(tipo_evt.split("_")[-1])
            p   = puestos_doc[pid - 1]
            cid = p.camion_id
            cam = camiones[cid]
            espera = cam.t_ini_doc - cam.t_llegada
            if cam.tipo == "General":
                esp_gen_acum += espera; cnt_doc_gen += 1
            else:
                esp_per_acum += espera; cnt_doc_per += 1
            p.libre = True; p.camion_id = None; p.t_fin = None
            rnd_der = round(random.random(), 4)
            if rnd_der < prob_fis:
                if puesto_fis.libre: rnd_dur = ocupar_fis(cid, reloj)
                else:                cola_fis.append(cid)
            else:
                cam.en_sistema = False
            sig = siguiente_cola_doc()
            if sig is not None:
                rnd_doc = ocupar_doc(sig, reloj)

        elif tipo_evt == "fin_fis":
            cid = puesto_fis.camion_id
            t_fis_ocup += puesto_fis.t_fin - puesto_fis.t_ini
            puesto_fis.libre = True; puesto_fis.camion_id = None
            puesto_fis.t_fin = None; puesto_fis.t_ini = None
            camiones[cid].en_sistema = False
            if cola_fis:
                rnd_dur = ocupar_fis(cola_fis.pop(0), reloj)

        # Llegadas con cierre=True son rechazadas; etiquetar como cierre
        nombre_evt = tipo_evt.replace("_", " ").title()
        if cierre and tipo_evt in ("llegada_gen", "llegada_per"):
            nombre_evt = "Cierre Aduana"
        filas.append(snap(nombre_evt, rnd_lg, rnd_lp, rnd_doc, rnd_der, rnd_dur))

    # ── Acumular tiempo físico si quedó ocupado al cortar ───
    if not puesto_fis.libre and puesto_fis.t_ini is not None:
        t_fis_ocup += reloj - puesto_fis.t_ini

    t_total = max(reloj - HORA_APERTURA, 1)
    stats = {
        "Iteraciones totales":         iteracion,
        "Tiempo simulado":             min2hhmm(reloj),
        "Camiones General":            cnt_gen,
        "Camiones Perecedera":         cnt_per,
        "Esp. prom. General (min)":    round(esp_gen_acum / cnt_doc_gen, 2) if cnt_doc_gen else 0,
        "Esp. prom. Perecedera (min)": round(esp_per_acum / cnt_doc_per, 2) if cnt_doc_per else 0,
        "Utiliz. Física (%)":          round((t_fis_ocup / t_total) * 100, 2),
        "Máx. en recinto":             max_recinto,
    }
    return filas, stats

# ─────────────────────────────────────────────
#  INTERFAZ
# ─────────────────────────────────────────────
st.title("🚛 Simulación Aduana de Camiones")

with st.sidebar:
    st.header("⚙️ Parámetros")

    st.subheader("Tiempo y corte")
    t_sim    = st.number_input("Tiempo a simular (min)", 60, 1440, 720, 60)
    n_iter   = st.number_input("Máximo de iteraciones N", 1, MAX_ITER, MAX_ITER, 1000)

    st.subheader("Filtro del vector de estado")
    hora_j   = st.text_input("Mostrar desde hora j (HH:MM)", "07:00")
    i_iter   = st.number_input("Cantidad de iteraciones i a mostrar", 1, 500, 30, 10)

    st.subheader("Llegadas")
    media_gen = st.number_input("Media Carga General (min)", 1.0, 120.0, 15.0, 1.0)
    media_per = st.number_input("Media Carga Perecedera (min)", 1.0, 120.0, 40.0, 1.0)

    st.subheader("Control Documental")
    tdoc_min = st.number_input("T. Doc. Mín (min)", 1.0, 60.0, 10.0, 1.0)
    tdoc_max = st.number_input("T. Doc. Máx (min)", 1.0, 60.0, 15.0, 1.0)

    st.subheader("Revisión Física")
    prob_fis = st.slider("% Derivación a Física", 0, 100, 15) / 100
    tfis_min = st.number_input("T. Fís. Mín (min)", 1.0, 120.0, 30.0, 1.0)
    tfis_max = st.number_input("T. Fís. Máx (min)", 1.0, 120.0, 60.0, 1.0)

    simular_btn = st.button("▶ Simular", type="primary", use_container_width=True)

if simular_btn:
    with st.spinner("Simulando..."):
        filas, stats = simular(t_sim, n_iter, media_gen, media_per, prob_fis,
                               tdoc_min, tdoc_max, tfis_min, tfis_max)

    # ── Métricas ─────────────────────────────
    st.subheader("📊 Resultados")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Esp. prom. General",    f"{stats['Esp. prom. General (min)']} min")
    c2.metric("Esp. prom. Perecedera", f"{stats['Esp. prom. Perecedera (min)']} min")
    c3.metric("Utilización Física",    f"{stats['Utiliz. Física (%)']}%")
    c4.metric("Máx. en recinto",       stats['Máx. en recinto'])

    c5,c6,c7,c8 = st.columns(4)
    c5.metric("Iteraciones",     stats['Iteraciones totales'])
    c6.metric("Tiempo simulado", stats['Tiempo simulado'])
    c7.metric("Cam. General",    stats['Camiones General'])
    c8.metric("Cam. Perecedera", stats['Camiones Perecedera'])

    df_all = pd.DataFrame(filas)

    # ── Fila final al instante X (sin objetos temporales) ──
    st.subheader("🏁 Fila final — instante de corte")
    fila_final = df_all.iloc[-1].copy()
    for col in ["RND Lleg Gen","RND Lleg Per","RND Doc","RND Deriva Fís","RND Dur Fís",
                "PD1","PD1 Fin","PD2","PD2 Fin","PD3","PD3 Fin",
                "PF Estado","PF Fin","Cola Doc","Cola Fís"]:
        fila_final[col] = "-"
    st.dataframe(pd.DataFrame([fila_final]), use_container_width=True, hide_index=True)

    # ── Vector de estado desde hora j ────────
    st.subheader(f"📋 Vector de estado — desde {hora_j}, {i_iter} iteraciones")
    try:
        t_j = hhmm2min(hora_j)
        df_desde = df_all[df_all["Hora"] >= min2hhmm(t_j)].head(i_iter)
        if df_desde.empty:
            st.warning(f"No hay eventos a partir de {hora_j}.")
        else:
            def colorear(df):
                s = pd.DataFrame("", index=df.index, columns=df.columns)
                for col in ["RND Lleg Gen","RND Lleg Per"]:
                    if col in df.columns:
                        s[col] = df[col].apply(
                            lambda v: "background-color:#3a2e00;color:#f9e2af" if v != "" else "")
                if "RND Doc" in df.columns:
                    s["RND Doc"] = df["RND Doc"].apply(
                        lambda v: "background-color:#003a1e;color:#a6e3a1" if v != "" else "")
                for col in ["RND Deriva Fís","RND Dur Fís"]:
                    if col in df.columns:
                        s[col] = df[col].apply(
                            lambda v: "background-color:#3a1000;color:#f38ba8" if v != "" else "")
                return s

            st.dataframe(df_desde.style.apply(colorear, axis=None),
                         use_container_width=True, hide_index=True, height=600)
            st.caption("🟡 RND Llegadas  🟢 RND Doc  🔴 RND Física")
    except Exception:
        st.error("Formato de hora inválido. Usá HH:MM (ej: 09:30).")

    # ── Exportar ─────────────────────────────
    st.subheader("💾 Exportar")
    csv_data = df_all.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar vector completo (CSV)",
                       csv_data, "aduana_simulacion.csv", "text/csv",
                       use_container_width=True)