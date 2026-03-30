<script setup>
import { defineProps, defineEmits, ref, watch, computed, onMounted, onUnmounted } from 'vue'
import katex from 'katex'
import axios from 'axios'
import iconosAreas from '../assets/iconos_areas.json'

const props = defineProps({
  pregunta: Object,
  pregunta: Object,
  numero: Number
})

const emit = defineEmits(['responder', 'pregunta-reportada'])

const mostrarLectura = ref(false)
const mostrarModalReferencia = ref(false)
const mostrarEsquema = ref(false)
const mostrarPdf = ref(false)
const opcionSeleccionadaId = ref(null)
const respondido = ref(false)
const reportando = ref(false)
const reporteExitoso = ref(false)

watch(() => props.pregunta, () => {
  mostrarLectura.value = false
  mostrarModalReferencia.value = false
  mostrarEsquema.value = false
  mostrarPdf.value = false
  opcionSeleccionadaId.value = null
  respondido.value = false
  reportando.value = false
  reporteExitoso.value = false
})

const renderizarTexto = (texto) => {
  if (!texto) return ''
  return texto.replace(/\$(.*?)\$/g, (match, formula) => {
    try {
      return katex.renderToString(formula, { throwOnError: false, displayMode: false })
    } catch (e) { return match }
  })
}

const seleccionar = (opcion) => {
  if (respondido.value) return
  opcionSeleccionadaId.value = opcion.id
  respondido.value = true
  emit('responder', opcion)
}

const esLecturaRelacion = computed(() => {
  if (!props.pregunta?.planteamiento || !props.pregunta?.lectura) return false;
  return props.pregunta.planteamiento.toLowerCase().includes('relaciona');
})

const tablasLectura = computed(() => {
  if (!esLecturaRelacion.value || !props.pregunta?.lectura) return [];
  
  // Dividir por saltos de línea o etiquetas html como <br>
  const bloques = props.pregunta.lectura.split(/\n|<br\s*\/?>/i);
  const resultados = [];
  
  bloques.forEach((bloque, idx) => {
    if (!bloque.trim()) return;
    
    // Buscar si tiene título (ej. "Funciones: A. Fática...")
    const partes = bloque.split(':');
    let titulo = bloques.length > 1 ? `Columna ${idx + 1}` : "Conceptos";
    let contenido = bloque.trim();
    
    // Validar que la primera parte antes de los ":" parezca un título y no una definición
    if (partes.length > 1 && partes[0].length < 30 && !partes[0].includes('.')) {
      titulo = partes[0].trim();
      contenido = partes.slice(1).join(':').trim();
    }
    
    // Expresión regular mejorada para partir por cualquier lista enumerada:
    // Busca espacios/comas seguidos estrictamente de 1 letra, 1-2 números o 1-4 letras romanas + Punto + Espacio
    const regex = /(?:^|\s+|,\s*|;\s*)([A-Z]\.|[a-z]\.|[0-9]{1,2}\.|[XIVxiv]{1,4}\.)\s+/;
    let partsSplit = contenido.split(regex);
    
    const items = [];
    for (let i = 1; i < partsSplit.length; i += 2) {
       // Eliminar comas o signos de puntuación sueltos al final de la definición
       const textoLimpio = partsSplit[i+1].trim().replace(/[,;]$/, '').trim();
       items.push({ inciso: partsSplit[i], texto: textoLimpio });
    }
    
    // Respaldo de seguridad en caso de que la limpieza falle
    if (items.length === 0) {
       items.push({ inciso: "", texto: contenido });
    }

    resultados.push({ titulo, items });
  });
  
  return resultados;
})

const reportarPregunta = async () => {
  if (reportando.value || reporteExitoso.value) return
  
  reportando.value = true
  try {
    await axios.post('/api/reportar-pregunta', { reactivo_id: props.pregunta.id })
    reporteExitoso.value = true
    emit('pregunta-reportada', props.pregunta.id)
    alert("¡Reporte enviado exitosamente al administrador!")
    mostrarModalReferencia.value = false
  } catch (e) {
    alert("Error al enviar el reporte. Por favor intenta más tarde.")
    reportando.value = false
  }
}

