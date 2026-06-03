# Simulación de Aduana de Camiones

Aplicación desarrollada en **Python** con **Streamlit** para simular el ingreso, procesamiento y egreso de camiones en una aduana fronteriza mediante un modelo de **simulación por eventos discretos**.

La versión principal del proyecto es el archivo:

```bash
tp4sim_corregido.py
```

Este archivo contiene la simulación corregida, donde se modela de forma más realista el funcionamiento de la aduana: apertura diaria, cierre de ventana operativa, continuidad de atención para los camiones que ya ingresaron, cálculo de tiempo activo y métricas finales del sistema.

---

## Descripción del proyecto

El sistema representa una aduana de camiones que opera durante una ventana horaria definida por el usuario. Durante ese período pueden ingresar camiones al sistema. Una vez cerrada la ventana, ya no se permiten nuevas llegadas, pero los camiones que quedaron dentro continúan siendo atendidos hasta que el sistema queda vacío.

Los camiones ingresan según distribuciones de probabilidad, esperan para ser atendidos en el control documental y, luego de finalizar esa etapa, pueden ser derivados aleatoriamente a una revisión física. La simulación permite observar la evolución del sistema mediante un vector de estado, gráficos de análisis y métricas operativas.

---

## Versión corregida

La versión corregida mejora la lógica temporal de la simulación. En lugar de finalizar simplemente al llegar a un tiempo fijo X, el programa trabaja con días de operación, ventanas horarias y cierre real del sistema.

Esto permite representar mejor el funcionamiento de una aduana real:

- la aduana abre en un horario determinado;
- durante la ventana operativa ingresan camiones;
- al cerrar la ventana, dejan de generarse nuevas llegadas;
- los camiones que ya ingresaron siguen siendo atendidos (overtime);
- la simulación finaliza cuando se cumple la cantidad de días definida y el sistema queda vacío.

### Características principales

- Simulación por eventos discretos.
- Llegadas de camiones con distribución exponencial negativa.
- Tiempos de atención documental y física con distribución uniforme.
- Diferenciación entre camiones de carga general (CCG) y carga perecedera (CCP).
- Prioridad para camiones con carga perecedera en el control documental.
- Cantidad parametrizable de tipos de camiones.
- Cantidad parametrizable de puestos documentales.
- Cantidad parametrizable de fosas de revisión física.
- Definición de inicio y fin de ventana operativa diaria (en minutos del día, 0–1440).
- Simulación de uno o varios días consecutivos.
- Cierre de ventana sin eliminar camiones ya ingresados.
- Atención de camiones pendientes luego del cierre (overtime).
- Cálculo de tiempo activo del sistema (ventana operativa efectiva + overtime, sin contar noches ociosas).
- Cálculo de utilización de fosa sobre tiempo activo real.
- Registro completo del vector de estado con MultiIndex.
- Visualización de números aleatorios utilizados.
- Colores en el vector de estado según tipo de evento y tipo de camión.
- Leyenda visual para interpretar los eventos.
- Gráficos de evolución del sistema (camiones en sistema, colas documentales, cola de fosa).
- Opción para mostrar todas las filas o solo una parte del vector.
- Filtro por minuto de inicio de visualización.

### Eventos modelados

La simulación trabaja avanzando de evento en evento. Los principales eventos son:

- Inicio de simulación.
- Apertura de día.
- Llegada de camión con carga general.
- Llegada de camión con carga perecedera.
- Fin de revisión documental.
- Fin de revisión física.
- Cierre de ventana operativa.
- Fin de simulación.
- Corte por límite de iteraciones.

El reloj de simulación no avanza minuto por minuto, sino que salta directamente al próximo evento más cercano.

### Objetos del sistema

#### Camiones

Los camiones son objetos temporales: ingresan al sistema, cambian de estado y luego salen.

Cada camión registra:

- ID del camión.
- Tipo de carga.
- Hora de llegada.
- Hora de inicio de atención documental.
- Estado actual.

Estados posibles:

| Estado | Descripción |
|---|---|
| En cola documental | Esperando puesto libre |
| En revisión documental | Siendo atendido en un puesto |
| En cola física | Esperando fosa libre |
| En revisión física | Siendo inspeccionado en una fosa |
| Destruido | Ya salió del sistema |

#### Puestos documentales

Los puestos documentales son recursos permanentes del sistema. Cada puesto puede estar libre u ocupado, y registra el camión asignado y la hora de fin de atención.

