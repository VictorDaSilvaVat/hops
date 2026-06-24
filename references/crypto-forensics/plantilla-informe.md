# Plantilla: Informe Pericial sobre Análisis Forense de Activos Digitales

---

## SECCIÓN 1 — DATOS DEL INFORME

```
INFORME PERICIAL SOBRE ANÁLISIS FORENSE DE ACTIVOS DIGITALES
Nº de Informe: [AÑO-CORRELATIVO, ej: 2024-001]
Fecha de emisión: [DD de MMMM de YYYY]
Asunto: Análisis de transacciones en red blockchain [NOMBRE RED]
        en el marco de presunta estafa [referencia interna del bufete]
Número de diligencias: [si existe procedimiento abierto]
Juzgado: [si está asignado]
Solicitante: [Nombre del bufete / abogado]
En nombre de: [Nombre del cliente / víctima]
```

---

## SECCIÓN 2 — OBJETO Y ALCANCE DEL INFORME

```
El presente informe tiene por objeto el análisis técnico forense de las
transacciones realizadas en la red blockchain [NOMBRE], con el fin de:

a) Verificar la existencia y cuantía de la transferencia efectuada por
   [NOMBRE VÍCTIMA] a la dirección [WALLET ESTAFADOR] con fecha [FECHA].

b) Rastrear el flujo de fondos desde la dirección de destino hasta
   identificar su salida a una plataforma de intercambio (exchange)
   sujeta a obligaciones de identificación de clientes (KYC/AML).

c) Proporcionar al Juzgado y/o a las Fuerzas y Cuerpos de Seguridad
   los elementos técnicos necesarios para requerir la identidad del
   titular de la cuenta en dicho exchange.

El análisis se circunscribe al período comprendido entre [FECHA INICIO]
y [FECHA FIN], sobre las direcciones y transacciones indicadas en el
apartado de Hechos Verificados.
```

---

## SECCIÓN 3 — DOCUMENTOS Y FUENTES EXAMINADAS

```
Para la elaboración del presente informe se han examinado:

3.1 Documentación aportada por el cliente:
    - [Lista: capturas de pantalla, emails, contratos, etc.]
    - [Hash de transacción aportado por el cliente: 0x...]

3.2 Fuentes públicas consultadas:
    - [NOMBRE EXPLORER] ([URL]) — consultado el [FECHA] a las [HORA] CET
    - [NOMBRE EXPLORER] ([URL]) — consultado el [FECHA] a las [HORA] CET
    - CoinGecko (coingecko.com) — para precios históricos en EUR
    - Base de datos de etiquetas de Etherscan/Blockchair

3.3 Nota sobre inmutabilidad:
    Los datos extraídos de la blockchain son registros públicos,
    distribuidos e inmutables por diseño criptográfico. Cualquier
    tercero puede verificar su autenticidad accediendo a las mismas
    URLs con los mismos identificadores de transacción.
```

---

## SECCIÓN 4 — METODOLOGÍA

```
4.1 Proceso de análisis

El análisis forense se ha realizado siguiendo la metodología estándar
de trazabilidad blockchain (transaction graph analysis), consistente en:

    1. Localización de la transacción inicial mediante el hash o la
       dirección de destino aportados por el cliente.

    2. Análisis del historial de transacciones de cada dirección
       identificada, siguiendo el flujo de salida de los fondos.

    3. Identificación de etiquetas conocidas (exchanges, mixers,
       servicios conocidos) mediante bases de datos públicas y
       análisis de patrones de comportamiento on-chain.

    4. Documentación de cada hop (salto entre wallets) con su
       correspondiente hash, timestamp, importe y conversión a EUR.

    5. Identificación del destino final de los fondos y, en su caso,
       del exchange con obligaciones KYC al que fueron enviados.

4.2 Limitaciones del análisis

    - El análisis on-chain permite trazar los movimientos de fondos
      pero no identifica por sí mismo a personas físicas o jurídicas,
      salvo en el caso de exchanges regulados cuya cartera de depósito
      es pública y conocida.

    - En caso de uso de servicios de mezcla (mixers) o intercambios
      descentralizados (DEX), la trazabilidad puede verse dificultada,
      lo que se indicará expresamente en el informe.

    - Los precios en EUR se calculan a partir del precio de mercado
      en la fecha y hora de la transacción según CoinGecko.
```

---

## SECCIÓN 5 — HECHOS VERIFICADOS

### 5.1 Transacción inicial

