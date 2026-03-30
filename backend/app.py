import os
import random
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql.expression import func
import os

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://oci_user:oci_password@db:5432/oci_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    correo = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Area(db.Model):
    __tablename__ = 'areas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    color_hex = db.Column(db.String(7))

class Reactivo(db.Model):
    __tablename__ = 'reactivos'
    id = db.Column(db.Integer, primary_key=True)
    identificador = db.Column(db.String(50), nullable=True)
    area_id = db.Column(db.Integer, db.ForeignKey('areas.id'))
    lectura = db.Column(db.Text, nullable=True)
    planteamiento = db.Column(db.Text)
    referencia = db.Column(db.String(255), nullable=True)
    pagina = db.Column(db.String(50), nullable=True)
    imagen_url = db.Column(db.String(255), nullable=True)
    retroalimentacion = db.Column(db.Text)
    reportado = db.Column(db.Boolean, default=False)
    revisado = db.Column(db.Boolean, default=False)
    revisado_por = db.Column(db.String(150), nullable=True)
    area = db.relationship('Area')
    opciones = db.relationship('Opcion', backref='reactivo', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'identificador': self.identificador,
            'area': self.area.nombre if self.area else 'General',
            'lectura': self.lectura,
            'planteamiento': self.planteamiento,
            'referencia': self.referencia,
            'pagina': self.pagina,
            'imagen_url': self.imagen_url,
            'retroalimentacion': self.retroalimentacion,
            'reportado': self.reportado,
            'revisado': self.revisado,
            'revisado_por': self.revisado_por,
            'opciones': [op.to_dict() for op in self.opciones]
        }

class Opcion(db.Model):
    __tablename__ = 'opciones'
    id = db.Column(db.Integer, primary_key=True)
    reactivo_id = db.Column(db.Integer, db.ForeignKey('reactivos.id'))
    texto_opcion = db.Column(db.Text)
    es_correcta = db.Column(db.Boolean)

    def to_dict(self):
        return {'id': self.id, 'texto_opcion': self.texto_opcion, 'es_correcta': self.es_correcta}

class Resultado(db.Model):
    __tablename__ = 'resultados'
    id = db.Column(db.Integer, primary_key=True)
    nombre_estudiante = db.Column(db.String(200))
    tipo_examen = db.Column(db.String(100), default='Genérica')
    modalidad_test = db.Column(db.String(100), default='Entrenamiento') # Entrenamiento, Concentración, Maratón
    calificacion_global = db.Column(db.Integer)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    detalles = db.Column(db.Text)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre_estudiante,
            'tipo_examen': self.tipo_examen,
            'modalidad_test': self.modalidad_test,
            'calificacion': self.calificacion_global,
            'fecha': self.fecha.strftime("%d/%m/%Y %H:%M"),
            'detalles': json.loads(self.detalles) if self.detalles else {}
        }

# --- NUEVA TABLA: PROGRESO ---
# Guarda qué preguntas ha contestado bien un alumno específico
class Progreso(db.Model):
    __tablename__ = 'progreso'
    id = db.Column(db.Integer, primary_key=True)
    nombre_estudiante_normalizado = db.Column(db.String(200), index=True) # nombre+apellido en minusculas
    reactivo_id = db.Column(db.Integer, db.ForeignKey('reactivos.id'))

# --- NUEVA TABLA: CONFIGURACION ---
class Configuracion(db.Model):
    __tablename__ = 'configuracion'
    id = db.Column(db.Integer, primary_key=True)
    entrenamiento_preguntas = db.Column(db.Integer, default=30)
    entrenamiento_minutos = db.Column(db.Integer, default=30)
    concentracion_preguntas = db.Column(db.Integer, default=45)
    concentracion_minutos = db.Column(db.Integer, default=30)
    maraton_preguntas = db.Column(db.Integer, default=100)
    maraton_minutos = db.Column(db.Integer, default=120)
    correo_supervisor = db.Column(db.Text, default='')
    filtro_referencia = db.Column(db.String(20), default='con_referencia')

    def to_dict(self):
        return {
            'entrenamiento_preguntas': self.entrenamiento_preguntas,
            'entrenamiento_minutos': self.entrenamiento_minutos,
            'concentracion_preguntas': self.concentracion_preguntas,
            'concentracion_minutos': self.concentracion_minutos,
            'maraton_preguntas': self.maraton_preguntas,
            'maraton_minutos': self.maraton_minutos,
            'correo_supervisor': self.correo_supervisor or '',
            'filtro_referencia': self.filtro_referencia or 'con_referencia'
        }