#### Fosas de revisión física

Las fosas también son recursos permanentes. Se utilizan cuando un camión es derivado a revisión física. Registran la hora de inicio y fin de ocupación para el cálculo de utilización.

### Métricas obtenidas

| Métrica | Fórmula |
|---|---|
| Espera promedio por tipo | ACU espera / cantidad atendida documentalmente |
| Utilización de fosa | ACU tiempo ocupado / ACU tiempo activo × 100 |
| Máximo de camiones simultáneos | Mayor valor registrado en el contador de camiones en sistema |

El denominador de utilización es el **tiempo activo** (suma de ventanas operativas efectivas más overtime de cada día), excluyendo los períodos nocturnos ociosos entre días.

### Vector de estado

El vector de estado muestra una fila por cada evento procesado. Entre los datos mostrados se incluyen:

- Evento actual y próximo evento.
- Reloj de simulación.
- Números aleatorios utilizados.
- Próximas llegadas por tipo.
- Colas documentales por tipo.
- Estado, demoras y fins de los puestos documentales.
- Decisión y cola de revisión física.
- Estado, demoras y fins de las fosas.
- Acumuladores y contadores del sistema.
- Camiones activos en el sistema.

### Gráficos de análisis

Al finalizar la simulación se generan tres gráficos de línea:

1. **Camiones en sistema**: evolución de la cantidad de camiones simultáneos. Permite detectar congestión y el pico máximo.
2. **Colas documentales**: evolución de las colas por tipo de camión. Permite verificar el efecto de la prioridad CCP sobre CCG.
3. **Cola de fosa**: evolución de la cola de revisión física. Permite detectar si la fosa es el cuello de botella del sistema.

### Parametrización

Desde la barra lateral de Streamlit el usuario puede configurar:

- Cantidad máxima de iteraciones (N).
- Semilla aleatoria (opcional).
- Cantidad de tipos de clientes y sus parámetros (código, nombre, media de llegada, prioridad documental).
- Cantidad de puestos documentales.
- Tiempos mínimo y máximo de revisión documental.
- Cantidad de fosas de revisión física.
- Probabilidad de revisión física.
- Tiempos mínimo y máximo de revisión física.
- Cantidad de días a simular.
- Inicio y fin de ventana operativa (minutos del día, 0–1440).
- Cantidad de filas a mostrar en el vector (o mostrar todas).
- Minuto desde el cual visualizar el vector.

### Tecnologías utilizadas

- Python
- Streamlit
- Pandas
- Dataclasses
- Random
- Math

### Instalación

Instalar las dependencias necesarias:

```bash
pip install streamlit pandas
```

### Ejecución de la versión corregida

Para iniciar la versión corregida de la aplicación, ejecutar:

```bash
python -m streamlit run tp4sim_corregido.py
```

Luego de ejecutar el comando, Streamlit abrirá la aplicación en el navegador.

---

## Versión anterior

El archivo antiguo del proyecto es:

```bash
tp4-sim.py
```

Esta versión contiene la primera implementación de la simulación. Modela las llegadas, colas, atención documental, revisión física y métricas principales, pero trabaja con una **lógica de tiempo total fijo**: la simulación avanza hasta un tiempo X definido por el usuario y luego se detiene, sin contemplar apertura y cierre de ventana como eventos diferenciados.

La versión anterior puede ejecutarse con:

```bash
python -m streamlit run tp4-sim.py
```

Actualmente se recomienda utilizar la versión corregida, ya que representa mejor el cierre de ventana operativa, la atención de camiones pendientes y el cálculo de utilización sobre tiempo activo real.

### Diferencias respecto a la versión corregida

| Aspecto | Versión anterior (`tp4-sim.py`) | Versión corregida (`tp4sim_corregido.py`) |
|---|---|---|
| Criterio de parada | Tiempo total fijo X | Sistema vacío después del último cierre |
| Ventana operativa | Solo cierre (`ventana_fin`) | Inicio y fin parametrizables por día |
| Multi-día | No | Sí, con cantidad de días parametrizable |
| Llegadas iniciales | Se generan desde el minuto 0 | Se generan al abrir la ventana (evento Apertura) |
| Denominador de métricas | Tiempo total simulado (incluye noches) | Tiempo activo real (ventana + overtime) |
| Colores en vector | No | Sí, por tipo de evento y tipo de camión |
| Gráficos | No | Sí (3 gráficos de evolución) |
| Mostrar todas las filas | No | Sí |
| Sección camiones activos | Sí | Eliminada |
| Exportación CSV | Sí | Eliminada |