const obtenerEstiloArea = (nombreArea) => {
  if (!nombreArea) return { header: 'bg-indigo-600', border: 'border-indigo-100' }
  const area = nombreArea.toLowerCase()
  if (area.includes('lenguajes')) return { header: 'bg-purple-600', border: 'border-purple-100' }
  if (area.includes('saberes') || area.includes('científico')) return { header: 'bg-orange-500', border: 'border-orange-100' }
  if (area.includes('ética') || area.includes('naturaleza')) return { header: 'bg-pink-600', border: 'border-pink-100' }
  if (area.includes('humano')) return { header: 'bg-teal-600', border: 'border-teal-100' }
  return { header: 'bg-indigo-600', border: 'border-indigo-100' }
}

const obtenerIconoArea = (nombreArea) => {
  if (!nombreArea) return 'fa-solid fa-cube'
  // Buscar coincidencia exacta o que contenga el nombre
  for (const [key, icono] of Object.entries(iconosAreas)) {
    if (nombreArea.toLowerCase().includes(key.toLowerCase())) {
      return icono
    }
  }
  return 'fa-solid fa-cube'
}



const obtenerClaseOpcion = (opcion) => {
  if (!respondido.value) return `border-gray-200 dark:border-slate-700/50 hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-indigo-50/50 dark:hover:bg-slate-700 cursor-pointer`
  
  if (opcion.id === opcionSeleccionadaId.value) {
    return opcion.es_correcta
      ? 'border-green-500 bg-green-600 text-white shadow-md ring-2 ring-green-500/50'
      : 'border-red-500 bg-red-600 text-white shadow-md ring-2 ring-red-500/50'
  }
  
  if (opcionSeleccionadaId.value !== null && !props.pregunta.opciones.find(o => o.id === opcionSeleccionadaId.value).es_correcta) {
    if (opcion.es_correcta) return 'border-green-500 bg-green-100 dark:bg-green-950/30 text-green-700 dark:text-green-400 animate-parpadeo shadow-lg'
  }
  
  return 'border-gray-200 dark:border-slate-700/50 opacity-50'
}
// Detectar dark mode reactivo
const isDark = ref(document.documentElement.classList.contains('dark'))
let darkObserver = null
onMounted(() => {
  darkObserver = new MutationObserver(() => {
    isDark.value = document.documentElement.classList.contains('dark')
  })
  darkObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
})
onUnmounted(() => darkObserver?.disconnect())
</script>

