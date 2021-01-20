FROM python:3.7-slim
ENV PYTHONUNBUFFERED 1
RUN mkdir /tom
WORKDIR /tom
COPY requirements.txt /tom/
RUN pip install -r requirements.txt
RUN pip install https://github.com/thusser/tom_iag/archive/main.zip
COPY . /tom/
#RUN python manage.py collectstatic --noinput
CMD gunicorn --bind 0.0.0.0:8000 --worker-tmp-dir /dev/shm --workers=2 --threads=4 --worker-class=gthread exotom.wsgi
