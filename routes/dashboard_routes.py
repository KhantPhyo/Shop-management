from flask import Blueprint, request, jsonify
from database import get_db
from auth_utils import token_required
from datetime import datetime, timedelta

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/api/dashboard/stats', methods=['GET'])
@token_required
def get_stats(current_user):
    db = get_db()
    try:
        stats = db.execute("""
            SELECT
                COUNT(*) as total_tasks_today,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
                SUM(CASE WHEN status = 'accepted' THEN 1 ELSE 0 END) as accepted_count,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_count,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done_count,
                SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue_count,
                SUM(fine_amount_mmk) as total_fines_mmk
            FROM tasks WHERE date(created_at) = date('now')
        """).fetchone()

        shop_counts = db.execute("""
            SELECT COUNT(*) as total_shops,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active_shops
            FROM shops
        """).fetchone()

        return jsonify({
            'total_tasks_today': stats['total_tasks_today'] or 0,
            'pending_count': stats['pending_count'] or 0,
            'accepted_count': stats['accepted_count'] or 0,
            'in_progress_count': stats['in_progress_count'] or 0,
            'done_count': stats['done_count'] or 0,
            'overdue_count': stats['overdue_count'] or 0,
            'total_fines_mmk': stats['total_fines_mmk'] or 0,
            'total_shops': shop_counts['total_shops'] or 0,
            'active_shops': shop_counts['active_shops'] or 0
        })
    finally:
        db.close()


@dashboard_bp.route('/api/dashboard/shop-performance', methods=['GET'])
@token_required
def shop_performance(current_user):
    period = request.args.get('period', 'month')

    date_filter = ""
    if period == 'today':
        date_filter = "AND date(t.created_at) = date('now')"
    elif period == 'week':
        date_filter = "AND t.created_at >= datetime('now', '-7 days')"
    elif period == 'month':
        date_filter = "AND t.created_at >= datetime('now', '-30 days')"

    db = get_db()
    try:
        shops = db.execute(f"""
            SELECT
                s.id as shop_id,
                s.shop_name,
                COUNT(t.id) as total_tasks,
                SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN t.status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN t.status = 'overdue' THEN 1 ELSE 0 END) as overdue,
                AVG(CASE WHEN t.completed_at IS NOT NULL
                    THEN (julianday(t.completed_at) - julianday(t.created_at)) * 24
                    ELSE NULL END) as avg_completion_hours,
                CASE WHEN COUNT(t.id) > 0
                    THEN ROUND(SUM(CASE WHEN t.status = 'done' THEN 1.0 ELSE 0 END) / COUNT(t.id) * 100, 1)
                    ELSE 0 END as completion_rate_percent,
                SUM(COALESCE(t.fine_amount_mmk, 0)) as fines_total_mmk
            FROM shops s
            LEFT JOIN tasks t ON s.id = t.shop_id {date_filter}
            WHERE s.is_active = 1
            GROUP BY s.id
            ORDER BY completion_rate_percent DESC
        """).fetchall()

        return jsonify([{
            'shop_id': s['shop_id'],
            'shop_name': s['shop_name'],
            'total_tasks': s['total_tasks'] or 0,
            'completed': s['completed'] or 0,
            'pending': s['pending'] or 0,
            'overdue': s['overdue'] or 0,
            'avg_completion_hours': round(s['avg_completion_hours'] or 0, 1),
            'completion_rate_percent': s['completion_rate_percent'] or 0,
            'fines_total_mmk': s['fines_total_mmk'] or 0
        } for s in shops])
    finally:
        db.close()


