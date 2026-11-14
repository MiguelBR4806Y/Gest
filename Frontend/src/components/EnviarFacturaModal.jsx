import { useEffect, useState } from "react";
import { Mail, MessageCircle, Send } from "lucide-react";

import Modal from "./Modal";
import { Button } from "./ui/Button";
import { Field, Input } from "./ui/Field";
import { api } from "../lib/api";
import { useToast } from "../context/ToastContext";

/**
 * Envío de una factura por correo o WhatsApp.
 *
 * WhatsApp no usa la API de Meta: se genera un enlace de descarga con token y
 * se abre `wa.me` con el mensaje ya escrito.
 */
export default function EnviarFacturaModal({ venta, open, onClose }) {
  const { toast } = useToast();
  const [canal, setCanal] = useState("whatsapp");
  const [destinatario, setDestinatario] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [enlace, setEnlace] = useState(null);

  useEffect(() => {
    if (!open) return;
    setCanal("whatsapp");
    setDestinatario("");
    setEnlace(null);
  }, [open, venta?.id]);

  async function enviar() {
    if (!venta?.id) return;
    setEnviando(true);
    try {
      const cuerpo = { canal };
      if (destinatario.trim()) cuerpo.destinatario = destinatario.trim();

      const data = await api.post(`/facturas/${venta.id}/enviar`, cuerpo);

      if (canal === "email") {
        toast(`Factura enviada a ${data.destinatario}`);
        onClose?.();
        return;
      }

      setEnlace(data);
      if (data.whatsapp_url) {
        window.open(data.whatsapp_url, "_blank", "noopener,noreferrer");
        toast("Se abrió WhatsApp con el mensaje listo");
      } else {
        toast("No hay teléfono del cliente; copia el enlace", "info");
      }
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Enviar factura #${venta?.id ?? ""}`}
      size="sm"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={enviando}>
            Cerrar
          </button>
          <Button onClick={enviar} loading={enviando} icon={Send}>
            {canal === "email" ? "Enviar por correo" : "Abrir WhatsApp"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="segmented" role="tablist" aria-label="Canal de envío">
          <button
            type="button"
            role="tab"
            aria-selected={canal === "whatsapp"}
            className={`segment ${canal === "whatsapp" ? "segment-active" : ""}`}
            onClick={() => setCanal("whatsapp")}
          >
            <MessageCircle size={14} aria-hidden="true" /> WhatsApp
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={canal === "email"}
            className={`segment ${canal === "email" ? "segment-active" : ""}`}
            onClick={() => setCanal("email")}
          >
            <Mail size={14} aria-hidden="true" /> Correo
          </button>
        </div>

        <Field
          label={canal === "email" ? "Correo del cliente" : "Teléfono del cliente"}
          hint={
            canal === "email"
              ? "Si lo dejas vacío se usa el correo guardado del cliente."
              : "Si lo dejas vacío se usa el teléfono guardado del cliente."
          }
        >
          <Input
            type={canal === "email" ? "email" : "tel"}
            value={destinatario}
            onChange={(e) => setDestinatario(e.target.value)}
            placeholder={canal === "email" ? "cliente@correo.com" : "8888-1234"}
            autoComplete="off"
          />
        </Field>

        {canal === "whatsapp" && (
          <p className="text-xs text-content-subtle">
            Se abre WhatsApp con el mensaje y un enlace de descarga válido por 7 días. El cliente
            puede abrir la factura sin iniciar sesión.
          </p>
        )}

        {enlace && (
          <div className="rounded-xl border border-border bg-surface-elevated/50 p-3 space-y-1.5">
            <p className="text-xs font-semibold text-content-muted">Enlace de descarga</p>
            <code className="block text-xs break-all font-mono text-content">{enlace.url}</code>
            <p className="text-[11px] text-content-subtle">
              Caduca el {new Date(enlace.expira).toLocaleDateString("es-NI")}.
            </p>
          </div>
        )}
      </div>
    </Modal>
  );
}
