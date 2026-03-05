
# RETORNO

**RETORNO** es un altamente inmersivo videojuego de ciencia ficción dura, pausado y sistémico, de INTERFAZ DE LÍNEA DE COMANDOS puro. 

Despiertas en un sarcófago de criogenización dentro de una nave averiada, miles de años después de tu sueño inducido. No puedes moverte físicamente. Tu único vínculo con el mundo es una terminal conectada a tu mente. Desde esa terminal tendrás que comprender qué ha ocurrido, restaurar sistemas críticos, gestionar energía, controlar drones de mantenimiento, explorar naves y estaciones abandonadas, recuperar recursos e información, y abrirte paso por un universo fragmentado y silencioso.

RETORNO está diseñado como una experiencia de exploración, supervivencia técnica y lectura: un juego calmado, de decisiones lentas y consecuencias reales, con momentos puntuales de alta tensión.

¿Conoces el excepcional «Duskers»? RETORNO pretende ser una versión «hardcore» del mismo.

## Estado del proyecto

**En desarrollo activo.**  
Actualmente RETORNO se encuentra en fase de prototipo jugable. Muchas mecánicas base ya están implementadas, pero el juego sigue evolucionando y ampliándose.

## Características destacadas

- **Interfaz de terminal**: el juego se controla escribiendo órdenes, con un parser inspirado en consolas y sistemas operativos diegéticos.
- **Ciencia ficción sistémica**: energía, degradación, radiación, drones, daños estructurales y estados críticos interactúan entre sí.
- **Prólogo tipo “puzzle técnico”**: el inicio del juego enseña las mecánicas a través de una crisis de energía y reparación.
- **Gestión de sistemas de nave**: arranque, apagado, diagnóstico, reparación y priorización de subsistemas.
- **Control de drones**: despliegue, movimiento, reparación, salvage, survey e instalación de módulos.
- **Exploración espacial no lineal**: viajes entre nodos, rutas descubiertas mediante escaneo, uplink, salvage de datos e intel.
- **Lore distribuido**: correos, logs, fragmentos de navegación y documentos dispersos que permiten reconstruir historias y mini-arcos narrativos.
- **Mundo híbrido**: combinación de localizaciones authored y generación procedural de nodos, rutas y contenido recuperable.
- **Sistema de riesgo real**: errores de gestión pueden llevar a estados críticos y, si no se corrigen, a una situación terminal.

## Filosofía de diseño

RETORNO no busca ser un juego de acción rápida ni un roguelike tradicional de combates constantes. Su núcleo está en:

- **gestión técnica bajo presión**
- **exploración lenta y deliberada**
- **lectura e interpretación de información dispersa**
- **agencia del jugador** y gestión de malas decisiones

El juego intenta evitar tanto el castigo arbitrario como el exceso de protecciones: el jugador debe poder equivocarse, pero también debe tener herramientas reales para comprender el sistema y reaccionar.

## Cómo ejecutarlo

Normal (carga save si existe):
```bash
PYTHONPATH=src python -m retorno.ui_textual.app
```

Perfiles de usuario (save por usuario):
```bash
PYTHONPATH=src python -m retorno.ui_textual.app --user Pepe
PYTHONPATH=src python -m retorno.ui_textual.app --user Pepe
```

Forzar partida nueva:
```bash
PYTHONPATH=src python -m retorno.ui_textual.app --new-game
```

Nueva partida para un usuario concreto:
```bash
PYTHONPATH=src python -m retorno.ui_textual.app --user Pepe --new-game
```

Opcional: ruta de save personalizada con --save-path ... (o env RETORNO_SAVE_PATH / RETORNO_SAVE_DIR).

Notas:
- --save-path tiene prioridad sobre --user.
- También puedes definir RETORNO_USER para seleccionar perfil por entorno.
- Formato de usuario válido: 1-32 caracteres en minúscula (a-z, 0-9, '.', '_' o '-').

## Basic commands

Some common in-game commands:

- **status**
- **alerts**
- **diag <system_id>**
- **boot <service_name>**
- **power status**
- **power plan cruise|normal**
- **drone status**
- **drone deploy! <drone_id> <sector_id>**
- **drone repair <drone_id> <system_id>**
- **drone salvage scrap <drone_id> <node_id>**
- **scan**
- **route solve <node_id>**
- **nav**
- **travel <node_id>**
- **dock <node_id>**
- **uplink**
- **mail**
- **ls**
- **cat <path>**
- **intel import <path>**

Dentro del juego, usa **help --verbose** para ver el listado actualizado de comandos.

## Idioma

RETORNO está siendo preparado para jugarse en español e inglés.
Los comandos y nombres técnicos del sistema se mantienen en inglés; los textos diegéticos (mails, logs, manuales, mensajes del sistema) pueden cambiar según la configuración de idioma.

## Estilo de manuales

La plantilla oficial y reglas de estructura están documentadas en:
- `docs/manuals_style_guide.md`

Validación de estilo:

```bash
python tests/manuals_style_check.py
```

## Roadmap (resumen)

Sistemas ya implementados o en desarrollo:

- **Galaxia proceduralmente generada**
- **gestión de energía y estados críticos**
- **drones: operaciones de salvamento, reparación, recuperación de módulos, y más**
- **rutas, navegación e intel**
- **localizaciones proceduralmente generadas**
- **privilegios de acceso (GUEST, MED, etc.)**
- **degradación, radiación y casco de nave**
- **eventos de viaje aleatorios**
- **expansión de lore distribuido y mini-arcos narrativos**

## Note

RETORNO está en construcción. Las mecánicas, comandos, balance y estructura del mundo pueden cambiar con frecuencia a medida que el proyecto evoluciona.
