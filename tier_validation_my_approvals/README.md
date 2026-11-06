# Mis aprobaciones

Aplicación con ícono propio que reúne **todas las aprobaciones por niveles** (tier validation de
OCA) de cualquier documento: expedientes, Solicitudes de Gasto/Ingreso, pago de facturas,
rendiciones de fondos o cualquier modelo que use `tier.validation`. No hace falta registrar cada
modelo: el tipo de documento sale solo.

No se llama "Aprobaciones" porque la app estándar `approvals` (Enterprise) ya usa ese nombre.

## Menús

| Menú | Qué muestra | Quién lo ve |
|---|---|---|
| Por aprobar | Mis aprobaciones abiertas; por defecto, las que **me tocan ahora** | Todos |
| Solicitadas por mí | Las aprobaciones que pedí | Todos |
| Historial | Las que aprobé o rechacé | Todos |
| Todas | Todas las aprobaciones de documentos que puedo leer | Supervisor |
| Análisis | Pivote y gráfico: cantidad y días hasta la aprobación, por tipo y estado | Supervisor |
| Configuración | Definiciones de aprobación y excepciones, sin necesitar *Ajustes / Técnico* | Administrador |

Los grupos están en *Ajustes → Usuarios → Mis aprobaciones*: **Supervisor** y **Administrador**
(incluye Supervisor).

## Aprobar y rechazar desde la bandeja

Los botones **Aprobar** y **Rechazar** aparecen solo cuando es mi turno. Llaman a
`validate_tier()` / `reject_tier()` **del documento de origen**, con el usuario actual, así que
se respetan las reglas propias de cada modelo (etapas del expediente, fases de la SG, avisos,
comentarios obligatorios). El turno lo decide el documento con `_get_sequences_to_approve`.

**Aprobar seleccionadas:** al marcar filas en la lista aparece el botón *Aprobar seleccionadas*.
Aprueba una vez por documento las que te tocan ahora, de cualquier tipo, y muestra un resumen:
cuántas se aprobaron, cuáles **piden comentario** (esas se aprueban de a una, desde la fila o el
formulario), cuáles no se pudieron aprobar y por qué, y cuántas no te tocaban. Si un documento
falla, los demás se aprueban igual.

**Límite:** para aprobar desde la bandeja hay que poder leer el documento, igual que al aprobar
desde el propio documento.

## Resumen diario por correo

Una vez por día, cada usuario recibe un correo con lo que le toca aprobar, agrupado por tipo de
documento. Sale de la misma búsqueda que el menú **Por aprobar**: incluye cualquier documento con
aprobaciones (expedientes, solicitudes, disposiciones, resoluciones, facturas, rendiciones), respeta
el turno de cada uno y el filtro de acceso. A quien no tiene nada pendiente no se le envía, y cada
fila lleva a la aprobación en la bandeja.

- Se activa en *Mis aprobaciones → Configuración → Ajustes* (hace falta ser administrador del
  sistema), por compañía, con la hora de envío en la zona horaria del contacto de la compañía. Viene
  apagado.
- **Enviarme el resumen ahora** manda el propio resumen, para probar, sin afectar el envío diario.
- Cada usuario lo recibe según su compañía principal y siempre por correo, sin importar su
  preferencia de notificaciones.
- Solo usuarios internos con correo: los de portal no tienen acceso a la bandeja.
- El aviso por cada aprobación es aparte: se apaga en la definición, con *Notify Reviewers on
  Creation* y *Notify Reviewers on reaching Pending*.

## Privacidad

Depende de `base_tier_validation_board`, que limita las revisiones a las de documentos que el
usuario puede leer o en las que participa. Eso vale para todos los menús, incluidos "Todas" y
"Análisis".
