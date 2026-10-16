import { useEffect, useState } from "react";

/** Devuelve el valor tras un periodo de calma, para no filtrar en cada tecla. */
export function useDebounce(valor, ms = 250) {
  const [diferido, setDiferido] = useState(valor);

  useEffect(() => {
    const id = setTimeout(() => setDiferido(valor), ms);
    return () => clearTimeout(id);
  }, [valor, ms]);

  return diferido;
}
