FROM python:3.6-alpine
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY . .
# EXPOSE 22222
ENTRYPOINT [ "/app/entrypoint.sh" ]
# CMD ["python3", "app.py", "--config_file", "config/sample-config.conf"]