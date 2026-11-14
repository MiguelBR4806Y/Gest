import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, EVENTO_SESION_EXPIRADA } from "../lib/api";
import { aplicarColorAcento, esHexValido } from "../lib/color";

const AuthContext = createContext(null);

const CLAVES = {
  token: "token",
  usuario: "usuario",
  nombre: "nombre_usuario",
  rol: "rol",
  modulos: "modulos",
  negocio_id: "negocio_id",
  email: "user_email",
  email_verified: "email_verified",
  provider: "provider",
  nombre_negocio: "nombre_negocio",
  tasa_cambio: "tasa_cambio",
  tasa_cambio_configurada: "tasa_cambio_configurada",
  zona_horaria: "zona_horaria",
  color_acento: "color_acento",
};

const leer = (clave) => {
  try {
    return sessionStorage.getItem(clave);
  } catch {
    return null;
  }
};

const escribir = (clave, valor) => {
  try {
    sessionStorage.setItem(clave, valor == null ? "" : String(valor));
  } catch {
    /* sessionStorage puede estar bloqueado */
  }
};

/** Lee la lista de módulos guardada, con la misma tolerancia al fallo. */
function leerModulos() {
  try {
    const guardado = JSON.parse(leer(CLAVES.modulos) || "[]");
    return Array.isArray(guardado) ? guardado : [];
  } catch {
    return [];
  }
}

