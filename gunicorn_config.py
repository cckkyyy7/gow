import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
timeout = 30
loglevel = "info"
accesslog = "access.log"
errorlog = "error.log"
