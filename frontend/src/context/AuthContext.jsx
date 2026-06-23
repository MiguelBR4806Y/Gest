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
      });
    }
    setLoading(false);
  }, []);

  async function login(usuario, password) {
    const data = await api.post("/auth/login", { usuario, password });
    sessionStorage.setItem("token", data.token);
    sessionStorage.setItem("usuario", data.usuario);
    sessionStorage.setItem("nombre_negocio", data.nombre_negocio);
    setUser({ token: data.token, usuario: data.usuario, nombre_negocio: data.nombre_negocio });
    return data;
  }

  async function registro(usuario, password, nombre_negocio) {
    await api.post("/auth/registro", { usuario, password, nombre_negocio });
  }

  function logout() {
    sessionStorage.clear();
    setUser(null);
  }

  function updateNegocio(nombre_negocio) {
    sessionStorage.setItem("nombre_negocio", nombre_negocio);
    setUser(u => ({ ...u, nombre_negocio }));
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, registro, updateNegocio }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