function usuarioDesdeStorage() {
  const token = leer(CLAVES.token);
  if (!token) return null;
  const rol = leer(CLAVES.rol) || "admin";
  return {
    token,
    usuario: leer(CLAVES.usuario),
    nombre: leer(CLAVES.nombre) || leer(CLAVES.usuario),
    rol,
    // El admin no necesita lista: sus módulos se derivan del rol.
    modulos: rol === "admin"
      ? ["ventas", "rrhh", "contabilidad"]
      : leerModulos(),
    negocio_id: Number(leer(CLAVES.negocio_id) || 0),
    email: leer(CLAVES.email) ?? "",
    email_verified: leer(CLAVES.email_verified) === "true",
    provider: leer(CLAVES.provider) ?? "",
    nombre_negocio: leer(CLAVES.nombre_negocio),
    tasa_cambio: Number(leer(CLAVES.tasa_cambio) || 36),
    tasa_cambio_configurada: leer(CLAVES.tasa_cambio_configurada) === "true",
    zona_horaria: leer(CLAVES.zona_horaria) || "America/Managua",
    color_acento: leer(CLAVES.color_acento) || "",
  };
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const guardarSesion = useCallback((data) => {
    escribir(CLAVES.token, data.token);
    escribir(CLAVES.usuario, data.usuario);
    escribir(CLAVES.nombre, data.nombre || data.usuario);
    escribir(CLAVES.rol, data.rol || "admin");
    escribir(CLAVES.modulos, JSON.stringify(data.modulos ?? []));
    escribir(CLAVES.negocio_id, data.negocio_id ?? "");
    escribir(CLAVES.email, data.email ?? "");
    escribir(CLAVES.email_verified, data.email_verified ?? false);
    escribir(CLAVES.provider, data.provider ?? "");
    escribir(CLAVES.nombre_negocio, data.nombre_negocio);
    escribir(CLAVES.tasa_cambio, data.tasa_cambio ?? 36);
    escribir(CLAVES.tasa_cambio_configurada, data.tasa_cambio_configurada ?? false);
    escribir(CLAVES.zona_horaria, data.zona_horaria || "America/Managua");
    if (data.color_acento) {
      escribir(CLAVES.color_acento, data.color_acento);
      aplicarColorAcento(data.color_acento);
    }

    setUser({
      token: data.token,
      usuario: data.usuario,
      nombre: data.nombre || data.usuario,
      rol: data.rol || "admin",
      modulos: data.modulos
        ?? ((data.rol || "admin") === "admin"
          ? ["ventas", "rrhh", "contabilidad"]
          : []),
      negocio_id: data.negocio_id ?? 0,
      email: data.email ?? "",
      email_verified: data.email_verified ?? false,
      provider: data.provider ?? "",
      nombre_negocio: data.nombre_negocio,
      tasa_cambio: data.tasa_cambio ?? 36,
      tasa_cambio_configurada: data.tasa_cambio_configurada ?? false,
      zona_horaria: data.zona_horaria || "America/Managua",
      color_acento: data.color_acento ?? "",
    });
  }, []);

  const cerrarSesionLocal = useCallback(() => {
    try {
      sessionStorage.clear();
    } catch {
      /* ignorado */
    }
    setUser(null);
  }, []);

  // Al arrancar se revalida el token contra el servidor. Esto refresca el color
  // de acento y detecta sesiones revocadas (cambio de contraseña o cuenta
  // eliminada) sin esperar a que falle una acción del usuario.
  useEffect(() => {
    const enStorage = usuarioDesdeStorage();
    if (!enStorage) {
      setLoading(false);
      return;
    }

    setUser(enStorage);

    let cancelado = false;

    api
      .get("/auth/perfil")
      .then((d) => {
        if (cancelado) return;
        const actualizado = {
          ...enStorage,
          nombre: d.nombre || enStorage.nombre,
          rol: d.rol || enStorage.rol,
          modulos: Array.isArray(d.modulos) ? d.modulos : enStorage.modulos,
          negocio_id: d.negocio_id ?? enStorage.negocio_id,
          nombre_negocio: d.nombre_negocio ?? enStorage.nombre_negocio,
          email: d.email ?? "",
          email_verified: d.email_verified ?? false,
          provider: d.provider ?? "",
          tasa_cambio: d.tasa_cambio ?? enStorage.tasa_cambio,
          tasa_cambio_configurada: d.tasa_cambio_configurada ?? false,
          zona_horaria: d.zona_horaria || enStorage.zona_horaria,
          color_acento: d.color_acento ?? "",
        };
        escribir(CLAVES.nombre_negocio, actualizado.nombre_negocio);
        escribir(CLAVES.nombre, actualizado.nombre);
        escribir(CLAVES.rol, actualizado.rol);
        escribir(CLAVES.modulos, JSON.stringify(actualizado.modulos ?? []));
        escribir(CLAVES.negocio_id, actualizado.negocio_id);
        escribir(CLAVES.email, actualizado.email);
        escribir(CLAVES.email_verified, actualizado.email_verified);
        escribir(CLAVES.tasa_cambio, actualizado.tasa_cambio);
        escribir(CLAVES.zona_horaria, actualizado.zona_horaria);
        if (esHexValido(d.color_acento)) {
          escribir(CLAVES.color_acento, d.color_acento);
          aplicarColorAcento(d.color_acento);
        }
        setUser(actualizado);
      })
      .catch((e) => {
        if (cancelado) return;
        // Solo se cierra la sesión si el fallo es de autenticación; un problema
        // de red no debe echar al usuario.
        if (/sesión|token|autenticad|credencial/i.test(e.message || "")) {
          cerrarSesionLocal();
        }
      })
      .finally(() => {
        if (!cancelado) setLoading(false);
      });

    return () => {
      cancelado = true;
    };
  }, [cerrarSesionLocal]);

  // La API avisa cuando el backend rechaza el token.
  useEffect(() => {
    window.addEventListener(EVENTO_SESION_EXPIRADA, cerrarSesionLocal);
    return () => window.removeEventListener(EVENTO_SESION_EXPIRADA, cerrarSesionLocal);
  }, [cerrarSesionLocal]);

  const login = useCallback(
    async (usuario, password) => {
      const data = await api.post("/auth/login", { usuario, password });
      guardarSesion(data);
      return data;
    },
    [guardarSesion]
  );

  const googleLogin = useCallback(
    async (credential) => {
      const data = await api.post("/auth/oauth/google", { credential });
      guardarSesion(data);
      return data;
    },
    [guardarSesion]
  );

  const registro = useCallback(
    async (usuario, password, nombre_negocio, tasa_cambio = 36, email = "") => {
      await api.post("/auth/registro", {
        usuario,
        password,
        nombre_negocio,
        tasa_cambio,
        email: email || null,
      });
    },
    []
  );

  const updateNegocio = useCallback((nombre_negocio) => {
    escribir(CLAVES.nombre_negocio, nombre_negocio);
    setUser((u) => (u ? { ...u, nombre_negocio } : u));
  }, []);

  const updateUser = useCallback((data) => {
    const MAPA = { email: CLAVES.email, color_acento: CLAVES.color_acento };
    Object.entries(data).forEach(([k, v]) => escribir(MAPA[k] ?? k, v));
    if (data.color_acento && esHexValido(data.color_acento)) {
      aplicarColorAcento(data.color_acento);
    }
    setUser((u) => (u ? { ...u, ...data } : u));
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      esAdmin: (user?.rol ?? "admin") === "admin",
      modulos: user?.modulos ?? [],
      /** El admin puede todo; una cuenta hija solo sus módulos. */
      puede: (modulo) =>
        (user?.rol ?? "admin") === "admin" || (user?.modulos ?? []).includes(modulo),
      login,
      googleLogin,
      logout: cerrarSesionLocal,
      registro,
      updateNegocio,
      updateUser,
    }),
    [user, loading, login, googleLogin, cerrarSesionLocal, registro, updateNegocio, updateUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