@dashboard_bp.route('/api/dashboard/task-timeline', methods=['GET'])
@token_required
def task_timeline(current_user):
    days = int(request.args.get('days', 7))

    db = get_db()
    try:
        timeline = []
        for i in range(days - 1, -1, -1):
            row = db.execute("""
                SELECT
                    date('now', ? || ' days') as date,
                    SUM(CASE WHEN date(created_at) = date('now', ? || ' days') THEN 1 ELSE 0 END) as created,
                    SUM(CASE WHEN date(completed_at) = date('now', ? || ' days') THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'overdue' AND date(updated_at) = date('now', ? || ' days') THEN 1 ELSE 0 END) as overdue
                FROM tasks
            """, (f'-{i}', f'-{i}', f'-{i}', f'-{i}')).fetchone()

            timeline.append({
                'date': row['date'],
                'created': row['created'] or 0,
                'completed': row['completed'] or 0,
                'overdue': row['overdue'] or 0
            })

        return jsonify(timeline)
    finally:
        db.close()


@dashboard_bp.route('/api/dashboard/kpi', methods=['GET'])
@token_required
def get_kpi(current_user):
    db = get_db()
    try:
        # Fastest shop
        fastest = db.execute("""
            SELECT s.shop_name, AVG((julianday(t.completed_at) - julianday(t.created_at)) * 24) as avg_hours
            FROM tasks t JOIN shops s ON t.shop_id = s.id
            WHERE t.status = 'done' AND t.completed_at IS NOT NULL
            GROUP BY t.shop_id ORDER BY avg_hours ASC LIMIT 1
        """).fetchone()

        # Slowest shop
        slowest = db.execute("""
            SELECT s.shop_name, AVG((julianday(t.completed_at) - julianday(t.created_at)) * 24) as avg_hours
            FROM tasks t JOIN shops s ON t.shop_id = s.id
            WHERE t.status = 'done' AND t.completed_at IS NOT NULL
            GROUP BY t.shop_id ORDER BY avg_hours DESC LIMIT 1
        """).fetchone()

        # Most tasks shop
        most_tasks = db.execute("""
            SELECT s.shop_name, COUNT(t.id) as count
            FROM tasks t JOIN shops s ON t.shop_id = s.id
            GROUP BY t.shop_id ORDER BY count DESC LIMIT 1
        """).fetchone()

        # Highest completion rate
        highest_rate = db.execute("""
            SELECT s.shop_name,
                   ROUND(SUM(CASE WHEN t.status = 'done' THEN 1.0 ELSE 0 END) / COUNT(t.id) * 100, 1) as rate
            FROM tasks t JOIN shops s ON t.shop_id = s.id
            GROUP BY t.shop_id HAVING COUNT(t.id) > 0
            ORDER BY rate DESC LIMIT 1
        """).fetchone()

        # Total fines
        total_fines = db.execute("SELECT SUM(fine_amount_mmk) as total FROM tasks").fetchone()

        # Overdue rate
        overdue_stats = db.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) as overdue
            FROM tasks
        """).fetchone()

        overdue_rate = 0
        if overdue_stats['total'] and overdue_stats['total'] > 0:
            overdue_rate = round((overdue_stats['overdue'] or 0) / overdue_stats['total'] * 100, 1)

        return jsonify({
            'fastest_shop': {
                'shop_name': fastest['shop_name'] if fastest else 'N/A',
                'avg_hours': round(fastest['avg_hours'], 1) if fastest and fastest['avg_hours'] else 0
            },
            'slowest_shop': {
                'shop_name': slowest['shop_name'] if slowest else 'N/A',
                'avg_hours': round(slowest['avg_hours'], 1) if slowest and slowest['avg_hours'] else 0
            },
            'most_tasks_shop': {
                'shop_name': most_tasks['shop_name'] if most_tasks else 'N/A',
                'count': most_tasks['count'] if most_tasks else 0
            },
            'highest_completion_rate': {
                'shop_name': highest_rate['shop_name'] if highest_rate else 'N/A',
                'rate': highest_rate['rate'] if highest_rate else 0
            },
            'total_fines_mmk': total_fines['total'] or 0,
            'overdue_rate_percent': overdue_rate
        })
    finally:
        db.close()