# --- RUTAS ---
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    correo = data.get('correo')
    password = data.get('password')
    
    if not correo or not password:
        return jsonify({"error": "Faltan credenciales"}), 400
        
    usuario = Usuario.query.filter_by(correo=correo).first()
    if usuario and usuario.check_password(password):
        return jsonify({"mensaje": "Login exitoso", "usuario": {"correo": usuario.correo}}), 200
    
    return jsonify({"error": "Credenciales inválidas"}), 401

@app.route('/uploads/<name>')
def download_file(name):
    return send_from_directory(app.config['UPLOAD_FOLDER'], name)

@app.route('/')
def home():
    return jsonify({"mensaje": "API OCI Online 🤖"})

@app.route('/generar-examen')
def generar_examen():
    # Recibimos quién es el alumno y qué área quiere
    nombre = request.args.get('nombre', '').strip().lower()
    apellido = request.args.get('apellido', '').strip().lower()
    area_solicitada = request.args.get('area', 'Genérica').strip()
    tipo_test = request.args.get('tipo_test', 'Entrenamiento').strip() # Entrenamiento, Concentración, Maratón
    usuario_id = f"{nombre} {apellido}"
    
    # Configuraciones
    conf = Configuracion.query.first()
    
    if tipo_test == 'Entrenamiento':
        limite_preguntas = conf.entrenamiento_preguntas if conf else 30
    elif tipo_test == 'Concentración':
        limite_preguntas = conf.concentracion_preguntas if conf else 45
    elif tipo_test == 'Maratón':
        limite_preguntas = conf.maraton_preguntas if conf else 100
    else:
        limite_preguntas = 15

    # Obtenemos los IDs de preguntas que YA dominó
    ids_dominados = []
    if nombre and apellido:
        registros = Progreso.query.filter_by(nombre_estudiante_normalizado=usuario_id).all()
        ids_dominados = [r.reactivo_id for r in registros]

    if area_solicitada != 'Genérica':
        nombres_areas = [area_solicitada]
    else:
        nombres_areas = ["Lenguajes", "Saberes y Pensamiento Científico", "Ética, Naturaleza y Sociedad", "De lo Humano y lo Comunitario"]
    
    todas_areas_nuevas = []
    todas_areas_vistas = []
    
    for nombre_area in nombres_areas:
        area_obj = Area.query.filter(Area.nombre.ilike(f"%{nombre_area}%")).first()
        if area_obj:
            query = Reactivo.query.filter_by(area_id=area_obj.id)
            
            # Aplicar filtro de referencia según la configuración e ignorar preguntas reportadas
            filtro = conf.filtro_referencia if conf else 'con_referencia'
            if filtro == 'con_referencia':
                query = query.filter(Reactivo.referencia.isnot(None), Reactivo.referencia != '', Reactivo.reportado == False)
            elif filtro == 'sin_referencia':
                query = query.filter((Reactivo.referencia.is_(None)) | (Reactivo.referencia == ''), Reactivo.reportado == False)
            else:
                query = query.filter(Reactivo.reportado == False)

            # 1. Obtener TODAS las preguntas filtradas del área
            todas_preguntas = query.all()
            
            # 2. Separar en Nuevas y Vistas
            preguntas_nuevas = [p for p in todas_preguntas if p.id not in ids_dominados]
            preguntas_vistas = [p for p in todas_preguntas if p.id in ids_dominados]
            
            random.shuffle(preguntas_nuevas)
            random.shuffle(preguntas_vistas)
            
            todas_areas_nuevas.append(preguntas_nuevas)
            todas_areas_vistas.append(preguntas_vistas)

    seleccion = []
    
    # Lógica de round-robin para asegurar distribución y cubrir exactamente el límite
    while len(seleccion) < limite_preguntas:
        added_in_round = False
        for i in range(len(todas_areas_nuevas)):
            if len(seleccion) >= limite_preguntas:
                break
            if todas_areas_nuevas[i]:
                seleccion.append(todas_areas_nuevas[i].pop(0))
                added_in_round = True
            elif todas_areas_vistas[i]:
                seleccion.append(todas_areas_vistas[i].pop(0))
                added_in_round = True
        
        if not added_in_round:
            # Nos quedamos sin preguntas en todas las áreas solicitadas que cumplan el filtro
            break
            
    # Formatear y marcar
    examen_completo = []
    for p in seleccion:
        d = p.to_dict()
        # Bandera para el Frontend: ¿Ya la dominó antes?
        d['ya_respondida_bien'] = (p.id in ids_dominados)
        random.shuffle(d['opciones'])
        examen_completo.append(d)
        
    random.shuffle(examen_completo)
    examen_completo = examen_completo[:limite_preguntas]
    
    if not examen_completo:
        return jsonify({"error": "No hay suficientes preguntas"}), 404
        
    return jsonify(examen_completo)