<template>
  <div
    class="bg-white dark:bg-slate-800 rounded-2xl shadow-xl overflow-hidden w-full border-2 md:border-4 flex flex-col transition-colors duration-500 dark:border-slate-700/50"
    :class="obtenerEstiloArea(pregunta.area).border">

    <div class="px-3 py-2 text-white flex justify-between items-center shadow-md z-10 transition-colors duration-500"
      :class="obtenerEstiloArea(pregunta.area).header">
      <div class="flex items-center gap-1.5 md:gap-2 overflow-hidden">
        <span class="font-black text-xs md:text-base tracking-wide uppercase truncate max-w-[120px] md:max-w-none">
          <i :class="[obtenerIconoArea(pregunta.area), 'mr-1 md:mr-1.5']"></i> {{ pregunta.area || 'Pregunta' }}
        </span>

        <div v-if="pregunta.ya_respondida_bien"
          class="flex items-center gap-1 bg-yellow-400 text-yellow-900 px-1.5 md:px-2 py-0.5 rounded-full text-[9px] md:text-xs font-black shadow-sm animate-pulse flex-shrink-0">
          <i class="fa-solid fa-star"></i> <span class="hidden sm:inline">Dominada</span>
        </div>

        <div v-if="pregunta.revisado"
          class="flex items-center gap-1 bg-green-500 text-white px-1.5 md:px-2 py-0.5 rounded-full text-[9px] md:text-xs font-black shadow-sm flex-shrink-0"
          title="Esta pregunta ha sido verificada por un supervisor.">
          <i class="fa-solid fa-file-circle-check"></i> <span class="hidden sm:inline">Revisada</span>
        </div>
      </div>

      <button 
        @click="mostrarModalReferencia = true"
        class="bg-white/20 hover:bg-white/30 px-2 md:px-2.5 py-1 rounded-full text-[10px] md:text-xs font-bold whitespace-nowrap ml-1 md:ml-2 transition-colors flex items-center gap-1 md:gap-1.5 cursor-pointer flex-shrink-0" 
        title="Ver origen de la pregunta">
        <i v-if="reportando" class="fa-solid fa-spinner fa-spin"></i>
        <i v-else-if="reporteExitoso" class="fa-solid fa-check text-green-300"></i>
        <i v-else class="fa-solid fa-flag text-white/70 hover:text-white"></i>
        <span class="hidden xs:inline">{{ pregunta.identificador || 'ID-ND' }}</span> (#{{ numero }})
      </button>
    </div>

    <div class="p-3 md:p-5 flex-grow flex flex-col pt-2 md:pt-3">
      <div v-if="pregunta.lectura" class="mb-3">
        <button @click="mostrarLectura = !mostrarLectura"
          class="w-full bg-amber-100 dark:bg-amber-900/30 hover:bg-amber-200 dark:hover:bg-amber-800/40 text-amber-900 dark:text-amber-200 border border-amber-300 dark:border-amber-700/50 font-bold py-1.5 px-3 rounded-xl flex items-center justify-between transition-colors shadow-sm text-xs md:text-sm">
          <span class="flex items-center gap-2">
            <i class="fa-solid fa-book-open"></i>
            {{ mostrarLectura ? 'Ocultar Lectura/Datos Extra' : 'Ver Lectura/Datos Extra' }}
          </span>
          <i :class="['fa-solid', mostrarLectura ? 'fa-chevron-up' : 'fa-chevron-down']"></i>
        </button>
        <div v-if="mostrarLectura"
          class="mt-2 text-justify text-gray-800 dark:text-gray-200 leading-relaxed font-serif animate-fade-in text-sm"
          :class="esLecturaRelacion ? '' : 'bg-amber-50 dark:bg-slate-900/50 p-3 rounded-xl border border-amber-200 dark:border-slate-700 max-h-48 overflow-y-auto'">
          
          <!-- Si NO es de relación, se muestra texto corrido normal -->
          <div v-if="!esLecturaRelacion" v-html="renderizarTexto(pregunta.lectura)"></div>
          
          <!-- Si ES de relación, renderizar tablas dinámicas -->
          <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
             <div v-for="(tabla, idx) in tablasLectura" :key="idx" class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden shadow-sm flex flex-col">
                <div class="bg-indigo-50 dark:bg-indigo-900/40 border-b-2 border-indigo-100 dark:border-indigo-800 p-2 text-center shrink-0">
                  <h4 class="font-bold text-indigo-900 dark:text-indigo-300 capitalize text-sm">{{ tabla.titulo }}</h4>
                </div>
                <ul class="divide-y divide-slate-100 dark:divide-slate-700 overflow-y-auto">
                  <li v-for="(item, i) in tabla.items" :key="'i'+i" class="p-2 md:p-2.5 flex gap-2 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition items-start">
                     <span v-if="item.inciso" class="font-black text-indigo-700 dark:text-indigo-400 whitespace-nowrap text-sm">{{ item.inciso }}</span>
                     <span class="text-slate-700 dark:text-gray-300 text-[11px] md:text-sm leading-tight">{{ item.texto }}</span>
                  </li>
                </ul>
             </div>
          </div>
          
        </div>
      </div>

      <div class="mb-3 relative w-full overflow-x-auto overflow-y-hidden custom-scrollbar">
        <!-- Render Planteamiento -->
        <div class="text-base md:text-xl font-bold text-gray-800 dark:text-white leading-snug math-content text-justify transition-colors break-words min-w-0"
          v-html="renderizarTexto(pregunta.planteamiento)"></div>
          
        <!-- Botón Ver Esquema (solo si hay imagen) -->
        <div v-if="pregunta.imagen_url" class="mt-3 flex justify-center">
            <button @click="mostrarEsquema = true" class="bg-indigo-50 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-800/60 border border-indigo-200 dark:border-indigo-700 font-bold py-1.5 px-4 rounded-xl flex items-center gap-2 transition-colors shadow-sm text-sm">
                <i class="fa-solid fa-image"></i> Ver Esquema de Apoyo
            </button>
        </div>
      </div>

      <div class="grid gap-2 w-full">
        <div v-for="(opcion, index) in pregunta.opciones" :key="opcion.id" @click="seleccionar(opcion)"
          class="option-row relative w-full px-3 py-2.5 md:p-3 rounded-xl border-2 transition-all duration-300 group flex items-center shadow-sm select-none"
          :style="isDark ? 'background-color: rgb(51 65 85 / 0.55)' : ''"
          :class="obtenerClaseOpcion(opcion)">

          <div
            class="flex-shrink-0 w-8 h-8 md:w-9 md:h-9 rounded-full flex items-center justify-center font-black text-sm md:text-base mr-3 md:mr-4 transition-colors border-2"
            style="font-family: Arial, sans-serif !important;"
            :style="!respondido && isDark ? 'background-color:#4f46e5; border-color:#818cf8; color:#fff;' : ''"
            :class="{
              'bg-green-500 text-white border-green-600': respondido && (opcion.id === opcionSeleccionadaId && opcion.es_correcta),
              'bg-red-500 text-white border-red-600': respondido && (opcion.id === opcionSeleccionadaId && !opcion.es_correcta),
              'option-circle bg-amber-400 border-amber-300 text-white': !respondido
            }">
            {{ String.fromCharCode(64 + index + 1) }}
          </div>

          <div class="text-sm md:text-base font-bold math-content transition-colors break-words overflow-x-auto custom-scrollbar flex-grow min-w-0"
            v-html="renderizarTexto(opcion.texto_opcion)"></div>

          <div v-if="respondido && opcion.id === opcionSeleccionadaId" class="absolute right-3 text-xl md:text-2xl text-white">
            <i :class="opcion.es_correcta ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-xmark'"></i>
          </div>
          <div
            v-if="respondido && !opcion.es_correcta && opcionSeleccionadaId !== null && !pregunta.opciones.find(o => o.id === opcionSeleccionadaId).es_correcta && opcion.es_correcta"
            class="absolute right-3 text-xl md:text-2xl animate-bounce text-green-600 dark:text-green-400">
            <i class="fa-solid fa-hand-point-left"></i>
          </div>
        </div>
      </div>
    </div>
  </div>
    <!-- Modal de Referencia y Reporte -->
    <div v-if="mostrarModalReferencia" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div class="bg-white dark:bg-slate-800 rounded-2xl w-full max-w-md shadow-2xl p-6 transition-colors duration-300 border dark:border-slate-700">
        <div class="flex justify-between items-start mb-4">
          <h3 class="text-xl font-bold text-gray-800 dark:text-white transition-colors">
            <i class="fa-solid fa-book text-indigo-500 mr-2"></i> Origen de la pregunta
          </h3>
          <button @click="mostrarModalReferencia = false" class="text-gray-400 hover:text-gray-600 dark:text-slate-500 dark:hover:text-slate-300 transition-colors">
            <i class="fa-solid fa-times text-xl"></i>
          </button>
        </div>
        
        <div class="bg-indigo-50 dark:bg-indigo-900/30 p-4 rounded-xl border border-indigo-100 dark:border-indigo-800/50 mb-6 transition-colors">
          <div class="mb-2 w-full overflow-hidden">
            <span class="text-xs font-bold text-indigo-400 uppercase tracking-wider">Referencia del libro</span>
            <p class="text-gray-800 dark:text-gray-200 font-medium mt-1 break-all transition-colors">{{ pregunta.referencia || 'No disponible' }}</p>
          </div>
          <div>
            <span class="text-xs font-bold text-indigo-400 uppercase tracking-wider">Página</span>
            <p class="text-gray-800 dark:text-gray-200 font-medium mt-1 transition-colors">{{ pregunta.pagina || 'No disponible' }}</p>
          </div>
          <div v-if="pregunta.referencia" class="mt-4">
            <button @click="mostrarPdf = true; mostrarModalReferencia = false"
               class="inline-flex items-center justify-center w-full py-2.5 rounded-xl font-bold bg-indigo-600 hover:bg-indigo-700 text-white transition-colors shadow-sm gap-2">
              <i class="fa-regular fa-file-pdf"></i>
              Abrir PDF de referencia
            </button>
          </div>
        </div>

        <div class="border-t dark:border-slate-700 pt-4 transition-colors">
          <p class="text-sm text-gray-500 dark:text-gray-400 mb-3 transition-colors">
            Si consideras que hay un error en esta pregunta (en la respuesta o planteamiento), puedes reportarla para revisión manual.
          </p>
          <div class="flex flex-col gap-2">
            <button 
              @click="reportarPregunta"
              :disabled="reportando || reporteExitoso"
              class="w-full py-2.5 rounded-xl font-bold transition-colors flex items-center justify-center gap-2 shadow-sm"
              :class="reporteExitoso ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400' : 'bg-red-100 dark:bg-red-900/30 hover:bg-red-200 dark:hover:bg-red-800/50 text-red-700 dark:text-red-400'">
              <i v-if="reportando" class="fa-solid fa-spinner fa-spin"></i>
              <i v-else-if="reporteExitoso" class="fa-solid fa-check"></i>
              <i v-else class="fa-solid fa-flag"></i>
              {{ reporteExitoso ? 'Reporte enviado exitosamente' : 'Reportar error al supervisor' }}
            </button>
            <button 
              @click="mostrarModalReferencia = false"
              class="w-full py-2.5 rounded-xl font-bold bg-gray-100 hover:bg-gray-200 text-gray-700 dark:bg-slate-700 dark:hover:bg-slate-600 dark:text-gray-200 transition-colors shadow-sm">
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Modal de Esquema de Apoyo (Imagen) -->
    <div v-if="mostrarEsquema && pregunta.imagen_url" class="fixed inset-0 bg-slate-900/80 z-50 flex items-center justify-center p-4 backdrop-blur-sm">
      <div class="bg-white rounded-3xl w-full max-w-3xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        
        <div class="p-4 border-b bg-slate-50 flex justify-between items-center shrink-0">
          <h3 class="text-xl font-bold text-slate-800 flex items-center gap-2">
            <i class="fa-solid fa-image text-indigo-500"></i> Esquema de Apoyo
          </h3>
          <button @click="mostrarEsquema = false" class="bg-white border text-gray-500 hover:text-gray-800 px-3 py-1.5 rounded-lg text-sm font-bold shadow-sm transition">
            <i class="fa-solid fa-times mr-1"></i> Cerrar
          </button>
        </div>
        
        <div class="p-4 flex-1 overflow-auto flex items-center justify-center bg-slate-100">
           <!-- Renderizamos la imagen con un max-height y max-width para que se adapte sin romper el modal -->
           <img :src="pregunta.imagen_url" alt="Esquema para la pregunta" class="max-w-full max-h-[70vh] object-contain rounded-xl shadow-md border-2 border-white">
        </div>
        
      </div>
    </div>

    <!-- Modal Visor de PDF Integrado -->
    <div v-if="mostrarPdf" class="fixed inset-0 bg-slate-900/95 z-[60] flex flex-col backdrop-blur-md transition-all duration-300 animate-fade-in">
      
      <!-- Cabecera del Visor Modal -->
      <div class="p-4 border-b border-white/10 bg-slate-900 flex justify-between items-center shrink-0 shadow-lg">
        <div>
          <h3 class="text-xl md:text-2xl font-black text-white flex items-center gap-3">
            <i class="fa-solid fa-file-pdf text-red-500"></i> Documento de Referencia
          </h3>
          <p class="text-slate-400 text-sm mt-1 font-medium hidden md:block">
            Libro: {{ pregunta.referencia }} &bull; Pág. {{ pregunta.pagina || '1' }}
          </p>
        </div>
        <div class="flex items-center gap-2">
          <a :href="`/referencias/${pregunta.referencia}#page=${pregunta.pagina || 1}`" target="_blank" class="bg-indigo-600 hover:bg-indigo-700 border border-indigo-500 text-white px-4 py-2.5 rounded-xl text-sm font-bold shadow-sm transition flex items-center gap-2">
            <i class="fa-solid fa-arrow-up-right-from-square"></i> <span class="hidden md:inline">Abrir en pestaña</span>
          </a>
          <button @click="mostrarPdf = false" class="bg-white/10 hover:bg-white/20 border border-white/10 text-white px-5 py-2.5 rounded-xl text-sm font-bold shadow-sm transition flex items-center gap-2">
            <i class="fa-solid fa-arrow-left"></i> <span class="hidden md:inline">Cerrar Visor</span>
          </button>
        </div>
      </div>

      <!-- Iframe Contenedor del PDF -->
      <div class="flex-1 w-full bg-[#323639] relative flex items-center justify-center">
         <iframe :src="`/referencias/${pregunta.referencia}#page=${pregunta.pagina || 1}`" class="w-full h-full border-0 shadow-inner bg-[#323639]" title="Visor PDF integrado"></iframe>
      </div>

    </div>

</template>

<style>
@keyframes parpadeo-borde {
  0%,
  100% {
    border-color: #22c55e;
    background-color: #dcfce7;
    transform: scale(1);
  }

  50% {
    border-color: #15803d;
    background-color: #bbf7d0;
    transform: scale(1.02);
  }
}

.animate-parpadeo {
  animation: parpadeo-borde 1.5s infinite ease-in-out;
}

/* Dark mode: fondo de cada opcion ligeramente mas claro que la tarjeta */
.dark .option-row {
  background-color: rgb(51 65 85 / 0.5); /* slate-700/50 */
}

/* Dark mode: circulo de la letra con color de enfasis indigo */
.dark .option-circle {
  background-color: #4f46e5; /* indigo-600 */
  border-color: #818cf8;     /* indigo-400 */
  color: white;
}
</style>