```
Se ha verificado la existencia de la siguiente transacción en la
red [NOMBRE RED]:

  Hash:           [HASH COMPLETO]
  Bloque nº:      [NÚMERO]
  Fecha y hora:   [DD/MM/YYYY HH:MM:SS] UTC ([HH:MM] hora Madrid)
  Wallet origen:  [DIRECCIÓN] [indicar si es la víctima]
  Wallet destino: [DIRECCIÓN] [indicar que es el presunto estafador]
  Importe:        [X.XX] [TOKEN] (equivalente a [X.XX] EUR en esa fecha)

  Fuente verificable: [URL EXACTA DEL EXPLORADOR]
```

### 5.2 Trazabilidad de fondos — Tabla de hops

```
A continuación se detalla el flujo de fondos observado desde la
dirección de destino inicial:

HOP | HASH (abreviado)  | FECHA       | ORIGEN          | DESTINO         | IMPORTE      | ETIQUETA DESTINO
----|-------------------|-------------|-----------------|-----------------|--------------|------------------
 1  | 0xABC...DEF       | 12/01/2024  | 0xWALLET1...    | 0xWALLET2...    | 0.49 ETH     | Sin etiqueta
 2  | 0xGHI...JKL       | 13/01/2024  | 0xWALLET2...    | 0xWALLET3...    | 0.48 ETH     | Sin etiqueta
 3  | 0xMNO...PQR       | 13/01/2024  | 0xWALLET3...    | 0xBINANCE...    | 0.47 ETH     | ⚠️ BINANCE (exchange KYC)

Para cada transacción se adjunta captura del explorador como Anexo [N].
```

### 5.3 Destino final identificado

```
Los fondos rastreados han sido recibidos en la dirección
[DIRECCIÓN WALLET EXCHANGE], identificada públicamente como
wallet de depósito del exchange [NOMBRE EXCHANGE].

Esta identificación se basa en:
  a) Etiqueta pública en [ETHERSCAN/BLOCKCHAIR]: "[NOMBRE EXCHANGE] X"
  b) Historial de transacciones consistente con una wallet de depósito
     de exchange (miles de usuarios distintos, consolidación periódica)
  c) [Otras evidencias si las hay]

[NOMBRE EXCHANGE] es un proveedor de servicios de activos virtuales (VASP)
registrado/regulado en [PAÍS], sujeto a obligaciones de identificación
de clientes (KYC) y reporte de operaciones sospechosas (AML) en virtud
de [NORMATIVA APLICABLE].
```

---

## SECCIÓN 6 — INDICIOS DE OCULTACIÓN (si aplica)

```
Durante el análisis se han observado los siguientes indicios que
sugieren una conducta orientada a dificultar el rastreo de fondos:

[INCLUIR SOLO LOS QUE APLIQUEN:]

6.1 Fragmentación de importes (structuring)
    Los fondos fueron divididos en [N] transferencias de importe inferior
    a [X] EUR, lo que es consistente con una estrategia de evasión de
    umbrales de reporte. [Detallar transacciones]

6.2 Uso de wallets intermedias (peeling chain)
    Los fondos pasaron por [N] direcciones intermedias sin actividad
    previa antes de llegar al exchange, patrón típico de layering.

6.3 Conversión entre criptomonedas
    Los fondos fueron convertidos de [TOKEN A] a [TOKEN B] mediante
    [DEX/servicio], añadiendo una capa adicional de complejidad.

6.4 Uso de servicio de mezcla
    Se detectó el envío de fondos a [NOMBRE MIXER], servicio diseñado
    específicamente para dificultar la trazabilidad de transacciones.
    Esto constituye un indicio de intención de ocultación.
```

---

## SECCIÓN 7 — CONCLUSIONES PERICIALES

```
PRIMERA: Se ha verificado de forma fehaciente que el día [FECHA], a las
[HORA] hora Madrid, desde la dirección [WALLET VÍCTIMA], se transfirió
la cantidad de [IMPORTE] [TOKEN] (equivalente a [X] EUR) a la dirección
[WALLET ESTAFADOR]. Hash de transacción: [HASH].

SEGUNDA: Tras el análisis de la trazabilidad de los fondos, se ha
determinado que [IMPORTE] [TOKEN] de los fondos recibidos en la dirección
anterior fueron remitidos, en [N] operaciones, a la dirección
[WALLET EXCHANGE], identificada como wallet de depósito del exchange
[NOMBRE EXCHANGE].

TERCERA: El exchange [NOMBRE EXCHANGE], registrado en [PAÍS] bajo el
número [REGISTRO], está sujeto a la normativa AML/KYC y tiene la
obligación legal de identificar a los titulares de las cuentas que
operan en su plataforma.

CUARTA: La identidad del titular de la cuenta asociada a [WALLET EXCHANGE]
en la plataforma [NOMBRE EXCHANGE] solo puede ser obtenida mediante
requerimiento judicial o policial al referido exchange, al tratarse de
datos personales protegidos por la normativa de privacidad.

[QUINTA (si aplica): Se han observado indicios de conductas orientadas
a la ocultación del origen de los fondos, consistentes en [resumen breve].]
```

