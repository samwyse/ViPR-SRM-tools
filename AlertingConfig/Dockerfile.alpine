FROM alpine:3.2

RUN apk update
RUN apk add graphviz 
RUN apk add python3
#RUN pip3 install --upgrade pip
RUN pip3 install graphviz

ADD src .

RUN apk add ttf-dejavu

EXPOSE 80

CMD [ "python3", "report.py", "--wsgi", "--port", "80" ]