@app.route('/pregunta-reemplazo', methods=['POST'])
def obtener_pregunta_reemplazo():
    data = request.json
    area_nombre = data.get('area', 'Genérica')
    excluir_ids = data.get('excluir_ids', [])
    
    conf = Configuracion.query.first()
    filtro = conf.filtro_referencia if conf else 'con_referencia'
    
    query = Reactivo.query
    if area_nombre != 'Genérica':
        area_obj = Area.query.filter(Area.nombre.ilike(f"%{area_nombre}%")).first()
        if area_obj:
            query = query.filter_by(area_id=area_obj.id)
            
    if filtro == 'con_referencia':
        query = query.filter(Reactivo.referencia.isnot(None), Reactivo.referencia != '', Reactivo.reportado == False)
    elif filtro == 'sin_referencia':
        query = query.filter((Reactivo.referencia.is_(None)) | (Reactivo.referencia == ''), Reactivo.reportado == False)
    else:
        query = query.filter(Reactivo.reportado == False)
        
    if excluir_ids:
        query = query.filter(~Reactivo.id.in_(excluir_ids))
        
    preguntas_disponibles = query.all()
    if not preguntas_disponibles:
        # Intenta sin importar el modulo
        query_fallback = Reactivo.query.filter(~Reactivo.id.in_(excluir_ids), Reactivo.reportado == False)
        preguntas_disponibles = query_fallback.all()
        if not preguntas_disponibles:
             return jsonify({"error": "No hay mas preguntas"}), 404
        
    seleccionada = random.choice(preguntas_disponibles)
    d = seleccionada.to_dict()
    d['ya_respondida_bien'] = False
    random.shuffle(d['opciones'])
    
    return jsonify(d), 200