---

## SECCIÓN 8 — EXCHANGE IDENTIFICADO Y DATOS PARA REQUERIMIENTO

```
EXCHANGE IDENTIFICADO:
  Nombre comercial:    [NOMBRE]
  Nombre legal:        [RAZÓN SOCIAL COMPLETA]
  País de registro:    [PAÍS]
  Regulador:           [NOMBRE DEL REGULADOR]
  Número de registro:  [NÚMERO VASP / LICENCIA]
  Dirección legal:     [DIRECCIÓN COMPLETA]
  Email legal/GDPR:    [EMAIL]
  Portal de solicitudes: [URL si existe]

WALLETS DE DEPÓSITO IDENTIFICADAS:
  [LISTA DE DIRECCIONES CON SUS HASHES DE TRANSACCIÓN]

---

TEXTO PROPUESTO PARA SOLICITUD DE REQUERIMIENTO JUDICIAL:

"Se solicita al Juzgado que libre oficio al exchange [NOMBRE COMERCIAL],
con domicilio en [DIRECCIÓN], ordenando la aportación de la siguiente
información en relación con las transacciones identificadas en el
presente informe pericial:

1. Datos identificativos completos (nombre y apellidos o razón social,
   número de documento de identidad o pasaporte, nacionalidad,
   domicilio, teléfono de contacto y dirección de correo electrónico)
   del titular o titulares de la/s cuenta/s asociada/s a la/s
   dirección/es de blockchain: [LISTA DE WALLETS].

2. Fecha de alta, verificación KYC y documentación de identidad
   aportada por el titular en el proceso de registro.

3. Extracto completo de movimientos de la/s cuenta/s indicada/s
   durante el período comprendido entre [FECHA INICIO] y [FECHA FIN].

4. Registros de acceso (dirección IP, dispositivo, timestamp) durante
   el referido período.

5. Cualquier otro dato que permita la identificación y localización
   del titular.

Todo ello al amparo de los artículos 588 ter a) y siguientes de la
Ley de Enjuiciamiento Criminal, en relación con la Directiva (UE)
2018/843 del Parlamento Europeo y del Consejo (AMLD5), relativa a la
prevención de la utilización del sistema financiero para el blanqueo
de capitales, que obliga a los proveedores de servicios de cambio de
monedas virtuales a aplicar medidas de identificación de clientes."
```

---

## SECCIÓN 9 — DECLARACIÓN DE VERACIDAD

```
El/La que suscribe declara:

Que el presente informe ha sido elaborado con objetividad e imparcialidad,
aportando los elementos técnicos de los que dispone con fidelidad a la
realidad verificada.

Que los datos extraídos de la blockchain son registros públicos,
verificables por cualquier tercero en las fuentes indicadas, e inmutables
por diseño tecnológico.

Que no tiene relación de parentesco, amistad ni enemistad con ninguna
de las partes, ni interés directo o indirecto en el resultado del proceso.

Que, de resultar necesario, está disponible para ratificar el presente
informe ante el Juzgado que conozca del asunto.

[Ciudad], a [DD] de [MES] de [AÑO]

Firma: _______________________
```

---

## SECCIÓN 10 — ANEXOS

```
ANEXO 1: Captura de explorador — Transacción inicial
  Fuente: [URL]
  Fecha de captura: [FECHA HORA]
  Hash SHA-256 del archivo: [HASH]

ANEXO 2: Captura de explorador — Hop 1
  [...]

ANEXO N: Captura identificación wallet exchange
  Fuente: [URL etiqueta en Etherscan/Blockchair]
  Fecha de captura: [FECHA HORA]

ANEXO N+1: Diagrama de flujo de fondos
  [Diagrama Mermaid o imagen]

ANEXO N+2: Tabla de precios históricos EUR
  Fuente: CoinGecko — [URL con fechas]
```
