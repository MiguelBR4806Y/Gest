const state = {
    nivel: "anios",
    anio: null,
    semestre: null,
    trimestre: null,
    mes: null,
    semana: null,
    dia: null,
}

const NIVELES = ["anios", "semestres", "trimestres", "meses", "semanas", "dias"]

function formatearCordobas(numero) {
    return "C$ " + Number(numero).toLocaleString("es-NI", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })
}

function urlDescargar() {
    // Each list level downloads its parent context (the scope the user is exploring)
    const mapa = {
        semestres: "anio",
        trimestres: "semestre",
        meses: "trimestre",
        semanas: "mes",
        dias: "semana"
    }
    const p = new URLSearchParams()
    p.set("nivel", mapa[state.nivel] || state.nivel)
    if (state.anio) p.set("anio", state.anio)
    if (state.semestre) p.set("semestre", state.semestre)
    if (state.trimestre) p.set("trimestre", state.trimestre)
    if (state.mes) p.set("mes", state.mes)
    if (state.semana) p.set("semana", state.semana)
    const usuario = sessionStorage.getItem("usuario") ?? "root"
    p.set("usuario", usuario)
    return "http://127.0.0.1:8000/organizacion/descargar?" + p.toString()
}

function descargarNivel() {
    window.open(urlDescargar(), "_blank")
}

function descargarDia() {
    const usuario = sessionStorage.getItem("usuario") ?? "root"
    window.open("http://127.0.0.1:8000/organizacion/descargar?nivel=dia&fecha=" + state.dia + "&usuario=" + usuario, "_blank")
}

function descargarFactura(id) {
    const usuario = sessionStorage.getItem("usuario") ?? "root"
    window.open("http://127.0.0.1:8000/organizacion/descargar?nivel=factura&factura_id=" + id + "&usuario=" + usuario, "_blank")
}

function renderizarBreadcrumb() {
    const ol = document.getElementById("breadcrumb")
    const items = [{ label: "Inicio", nivel: "anios" }]

    if (state.anio) {
        items.push({ label: state.anio, nivel: "semestres" })
    }
    if (state.semestre) {
        const labels = { 1: "H1", 2: "H2" }
        items.push({ label: labels[state.semestre] || "Semestre", nivel: "trimestres" })
    }
    if (state.trimestre) {
        items.push({ label: "Q" + state.trimestre, nivel: "meses" })
    }
    if (state.mes) {
        const meses = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        items.push({ label: meses[state.mes] || "Mes", nivel: "semanas" })
    }
    if (state.semana) {
        const partes = state.semana.split("-")
        items.push({ label: "Semana " + partes[2] + "/" + partes[1], nivel: "dias" })
    }
    if (state.dia) {
        const fecha = new Date(state.dia + "T12:00:00")
        const dias = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
        const diaSemana = fecha.getDay()
        const diaIdx = diaSemana === 0 ? 6 : diaSemana - 1
        const partes = state.dia.split("-")
        items.push({ label: dias[diaIdx] + " " + partes[2] + "/" + partes[1], nivel: "facturas" })
    }

    ol.innerHTML = items.map((item, i) => {
        const esUltimo = i === items.length - 1
        if (esUltimo) {
            return `<li class="breadcrumb-item active" aria-current="page">${item.label}</li>`
        }
        return `<li class="breadcrumb-item"><a href="#" onclick="navegarA('${item.nivel}'); return false;">${item.label}</a></li>`
    }).join("")
}

function navegarA(nivel) {
    const idx = NIVELES.indexOf(nivel)
    if (idx >= 0) {
        state.nivel = nivel
        if (idx < 1) state.anio = null
        if (idx < 2) state.semestre = null
        if (idx < 3) state.trimestre = null
        if (idx < 4) state.mes = null
        if (idx < 5) state.semana = null
        if (idx < 6) state.dia = null
    }
    document.getElementById("vista-facturas").style.display = "none"
    document.getElementById("contenido").style.display = "block"
    cargarNivel()
}

