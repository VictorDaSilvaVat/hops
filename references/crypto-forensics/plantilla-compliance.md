# Plantilla: Informe de Compliance / Auditoría AML sobre Activos Digitales

Este informe NO es un dictamen pericial para autoridades judiciales. Es un
informe de auditoría de compliance/AML, orientado a sujetos obligados
(exchanges, VASPs, entidades financieras, fondos) para fundamentar
decisiones de onboarding, monitorización continua, EDD (Enhanced Due
Diligence) o reporte de operativa sospechosa (SAR/STR) ante la UIF/SEPBLAC
u organismo equivalente.

---

## SECCIÓN 1 — DATOS DEL INFORME

```
INFORME DE COMPLIANCE — ANÁLISIS DE RIESGO DE ACTIVOS VIRTUALES
Nº de referencia interno: [AÑO-CORRELATIVO]
Fecha de emisión: [DD de MMMM de YYYY]
Red analizada: [NOMBRE RED / TOKEN]
Dirección auditada: [DIRECCIÓN]
Entidad/sujeto obligado solicitante: [NOMBRE]
Motivo del análisis: [Onboarding KYC / Monitorización continua /
                      Alerta de transacción sospechosa / Offboarding /
                      Revisión periódica de cartera de riesgo]
Analista responsable: [NOMBRE]
```

---

## SECCIÓN 2 — RESUMEN EJECUTIVO Y CALIFICACIÓN DE RIESGO

```
CALIFICACIÓN DE RIESGO: [BAJO / MEDIO / ALTO / CRÍTICO]
PUNTUACIÓN: [0-100]

[Resumen de 1-2 párrafos: qué se ha analizado, el hallazgo principal, y
la calificación de riesgo resultante, en lenguaje directo apto para un
comité de riesgos o un oficial de cumplimiento que no es técnico.]
```

---

## SECCIÓN 3 — ALCANCE Y METODOLOGÍA

```
3.1 Alcance
    Dirección: [DIRECCIÓN]
    Red: [NOMBRE RED]
    Profundidad de rastreo: [N] hops
    Periodo analizado: [FECHA INICIO] – [FECHA FIN]
    Fuentes de datos: exploradores de blockchain públicos, base de datos
    interna de etiquetas de entidades (WalletExplorer y heurísticas
    propias), listas de sanciones (OFAC SDN, UE, ONU).

3.2 Metodología
    Análisis de grafo de transacciones (transaction graph analysis) con
    clasificación de contrapartes por tipo de entidad, cribado contra
    listas de sanciones, y detección automatizada de patrones asociados
    a blanqueo de capitales (mixing, peeling chains, fragmentación de
    importes).

3.3 Limitaciones
    - La clasificación de entidades depende de bases de datos de
      etiquetas públicas y heurísticas; puede haber contrapartes sin
      clasificar ("desconocido") que no implican necesariamente riesgo.
    - El análisis cubre un número limitado de hops; existe exposición
      indirecta más allá del alcance analizado que no queda reflejada.
    - Este informe es una herramienta de apoyo a la decisión de
      compliance, no sustituye el juicio profesional del oficial de
      cumplimiento ni constituye asesoramiento legal.
```

---

## SECCIÓN 4 — PERFIL DE LA DIRECCIÓN ANALIZADA

```
Dirección:              [DIRECCIÓN]
Total recibido:         [IMPORTE] [TOKEN]
Total enviado:          [IMPORTE] [TOKEN]
Direcciones únicas relacionadas: [N]
Primera actividad observada:     [FECHA / "No disponible"]
Última actividad observada:      [FECHA / "No disponible"]
Clasificación de entidad (si conocida): [exchange/mixer/individual/etc.]
```

---

## SECCIÓN 5 — CRIBADO DE SANCIONES Y LISTAS RESTRICTIVAS

```
Resultado: [SANCIONADO / SIN COINCIDENCIAS / NO VERIFICABLE]

[Si hay coincidencias, detallar cada una: lista de origen, nombre del
match, fecha de verificación. Si no se pudo verificar, indicarlo
expresamente — un resultado "no verificable" NO equivale a "limpio" y
debe tratarse con la debida cautela en la recomendación final.]
```

---