@app.route('/guardar-resultado', methods=['POST'])
def guardar_resultado():
    data = request.json
    nombre_completo = f"{data['nombre']} {data['apellido']}"
    usuario_norm = nombre_completo.strip().lower()
    tipo_examen = data.get('area', 'Genérica')
    modalidad_test = data.get('modalidad_test', 'Entrenamiento') # Nuevo campo
    veces_tiempo_extra = data.get('veces_tiempo_extra', 0)
    tiempo_total_empleado = data.get('tiempo_total_empleado', 0)
    
    detalles_guardar = data.get('puntajes', {})
    detalles_guardar['metricas_extra'] = {
        'veces_tiempo_extra': veces_tiempo_extra,
        'tiempo_total_empleado': tiempo_total_empleado
    }
    
    # 1. Guardar Resultado General (Dashboard)
    nuevo_resultado = Resultado(
        nombre_estudiante=nombre_completo,
        tipo_examen=tipo_examen,
        modalidad_test=modalidad_test,
        calificacion_global=data['calificacion'],
        detalles=json.dumps(detalles_guardar)
    )
    db.session.add(nuevo_resultado)
    
    # Notificar al supervisor
    try:
        conf = Configuracion.query.first()
        if conf and conf.correo_supervisor:
            asunto = f"OCI / Nuevo Resultado de Examen: {nombre_completo}"
            
            html_puntajes = "<ul>"
            for area_nombre, datos_area in data['puntajes'].items():
                html_puntajes += f"<li><strong>{area_nombre}</strong>: {datos_area['correctas']} / {datos_area['total']} correctas ({datos_area['incorrectas']} incorrectas)</li>"
            html_puntajes += "</ul>"
            
            minutos = tiempo_total_empleado // 60
            segundos = tiempo_total_empleado % 60
            tiempo_str = f"{minutos}m {segundos}s"
            
            html_correo = f"""
            <html>
              <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #4f46e5;">Nuevo Resultado de Examen</h2>
                <p>El alumno ha completado un examen en el simulador OCI.</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9; width: 150px;"><strong>Alumno:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{nombre_completo}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Área:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{tipo_examen}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Modalidad:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{modalidad_test}</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Calificación Global:</strong></td><td style="padding: 10px; border: 1px solid #ccc; font-weight: bold; font-size: 1.2em;">{data['calificacion']}%</td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Tiempo Empleado:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{tiempo_str} <span style="color: #666; font-size: 0.9em;">(Solicitó tiempo: {veces_tiempo_extra} veces)</span></td></tr>
                    <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Desglose por Área:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{html_puntajes}</td></tr>
                </table>
              </body>
            </html>
            """
            enviar_correo_helper(asunto, html_correo, conf.correo_supervisor)
    except Exception as e:
        print(f"Error procesando correo del supervisor: {e}")

    # 2. Guardar Progreso (Las preguntas que tuvo bien)
    ids_correctos = data.get('ids_correctos', [])
    
    # Para no duplicar filas, verificamos antes de insertar
    # (Esto podría optimizarse, pero para <100 preguntas está bien)
    existing = {p.reactivo_id for p in Progreso.query.filter_by(nombre_estudiante_normalizado=usuario_norm).all()}
    
    for rid in ids_correctos:
        if rid not in existing:
            nuevo_progreso = Progreso(nombre_estudiante_normalizado=usuario_norm, reactivo_id=rid)
            db.session.add(nuevo_progreso)
            
    db.session.commit()
    return jsonify({"mensaje": "Guardado y progreso actualizado"}), 201

@app.route('/resultados', methods=['GET'])
def obtener_resultados():
    resultados = Resultado.query.order_by(Resultado.fecha.desc()).all()
    return jsonify([r.to_dict() for r in resultados])

