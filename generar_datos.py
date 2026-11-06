"""
Genera datos ficticios de un mes de ventas para probar la conciliación.

- data/ventas_pos.csv       -> lo que registró la caja (POS) en cada sede
- data/facturacion.csv      -> lo que se emitió en el sistema de facturación
                               electrónica (boletas, facturas y notas de crédito)

Se meten diferencias típicas: comprobantes que no llegaron a facturación,
montos distintos, notas de crédito sin comprobante de origen y comprobantes
emitidos dos veces. Todos los datos son inventados.
"""

from pathlib import Path
import random

import numpy as np
import pandas as pd

SEMILLA = 7
random.seed(SEMILLA)
np.random.seed(SEMILLA)

CARPETA = Path(__file__).parent / "data"
SEDES = {"Sede Centro": "B001", "Sede Norte": "B002", "Sede Sur": "B003", "Sede Playa": "B004"}


def ventas_pos(mes: str = "2026-09") -> pd.DataFrame:
    filas = []
    dias = pd.date_range(f"{mes}-01", periods=30, freq="D")
    for sede, serie in SEDES.items():
        correlativo_b, correlativo_f = 1, 1
        for dia in dias:
            tickets = np.random.poisson(45 if dia.day_of_week >= 4 else 30)
            for _ in range(tickets):
                es_factura = random.random() < 0.12
                if es_factura:
                    tipo, num = "FACTURA", f"F{serie[1:]}-{correlativo_f:06d}"
                    correlativo_f += 1
                else:
                    tipo, num = "BOLETA", f"{serie}-{correlativo_b:06d}"
                    correlativo_b += 1
                total = round(float(np.random.lognormal(3.6, 0.5)), 2)
                hora = dia + pd.Timedelta(minutes=random.randint(11 * 60, 23 * 60))
                filas.append({"fecha_hora": hora, "sede": sede, "tipo": tipo,
                              "comprobante": num, "total": total,
                              "medio_pago": random.choice(["Efectivo", "Tarjeta", "Yape", "Plin"])})
    return pd.DataFrame(filas)


def facturacion_desde(pos: pd.DataFrame) -> pd.DataFrame:
    fac = pos[["fecha_hora", "sede", "tipo", "comprobante", "total"]].copy()
    fac["fecha_emision"] = fac["fecha_hora"].dt.date
    fac = fac.drop(columns="fecha_hora")
    fac["referencia"] = ""

    # 1) Comprobantes que nunca llegaron a facturación (falla de envío)
    fac = fac.drop(fac.sample(14, random_state=1).index)

    # 2) Montos distintos (redondeo, descuento aplicado solo en un sistema)
    idx = fac.sample(11, random_state=2).index
    fac.loc[idx, "total"] = (fac.loc[idx, "total"] * np.random.choice([0.9, 0.95, 1.1], len(idx))).round(2)
    idx2 = fac.sample(6, random_state=3).index
    fac.loc[idx2, "total"] = fac.loc[idx2, "total"] + 0.01  # diferencias de céntimo

    # 3) Comprobantes emitidos dos veces
    fac = pd.concat([fac, fac.sample(4, random_state=4)], ignore_index=True)

    # 4) Notas de crédito: la mayoría con comprobante de origen, algunas sin él
    nc = []
    origen = fac[fac["tipo"] == "BOLETA"].sample(12, random_state=5)
    for i, (_, fila) in enumerate(origen.iterrows(), start=1):
        nc.append({"sede": fila["sede"], "tipo": "NOTA DE CREDITO",
                   "comprobante": f"BC{SEDES[fila['sede']][1:]}-{i:06d}",
                   "total": -fila["total"], "fecha_emision": fila["fecha_emision"],
                   "referencia": fila["comprobante"]})
    for j in range(3):
        sede = random.choice(list(SEDES))
        nc.append({"sede": sede, "tipo": "NOTA DE CREDITO",
                   "comprobante": f"BC{SEDES[sede][1:]}-{900 + j:06d}",
                   "total": -round(random.uniform(20, 80), 2),
                   "fecha_emision": pd.Timestamp("2026-09-20").date(),
                   "referencia": f"{SEDES[sede]}-999{j:03d}"})
    return pd.concat([fac, pd.DataFrame(nc)], ignore_index=True)


def main() -> None:
    CARPETA.mkdir(exist_ok=True)
    pos = ventas_pos()
    fac = facturacion_desde(pos)
    pos.to_csv(CARPETA / "ventas_pos.csv", index=False)
    fac.sample(frac=1, random_state=9).to_csv(CARPETA / "facturacion.csv", index=False)
    print(f"POS: {len(pos)} tickets | Facturación: {len(fac)} comprobantes")


if __name__ == "__main__":
    main()