## SECCIÓN 6 — EXPOSICIÓN A CONTRAPARTES DE RIESGO

```
Se detalla a continuación la distribución del volumen transaccionado
por tipo de contraparte (exposición directa e indirecta dentro del
alcance analizado):

TIPO DE ENTIDAD          | % DEL VOLUMEN | NIVEL DE RIESGO
--------------------------|---------------|------------------
Exchange regulado         | [X]%          | Bajo
Mixer / servicio de mezcla| [X]%          | Alto
Sancionado                | [X]%          | Crítico
Darknet market            | [X]%          | Crítico
Casa de apuestas          | [X]%          | Medio
Servicio de wallet        | [X]%          | Bajo
Bridge / puente entre redes| [X]%         | Medio
Desconocido / individual  | [X]%          | Indeterminado

[Comentar cualquier concentración relevante, p.ej. "el 45% del volumen
saliente se dirige a una dirección clasificada como mixer".]
```

---

## SECCIÓN 7 — TIPOLOGÍAS Y SEÑALES DE ALERTA DETECTADAS

```
[Reportar ÚNICAMENTE las señales que los datos indiquen como detectadas.
No inventar señales que no consten en los datos proporcionados.]

7.1 Mixing / tumbling
    Detectado: [SÍ/NO] — Confianza: [X]%
    [Si sí, describir los indicadores: baja variación en importes,
    temporización regular, etc.]

7.2 Peeling chain (fragmentación progresiva)
    Detectado: [SÍ/NO] — Longitud máxima de cadena: [N]
    [Si sí, describir el patrón observado.]

7.3 Otras señales
    [Reutilización de direcciones, velocidad de movimiento anómala,
    fragmentación bajo umbrales de reporte, etc. — solo si constan en
    los datos.]
```

---

## SECCIÓN 8 — EVALUACIÓN CUANTITATIVA DE RIESGO

```
Los siguientes valores se han calculado directamente a partir de los
datos on-chain (no son una estimación de la IA):

Factor                          | Puntuación | Peso
---------------------------------|-----------|------
Exposición a contrapartes de riesgo | [X]     | [X]
Resultado de cribado de sanciones   | [X]     | [X]
Señales de tipología detectadas     | [X]     | [X]
---------------------------------|-----------|------
PUNTUACIÓN TOTAL                              | [X] / 100

Interpretación: 0-24 Bajo · 25-49 Medio · 50-74 Alto · 75-100 Crítico
```

---

## SECCIÓN 9 — RECOMENDACIÓN DE COMPLIANCE

```
[Elegir la recomendación que corresponda según la calificación de
riesgo y justificar brevemente. No recomendar una acción no soportada
por los hallazgos.]

[ ] Aceptar relación / operación sin medidas adicionales (riesgo bajo)
[ ] Aplicar Diligencia Debida Reforzada (EDD) — solicitar documentación
    adicional sobre el origen de fondos antes de proceder
[ ] Monitorización continua reforzada de la cuenta/dirección
[ ] Rechazar la relación / bloquear la operación
[ ] Presentar comunicación de operativa sospechosa (SAR/STR) ante la
    Unidad de Inteligencia Financiera competente

Justificación: [1-2 párrafos]
```

---

## SECCIÓN 10 — DECLARACIÓN Y VALIDEZ DEL INFORME

```
El presente informe se ha elaborado con base en fuentes públicas de
blockchain, verificables por cualquier tercero, y en las bases de datos
de clasificación de entidades y sanciones disponibles en la fecha de
emisión. La información on-chain es inmutable; las clasificaciones de
entidad y los resultados de cribado de sanciones pueden actualizarse
con el tiempo y deben revalidarse periódicamente.

Este documento tiene carácter confidencial y de uso interno para fines
de cumplimiento normativo (AML/CFT). No constituye asesoramiento legal
ni de inversión.

[Ciudad], a [DD] de [MES] de [AÑO]
Analista: _______________________
```

---

## SECCIÓN 11 — ANEXO: TABLA DE TRANSACCIONES

```
HOP | HASH (abreviado) | FECHA | ORIGEN | DESTINO | IMPORTE | ENTIDAD DESTINO
----|-------------------|-------|--------|---------|---------|----------------
[Tabla completa de las transacciones analizadas]
```