@app.route('/admin/rendimiento/<string:estudiante>', methods=['GET'])
def obtener_rendimiento_estudiante(estudiante):
    estudiante_norm = estudiante.strip().lower()
    
    # 1. Buscar todos los exámenes que coincidan (insensible a mayúsculas)
    resultados = Resultado.query.filter(
        db.func.lower(Resultado.nombre_estudiante).like(f"%{estudiante_norm}%")
    ).order_by(Resultado.fecha.desc()).all()

    if not resultados:
        return jsonify({"error": "No hay historial para este estudiante."}), 404

    total_examenes = len(resultados)
    suma_calificaciones = sum(r.calificacion_global for r in resultados)
    promedio_global = round(suma_calificaciones / total_examenes, 1) if total_examenes > 0 else 0

    # 2. Extraer tiempos y calificaciones por área
    tiempo_extra_historico = 0
    areas_sumatoria = {}
    areas_conteo = {}
    
    for r in resultados:
        if r.detalles:
            try:
                det = json.loads(r.detalles)
                if 'metricas_extra' in det:
                    tiempo_extra_historico += det['metricas_extra'].get('veces_tiempo_extra', 0)
                
                # Iterar las llaves que no son metricas (áreas)
                for llave, data in det.items():
                    if llave == 'metricas_extra': continue
                    
                    if data['total'] > 0:
                        porcentaje_area = (data['correctas'] / data['total']) * 100
                        
                        if llave not in areas_sumatoria:
                            areas_sumatoria[llave] = 0
                            areas_conteo[llave] = 0
                            
                        areas_sumatoria[llave] += porcentaje_area
                        areas_conteo[llave] += 1

            except Exception:
                pass

    mejores_areas = {}
    for llave in areas_sumatoria:
        mejores_areas[llave] = round(areas_sumatoria[llave] / areas_conteo[llave], 1)

    # 3. Contar preguntas que este estudiante obligó a revisión (si las tuviéramos atadas a usuario, 
    # por ahora la base de datos de Reactivos reportados no guarda QUIÉN la reportó, 
    # se podría adaptar en un futuro o dejar a 0).
    preguntas_reportadas = Reactivo.query.filter_by(reportado=True).count() # Dato global tentativo

    # 4. Formatear y enviar histórico puntual
    historial = [{
         "fecha": r.fecha.strftime("%Y-%m-%d %H:%M"),
         "area": r.tipo_examen,
         "calificacion": r.calificacion_global
    } for r in resultados]

    return jsonify({
        "estudiante": resultados[0].nombre_estudiante,
        "estadisticas": {
            "total_examenes": total_examenes,
            "promedio_global": promedio_global,
            "tiempo_extra_solicitado": tiempo_extra_historico,
            "preguntas_enviadas_revision": "N/A" # Actualmente los reportes son anónimos
        },
        "mejores_por_area": mejores_areas,
        "historial": historial
    }), 200

@app.route('/estadisticas-globales', methods=['GET'])
def obtener_estadisticas_globales():
    resultados = Resultado.query.all()
    
    if not resultados:
        return jsonify({"promedios_area": {}, "alumnos": []}), 200
        
    # Calculo global por area
    areas_sumatoria = {}
    areas_conteo = {}
    
    # Calculo por alumno (promedio general)
    alumnos_data = {}
    
    for r in resultados:
        # Sumatoria para los alumnos
        nombre = r.nombre_estudiante.strip().title()
        if nombre not in alumnos_data:
            alumnos_data[nombre] = {"suma_calif": 0, "total_tests": 0}
            
        alumnos_data[nombre]["suma_calif"] += r.calificacion_global
        alumnos_data[nombre]["total_tests"] += 1
        
        # Sumatoria por áreas para el radar general
        if r.detalles:
            try:
                det = json.loads(r.detalles)
                for llave, data in det.items():
                    if llave == 'metricas_extra': continue
                    if data['total'] > 0:
                        porc = (data['correctas'] / data['total']) * 100
                        if llave not in areas_sumatoria:
                            areas_sumatoria[llave] = 0
                            areas_conteo[llave] = 0
                        areas_sumatoria[llave] += porc
                        areas_conteo[llave] += 1
            except Exception:
                pass
                
    # Calcular promedios finales
    promedios_area = {}
    for llave in areas_sumatoria:
        promedios_area[llave] = round(areas_sumatoria[llave] / areas_conteo[llave], 1)
        
    alumnos_lista = []
    for nombre, obj in alumnos_data.items():
        alumnos_lista.append({
            "nombre": nombre,
            "promedio": round(obj["suma_calif"] / obj["total_tests"], 1),
            "total_tests": obj["total_tests"]
        })
        
    # Ordenar por promedio descendente
    alumnos_lista.sort(key=lambda x: x["promedio"], reverse=True)

    return jsonify({
        "promedios_area": promedios_area,
        "alumnos": alumnos_lista
    }), 200

