import os
import json
import random
from datetime import datetime
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, flash)
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
app.secret_key = os.environ.get('SECRET_KEY', 'simulador-derecho-ufv-2024-secreto')
basedir = os.path.abspath(os.path.dirname(__file__))

# Use DATABASE_URL env var if set (points to persistent disk on Render)
# Otherwise fallback to local file for development
_db_file = os.environ.get('DATABASE_URL', os.path.join(basedir, 'simulador.db'))
if not _db_file.startswith('sqlite'):
    _db_file = f'sqlite:///{_db_file}'
app.config['SQLALCHEMY_DATABASE_URI'] = _db_file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join('/tmp', 'flask_sessions_simulador')
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_FILE_THRESHOLD'] = 500

os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

db = SQLAlchemy(app)
Session(app)

# ─── MODELS ───────────────────────────────────────────────────────────────────
class Question(db.Model):
    __tablename__ = 'questions'
    id         = db.Column(db.Integer, primary_key=True)
    num        = db.Column(db.Integer)
    question   = db.Column(db.Text, nullable=False)
    option_a   = db.Column(db.Text, nullable=False)
    option_b   = db.Column(db.Text, nullable=False)
    option_c   = db.Column(db.Text, nullable=False)
    option_d   = db.Column(db.Text, default='')
    correct    = db.Column(db.String(1), nullable=False)
    category   = db.Column(db.String(100), default='General')

class ExamSession(db.Model):
    __tablename__ = 'exam_sessions'
    id           = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(200), nullable=False)
    start_time   = db.Column(db.DateTime, default=datetime.utcnow)
    end_time     = db.Column(db.DateTime)
    score        = db.Column(db.Integer, default=0)
    total        = db.Column(db.Integer, default=100)
    passed       = db.Column(db.Boolean, default=False)
    answers_json = db.Column(db.Text)

    def get_answers(self):
        try:
            return json.loads(self.answers_json) if self.answers_json else []
        except Exception:
            return []

    def get_by_category(self):
        by_cat = {}
        for r in self.get_answers():
            cat = r.get('category', 'General')
            if cat not in by_cat:
                by_cat[cat] = {'correct': 0, 'total': 0}
            by_cat[cat]['total'] += 1
            if r.get('is_correct'):
                by_cat[cat]['correct'] += 1
        return by_cat

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True)
    password_hash = db.Column(db.String(256))

# ─── DB FUNCTIONS ─────────────────────────────────────────────────────────────
def load_questions_from_json():
    data_path = os.path.join(basedir, 'data', 'questions.json')
    if not os.path.exists(data_path):
        return 0
    with open(data_path, encoding='utf-8') as f:
        qs = json.load(f)
    Question.query.delete()
    db.session.commit()
    for q in qs:
        db.session.add(Question(
            num=q.get('num'),
            question=q['question'],
            option_a=q['option_a'],
            option_b=q['option_b'],
            option_c=q['option_c'],
            option_d=q.get('option_d', ''),
            correct=q['correct'],
            category=q.get('category', 'General'),
        ))
    db.session.commit()
    print(f"[DB] Recargadas {len(qs)} preguntas.")
    return len(qs)


def init_db():
    db.create_all()
    if not AdminUser.query.filter_by(username='admin').first():
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'derecho2024')
        db.session.add(AdminUser(
            username='admin',
            password_hash=generate_password_hash(admin_pass)
        ))
        db.session.commit()
    data_path = os.path.join(basedir, 'data', 'questions.json')
    if os.path.exists(data_path):
        with open(data_path, encoding='utf-8') as f:
            qs_json = json.load(f)
        db_count = Question.query.count()
        if db_count != len(qs_json):
            print(f"[DB] BD={db_count}, JSON={len(qs_json)}. Actualizando...")
            load_questions_from_json()
        else:
            print(f"[DB] BD al día: {db_count} preguntas.")

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import session
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ─── RUTAS PÚBLICAS ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    total_q = Question.query.count()
    return render_template('index.html', total_q=total_q)


