# Guía de la UI Textual

El juego incluye una interfaz Textual con varios paneles y atajos de teclado.

## Paneles
- Header (arriba): tiempo galáctico, tiempo propio de la nave, tiempo biológico del personaje, modo de la nave y ubicación. Los relojes usan `G:` (galáctico), `S:` (nave) y `P:` (personaje), con el mismo color de etiqueta que `P_gen=` y `P_load=`, e incluyen segundos; la barra se distribuye en varias líneas en terminales estrechos.
- Status (izquierda): estado y salud de los sistemas, sin el resumen de velocidad de motores.
- Alerts (derecha, arriba): alertas activas.
- Jobs (derecha, abajo): cola de trabajos y resultados recientes.
- Log (abajo): salida de comandos y eventos.
- Input (abajo): línea de comandos.

El comando `status` también enumera los tres relojes. El tiempo de la nave refleja la dilatación temporal relativista; el tiempo biológico del personaje refleja además la hibernación. Cada reloj cuenta desde el inicio de la misión (año 1, día 1).

En `A1 D1 00:01:58`, `A1` indica el primer año, `D1` el primer día de ese año y `00:01:58` horas, minutos y segundos desde el inicio de la misión. Los años y días se numeran desde 1, así que el ejemplo representa 1 minuto y 58 segundos transcurridos. Los años tienen 365 días. En inglés se usa `Y` en lugar de `A`. La barra omite el prefijo redundante `T+`. Los años inferiores a 10.000 aparecen completos; desde 10.000 usan `k` (miles), desde 1.000.000 `M` (millones) y desde 1.000.000.000 `B` (miles de millones), redondeados a un decimal. Cuando se abrevia el año, el día aparece como `+1d` en lugar de `D1`; por ejemplo, `A12.5k +1d 00:00:00`.

## Atajos Principales
- `TAB`: autocompletar el comando o argumento actual.
- `Alt+J`: enfocar el siguiente panel.
- `Alt+K`: enfocar el panel anterior.
- `J`: desplazarse hacia abajo en el panel enfocado.
- `K`: desplazarse hacia arriba en el panel enfocado.
- `Ctrl+L`: limpiar el panel de log.

## Mostrar/Ocultar Paneles
Principal (fiable):
- `F2`: alternar panel Status.
- `F3`: alternar panel Alerts.
- `F4`: alternar panel Jobs.
- `F5`: alternar todos los paneles.

Opcional (depende del terminal):
- `Alt+1`: alternar panel Status.
- `Alt+2`: alternar panel Alerts.
- `Alt+3`: alternar panel Jobs.
- `Alt+0`: alternar todos los paneles.

Al ocultar paneles, el espacio se reasigna al resto. Si se ocultan status/alerts/jobs, el panel de log se expande.

## Notas de Autocompletado
- El autocompletado usa sistemas, contactos, sectores y archivos conocidos.
- Pulsa `TAB` para completar. Si hay varias opciones con prefijo común, se extiende hasta ese prefijo. Si no hay prefijo común, pulsa `TAB` dos veces para listar candidatos en el log.

## Consejos de Foco
- Usa `Alt+J` / `Alt+K` para cambiar el foco.
- El scroll afecta al panel enfocado.
