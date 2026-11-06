# Conciliación POS vs. facturación electrónica

Compara las ventas registradas en caja (POS) con los comprobantes emitidos en el sistema de facturación electrónica, sede por sede, y genera un Excel con cada diferencia encontrada.

En un negocio con varias sedes, los dos sistemas no siempre cuadran: un comprobante no se envía, una boleta se emite dos veces o una nota de crédito apunta a un comprobante que no existe. Revisarlo a mano con filtros en Excel toma horas. Este script lo hace en segundos.

> Los datos de este repositorio son **ficticios**: un mes de ventas de 4 sedes inventadas, generado por `generar_datos.py`.

## Qué clasifica

| Estado | Significado |
|---|---|
| OK | Existe en ambos sistemas con el mismo monto |
| Falta en facturación | Se vendió en caja, pero el comprobante no se emitió |
| No está en POS | Se emitió un comprobante sin venta en caja |
| Diferencia de monto | Existe en ambos, pero el monto no coincide |
| Emitido más de una vez | El mismo número de comprobante aparece repetido |
| NC sin comprobante origen | Nota de crédito que referencia un comprobante inexistente |

Las diferencias de céntimos por redondeo no se marcan. La tolerancia se ajusta con `--tolerancia` (por defecto S/ 0.02).

## Cómo usarlo

```bash
pip install -r requirements.txt
python generar_datos.py   # crea data/ventas_pos.csv y data/facturacion.csv
python conciliar.py       # crea salida/conciliacion.xlsx
```

## Resultado con los datos de ejemplo

```
Tickets en POS: 4379 | Comprobantes en facturación: 4384
OK                        4354
Falta en facturación        14
Diferencia de monto         11
Emitido más de una vez       4
Notas de crédito sin origen: 3
```

| Sede | Diferencia de monto | Emitido 2 veces | Falta en facturación | NC sin origen | Total observados | S/ sin facturar |
|---|---|---|---|---|---|---|
| Sede Centro | 2 | 2 | 3 | 0 | 7 | 119.55 |
| Sede Norte | 3 | 0 | 4 | 1 | 8 | 132.31 |
| Sede Playa | 4 | 0 | 5 | 1 | 10 | 229.92 |
| Sede Sur | 2 | 2 | 2 | 1 | 7 | 84.22 |

El Excel trae cuatro hojas: **Resumen por sede**, **Observados** (solo lo que hay que revisar), **Notas de crédito** y **Detalle completo**. Cada estado tiene su color y los encabezados quedan fijos.

## Tecnologías

Python · pandas · openpyxl

## Próximos pasos

- Conectarse directo a las bases de datos del POS y de facturación con SQL
- Conciliar también por medio de pago (efectivo, tarjeta, Yape, Plin) contra los depósitos
- Dashboard en Power BI con la evolución diaria de observados por sede