@app.route('/configuracion', methods=['GET'])
def obtener_configuracion():
    conf = Configuracion.query.first()
    if not conf:
        conf = Configuracion()
        db.session.add(conf)
        db.session.commit()
    return jsonify(conf.to_dict())

@app.route('/configuracion', methods=['POST'])
def actualizar_configuracion():
    data = request.json
    conf = Configuracion.query.first()
    if not conf:
        conf = Configuracion()
    
    if 'entrenamiento_preguntas' in data:
        conf.entrenamiento_preguntas = int(data['entrenamiento_preguntas'])
    if 'entrenamiento_minutos' in data:
        conf.entrenamiento_minutos = int(data['entrenamiento_minutos'])
    if 'concentracion_preguntas' in data:
        conf.concentracion_preguntas = int(data['concentracion_preguntas'])
    if 'concentracion_minutos' in data:
        conf.concentracion_minutos = int(data['concentracion_minutos'])
    if 'maraton_preguntas' in data:
        conf.maraton_preguntas = int(data['maraton_preguntas'])
    if 'maraton_minutos' in data:
        conf.maraton_minutos = int(data['maraton_minutos'])

    if 'correo_supervisor' in data:
        conf.correo_supervisor = data['correo_supervisor'].strip()
    if 'filtro_referencia' in data:
        conf.filtro_referencia = data['filtro_referencia'].strip()
        
    db.session.add(conf)
    db.session.commit()
    return jsonify({"mensaje": "Configuración guardada", "config": conf.to_dict()})

def enviar_correo_helper(asunto, html_content, destinatarios):
    smtp_server = "mail.terian.com.mx"
    smtp_port = 465
    sender_email = "oci@terian.com.mx"
    sender_password = os.getenv('SMTP_PASSWORD', 'oci1$7913X4')
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = destinatarios
    msg['Subject'] = asunto
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender_email, sender_password)
        dest_list = [email.strip() for email in destinatarios.split(',') if email.strip()]
        if dest_list:
            server.sendmail(sender_email, dest_list, msg.as_string())
        server.quit()
        return True, "Enviado"
    except Exception as e:
        print(f"Error enviando correo SMTP: {str(e)}")
        return False, str(e)

