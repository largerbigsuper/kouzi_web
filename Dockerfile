FROM python:3

WORKDIR /kouzi_web
ADD . .
RUN pip install -r requirements.txt
EXPOSE 5000
CMD [ "python", "./app.py"]
