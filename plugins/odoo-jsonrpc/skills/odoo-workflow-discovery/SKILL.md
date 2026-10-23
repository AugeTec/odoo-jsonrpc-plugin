---
name: odoo-workflow-discovery
description: Usar para descubrir y proponer flujos de trabajo de punta a punta en cualquier base Odoo (p. ej. compra → recepción → factura, venta → entrega → cobro, manufactura, soporte), sin conocerlos de antemano. Combina introspección del modelo (estados, botones, enlaces entre documentos), configuración (automatizaciones, crons, plantillas) y trazas de registros reales. Requiere la skill odoo-jsonrpc para la conexión.
---

# Descubrir flujos de trabajo en Odoo

Genérico: parte de **un modelo de entrada** (el documento que inicia el proceso) y deduce el flujo a partir de lo que la instancia realmente tiene instalado, configurado y usado. No asumir el flujo "estándar" de Odoo: la instancia puede tener módulos, estudio o automatizaciones que lo cambian.

Cliente: `scripts/discover.py` (usa las credenciales de `odoo-jsonrpc`: `ODOO_URL`, `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD`). Solo lectura.

## Método

1. **Contexto**: `ir.module.module` con `state=installed` y `application=true` → qué áreas existen.
2. **Elegir el modelo de entrada** (el usuario lo nombra o se deduce del proceso: `purchase.order`, `sale.order`, `mrp.production`, `helpdesk.ticket`…). Verificar con `search_count`.
3. **Perfil** — `discover.py profile <modelo>`: campos de estado con conteo de registros por valor (`state`, `invoice_status`, `receipt_status`…), botones del form (cada uno es una transición posible; su `invisible` dice desde qué estado), y automatizaciones, crons y plantillas de correo del modelo.
4. **Mapa de documentos** — `discover.py graph <modelo> --depth 2`: solo enlaces relacionales hacia otros documentos *con datos reales* (conteo de registros que usan el enlace). Un enlace con 0 registros se descarta: el flujo existe en el código pero no se usa.
5. **Transiciones reales** — `discover.py trans <modelo>`: pares estado→estado con frecuencia, de `mail.tracking.value`. Revela caminos usados (y saltados). Si no hay tracking, inferir de los conteos del perfil.
6. **Traza de un caso real** — `discover.py trace <modelo> <id> --depth 2`: sigue un registro por todos sus enlaces mostrando el estado de cada documento. Elegir un registro representativo (`search` con dominio sobre un enlace, p. ej. `invoice_ids != false`) y uno atípico (cancelado, parcial).
7. **Profundizar donde importe**: repetir `profile` en cada modelo enlazado; leer `base.automation`/`ir.actions.server` (campo `code`) para efectos ocultos; aprobaciones (`approval.rule`, `*_double_validation`) y picking types / diarios / rutas para saber *dónde* ocurre cada paso.
8. **Proponer el flujo** en este formato:
   - Secuencia de pasos: documento, estado de inicio → acción (botón) → estado final, y quién/qué la dispara (usuario, automatización, cron).
   - Documentos que se generan en cada paso y su enlace (campo).
   - Puntos de decisión/aprobación y ramas (parcial, backorder, devolución, cancelación) **con su frecuencia observada**.
   - Qué está configurado pero sin uso, y qué se usa sin estar documentado.
   - Hallazgos de higiene (borradores viejos, estados atascados) con IDs, sin corregir sin confirmación.

## Límites a tener presentes

- Los botones se leen de la vista form; hay lógica que corre sin botón (automatizaciones, `create` heredados) y solo se ve leyendo las acciones de servidor.
- `to approve`, parciales o devoluciones pueden tener 0 registros en una base de pruebas: reportarlos como "existe, sin evidencia de uso".
- Los nombres de campos de estado varían (`state`, `invoice_status`, `receipt_status`, `stage_id`). Los estados tipo `stage_id` (many2one) no los cubre `profile`: consultar su modelo de etapas aparte.

## Ejemplo ejecutado: compra → recepción → factura (Odoo 19, DB de pruebas)

Entrada `purchase.order`. Hallazgos:
- Estados: `draft → sent → to approve → purchase → cancel`, más ejes paralelos `receipt_status` (pending/partial/full) e `invoice_status` (no/to invoice/invoiced). Confirmar = `button_confirm`; `to approve` solo si hay doble validación (`button_approve`).
- Enlaces con datos: `picking_ids → stock.picking` (recepciones) y `invoice_ids → account.move` (facturas de proveedor); recepciones → `stock.move`; factura → documentos EDI MX (`l10n_mx_edi.document`).
- Traza PO#1: `purchase` / `invoiced` / `partial` → factura en borrador + recepción WH/IN/00002 `assigned` con backorder de WH/IN/00001 `done` (recepción parcial real).
- Automatización: reinicio de aprobaciones al cambiar el PO, cron de recordatorio de compra, plantillas RFQ/PO/recordatorio.
