# Glosario Jurídico: Terminología Blockchain para Documentos Judiciales

## Principio de uso

En informes periciales dirigidos a juzgados, fiscalías o policía, utilizar siempre la
**explicación jurídica** entre paréntesis la primera vez que se mencione el término técnico.
En menciones posteriores se puede usar el término técnico solo.

---

## Términos fundamentales

### Blockchain / Cadena de bloques
**Para el juzgado:** Registro contable digital de carácter público, distribuido entre miles de
ordenadores en todo el mundo e inalterable por diseño tecnológico. Cada operación queda
grabada de forma permanente y verificable por cualquier tercero. Equivale, en términos
funcionales, a un libro de contabilidad público e infalsificable.

### Wallet / Monedero digital / Dirección
**Para el juzgado:** Identificador único alfanumérico que funciona como "número de cuenta"
en la red blockchain. Una persona puede controlar múltiples wallets. La titularidad de una
wallet no consta en la propia blockchain, sino que la conoce el exchange o servicio a través
del cual fue creada.
**Ejemplo de formato Bitcoin:** `1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf0R`
**Ejemplo de formato Ethereum:** `0x742d35Cc6634C0532925a3b844Bc454e4438f44e`

### Hash de transacción / TXID (Transaction ID)
**Para el juzgado:** Código alfanumérico único que identifica de forma inequívoca cada
operación registrada en la blockchain. Es la "huella digital" de la transacción, inmutable
e irrepetible. Permite localizar y verificar cualquier operación en los registros públicos.
**Ejemplo:** `0x4a6e8b7c9d2f1e3a5b8c0d4e7f9a2b5c8d1e4f7a`

### Exchange / Plataforma de intercambio de criptomonedas
**Para el juzgado:** Empresa que presta servicios de compraventa e intercambio de
criptomonedas, actuando como intermediaria entre usuarios. Los exchanges regulados están
obligados por ley a identificar a sus clientes (KYC) y a conservar esos datos.

### KYC (Know Your Customer) / Verificación de identidad
**Para el juzgado:** Proceso de identificación obligatorio por el que los exchanges deben
verificar la identidad real de sus clientes mediante documento de identidad, pasaporte u
otros medios, al amparo de la normativa antiblanqueo. Equivale al proceso de apertura de
cuenta bancaria.

### AML (Anti-Money Laundering) / Prevención del blanqueo
**Para el juzgado:** Conjunto de obligaciones legales impuestas a los exchanges y otros
proveedores de servicios de criptomonedas para detectar y prevenir el blanqueo de capitales.
Incluye la identificación de clientes, el reporte de operaciones sospechosas y la conservación
de registros.

### VASP (Virtual Asset Service Provider) / Proveedor de Servicios de Activos Virtuales
**Para el juzgado:** Denominación legal reconocida por el GAFI (FATF) y la normativa UE para
las empresas que prestan servicios relacionados con criptomonedas. Los VASP son "sujetos
obligados" en materia de prevención del blanqueo de capitales.

### Bloque / Block
**Para el juzgado:** Unidad de registro en la blockchain que agrupa un conjunto de transacciones
validadas. Cada bloque tiene un número de orden, un sello temporal exacto y está vinculado
criptográficamente al bloque anterior, lo que hace imposible su alteración retroactiva.

### Nodo / Node
**Para el juzgado:** Cada uno de los miles de ordenadores distribuidos por el mundo que
mantienen una copia completa de la blockchain y validan las transacciones. La naturaleza
distribuida garantiza que ninguna entidad pueda modificar el registro.

### Clave privada / Private key
**Para el juzgado:** Código secreto que permite al titular de una wallet autorizar transacciones.
Equivale al PIN o firma autorizada de una cuenta bancaria. Quien controla la clave privada
controla los fondos.

### Token
**Para el juzgado:** Activo digital que opera sobre una red blockchain existente. Por ejemplo,
USDT (Tether) es un token que opera sobre la red Ethereum o Tron. Los tokens tienen valor
económico y pueden transferirse entre wallets.

### USDT / Tether
**Para el juzgado:** Criptomoneda cuyo valor está vinculado al dólar estadounidense (1 USDT ≈ 1 USD).
Es la criptomoneda estable (stablecoin) más utilizada en el mundo y frecuentemente empleada en
estafas por su valor predecible y facilidad de transferencia internacional.

### Gas / Fee / Comisión de red
**Para el juzgado:** Cantidad pequeña de criptomoneda pagada como comisión al ejecutar una
transacción, recompensando a los validadores de la red. Permite calcular con exactitud cuándo
se ejecutó una transacción y desde qué wallet se pagó la comisión.