@app.route('/start', methods=['POST'])
def start_exam():
    from flask import session
    name = request.form.get('student_name', '').strip()
    if not name:
        flash('Por favor ingrese su nombre para continuar.', 'error')
        return redirect(url_for('index'))
    all_questions = Question.query.all()
    if len(all_questions) < 5:
        flash('No hay suficientes preguntas. Contacte al administrador.', 'error')
        return redirect(url_for('index'))
    selected = random.sample(all_questions, min(100, len(all_questions)))
    exam_questions = []
    for q in selected:
        options = [('a', q.option_a), ('b', q.option_b), ('c', q.option_c)]
        if q.option_d and q.option_d.strip():
            options.append(('d', q.option_d))
        correct_text = dict(options).get(q.correct, q.option_a)
        random.shuffle(options)
        remapped = {}
        new_correct = 'a'
        for idx, (_, text) in enumerate(options):
            new_l = ['a', 'b', 'c', 'd'][idx]
            remapped[new_l] = text
            if text == correct_text:
                new_correct = new_l
        exam_questions.append({
            'id': q.id, 'question': q.question, 'category': q.category,
            'option_a': remapped.get('a', ''), 'option_b': remapped.get('b', ''),
            'option_c': remapped.get('c', ''), 'option_d': remapped.get('d', ''),
            'correct': new_correct,
        })
    session['exam_name']      = name
    session['exam_questions'] = exam_questions
    session['exam_start']     = datetime.utcnow().isoformat()
    session['exam_answers']   = {}
    return redirect(url_for('exam', page=1))


