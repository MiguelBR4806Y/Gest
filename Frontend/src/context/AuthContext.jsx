import { createContext, useContext, useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../lib/api";

const AuthContext = createContext(null);

const STORAGE_KEYS = {
  token: "token",
  usuario: "usuario",
  user_email: "user_email",
  email_verified: "email_verified",
  provider: "provider",
  nombre_negocio: "nombre_negocio",
  tasa_cambio: "tasa_cambio",
  tasa_cambio_configurada: "tasa_cambio_configurada",
  zona_horaria: "zona_horaria",
};

function loadUserFromStorage() {
  const token = sessionStorage.getItem(STORAGE_KEYS.token);
  if (!token) return null;
  return {
    token,
    usuario: sessionStorage.getItem(STORAGE_KEYS.usuario),
    email: sessionStorage.getItem(STORAGE_KEYS.user_email),
    email_verified: sessionStorage.getItem(STORAGE_KEYS.email_verified) === "true",
    provider: sessionStorage.getItem(STORAGE_KEYS.provider),
    nombre_negocio: sessionStorage.getItem(STORAGE_KEYS.nombre_negocio),
    tasa_cambio: Number(sessionStorage.getItem(STORAGE_KEYS.tasa_cambio) || 36),
    tasa_cambio_configurada: sessionStorage.getItem(STORAGE_KEYS.tasa_cambio_configurada) === "true",
    zona_horaria: sessionStorage.getItem(STORAGE_KEYS.zona_horaria) || "America/Managua",
  };
}

function saveUserToStorage(data) {
  sessionStorage.setItem(STORAGE_KEYS.token, data.token);
  sessionStorage.setItem(STORAGE_KEYS.usuario, data.usuario);
  sessionStorage.setItem(STORAGE_KEYS.user_email, data.email ?? "");
  sessionStorage.setItem(STORAGE_KEYS.email_verified, String(data.email_verified ?? false));
  sessionStorage.setItem(STORAGE_KEYS.provider, data.provider ?? "");
  sessionStorage.setItem(STORAGE_KEYS.nombre_negocio, data.nombre_negocio);
  sessionStorage.setItem(STORAGE_KEYS.tasa_cambio, String(data.tasa_cambio ?? 36));
  sessionStorage.setItem(STORAGE_KEYS.tasa_cambio_configurada, String(data.tasa_cambio_configurada ?? false));
  sessionStorage.setItem(STORAGE_KEYS.zona_horaria, data.zona_horaria || "America/Managua");
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setUser(loadUserFromStorage());
    setLoading(false);
  }, []);

  const guardarSesion = useCallback((data) => {
    saveUserToStorage(data);
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
  }, []);

  const login = useCallback(async (usuario, password) => {
    const data = await api.post("/auth/login", { usuario, password });
    guardarSesion(data);
    return data;
  }, [guardarSesion]);

  const googleLogin = useCallback(async (credential) => {
    const data = await api.post("/auth/oauth/google", { credential });
    guardarSesion(data);
    return data;
  }, [guardarSesion]);

  const registro = useCallback(async (usuario, password, nombre_negocio, tasa_cambio = 36, email = "") => {
    await api.post("/auth/registro", { usuario, password, nombre_negocio, tasa_cambio, email });
  }, []);

  const logout = useCallback(() => {
    sessionStorage.clear();
    setUser(null);
  }, []);

  const updateNegocio = useCallback((nombre_negocio) => {
    sessionStorage.setItem(STORAGE_KEYS.nombre_negocio, nombre_negocio);
    setUser(u => ({ ...u, nombre_negocio }));
  }, []);

  const updateUser = useCallback((data) => {
    const MAP = { email: 'user_email' };
    Object.entries(data).forEach(([k, v]) => {
      const key = MAP[k] ?? k;
      sessionStorage.setItem(key, String(v));
    });
    setUser(u => ({ ...u, ...data }));
  }, []);

  const value = useMemo(() => ({
    user, loading, login, googleLogin, logout, registro, updateNegocio, updateUser
  }), [user, loading, login, googleLogin, logout, registro, updateNegocio, updateUser]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
