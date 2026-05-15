# Simulación de Aduana de Camiones

Aplicación desarrollada en **Python** con **Streamlit** para simular el ingreso y procesamiento de camiones en una aduana fronteriza mediante un modelo de **simulación por eventos discretos**.

El sistema contempla camiones con **carga general** y **carga perecedera**, control documental con prioridad para perecederos, revisión física aleatoria y cálculo de métricas operativas del sistema.

---

## Descripción del proyecto

Este proyecto simula el funcionamiento de una aduana de camiones que opera durante una ventana horaria determinada.

Los camiones ingresan al sistema según distribuciones de probabilidad, esperan para ser atendidos en el control documental y, luego de finalizar esa etapa, pueden ser derivados a una revisión física. La simulación permite observar la evolución del sistema mediante un vector de estado y obtener indicadores de desempeño.

---

## Características principales

- Simulación de llegadas de camiones con distribución exponencial negativa.
- Diferenciación entre camiones de carga general y carga perecedera.
- Prioridad para camiones con carga perecedera en el control documental.
- Tres puestos de atención para el control documental.
- Revisión física con un único puesto de inspección.
- Derivación aleatoria de camiones a revisión física.
- Registro del vector de estado de la simulación.
- Visualización de números aleatorios utilizados.
- Cálculo de métricas finales del sistema.
- Exportación del vector de estado en formato CSV.

---

## Métricas obtenidas

La aplicación permite calcular:

- Tiempo de espera promedio de camiones con carga general en el control documental.
- Tiempo de espera promedio de camiones con carga perecedera en el control documental.
- Porcentaje de utilización del puesto de revisión física.
- Cantidad máxima de camiones acumulados simultáneamente en el recinto aduanero.
- Cantidad total de camiones ingresados por tipo de carga.
- Cantidad total de iteraciones simuladas.

---

## Tecnologías utilizadas

- Python
- Streamlit
- Pandas
- Dataclasses
- Random
- Math

---

## Instalación
Instalar las dependencias necesarias:

```bash
pip install streamlit pandas
```

---

## Ejecución

Para iniciar la aplicación, ejecutar:

```bash
python -m streamlit run tp4-sim.py```

Luego de ejecutar el comando, Streamlit abrirá la aplicación en el navegador.

---

## Contexto académico

Este proyecto fue desarrollado como parte de un trabajo práctico de la materia **Simulación**, con el objetivo de aplicar conceptos de simulación por eventos discretos, variables aleatorias, colas, servidores, acumuladores y análisis de métricas de desempeño.

---
