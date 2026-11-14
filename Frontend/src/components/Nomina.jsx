import { useEffect, useState } from "react";
import { Calculator, Info } from "lucide-react";

import Modal from "./Modal";
import { Button } from "./ui/Button";
import { api, fmtMoney } from "../lib/api";
import { useToast } from "../context/ToastContext";

/** Desglose bruto → deducciones → neto, con el costo patronal. */
export function DesgloseNomina({ nomina, compacto = false }) {
  if (!nomina) return null;
  const extra = nomina.detalle_extra ?? [];
  const filas = [
    { etiqueta: "Salario base", valor: nomina.salario_base ?? nomina.salario_bruto, fuerte: true },
    ...extra.map((e) => ({
      etiqueta: e.concepto,
      valor: e.monto,
      nota: e.recurrente ? "mensual" : undefined,
    })),
    { etiqueta: `INSS laboral (${nomina.parametros.inss_laboral_pct}%)`, valor: -nomina.inss_laboral },
    { etiqueta: "IR mensual", valor: -nomina.ir_mensual },
  ];

  return (
    <div className={compacto ? "" : "rounded-xl border border-border bg-surface-elevated/40 p-4"}>
      <dl className="space-y-1.5">
        {filas.map((f, i) => (
          <div key={`${f.etiqueta}-${i}`} className="flex items-baseline justify-between gap-4 text-sm">
            <dt className={f.fuerte ? "font-medium text-content" : "text-content-muted"}>
              {f.etiqueta}
              {f.nota && <span className="ml-1 text-[10px] text-content-subtle">({f.nota})</span>}
            </dt>
            <dd className={`tabular ${f.valor < 0 ? "text-red-600 dark:text-red-400" : "text-content"} ${f.fuerte ? "font-semibold" : ""}`}>
              {fmtMoney(f.valor)}
            </dd>
          </div>
        ))}
        {extra.length > 0 && (
          <div className="flex items-baseline justify-between gap-4 pt-2 border-t border-border/70 text-sm">
            <dt className="font-medium text-content">Bruto del periodo</dt>
            <dd className="tabular font-medium text-content">{fmtMoney(nomina.salario_bruto)}</dd>
          </div>
        )}
        <div className="flex items-baseline justify-between gap-4 pt-2 border-t border-border/70">
          <dt className="font-semibold text-content">Neto a pagar</dt>
          <dd className="tabular font-bold text-secondary-600 dark:text-secondary-400">
            {fmtMoney(nomina.salario_neto)}
          </dd>
        </div>
      </dl>

      {!compacto && (
        <>
          <dl className="mt-4 space-y-1.5 border-t border-border/70 pt-3">
            <div className="flex items-baseline justify-between gap-4 text-sm">
              <dt className="text-content-muted">
                INSS patronal ({nomina.parametros.inss_patronal_pct}%)
              </dt>
              <dd className="tabular text-content-muted">{fmtMoney(nomina.inss_patronal)}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4 text-sm">
              <dt className="text-content-muted">INATEC ({nomina.parametros.inatec_pct}%)</dt>
              <dd className="tabular text-content-muted">{fmtMoney(nomina.inatec)}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4 pt-1">
              <dt className="text-sm font-medium text-content">Costo total para la empresa</dt>
              <dd className="tabular font-semibold text-content">
                {fmtMoney(nomina.costo_total_empleador)}
              </dd>
            </div>
          </dl>

          <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-relaxed text-content-subtle">
            <Info size={12} className="mt-0.5 shrink-0" aria-hidden="true" />
            <span>
              Renta anual proyectada: {fmtMoney(nomina.renta_anual_proyectada)} ·{" "}
              {nomina.exento_ir
                ? "exento de IR"
                : `tramo ${nomina.tramo.tasa}%`}
              . {nomina.parametros.version}
            </span>
          </p>
        </>
      )}
    </div>
  );
}

/**
 * Calculadora de nómina: simula un salario contra el backend para no duplicar
 * la tabla fiscal en el cliente.
 */
export default function CalculadoraNomina({ open, onClose, salarioInicial = 0 }) {
  const { toast } = useToast();
  const [salario, setSalario] = useState(String(salarioInicial || ""));
  const [empleados, setEmpleados] = useState(1);
  const [resultado, setResultado] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [tabla, setTabla] = useState(null);

  useEffect(() => {
    if (!open) return;
    setSalario(salarioInicial ? String(salarioInicial) : "");
    setResultado(null);
  }, [open, salarioInicial]);

  useEffect(() => {
    if (!open || tabla) return;
    api.get("/empleados/nomina/tabla").then(setTabla).catch(() => {});
  }, [open, tabla]);

  async function calcular() {
    const monto = Number(salario);
    if (!Number.isFinite(monto) || monto < 0) {
      toast("Escribe un salario válido", "error");
      return;
    }
    setCargando(true);
    try {
      setResultado(
        await api.post("/empleados/nomina/simular", {
          salario: monto,
          empleados_empresa: Number(empleados) || 1,
        })
      );
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Calculadora de nómina e impuestos"
      size="lg"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose}>
            Cerrar
          </button>
          <Button icon={Calculator} onClick={calcular} loading={cargando}>
            Calcular
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block">
            <span className="label">Salario bruto mensual (C$)</span>
            <input
              type="number"
              min="0"
              step="0.01"
              value={salario}
              onChange={(e) => setSalario(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && calcular()}
              className="input"
              placeholder="15000"
            />
          </label>
          <label className="block">
            <span className="label">Trabajadores en la empresa</span>
            <input
              type="number"
              min="1"
              step="1"
              value={empleados}
              onChange={(e) => setEmpleados(e.target.value)}
              className="input"
              placeholder="1"
            />
          </label>
        </div>

        <p className="text-xs text-content-subtle">
          {Number(empleados) >= 50
            ? "Con 50 trabajadores o más, el INSS patronal es 22.50 %."
            : "Con menos de 50 trabajadores, el INSS patronal es 21.50 %."}
        </p>

        {resultado ? (
          <>
            <DesgloseNomina nomina={resultado} />
            <div className="rounded-xl border border-border p-3 text-xs text-content-muted">
              <p className="font-medium text-content">Aguinaldo</p>
              <p className="mt-1">
                Se provisiona {fmtMoney(resultado.aguinaldo_mensual_provisionado)} al mes
                ({fmtMoney(resultado.aguinaldo_anual)} al año). No cotiza al INSS.
              </p>
            </div>
          </>
        ) : (
          <p className="rounded-xl border border-border bg-surface-elevated/40 p-4 text-sm text-content-muted">
            Escribe un salario y pulsa Calcular para ver INSS, IR y neto.
          </p>
        )}

        {tabla && (
          <details className="rounded-xl border border-border p-3">
            <summary className="cursor-pointer text-sm font-medium text-content">
              Tabla de IR aplicada
            </summary>
            <table className="w-full mt-3">
              <thead>
                <tr>
                  <th className="th">Renta anual</th>
                  <th className="th text-right">Base</th>
                  <th className="th text-right">Tasa</th>
                </tr>
              </thead>
              <tbody>
                {tabla.tramos_ir.map((t) => (
                  <tr key={t.desde} className="table-row">
                    <td className="td text-xs">
                      {fmtMoney(t.desde)} – {t.hasta === null ? "más" : fmtMoney(t.hasta)}
                    </td>
                    <td className="td text-xs text-right tabular">{fmtMoney(t.impuesto_base)}</td>
                    <td className="td text-xs text-right tabular">{t.tasa}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[11px] text-content-subtle">{tabla.nota}</p>
          </details>
        )}
      </div>
    </Modal>
  );
}