### Características de la versión anterior

- Simulación por eventos discretos con tiempo total fijo X.
- Llegadas de camiones con distribución exponencial negativa desde el minuto 0.
- Tiempos de atención con distribución uniforme.
- Dos tipos de camiones parametrizables: carga general (CCG) y carga perecedera (CCP).
- Prioridad para CCP en el control documental.
- Puestos documentales y fosas parametrizables.
- Derivación aleatoria de camiones a revisión física.
- Registro del vector de estado.
- Visualización de números aleatorios.
- Cálculo de métricas finales con denominador de tiempo total.
- Sección de camiones activos al finalizar.
- Exportación del vector de estado en formato CSV.

---

## Contexto académico

Este proyecto fue desarrollado como parte de un trabajo práctico de la materia **Simulación**, con el objetivo de aplicar conceptos de simulación por eventos discretos, variables aleatorias, colas, servidores, acumuladores y análisis de métricas de desempeño.

---

### Enunciado: Aduana de Camiones

La aduana fronteriza procesa el ingreso de camiones en una ventana operativa de **07:00 a 19:00 horas**. Al cierre, los camiones que ya están en la fila de control documental son procesados, pero se rechaza cualquier llegada posterior.

Arriban dos tipos de cargas:

- **Carga General (CCG):** frecuencia exponencial negativa con media de 15 minutos.
- **Carga Perecedera (CCP):** frecuencia exponencial negativa con media de 40 minutos.

El control consta de dos etapas:

**Control Documental**
- Hay tres puestos de atención.
- Los camiones con carga perecedera tienen prioridad absoluta en la fila.
- El tiempo de revisión es uniforme entre 10 y 15 minutos.

**Revisión Física**
- Al finalizar el control documental, el 15% de todos los camiones es derivado a una fosa de inspección profunda (un solo servidor).
- Demora entre 30 y 60 minutos con distribución uniforme.
- En esta instancia no existen prioridades por tipo de carga.

**Objetivos de la simulación:**

- Tiempo de espera promedio diferenciado para camiones de carga general y perecedera en el control documental.
- Porcentaje de utilización del puesto de revisión física.
- Cantidad máxima de camiones que se acumularon simultáneamente en el recinto aduanero.

---

### Consignas de la actividad

#### Parte A — Análisis y definición del sistema

Entregar un documento con el análisis y las definiciones del sistema que incluya:

- **Identificación de objetos:** nombre, características, atributos (nombre, estado y resto de atributos necesarios, cada uno con sus valores posibles).
- **Determinación de eventos.**
- **Colas existentes en el sistema** y características.
- **Variables aleatorias del sistema:** indicar la fórmula que se utiliza para generar valores para cada variable, reemplazando la fórmula teórica por la que corresponda en cada caso.

#### Parte B — Desarrollo del aplicativo

Desarrollar un aplicativo que efectúe la simulación del sistema con las siguientes pautas:

- Se deberá simular **X tiempo** (parámetro solicitado al inicio) generando **N cantidad de iteraciones** en total. El aplicativo debe permitir simular hasta 100000 iteraciones del vector de estado o hasta el tiempo X, lo que ocurra primero.
- Se deberá mostrar en el vector de estado **i iteraciones a partir de una hora j** (valores i y j ingresados por parámetro).
- Se deberá mostrar en el vector de estado la **última fila de simulación**, es decir la fila correspondiente al instante X. En esta fila no es necesario mostrar los objetos temporales.
- Todos los valores en rojo deben ser parametrizables.
- El vector de estado debe mostrar como mínimo:
  - hora simulada;
  - nombre del evento simulado;
  - próximos eventos a ejecutarse;
  - objetos considerados en la simulación, cada uno con sus atributos (nombre, estado y otros atributos necesarios);
  - variables auxiliares (acumuladores, contadores, etc.).
- Para cada variable aleatoria de la simulación se debe mostrar el **número aleatorio** que se usó para determinar su valor.
- El vector de estado debe permitir conocer, a partir de una hora j y durante i iteraciones, el valor de todos los atributos de los objetos presentes en el sistema en cualquier instante de ese intervalo. No es necesario mostrar los objetos que ya dejaron de existir en el sistema.
- Plantear las **fórmulas necesarias** para responder lo que se desea averiguar con la simulación, y el resultado para la simulación efectuada.
