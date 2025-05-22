# /epics_recommendation_flask/app.py

import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import database as db
import datetime
import ml_recommender 
import logging # Importar logging

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key_for_dev_123!@#')

db.init_db()

if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    ml_recommender.inicializar_y_entrenar_recomendador()

@app.context_processor
def inject_now():
    return {'now': datetime.datetime.utcnow()}

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = None
    if user_id is not None:
        user_data = db.query_db('SELECT * FROM Usuarios WHERE id_usuario = %s', (user_id,), one=True)
        if user_data:
            g.user = user_data

@app.route('/register', methods=('GET', 'POST'))
def register():
    if g.user: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        nombre_completo = request.form['nombre_completo']
        email = request.form['email']
        password = request.form['password']
        error = None
        if not nombre_completo: error = 'Nombre completo es requerido.'
        elif not email: error = 'Email es requerido.'
        elif not password: error = 'Contraseña es requerida.'
        if not error:
            existing_user = db.query_db('SELECT id_usuario FROM Usuarios WHERE email = %s', (email,), one=True)
            if existing_user: error = f"El email {email} ya está registrado."
        if error is None:
            try:
                hashed_password = generate_password_hash(password)
                db.execute_db(
                    'INSERT INTO Usuarios (nombre_completo, email, password_hash) VALUES (%s, %s, %s)',
                    (nombre_completo, email, hashed_password)
                )
                newly_inserted_user = db.query_db('SELECT id_usuario FROM Usuarios WHERE email = %s', (email,), one=True)
                if newly_inserted_user:
                    db.execute_db(
                        '''INSERT INTO PerfilesEgresados 
                           (id_usuario, habilidades_texto, experiencia_texto, preferencias_texto, telefono, link_linkedin, link_github, formacion_texto)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                        (newly_inserted_user['id_usuario'], '', '', '', '', '', '', '')
                    )
                else: app.logger.error(f"No se pudo encontrar el usuario {email} para crear perfil.")
                flash('Registro exitoso. Ahora puedes iniciar sesión y completar tu perfil.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                error = f"Error al registrar el usuario: {e}"
                app.logger.error(f"Error en registro: {e}")
        if error: flash(error, 'danger')
    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if g.user: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        error = None
        user = db.query_db('SELECT * FROM Usuarios WHERE email = %s', (email,), one=True)
        if user is None or not check_password_hash(user['password_hash'], password):
            error = 'Email o contraseña incorrectos.'
        if error is None and user:
            session.clear()
            session['user_id'] = user['id_usuario']
            session['nombre_completo'] = user['nombre_completo']
            flash(f'Bienvenido de nuevo, {user["nombre_completo"]}!', 'success')
            return redirect(url_for('dashboard'))
        if error: flash(error, 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login')) if g.user is None else redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if g.user is None:
        flash('Debes iniciar sesión para ver el dashboard.', 'warning')
        return redirect(url_for('login'))
    perfil = db.query_db('SELECT * FROM PerfilesEgresados WHERE id_usuario = %s', (g.user['id_usuario'],), one=True)
    return render_template('dashboard.html', perfil=perfil)

@app.route('/profile', methods=('GET', 'POST'))
def profile():
    if g.user is None:
        flash('Debes iniciar sesión para gestionar tu perfil.', 'warning')
        return redirect(url_for('login'))
    user_id = g.user['id_usuario']
    perfil_existente = db.query_db('SELECT * FROM PerfilesEgresados WHERE id_usuario = %s', (user_id,), one=True)
    if request.method == 'POST':
        habilidades = request.form.get('habilidades_texto', '')
        experiencia = request.form.get('experiencia_texto', '')
        preferencias = request.form.get('preferencias_texto', '')
        telefono = request.form.get('telefono', '')
        linkedin = request.form.get('linkedin', '')
        github = request.form.get('github', '')
        formacion = request.form.get('formacion_texto', '')
        if perfil_existente:
            db.execute_db(
                '''UPDATE PerfilesEgresados SET 
                   habilidades_texto = %s, experiencia_texto = %s, preferencias_texto = %s,
                   telefono = %s, link_linkedin = %s, link_github = %s, formacion_texto = %s,
                   ultima_actualizacion = CURRENT_TIMESTAMP WHERE id_usuario = %s''',
                (habilidades, experiencia, preferencias, telefono, linkedin, github, formacion, user_id)
            )
            flash('Perfil actualizado con éxito.', 'success')
        else:
            db.execute_db(
                '''INSERT INTO PerfilesEgresados (id_usuario, habilidades_texto, experiencia_texto, preferencias_texto, telefono, link_linkedin, link_github, formacion_texto)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                (user_id, habilidades, experiencia, preferencias, telefono, linkedin, github, formacion)
            )
            flash('Perfil creado/actualizado con éxito.', 'success')
        return redirect(url_for('dashboard')) 
    perfil_para_plantilla = perfil_existente if perfil_existente else {
        'habilidades_texto': '', 'experiencia_texto': '', 'preferencias_texto': '',
        'telefono': '', 'link_linkedin': '', 'link_github': '', 'formacion_texto': ''
    }
    return render_template('profile_form.html', perfil=perfil_para_plantilla)

