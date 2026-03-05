BUGS

- [ ] En CURL_12 hice drone survey y obtuve el mensaje "recoverable data signatures detected". Sin embargo, después hice "drone salvage data D1 CURL_12" y he recibido "Data salvaged: 0 files mounted at /remote/CURL_12/". ¿Cómo es posible? ¿Qué está sucediendo?

- [x] He hecho un viaje de 15 minutos ETA con el dron D1 en su bahía y no se le ha recargado la batería. [P.D. No es un bug, pero hay que ajustar cosas (o mejor dicho: informar mejor al usuario):

ahora mismo la recarga del dron está condicionada por energía, no solo por estar “docked”.

La causa principal en tu caso es esta:

Al hacer nav (sin --no-cruise), el motor activa CRUISE y apaga drone_bay (OFFLINE + forced_offline) automáticamente:
engine.py (line 314)

La rutina de mantenimiento de drones corta la recarga si drone_bay está OFFLINE:
engine.py (line 3825)

Además, aunque enciendas la bahía, solo carga si el balance de potencia lo permite:

carga normal si net_kw >= 0.2
carga lenta si net_kw >= -0.2 y hay SoC
engine.py (line 3838), balance.py (line 228)
En resumen: viaje en CRUISE te deja la bahía apagada (y en muchos estados iniciales además vas justo de potencia), por eso D1 en 0.14 no sube.

]

- [ ] Al hacer scan repetidamente desde una misma localización no obtengo siempre el mismo output. ¿Por qué?

- [ ] A veces en textual al darle a TAB no se autocompleta (ni listan las opciones) sino que se cambia el foco de la ventana. Esto sólo sucede a veces. Parece que sucede con el comando ls o cat, al intentar que se autocomplete el path.




