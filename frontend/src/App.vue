<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'
import confetti from 'canvas-confetti'
import katex from 'katex' // Importamos katex para la vista de estudio
import TarjetaReactivo from './components/TarjetaReactivo.vue'

// Gráficas Chart.js
import { Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, PointElement, LineElement, RadialLinearScale, Filler } from 'chart.js'
import { Radar, Bar } from 'vue-chartjs'
ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, PointElement, LineElement, RadialLinearScale, Filler)

// --- CONSTANTES Y CONFIGURACIÓN ---
const STORAGE_KEY = 'oci_examen_progreso_v1'
const tiempoTotalAsignado = ref(3600)
const estadisticasGlobales = ref({ promedios_area: {}, alumnos: [] })
const configAdmin = ref({ 
  entrenamiento_preguntas: 30, entrenamiento_minutos: 30,
  concentracion_preguntas: 45, concentracion_minutos: 30,
  maraton_preguntas: 100, maraton_minutos: 120,
  correo_supervisor: '', filtro_referencia: 'con_referencia' 
})
const mostrarToastConfig = ref(false)
const anioActual = new Date().getFullYear()

// --- DATOS DEL ALUMNO ---
const nombreEstudiante = ref('')
const apellidoEstudiante = ref('')
const areaSeleccionada = ref('Genérica')
const modalidadSeleccionada = ref('Entrenamiento') // Entrenamiento, Concentración, Maratón
const fechaFinalizacion = ref('')
const errorNombre = ref(false)

// --- ESTADOS DE LA APP ---
const pantalla = ref('inicio')
const cargando = ref(false)
const sesionEncontrada = ref(false)
const nombreSesionGuardada = ref('')
const rendimientoAlumno = ref(null)
const mostrarModalRendimiento = ref(false)

// --- ESTADO DE PESTAÑAS RENDIMIENTO ---
const tabInternoRendimiento = ref('resumen')
const setTabInterno = (t) => {
  tabInternoRendimiento.value = t
}

// --- ADMIN Y REVISIÓN ---
const listaResultados = ref([])
const preguntasReportadas = ref([])
const preguntaEditando = ref(null)
const vistaAdmin = ref('resultados') // 'resultados' o 'reportadas'
const cargandoAdmin = ref(false)
const loginCorreo = ref('')
const loginPassword = ref('')
const errorLogin = ref('')
const cargandoLogin = ref(false)
const usuarioAdmin = ref(null)

// --- TEMPORIZADOR ---
const tiempoRestante = ref(3600)
let timerInterval = null

// Datos del examen
const examen = ref([])
const indiceActual = ref(0)
const reactivoActual = computed(() => examen.value[indiceActual.value])

// Estado de respuesta
const respuestaSeleccionada = ref(null)
const mostrarRetroalimentacion = ref(false)
const puntajes = ref({})

// --- CÁLCULOS ---
const totalAciertos = computed(() => {
  let suma = 0
  for (const area in puntajes.value) { suma += puntajes.value[area].correctas }
  return suma
})

const porcentajeGlobal = computed(() => {
  if (examen.value.length === 0) return 0
  const totalReportadas = preguntasReportadasEnSesion.value.length || 0
  const den = Math.max(1, examen.value.length - totalReportadas)
  return Math.round((totalAciertos.value / den) * 100)
})

const tiempoFormateado = computed(() => {
  const minutos = Math.floor(tiempoRestante.value / 60)
  const segundos = tiempoRestante.value % 60
  return `${minutos < 10 ? '0' + minutos : minutos}:${segundos < 10 ? '0' + segundos : segundos}`
})

const porcentajeAvance = computed(() => {
  if (!examen.value || examen.value.length === 0) return 0
  const totalReportadas = preguntasReportadasEnSesion.value.length || 0
  const den = Math.max(1, examen.value.length - totalReportadas)
  const respuestasEfectivas = Math.max(0, indiceRespondidos.value.length - totalReportadas)
  return Math.round((respuestasEfectivas / den) * 100)
})

// Función para renderizar LaTeX en la vista de revisión
const renderizarTexto = (texto) => {
  if (!texto) return ''
  
  // Limpieza preventiva para comandos matemáticos huérfanos por colisión del símbolo $ (ej. $10 pesos)
  let textoLimpio = texto
    .replace(/\\times/g, '×')
    .replace(/\\approx/g, '≈')
    .replace(/\\pi/g, 'π')
    .replace(/\\frac\{([^}]+)\}\{([^}]+)\}/g, '$1/$2');

  return textoLimpio.replace(/\$(.*?)\$/g, (match, formula) => {
    try {
      return katex.renderToString(formula, { throwOnError: false, displayMode: false })
    } catch (e) { return match }
  })
}

const resultadoNivel = computed(() => {
  const p = porcentajeGlobal.value
  if (p < 80) return { mensaje: "¡Puedes mejorar!", iconoClass: "fa-solid fa-person-running", subtitulo: "¡No te rindas, el aprendizaje es un viaje!", claseColor: "bg-blue-50 border-blue-200 text-blue-700", iconColor: "text-blue-500", esMedalla: false }
  else if (p < 90) return { mensaje: "¡Buen esfuerzo!", iconoClass: "fa-solid fa-medal", subtitulo: "El éxito es la suma de pequeños esfuerzos.", claseColor: "bg-orange-50 border-orange-300 text-orange-800", iconColor: "text-orange-500", esMedalla: true, tipoMedalla: "bronce" }
  else if (p <= 95) return { mensaje: "¡Muy buen trabajo!", iconoClass: "fa-solid fa-medal", subtitulo: "La perseverancia es la clave del éxito. ¡Sigue así!", claseColor: "bg-slate-100 border-slate-300 text-slate-700", iconColor: "text-slate-400", esMedalla: true, tipoMedalla: "plata" }
  else return { mensaje: "¡Excelente desempeño!", iconoClass: "fa-solid fa-medal", subtitulo: "¡Eres un campeón! Tu dedicación rinde frutos increíbles.", claseColor: "bg-yellow-100 border-yellow-400 text-yellow-800", iconColor: "text-yellow-500", esMedalla: true, tipoMedalla: "oro" }
})

const iniciarReloj = () => {
  if (timerInterval) clearInterval(timerInterval)
  timerInterval = setInterval(() => {
    if (tiempoRestante.value > 0) { tiempoRestante.value--; guardarEstado(); }
    else { clearInterval(timerInterval); alert("⏰ ¡Se acabó el tiempo!"); finalizarExamen(); }
  }, 1000)
}
const detenerReloj = () => { if (timerInterval) clearInterval(timerInterval) }
const getIniciales = () => {
  const n = nombreEstudiante.value ? nombreEstudiante.value.charAt(0).toUpperCase() : '';
  const a = apellidoEstudiante.value ? apellidoEstudiante.value.charAt(0).toUpperCase() : '';
  return n + a || '??';
}

// --- TEMA E INTERFAZ ---
const temaDark = ref(false)
const menuAdminAbierto = ref(false)


const toggleTema = () => {
  temaDark.value = !temaDark.value
  localStorage.setItem('oci_tema_dark', temaDark.value)
  if (temaDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

onMounted(async () => {
  // Inicializar Tema
  const savedTheme = localStorage.getItem('oci_tema_dark')
  if (savedTheme === 'true' || (savedTheme === null && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    temaDark.value = true
    document.documentElement.classList.add('dark')
  }
  // Cargar configuración global (dentro de onMounted)
  try {
    const resConf = await axios.get('/api/configuracion')
    configAdmin.value = resConf.data
    tiempoTotalAsignado.value = Math.max((configAdmin.value.entrenamiento_minutos || 30) * 60, 60)
    tiempoRestante.value = tiempoTotalAsignado.value
  } catch (e) { console.error("Error cargando configuración", e) }

  const guardado = localStorage.getItem(STORAGE_KEY)
  if (guardado) {
    try {
      const datos = JSON.parse(guardado)
      if (datos.examen && datos.examen.length > 0 && datos.pantalla === 'jugando') {
        sesionEncontrada.value = true; nombreSesionGuardada.value = `${datos.nombre} ${datos.apellido}`;
      }
    } catch (e) { localStorage.removeItem(STORAGE_KEY) }
  }
})

const guardarEstado = () => {
  if (pantalla.value !== 'jugando') return
  const estado = {
    nombre: nombreEstudiante.value,
    apellido: apellidoEstudiante.value,
    area: areaSeleccionada.value,
    modalidad: modalidadSeleccionada.value,
    examen: examen.value,
    indice: indiceActual.value,
    puntajes: puntajes.value,
    pantalla: pantalla.value,
    tiempoTotal: tiempoTotalAsignado.value,
    tiempoRestante: Math.max(0, tiempoRestante.value),
    indiceRespondidos: indiceRespondidos.value,
    preguntasGuardadas: preguntasGuardadas.value,
    vecesTiempoSolicitado: vecesTiempoSolicitado.value
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(estado))
}

const recuperarSesion = () => {
  const guardado = localStorage.getItem(STORAGE_KEY); if (!guardado) return;
  const datos = JSON.parse(guardado)
  nombreEstudiante.value = datos.nombre; 
  apellidoEstudiante.value = datos.apellido; 
  areaSeleccionada.value = datos.area || 'Genérica'; 
  modalidadSeleccionada.value = datos.modalidad || 'Entrenamiento';
  examen.value = datos.examen; 
  indiceActual.value = datos.indice; 
  puntajes.value = datos.puntajes; 
  tiempoTotalAsignado.value = datos.tiempoTotal || 3600;
  tiempoRestante.value = datos.tiempoRestante || tiempoTotalAsignado.value; 
  pantalla.value = 'jugando';
  indiceRespondidos.value = datos.indiceRespondidos || [];
  preguntasGuardadas.value = datos.preguntasGuardadas || [];
  vecesTiempoSolicitado.value = datos.vecesTiempoSolicitado || 0;
  sesionEncontrada.value = false; iniciarReloj();
}

const descartarSesion = () => { localStorage.removeItem(STORAGE_KEY); sesionEncontrada.value = false; }

const abrirAdmin = async () => {
  pantalla.value = 'login_admin';
  errorLogin.value = '';
  loginCorreo.value = '';
  loginPassword.value = '';
}

// --- COMPUTED PROPERTIES PARA GRÁFICAS ---
const chartDataRadarGlobal = computed(() => {
  const labels = Object.keys(estadisticasGlobales.value.promedios_area || {});
  const data = Object.values(estadisticasGlobales.value.promedios_area || {});
  return {
    labels: labels.length ? labels : ['Sin datos'],
    datasets: [{
      label: 'Promedio Global %',
      data: data.length ? data : [0],
      backgroundColor: 'rgba(99, 102, 241, 0.2)',
      borderColor: 'rgba(99, 102, 241, 1)',
      pointBackgroundColor: 'rgba(99, 102, 241, 1)',
      pointBorderColor: '#fff',
      pointHoverBackgroundColor: '#fff',
      pointHoverBorderColor: 'rgba(99, 102, 241, 1)'
    }]
  }
})

const chartOptionsRadar = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    r: {
      min: 0,
      max: 100,
      ticks: {
        stepSize: 20,
        backdropColor: 'transparent',
        color: temaDark.value ? '#94a3b8' : '#64748b'
      },
      grid: {
        color: temaDark.value ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
      },
      angleLines: {
        color: temaDark.value ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
      },
      pointLabels: {
        color: temaDark.value ? '#ffffff' : '#475569',
        font: {
          size: 11,
          weight: 'bold'
        }
      }
    }
  },
  plugins: {
    legend: {
      display: false
    }
  }
}))

const chartDataBarrasGlobal = computed(() => {
  const alumnos = estadisticasGlobales.value.alumnos || [];
  return {
    labels: alumnos.length ? alumnos.map(a => a.nombre) : ['Sin datos'],
    datasets: [
      {
        label: 'Promedio Global %',
        data: alumnos.length ? alumnos.map(a => a.promedio) : [0],
        backgroundColor: 'rgba(99, 102, 241, 0.7)',
        yAxisID: 'y'
      },
      {
        label: 'Exámenes Realizados',
        data: alumnos.length ? alumnos.map(a => a.total_tests) : [0],
        backgroundColor: 'rgba(234, 179, 8, 0.7)', // amber-500
        yAxisID: 'y1'
      }
    ]
  }
})

