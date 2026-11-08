"""
Caja (BillingPort) para los motores relacionales: PostgreSQL (hospital) y MySQL (pediátrico).

Las dos bases tienen las mismas tablas (arancel, factura, detalle_factura, pago) y los
mismos triggers, así que el SQL es común. Cada adaptador solo dice:
  * _PREFIJO_CAJA: "HG" o "CP" para numerar facturas y recibos
  * _ultimo_id(cur, tabla, columna): cómo obtener el id recién insertado
La lógica que protege el dinero (no cobrar de más, no pagar facturas anuladas, no anular
con pagos, total = suma del detalle) vive en los triggers de cada base.
"""

import secrets
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ...domain.ports import BillingPort


def _plano(fila: Dict[str, Any]) -> Dict[str, Any]:
    """Decimal -> float y fechas -> texto, para que la API las entregue como JSON."""
    out = {}
    for k, v in fila.items():
        if isinstance(v, Decimal):
            out[k] = float(v)
        elif hasattr(v, "isoformat"):
            out[k] = v.isoformat(sep=" ", timespec="minutes") if hasattr(v, "hour") else v.isoformat()
        else:
            out[k] = v
    return out


class SQLBillingMixin(BillingPort):
    _PREFIJO_CAJA = "XX"

    def _ultimo_id(self, cur, tabla: str, columna: str) -> int:   # pragma: no cover - lo define cada adaptador
        raise NotImplementedError

    # ------------------------------------------------------------- aranceles
    def list_tariffs(self) -> List[Dict[str, Any]]:
        with self._tx() as cur:
            cur.execute("SELECT codigo, descripcion, categoria, precio, activo FROM arancel ORDER BY categoria, descripcion")
            return [{**_plano(r), "activo": bool(r["activo"])} for r in cur.fetchall()]

    def save_tariff(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._tx() as cur:
            cur.execute("SELECT codigo FROM arancel WHERE codigo = %s FOR UPDATE", (data["codigo"],))
            if cur.fetchone():
                cur.execute("UPDATE arancel SET descripcion = %s, categoria = %s, precio = %s, activo = %s WHERE codigo = %s",
                            (data["descripcion"], data["categoria"], data["precio"], bool(data.get("activo", True)), data["codigo"]))
            else:
                cur.execute("INSERT INTO arancel (codigo, descripcion, categoria, precio, activo) VALUES (%s, %s, %s, %s, %s)",
                            (data["codigo"], data["descripcion"], data["categoria"], data["precio"], bool(data.get("activo", True))))
            cur.execute("SELECT codigo, descripcion, categoria, precio, activo FROM arancel WHERE codigo = %s", (data["codigo"],))
            r = cur.fetchone()
            return {**_plano(r), "activo": bool(r["activo"])}

    # ------------------------------------------------------------- facturas
    _SQL_FACTURA = """SELECT f.*, f.monto_total - f.monto_pagado AS saldo,
                             p.nombres AS p_nombres, p.apellidos AS p_apellidos
                      FROM factura f JOIN {pac} p ON p.id_paciente = f.id_paciente"""

    def _tabla_pacientes(self) -> str:
        return "paciente"

    def _facturas(self, cur, where: str, params: tuple) -> List[Dict[str, Any]]:
        cur.execute(self._SQL_FACTURA.format(pac=self._tabla_pacientes()) + f" WHERE {where} ORDER BY f.fecha_emision DESC, f.id_factura DESC", params)
        out = []
        for r in cur.fetchall():
            r = _plano(r)
            r["paciente"] = f"{r.pop('p_nombres')} {r.pop('p_apellidos')}"
            out.append(r)
        return out

    def list_invoices(self, estado: Optional[str] = None, patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
        cond, params = ["1 = 1"], []
        if estado:
            cond.append("f.estado = %s")
            params.append(estado)
        if patient_id:
            cond.append("f.id_paciente = %s")
            params.append(int(patient_id))
        with self._tx() as cur:
            return self._facturas(cur, " AND ".join(cond), tuple(params))

    def _factura_completa(self, cur, invoice_id: int) -> Dict[str, Any]:
        lista = self._facturas(cur, "f.id_factura = %s", (int(invoice_id),))
        if not lista:
            raise ValueError("Factura no encontrada")
        f = lista[0]
        cur.execute("SELECT codigo_arancel, concepto, cantidad, precio_unitario, subtotal FROM detalle_factura WHERE id_factura = %s ORDER BY id_detalle", (f["id_factura"],))
        f["detalle"] = [_plano(r) for r in cur.fetchall()]
        cur.execute("SELECT numero_recibo, fecha_pago, monto, metodo_pago, referencia, recibido_por FROM pago WHERE id_factura = %s ORDER BY id_pago", (f["id_factura"],))
        f["pagos"] = [_plano(r) for r in cur.fetchall()]
        return f

    def get_invoice(self, invoice_id: int) -> Dict[str, Any]:
        with self._tx() as cur:
            return self._factura_completa(cur, invoice_id)

    def create_invoice(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pid = int(data["id_paciente"])
        with self._tx() as cur:
            cur.execute(f"SELECT nombres, apellidos FROM {self._tabla_pacientes()} WHERE id_paciente = %s FOR UPDATE", (pid,))
            pac = cur.fetchone()
            if not pac:
                raise ValueError(f"Paciente {pid} no encontrado")
            origen_tipo, origen_id = data.get("origen_tipo") or "manual", data.get("origen_id")
            if origen_id:
                cur.execute("SELECT numero_factura FROM factura WHERE origen_tipo = %s AND origen_id = %s AND estado <> 'anulada'",
                            (origen_tipo, int(origen_id)))
                ya = cur.fetchone()
                if ya:
                    raise ValueError(f"Eso ya está facturado en la factura {ya['numero_factura']}")
            temporal = "TMP-" + secrets.token_hex(6)
            cur.execute("""INSERT INTO factura (numero_factura, id_paciente, nit, nombre_facturacion, origen_tipo, origen_id)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (temporal, pid, data.get("nit") or "CF",
                         data.get("nombre_facturacion") or f"{pac['nombres']} {pac['apellidos']}", origen_tipo,
                         int(origen_id) if origen_id else None))
            fid = self._ultimo_id(cur, "factura", "id_factura")
            cur.execute("UPDATE factura SET numero_factura = %s WHERE id_factura = %s", (f"{self._PREFIJO_CAJA}-{fid:06d}", fid))
            for l in data["lineas"]:
                cur.execute("""INSERT INTO detalle_factura (id_factura, codigo_arancel, concepto, cantidad, precio_unitario)
                               VALUES (%s, %s, %s, %s, %s)""",
                            (fid, l.get("codigo_arancel") or None, l["concepto"], l["cantidad"], l["precio_unitario"]))
            return self._factura_completa(cur, fid)

    def register_invoice_payment(self, invoice_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        with self._tx() as cur:
            temporal = "TMP-" + secrets.token_hex(6)
            # El trigger de la base bloquea la factura y rechaza pagos mayores al saldo
            cur.execute("""INSERT INTO pago (id_factura, numero_recibo, monto, metodo_pago, referencia, recibido_por)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (int(invoice_id), temporal, data["monto"], data["metodo_pago"], data.get("referencia") or None,
                         data.get("recibido_por") or "Caja"))
            pago_id = self._ultimo_id(cur, "pago", "id_pago")
            cur.execute("UPDATE pago SET numero_recibo = %s WHERE id_pago = %s", (f"R-{self._PREFIJO_CAJA}-{pago_id:06d}", pago_id))
            return self._factura_completa(cur, invoice_id)

    def void_invoice(self, invoice_id: int, motivo: str) -> Dict[str, Any]:
        with self._tx() as cur:
            cur.execute("SELECT estado FROM factura WHERE id_factura = %s FOR UPDATE", (int(invoice_id),))
            f = cur.fetchone()
            if not f:
                raise ValueError("Factura no encontrada")
            if f["estado"] == "anulada":
                raise ValueError("La factura ya está anulada")
            cur.execute("UPDATE factura SET estado = 'anulada', motivo_anulacion = %s WHERE id_factura = %s", (motivo, int(invoice_id)))
            return self._factura_completa(cur, invoice_id)

    def suggested_charges(self, origen_tipo: str, origen_id: int) -> List[Dict[str, Any]]:
        return []
