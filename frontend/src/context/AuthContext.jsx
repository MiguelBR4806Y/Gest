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
        nombre_negocio: sessionStorage.getItem("nombre_negocio"),
        tasa_cambio: Number(sessionStorage.getItem("tasa_cambio") || 36),
        tasa_cambio_configurada: sessionStorage.getItem("tasa_cambio_configurada") === "true",
        zona_horaria: sessionStorage.getItem("zona_horaria") || "America/Managua",
      });
    }
    setLoading(false);
  }, []);

  async function login(usuario, password) {
    const data = await api.post("/auth/login", { usuario, password });
    sessionStorage.setItem("token", data.token);
    sessionStorage.setItem("usuario", data.usuario);
    sessionStorage.setItem("nombre_negocio", data.nombre_negocio);
    sessionStorage.setItem("tasa_cambio", String(data.tasa_cambio ?? 36));
    sessionStorage.setItem("tasa_cambio_configurada", String(data.tasa_cambio_configurada ?? false));
    sessionStorage.setItem("zona_horaria", data.zona_horaria || "America/Managua");
    setUser({
      token: data.token, usuario: data.usuario,
      nombre_negocio: data.nombre_negocio,
      tasa_cambio: data.tasa_cambio ?? 36,
      tasa_cambio_configurada: data.tasa_cambio_configurada ?? false,
      zona_horaria: data.zona_horaria || "America/Managua",
    });
    return data;
  }

  async function registro(usuario, password, nombre_negocio, tasa_cambio = 36) {
    await api.post("/auth/registro", { usuario, password, nombre_negocio, tasa_cambio });
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
    Object.entries(data).forEach(([k, v]) => {
      sessionStorage.setItem(k, String(v));
    });
    setUser(u => ({ ...u, ...data }));
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, registro, updateNegocio, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
