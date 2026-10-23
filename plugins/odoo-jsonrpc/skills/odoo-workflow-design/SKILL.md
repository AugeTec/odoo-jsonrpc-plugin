---
name: odoo-workflow-design
description: Usar para diseñar y lograr un flujo de trabajo de punta a punta en una base Odoo a partir de una meta (p. ej. "que una compra importada termine recibida y facturada con lotes", "cobrar por anticipado y entregar en etapas"). El agente investiga la instancia, prueba caminos reales con registros de prueba hasta lograr la meta y entrega el flujo validado. Puede o no tener permitido personalizar (módulos, Studio, automatizaciones, código); si no, solo recomienda personalizaciones cuando son estrictamente necesarias. Requiere la skill odoo-jsonrpc para la conexión.
---

# Diseñar flujos de trabajo en Odoo

Parte de una **meta de negocio**, no de un modelo. El agente no se limita a describir lo que existe: **propone un diseño, lo prueba en la instancia, observa qué falla y lo ajusta** hasta que la meta se logra o queda demostrado por qué no es posible sin personalizar.

Herramienta única: `odoo.py`/`connect()` de `odoo-jsonrpc` (lectura con `search_read`, `fields_get`, `get_views`, `read_group`; pruebas con `create`, `write`, `action_confirm`, `button_validate`…). No hay script propio. No asumir el flujo "estándar": la instancia puede tener módulos, Studio o automatizaciones que lo cambian.

## 0. Acordar antes de empezar (preguntar solo lo que falte)

1. **Meta**: resultado esperado y cómo se verifica (estados finales, documentos generados, cantidades/importes, quién interviene).
2. **Permiso de personalización** — es un modo, pregúntalo si no está dicho:
   - **`sin-personalizar`** (por defecto si hay duda): solo configuración estándar y datos (ajustes, diarios, rutas, tipos de operación, reglas, plantillas, productos, secuencias…) y el uso normal de los métodos de Odoo. Prohibido crear/editar módulos, vistas, campos, reglas de servidor, automatizaciones, Studio.
   - **`personalizar`**: además se permiten campos/vistas Studio, automatizaciones (`base.automation`), acciones de servidor y módulos propios, siempre después de agotar lo estándar (ver §3).
3. **Entorno de pruebas**: dónde se puede escribir. Preferir base de pruebas/staging/copia. Si solo hay producción, las pruebas se limitan a lo reversible y requieren confirmación explícita antes de la primera escritura.

## 1. Entender el punto de partida (lectura)

- Contexto: `ir.module.module` con `state=installed` y `application=true`; ajustes relevantes (`ir.config_parameter`, `res.config.settings` por campo), compañías, diarios, almacenes/tipos de operación, rutas, listas de precios, impuestos.
- Modelo de entrada del flujo (`purchase.order`, `sale.order`, `mrp.production`, `helpdesk.ticket`…). Verificar con `search_count`.
- **Estados**: `fields_get` del modelo → campos `selection` con nombre `state`/`status`/`stage` (o `*_status`); conteo por valor con `read_group '[[], ["<campo>"], ["<campo>"]]'`.
- **Botones (transiciones)**: `get_views '[[[false,"form"]]]'` → en el `arch`, los `<button type="object|action" name=...>` y su `invisible` (desde qué estado aplican).
- **Documentos enlazados con datos reales**: de `fields_get`, los `many2one/one2many/many2many` hacia modelos de negocio; `search_count '[[["<campo>","!=",false]]]'` descarta enlaces con 0 registros (existen en código pero no se usan). Repetir un nivel más en los modelos enlazados.
- **Transiciones usadas**: `mail.tracking.value` con `[["mail_message_id.model","=","<modelo>"],["field_id.name","in",[<campos de estado>]]]`, agrupando `old_value_char → new_value_char`.
- **Caso real**: `read` de un registro representativo y de uno atípico (cancelado, parcial) siguiendo sus enlaces y mostrando el estado de cada documento; es la mejor referencia para imitar.
- Leer `base.automation`/`ir.actions.server` (campo `code`), aprobaciones y reglas para efectos ocultos.

## 2. Plan → prueba → observación (el ciclo central)

1. **Hipótesis de flujo**: lista ordenada de pasos (documento, método/botón, estado esperado) que, según §1, llevaría a la meta.
2. **Ejecutar en pequeño** con datos de prueba mínimos, por el flujo real (`action_confirm`, `button_validate`, `action_post`, wizards como `stock.immediate.transfer`/`stock.backorder.confirmation` vía `context`/`web_save`…). No escribir `state` como atajo: eso no prueba nada.
3. **Observar** tras cada paso: estado del documento, documentos generados, cantidades, asientos. Comparar con lo esperado.
4. **Si falla o no cuadra**: leer el error (`error.data.debug`), el código/vista/configuración implicada y probar la alternativa: otro tipo de operación, otro ajuste, otra ruta, otro orden de pasos, otro método. Registrar cada intento (qué se probó, resultado, por qué).
5. **Iterar** hasta lograr la meta, o hasta tener evidencia de que lo estándar no alcanza.
6. **Variantes**: repetir con los casos que importan (parcial/backorder, devolución, cancelación, multicompañía, moneda, lote/serie) y probar que el flujo resiste.

