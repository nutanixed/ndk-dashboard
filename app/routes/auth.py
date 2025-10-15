"""
Authentication routes
"""
from flask import Blueprint, render_template, request, session, redirect, url_for
from config import Config

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == Config.DASHBOARD_USERNAME and password == Config.DASHBOARD_PASSWORD:
            session['logged_in'] = True
            session.permanent = True
            return redirect(url_for('main.index'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('auth.login'))