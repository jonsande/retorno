# Autorretorno preventivo — validación

El intérprete del proyecto ejecutó primero comprobaciones focalizadas, después
la colección predeterminada de pytest y los 84 scripts ejecutables de pruebas
smoke/integración/unitarias. La base de comparación es la integración anterior
de motores, documentada en [su evidencia](engines-antimatter-results.json).
Se conservan los [resultados por script](drone-autorecall-results.json).

| Comprobación | Resultado |
| --- | --- |
| Nueva integración de reserva | 17 grupos CORRECTOS |
| Pytest predeterminado | 17 CORRECTOS, 14 subtests CORRECTOS |
| Suite de scripts ejecutables | 66/84 CORRECTOS, 18 FALLOS |
| Base de la integración anterior | 65/83 CORRECTOS, los mismos 18 FALLOS |
| Estilo de manuales, parejas EN/ES y espacios de la tarea | CORRECTO |

Los fallos sin cambios ya se reprodujeron en HEAD canónico limpio durante la
integración de motores. No se ha detectado ningún script fallido nuevo. Esto
no afirma que la suite global esté en verde; la lista completa de fallos está
en la evidencia legible por máquina. Pasan política eléctrica, cadena/política
del prólogo, guardado/carga, módulos, recall-all, IDs públicos, límites de
conocimiento, Textual, relojes y avance temporal. La suite nueva se repitió tras
el filtro final de configuración por dron: pasan sus 17 grupos.

La integración nueva comprueba el caso comunicado de 12% -> reparación -> 4%
sin gastar batería/tiempo ni perder chatarra; un único retorno en cola;
un solo descuento por tarea en éxito y fallo; comportamiento OFF y modo dios;
presupuestos acumulados y devoluciones de colas; prioridad de retorno tras
trabajo activo seguro; revalidación tras cambios de batería, umbral o capacidad;
esperas largas y umbrales bajos; bloqueos explícitos sin repetición por batería,
integridad o acoplamiento; estado EN/ES de solo lectura y presentación compartida;
guardado/carga del retorno pendiente y bloqueo; movimiento/reparación compuestos;
y comandos reales por teclado de Textual en ambos idiomas con debug pausado.

El parche no modifica la partida en ejecución ni concede energía a D1. Un dron
ya agotado sigue sujeto a los requisitos normales de retorno. Inicia la aplicación
actualizada para utilizar la lógica nueva; los guardados del formato actual de
motores conservan baterías y trabajos. No se hizo commit ni push y se conservó
el cambio previo de TODO.md.

Comportamiento, fórmulas y comandos públicos: [implementación](../systems/drone-autorecall.es.md).
