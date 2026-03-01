# Guía de la UI Textual

El juego incluye una interfaz Textual con varios paneles y atajos de teclado.

## Paneles
- Header (arriba): tiempo actual, modo de la nave y ubicación.
- Status (izquierda): estado de nave/sistemas.
- Alerts (derecha, arriba): alertas activas.
- Jobs (derecha, abajo): cola de trabajos y resultados recientes.
- Log (abajo): salida de comandos y eventos.
- Input (abajo): línea de comandos.

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
