# Tier Validation Apps

Módulos de Odoo sobre las aprobaciones por niveles de OCA (`base_tier_validation`).

| | |
|---|---|
| **Módulos** | `base_tier_validation_board`, `tier_validation_my_approvals` |
| **Licencia** | AGPL-3 |
| **Versiones** | 18.0 — Community y Enterprise |
| **Depende de** | [`base_tier_validation`](https://github.com/OCA/server-ux/tree/18.0/base_tier_validation) (OCA server-ux), `spreadsheet_dashboard` |

## `tier_validation_my_approvals` — app "Mis aprobaciones"

Aplicación con ícono propio que reúne las aprobaciones por niveles de todos los documentos, con
menús Por aprobar, Solicitadas por mí, Historial, Todas y Análisis, y botones para aprobar o
rechazar desde la bandeja. Detalle en su [README](tier_validation_my_approvals/README.md).

## `base_tier_validation_board`

Port a 18.0 de `base_tier_validation_board` de OCA, que se fusionó solo en 16.0. La migración a
18.0 ([OCA/server-ux#1155](https://github.com/OCA/server-ux/pull/1155)) se cerró sin fusionar; la
de 19.0 está en [OCA/tier-validation#40](https://github.com/OCA/tier-validation/pull/40).

Además del tablero de revisiones, **limita qué revisiones ve cada usuario**. Sin este módulo,
`base_tier_validation` deja que cualquier usuario interno liste todas las revisiones, con el
nombre del documento, aunque no pueda abrirlo. Con el módulo, una revisión aparece solo si el
usuario:

- puede leer el documento, o
- participa de la revisión: es aprobador, la pidió o la resolvió. Un aprobador puede tener que
  decidir sobre un documento que no puede abrir, por ejemplo una factura para alguien sin
  acceso a contabilidad.

Aplica a listas, búsquedas, conteos, agrupaciones y pivotes. `sudo()` no pasa por el filtro, así
que los cálculos internos de las aprobaciones no cambian.

Cambios respecto del PR de OCA: ver [HISTORY](base_tier_validation_board/readme/HISTORY.md).

### Límite conocido

El filtro está en la búsqueda, como en OCA. Leer una revisión **por ID** sigue permitido, porque
una regla de registro sobre `tier.review` rompería los cálculos de las aprobaciones, que leen
las revisiones con el usuario actual. La interfaz siempre llega a las revisiones buscando, así
que queda cubierta.
