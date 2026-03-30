-- db/init.sql

-- 1. Áreas de conocimiento
CREATE TABLE areas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    color_hex VARCHAR(7)
);

INSERT INTO areas (nombre, color_hex) VALUES 
('Lenguajes', '#FF5733'), -- Naranja
('Saberes y Pensamiento Científico', '#33FF57'), -- Verde
('Ética, Naturaleza y Sociedad', '#3357FF'), -- Azul
('De lo Humano y lo Comunitario', '#F333FF'); -- Morado

-- 2. Contextos (Lecturas largas o Infografías de los PDFs)
CREATE TABLE contextos (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(200),
    contenido_texto TEXT, -- Para cuentos como "La liebre y la tortuga"
    imagen_url VARCHAR(255), -- Para etiquetas nutricionales o mapas
    tipo VARCHAR(50) DEFAULT 'texto' -- 'texto' o 'imagen'
);

-- 3. Reactivos (Preguntas)
CREATE TABLE reactivos (
    id SERIAL PRIMARY KEY,
    area_id INTEGER REFERENCES areas(id),
    contexto_id INTEGER REFERENCES contextos(id), -- NULL si es pregunta suelta
    identificador VARCHAR(50), -- ID único autogenerado (ej. LENG-001)
    lectura TEXT, -- Nuevo campo esperado por importar.py
    planteamiento TEXT NOT NULL, -- Soporta LaTeX: "Calcula $\frac{1}{2} + \frac{1}{4}$"
    referencia VARCHAR(255),
    pagina VARCHAR(50),
    imagen_url VARCHAR(255), -- Nuevo campo esperado por importar.py
    imagen_pregunta_url VARCHAR(255),
    retroalimentacion TEXT NOT NULL, -- Explicación para el niño
    dificultad INTEGER DEFAULT 1,
    reportado BOOLEAN DEFAULT FALSE,
    revisado BOOLEAN DEFAULT FALSE,
    revisado_por VARCHAR(150)
);

-- 4. Opciones de respuesta
CREATE TABLE opciones (
    id SERIAL PRIMARY KEY,
    reactivo_id INTEGER REFERENCES reactivos(id),
    texto_opcion TEXT NOT NULL,
    es_correcta BOOLEAN DEFAULT FALSE
);

-- 5. Resultados (Dashboard global)
CREATE TABLE resultados (
    id SERIAL PRIMARY KEY,
    nombre_estudiante VARCHAR(200),
    tipo_examen VARCHAR(100) DEFAULT 'Genérica', -- Nueva columna
    modalidad_test VARCHAR(100) DEFAULT 'Entrenamiento',
    calificacion_global INTEGER,
    fecha TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    detalles TEXT
);

-- 5.5 Usuarios Administradores
CREATE TABLE usuario (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    rol VARCHAR(50) NOT NULL
);

-- 6. Progreso (Preguntas que dominó el alumno)
CREATE TABLE progreso (
    id SERIAL PRIMARY KEY,
    nombre_estudiante_normalizado VARCHAR(200),
    reactivo_id INTEGER REFERENCES reactivos(id)
);
CREATE INDEX ix_progreso_nombre ON progreso(nombre_estudiante_normalizado);

-- 7. Configuración del Administrador
CREATE TABLE configuracion (
    id SERIAL PRIMARY KEY,
    entrenamiento_preguntas INTEGER DEFAULT 30,
    entrenamiento_minutos INTEGER DEFAULT 30,
    concentracion_preguntas INTEGER DEFAULT 45,
    concentracion_minutos INTEGER DEFAULT 30,
    maraton_preguntas INTEGER DEFAULT 100,
    maraton_minutos INTEGER DEFAULT 120,
    correo_supervisor TEXT DEFAULT '',
    filtro_referencia VARCHAR(255)
);
INSERT INTO configuracion (entrenamiento_preguntas, entrenamiento_minutos) VALUES (30, 30);

-- DATOS DE PRUEBA (Basado en tu PDF de Matemáticas)
-- Pregunta de fracciones
INSERT INTO reactivos (area_id, planteamiento, retroalimentacion) 
VALUES (2, '¿Cuánto es la suma de $\frac{1}{2} + \frac{1}{4}$?', 'Debes convertir 1/2 a cuartos (2/4) y sumar.');

INSERT INTO opciones (reactivo_id, texto_opcion, es_correcta) VALUES
((SELECT id FROM reactivos LIMIT 1), '$\frac{3}{4}$', TRUE),
((SELECT id FROM reactivos LIMIT 1), '$\frac{2}{4}$', FALSE),
((SELECT id FROM reactivos LIMIT 1), '$\frac{5}{4}$', FALSE);