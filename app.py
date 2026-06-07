import os
import json
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
app.secret_key = os.environ.get('SECRET_KEY', 'simulador-derecho-ufv-2024-secret-key')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'simulador.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'num': self.num,
            'question': self.question,
            'option_a': self.option_a, 'option_b': self.option_b,
            'option_c': self.option_c, 'option_d': self.option_d,
            'correct': self.correct, 'category': self.category,
        }

class ExamSession(db.Model):
    __tablename__ = 'exam_sessions'
    id           = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(200))
    start_time   = db.Column(db.DateTime, default=datetime.utcnow)
    end_time     = db.Column(db.DateTime)
    score        = db.Column(db.Integer)
    total        = db.Column(db.Integer)
    passed       = db.Column(db.Boolean)
    answers_json = db.Column(db.Text)

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

# ─── DB INIT ──────────────────────────────────────────────────────────────────
def init_db():
    db.create_all()
    if not AdminUser.query.filter_by(username='admin').first():
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'derecho2024')
        db.session.add(AdminUser(
            username='admin',
            password_hash=generate_password_hash(admin_pass)
        ))
        db.session.commit()

    if Question.query.count() == 0:
        data_path = os.path.join(basedir, 'data', 'questions.json')
        if os.path.exists(data_path):
            with open(data_path, encoding='utf-8') as f:
                qs = json.load(f)
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
            print(f"[DB] Cargadas {len(qs)} preguntas.")

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ─── RUTAS PÚBLICAS ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    total_q = Question.query.count()
    return render_template('index.html', total_q=total_q)


@app.route('/start', methods=['GET', 'POST'])
def start_exam():
    if request.method == 'GET':
        return redirect(url_for('index'))

    name = request.form.get('student_name', '').strip()
    if not name:
        flash('Por favor ingrese su nombre para continuar.', 'error')
        return redirect(url_for('index'))

    all_questions = Question.query.all()
    if len(all_questions) < 5:
        flash('No hay suficientes preguntas en la base de datos. Contacte al administrador.', 'error')
        return redirect(url_for('index'))

    # Seleccionar hasta 100 preguntas aleatorias
    selected = random.sample(all_questions, min(100, len(all_questions)))

    exam_questions = []
    for q in selected:
        # Construir lista de opciones disponibles
        options = [('a', q.option_a), ('b', q.option_b), ('c', q.option_c)]
        if q.option_d:
            options.append(('d', q.option_d))

        correct_text = dict(options).get(q.correct, q.option_a)
        random.shuffle(options)

        new_letters = ['a', 'b', 'c', 'd']
        remapped = {}
        new_correct = 'a'
        for idx, (orig_letter, text) in enumerate(options):
            new_l = new_letters[idx]
            remapped[new_l] = text
            if text == correct_text:
                new_correct = new_l

        exam_questions.append({
            'id': q.id,
            'question': q.question,
            'category': q.category,
            'option_a': remapped.get('a', ''),
            'option_b': remapped.get('b', ''),
            'option_c': remapped.get('c', ''),
            'option_d': remapped.get('d', ''),
            'correct': new_correct,
        })

    session.clear()
    session['exam'] = {
        'student_name': name,
        'questions': exam_questions,
        'start_time': datetime.utcnow().isoformat(),
        'answers': {},
    }
    session.modified = True
    return redirect(url_for('exam', page=1))


