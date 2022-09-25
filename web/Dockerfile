# HBNet Web Service Dockerfile 
FROM debian:11
MAINTAINER Eric Craw "kf7eel@qsl.net"
WORKDIR /opt/hbnet_web

RUN useradd -ms /bin/bash hbnet_web

COPY . .

#Install Python3.9 and dependencies
RUN apt-get -y update; apt-get -y upgrade; apt-get -y install --no-install-recommends python3.9-dev python3-pip python3.9 build-essential net-tools nginx; apt-get clean; rm -rf /var/lib/apt/lists/*

# Remove unnecessary NGINX stuff
RUN rm -f /etc/nginx/fastcgi.conf /etc/nginx/fastcgi_params && \
    rm -f /etc/nginx/snippets/fastcgi-php.conf /etc/nginx/snippets/snakeoil.conf

# Install Supervisor
RUN python3.9 -m pip install --no-cache-dir supervisor

# Install NGINX config
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/hbnet.conf /etc/nginx/sites-enabled/hbnet.conf
COPY docker/nginx_default /etc/nginx/sites-enabled/default
RUN chown -R www-data:www-data /var/log/nginx
COPY docker/wsgi.py /opt/hbnet_web

COPY docker/wsgi.ini /opt/hbnet_web
COPY docker/config.py /opt/hbnet_web
COPY docker/hbnet.sqlite /opt/hbnet_web

RUN mkdir -p /opt/hbnet_web/data

RUN chown -R hbnet_web:hbnet_web /opt/hbnet_web/data/

RUN chown -R hbnet_web:hbnet_web /opt/hbnet_web/

COPY docker/supervisord.conf /etc

# Switch user and install dependencies
USER hbnet_web


#Upgrade PIP
RUN python3.9 -m pip install --upgrade pip

#Install from requirements.txt
RUN python3.9 -m pip install --no-cache-dir -r requirements.txt

EXPOSE 80
EXPOSE 443

#ENTRYPOINT ["/home/hbnet_web/.local/bin/supervisord"]

USER root

CMD ["/usr/local/bin/supervisord", "-n"]
