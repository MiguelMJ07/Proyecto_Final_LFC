# Production image: gunicorn serving the Flask app. Build: docker build -t formal-languages .
# Run:   docker run -p 5000:5000 -v fl-data:/data formal-languages     then open http://localhost:5000
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=5000 SESSIONS_DB=/data/sessions.db
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0
COPY src ./src
COPY cli ./cli
COPY examples ./examples
RUN useradd --create-home app && mkdir /data && chown app /data
USER app
VOLUME /data
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '5000'))"
CMD ["sh", "-c", "exec gunicorn --chdir src --bind 0.0.0.0:${PORT} --workers 2 --threads 4 app:app"]
