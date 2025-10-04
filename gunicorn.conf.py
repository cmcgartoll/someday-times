bind = "0.0.0.0:8080"
workers = 2          # bump to 3–4 if CPU allows
threads = 4
timeout = 60
graceful_timeout = 30
keepalive = 5
preload_app = True