Reglas de las pruebas:
- Todo registro de prueba lleva una marca reconocible (`[TEST-WFD]` en nombre/referencia/nota). Llevar en el script de la sesión (`connect()`) la lista de IDs creados por modelo y los valores anteriores de lo modificado, para poder deshacer.
- No tocar registros preexistentes salvo que el usuario lo pida; si una prueba lo exige, confirmar antes.
- Al terminar, deshacer por el flujo real, en orden inverso (`button_cancel`, `action_cancel`, reversa de asientos) y restaurar los valores anteriores; los documentos que Odoo no deja borrar (publicados, hechos) se **reportan con ID**, no se fuerzan. Nunca `unlink` ni SQL para limpiar sin confirmación.
- Cambios de configuración hechos para probar se anotan (valor anterior → nuevo) y se revierten o se proponen como parte del diseño con confirmación.

## 3. Escalera de soluciones (de menos a más invasiva)

Probar en este orden; subir un peldaño solo con evidencia de que el anterior falló:

1. **Datos y uso correcto** — el flujo ya existe pero faltaban datos (producto sin ruta, diario/impuesto/posición fiscal, tipo de operación).
2. **Configuración estándar** — ajustes, rutas, reglas de reabastecimiento, aprobaciones, plantillas, secuencias, informes, acciones planificadas ya existentes.
3. **Módulo estándar/no instalado** — un módulo oficial instalado o por instalar resuelve la meta (instalar = cambio de instancia: confirmar).
4. **Personalización ligera** — solo en modo `personalizar`: campos/vistas, automatizaciones, acciones de servidor, informes.
5. **Desarrollo a la medida** — solo en modo `personalizar`: módulo propio.

### Comportamiento según el modo

- **`personalizar`**: aplicar el peldaño mínimo suficiente, probarlo, y dejar documentado qué se creó (modelo, ID, XML ID) y cómo revertirlo. Cada creación persistente se confirma con el usuario antes de escribirla en una base que no sea de pruebas.
- **`sin-personalizar`**: nunca crear nada de los peldaños 4-5, ni como "prueba rápida". Si tras agotar 1-3 la meta no se logra, **recomendar** la personalización solo si es **requerida**, y en la recomendación incluir: la brecha concreta, los caminos estándar probados y por qué fallaron (con evidencia), el peldaño mínimo propuesto, su alcance y riesgos, y la alternativa de proceso (cambiar el procedimiento humano) si existe. Si algo se puede lograr estándar aunque sea menos cómodo, **no** recomendar personalización: entregar el camino estándar y mencionar la limitación.
  No recomendar personalizaciones "deseables" o de comodidad; si se quiere mencionarlas, van aparte como mejoras opcionales, claramente separadas de las requeridas.

## 4. Entrega

Presentar:
- **Resultado**: meta lograda / lograda con limitaciones / no lograda sin personalizar.
- **Flujo validado**: pasos en orden — documento, acción (botón/método), estado inicial → final, quién/qué la dispara (usuario, automatización, cron) — y los documentos que se generan y su enlace (campo).
- **Configuración necesaria** (valor exacto y dónde) y la que ya estaba.
- **Ramas probadas** (parcial, devolución, cancelación…) con su resultado y las no probadas.
- **Intentos descartados** y por qué (evita repetirlos).
- **Personalizaciones**: realizadas (modo `personalizar`) o requeridas recomendadas (modo `sin-personalizar`), con la justificación de §3.
- **Estado de la limpieza**: registros de prueba creados, revertidos y los que quedaron (IDs).
- Hallazgos de higiene de la instancia (borradores viejos, estados atascados) con IDs, sin corregir sin confirmación.

## Límites a tener presentes

- Los botones se leen de la vista form; hay lógica sin botón (automatizaciones, `create` heredados) visible solo en las acciones de servidor.
- Ramas sin registros en la base (aprobación, devoluciones) se reportan como "existe, sin evidencia de uso" hasta probarlas.
- Los campos de etapa (`stage_id`, many2one) no los cubre un perfil por estados: consultar su modelo de etapas aparte.
- Una prueba exitosa en staging no garantiza producción si difieren módulos, ajustes o datos maestros: contrastar con §1 antes de aplicar.
