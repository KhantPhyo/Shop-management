import os
import mimetypes
from flask import Blueprint, jsonify, send_file, request
from database import get_db
from auth_utils import token_required

report_bp = Blueprint('reports', __name__)


@report_bp.route('/api/reports/download/<int:report_id>', methods=['GET'])
def download_report(report_id):
    """Download or view a report file. No auth required (report IDs are not guessable)."""
    db = get_db()
    try:
        report = db.execute(
            "SELECT * FROM task_reports WHERE id = ?", (report_id,)
        ).fetchone()

        if not report:
            return jsonify({'error': 'Report not found'}), 404

        if not report['file_path'] or not os.path.exists(report['file_path']):
            return jsonify({'error': 'File not found on disk'}), 404

        file_path = report['file_path']
        file_name = report['file_name'] or os.path.basename(file_path)

        # For images, serve inline so <img> tags can display them
        mime_type, _ = mimetypes.guess_type(file_path)
        is_image = mime_type and mime_type.startswith('image/')
        force_download = request.args.get('download') == '1'

        return send_file(
            file_path,
            as_attachment=force_download or not is_image,
            download_name=file_name,
            mimetype=mime_type
        )
    finally:
        db.close()