@app.route('/exam')
@app.route('/exam/<int:page>')
def exam(page=1):
    from flask import session
    if 'exam_questions' not in session:
        flash('No hay un examen activo. Por favor inicie uno nuevo.', 'error')
        return redirect(url_for('index'))
    questions   = session['exam_questions']
    per_page    = 10
    total_pages = max(1, (len(questions) + per_page - 1) // per_page)
    page        = max(1, min(page, total_pages))
    start       = (page - 1) * per_page
    page_questions = questions[start:start + per_page]
    for i, q in enumerate(page_questions):
        q['global_index'] = start + i + 1
    answered = session.get('exam_answers', {})
    return render_template('exam.html',
        questions=page_questions, current_page=page, total_pages=total_pages,
        total_questions=len(questions), answered_count=len(answered),
        student_name=session.get('exam_name', ''), answered=answered)


@app.route('/save_answer', methods=['POST'])
def save_answer():
    from flask import session
    if 'exam_questions' not in session:
        return jsonify({'error': 'No exam active'}), 400
    data    = request.get_json()
    q_index = str(data.get('question_index'))
    answer  = data.get('answer')
    answers = session.get('exam_answers', {})
    answers[q_index] = answer
    session['exam_answers'] = answers
    return jsonify({'answered': len(answers), 'total': len(session['exam_questions'])})


@app.route('/submit', methods=['POST'])
def submit_exam():
    from flask import session
    if 'exam_questions' not in session:
        return redirect(url_for('index'))
    questions    = session['exam_questions']
    answers      = session.get('exam_answers', {})
    student_name = session.get('exam_name', 'Estudiante')
    score   = 0
    results = []
    for i, q in enumerate(questions):
        given      = answers.get(str(i + 1))
        correct    = q['correct']
        is_correct = (given == correct)
        if is_correct:
            score += 1
        results.append({
            'num': i+1, 'question': q['question'], 'category': q['category'],
            'given': given, 'correct': correct, 'is_correct': is_correct,
            'option_a': q['option_a'], 'option_b': q['option_b'],
            'option_c': q['option_c'], 'option_d': q['option_d'],
        })
    total    = len(questions)
    passed   = score >= 70
    end_time = datetime.utcnow()
    # GUARDAR PERMANENTEMENTE EN BD
    record = ExamSession(
        student_name=student_name,
        start_time=datetime.fromisoformat(session['exam_start']),
        end_time=end_time, score=score, total=total, passed=passed,
        answers_json=json.dumps(results, ensure_ascii=False),
    )
    db.session.add(record)
    db.session.commit()
    # Limpiar sesión del examen
    session.pop('exam_questions', None)
    session.pop('exam_answers',   None)
    session.pop('exam_name',      None)
    session.pop('exam_start',     None)
    # Solo guardar el ID — los datos vienen de BD
    session['last_exam_id'] = record.id
    return redirect(url_for('results'))


@app.route('/results')
@app.route('/results/<int:exam_id>')
def results(exam_id=None):
    from flask import session
    if exam_id is None:
        exam_id = session.get('last_exam_id')
    if not exam_id:
        flash('No se encontró el examen. Por favor inicie uno nuevo.', 'error')
        return redirect(url_for('index'))
    record = ExamSession.query.get(exam_id)
    if not record:
        flash('No se encontró el examen en la base de datos.', 'error')
        return redirect(url_for('index'))
    return render_template('results.html',
        exam_id=record.id, student_name=record.student_name,
        score=record.score, total=record.total, passed=record.passed,
        end_time=record.end_time,
        results=record.get_answers(), by_category=record.get_by_category())


# ─── RUTAS ADMIN ──────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    from flask import session
    if request.method == 'POST':
        user = AdminUser.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        flash('Usuario o contraseña incorrectos.', 'error')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
    from flask import session
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_q      = Question.query.count()
    total_exams  = ExamSession.query.count()
    passed_exams = ExamSession.query.filter_by(passed=True).count()
    failed_exams = ExamSession.query.filter_by(passed=False).count()
    avg_score    = db.session.query(db.func.avg(ExamSession.score)).scalar()
    avg_score    = round(avg_score, 1) if avg_score else 0
    recent_exams = ExamSession.query.order_by(ExamSession.end_time.desc()).limit(20).all()
    cats = db.session.query(Question.category, db.func.count(Question.id))\
               .group_by(Question.category).all()
    return render_template('admin/dashboard.html',
        total_q=total_q, total_exams=total_exams,
        passed_exams=passed_exams, failed_exams=failed_exams,
        avg_score=avg_score, recent_exams=recent_exams, categories=cats)


@app.route('/admin/reload-questions', methods=['GET', 'POST'])
@admin_required
def admin_reload_questions():
    if request.method == 'POST':
        count = load_questions_from_json()
        flash(f'✅ Base de datos actualizada con {count} preguntas.', 'success')
        return redirect(url_for('admin_dashboard'))
    data_path  = os.path.join(basedir, 'data', 'questions.json')
    json_count = 0
    if os.path.exists(data_path):
        with open(data_path, encoding='utf-8') as f:
            json_count = len(json.load(f))
    db_count = Question.query.count()
    return render_template('admin/reload.html', json_count=json_count, db_count=db_count)


@app.route('/admin/questions')
@admin_required
def admin_questions():
    page       = request.args.get('page', 1, type=int)
    search     = request.args.get('search', '')
    cat_filter = request.args.get('category', '')
    q = Question.query
    if search:
        q = q.filter(Question.question.ilike(f'%{search}%'))
    if cat_filter:
        q = q.filter(Question.category == cat_filter)
    questions  = q.order_by(Question.num).paginate(page=page, per_page=20, error_out=False)
    categories = [c[0] for c in db.session.query(Question.category).distinct().all()]
    return render_template('admin/questions.html',
        questions=questions, search=search, cat_filter=cat_filter, categories=categories)


@app.route('/admin/questions/add', methods=['GET', 'POST'])
@admin_required
def admin_add_question():
    if request.method == 'POST':
        db.session.add(Question(
            question=request.form['question'],
            option_a=request.form['option_a'], option_b=request.form['option_b'],
            option_c=request.form['option_c'], option_d=request.form.get('option_d', ''),
            correct=request.form['correct'],
            category=request.form.get('category', 'General'),
        ))
        db.session.commit()
        flash('Pregunta agregada exitosamente.', 'success')
        return redirect(url_for('admin_questions'))
    categories = [c[0] for c in db.session.query(Question.category).distinct().all()]
    return render_template('admin/question_form.html', question=None, categories=categories)


@app.route('/admin/questions/edit/<int:qid>', methods=['GET', 'POST'])
@admin_required
def admin_edit_question(qid):
    q = Question.query.get_or_404(qid)
    if request.method == 'POST':
        q.question = request.form['question']
        q.option_a = request.form['option_a']; q.option_b = request.form['option_b']
        q.option_c = request.form['option_c']; q.option_d = request.form.get('option_d', '')
        q.correct  = request.form['correct']
        q.category = request.form.get('category', 'General')
        db.session.commit()
        flash('Pregunta actualizada.', 'success')
        return redirect(url_for('admin_questions'))
    categories = [c[0] for c in db.session.query(Question.category).distinct().all()]
    return render_template('admin/question_form.html', question=q, categories=categories)


@app.route('/admin/questions/delete/<int:qid>', methods=['POST'])
@admin_required
def admin_delete_question(qid):
    db.session.delete(Question.query.get_or_404(qid))
    db.session.commit()
    flash('Pregunta eliminada.', 'success')
    return redirect(url_for('admin_questions'))


@app.route('/admin/questions/import', methods=['GET', 'POST'])
@admin_required
def admin_import():
    if request.method == 'POST':
        file = request.files.get('csv_file')
        if not file:
            flash('No se seleccionó ningún archivo.', 'error')
            return redirect(url_for('admin_import'))
        import csv, io
        reader = csv.DictReader(io.StringIO(file.read().decode('utf-8')))
        count = 0
        for row in reader:
            if row.get('pregunta', '').strip():
                db.session.add(Question(
                    question=row.get('pregunta', '').strip(),
                    option_a=row.get('opcion_a', '').strip(),
                    option_b=row.get('opcion_b', '').strip(),
                    option_c=row.get('opcion_c', '').strip(),
                    option_d=row.get('opcion_d', '').strip(),
                    correct=row.get('respuesta_correcta', 'a').strip().lower(),
                    category=row.get('categoria', 'General').strip(),
                ))
                count += 1
        db.session.commit()
        flash(f'{count} preguntas importadas.', 'success')
        return redirect(url_for('admin_questions'))
    return render_template('admin/import.html')


@app.route('/admin/stats')
@admin_required
def admin_stats():
    search       = request.args.get('search', '').strip()
    result       = request.args.get('result', '')
    page         = request.args.get('page', 1, type=int)
    q = ExamSession.query
    if search:
        q = q.filter(ExamSession.student_name.ilike(f'%{search}%'))
    if result == 'passed':
        q = q.filter_by(passed=True)
    elif result == 'failed':
        q = q.filter_by(passed=False)
    # ALL exams as a simple list (no pagination issues)
    all_sessions = q.order_by(ExamSession.end_time.desc()).all()
    total_exams  = ExamSession.query.count()
    passed_count = ExamSession.query.filter_by(passed=True).count()
    failed_count = ExamSession.query.filter_by(passed=False).count()
    return render_template('admin/stats.html',
        sessions=all_sessions, search=search, result=result,
        total_exams=total_exams, passed_count=passed_count, failed_count=failed_count)


@app.route('/admin/exams/<int:session_id>')
@admin_required
def admin_exam_detail(session_id):
    record      = ExamSession.query.get_or_404(session_id)
    answers     = record.get_answers()
    by_category = record.get_by_category()
    return render_template('admin/exam_detail.html',
        exam=record, answers=answers, by_category=by_category)


@app.route('/admin/exams/delete/<int:session_id>', methods=['POST'])
@admin_required
def admin_delete_exam(session_id):
    record = ExamSession.query.get_or_404(session_id)
    db.session.delete(record)
    db.session.commit()
    flash('Examen eliminado.', 'success')
    return redirect(url_for('admin_stats'))


# ─── INICIO ───────────────────────────────────────────────────────────────────
with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)


