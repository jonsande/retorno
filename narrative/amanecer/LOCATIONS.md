# AMANECER — Lugares y pistas de exploración (contrato editorial, NO esquema de motor)

| Referencia | Clasificación | Generación y uso |
|---|---|---|
| **Tábano** | **OBLIGATORIO / PERSISTENTE** | Pecio de nave explorable. El generador elige posición. Contiene `05_the_route.md`, `06_last_watch.md` y ruta de navegación a destino sospechoso. |
| **Bruma** | **OBLIGATORIO / PERSISTENTE** | Nave asociada al sexto transporte de AMANECER. Posición generada. Conservación presente por definir. |
| **VAELOR** | **OBLIGATORIO / LOCALIZABLE** | Sistema estelar cuya ubicación/sector debe ser inferible mediante pista. Comunidad humana extinta en presente jugable. |
| **THALLOINOV, Lunviea, Druinope** | **COMPONENTES VAELOR** | No crear tres nodos independientes por aparición textual: deben representarse conforme al modelo de sistema y planetas que permita el juego. |
| **Destino de la ruta del Tábano** | **OBLIGATORIO / ALCANZABLE** | Generador decide posición. Puede coincidir o no con la instalación de investigación; no decidir aquí. Información recuperable solo desde pecio. |
| **Liria** | **POR DECIDIR** | Estación en la historia, pero pendiente definir si existe como nodo jugable adicional. |
| **Módulo auxiliar de la Bruma** | **SOLO REFERENCIA POR AHORA** | No generar como nodo autónomo. |
| **Otros lugares genéricos** | **AMBIENTAL** | No crear nodos por menciones de sector, puerto, repetidor, etc. |

## Dependencias narrativas previstas
1. Una o varias pistas permiten al jugador encontrar el **Tábano**. Definir canal y modalidad cuando se implementen los arcos; no se han inventado coordenadas.
2. Dentro del pecio, el jugador recupera un registro narrativo que explica el origen de una ruta **y una pieza de intel generada/parametrizada** para el destino sospechoso. Deben concordar en la partida.
3. La ruta señala un lugar existente en la partida, aunque no garantiza el destino de las siete personas ni que la instalación secreta funcionara allí.
4. El single `01_vaelor_shipping_receipt.md` contiene `[SECTOR_VAELOR]`, pendiente de sustituir por un valor auténtico compatible con el mundo generado.

## Importante para la fase técnica
El sistema actual de lore/intel basado en `LINK: NODE_A -> NODE_B` puede no cubrir por sí solo **generación obligatoria de naves con posiciones variables**, **sistemas planetarios completos**, o **interacciones de varios artefactos en un pecio**. Evaluar y diseñar las modificaciones necesarias antes de afirmar que el JSON es suficiente. El contrato anterior describe el resultado deseado, no la capacidad ya demostrada del motor.
