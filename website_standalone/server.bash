#!/bin/sh

## as Daemon listening for HTTPS on 443
#gunicorn -D --certfile /etc/letsencrypt/live/satorinet.io/fullchain.pem --keyfile /etc/letsencrypt/live/satorinet.io/privkey.pem -b 0.0.0.0:443 app:app
gunicorn -c gunicorn.py -D -b 0.0.0.0:443 app:app
#gunicorn -c gunicorn.py -D -b 0.0.0.0:443 -b [::]:443 app:app

## as Daemon listening for HTTP on port 80 - redirect to HTTPS in flask app
gunicorn -D -b 0.0.0.0:80 app:app
#gunicorn -D -b 0.0.0.0:80 -b [::]:80 app:app

## for manual debugging:
# gunicorn --certfile /etc/letsencrypt/live/satorinet.io/fullchain.pem --keyfile /etc/letsencrypt/live/satorinet.io/privkey.pem --log-level=DEBUG -b 0.0.0.0:443 app:app