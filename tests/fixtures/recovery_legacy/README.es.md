# Guardado anterior a la corrección focal

[English](README.md). `pending-v1.dat` se generó ejecutando la entrega original
4D-3e5b antes de modificar su comportamiento. Contiene un plan
`historical-recovery-v1`, A → B → C, con primera oportunidad pendiente local
sin emisor/emisión nuevos. La segunda etapa todavía no tenía oportunidad.

Se usa solo en pruebas: no es contenido instalado ni un guardado del usuario.
`tests/recovery_provenance_smoke.py` comprueba carga sin reescribir, captura única
de la oportunidad ya preparada y prohibición de inventar la segunda emisión.
El JSON del informe conserva reproducción y SHA-256 del archivo.