const chartOptionsBarras = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    y: { type: 'linear', display: true, position: 'left', min: 0, max: 100 },
    y1: { type: 'linear', display: true, position: 'right', grid: { drawOnChartArea: false }, min: 0 }
  }
}

const chartDataRadarAlumno = computed(() => {
  if (!rendimientoAlumno.value || !rendimientoAlumno.value.mejores_por_area) {
    return { labels: ['Sin datos'], datasets: [{ data: [0] }] }
  }
  const labels = Object.keys(rendimientoAlumno.value.mejores_por_area);
  const data = Object.values(rendimientoAlumno.value.mejores_por_area);
  return {
    labels: labels.length ? labels : ['Sin datos'],
    datasets: [{
      label: 'Promedio del Alumno %',
      data: data.length ? data : [0],
      backgroundColor: 'rgba(34, 197, 94, 0.2)', // green-500
      borderColor: 'rgba(34, 197, 94, 1)',
      pointBackgroundColor: 'rgba(34, 197, 94, 1)',
      pointBorderColor: '#fff'
    }]
  }
})

const iniciarSesionAdmin = async () => {
  if (!loginCorreo.value || !loginPassword.value) {
    errorLogin.value = 'Ingresa tus credenciales.'; return;
  }
  cargandoLogin.value = true;
  errorLogin.value = '';
  try {
    const res = await axios.post('/api/login', { correo: loginCorreo.value, password: loginPassword.value });
    usuarioAdmin.value = res.data.usuario;
    // Pasa a vista admin
    pantalla.value = 'admin'; cargandoAdmin.value = true;
    try {
      const resResultados = await axios.get('/api/resultados');
      listaResultados.value = resResultados.data;
      
      const resStats = await axios.get('/api/estadisticas-globales');
      estadisticasGlobales.value = resStats.data;
      
      await cargarPreguntasReportadas()
    } catch (e) { alert("Error al cargar datos"); } finally { cargandoAdmin.value = false; }
  } catch (e) {
    if (e.response && e.response.status === 401) {
      errorLogin.value = 'Credenciales inválidas, intenta de nuevo.';
    } else {
      errorLogin.value = 'No se pudo conectar al servidor. Intenta de nuevo.';
      console.error(e);
    }
  } finally {
    cargandoLogin.value = false;
  }
}

// Dev Bypass para pruebas de QA automáticas (Subagente Browser)
const bypassAdmin = async () => {
  pantalla.value = 'admin'; cargandoAdmin.value = true;
  try {
    const res = await axios.get('/api/resultados');
    listaResultados.value = res.data;
    const resStats = await axios.get('/api/estadisticas-globales');
    estadisticasGlobales.value = resStats.data;
    await cargarPreguntasReportadas()
  } catch (e) { console.error("Error bypassing admin", e); } finally { cargandoAdmin.value = false; }
}

const idsCorrectosSesion = ref([]) // <--- AGREGAR ESTO EN EL SETUP
const indiceRespondidos = ref([])
const preguntasGuardadas = ref([])
const preguntasReportadasEnSesion = ref([]) // ID de las preguntas que reportó el alumno
const vecesTiempoSolicitado = ref(0)
const mostrarPanelPendientes = ref(false)

const listaReferencias = ref([])
const mostrarPdfAdmin = ref(false)

const cargarPreguntasReportadas = async () => {
  try {
    const res = await axios.get('/api/admin/preguntas-reportadas')
    preguntasReportadas.value = res.data

    // Cargar PDFs disponibles localmente
    const resRef = await axios.get('/api/referencias')
    listaReferencias.value = resRef.data || []
  } catch (e) {
    console.error("No se pudieron cargar las preguntas reportadas", e)
  }
}

const editarPregunta = (pregunta) => {
  // Copiamos la pregunta para no mutar el array original hasta guardar
  preguntaEditando.value = JSON.parse(JSON.stringify(pregunta))
}

const guardarPregunta = async () => {
  if (!preguntaEditando.value) return;

  try {
    cargandoAdmin.value = true
    preguntaEditando.value.revisado_por = usuarioAdmin.value?.correo || 'admin'
    const res = await axios.put(`/api/admin/reactivo/${preguntaEditando.value.id}`, preguntaEditando.value)
    alert("¡Pregunta guardada y marcada como revisada exitosamente!")
    preguntaEditando.value = null
    await cargarPreguntasReportadas() // Recargar lista
  } catch (e) {
    alert("Error al guardar la pregunta.")
    console.error(e)
  } finally {
    cargandoAdmin.value = false
  }
}

const cancelarEdicion = () => {
  preguntaEditando.value = null
}