# RUTA AÑADIDA AL FINAL — reemplaza la función admin_stats existente
# y agrega diagnóstico

@app.route('/admin/debug')
@admin_required  
def admin_debug():
    """Diagnóstico: muestra estado real de la BD."""
    total_q  = Question.query.count()
    total_ex = ExamSession.query.count()
    exams    = ExamSession.query.order_by(ExamSession.id.desc()).limit(20).all()
    db_uri   = app.config['SQLALCHEMY_DATABASE_URI']
    lines    = [
        "=== DIAGNÓSTICO BASE DE DATOS ===",
        f"Ruta BD: {db_uri}",
        f"Total preguntas: {total_q}",
        f"Total exámenes guardados: {total_ex}",
        "",
        "--- Últimos 20 exámenes ---",
    ]
    if exams:
        for e in exams:
            lines.append(
                f"ID={e.id} | Estudiante='{e.student_name}' | "
                f"Puntaje={e.score}/{e.total} | "
                f"{'APROBADO' if e.passed else 'REPROBADO'} | "
                f"Fecha={e.end_time} | "
                f"Respuestas={'SI' if e.answers_json else 'NO'}"
            )
    else:
        lines.append("*** LA TABLA exam_sessions ESTÁ VACÍA ***")
        lines.append("Razón probable: Render reinició y la BD se borró,")
        lines.append("o los exámenes se guardaron en una instancia diferente.")
    return "<pre style='font-family:monospace;padding:2rem;font-size:14px;line-height:1.6'>" + \
           "\n".join(lines) + "</pre>"