function mostrarCargando() {
    document.getElementById("contenido").innerHTML = `
        <div class="text-center text-secondary py-5">
            <div class="spinner-border mb-3" role="status"></div>
            <p>Cargando...</p>
        </div>
    `
}

async function cargarNivel() {
    renderizarBreadcrumb()
    mostrarCargando()
    document.getElementById("btnDescargar").style.display = "none"

    try {
        let data
        switch (state.nivel) {
            case "anios":
                data = await apiGet("/organizacion/anios")
                renderizarAnios(data.anios)
                break
            case "semestres":
                data = await apiGet("/organizacion/" + state.anio + "/semestres")
                renderizarSemestres(data.semestres)
                break
            case "trimestres":
                data = await apiGet("/organizacion/" + state.anio + "/" + state.semestre + "/trimestres")
                renderizarTrimestres(data.trimestres)
                break
            case "meses":
                data = await apiGet("/organizacion/" + state.anio + "/" + state.trimestre + "/meses")
                renderizarMeses(data.meses)
                break
            case "semanas":
                data = await apiGet("/organizacion/" + state.anio + "/" + state.mes + "/semanas")
                renderizarSemanas(data.semanas)
                break
            case "dias":
                data = await apiGet("/organizacion/" + state.anio + "/" + state.mes + "/" + state.semana + "/dias")
                renderizarDias(data.dias)
                break
        }
    } catch (e) {
        document.getElementById("contenido").innerHTML = `
            <div class="alert alert-danger text-center">Error al cargar datos</div>
        `
    }
}

function crearCard(label, ventas, ingresos, onclick) {
    return `
        <div class="col-12 col-sm-6 col-lg-4 col-xl-3">
            <div class="card h-100 p-3" style="cursor:pointer;" onclick="${onclick}">
                <div class="card-body text-center d-flex flex-column justify-content-center">
                    <h5 class="card-title mb-3">${label}</h5>
                    <p class="display-6 fw-bold text-success mb-1">${ventas}</p>
                    <small class="text-secondary">factura${ventas !== 1 ? "s" : ""}</small>
                    ${ingresos > 0 ? `<p class="mt-2 mb-0 text-info"><small>${formatearCordobas(ingresos)}</small></p>` : ""}
                </div>
            </div>
        </div>
    `
}

function renderizarCards(items, keyLabel, keyVentas, keyIngresos, onclickTemplate) {
    const cont = document.getElementById("contenido")
    if (!items || items.length === 0) {
        cont.innerHTML = `<div class="alert alert-info text-center">No hay facturas en este período</div>`
        return
    }
    cont.innerHTML = `<div class="row g-4">` + items.map((item, i) => {
        const ventas = item[keyVentas] ?? 0
        const ingresos = item[keyIngresos] ?? 0
        return crearCard(
            item[keyLabel],
            ventas,
            ingresos,
            onclickTemplate(item, i)
        )
    }).join("") + `</div>`
    document.getElementById("btnDescargar").style.display = "inline-block"
}

function renderizarAnios(anios) {
    renderizarCards(anios, "anio", "total_ventas", "total_ingresos",
        (item) => `state.anio=${item.anio}; state.nivel='semestres'; cargarNivel();`)
    document.getElementById("btnDescargar").style.display = "none"
}

function renderizarSemestres(semestres) {
    renderizarCards(semestres, "label", "total_ventas", "total_ingresos",
        (item) => `state.semestre=${item.semestre}; state.nivel='trimestres'; cargarNivel();`)
}

function renderizarTrimestres(trimestres) {
    renderizarCards(trimestres, "label", "total_ventas", "total_ingresos",
        (item) => `state.trimestre=${item.trimestre}; state.nivel='meses'; cargarNivel();`)
}

function renderizarMeses(meses) {
    renderizarCards(meses, "label", "total_ventas", "total_ingresos",
        (item) => `state.mes=${item.mes}; state.nivel='semanas'; cargarNivel();`)
}