---

## Términos de obfuscación (para describir conductas sospechosas)

### Mixer / Tumbler / Servicio de mezcla
**Para el juzgado:** Servicio informático diseñado específicamente para dificultar la trazabilidad
de fondos en la blockchain, mezclando las criptomonedas de varios usuarios de forma que resulte
difícil determinar el origen. El uso de estos servicios constituye un indicio relevante de
intención de ocultación del origen de los fondos. El servicio Tornado Cash fue sancionado por
el Departamento del Tesoro de EEUU en 2022 precisamente por este motivo.

### Layering / Estratificación
**Para el juzgado:** Técnica de blanqueo consistente en realizar múltiples transferencias entre
distintas wallets con el fin de distanciar los fondos de su origen ilícito y dificultar su
rastreo. Equivale a la fase de "transformación" descrita en los esquemas clásicos de blanqueo.

### Structuring / Smurfing / Fragmentación
**Para el juzgado:** Técnica consistente en dividir un importe elevado en múltiples
transferencias de menor cuantía para evadir los umbrales de reporte obligatorio.
Constituye en sí misma una infracción de la normativa antiblanqueo en muchas jurisdicciones.

### Peeling chain / Cadena de peeling
**Para el juzgado:** Secuencia de transacciones en la que los fondos pasan sucesivamente
por distintas wallets, "pelando" una pequeña cantidad en cada paso y enviando el resto
a la siguiente wallet. Es una técnica para dificultar el rastreo automatizado.

### DEX (Decentralized Exchange) / Exchange descentralizado
**Para el juzgado:** Plataforma de intercambio de criptomonedas que opera sin intermediario
central y sin obligaciones KYC, lo que permite el cambio entre criptomonedas de forma anónima.
Su uso en una cadena de transacciones añade una capa de complejidad al rastreo.

### Bridge / Puente entre cadenas
**Para el juzgado:** Servicio que permite transferir activos entre distintas redes blockchain
(por ejemplo, de Ethereum a Tron). Su uso puede dificultar el rastreo si el analista no
examina ambas redes.

### Swap / Intercambio de criptomonedas
**Para el juzgado:** Operación de cambio de una criptomoneda por otra. Por ejemplo, convertir
Bitcoin en Tether (USDT). Frecuentemente se realiza en exchanges descentralizados para
dificultar la trazabilidad.

---

## Términos procesales relacionados

### Requerimiento de información a exchange
**Naturaleza jurídica:** Diligencia de investigación tecnológica regulada en los arts. 588 ter a)
y siguientes LECrim, que permite al juez instructor ordenar a un proveedor de servicios
(en este caso, un exchange) la aportación de datos de sus clientes y registros de actividad.

### Cadena de custodia digital
**Para el juzgado:** Documentación del proceso de obtención, preservación y análisis de
evidencias digitales que garantiza su integridad y autenticidad. Es requisito para que
las evidencias sean admisibles en juicio.

### Hash SHA-256 de archivo
**Para el juzgado:** Código único que identifica de forma inequívoca el contenido de un
archivo digital. Si el archivo es alterado mínimamente, el hash cambia por completo.
Permite verificar que las capturas y documentos aportados no han sido modificados
desde su obtención.

### Timestamp / Sello temporal
**Para el juzgado:** Registro exacto de la fecha y hora en que se produjo un evento digital
(transacción, acceso, etc.), generado y validado por la red blockchain. Es equivalente
a la fecha y hora de una operación bancaria.

### Explorer / Explorador de bloques
**Para el juzgado:** Herramienta web que permite consultar el registro público de la
blockchain y visualizar las transacciones, wallets y bloques de forma legible. Equivale
a un visor del libro de contabilidad público. Los más conocidos son Etherscan.io (red
Ethereum) y Blockchain.com (red Bitcoin).

---

## Conversión de unidades frecuentes

| Cripto | Unidad mínima | Equivalencia |
|--------|--------------|--------------|
| Bitcoin (BTC) | Satoshi (sat) | 1 BTC = 100.000.000 sat |
| Ethereum (ETH) | Wei / Gwei | 1 ETH = 1.000.000.000 Gwei |
| USDT | — | 1 USDT ≈ 1 USD (stablecoin) |

**Nota para el informe:** Siempre expresar los importes en la unidad principal (BTC, ETH, USDT)
y su equivalente en EUR en la fecha de la transacción, citando CoinGecko como fuente del precio histórico.
