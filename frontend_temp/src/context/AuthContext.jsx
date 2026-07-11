import { createContext, useContext, useState, useEffect } from "react";
import { api } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = sessionStorage.getItem("token");
    if (token) {
      setUser({
        token,
        usuario: sessionStorage.getItem("usuario"),
        email: sessionStorage.getItem("user_email"),
        email_verified: sessionStorage.getItem("email_verified") === "true",
        provider: sessionStorage.getItem("provider"),
        nombre_negocio: sessionStorage.getItem("nombre_negocio"),
        tasa_cambio: Number(sessionStorage.getItem("tasa_cambio") || 36),
        tasa_cambio_configurada: sessionStorage.getItem("tasa_cambio_configurada") === "true",
        zona_horaria: sessionStorage.getItem("zona_horaria") || "America/Managua",
      });
    }
    setLoading(false);
  }, []);

  function guardarSesion(data) {
    sessionStorage.setItem("token", data.token);
    sessionStorage.setItem("usuario", data.usuario);
    sessionStorage.setItem("user_email", data.email ?? "");
    sessionStorage.setItem("email_verified", String(data.email_verified ?? false));
    sessionStorage.setItem("provider", data.provider ?? "");
    sessionStorage.setItem("nombre_negocio", data.nombre_negocio);
    sessionStorage.setItem("tasa_cambio", String(data.tasa_cambio ?? 36));
    sessionStorage.setItem("tasa_cambio_configurada", String(data.tasa_cambio_configurada ?? false));
    sessionStorage.setItem("zona_horaria", data.zona_horaria || "America/Managua");
    setUser({
      token: data.token, usuario: data.usuario,
      email: data.email ?? "",
      email_verified: data.email_verified ?? false,
      provider: data.provider ?? "",
      nombre_negocio: data.nombre_negocio,
      tasa_cambio: data.tasa_cambio ?? 36,
      tasa_cambio_configurada: data.tasa_cambio_configurada ?? false,
      zona_horaria: data.zona_horaria || "America/Managua",
    });
  }

  async function login(usuario, password) {
    const data = await api.post("/auth/login", { usuario, password });
    guardarSesion(data);
    return data;
  }

  async function googleLogin(credential) {
    const data = await api.post("/auth/oauth/google", { credential });
    guardarSesion(data);
    return data;
  }

  async function registro(usuario, password, nombre_negocio, tasa_cambio = 36, email = "") {
    await api.post("/auth/registro", { usuario, password, nombre_negocio, tasa_cambio, email });
  }

  function logout() {
    sessionStorage.clear();
    setUser(null);
  }

  function updateNegocio(nombre_negocio) {
    sessionStorage.setItem("nombre_negocio", nombre_negocio);
    setUser(u => ({ ...u, nombre_negocio }));
  }

  function updateUser(data) {
    const MAP = { email: 'user_email' };
    Object.entries(data).forEach(([k, v]) => {
      const key = MAP[k] ?? k;
      sessionStorage.setItem(key, String(v));
    });
    setUser(u => ({ ...u, ...data }));
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, googleLogin, logout, registro, updateNegocio, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