function renderizarSemanas(semanas) {
    renderizarCards(semanas, "label", "total_ventas", "total_ingresos",
        (item) => `state.semana='${item.inicio_semana}'; state.nivel='dias'; cargarNivel();`)
}

function renderizarDias(dias) {
    const cont = document.getElementById("contenido")
    if (!dias || dias.every(d => d.total_ventas === 0)) {
        cont.innerHTML = `<div class="alert alert-info text-center">No hay facturas en esta semana</div>`
        return
    }
    cont.innerHTML = `<div class="row g-4">` + dias.map(d => {
        if (d.total_ventas === 0) {
            return `
                <div class="col-12 col-sm-6 col-lg-4 col-xl-3">
                    <div class="card h-100 p-3 opacity-50">
                        <div class="card-body text-center d-flex flex-column justify-content-center">
                            <h5 class="card-title mb-3">${d.label}</h5>
                            <p class="text-secondary mb-0">Sin facturas</p>
                        </div>
                    </div>
                </div>
            `
        }
        return `
            <div class="col-12 col-sm-6 col-lg-4 col-xl-3">
                <div class="card h-100 p-3" style="cursor:pointer;" onclick="verFacturas('${d.fecha}', '${d.label}')">
                    <div class="card-body text-center d-flex flex-column justify-content-center">
                        <h5 class="card-title mb-3">${d.label}</h5>
                        <p class="display-6 fw-bold text-success mb-1">${d.total_ventas}</p>
                        <small class="text-secondary">factura${d.total_ventas !== 1 ? "s" : ""}</small>
                        ${d.total_ingresos > 0 ? `<p class="mt-2 mb-0 text-info"><small>${formatearCordobas(d.total_ingresos)}</small></p>` : ""}
                    </div>
                </div>
            </div>
        `
    }).join("") + `</div>`
    document.getElementById("btnDescargar").style.display = "inline-block"
}

async function verFacturas(fecha, label) {
    state.dia = fecha
    renderizarBreadcrumb()
    document.getElementById("btnDescargar").style.display = "none"
    document.getElementById("contenido").style.display = "none"
    document.getElementById("vista-facturas").style.display = "block"
    document.getElementById("titulo-facturas").textContent = "Facturas del " + label

    const tbody = document.getElementById("tabla-facturas")
    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary">Cargando...</td></tr>'

    try {
        const data = await apiGet("/organizacion/dia/" + fecha)
        const facturas = data.facturas ?? []

        if (facturas.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center text-secondary">Sin facturas en este día</td></tr>'
            return
        }

        tbody.innerHTML = facturas.map((v) => `
            <tr>
                <td>${v.id}</td>
                <td>${v.cliente_nombre}</td>
                <td class="fw-bold text-success">${formatearCordobas(v.total ?? 0)}</td>
                <td>${formatearHora12(v.fecha_hora)}</td>
                <td><span class="badge bg-secondary">${v.metodo_pago ?? "—"}</span></td>
                <td>
                    <div class="d-flex gap-1">
                        <button class="btn btn-sm btn-outline-success" onclick="verFactura(${v.id})">Ver</button>
                        <button class="btn btn-sm btn-outline-info" onclick="descargarFactura(${v.id})">⬇</button>
                    </div>
                </td>
            </tr>
        `).join("")
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger">Error al cargar facturas</td></tr>'
    }
}

function volverALista() {
    state.dia = null
    document.getElementById("vista-facturas").style.display = "none"
    document.getElementById("contenido").style.display = "block"
    document.getElementById("btnDescargar").style.display = "inline-block"
    cargarNivel()
}

function verFactura(id) {
    const usuario = sessionStorage.getItem("usuario") ?? "root"
    window.open("http://127.0.0.1:8000/facturas/" + id + "?usuario=" + usuario, "_blank")
}

cargarNivel()