@app.route('/exam')
@app.route('/exam/<int:page>')
def exam(page=1):
    exam_data = session.get('exam')
    if not exam_data:
        flash('No hay un examen activo. Por favor inicie uno nuevo.', 'error')
        return redirect(url_for('index'))

    questions = exam_data['questions']
    per_page = 10
    total_pages = max(1, (len(questions) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    page_questions = questions[start:start + per_page]
    for i, q in enumerate(page_questions):
        q['global_index'] = start + i + 1

    answered = exam_data.get('answers', {})

    return render_template(
        'exam.html',
        questions=page_questions,
        current_page=page,
        total_pages=total_pages,
        total_questions=len(questions),
        answered_count=len(answered),
        student_name=exam_data['student_name'],
        answered=answered,
    )


@app.route('/save_answer', methods=['POST'])
def save_answer():
    exam_data = session.get('exam')
    if not exam_data:
        return jsonify({'error': 'No exam active'}), 400
    data = request.get_json()
    q_index = str(data.get('question_index'))
    answer  = data.get('answer')
    exam_data['answers'][q_index] = answer
    session['exam'] = exam_data
    session.modified = True
    answered_count = len(exam_data['answers'])
    total = len(exam_data['questions'])
    return jsonify({'answered': answered_count, 'total': total})


@app.route('/submit', methods=['POST'])
def submit_exam():
    exam_data = session.get('exam')
    if not exam_data:
        return redirect(url_for('index'))

    questions    = exam_data['questions']
    answers      = exam_data.get('answers', {})
    student_name = exam_data['student_name']

    score   = 0
    results = []
    for i, q in enumerate(questions):
        given      = answers.get(str(i + 1))
        correct    = q['correct']
        is_correct = (given == correct)
        if is_correct:
            score += 1
        results.append({
            'num': i + 1, 'question': q['question'], 'category': q['category'],
            'given': given, 'correct': correct, 'is_correct': is_correct,
            'option_a': q['option_a'], 'option_b': q['option_b'],
            'option_c': q['option_c'], 'option_d': q['option_d'],
        })

    total  = len(questions)
    passed = score >= 70
    end_time = datetime.utcnow()

    record = ExamSession(
        student_name=student_name,
        start_time=datetime.fromisoformat(exam_data['start_time']),
        end_time=end_time,
        score=score, total=total, passed=passed,
        answers_json=json.dumps(results, ensure_ascii=False),
    )
    db.session.add(record)
    db.session.commit()

    by_category = {}
    for r in results:
        cat = r['category']
        if cat not in by_category:
            by_category[cat] = {'correct': 0, 'total': 0}
        by_category[cat]['total'] += 1
        if r['is_correct']:
            by_category[cat]['correct'] += 1

    session['results'] = {
        'student_name': student_name,
        'score': score, 'total': total, 'passed': passed,
        'results': results, 'by_category': by_category,
        'session_id': record.id,
    }
    session.pop('exam', None)
    session.modified = True
    return redirect(url_for('results'))


@app.route('/results')
def results():
    result_data = session.get('results')
    if not result_data:
        return redirect(url_for('index'))
    return render_template('results.html', **result_data)


# ─── RUTAS ADMIN ──────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = AdminUser.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_user'] = username
            return redirect(url_for('admin_dashboard'))
        flash('Usuario o contraseña incorrectos.', 'error')
    return render_template('admin/login.html')


@app.route('/admin/logout')
def admin_logout():
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
    cats = db.session.query(Question.category, db.func.count(Question.id)).group_by(Question.category).all()
    return render_template('admin/dashboard.html',
        total_q=total_q, total_exams=total_exams,
        passed_exams=passed_exams, failed_exams=failed_exams,
        avg_score=avg_score, recent_exams=recent_exams, categories=cats)


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
            q = Question(
                question=row.get('pregunta','').strip(),
                option_a=row.get('opcion_a','').strip(),
                option_b=row.get('opcion_b','').strip(),
                option_c=row.get('opcion_c','').strip(),
                option_d=row.get('opcion_d','').strip(),
                correct=row.get('respuesta_correcta','a').strip().lower(),
                category=row.get('categoria','General').strip(),
            )
            if q.question and q.option_a:
                db.session.add(q); count += 1
        db.session.commit()
        flash(f'{count} preguntas importadas.', 'success')
        return redirect(url_for('admin_questions'))
    return render_template('admin/import.html')


@app.route('/admin/stats')
@admin_required
def admin_stats():
    sessions = ExamSession.query.order_by(ExamSession.end_time.desc()).limit(50).all()
    return render_template('admin/stats.html', sessions=sessions)


# ─── INICIO ───────────────────────────────────────────────────────────────────
with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

             