const subirImagenReactivo = async (event) => {
  const file = event.target.files[0];
  if (!file || !preguntaEditando.value) return;

  const formData = new FormData();
  formData.append('imagen', file);

  try {
    cargandoAdmin.value = true;
    const res = await axios.post(`/api/admin/reactivo/imagen/${preguntaEditando.value.id}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    preguntaEditando.value.imagen_url = res.data.imagen_url;
    alert("¡Imagen subida correctamente!");
  } catch (e) {
    alert("Error al subir la imagen.");
    console.error(e);
  } finally {
    cargandoAdmin.value = false;
    // Resetear el input file para permitir subir otra imagen si se desea
    if (event.target) event.target.value = '';
  }
}

const comenzarExamen = async () => {
  if (!nombreEstudiante.value.trim() || !apellidoEstudiante.value.trim()) {
    errorNombre.value = true; return;
  }
  errorNombre.value = false; descartarSesion(); cargando.value = true;
  
  // Establecemos el tiempo en función de la modalidad elegida
  if (modalidadSeleccionada.value === 'Entrenamiento') {
    tiempoTotalAsignado.value = (configAdmin.value.entrenamiento_minutos || 30) * 60
  } else if (modalidadSeleccionada.value === 'Concentración') {
    tiempoTotalAsignado.value = (configAdmin.value.concentracion_minutos || 30) * 60
  } else if (modalidadSeleccionada.value === 'Maratón') {
    tiempoTotalAsignado.value = (configAdmin.value.maraton_minutos || 120) * 60
  }
  tiempoRestante.value = tiempoTotalAsignado.value

  try {
    const res = await axios.get('/api/generar-examen', {
      params: { 
        nombre: nombreEstudiante.value, 
        apellido: apellidoEstudiante.value, 
        area: areaSeleccionada.value,
        tipo_test: modalidadSeleccionada.value
      }
    })
    
    if (res.data.error) throw new Error(res.data.error)
    examen.value = res.data;
    indiceActual.value = 0;
    puntajes.value = {};
    indiceRespondidos.value = [];
    preguntasGuardadas.value = [];
    preguntasReportadasEnSesion.value = [];
    vecesTiempoSolicitado.value = 0;
    pantalla.value = 'jugando';
    iniciarReloj();
    guardarEstado();
  } catch (error) {
    console.error("Error generando examen", error)
    alert("Hubo un error al generar el examen. Revisa la consola o intenta de nuevo.")
  } finally {
    cargando.value = false;
  }
}

const solicitarMasTiempo = () => {
  tiempoRestante.value += 300; // 5 minutos extras
  vecesTiempoSolicitado.value++;
  guardarEstado();
}

const registrarPreguntaReportada = async (preguntaId) => {
  if (!preguntasReportadasEnSesion.value.includes(preguntaId)) {
    preguntasReportadasEnSesion.value.push(preguntaId);
  }
  
  if (!indiceRespondidos.value.includes(indiceActual.value)) {
    indiceRespondidos.value.push(indiceActual.value);
  }
  preguntasGuardadas.value = preguntasGuardadas.value.filter(i => i !== indiceActual.value);
  
  try {
    const idsActuales = examen.value.map(p => p.id);
    const res = await axios.post('/api/pregunta-reemplazo', {
      area: reactivoActual.value.area,
      excluir_ids: idsActuales
    });
    if (res.data && res.data.id) {
      examen.value.push(res.data);
    }
  } catch (e) {
    console.error("No se pudo obtener una pregunta de reemplazo:", e);
  }

  mostrarRetroalimentacion.value = false;
  respuestaSeleccionada.value = null;
  
  avanzarSiguiente();
}

const guardarParaDespues = () => {
  if (!preguntasGuardadas.value.includes(indiceActual.value)) {
    preguntasGuardadas.value.push(indiceActual.value);
  }
  avanzarSiguiente();
}

const irAPreguntaGuardada = (idx) => {
  mostrarPanelPendientes.value = false;
  indiceActual.value = idx;
  guardarEstado();
}

const procesarRespuesta = (opcion) => {
  if (mostrarRetroalimentacion.value) return
  respuestaSeleccionada.value = opcion; mostrarRetroalimentacion.value = true;

  if (!indiceRespondidos.value.includes(indiceActual.value)) {
    indiceRespondidos.value.push(indiceActual.value);
  }
  preguntasGuardadas.value = preguntasGuardadas.value.filter(i => i !== indiceActual.value);

  const area = reactivoActual.value.area
  if (!puntajes.value[area]) puntajes.value[area] = { correctas: 0, incorrectas: 0, total: 0 }
  puntajes.value[area].total++;

  if (opcion.es_correcta) {
    puntajes.value[area].correctas++
    idsCorrectosSesion.value.push(reactivoActual.value.id)
  } else {
    puntajes.value[area].incorrectas++
  }

  // Si esta pregunta FUE reportada, no la contamos de todas formas (le "perdonamos" el punto restando del total posible más adelante)
  guardarEstado();
}

const avanzarSiguiente = () => {
  mostrarRetroalimentacion.value = false; respuestaSeleccionada.value = null;

  const remaining = examen.value.map((_, i) => i).filter(i => !indiceRespondidos.value.includes(i));
  if (remaining.length === 0) {
    finalizarExamen();
    return;
  }

  let tryIndex = indiceActual.value + 1;
  while (tryIndex < examen.value.length && indiceRespondidos.value.includes(tryIndex)) {
    tryIndex++;
  }

  if (tryIndex < examen.value.length) {
    indiceActual.value = tryIndex;
  } else {
    indiceActual.value = remaining[0];
  }
  guardarEstado();
}

const finalizarExamen = async () => {
  detenerReloj();
  const tiempoConsumidoTotal = tiempoTotalAsignado.value + (vecesTiempoSolicitado.value * 300) - Math.max(0, tiempoRestante.value);
  const ahora = new Date()
  fechaFinalizacion.value = ahora.toLocaleString('es-MX', { dateStyle: 'long', timeStyle: 'short' })

  // -- Lógica de Calificación Ajustada por Reportes --
  // Recalcularemos el porcentajeGlobal.value ignorando las preguntas reportadas del denominador
  let totalCorrectasReales = 0;
  let totalPreguntasExamen = examen.value.length;
  let totalReportadas = preguntasReportadasEnSesion.value.length;
  let nuevoDenominador = Math.max(1, totalPreguntasExamen - totalReportadas); // Evitar división por cero

  for (const area in puntajes.value) {
    totalCorrectasReales += puntajes.value[area].correctas;
  }

  // Ajustar puntaje global
  const porcentajeAjustado = Math.round((totalCorrectasReales / nuevoDenominador) * 100);
  porcentajeGlobal.value = porcentajeAjustado > 100 ? 100 : porcentajeAjustado;

  try {
    await axios.post('/api/guardar-resultado', {
      nombre: nombreEstudiante.value,
      apellido: apellidoEstudiante.value,
      area: areaSeleccionada.value,
      modalidad_test: modalidadSeleccionada.value,
      calificacion: porcentajeGlobal.value,
      puntajes: puntajes.value,
      ids_correctos: idsCorrectosSesion.value,
      veces_tiempo_extra: vecesTiempoSolicitado.value,
      tiempo_total_empleado: tiempoConsumidoTotal
    })
  } catch (e) { console.error(e) }
  pantalla.value = 'resultados'; localStorage.removeItem(STORAGE_KEY);
  if (porcentajeGlobal.value > 90) { setTimeout(() => { confetti({ particleCount: 800, spread: 100, startVelocity: 60 }) }, 500) }
}

const abrirRendimientoAlumno = async (estudiante = null) => {
  tabInternoRendimiento.value = 'resumen';
  const target = (typeof estudiante === 'string') ? estudiante : `${nombreEstudiante.value} ${apellidoEstudiante.value}`;
  if (!target.trim()) return;

  try {
    cargando.value = true;
    const res = await axios.get(`/api/admin/rendimiento/${target}`);
    rendimientoAlumno.value = res.data;
    mostrarModalRendimiento.value = true;
  } catch (e) {
    alert("No se pudo cargar el rendimiento histórico de este alumno.");
    console.error(e);
  } finally {
    cargando.value = false;
  }
}

const imprimirGuia = () => {
  // Damos 250ms para que el navegador recalcule el diseño sin scroll antes de abrir el diálogo
  setTimeout(() => {
    window.print();
  }, 250);
};

const guardarConfigAdmin = async () => {
  try {
    const res = await axios.post('/api/configuracion', configAdmin.value)
    // alert("¡Configuración guardada! Aplicará para los siguientes exámenes.")
    tiempoTotalAsignado.value = Math.max((configAdmin.value.tiempo_minutos || 60) * 60, 60)

    // Mostrar Toast
    mostrarToastConfig.value = true;
    setTimeout(() => {
      mostrarToastConfig.value = false;
    }, 3000);
  } catch (e) {
    alert("Hubo un error al guardar la configuración.")
  }
}
</script>

<template>
  <div :class="[
    'min-h-screen flex flex-col items-center transition-colors duration-300 font-sans',
    pantalla === 'jugando' || pantalla === 'admin' ? 'bg-white dark:bg-slate-900' : 'bg-blue-50 dark:bg-slate-900 p-3 md:p-4 justify-between'
  ]">

    <div class="flex-1 w-full flex flex-col items-center justify-center max-w-4xl">

      <div v-if="pantalla === 'inicio'"
        class="text-center w-full max-w-lg bg-white dark:bg-slate-800 p-6 md:p-8 rounded-[2rem] shadow-2xl border-b-[6px] border-indigo-500 animate-fade-in relative transition-colors duration-300">
        
        <!-- Toggle Dark Mode Superior -->
        <button @click="toggleTema" class="absolute top-4 right-4 w-10 h-10 rounded-full text-slate-400 hover:text-indigo-500 hover:bg-slate-100 dark:hover:bg-slate-700 transition flex items-center justify-center">
          <i class="fa-solid text-xl" :class="temaDark ? 'fa-sun text-amber-400' : 'fa-moon'"></i>
        </button>

        <div v-if="sesionEncontrada"
          class="absolute top-0 left-0 w-full bg-amber-100 dark:bg-amber-900/30 border-b border-amber-300 dark:border-amber-700/50 p-4 text-left z-20 transition-colors">
          <p class="text-amber-900 dark:text-amber-200 font-bold text-sm">Examen incompleto: {{ nombreSesionGuardada }}</p>
          <div class="flex gap-2 mt-1">
            <button @click="recuperarSesion" class="bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold py-1 px-3 rounded shadow-sm transition">🔄
              Continuar</button>
            <button @click="descartarSesion"
              class="bg-white dark:bg-slate-700 text-gray-500 dark:text-gray-300 border dark:border-slate-600 text-xs font-bold py-1 px-3 rounded hover:bg-gray-50 dark:hover:bg-slate-600 transition">🗑️ Borrar</button>
          </div>
        </div>
        
        <h1 class="text-xl md:text-3xl font-extrabold text-indigo-800 dark:text-indigo-400 mb-1 mt-4 md:mt-6 leading-tight transition-colors"><i
            class="fa-solid fa-medal text-yellow-500 mr-2"></i>Olimpiadas de Conocimiento</h1>
        <p class="text-gray-500 dark:text-gray-400 mb-4 md:mb-6 font-bold text-sm md:text-base transition-colors">Simulador de Examen</p>
        <div class="space-y-2.5 mb-5 text-left">
          <input v-model="nombreEstudiante" type="text" placeholder="Nombre(s)"
            class="w-full px-4 py-3 md:p-3.5 rounded-xl border-2 border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900/50 text-slate-800 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-indigo-500 focus:ring-0 outline-none transition-colors text-sm">
          <input v-model="apellidoEstudiante" type="text" placeholder="Apellidos"
             class="w-full px-4 py-3 md:p-3.5 rounded-xl border-2 border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900/50 text-slate-800 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:border-indigo-500 focus:ring-0 outline-none transition-colors text-sm">
          
        </div>

        <div v-if="errorNombre"
          class="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-3 rounded-xl text-xs font-bold animate-shake mb-6 flex items-center gap-2 border border-red-200 dark:border-red-800/30 transition-colors">
          <i class="fa-solid fa-triangle-exclamation"></i> Por favor ingresa tu nombre y apellido
        </div>

        <div v-if="!errorNombre" class="animate-fade-in">
          <!-- Área de Interés -->
          <div class="mb-4 md:mb-5 text-left">
            <label class="block text-gray-700 dark:text-gray-300 font-bold mb-1.5 text-sm transition-colors">Área a Evaluar</label>
            <div class="relative">
              <select v-model="areaSeleccionada" class="w-full px-4 py-2.5 md:py-3 bg-gray-50 dark:bg-slate-900/50 border border-gray-300 dark:border-slate-600 text-slate-800 dark:text-white rounded-xl focus:ring-2 focus:ring-indigo-200 dark:focus:ring-indigo-900/50 focus:border-indigo-500 transition-all appearance-none cursor-pointer text-sm font-semibold selection:bg-indigo-100">
                <option value="Genérica">Genérica (Todas las áreas)</option>
                <option value="Lenguajes">Lenguajes</option>
                <option value="Saberes y Pensamiento Científico">Saberes y Pensamiento Científico</option>
                <option value="Ética, Naturaleza y Sociedad">Ética, Naturaleza y Sociedad</option>
                <option value="De lo Humano y lo Comunitario">De lo Humano y lo Comunitario</option>
              </select>
              <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-gray-500 dark:text-gray-400">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
              </div>
            </div>
          </div>

          <!-- Tipo de Test -->
          <div class="mb-5 md:mb-6 text-left">
            <label class="block text-gray-700 dark:text-gray-300 font-bold mb-1.5 text-sm transition-colors">Modalidad de Prueba</label>
            <div class="grid grid-cols-1 gap-2">
              <label class="relative flex items-center justify-between p-2.5 md:p-3.5 cursor-pointer rounded-xl border-2 transition-all dark:bg-slate-900/50" 
                     :class="modalidadSeleccionada === 'Entrenamiento' ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/30 dark:border-indigo-400' : 'border-gray-100 dark:border-slate-700 bg-gray-50 hover:border-indigo-300 dark:hover:border-slate-600'">
                <div class="flex items-center gap-3">
                  <input type="radio" name="modalidad" value="Entrenamiento" v-model="modalidadSeleccionada" class="w-4 h-4 text-indigo-600 bg-gray-100 border-gray-300 focus:ring-indigo-500 dark:focus:ring-indigo-600 dark:ring-offset-gray-800 dark:bg-gray-700 dark:border-gray-600">
                  <span class="font-bold text-gray-800 dark:text-white text-sm transition-colors">Entrenamiento</span>
                </div>
                <div class="text-right flex flex-col items-end">
                  <span class="text-[11px] font-bold text-gray-500 dark:text-gray-400 transition-colors px-2 py-0.5 bg-white dark:bg-slate-700 rounded-md border dark:border-slate-600">{{ configAdmin.entrenamiento_preguntas || 30 }} p</span>
                  <span class="text-[10px] text-indigo-600 dark:text-indigo-400 font-bold mt-0.5 transition-colors">{{ configAdmin.entrenamiento_minutos || 30 }} min</span>
                </div>
              </label>

              <label class="relative flex items-center justify-between p-2.5 md:p-3.5 cursor-pointer rounded-xl border-2 transition-all dark:bg-slate-900/50" 
                     :class="modalidadSeleccionada === 'Concentración' ? 'border-amber-500 bg-amber-50 dark:bg-amber-900/30 dark:border-amber-400' : 'border-gray-100 dark:border-slate-700 bg-gray-50 hover:border-amber-300 dark:hover:border-slate-600'">
                <div class="flex items-center gap-3">
                  <input type="radio" name="modalidad" value="Concentración" v-model="modalidadSeleccionada" class="w-4 h-4 text-amber-600 bg-gray-100 border-gray-300 focus:ring-amber-500 dark:focus:ring-amber-600 dark:ring-offset-gray-800 dark:bg-gray-700 dark:border-gray-600">
                  <span class="font-bold text-gray-800 dark:text-white text-sm transition-colors">Concentración</span>
                </div>
                <div class="text-right flex flex-col items-end">
                  <span class="text-[11px] font-bold text-gray-500 dark:text-gray-400 transition-colors px-2 py-0.5 bg-white dark:bg-slate-700 rounded-md border dark:border-slate-600">{{ configAdmin.concentracion_preguntas || 45 }} p</span>
                  <span class="text-[10px] text-amber-600 dark:text-amber-400 font-bold mt-0.5 transition-colors">{{ configAdmin.concentracion_minutos || 30 }} min</span>
                </div>
              </label>
              
              <label class="relative flex items-center justify-between p-2.5 md:p-3.5 cursor-pointer rounded-xl border-2 transition-all dark:bg-slate-900/50" 
                     :class="modalidadSeleccionada === 'Maratón' ? 'border-rose-500 bg-rose-50 dark:bg-rose-900/30 dark:border-rose-400' : 'border-gray-100 dark:border-slate-700 bg-gray-50 hover:border-rose-300 dark:hover:border-slate-600'">
                <div class="flex items-center gap-3">
                  <input type="radio" name="modalidad" value="Maratón" v-model="modalidadSeleccionada" class="w-4 h-4 text-rose-600 bg-gray-100 border-gray-300 focus:ring-rose-500 dark:focus:ring-rose-600 dark:ring-offset-gray-800 dark:bg-gray-700 dark:border-gray-600">
                  <span class="font-bold text-gray-800 dark:text-white text-sm transition-colors">Maratón</span>
                </div>
                <div class="text-right flex flex-col items-end">
                  <span class="text-[11px] font-bold text-gray-500 dark:text-gray-400 transition-colors px-2 py-0.5 bg-white dark:bg-slate-700 rounded-md border dark:border-slate-600">{{ configAdmin.maraton_preguntas || 100 }} p</span>
                  <span class="text-[10px] text-rose-600 dark:text-rose-400 font-bold mt-0.5 transition-colors">{{ configAdmin.maraton_minutos || 120 }} min</span>
                </div>
              </label>
            </div>
          </div>

          <button @click="comenzarExamen" :disabled="cargando"
            class="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold py-3 md:py-4 px-8 rounded-xl shadow-lg hover:shadow-xl transition-all transform hover:-translate-y-1 flex justify-center items-center text-lg disabled:opacity-70 disabled:cursor-not-allowed">
            Comenzar
          </button>
        </div>
      </div>

      <div v-else-if="pantalla === 'jugando'" class="w-full flex-grow flex flex-col bg-gray-50 dark:bg-slate-900 transition-colors duration-300">
        <header class="bg-white dark:bg-slate-800 shadow-sm sticky top-0 z-40 px-2 py-2 md:px-4 md:py-2.5 flex justify-between items-center border-b border-gray-100 dark:border-slate-700 transition-colors">
          <div class="flex items-center gap-2">
            <div class="w-8 h-8 md:w-9 md:h-9 bg-indigo-100 dark:bg-indigo-900 rounded-full flex items-center justify-center text-indigo-600 dark:text-indigo-300 font-bold shadow-inner flex-shrink-0 text-sm">
              {{ getIniciales() }}
            </div>
            <div class="hidden sm:block">
              <p class="text-[10px] md:text-xs text-gray-500 dark:text-gray-400 font-medium">Alumno</p>
              <p class="text-sm md:text-base font-bold text-gray-800 dark:text-gray-100 leading-tight truncate max-w-[120px] md:max-w-xs">{{ nombreEstudiante }} {{ apellidoEstudiante }}</p>
            </div>
          </div>
          
          <div class="flex items-center gap-2 md:gap-3">
            <button @click="solicitarMasTiempo" 
              class="flex items-center gap-1 md:gap-1.5 px-2 py-1 md:px-2.5 md:py-1.5 text-xs md:text-sm font-medium text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 hover:bg-amber-100 dark:hover:bg-amber-800/50 rounded-lg transition-colors border border-amber-200 dark:border-amber-700/50">
              <svg class="w-3.5 h-3.5 md:w-4 md:h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              <span class="hidden md:inline">+5 Min</span>
              <span class="md:hidden">+5m</span>
              <span v-if="vecesTiempoSolicitado > 0" class="ml-1 md:ml-0.5 bg-amber-200 dark:bg-amber-700 text-amber-800 dark:text-amber-100 py-0.5 px-1.5 rounded-full text-[9px] md:text-[10px] leading-none">{{vecesTiempoSolicitado}}</span>
            </button>

            <!-- Toggle Dark Mode Minimalista (Jugando) -->
            <button @click="toggleTema" class="w-8 h-8 md:w-9 md:h-9 rounded-full text-slate-400 hover:text-indigo-500 hover:bg-slate-100 dark:hover:bg-slate-700 transition flex items-center justify-center">
              <i class="fa-solid text-sm md:text-base" :class="temaDark ? 'fa-sun text-amber-400' : 'fa-moon'"></i>
            </button>

            <div class="flex items-center gap-1.5 bg-gray-50 dark:bg-slate-700 px-2 py-1 md:px-3 md:py-1.5 rounded-lg border border-gray-200 dark:border-slate-600 shadow-inner transition-colors" :class="{'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/30 border-red-200 dark:border-red-800/50 animate-pulse': tiempoRestante < 300, 'text-gray-800 dark:text-gray-100': tiempoRestante >= 300}">
              <svg class="w-3.5 h-3.5 md:w-4 md:h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              <span class="font-mono font-bold text-sm md:text-base tracking-wider">{{ tiempoFormateado }}</span>
            </div>
          </div>
        </header>

        <!-- Barra de Progreso Sticky -->
        <div class="sticky top-[57px] md:top-[65px] z-30 w-full bg-white dark:bg-slate-800 border-b border-gray-100 dark:border-slate-700 px-4 py-2 transition-colors">
          <div class="max-w-4xl mx-auto flex items-center gap-2 md:gap-3">
            <div class="flex-grow bg-gray-100 dark:bg-slate-700 h-2 rounded-full overflow-hidden shadow-inner">
              <div class="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 transition-all duration-500 ease-out rounded-full shadow-[0_0_10px_rgba(99,102,241,0.5)]"
                   :style="{ width: `${porcentajeAvance}%` }"></div>
            </div>
            <span class="text-[10px] md:text-xs font-black text-indigo-600 dark:text-indigo-400 font-mono w-8 md:w-10 text-right">{{ porcentajeAvance }}%</span>
          </div>
        </div>

        <main class="flex-grow w-full max-w-4xl mx-auto p-2 md:p-6 flex flex-col">
          <div class="flex justify-between items-center mb-3 md:mb-5 bg-white dark:bg-slate-800 p-3 md:p-4 rounded-2xl shadow-sm border border-gray-200 dark:border-slate-700 transition-colors">
          <div class="text-indigo-900 dark:text-indigo-300 font-bold flex flex-col items-start gap-0.5">
            <span class="text-sm md:text-base">{{ nombreEstudiante }}</span>
            <button v-if="preguntasGuardadas.length > 0" @click="mostrarPanelPendientes = true"
              class="text-[10px] md:text-xs bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-200 px-2 py-0.5 rounded-full font-bold shadow-sm hover:bg-amber-200 dark:hover:bg-amber-800 transition-colors flex items-center gap-1">
              <i class="fa-solid fa-bookmark"></i> {{ preguntasGuardadas.length }} Pendientes
            </button>
          </div>
          <div class="flex flex-col items-center">
            <div class="font-mono text-xl md:text-2xl font-black text-gray-700 dark:text-gray-200 flex items-center gap-2 transition-colors">
              <i class="fa-regular fa-clock"></i> {{ tiempoFormateado }}
            </div>
          </div>
          <div class="font-bold text-indigo-600 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-900/40 px-2 py-1 md:px-3 md:py-1.5 rounded-xl border border-indigo-100 dark:border-indigo-800 text-center transition-colors">
            <span class="text-sm md:text-base">{{ Math.max(0, indiceRespondidos.length - preguntasReportadasEnSesion.length) }} / {{ Math.max(1, examen.length - preguntasReportadasEnSesion.length) }}</span><br><span class="text-[9px] md:text-[10px] font-normal uppercase tracking-wide">Contestadas</span>
          </div>
        </div>
        <TarjetaReactivo v-if="reactivoActual" :pregunta="reactivoActual" :numero="indiceActual + 1"
          @responder="procesarRespuesta" @pregunta-reportada="registrarPreguntaReportada" />

        <div v-if="!mostrarRetroalimentacion" class="mt-4 flex justify-center w-full mb-4">
          <button @click="guardarParaDespues"
            class="w-full md:w-auto bg-white dark:bg-slate-800 border-2 border-slate-300 dark:border-slate-600 text-slate-600 dark:text-slate-300 font-bold py-2.5 md:py-3 px-6 md:px-8 rounded-xl shadow-sm hover:bg-slate-50 dark:hover:bg-slate-700 hover:border-slate-400 dark:hover:border-slate-500 transition-colors flex items-center justify-center gap-2 text-sm md:text-base">
            <i class="fa-solid fa-forward-step"></i> Saltar / Guardar para después
          </button>
        </div>

        <div v-if="mostrarRetroalimentacion"
          class="fixed bottom-0 left-0 right-0 bg-white dark:bg-slate-800 border-t-8 border-t-indigo-500/10 dark:border-t-slate-700 p-6 shadow-2xl animate-slide-up z-50 transition-colors">
          <div class="max-w-3xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
            <div class="text-left flex-1">
              <h3 class="text-2xl font-black mb-2 transition-colors"
                :class="respuestaSeleccionada.es_correcta ? 'text-green-600 dark:text-green-400' : 'text-orange-600 dark:text-orange-400'">{{
                  respuestaSeleccionada.es_correcta ? '¡Correcto!' : 'Incorrecto' }}</h3>
              <p class="text-gray-700 dark:text-gray-300 text-lg transition-colors" v-html="renderizarTexto(reactivoActual.retroalimentacion)"></p>
            </div>
            <button @click="avanzarSiguiente"
              class="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-4 rounded-xl font-black transition-colors shadow-lg shadow-indigo-500/30">Siguiente</button>
          </div>
        </div>

        </main>

        <!-- PANEL PENDIENTES -->
        <div v-if="mostrarPanelPendientes"
          class="fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
          <div class="bg-white rounded-3xl shadow-2xl w-full max-w-md overflow-hidden flex flex-col max-h-[80vh]">
            <div class="p-5 border-b bg-slate-50 flex justify-between items-center">
              <h3 class="font-bold text-slate-800 text-lg"><i class="fa-solid fa-bookmark text-amber-500 mr-2"></i>
                Preguntas guardadas</h3>
              <button @click="mostrarPanelPendientes = false"
                class="text-slate-400 hover:text-slate-700 bg-white shadow-sm border px-2 py-1 rounded-lg"><i
                  class="fa-solid fa-times text-xl"></i></button>
            </div>
            <div class="overflow-y-auto p-4 flex-1">
              <div v-if="preguntasGuardadas.length === 0" class="text-center text-slate-500 py-6 font-medium">No tienes
                preguntas pendientes.</div>
              <div v-for="idx in preguntasGuardadas" :key="idx" @click="irAPreguntaGuardada(idx)"
                class="bg-white border-2 border-slate-100 rounded-xl p-4 mb-3 shadow-sm hover:border-indigo-300 hover:shadow-md cursor-pointer transition flex justify-between items-center group">
                <div class="flex-1 pr-3">
                  <div class="flex flex-wrap items-center gap-2 mb-1">
                    <span class="text-xs font-bold text-indigo-500 uppercase">Reactivo {{ idx + 1 }}</span>
                    <span class="text-[10px] font-bold text-slate-500 uppercase bg-slate-100 px-2 py-0.5 rounded">{{
                      examen[idx].area }}</span>
                  </div>
                  <p class="text-sm text-slate-700 line-clamp-2 group-hover:text-indigo-800"
                    v-html="renderizarTexto(examen[idx].planteamiento)"></p>
                </div>
                <i class="fa-solid fa-arrow-right text-slate-300 group-hover:text-indigo-500"></i>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="pantalla === 'login_admin'"
        class="w-full max-w-md bg-white p-10 rounded-3xl shadow-xl mt-10 border-t-8 border-indigo-600 animate-fade-in">
        <h2 class="text-3xl font-black text-indigo-900 mb-6 text-center"><i
            class="fa-solid fa-lock mr-2 text-indigo-500"></i>Acceso a Revisión</h2>
        <div v-if="errorLogin"
          class="bg-red-50 border border-red-200 text-red-600 p-3 rounded-xl mb-4 text-center font-bold text-sm">{{
            errorLogin }}</div>
        <form @submit.prevent="iniciarSesionAdmin" class="space-y-5">
          <div>
            <label class="block text-sm font-bold text-gray-700 mb-1">Correo Electrónico</label>
            <input v-model="loginCorreo" type="email" placeholder="admin@oci.com" required
              class="w-full p-3.5 rounded-xl border-2 border-gray-200 focus:border-indigo-400 outline-none transition text-gray-800">
          </div>
          <div>
            <label class="block text-sm font-bold text-gray-700 mb-1">Contraseña</label>
            <input v-model="loginPassword" type="password" placeholder="••••••••" required
              class="w-full p-3.5 rounded-xl border-2 border-gray-200 focus:border-indigo-400 outline-none transition text-gray-800">
          </div>
          <button type="submit" :disabled="cargandoLogin"
            class="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-black py-4 rounded-xl shadow-lg mt-2 transition flex items-center justify-center gap-2">
            <i v-if="cargandoLogin" class="fa-solid fa-spinner fa-spin"></i>
            <span v-if="cargandoLogin">Autenticando...</span>
            <span v-else>Entrar al Panel</span>
          </button>
        </form>
        <button @click="pantalla = 'inicio'"
          class="w-full mt-4 bg-transparent border-2 border-gray-200 text-gray-500 hover:text-gray-700 font-bold py-3 rounded-xl transition">Cancelar</button>
      </div>

      <div v-else-if="pantalla === 'resultados'"
        class="w-full max-w-2xl bg-white rounded-3xl shadow-2xl overflow-hidden animate-fade-in relative border-4"
        :class="resultadoNivel.claseColor">
        <div class="bg-indigo-600 dark:bg-slate-900 p-6 md:p-8 border-b-4 border-indigo-400 dark:border-indigo-500 transition-colors">
          <h2 class="text-xs md:text-sm font-black text-indigo-200 dark:text-indigo-400 uppercase tracking-[0.2em] mb-1">Resultado Final</h2>
          <h3 class="text-2xl md:text-3xl font-black text-white transition-colors">{{ nombreEstudiante }} {{ apellidoEstudiante }}</h3>
          <p class="text-indigo-100 dark:text-slate-400 text-sm italic">{{ fechaFinalizacion }}</p>
        </div>
        <div class="py-10 text-center px-4 bg-white dark:bg-slate-800 transition-colors rounded-b-3xl">
          <div class="text-[7rem] animate-bounce-slow transition-all duration-700" 
               :class="resultadoNivel.iconColor"
               :style="{ filter: `drop-shadow(0 0 25px ${resultadoNivel.iconColor.includes('blue') ? '#3b82f6' : resultadoNivel.iconColor.includes('orange') ? '#f97316' : '#94a3b8'})` }">
            <i v-if="!resultadoNivel.esMedalla" :class="resultadoNivel.iconoClass"></i>
            <img v-else-if="resultadoNivel.tipoMedalla === 'oro'"
              src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/solid/medal.svg"
              class="w-32 h-32 mx-auto hover:scale-110 transition cursor-pointer"
              style="filter: brightness(0) saturate(100%) invert(88%) sepia(21%) saturate(2335%) hue-rotate(345deg) brightness(101%) contrast(106%) drop-shadow(0 0 20px #fbbf24);" />
            <img v-else-if="resultadoNivel.tipoMedalla === 'plata'"
              src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/solid/medal.svg"
              class="w-32 h-32 mx-auto hover:scale-110 transition cursor-pointer"
              style="filter: brightness(0) saturate(100%) invert(87%) sepia(2%) saturate(913%) hue-rotate(185deg) brightness(89%) contrast(85%) drop-shadow(0 0 20px #94a3b8);" />
            <img v-else-if="resultadoNivel.tipoMedalla === 'bronce'"
              src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/solid/medal.svg"
              class="w-32 h-32 mx-auto hover:scale-110 transition cursor-pointer"
              style="filter: brightness(0) saturate(100%) invert(58%) sepia(87%) saturate(2250%) hue-rotate(342deg) brightness(87%) contrast(92%) drop-shadow(0 0 20px #92400e);" />
          </div>
          <div class="text-6xl font-black mb-4 text-indigo-900 dark:text-indigo-400 transition-colors">{{ porcentajeGlobal }}%</div>
          <h3 class="text-2xl font-black mb-2 text-gray-800 dark:text-gray-100 transition-colors">{{ resultadoNivel.mensaje }}</h3>
          <p class="text-gray-600 dark:text-slate-400 italic transition-colors">"{{ resultadoNivel.subtitulo }}"</p>

          <div class="mt-8 flex flex-col gap-3 max-w-xs mx-auto">
            <button @click="abrirRendimientoAlumno()"
              class="bg-amber-500 hover:bg-amber-600 transition text-white py-4 px-6 rounded-xl font-bold shadow-lg flex items-center justify-start gap-3">
              <i class="fa-solid fa-chart-line text-white"></i> Mi Rendimiento
            </button>
            <button @click="pantalla = 'revision'"
              class="bg-indigo-600 hover:bg-indigo-700 transition text-white py-4 px-6 rounded-xl font-bold flex items-center justify-start gap-3 mt-2">
              <i class="fa-solid fa-book-open text-white"></i> Ver Guía de Estudio
            </button>
            <button @click="pantalla = 'inicio'"
              class="bg-white dark:bg-slate-800 border-2 border-indigo-600 dark:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-slate-700 transition text-indigo-600 dark:text-indigo-400 py-4 px-6 rounded-xl font-bold flex items-center justify-start gap-3 mt-2 shadow-md">
              <i class="fa-solid fa-rotate-right text-indigo-600 dark:text-indigo-400"></i> Intentar de Nuevo
            </button>
          </div>
        </div>
      </div>

      <div v-else-if="pantalla === 'revision'" class="w-full max-w-4xl animate-fade-in print-area">
        <div
          class="bg-white p-6 rounded-t-3xl border-b-4 border-indigo-500 flex justify-between items-center sticky top-0 z-10 no-print shadow-md">
          <h2 class="text-2xl font-black text-indigo-800">Guía de Estudio</h2>
          <div class="flex gap-2">
            <button @click="imprimirGuia" class="bg-slate-800 text-white px-4 py-2 rounded-lg font-bold">
              <i class="fa-solid fa-print"></i> Imprimir
            </button>
            <button @click="pantalla = 'resultados'" class="bg-gray-100 p-2 rounded-lg font-bold text-gray-600">
              Cerrar
            </button>
          </div>
        </div>

        <div class="bg-blue-50 p-6 space-y-8 study-content">
          <div v-for="(p, i) in examen" :key="p.id" class="bg-white p-6 rounded-2xl border page-block">
            <span class="bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full text-xs font-black mb-4 inline-block">
              [{{ p.identificador || 'ID-ND' }}] Reactivo {{ i + 1 }} - {{ p.area }}
            </span>
            <p class="text-xl font-bold text-gray-800 mb-4" v-html="renderizarTexto(p.planteamiento)"></p>

            <div class="bg-green-50 p-4 rounded-xl border-2 border-green-200 mb-4">
              <p class="text-xs font-bold text-green-600 uppercase mb-1">Respuesta Correcta:</p>
              <p class="text-lg font-bold text-green-900"
                v-html="renderizarTexto(p.opciones.find(o => o.es_correcta)?.texto_opcion || 'Sin respuesta correcta asignada')">
              </p>
            </div>

            <div class="bg-blue-50 border-l-4 border-blue-400 p-4 rounded-r-xl">
              <p class="text-xs font-bold text-blue-600 uppercase mb-1">Explicación:</p>
              <p class="text-gray-700" v-html="renderizarTexto(p.retroalimentacion)"></p>
            </div>
          </div>
        </div>
      </div>

      <!-- PANEL RENDIMIENTO ALUMNO (MODAL) -->
      <div v-if="mostrarModalRendimiento && rendimientoAlumno"
        class="fixed inset-0 bg-slate-900/80 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
        <div class="bg-white rounded-3xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">

          <div class="p-6 border-b bg-indigo-600 text-white flex justify-between items-center">
            <div>
              <h3 class="font-black text-2xl"><i class="fa-solid fa-chart-line mr-2"></i> Mi Rendimiento</h3>
              <p class="text-indigo-200 text-sm mt-1">{{ rendimientoAlumno.estudiante }}</p>
            </div>
            <button @click="mostrarModalRendimiento = false"
              class="text-white hover:text-indigo-200 bg-indigo-700/50 p-2 rounded-xl transition"><i
                class="fa-solid fa-times text-xl"></i></button>
          </div>

          <!-- Navegación de Pestañas -->
          <div class="bg-indigo-600 p-1 flex border-b dark:border-slate-700">
            <button @click="setTabInterno('resumen')" 
              class="flex-1 py-3 text-sm font-bold transition-all rounded-t-2xl flex items-center justify-center gap-2"
              :class="tabInternoRendimiento === 'resumen' ? 'bg-slate-50 text-indigo-700 shadow-inner' : 'text-white hover:bg-indigo-700'">
              <i class="fa-solid fa-list-ul"></i> Resumen
            </button>
            <button @click="setTabInterno('grafica')" 
              class="flex-1 py-3 text-sm font-bold transition-all rounded-t-2xl flex items-center justify-center gap-2"
              :class="tabInternoRendimiento === 'grafica' ? 'bg-slate-50 text-indigo-700 shadow-inner' : 'text-white hover:bg-indigo-700'">
              <i class="fa-solid fa-chart-pie"></i> Gráfica
            </button>
          </div>

          <!-- Contenido de Pestañas -->
          <div class="overflow-y-auto p-6 flex-1 space-y-8 bg-slate-50 dark:bg-slate-900 transition-colors">
            
            <!-- PESTAÑA RESUMEN -->
            <div v-if="tabInternoRendimiento === 'resumen'" class="space-y-8 animate-fade-in">
              <!-- Resumen de Métricas -->
              <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div class="bg-white dark:bg-slate-800 p-4 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 text-center transition-colors">
                  <p class="text-xs text-slate-500 dark:text-slate-400 font-bold uppercase mb-1">Exámenes</p>
                  <p class="text-3xl font-black text-indigo-700 dark:text-indigo-400">{{ rendimientoAlumno.estadisticas.total_examenes }}</p>
                </div>
                <div class="bg-white dark:bg-slate-800 p-4 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 text-center transition-colors">
                  <p class="text-xs text-slate-500 dark:text-slate-400 font-bold uppercase mb-1">Promedio</p>
                  <p class="text-3xl font-black"
                    :class="rendimientoAlumno.estadisticas.promedio_global >= 80 ? 'text-green-600' : 'text-amber-500'">{{
                      rendimientoAlumno.estadisticas.promedio_global }}%</p>
                </div>
                <div class="bg-white dark:bg-slate-800 p-4 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 text-center transition-colors">
                  <p class="text-xs text-slate-500 dark:text-slate-400 font-bold uppercase mb-1">Tiempo Extra</p>
                  <p class="text-3xl font-black text-rose-500">{{ rendimientoAlumno.estadisticas.tiempo_extra_solicitado
                  }}<span class="text-base text-rose-300 ml-1">veces</span></p>
                </div>
                <div class="bg-white dark:bg-slate-800 p-4 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 text-center transition-colors">
                  <p class="text-xs text-slate-500 dark:text-slate-400 font-bold uppercase mb-1">Reportes</p>
                  <p class="text-3xl font-black text-slate-700 dark:text-slate-200">{{
                    rendimientoAlumno.estadisticas.preguntas_enviadas_revision }}</p>
                </div>
              </div>

              <!-- Gráfica de Barras CSS (Top Scores por Área) -->
              <div class="bg-white dark:bg-slate-800 p-6 rounded-3xl shadow-sm border border-slate-200 dark:border-slate-700 transition-colors">
                <h4 class="font-bold text-slate-800 dark:text-slate-100 mb-6 flex items-center gap-2"><i
                    class="fa-solid fa-trophy text-amber-500"></i> Puntuaciones Más Altas por Área</h4>
                <div class="space-y-5">
                  <div v-for="(puntaje, area) in rendimientoAlumno.mejores_por_area" :key="area">
                    <div class="flex justify-between items-end mb-1">
                      <span class="text-sm font-bold text-slate-700 dark:text-slate-300">{{ area }}</span>
                      <span class="text-xs font-black" :class="puntaje >= 80 ? 'text-green-600' : 'text-slate-600 dark:text-slate-400'">{{
                        puntaje }}%</span>
                    </div>
                    <div class="w-full bg-slate-100 dark:bg-slate-700 rounded-full h-3 overflow-hidden">
                      <div class="h-3 rounded-full transition-all duration-1000 ease-out"
                        :class="puntaje >= 90 ? 'bg-green-500' : (puntaje >= 70 ? 'bg-amber-400' : 'bg-rose-400')"
                        :style="`width: ${puntaje}%`"></div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Historial Lista -->
              <div>
                <h4 class="font-bold text-slate-800 dark:text-slate-100 mb-4 ml-2"><i class="fa-regular fa-clock text-indigo-400 mr-2"></i>
                  Historial de Intentos</h4>
                <div class="space-y-2">
                  <div v-for="(h, i) in rendimientoAlumno.historial" :key="i"
                    class="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-100 dark:border-slate-700 shadow-sm flex justify-between items-center hover:border-indigo-200 dark:hover:border-indigo-800 transition-colors">
                    <div>
                      <p class="text-xs text-slate-400 font-bold">{{ h.fecha }}</p>
                      <p class="text-sm font-bold text-slate-800 dark:text-slate-200">{{ h.area }}</p>
                    </div>
                    <div class="px-3 py-1 rounded-lg font-black text-sm"
                      :class="h.calificacion >= 80 ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-slate-50 dark:bg-slate-700 text-slate-600 dark:text-slate-400'">
                      {{ h.calificacion }}%
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- PESTAÑA GRÁFICA -->
            <div v-if="tabInternoRendimiento === 'grafica'" class="animate-fade-in flex flex-col items-center">
              <div class="bg-white dark:bg-slate-800 p-6 rounded-3xl shadow-sm border border-slate-200 dark:border-slate-700 w-full transition-colors">
                <h4 class="font-bold text-slate-800 dark:text-slate-100 mb-6 flex items-center justify-center gap-2">
                  <i class="fa-solid fa-chart-pie text-indigo-500"></i> Promedio Histórico por Área
                </h4>
                <div class="flex justify-center w-full min-h-[400px]">
                   <Radar :data="chartDataRadarAlumno" :options="chartOptionsRadar" />
                </div>
                <p class="text-center text-xs text-slate-500 dark:text-slate-400 mt-6 italic">
                  Este gráfico representa tus mejores puntuaciones registradas en cada área de conocimiento.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="pantalla === 'admin'"
        class="w-full bg-white dark:bg-slate-900 rounded-3xl shadow-xl overflow-hidden max-w-[1400px] mx-auto flex h-[90vh] transition-colors relative">
        
        <!-- Botón Toggle Sidebar (Móvil) -->
        <button @click="menuAdminAbierto = !menuAdminAbierto" class="md:hidden absolute top-4 right-4 z-50 bg-indigo-600 text-white p-2.5 rounded-xl shadow-lg">
          <i class="fa-solid" :class="menuAdminAbierto ? 'fa-times' : 'fa-bars'"></i>
        </button>

        <!-- Sidebar (Izquierda) -->
        <div :class="[menuAdminAbierto ? 'translate-x-0' : '-translate-x-full md:translate-x-0']" class="absolute md:relative z-40 w-72 h-full bg-slate-50 dark:bg-slate-800 border-r border-slate-200 dark:border-slate-700 flex flex-col shrink-0 transition-transform duration-300">
          <div class="p-6 border-b border-slate-200 dark:border-slate-700 mt-2 md:mt-0">
            <h2 class="text-2xl font-black text-slate-800 dark:text-white flex items-center gap-3">
              <i class="fa-solid fa-shapes text-indigo-600 dark:text-indigo-400"></i>Panel Admin
            </h2>
          </div>
          
          <div class="p-4 flex-1 overflow-y-auto space-y-2 flex flex-col">
            <button @click="vistaAdmin = 'resultados'; menuAdminAbierto = false" 
              class="w-full text-left px-4 py-3 rounded-xl font-bold transition flex items-center gap-3"
              :class="vistaAdmin === 'resultados' ? 'bg-indigo-600 dark:bg-indigo-500 text-white shadow-md' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'">
              <i class="fa-solid fa-table-list w-5 text-center"></i> Resultados
            </button>
            <button @click="vistaAdmin = 'configuracion'; menuAdminAbierto = false" 
              class="w-full text-left px-4 py-3 rounded-xl font-bold transition flex items-center gap-3"
              :class="vistaAdmin === 'configuracion' ? 'bg-indigo-600 dark:bg-indigo-500 text-white shadow-md' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'">
              <i class="fa-solid fa-gear w-5 text-center"></i> Configuración
            </button>
            <button @click="vistaAdmin = 'reportadas'; menuAdminAbierto = false"
              class="w-full text-left px-4 py-3 rounded-xl font-bold transition flex items-center justify-between"
              :class="vistaAdmin === 'reportadas' ? 'bg-indigo-600 dark:bg-indigo-500 text-white shadow-md' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'">
              <div class="flex items-center gap-3">
                <i class="fa-solid fa-flag w-5 text-center"></i> Reportes
              </div>
              <span v-if="preguntasReportadas.length > 0"
                class="bg-rose-500 dark:bg-rose-600 text-white text-xs px-2.5 py-1 rounded-full shadow-sm">{{ preguntasReportadas.length }}</span>
            </button>
            <button @click="vistaAdmin = 'rendimiento'; menuAdminAbierto = false" 
              class="w-full text-left px-4 py-3 rounded-xl font-bold transition flex items-center gap-3"
              :class="vistaAdmin === 'rendimiento' ? 'bg-indigo-600 dark:bg-indigo-500 text-white shadow-md' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'">
              <i class="fa-solid fa-magnifying-glass-chart w-5 text-center"></i> Rendimiento
            </button>
            <button @click="vistaAdmin = 'estadisticas'; menuAdminAbierto = false" 
              class="w-full text-left px-4 py-3 rounded-xl font-bold transition flex items-center gap-3"
              :class="vistaAdmin === 'estadisticas' ? 'bg-indigo-600 dark:bg-indigo-500 text-white shadow-md' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'">
              <i class="fa-solid fa-chart-line w-5 text-center"></i> Estadísticas
            </button>
            
            <div class="mt-auto pt-6 pb-2">
              <button @click="pantalla = 'inicio'"
                class="w-full bg-rose-50 dark:bg-rose-900/30 text-rose-600 dark:text-rose-400 hover:bg-rose-500 hover:text-white dark:hover:bg-rose-600 border border-rose-200 dark:border-rose-800/50 px-4 py-3 rounded-xl font-bold transition-colors flex items-center gap-3">
                <i class="fa-solid fa-power-off w-5 text-center"></i> Cerrar Sesión
              </button>
            </div>
          </div>
        </div>

        <!-- Área de Contenido (Derecha) -->
        <div class="p-6 md:p-10 overflow-y-auto w-full md:flex-1 bg-white">

          <!-- VISTA 1: RESULTADOS (TABLA SOLAMENTE) -->
          <div v-if="vistaAdmin === 'resultados'" class="flex flex-col gap-6 animate-fade-in">
            <div class="flex items-center justify-between border-b pb-4 mb-2">
              <h3 class="font-black text-indigo-900 text-2xl flex items-center gap-3">
                <i class="fa-solid fa-table-list text-indigo-400"></i> Historial de Resultados
              </h3>
            </div>
            
            <div class="w-full">
              <div class="overflow-hidden rounded-2xl border bg-white shadow-sm">
                <table class="w-full text-left">
                  <thead>
                    <tr class="bg-indigo-50 text-indigo-900 text-xs uppercase tracking-wider">
                      <th class="p-4">Alumno</th>
                      <th class="p-4">Área / Tipo</th>
                      <th class="p-4 text-center">Calif</th>
                      <th class="p-4 text-right">Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="res in listaResultados" :key="res.id"
                      class="border-t text-sm transition hover:bg-indigo-50/30">
                      <td class="p-4 font-bold text-gray-800">{{ res.nombre }}</td>
                      <td class="p-4 text-xs">
                        <div class="flex flex-col gap-1.5 items-start">
                          <span class="bg-slate-100 text-slate-700 px-2.5 py-1 rounded-full font-bold border">
                            {{ res.tipo_examen }}
                          </span>
                          <span v-if="res.modalidad_test" class="bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full font-bold border border-indigo-200 text-[10px] uppercase tracking-wider">
                            {{ res.modalidad_test }}
                          </span>
                        </div>
                      </td>
                      <td class="p-4 font-black text-center"
                        :class="res.calificacion >= 70 ? 'text-green-600' : (res.calificacion >= 60 ? 'text-amber-500' : 'text-red-500')">
                        {{ res.calificacion }}%</td>
                      <td class="p-4 text-gray-500 text-xs text-right">{{ res.fecha }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            </div>

          <!-- NUEVA VISTA: CONFIGURACIÓN -->
          <div v-else-if="vistaAdmin === 'configuracion'" class="flex flex-col gap-6 animate-fade-in">
            <div class="flex items-center justify-between border-b pb-4 mb-2">
              <h3 class="font-black text-indigo-900 text-2xl flex items-center gap-3">
                <i class="fa-solid fa-gear text-indigo-400"></i> Configuración del Simulador
              </h3>
            </div>
            
            <div class="w-full bg-slate-50 p-6 rounded-3xl border border-slate-200">
              <div class="bg-indigo-50 border border-indigo-100 rounded-2xl p-6 mb-8 shadow-sm">
                <h3 class="text-xl font-black text-indigo-900 mb-2 flex items-center gap-2">Ajustes Globales</h3>
                <p class="text-indigo-700">Ajusta los parámetros para las distintas modalidades de examen que se ofrecerán a los alumnos. Los cambios aplicarán inmediatamente a los nuevos exámenes que se generen.</p>
              </div>

              <!-- Tres tipos de test configs -->
              <div class="flex flex-col gap-5 mb-8">
                <!-- Entrenamiento -->
                <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm hover:border-indigo-300 transition">
                  <h4 class="font-bold text-slate-800 mb-5 border-b border-slate-100 pb-3 flex items-center gap-2"><i class="fa-solid fa-dumbbell text-indigo-500"></i> Entrenamiento</h4>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Preguntas a Mostrar</label>
                      <input type="number" v-model="configAdmin.entrenamiento_preguntas" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:bg-white text-lg font-bold text-slate-700 outline-none transition">
                    </div>
                    <div>
                      <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Tiempo (Minutos)</label>
                      <input type="number" v-model="configAdmin.entrenamiento_minutos" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:bg-white text-lg font-bold text-slate-700 outline-none transition">
                    </div>
                  </div>
                </div>

                <!-- Concentracion -->
                <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm hover:border-amber-300 transition">
                  <h4 class="font-bold text-slate-800 mb-5 border-b border-slate-100 pb-3 flex items-center gap-2"><i class="fa-solid fa-brain text-amber-500"></i> Concentración</h4>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Preguntas a Mostrar</label>
                      <input type="number" v-model="configAdmin.concentracion_preguntas" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-amber-500 focus:bg-white text-lg font-bold text-slate-700 outline-none transition">
                    </div>
                    <div>
                      <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Tiempo (Minutos)</label>
                      <input type="number" v-model="configAdmin.concentracion_minutos" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-amber-500 focus:bg-white text-lg font-bold text-slate-700 outline-none transition">
                    </div>
                  </div>
                </div>

                <!-- Maraton -->
                <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm hover:border-rose-300 transition">
                  <h4 class="font-bold text-slate-800 mb-5 border-b border-slate-100 pb-3 flex items-center gap-2"><i class="fa-solid fa-fire text-rose-500"></i> Maratón</h4>
                  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Preguntas a Mostrar</label>
                      <input type="number" v-model="configAdmin.maraton_preguntas" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-rose-500 focus:bg-white text-lg font-bold text-slate-700 outline-none transition">
                    </div>
                    <div>
                      <label class="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Tiempo (Minutos)</label>
                      <input type="number" v-model="configAdmin.maraton_minutos" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-rose-500 focus:bg-white text-lg font-bold text-slate-700 outline-none transition">
                    </div>
                  </div>
                </div>
              </div>

               <!-- Referencias PDF Config -->
              <div class="bg-white border rounded-2xl p-6 shadow-sm mb-8">
                <h4 class="font-bold text-slate-800 mb-4 border-b pb-2 flex items-center gap-2"><i class="fa-solid fa-file-pdf text-red-500"></i> Selección de Preguntas (PDFs Base)</h4>
                <div class="space-y-2">
                   <p class="text-sm text-slate-600 mb-4">Puedes elegir si el sistema genera exámenes utilizando únicamente preguntas que tienen una referencia bibliográfica cargada, aquellas que no tienen, o mezclar ambas.</p>
                   <select v-model="configAdmin.filtro_referencia" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-slate-800 font-bold">
                     <option value="con_referencia">Solo preguntas que TENGAN Referencia (Recomendado)</option>
                     <option value="sin_referencia">Solo preguntas SIN Referencia</option>
                     <option value="ambas">Mezclar preguntas con y sin referencia</option>
                   </select>
                </div>
              </div>

              <div class="grid grid-cols-1 md:grid-cols-2 gap-4 border-t pt-4 mt-6">
                <div>
                  <label class="block text-sm font-bold text-gray-700 mb-1 flex items-center gap-2"><i class="fa-solid fa-envelope text-indigo-400"></i> Correo Supervisor</label>
                  <input v-model="configAdmin.correo_supervisor" type="text" placeholder="supervisor@escuela.edu.mx" class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-slate-800 font-bold">
                </div>
              </div>

              <div class="flex justify-end mt-8">
                <button @click="guardarConfigAdmin"
                  class="w-full md:w-auto bg-slate-800 hover:bg-black text-white font-bold py-4 px-10 rounded-xl transition shadow-xl text-lg flex justify-center items-center gap-2">
                  <i class="fa-solid fa-floppy-disk"></i> Guardar Configuración
                </button>
              </div>
            </div>

          </div>

            <!-- NUEVA VISTA: ESTADÍSTICAS GLOBALES -->
          <div v-else-if="vistaAdmin === 'estadisticas'" class="flex flex-col gap-8 animate-fade-in">
            <h3 class="font-bold text-indigo-800 mb-2 border-b pb-2 text-2xl"><i class="fa-solid fa-chart-line mr-2"></i> Estadísticas Generales</h3>
            
            <div class="grid grid-cols-1 xl:grid-cols-2 gap-8 w-full">
              <!-- Radar General -->
              <div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-200 flex flex-col items-center">
                <h4 class="font-bold text-slate-800 mb-6 w-full text-center flex justify-center items-center gap-2">
                  <i class="fa-solid fa-bullseye text-indigo-500"></i>
                  Promedio de Áreas (Global)
                </h4>
                <div class="w-full flex justify-center items-center relative" style="height: 400px; max-width: 500px;">
                  <Radar :data="chartDataRadarGlobal" :options="chartOptionsRadar" />
                </div>
              </div>

              <!-- Barras General -->
               <div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-200 flex flex-col items-center">
                <h4 class="font-bold text-slate-800 mb-6 w-full text-center flex justify-center items-center gap-2">
                  <i class="fa-solid fa-users text-indigo-500"></i>
                  Rendimiento por Estudiante
                </h4>
                <div class="w-full flex justify-center items-center relative" style="height: 400px;">
                  <Bar :data="chartDataBarrasGlobal" :options="chartOptionsBarras" />
                </div>
              </div>
            </div>
            
          </div>

          <!-- VISTA 3: RENDIMIENTO ESTUDIANTIL -->
          <div v-else-if="vistaAdmin === 'rendimiento'" class="flex flex-col gap-6">
            <div class="bg-white p-6 rounded-2xl border shadow-sm">
              <h3 class="font-bold text-slate-800 mb-4 border-b pb-2"><i
                  class="fa-solid fa-magnifying-glass mr-2 text-indigo-500"></i> Buscar Historial de Alumno</h3>
              <div class="flex flex-col md:flex-row gap-4 mb-4">
                <input type="text" id="busquedaAlumnoInput" placeholder="Nombre completo o palabra clave..."
                  class="flex-1 p-3 rounded-xl border-2 border-slate-200 focus:border-indigo-400 outline-none"
                  @keyup.enter="abrirRendimientoAlumno(document.getElementById('busquedaAlumnoInput').value)">
                <button @click="abrirRendimientoAlumno(document.getElementById('busquedaAlumnoInput').value)"
                  class="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-3 rounded-xl font-bold transition flex items-center gap-2">
                  <i class="fa-solid fa-search"></i> Buscar
                </button>
              </div>
              <!-- Instrucciones -->
              <div v-if="!rendimientoAlumno"
                class="text-center py-10 bg-slate-50 rounded-xl border border-dashed border-slate-300">
                <div class="text-4xl mb-3 text-slate-300"><i class="fa-solid fa-user-graduate"></i></div>
                <p class="text-slate-500 font-bold">Ingresa el nombre de un alumno para inspeccionar sus estadísticas e
                  historial de intentos a lo largo del tiempo.</p>
              </div>
            </div>

            <!-- Inyectar el mismo diseño del modal aquí mismo para el modo admin, pero embebido -->
            <div v-if="rendimientoAlumno"
              class="animate-fade-in bg-white rounded-3xl shadow-sm border border-slate-200 overflow-hidden flex flex-col">
              <div class="p-6 border-b bg-indigo-50 flex justify-between items-center">
                <div>
                  <h3 class="font-black text-2xl text-indigo-900"><i
                      class="fa-solid fa-chart-line mr-2 text-indigo-600"></i> Rendimiento: {{
                        rendimientoAlumno.estudiante }}</h3>
                </div>
              </div>
              <div class="p-6 space-y-8 bg-slate-50">
                <!-- Resumen de Métricas -->
                <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <div class="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 text-center">
                    <p class="text-xs text-slate-500 font-bold uppercase mb-1">Exámenes</p>
                    <p class="text-3xl font-black text-indigo-700">{{ rendimientoAlumno.estadisticas.total_examenes }}
                    </p>
                  </div>
                  <div class="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 text-center">
                    <p class="text-xs text-slate-500 font-bold uppercase mb-1">Promedio</p>
                    <p class="text-3xl font-black"
                      :class="rendimientoAlumno.estadisticas.promedio_global >= 80 ? 'text-green-600' : 'text-amber-500'">
                      {{ rendimientoAlumno.estadisticas.promedio_global }}%</p>
                  </div>
                  <div class="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 text-center">
                    <p class="text-xs text-slate-500 font-bold uppercase mb-1">Tiempo Extra</p>
                    <p class="text-3xl font-black text-rose-500">{{
                      rendimientoAlumno.estadisticas.tiempo_extra_solicitado }}<span
                        class="text-base text-rose-300 ml-1">veces</span></p>
                  </div>
                  <div class="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 text-center">
                    <p class="text-xs text-slate-500 font-bold uppercase mb-1">Reportes</p>
                    <p class="text-3xl font-black text-slate-700">{{
                      rendimientoAlumno.estadisticas.preguntas_enviadas_revision }}</p>
                  </div>
                </div>

                <!-- Gráfica de Radar (Promedio de Áreas) -->
                <div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-200">
                  <h4 class="font-bold text-slate-800 mb-6 flex items-center gap-2">
                    <i class="fa-solid fa-chart-pie text-indigo-500"></i> Promedio por Área de Estudio
                  </h4>
                  <div class="w-full flex justify-center items-center" style="height: 400px;">
                    <Radar v-if="rendimientoAlumno.mejores_por_area" :data="chartDataRadarAlumno" :options="chartOptionsRadar" />
                  </div>
                </div>

                <!-- Historial Lista -->
                <div>
                  <h4 class="font-bold text-slate-800 mb-4 ml-2"><i
                      class="fa-regular fa-clock text-indigo-400 mr-2"></i> Historial de Intentos</h4>
                  <div class="space-y-2">
                    <div v-for="(h, i) in rendimientoAlumno.historial" :key="i"
                      class="bg-white p-4 rounded-2xl border border-slate-100 shadow-sm flex justify-between items-center hover:border-indigo-200 transition">
                      <div>
                        <p class="text-xs text-slate-400 font-bold">{{ h.fecha }}</p>
                        <p class="text-sm font-bold text-slate-800">{{ h.area }}</p>
                      </div>
                      <div class="px-3 py-1 rounded-lg font-black text-sm"
                        :class="h.calificacion >= 80 ? 'bg-green-50 text-green-700' : 'bg-slate-50 text-slate-600'">
                        {{ h.calificacion }}%
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- VISTA 2: PREGUNTAS REPORTADAS -->
          <div v-else-if="vistaAdmin === 'reportadas'">
            <div v-if="preguntasReportadas.length === 0"
              class="text-center py-20 bg-white rounded-2xl border border-dashed border-gray-300 shadow-sm">
              <div class="text-6xl text-gray-200 mb-4"><i class="fa-solid fa-check-circle"></i></div>
              <h3 class="text-xl font-bold text-gray-600">¡Todo al día!</h3>
              <p class="text-gray-400">No hay preguntas pendientes por revisar en este momento.</p>
            </div>

            <div v-else class="flex flex-col gap-6">

              <!-- Tarjeta de Pregunta Reportada (Listado) -->
              <div v-for="pregunta in preguntasReportadas" :key="pregunta.id"
                class="bg-white p-6 rounded-2xl border shadow-sm flex flex-col hover:border-indigo-300 transition group relative">

                <div
                  class="absolute top-4 right-4 bg-red-100 text-red-700 px-2.5 py-1 rounded-md text-xs font-black animate-pulse">
                  Reportada
                </div>

                <div class="text-xs font-bold text-indigo-400 mb-2 uppercase tracking-wide pr-24">
                  ID: {{ pregunta.identificador || pregunta.id }} &bull; {{ pregunta.area }}
                </div>

                <div class="flex flex-col md:flex-row gap-6 items-start">
                  <div class="flex-1">
                    <p class="text-gray-800 font-medium mb-4 text-sm border-l-4 border-indigo-200 pl-4 py-1">
                      {{ pregunta.planteamiento }}
                    </p>
                    
                    <div class="flex flex-wrap gap-4 mt-2">
                       <div v-if="pregunta.referencia" class="bg-indigo-50 dark:bg-indigo-900/30 px-3 py-1.5 rounded-lg border border-indigo-100 dark:border-indigo-800 flex items-center gap-2">
                         <i class="fa-solid fa-book text-indigo-500 text-xs"></i>
                         <span class="text-xs font-bold text-indigo-700 dark:text-indigo-300">{{ pregunta.referencia }}</span>
                       </div>
                       <div v-if="pregunta.pagina" class="bg-slate-100 dark:bg-slate-700 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-600 flex items-center gap-2">
                         <i class="fa-solid fa-file-lines text-slate-500 text-xs"></i>
                         <span class="text-xs font-bold text-slate-700 dark:text-slate-300">Pág. {{ pregunta.pagina }}</span>
                       </div>
                    </div>
                  </div>

                  <div class="w-full md:w-auto shrink-0 self-center">
                    <button @click="editarPregunta(pregunta)"
                      class="bg-indigo-600 hover:bg-indigo-700 text-white font-black py-4 px-8 rounded-2xl transition shadow-lg flex justify-center items-center gap-3">
                      <i class="fa-solid fa-pen-to-square"></i> Revisar y Editar
                    </button>
                  </div>
                </div>
              </div>

            </div>
          </div>

        </div>

        <!-- MODAL DE EDICIÓN DE PREGUNTA REPORTADA -->
        <div v-if="preguntaEditando"
          class="fixed inset-0 bg-slate-900/60 z-50 flex items-center justify-center p-4 md:p-10 backdrop-blur-sm">
          <div class="bg-white w-full max-w-4xl rounded-3xl shadow-2xl flex flex-col max-h-full overflow-hidden border">

            <!-- Header Modal -->
            <div class="p-6 border-b bg-slate-50 flex justify-between items-center shrink-0">
              <div>
                <h3 class="text-xl font-bold text-slate-800 flex items-center gap-3">
                  <i class="fa-solid fa-pen-nib text-indigo-500"></i>
                  Editando Pregunta ({{ preguntaEditando.identificador || preguntaEditando.id }})
                </h3>
                <p class="text-sm text-slate-500">Corrige y guarda para quitar la marca de reportada.</p>
              </div>
              <button @click="cancelarEdicion"
                class="bg-white border text-gray-500 hover:text-gray-800 px-3 py-1.5 rounded-lg text-sm font-bold shadow-sm">
                Cerrar
              </button>
            </div>

            <!-- Body Modal (Formulario) -->
            <div class="p-6 overflow-y-auto flex-1 bg-white space-y-6">

              <!-- Lectura (Si tiene) -->
              <div>
                <label class="block text-sm font-bold text-gray-700 mb-2">Lectura de Apoyo (Opcional, Ojo: HTML
                  Complejo)</label>
                <textarea v-model="preguntaEditando.lectura" rows="3"
                  class="w-full p-4 rounded-xl border-2 border-slate-200 text-sm font-mono text-gray-600 bg-slate-50 focus:bg-white focus:border-indigo-400 transition"
                  placeholder="Texto o HTML..."></textarea>
              </div>

              <!-- Planteamiento -->
              <div>
                <label class="block text-sm font-bold text-gray-700 mb-2">Planteamiento (La pregunta principal)</label>
                <textarea v-model="preguntaEditando.planteamiento" rows="3"
                  class="w-full p-4 rounded-xl border-2 border-slate-200 text-base text-gray-900 focus:border-indigo-400 transition"></textarea>
              </div>

              <!-- Referencia y Página Mejorado -->
              <div class="bg-indigo-50/50 p-6 rounded-2xl border border-indigo-100 space-y-4">
                <div class="flex flex-col md:flex-row items-end gap-4">
                  <div class="flex-1 w-full">
                    <label class="block text-xs font-black text-indigo-900 uppercase tracking-widest mb-2">Libro / Referencia</label>
                    <select v-model="preguntaEditando.referencia"
                      class="w-full p-3.5 rounded-xl border-2 border-indigo-200 focus:border-indigo-500 transition bg-white text-sm font-bold shadow-sm outline-none">
                      <option value="">(Ninguno)</option>
                      <option v-for="refPdf in listaReferencias" :key="refPdf" :value="refPdf">{{ refPdf }}</option>
                    </select>
                  </div>
                  <div class="w-full md:w-32">
                    <label class="block text-xs font-black text-indigo-900 uppercase tracking-widest mb-2">Página</label>
                    <input v-model="preguntaEditando.pagina" type="text"
                      class="w-full p-3.5 rounded-xl border-2 border-indigo-200 focus:border-indigo-500 transition bg-white text-center font-bold shadow-sm outline-none">
                  </div>
                  <div class="w-full md:w-auto">
                    <button v-if="preguntaEditando.referencia" @click="mostrarPdfAdmin = true" type="button"
                      class="w-full md:w-auto bg-indigo-600 text-white p-3.5 rounded-xl hover:bg-indigo-700 font-bold transition flex items-center justify-center gap-2 shadow-lg min-w-[140px]"
                      title="Previsualizar PDF">
                      <i class="fa-solid fa-file-pdf"></i> Abrir PDF
                    </button>
                  </div>
                </div>
              </div>

              <!-- Imagen de Apoyo -->
              <div class="border-t pt-6 bg-slate-50 border-l-4 border-l-indigo-500 -mx-6 px-6 pb-6 shadow-sm">
                <label class="block text-lg font-black text-indigo-900 mb-4"><i
                    class="fa-regular fa-image mr-2 text-indigo-500"></i>Esquema de Apoyo (Gráfico)</label>
                <div
                  class="flex flex-col md:flex-row gap-6 items-start bg-white p-5 rounded-2xl shadow-sm border border-slate-200">
                  <div class="flex-1 w-full space-y-4">
                    <p class="text-sm text-gray-500 leading-relaxed">Adjunta una imagen desde tu ordenador si la
                      pregunta requiere una referencia visual. Al cargarla se subirá automáticamente y se enlazará con
                      este reactivo.</p>
                    <div class="flex gap-2">
                      <input v-model="preguntaEditando.imagen_url" type="text"
                        placeholder="Ej. /api/uploads/diagrama.png"
                        class="w-full p-3 rounded-xl border-2 border-slate-200 focus:border-indigo-400 transition text-sm font-mono text-gray-600 bg-slate-50">
                      <button @click="$refs.fileInput.click()" type="button"
                        class="bg-indigo-600 text-white px-5 rounded-xl font-bold hover:bg-indigo-700 transition flex items-center justify-center gap-2 whitespace-nowrap shadow-sm">
                        <i class="fa-solid fa-cloud-arrow-up"></i> Cargar del PC
                      </button>
                      <input type="file" ref="fileInput" @change="subirImagenReactivo" class="hidden" accept="image/*">
                    </div>
                  </div>

                  <div
                    class="w-full md:w-5/12 bg-slate-100 p-2 rounded-xl border-2 border-dashed border-slate-300 flex flex-col items-center justify-center min-h-[160px] relative group">
                    <img v-if="preguntaEditando.imagen_url" :src="preguntaEditando.imagen_url"
                      alt="Vista previa del esquema"
                      class="max-w-full max-h-[160px] object-contain rounded-lg shadow-sm bg-white">
                    <button v-if="preguntaEditando.imagen_url" @click="preguntaEditando.imagen_url = ''"
                      class="absolute top-2 right-2 bg-red-500 hover:bg-red-600 text-white rounded-full w-8 h-8 flex items-center justify-center shadow-lg opacity-0 group-hover:opacity-100 transition"
                      title="Remover imagen">
                      <i class="fa-solid fa-trash-can text-xs"></i>
                    </button>
                    <div v-if="!preguntaEditando.imagen_url"
                      class="text-center text-slate-400 flex flex-col items-center gap-2">
                      <i class="fa-regular fa-image text-4xl mb-1 text-slate-300"></i>
                      <span class="text-xs font-bold uppercase tracking-wider">Sin esquema</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Opciones -->
              <div class="border-t pt-6">
                <label class="block text-sm font-bold text-gray-700 mb-4 flex justify-between items-center">
                  <span>Opciones de Respuesta</span>
                  <span class="text-xs font-normal text-gray-500 bg-gray-100 px-2 py-1 rounded">Habilita solo 1 o más
                    correctas (Check)</span>
                </label>

                <div class="space-y-3">
                  <!-- Cada Opcion -->
                  <div v-for="(opc, idx) in preguntaEditando.opciones" :key="opc.id"
                    class="flex gap-3 items-center bg-slate-50 p-3 rounded-xl border border-slate-200 group focus-within:border-indigo-300">
                    <div class="flex-shrink-0 w-8 text-center text-slate-400 font-black">
                      {{ String.fromCharCode(65 + idx) }}
                    </div>
                    <!-- Check es_correcta -->
                    <label
                      class="flex items-center gap-2 cursor-pointer bg-white p-2 rounded-lg border shadow-sm group-hover:border-indigo-200">
                      <input type="checkbox" v-model="opc.es_correcta"
                        class="w-5 h-5 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500">
                    </label>
                    <!-- Input Texto -->
                    <input v-model="opc.texto_opcion" type="text"
                      class="flex-1 p-2 bg-transparent border-0 border-b-2 border-transparent focus:ring-0 focus:border-indigo-500 transition text-sm">
                  </div>
                </div>
              </div>

              <!-- Retroalimentación -->
              <div class="border-t pt-6 pb-4">
                <label class="block text-sm font-bold text-gray-700 mb-2">Retroalimentación / Justificación</label>
                <textarea v-model="preguntaEditando.retroalimentacion" rows="3"
                  class="w-full p-4 rounded-xl border-2 border-slate-200 text-sm bg-blue-50/50 text-blue-900 border-blue-100 focus:bg-white focus:border-indigo-400 transition"></textarea>
              </div>

            </div>

            <!-- Footer Modal -->
            <div class="p-4 border-t bg-slate-50 flex justify-end gap-3 shrink-0">
              <button @click="cancelarEdicion" :disabled="cargandoAdmin"
                class="px-6 py-2.5 rounded-xl font-bold text-slate-600 hover:bg-slate-200 transition">
                Cancelar
              </button>
              <button @click="guardarPregunta" :disabled="cargandoAdmin"
                class="bg-green-600 hover:bg-green-700 text-white px-8 py-2.5 rounded-xl font-black shadow-lg transition flex items-center gap-2">
                <i v-if="cargandoAdmin" class="fa-solid fa-spinner fa-spin"></i>
                <i v-else class="fa-solid fa-floppy-disk"></i>
                Grabar Pregunta
              </button>
            </div>

          </div>
        </div>

        <!-- Modal Visor de PDF Integrado para Admin -->
        <div v-if="mostrarPdfAdmin"
          class="fixed inset-0 bg-slate-900/95 z-[60] flex flex-col backdrop-blur-md transition-all duration-300 animate-fade-in">
          <div class="flex justify-between items-center p-4 border-b border-white/10 shrink-0">
            <h3 class="text-white font-bold text-lg flex items-center gap-2">
              <i class="fa-solid fa-file-pdf text-red-500"></i> Documento de Referencia
            </h3>
            <button @click="mostrarPdfAdmin = false"
              class="bg-white/10 hover:bg-white/20 border border-white/10 text-white px-5 py-2.5 rounded-xl text-sm font-bold shadow-sm transition flex items-center gap-2">
              <i class="fa-solid fa-xmark"></i> Cerrar Visor
            </button>
          </div>
          <div class="flex-1 w-full relative bg-[#323639]">
            <iframe :src="`/referencias/${preguntaEditando.referencia}#page=${preguntaEditando.pagina || 1}`"
              class="w-full h-full border-0 shadow-inner bg-[#323639]" title="Visor PDF integrado"></iframe>
          </div>
        </div>

      </div>

    </div>

    <!-- Toast de Configuración Guardada -->
    <transition enter-active-class="transition ease-out duration-300 transform"
      enter-from-class="translate-y-10 opacity-0" enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition ease-in duration-200 transform" leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-10 opacity-0">
      <div v-if="mostrarToastConfig"
        class="fixed bottom-6 lg:bottom-10 right-1/2 translate-x-1/2 lg:translate-x-0 lg:right-10 bg-gray-900 border border-gray-700 text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-4 z-50 pointer-events-none">
        <div class="bg-green-500/20 p-2 rounded-full text-green-400 border border-green-500/30">
          <i class="fa-solid fa-check"></i>
        </div>
        <div>
          <h4 class="font-bold text-sm tracking-wide">Configuración Guardada</h4>
          <p class="text-xs text-gray-400 mt-0.5">Aplicará para los siguientes exámenes.</p>
        </div>
      </div>
    </transition>

  </div>

  <footer class="w-full mt-10 text-center pb-2 opacity-80 hover:opacity-100 transition-opacity relative group">
    <img src="https://terian.com.mx/wp-content/uploads/2025/03/cropped-Imagen11111111111-1-200x54.png"
      alt="Logo Terian I2D" class="h-10 mx-auto mb-3 object-contain" />
    <p class="text-xs md:text-sm text-slate-500 font-medium tracking-wide">
      Desarrollado en <span class="font-bold text-indigo-900">Terian I<sup>2</sup>D</span> &copy; {{ anioActual }}
    </p>
    <p class="text-[10px] text-slate-400 font-medium tracking-widest mt-0.5">
      INNOVACIÓN, INVESTIGACIÓN Y DESARROLLO
    </p>
    <button @click="abrirAdmin" class="absolute bottom-0 right-0 p-2 text-gray-300 hover:text-gray-500"><i
        class="fa-solid fa-lock text-xs"></i></button>
    <button id="devBypassAdmin" @click="bypassAdmin"
      class="absolute bottom-0 right-6 p-2 text-transparent hover:text-transparent w-2 h-2 opacity-0"></button>
  </footer>

</template>

<style>
@keyframes slide-up {
  from {
    transform: translateY(100%);
  }

  to {
    transform: translateY(0);
  }
}

.animate-slide-up {
  animation: slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: scale(0.95);
  }

  to {
    opacity: 1;
    transform: scale(1);
  }
}

.animate-fade-in {
  animation: fade-in 0.5s ease-out;
}

@keyframes bounce-slow {

  0%,
  100% {
    transform: translateY(-5%);
  }

  50% {
    transform: translateY(5%);
  }
}

.animate-bounce-slow {
  animation: bounce-slow 2s infinite ease-in-out;
}

/* Estilos para impresión */
@media print {

  /* RESET DE PÁGINA: Crucial para evitar las 300+ hojas en blanco */
  html,
  body {
    height: auto !important;
    overflow: visible !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  .no-print,
  footer,
  button,
  .sticky {
    display: none !important;
  }

  .min-h-screen,
  .flex-1,
  .max-w-4xl {
    display: block !important;
    height: auto !important;
    overflow: visible !important;
    max-width: 100% !important;
    width: 100% !important;
  }

  .study-content {
    background: white !important;
    padding: 0 !important;
    margin: 0 !important;
    height: auto !important;
    overflow: visible !important;
  }

  .page-block {
    page-break-inside: avoid !important;
    break-inside: avoid !important;
    margin-bottom: 2cm !important;
    border: 1px solid #eee !important;
    display: block !important;
  }
}
</style>