@app.route('/jobs')
def jobs_list():
    if g.user is None:
        flash('Debes iniciar sesión para ver las ofertas laborales.', 'warning')
        return redirect(url_for('login'))
    ofertas = db.query_db('SELECT * FROM OfertasLaborales WHERE activa = TRUE ORDER BY fecha_publicacion DESC')
    return render_template('jobs_list.html', ofertas=ofertas)

@app.route('/recommendations')
def recommendations():
    if g.user is None:
        flash('Debes iniciar sesión para ver tus recomendaciones.', 'warning')
        return redirect(url_for('login'))
    user_id = g.user['id_usuario']
    perfil_usuario = ml_recommender.cargar_perfil_usuario_db(user_id) 
    lista_recomendaciones = []
    if not ml_recommender.recommender_instance.fitted:
        flash('El sistema de recomendación aún no ha sido entrenado o no hay ofertas. Inténtalo más tarde.', 'warning')
        return render_template('recommendations.html', recomendaciones=lista_recomendaciones)
    if perfil_usuario and any(str(perfil_usuario.get(key,"")).strip() for key in ['habilidades_texto', 'experiencia_texto', 'preferencias_texto', 'formacion_texto']):
        app.logger.debug(f"DEBUG: Perfil para recomendación (usuario {user_id}): {perfil_usuario}")
        lista_recomendaciones = ml_recommender.recommender_instance.recommend(perfil_usuario, top_n=5)
        app.logger.debug(f"DEBUG: Recomendaciones generadas: {[r['id_oferta'] for r in lista_recomendaciones]}")
        if not lista_recomendaciones: flash('No se encontraron recomendaciones para tu perfil. Actualiza tu perfil o revisa todas las ofertas.', 'info')
        elif len(lista_recomendaciones) < 3: flash(f'Hemos encontrado {len(lista_recomendaciones)} recomendacion(es).', 'info')
        else: flash(f'Se encontraron {len(lista_recomendaciones)} recomendaciones para ti.', 'success')
    else: flash('Completa tu perfil profesional para recibir recomendaciones.', 'warning')
    return render_template('recommendations.html', recomendaciones=lista_recomendaciones)

@app.route('/add_job', methods=['GET', 'POST'])
def add_job():
    if g.user is None:
        flash('Debes iniciar sesión para añadir ofertas.', 'warning')
        return redirect(url_for('login'))
    if request.method == 'POST':
        titulo = request.form.get('titulo_oferta')
        empresa = request.form.get('empresa_nombre')
        ubicacion = request.form.get('ubicacion')
        descripcion = request.form.get('descripcion_completa_oferta')
        error = None
        if not titulo: error = 'El título de la oferta es requerido.'
        elif not descripcion: error = 'La descripción es requerida.'
        if error is None:
            try:
                db.execute_db(
                    '''INSERT INTO OfertasLaborales (titulo_oferta, empresa_nombre, ubicacion, descripcion_completa_oferta, activa)
                       VALUES (%s, %s, %s, %s, TRUE)''',
                    (titulo, empresa, ubicacion, descripcion)
                )
                ml_recommender.inicializar_y_entrenar_recomendador()
                flash('Oferta laboral añadida y recomendador actualizado.', 'success')
                return redirect(url_for('jobs_list'))
            except Exception as e:
                error = f"Error al añadir la oferta: {e}"
                app.logger.error(f"Error en add_job: {e}")
        if error: flash(error, 'danger')
    return render_template('job_form.html')

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    if debug_mode:
        app.logger.setLevel(logging.DEBUG)
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)