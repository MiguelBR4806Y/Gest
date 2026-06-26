const BASE = "http://127.0.0.1:8000";

function getToken() {
  return sessionStorage.getItem("token") ?? "";
}

async function request(method, path, body) {
  const opts = {
    method,
    headers: { Authorization: "Bearer " + getToken() },
  };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  get:    (path)        => request("GET",    path),
  post:   (path, body)  => request("POST",   path, body),
  put:    (path, body)  => request("PUT",    path, body),
  delete: (path)        => request("DELETE", path),
  postForm: async (path, formData) => {
    const res = await fetch(BASE + path, {
      method: "POST",
      headers: { Authorization: "Bearer " + getToken() },
      body: formData,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  },
  baseUrl: BASE,
};

export function formatHora(str) {
  if (!str) return "—";
  if (str.length === 5 && str.includes(":")) {
    const [h, m] = str.split(":").map(Number);
    const ampm = h >= 12 ? "PM" : "AM";
    const h12 = h % 12 || 12;
    return `${h12}:${String(m).padStart(2, "0")} ${ampm}`;
  }
  const d = new Date(str);
  if (isNaN(d.getTime())) return str;
  return d.toLocaleString("es-NI", { hour: "numeric", minute: "2-digit", hour12: true });
}

export function fmtMoney(n) {
  return "C$ " + Number(n ?? 0).toLocaleString("es-NI", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function fmtMoneyUSD(n) {
  return "$ " + Number(n ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
