import logging

# Specify the log file location
errorlog = "/tmp/server-gunicorn-error.log"
accesslog = "/tmp/server-gunicorn-access.log"
loglevel = "info"

# import multiprocessing
# bind = "127.0.0.1:8000"
# workers = multiprocessing.cpu_count() * 2 + 1
secure_scheme_headers = {'X-FORWARDED-PROTO': 'https'}
forwarded_allow_ips = '*'
# --certfile /etc/letsencrypt/live/satorinet.io/fullchain.pem --keyfile /etc/letsencrypt/live/satorinet.io/privkey.pem
certfile = '/etc/letsencrypt/live/satorinet.io/fullchain.pem'
keyfile = '/etc/letsencrypt/live/satorinet.io/privkey.pem'
# limit gunicorn resources
workers = 1
worker_connections = 100
timeout = 60