@app.route('/reportar-pregunta', methods=['POST'])
def reportar_pregunta():
    data = request.json
    reactivo_id = data.get('reactivo_id')
    if not reactivo_id:
        return jsonify({"error": "Falta el ID del reactivo"}), 400
        
    reactivo = Reactivo.query.get(reactivo_id)
    if not reactivo:
        return jsonify({"error": "Reactivo no encontrado"}), 404
        
    # Marcar como reportado en la BD
    reactivo.reportado = True
    reactivo.revisado = False
    db.session.commit()
    
    # Preparar el contenido
    area_nombre = reactivo.area.nombre if reactivo.area else 'General'
    lectura_texto = reactivo.lectura or "No aplica"
    
    opciones_texto = "<ul>"
    for op in reactivo.opciones:
        marca = "✅ (Correcta)" if op.es_correcta else "❌"
        opciones_texto += f"<li>{op.texto_opcion} - <strong>{marca}</strong></li>"
    opciones_texto += "</ul>"
    
    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #4f46e5;">Reporte de Revisión de Pregunta</h2>
        <p>Se ha solicitado la revisión de la siguiente pregunta en la plataforma.</p>
        
        <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
            <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9; width: 150px;"><strong>ID / Identificador:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{reactivo.identificador or reactivo.id}</td></tr>
            <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Área:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{area_nombre}</td></tr>
            <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Origen:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{reactivo.referencia or 'No aplica'} (Pág. {reactivo.pagina or '-'})</td></tr>
            <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Lectura de Ref.:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{lectura_texto}</td></tr>
            <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Planteamiento:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{reactivo.planteamiento}</td></tr>
            <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Opciones:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{opciones_texto}</td></tr>
            <tr><td style="padding: 10px; border: 1px solid #ccc; background-color: #f9f9f9;"><strong>Retroalimentación:</strong></td><td style="padding: 10px; border: 1px solid #ccc;">{reactivo.retroalimentacion}</td></tr>
        </table>
      </body>
    </html>
    """
    
    asunto = f"OCI / Revision de Pregunta {reactivo.identificador or reactivo.id}"
    exito, msj_error = enviar_correo_helper(asunto, html, "oci@terian.com.mx")
    
    if exito:
        return jsonify({"mensaje": "Reporte enviado por correo con éxito"}), 200
    else:
        return jsonify({"error": "No se pudo enviar el correo de reporte al supervisor, pero se guardó en el sistema", "detalle": msj_error}), 500

@app.route('/admin/reactivo/imagen/<int:reactivo_id>', methods=['POST'])
def subir_imagen_reactivo(reactivo_id):
    reactivo = Reactivo.query.get(reactivo_id)
    if not reactivo:
        return jsonify({"error": "Reactivo no encontrado"}), 404
        
    if 'imagen' not in request.files:
        return jsonify({"error": "No se envió ninguna imagen"}), 400
        
    file = request.files['imagen']
    if file.filename == '':
        return jsonify({"error": "No se seleccionó ningún archivo"}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(f"reactivo_{reactivo_id}_{int(datetime.now().timestamp())}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Guardar url (ruta accesible públicamente)
        reactivo.imagen_url = f"/api/uploads/{filename}"
        db.session.commit()
        return jsonify({"mensaje": "Imagen subida correctamente", "imagen_url": reactivo.imagen_url}), 200
        
    return jsonify({"error": "Tipo de archivo no permitido"}), 400

@app.route('/admin/preguntas-reportadas', methods=['GET'])
def obtener_preguntas_reportadas():
    preguntas = Reactivo.query.filter_by(reportado=True).all()
    return jsonify([p.to_dict() for p in preguntas])

@app.route('/referencias', methods=['GET'])
def obtener_referencias():
    try:
        ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'public', 'referencias')
        if not os.path.exists(ruta):
            return jsonify([])
        archivos = [f for f in os.listdir(ruta) if f.endswith('.pdf')]
        return jsonify(archivos)
    except Exception as e:
        return jsonify([])

@app.route('/admin/reactivo/<int:id>', methods=['PUT'])
def actualizar_reactivo(id):
    data = request.json
    reactivo = Reactivo.query.get(id)
    if not reactivo:
        return jsonify({"error": "Reactivo no encontrado"}), 404
        
    if 'planteamiento' in data: reactivo.planteamiento = data['planteamiento']
    if 'lectura' in data: reactivo.lectura = data['lectura']
    if 'referencia' in data: reactivo.referencia = data['referencia']
    if 'pagina' in data: reactivo.pagina = data['pagina']
    if 'imagen_url' in data: reactivo.imagen_url = data['imagen_url']
    if 'retroalimentacion' in data: reactivo.retroalimentacion = data['retroalimentacion']
    if 'revisado_por' in data: reactivo.revisado_por = data['revisado_por']
    
    if 'opciones' in data:
        # data['opciones'] debe ser una lista de diccionarios {id, texto_opcion, es_correcta}
        # Actualizamos opciones existentes
        for op_data in data['opciones']:
            opciones_db = [o for o in reactivo.opciones if o.id == op_data.get('id')]
            if opciones_db:
                op_db = opciones_db[0]
                if 'texto_opcion' in op_data: op_db.texto_opcion = op_data['texto_opcion']
                if 'es_correcta' in op_data: op_db.es_correcta = op_data['es_correcta']
                
    # Al ser guardado por un admin, marcamos como revisado y quitamos la bandera de reportado
    reactivo.reportado = False
    reactivo.revisado = True
    
    db.session.commit()
    return jsonify({"mensaje": "Reactivo actualizado correctamente", "reactivo": reactivo.to_dict()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)