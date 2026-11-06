"""
Conciliación entre el POS (caja) y el sistema de facturación electrónica.

Cada venta registrada en caja debería tener su comprobante emitido con el mismo
monto, y cada nota de crédito debería apuntar a un comprobante que exista.
Este script compara ambas fuentes por número de comprobante y clasifica cada caso:

- OK                         -> existe en ambos con el mismo monto
- Falta en facturación       -> se vendió en caja pero no se emitió
- No está en POS             -> se emitió pero no hay venta en caja
- Diferencia de monto        -> existe en ambos, pero el monto no cuadra
- Emitido más de una vez     -> el mismo comprobante aparece repetido
- NC sin comprobante origen  -> nota de crédito que referencia algo inexistente

Genera un Excel con el detalle y un resumen por sede.

Uso:
    python conciliar.py
    python conciliar.py --tolerancia 0.05
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill

BASE = Path(__file__).parent
COLORES = {
    "OK": "E2F0D9",
    "Diferencia de monto": "FFF2CC",
    "Falta en facturación": "F8CBAD",
    "No está en POS": "F8CBAD",
    "Emitido más de una vez": "FCE4D6",
    "NC sin comprobante origen": "F8CBAD",
}


def cargar(ruta_pos: Path, ruta_fac: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    pos = pd.read_csv(ruta_pos, parse_dates=["fecha_hora"])
    fac = pd.read_csv(ruta_fac, dtype={"referencia": str})
    for df in (pos, fac):
        df["comprobante"] = df["comprobante"].str.strip().str.upper()
    return pos, fac


def conciliar_ventas(pos: pd.DataFrame, fac: pd.DataFrame, tolerancia: float) -> pd.DataFrame:
    emitidos = fac[fac["tipo"] != "NOTA DE CREDITO"]

    repetidos = emitidos[emitidos.duplicated("comprobante", keep="first")].copy()
    repetidos["estado"] = "Emitido más de una vez"

    unicos = emitidos.drop_duplicates("comprobante")
    cruce = pos.merge(unicos, on="comprobante", how="outer",
                      suffixes=("_pos", "_fac"), indicator=True)
    cruce["sede"] = cruce["sede_pos"].fillna(cruce["sede_fac"])
    cruce["tipo"] = cruce["tipo_pos"].fillna(cruce["tipo_fac"])
    cruce["diferencia"] = (cruce["total_fac"] - cruce["total_pos"]).round(2)

    def estado(fila) -> str:
        if fila["_merge"] == "left_only":
            return "Falta en facturación"
        if fila["_merge"] == "right_only":
            return "No está en POS"
        if abs(fila["diferencia"]) > tolerancia:
            return "Diferencia de monto"
        return "OK"

    cruce["estado"] = cruce.apply(estado, axis=1)
    detalle = cruce[["sede", "tipo", "comprobante", "fecha_hora", "total_pos", "total_fac",
                     "diferencia", "estado"]]

    repetidos = repetidos.rename(columns={"total": "total_fac"})[["sede", "tipo", "comprobante", "total_fac", "estado"]]
    return pd.concat([detalle, repetidos], ignore_index=True)


def revisar_notas_credito(fac: pd.DataFrame) -> pd.DataFrame:
    nc = fac[fac["tipo"] == "NOTA DE CREDITO"].copy()
    existentes = set(fac.loc[fac["tipo"] != "NOTA DE CREDITO", "comprobante"])
    nc["estado"] = nc["referencia"].map(lambda r: "OK" if r in existentes else "NC sin comprobante origen")
    return nc[["sede", "comprobante", "referencia", "total", "fecha_emision", "estado"]]


def resumen_por_sede(ventas: pd.DataFrame, nc: pd.DataFrame) -> pd.DataFrame:
    todos = pd.concat([ventas[["sede", "estado"]], nc[["sede", "estado"]]])
    tabla = pd.crosstab(todos["sede"], todos["estado"])
    tabla["Total observados"] = tabla.drop(columns="OK", errors="ignore").sum(axis=1)
    monto = ventas.loc[ventas["estado"] == "Falta en facturación"].groupby("sede")["total_pos"].sum()
    tabla["S/ sin facturar"] = monto.reindex(tabla.index).fillna(0).round(2)
    return tabla.reset_index()


def exportar(hojas: dict[str, pd.DataFrame], salida: Path) -> None:
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        for nombre, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre, index=False)
            hoja = writer.sheets[nombre]
            for celda in hoja[1]:
                celda.font = Font(bold=True, color="FFFFFF")
                celda.fill = PatternFill("solid", fgColor="364D5A")
            if "estado" in df.columns:
                col = df.columns.get_loc("estado") + 1
                for fila in range(2, len(df) + 2):
                    color = COLORES.get(hoja.cell(fila, col).value)
                    if color:
                        hoja.cell(fila, col).fill = PatternFill("solid", fgColor=color)
            for columna in hoja.columns:
                ancho = max(len(str(c.value or "")) for c in columna)
                hoja.column_dimensions[columna[0].column_letter].width = min(ancho + 2, 40)
            hoja.freeze_panes = "A2"


def main() -> None:
    parser = argparse.ArgumentParser(description="Concilia POS contra facturación electrónica.")
    parser.add_argument("--pos", type=Path, default=BASE / "data" / "ventas_pos.csv")
    parser.add_argument("--facturacion", type=Path, default=BASE / "data" / "facturacion.csv")
    parser.add_argument("--tolerancia", type=float, default=0.02,
                        help="Diferencia máxima aceptada en soles (por redondeo). Por defecto 0.02")
    parser.add_argument("--salida", type=Path, default=BASE / "salida" / "conciliacion.xlsx")
    args = parser.parse_args()

    pos, fac = cargar(args.pos, args.facturacion)
    ventas = conciliar_ventas(pos, fac, args.tolerancia)
    nc = revisar_notas_credito(fac)
    resumen = resumen_por_sede(ventas, nc)

    observados = ventas[ventas["estado"] != "OK"].sort_values(["sede", "estado"])
    args.salida.parent.mkdir(exist_ok=True)
    exportar({"Resumen por sede": resumen, "Observados": observados,
              "Notas de credito": nc, "Detalle completo": ventas}, args.salida)

    print(f"Tickets en POS: {len(pos)} | Comprobantes en facturación: {len(fac)}")
    print(ventas["estado"].value_counts().to_string())
    print(f"Notas de crédito sin origen: {(nc['estado'] != 'OK').sum()}")
    print(f"Reporte guardado en {args.salida}")


if __name__ == "__main__":
    main()
